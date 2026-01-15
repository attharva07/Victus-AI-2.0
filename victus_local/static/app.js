const statusPill = document.getElementById("status-pill");
const logConsole = document.getElementById("log-console");
const chatInput = document.getElementById("chat-input");
const chatOutput = document.getElementById("chat-output");
const chatSend = document.getElementById("chat-send");
let streamingMessage = null;
let streamingText = null;

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
  appendChat("You", message);
  chatInput.value = "";

  try {
    const response = await fetch("/api/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (!response.ok) {
      const payload = await response.json();
      appendChat("Victus", payload.detail || "Error retrieving response.");
      endStreamMessage();
      return;
    }
    await readTurnStream(response);
  } catch (error) {
    appendChat("Victus", "Network error while contacting server.");
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
    const segments = buffer.split("\n\n");
    buffer = segments.pop();
    segments.forEach((segment) => {
      const dataLine = segment
        .split("\n")
        .find((line) => line.startsWith("data: "));
      if (!dataLine) {
        return;
      }
      const payload = JSON.parse(dataLine.replace("data: ", ""));
      handleTurnEvent(payload);
    });
  }

  if (buffer.trim()) {
    const dataLine = buffer
      .split("\n")
      .find((line) => line.startsWith("data: "));
    if (dataLine) {
      const payload = JSON.parse(dataLine.replace("data: ", ""));
      handleTurnEvent(payload);
    }
  }
}

function handleTurnEvent(payload) {
  if (payload.event === "status") {
    updateStatus(payload.status);
    return;
  }
  if (payload.event === "token") {
    appendStreamChunk(payload.token);
    return;
  }
  if (payload.event === "tool_start") {
    appendChat("Victus", `Running ${payload.tool}.${payload.action}...`);
    return;
  }
  if (payload.event === "tool_done") {
    appendChat("Victus", formatToolResult(payload));
    return;
  }
  if (payload.event === "clarify") {
    appendChat("Victus", payload.message || "Can you clarify?");
    endStreamMessage();
    return;
  }
  if (payload.event === "error") {
    appendChat("Victus", payload.message || "Request failed.");
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

function formatToolResult(payload) {
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
