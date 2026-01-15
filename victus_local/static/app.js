const statusPill = document.getElementById("status-pill");
const logConsole = document.getElementById("log-console");
const chatInput = document.getElementById("chat-input");
const chatOutput = document.getElementById("chat-output");
const chatSend = document.getElementById("chat-send");
const errorBanner = document.getElementById("error-banner");
let streamingMessage = null;
let streamingText = null;
let activeStreamState = null;

function setStatus(label, state) {
  statusPill.textContent = label;
  statusPill.classList.remove("connected", "busy", "error", "denied");
  if (state) {
    statusPill.classList.add(state);
  }
}

function appendLog(entry) {
  const line = document.createElement("div");
  line.className = "log-entry";
  line.innerHTML = `<span>[${entry.timestamp}]</span> ${entry.event} ${
    entry.data ? JSON.stringify(entry.data) : ""
  }`;
  logConsole.appendChild(line);
  logConsole.scrollTop = logConsole.scrollHeight;
}

function appendChat(speaker, message) {
  const paragraph = document.createElement("p");
  paragraph.innerHTML = `<strong>${speaker}:</strong> ${message}`;
  chatOutput.appendChild(paragraph);
  chatOutput.scrollTop = chatOutput.scrollHeight;
}

function appendActivityLog(event, data = {}) {
  appendLog({
    timestamp: new Date().toISOString(),
    event,
    data,
  });
}

function showErrorBanner(message) {
  if (!errorBanner) {
    return;
  }
  errorBanner.textContent = message;
  errorBanner.classList.remove("hidden");
}

function hideErrorBanner() {
  if (!errorBanner) {
    return;
  }
  errorBanner.textContent = "";
  errorBanner.classList.add("hidden");
}

function isOllamaMemoryError(message) {
  if (!message) {
    return false;
  }
  const lowered = message.toLowerCase();
  return (
    lowered.includes("requires more memory") ||
    lowered.includes("requires more system memory") ||
    lowered.includes("out of memory")
  );
}

function beginStreamMessage() {
  streamingMessage = document.createElement("p");
  streamingText = document.createElement("span");
  streamingMessage.innerHTML = "<strong>Victus:</strong> ";
  streamingMessage.appendChild(streamingText);
  chatOutput.appendChild(streamingMessage);
}

function appendStreamChunk(chunk) {
  if (!streamingMessage) {
    beginStreamMessage();
  }
  streamingText.textContent += chunk;
  chatOutput.scrollTop = chatOutput.scrollHeight;
}

function endStreamMessage() {
  streamingMessage = null;
  streamingText = null;
}

function handleLogEvent(entry) {
  appendLog(entry);
  if (entry.event === "status_update") {
    updateStatus(entry.data.status);
  }
}

function connectWebSocket() {
  const ws = new WebSocket(`ws://${window.location.host}/ws/logs`);

  ws.addEventListener("open", () => {
    setStatus("Connected", "connected");
    ws.send("hello");
  });

  ws.addEventListener("message", (event) => {
    const entry = JSON.parse(event.data);
    handleLogEvent(entry);
  });

  ws.addEventListener("close", () => {
    setStatus("Disconnected", "");
    connectSSE();
  });

  return ws;
}

function connectSSE() {
  const source = new EventSource("/api/logs/stream");
  source.onmessage = (event) => {
    const entry = JSON.parse(event.data);
    handleLogEvent(entry);
  };
  source.onerror = () => {
    setStatus("Disconnected", "");
  };
}

async function sendChat() {
  const message = chatInput.value.trim();
  if (!message) {
    return;
  }
  chatSend.disabled = true;
  hideErrorBanner();
  appendChat("You", message);
  chatInput.value = "";
  activeStreamState = { hasToken: false, hasError: false, hasOutput: false };

  try {
    const response = await fetch("/api/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (!response.ok) {
      const errorMessage = await getResponseErrorMessage(response);
      appendChat("Victus", errorMessage);
      updateStatus("error");
      maybeShowMemoryBanner(errorMessage);
      endStreamMessage();
      return;
    }
    await readTurnStream(response);
  } catch (error) {
    appendChat("Victus", "Network error while contacting server.");
    updateStatus("error");
    endStreamMessage();
  } finally {
    chatSend.disabled = false;
  }
}

