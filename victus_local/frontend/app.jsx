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
  const [isStreaming, setIsStreaming] = useState(false);
  const [logs, setLogs] = useState([]);
  const [sphereState, setSphereState] = useState("idle");
  const [audioActive, setAudioActive] = useState(false);
  const [visualHint, setVisualHint] = useState(null);
  const [nowPlaying, setNowPlaying] = useState(null);
  const [policyState, setPolicyState] = useState(null);
  const [policyError, setPolicyError] = useState(null);
  const [adminPassword, setAdminPassword] = useState("");
  const [adminStatus, setAdminStatus] = useState({ unlocked: false, expiresAt: null });
  const [policySaving, setPolicySaving] = useState(false);
  const chatInputRef = useRef(null);
  const controllerRef = useRef(null);
  const logsSourceRef = useRef(null);
  const streamingLengthRef = useRef(0);
  const streamingTextRef = useRef("");
  const currentAssistantIdRef = useRef(null);
  const logDedupRef = useRef(new Map());
  const statusRef = useRef(status);
  const pendingVisualHintRef = useRef(null);

  const apiTurnEndpoint = useMemo(() => {
    const meta = document.querySelector('meta[name="victus-api-turn"]');
    return meta?.content || "/api/turn";
  }, []);

  const appendLog = (event, data = {}) => {
    const now = Date.now();
    const cleanupBefore = now - 5000;
    logDedupRef.current.forEach((timestamp, key) => {
      if (timestamp < cleanupBefore) {
        logDedupRef.current.delete(key);
      }
    });

    const eventId = data?.event_id;
    const bucket = Math.floor(now / 1000);
    const keyMessage = data?.message || data?.status || data?.tool || "";
    const keyAction = data?.action ? `:${data.action}` : "";
    const dedupKey = eventId
      ? `id:${eventId}`
      : `hash:${event}:${keyMessage}${keyAction}:${bucket}`;

    if (logDedupRef.current.has(dedupKey)) {
      return;
    }
    logDedupRef.current.set(dedupKey, now);

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

  const createMessageId = () =>
    `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  const createMessage = (role, text, extra = {}) => ({
    id: createMessageId(),
    role,
    text,
    ...extra,
  });

  const beginStream = () => {
    streamingTextRef.current = "";
    setIsStreaming(true);
    streamingLengthRef.current = 0;
    pendingVisualHintRef.current = null;
    setSphereState("thinking");
    const messageId = createMessageId();
    currentAssistantIdRef.current = messageId;
    setMessages((prev) => [
      ...prev,
      {
        id: messageId,
        role: "Victus",
        text: "",
        status: "streaming",
      },
    ]);
  };

  const endStream = () => {
    setIsStreaming(false);
    const assistantId = currentAssistantIdRef.current;
    if (assistantId) {
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? { ...message, status: "done" }
            : message
        )
      );
    }
    setSphereState("idle");
    currentAssistantIdRef.current = null;

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
    const assistantId = currentAssistantIdRef.current;
    if (assistantId) {
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? { ...message, status: "stopped" }
            : message
        )
      );
    }
    currentAssistantIdRef.current = null;
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
    if (eventType === "status" || eventType === "status_update") {
      setStatusFromServer(payload.status);
      appendLog("status_update", { status: payload.status, event_id: payload.event_id });
      return;
    }
    if (eventType === "token") {
      const chunk = payload.text ?? payload.token ?? "";
      if (chunk) {
        streamingLengthRef.current += chunk.length;
        const assistantId = currentAssistantIdRef.current;
        setMessages((prev) => {
          let found = false;
          const next = prev.map((message) => {
            if (message.id === assistantId) {
              found = true;
              const nextText = `${message.text}${chunk}`;
              streamingTextRef.current = nextText;
              return { ...message, text: nextText };
            }
            return message;
          });
          if (!found) {
            const messageId = assistantId || createMessageId();
            currentAssistantIdRef.current = messageId;
            const nextText = `${chunk}`;
            streamingTextRef.current = nextText;
            next.push({
              id: messageId,
              role: "Victus",
              text: nextText,
              status: "streaming",
            });
          }
          return next;
        });
        setSphereState("streaming");
      }
      return;
    }
    if (eventType === "clarify") {
      const message = payload.message || "Can you clarify what you want Victus to do?";
      setMessages((prev) => [...prev, createMessage("Victus", message)]);
      return;
    }
    if (eventType === "tool_start") {
      appendLog("tool_start", {
        tool: payload.tool,
        action: payload.action,
        args: payload.args,
        event_id: payload.event_id,
      });
      return;
    }
    if (eventType === "tool_done") {
      appendLog("tool_done", {
        tool: payload.tool,
        action: payload.action,
        result: payload.result,
        event_id: payload.event_id,
      });
      if (payload.action === "media_play") {
        const result = payload.result || {};
        if (result.now_playing) {
          setNowPlaying({
            ...result.now_playing,
            decision: result.decision,
            confidence: result.confidence,
            query: result.query,
          });
        } else if (result.error || ["clarify", "block"].includes(result.decision)) {
          setNowPlaying(null);
        }
      }
      return;
    }
    if (eventType === "error") {
      const message = payload.message || "Request failed.";
      appendLog("error", { message, event_id: payload.event_id });
      setMessages((prev) => [...prev, createMessage("Victus", message)]);
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

  const loadPolicy = async () => {
    try {
      const response = await fetch("/api/policy", { credentials: "include" });
      if (!response.ok) {
        throw new Error("Unable to load policy.");
      }
      const payload = await response.json();
      setPolicyState(payload);
      setAdminStatus({
        unlocked: Boolean(payload?.admin?.unlocked),
        expiresAt: payload?.admin?.expires_at || null,
      });
      setPolicyError(null);
    } catch (error) {
      setPolicyError("Unable to load policy.");
    }
  };

  const updatePolicy = async (nextEnabled) => {
    setPolicySaving(true);
    try {
      const response = await fetch("/api/policy", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ enabled_actions: nextEnabled }),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Unable to update policy.");
      }
      const payload = await response.json();
      setPolicyState(payload);
      setPolicyError(null);
    } catch (error) {
      setPolicyError(error.message || "Unable to update policy.");
    } finally {
      setPolicySaving(false);
    }
  };

  const handleUnlockAdmin = async () => {
    if (!adminPassword) {
      setPolicyError("Admin password is required.");
      return;
    }
    try {
      const response = await fetch("/api/admin/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ password: adminPassword }),
      });
      if (!response.ok) {
        throw new Error("Invalid admin password.");
      }
      const payload = await response.json();
      setAdminStatus({ unlocked: true, expiresAt: payload.expires_at || null });
      setPolicyError(null);
      setAdminPassword("");
      await loadPolicy();
    } catch (error) {
      setPolicyError(error.message || "Unable to unlock admin.");
    }
  };

  const handleLockAdmin = async () => {
    try {
      await fetch("/api/admin/lock", { method: "POST", credentials: "include" });
      setAdminStatus({ unlocked: false, expiresAt: null });
      await loadPolicy();
    } catch (error) {
      setPolicyError("Unable to lock admin.");
    }
  };

  const toggleAction = (action) => {
    if (!policyState || !adminStatus.unlocked) {
      return;
    }
    const enabled = new Set(policyState.enabled_actions || []);
    if (enabled.has(action)) {
      enabled.delete(action);
    } else {
      enabled.add(action);
    }
    updatePolicy(Array.from(enabled));
  };

  const sendChat = async () => {
    const text = chatInputRef.current?.value?.trim();
    if (!text) {
      return;
    }

    setMessages((prev) => [...prev, createMessage("You", text)]);
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
          createMessage("Victus", errorText || "Error retrieving response."),
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
        createMessage("Victus", "Network error while contacting server."),
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
    if (activeTab === "Settings") {
      loadPolicy();
    }
  }, [activeTab]);

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
        const normalizedEvent = entry.event === "status" ? "status_update" : entry.event;
        if (["status_update", "tool_start", "tool_done", "turn_error"].includes(normalizedEvent)) {
          appendLog(normalizedEvent, entry.data || {});
        }
        if (normalizedEvent === "status_update") {
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

  const stopPlayback = async () => {
    if (!nowPlaying) {
      return;
    }
    const provider = nowPlaying.provider || "spotify";
    setNowPlaying(null);
    if (provider === "spotify") {
      try {
        await fetch("/api/media/stop", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider }),
        });
      } catch (error) {
        appendLog("error", { message: "Unable to stop Spotify playback." });
      }
    }
  };

  const renderDynamicModule = () => {
    if (activeTab === "Home") {
      return (
        <div className="dynamic-list">
          {nowPlaying ? (
            <div className="dynamic-card now-playing-card">
              <div className="now-playing-header">
                <div>
                  <h3>Now Playing</h3>
                  <p className="now-playing-meta">
                    {nowPlaying.provider?.toUpperCase()} · {nowPlaying.title || nowPlaying.query}
                  </p>
                </div>
                <button className="secondary" onClick={stopPlayback}>
                  Stop
                </button>
              </div>
              {nowPlaying.provider === "youtube" ? (
                <iframe
                  className="now-playing-embed"
                  src={nowPlaying.embed_url}
                  title={nowPlaying.title || "YouTube Player"}
                  allow="autoplay; encrypted-media"
                  allowFullScreen
                />
              ) : (
                <div className="now-playing-details">
                  <div>{nowPlaying.title}</div>
                  {nowPlaying.artist && <div className="now-playing-artist">{nowPlaying.artist}</div>}
                  {nowPlaying.spotify_url && (
                    <a href={nowPlaying.spotify_url} target="_blank" rel="noreferrer">
                      Open in Spotify
                    </a>
                  )}
                </div>
              )}
            </div>
          ) : null}
          <div className="dynamic-card">
            <h3>Chat History</h3>
            <ul>
              {recentMessages.length ? (
                recentMessages.map((message) => (
                  <li key={message.id}>
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

  const renderSettings = () => {
    const toggleable = policyState?.toggleable_actions || [];
    const enabledActions = new Set(policyState?.enabled_actions || []);
    return (
      <div className="settings-content">
        <section className="panel settings-panel">
          <h2>Settings</h2>
          <div className="settings-section">
            <h3>Unlock Admin</h3>
            <p className="settings-muted">
              Admin access is required to change policy toggles. Default password is{" "}
              <strong>victus</strong> unless configured.
            </p>
            <div className="settings-inline">
              <input
                type="password"
                placeholder="Admin password"
                value={adminPassword}
                onChange={(event) => setAdminPassword(event.target.value)}
              />
              <button onClick={handleUnlockAdmin} disabled={!adminPassword}>
                Unlock
              </button>
              <button className="secondary" onClick={handleLockAdmin} disabled={!adminStatus.unlocked}>
                Lock
              </button>
            </div>
            {adminStatus.unlocked && (
              <p className="settings-muted">Admin unlocked {adminStatus.expiresAt ? `until ${adminStatus.expiresAt}` : ""}</p>
            )}
            {policyError && <p className="settings-error">{policyError}</p>}
          </div>

          <div className="settings-section">
            <h3>Policy</h3>
            {!adminStatus.unlocked && <p className="settings-muted">Unlock admin to edit.</p>}
            {policySaving && <p className="settings-muted">Saving policy changes…</p>}
            {!toggleable.length ? (
              <p className="settings-muted">No toggleable actions available.</p>
            ) : (
              <div className="policy-list">
                {toggleable.map((entry) => {
                  const action = entry.action || entry;
                  const enabled = entry.enabled ?? enabledActions.has(action);
                  return (
                    <label className="policy-toggle" key={action}>
                      <input
                        type="checkbox"
                        checked={enabled}
                        disabled={!adminStatus.unlocked || policySaving}
                        onChange={() => toggleAction(action)}
                      />
                      <span>{action}</span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        </section>
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

      {activeTab === "Settings" ? (
        <div className="app-shell settings-shell">{renderSettings()}</div>
      ) : (
        <div className="app-shell">
          <div className="row primary">
            <section className="panel conversation-panel">
              <h2>Conversation</h2>
              <div className="chat-output">
                {messages.map((message) => (
                  <div className="chat-message" key={message.id}>
                    <strong>{message.role}:</strong> {message.text}
                  </div>
                ))}
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
                    recentMessages.map((message) => (
                      <li key={message.id}>
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
      )}
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
