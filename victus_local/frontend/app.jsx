const { useEffect, useMemo, useRef, useState } = React;

const TABS = ["Home", "Memory", "Finance", "Settings"];
const PLACEHOLDERS = {
  Memory: [
    "Memory viewer (placeholder)",
    "Retention policies", 
    "Search + recall",
    "Safety audit log",
  ],
  Finance: [
    "Finance data (placeholder)",
    "Monthly summary", 
    "Export logbook", 
    "Budget targets",
  ],
  Settings: [
    "Settings (placeholder)",
    "Model selection", 
    "Tool approvals", 
    "Logs verbosity",
  ],
};

const LONG_RESPONSE_THRESHOLD = 240;

function App() {
  const [activeTab, setActiveTab] = useState("Home");
  const [status, setStatus] = useState({ label: "Connected", state: "connected" });
  const [messages, setMessages] = useState([]);
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [logs, setLogs] = useState([]);
  const [sphereState, setSphereState] = useState("idle");
  const [audioActive, setAudioActive] = useState(false);
  const [visualHint, setVisualHint] = useState(null);
  const chatInputRef = useRef(null);
  const controllerRef = useRef(null);
  const logsSourceRef = useRef(null);
  const streamingLengthRef = useRef(0);
  const streamingTextRef = useRef("");
  const statusRef = useRef(status);
  const pendingVisualHintRef = useRef(null);

  const apiTurnEndpoint = useMemo(() => {
    const meta = document.querySelector('meta[name="victus-api-turn"]');
    return meta?.content || "/api/turn";
  }, []);

  const appendLog = (event, data = {}) => {
    setLogs((prev) => [
      ...prev,
      {
        id: `${Date.now()}-${Math.random()}`,
        event,
        data,
        timestamp: new Date(),
      },
    ]);
  };

  const setStatusState = (label, state) => {
    setStatus({ label, state });
  };

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  const setStatusFromServer = (state) => {
    if (state === "thinking") {
      setStatusState("Thinking", "busy");
      setSphereState("thinking");
      return;
    }
    if (state === "executing") {
      setStatusState("Executing", "busy");
      setSphereState("thinking");
      return;
    }
    if (state === "done") {
      setStatusState("Done", "connected");
      setSphereState("idle");
      return;
    }
    if (state === "error") {
      setStatusState("Error", "error");
      setSphereState("error");
    }
  };

  const beginStream = () => {
    setStreamingText("");
    streamingTextRef.current = "";
    setIsStreaming(true);
    streamingLengthRef.current = 0;
    pendingVisualHintRef.current = null;
    setSphereState("thinking");
  };

  const endStream = () => {
    setIsStreaming(false);
    if (streamingTextRef.current.trim()) {
      setMessages((prev) => [...prev, { role: "Victus", text: streamingTextRef.current }]);
    }
    setStreamingText("");
    streamingTextRef.current = "";
    setSphereState("idle");

    if (
      pendingVisualHintRef.current &&
      streamingLengthRef.current >= LONG_RESPONSE_THRESHOLD
    ) {
      setVisualHint(pendingVisualHintRef.current);
    } else {
      setVisualHint(null);
    }
  };

  const stopStreaming = () => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
      appendLog("client_stop", { reason: "user" });
    }
    setStatusState("Connected", "connected");
    setSphereState("idle");
    setIsStreaming(false);
    setStreamingText("");
    streamingTextRef.current = "";
    pendingVisualHintRef.current = null;
    streamingLengthRef.current = 0;
  };

  const handleTurnEvent = (eventType, payload) => {
    if (!eventType) {
      return;
    }
    if (payload?.visual_hint) {
      pendingVisualHintRef.current = payload.visual_hint;
    }
    if (eventType === "status") {
      setStatusFromServer(payload.status);
      appendLog("status", { status: payload.status });
      return;
    }
    if (eventType === "token") {
      const chunk = payload.text ?? payload.token ?? "";
      if (chunk) {
        streamingLengthRef.current += chunk.length;
        setStreamingText((prev) => {
          const nextText = `${prev}${chunk}`;
          streamingTextRef.current = nextText;
          return nextText;
        });
        setSphereState("streaming");
      }
      return;
    }
    if (eventType === "tool_start") {
      appendLog("tool_start", {
        tool: payload.tool,
        action: payload.action,
        args: payload.args,
      });
      return;
    }
    if (eventType === "tool_done") {
      appendLog("tool_done", {
        tool: payload.tool,
        action: payload.action,
        result: payload.result,
      });
      return;
    }
    if (eventType === "error") {
      const message = payload.message || "Request failed.";
      appendLog("error", { message });
      setMessages((prev) => [...prev, { role: "Victus", text: message }]);
      setStatusState("Error", "error");
      setSphereState("error");
    }
  };

  const parseSseBuffer = (buffer) => {
    const segments = buffer.split("\n\n");
    const remainder = segments.pop() || "";
    segments.forEach((segment) => {
      if (!segment.trim()) {
        return;
      }
      const lines = segment.split("\n");
      let eventType = null;
      const dataLines = [];
      lines.forEach((line) => {
        if (line.startsWith("event:")) {
          eventType = line.replace(/^event:\s?/, "").trim();
        }
        if (line.startsWith("data:")) {
          dataLines.push(line.replace(/^data:\s?/, ""));
        }
      });
      if (!dataLines.length) {
        return;
      }
      const data = dataLines.join("\n");
      try {
        const payload = JSON.parse(data);
        handleTurnEvent(eventType || payload.event, payload);
      } catch (error) {
        appendLog("error", { message: "Malformed SSE payload" });
        setStatusState("Error", "error");
      }
    });
    return remainder;
  };

  const readTurnStream = async (response) => {
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
    endStream();
    if (statusRef.current.state !== "error") {
      setStatusState("Done", "connected");
    }
  };

  const sendChat = async () => {
    const text = chatInputRef.current?.value?.trim();
    if (!text) {
      return;
    }

    setMessages((prev) => [...prev, { role: "You", text }]);
    chatInputRef.current.value = "";
    setStatusState("Thinking", "busy");
    beginStream();
    setAudioActive(true);

    controllerRef.current = new AbortController();

    try {
      const response = await fetch(apiTurnEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
        signal: controllerRef.current.signal,
      });

      if (!response.ok) {
        const errorText = await response.text();
        setMessages((prev) => [
          ...prev,
          { role: "Victus", text: errorText || "Error retrieving response." },
        ]);
        setStatusState("Error", "error");
        return;
      }

      await readTurnStream(response);
    } catch (error) {
      if (error.name === "AbortError") {
        appendLog("client_stop", { reason: "aborted" });
        return;
      }
      setMessages((prev) => [
        ...prev,
        { role: "Victus", text: "Network error while contacting server." },
      ]);
      setStatusState("Error", "error");
      setSphereState("error");
    } finally {
      controllerRef.current = null;
      setIsStreaming(false);
    }
  };

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        stopStreaming();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (logsSourceRef.current) {
      logsSourceRef.current.close();
    }

    const source = new EventSource("/api/logs/stream");
    logsSourceRef.current = source;

    source.onopen = () => {
      setStatusState("Connected", "connected");
    };

    source.onmessage = (event) => {
      try {
        const entry = JSON.parse(event.data);
        if (["status_update", "tool_start", "tool_done", "turn_error"].includes(entry.event)) {
          appendLog(entry.event, entry.data || {});
        }
        if (entry.event === "status_update") {
          setStatusFromServer(entry.data.status);
        }
      } catch (error) {
        appendLog("error", { message: "Malformed log payload" });
      }
    };

    source.onerror = () => {
      setStatusState("Disconnected", "error");
      source.close();
    };

    return () => {
      source.close();
    };
  }, []);

  const recentMessages = useMemo(() => messages.slice(-4), [messages]);
  const recentLogs = useMemo(() => logs.slice(-5).reverse(), [logs]);

  const renderDynamicModule = () => {
    if (activeTab === "Home") {
      return (
        <div className="dynamic-list">
          <div className="dynamic-card">
            <h3>Chat History</h3>
            <ul>
              {recentMessages.length ? (
                recentMessages.map((message) => (
                  <li key={`${message.role}-${message.text}`}>
                    <strong>{message.role}:</strong> {message.text}
                  </li>
                ))
              ) : (
                <li>No interactions yet. Start a conversation above.</li>
              )}
            </ul>
          </div>
          <div className="dynamic-card">
            <h3>Recent Interactions</h3>
            <p className="placeholder-pill">Streaming pipeline ready</p>
            <p>Victus will populate richer insights here once memory and finance UI ships.</p>
          </div>
        </div>
      );
    }

    const placeholderItems = PLACEHOLDERS[activeTab] || [];
    return (
      <div className="dynamic-list">
        {placeholderItems.map((item) => (
          <div className="dynamic-card" key={item}>
            {item}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div>
      <nav className="top-nav">
        <div className="nav-left">Victus Local</div>
        <div className="nav-tabs">
          {TABS.map((tab) => (
            <button
              key={tab}
              className={`nav-tab ${activeTab === tab ? "active" : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>
        <div className="nav-right">
          <span>Status</span>
          <span className={`status-pill ${status.state === "busy" ? "busy" : ""} ${status.state === "error" ? "error" : ""}`}>
            {status.label}
          </span>
        </div>
      </nav>

      <div className="app-shell">
        <div className="row primary">
          <section className="panel conversation-panel">
            <h2>Conversation</h2>
            <div className="chat-output">
              {messages.map((message, index) => (
                <div className="chat-message" key={`${message.role}-${index}`}>
                  <strong>{message.role}:</strong> {message.text}
                </div>
              ))}
              {isStreaming && (
                <div className="chat-message">
                  <strong>Victus:</strong> {streamingText}
                </div>
              )}
            </div>
            <div className="chat-input">
              <textarea
                ref={chatInputRef}
                rows="3"
                placeholder="Ask or command Victus..."
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    sendChat();
                  }
                }}
              ></textarea>
              <div className="chat-actions">
                <button onClick={sendChat} disabled={isStreaming}>
                  Send
                </button>
                <button className="secondary" onClick={stopStreaming} disabled={!isStreaming}>
                  Stop
                </button>
              </div>
            </div>
          </section>

          <section className="panel sphere-panel">
            <h2>Sphere</h2>
            <VictusSphere audioActive={audioActive} visualHint={visualHint} sphereState={sphereState} />
            <div className="sphere-overlay">Three.js · Audio reactive</div>
          </section>

          <aside className="panel logs-panel">
            <h2>Live Logs</h2>
            <div className="logs-output">
              {logs.length === 0 ? (
                <div className="log-entry">
                  <span>Awaiting events</span>
                  <div>Logs will stream in real time.</div>
                </div>
              ) : (
                logs.map((log) => (
                  <div className="log-entry" key={log.id}>
                    <span>
                      {log.timestamp.toLocaleTimeString()} · {log.event}
                    </span>
                    <div>{JSON.stringify(log.data)}</div>
                  </div>
                ))
              )}
            </div>
          </aside>
        </div>

        <div className="row secondary">
          <section className="panel dynamic-module">
            <h2>Dynamic Module</h2>
            <div className="placeholder-pill">{activeTab} view</div>
            {renderDynamicModule()}
          </section>

          <aside className="panel activity-panel">
            <h2>Recent Activity</h2>
            <div className="activity-section">
              <h3>Live Telemetry</h3>
              <ul>
                {recentLogs.length ? (
                  recentLogs.map((log) => (
                    <li key={log.id}>
                      {log.event} · {log.timestamp.toLocaleTimeString()}
                    </li>
                  ))
                ) : (
                  <li>Waiting for activity events.</li>
                )}
              </ul>
            </div>
            <div className="activity-section">
              <h3>Chat History</h3>
              <ul>
                {recentMessages.length ? (
                  recentMessages.map((message, index) => (
                    <li key={`${message.role}-${index}`}>
                      <strong>{message.role}:</strong> {message.text}
                    </li>
                  ))
                ) : (
                  <li>No chat history yet.</li>
                )}
              </ul>
            </div>
            <div className="activity-section">
              <h3>Reminders</h3>
              <ul>
                <li>Memory + finance modules will appear here when enabled.</li>
              </ul>
            </div>
          </aside>
        </div>

        <div className="footer-note">UI Build: victus-react-sphere-1</div>
      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