async function readTurnStream(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    buffer = parseSseBuffer(buffer);
  }

  if (buffer.trim()) {
    parseSseBuffer(`${buffer}\n\n`);
  }
  activeStreamState = null;
}

function handleTurnEvent(payload) {
  if (payload.event === "status") {
    updateStatus(payload.status);
    return;
  }
  if (payload.event === "token") {
    const textChunk = payload.text ?? payload.token ?? "";
    if (textChunk) {
      appendStreamChunk(textChunk);
    }
    return;
  }
  if (payload.event === "tool_start") {
    appendActivityLog("tool_start", {
      tool: payload.tool,
      action: payload.action,
      args: payload.args,
    });
    appendChat("Victus", formatToolStart(payload));
    return;
  }
  if (payload.event === "tool_done") {
    appendActivityLog("tool_done", {
      tool: payload.tool,
      action: payload.action,
      result: payload.result,
    });
    appendChat("Victus", formatToolResult(payload));
    if (activeStreamState) {
      activeStreamState.hasOutput = true;
    }
    return;
  }
  if (payload.event === "clarify") {
    appendChat("Victus", payload.message || "Can you clarify?");
    endStreamMessage();
    if (activeStreamState) {
      activeStreamState.hasOutput = true;
    }
    return;
  }
  if (payload.event === "error") {
    const message = payload.message || "Request failed.";
    appendChat("Victus", message);
    updateStatus("error");
    maybeShowMemoryBanner(message);
    endStreamMessage();
  }
}

function updateStatus(status) {
  if (status === "thinking") {
    setStatus("Thinking…", "busy");
    return;
  }
  if (status === "executing") {
    setStatus("Executing…", "busy");
    return;
  }
  if (status === "done") {
    setStatus("Connected", "connected");
    endStreamMessage();
    return;
  }
  if (status === "denied") {
    setStatus("Denied", "denied");
    endStreamMessage();
    return;
  }
  if (status === "error") {
    setStatus("Error", "error");
    endStreamMessage();
    return;
  }
}

async function getResponseErrorMessage(response) {
  let bodyText = "";
  try {
    bodyText = await response.text();
  } catch (error) {
    bodyText = "";
  }
  if (response.status === 404) {
    return "Not Found";
  }
  let message = "Error retrieving response.";
  if (bodyText) {
    try {
      const payload = JSON.parse(bodyText);
      message = payload.detail || payload.message || bodyText;
    } catch (error) {
      message = bodyText;
    }
  }
  if (message === "Not Found") {
    return "Error retrieving response.";
  }
  return message;
}

function maybeShowMemoryBanner(message) {
  if (isOllamaMemoryError(message)) {
    showErrorBanner(
      "Ollama memory error detected. Try a smaller model (e.g., phi-2, tinyllama, llama3.2:1b)."
    );
  }
}

function parseSseBuffer(buffer) {
  const segments = buffer.split("\n\n");
  const remainder = segments.pop() || "";
  segments.forEach((segment) => {
    const dataLines = segment
      .split("\n")
      .filter((line) => line.startsWith("data:"));
    if (!dataLines.length) {
      return;
    }
    const data = dataLines
      .map((line) => line.replace(/^data:\s?/, ""))
      .join("\n");
    try {
      const payload = JSON.parse(data);
      handleTurnEvent(payload);
    } catch (error) {
      appendChat("Victus", "Received malformed response from server.");
      updateStatus("error");
      endStreamMessage();
    }
  });
  return remainder;
}

function formatToolStart(payload) {
  const action = payload?.action || "task";
  const toolArgs = payload?.args || {};
  const argsSummary = Object.values(toolArgs).join(", ");
  if (argsSummary) {
    return `Task: ${action}(${argsSummary}) started.`;
  }
  return `Task: ${action} started.`;
}

function formatToolResult(payload) {
  const error = payload?.result?.error;
  if (error) {
    updateStatus("error");
    maybeShowMemoryBanner(error);
    return `Task failed: ${error}`;
  }
  if (payload?.result?.opened) {
    return `Task complete: opened ${payload.result.opened}.`;
  }
  if (payload?.result) {
    return `Task complete: ${JSON.stringify(payload.result)}.`;
  }
  return "Task complete.";
}

chatSend.addEventListener("click", sendChat);
chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendChat();
  }
});

connectWebSocket();
