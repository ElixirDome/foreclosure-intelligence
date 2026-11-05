import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client";

interface SkippedProperty {
  property_id: number;
  address: string;
  reason: string;
}

interface ImportResponse {
  message: string;
  saved_count: number;
  skipped_count: number;
  properties: unknown[];
  skipped: SkippedProperty[];
}

interface ConnectedSourceItem {
  id: number;
  name: string;
  base_url: string;
  adapter_key: string;
  enabled: boolean;
  last_run_at: string | null;
  last_status: string | null;
}

interface DiscoveryResult {
  status: "discovered" | "partial" | "failed";
  source_name: string;
  candidate_url: string | null;
  adapter_key: "pnb" | "banknet" | "custom_html";
  confidence: string;
  evidence: string[];
  sample_listings: Array<{
    title: string;
    details: string;
    document_url?: string | null;
  }>;
  failure_reason?: string | null;
  guidance?: string | null;
  suggested_urls?: string[];
}

interface LiveIngestionStatus {
  run_id?: number;
  source?: string;
  stage: "idle" | "discovery_started" | "documents_discovered" | "extraction_completed" | "completed";
  status?: "running" | "success" | "zero_properties_extracted" | "no_items_found" | "partial_success" | "failed";
  items_found?: number;
  items_extracted?: number;
  items_saved?: number;
  items_skipped?: number;
  documents_without_property?: number;
  discovery_time_ms?: number;
  extraction_time_ms?: number;
  extraction_errors?: number | string[];
  latency?: {
    discovery_and_fetch_ms?: number;
    extraction_ms?: number;
    commit_time_ms?: number;
    total_time_ms?: number;
  };
  timestamp?: number;
}

function Import() {
  const [activeTab, setActiveTab] = useState<"discover" | "active" | "pdf">("discover");

  // Real-Time SSE Stream & Ingestion Tracker State
  const [streamStatus, setStreamStatus] = useState<"live" | "reconnecting" | "polling">("polling");
  const [liveIngestion, setLiveIngestion] = useState<LiveIngestionStatus | null>(null);

  // Autonomous Discovery State
  const [discoverQuery, setDiscoverQuery] = useState("PNB");
  const [discovering, setDiscovering] = useState(false);
  const [discoveryResult, setDiscoveryResult] = useState<DiscoveryResult | null>(null);
  const [discoveryError, setDiscoveryError] = useState("");

  // Manual PDF upload state
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Connected Sources state
  const [sources, setSources] = useState<ConnectedSourceItem[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const [connectName, setConnectName] = useState("");
  const [connectUrl, setConnectUrl] = useState("https://www.pnb.bank.in/EAuction.aspx");
  const [connectAdapter, setConnectAdapter] = useState<"pnb" | "banknet" | "custom_html">("pnb");
  const [connectLocation, setConnectLocation] = useState("");
  const [connectLimit, setConnectLimit] = useState(50);
  const [connectSuccess, setConnectSuccess] = useState("");
  const [connectError, setConnectError] = useState("");
  const [syncingId, setSyncingId] = useState<number | null>(null);

  async function loadSources() {
    try {
      setSourcesLoading(true);
      const res = await api.get<ConnectedSourceItem[]>("/sources/");
      setSources(res.data);
    } catch (err: any) {
      console.error("Could not load connected sources:", err);
    } finally {
      setSourcesLoading(false);
    }
  }

  useEffect(() => {
    loadSources();
  }, []);

  // Subscribe to real-time ingestion events via SSE
  useEffect(() => {
    let eventSource: EventSource | null = null;
    let isMounted = true;

    function connectSSE() {
      const token = localStorage.getItem("access_token");
      if (!token) return;

      const baseUrl = api.defaults.baseURL || "http://127.0.0.1:8000";
      const sseUrl = `${baseUrl}/properties/stream?token=${encodeURIComponent(token)}`;

      try {
        eventSource = new EventSource(sseUrl);

        eventSource.onopen = () => {
          if (!isMounted) return;
          setStreamStatus("live");
        };

        eventSource.addEventListener("connected", () => {
          if (!isMounted) return;
          setStreamStatus("live");
        });

        eventSource.addEventListener("ping", () => {
          if (!isMounted) return;
          setStreamStatus("live");
        });

        eventSource.addEventListener("ingestion_status", (event: MessageEvent) => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(event.data);
            setLiveIngestion(data);

            // When a run finishes, refresh the connected sources table
            if (data.stage === "completed") {
              loadSources();
            }
          } catch (e) {
            console.error("Error parsing ingestion_status event:", e);
          }
        });

        eventSource.onerror = () => {
          if (!isMounted) return;
          setStreamStatus("reconnecting");
        };
      } catch (err) {
        console.error("Failed to connect SSE in Import:", err);
      }
    }

    connectSSE();

    return () => {
      isMounted = false;
      if (eventSource) {
        eventSource.close();
      }
    };
  }, []);

  async function handleAutonomousDiscover(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!discoverQuery.trim()) return;

    try {
      setDiscovering(true);
      setDiscoveryError("");
      setDiscoveryResult(null);

      const res = await api.post<DiscoveryResult>("/sources/discover", {
        url_or_name: discoverQuery.trim(),
      });

      setDiscoveryResult(res.data);
      if (res.data.candidate_url) {
        setConnectUrl(res.data.candidate_url);
        setConnectName(res.data.source_name);
        setConnectAdapter(res.data.adapter_key);
      }
    } catch (err: any) {
      console.error(err);
      setDiscoveryError(err.response?.data?.detail || "Endpoint discovery failed. Check network or enter direct URL.");
    } finally {
      setDiscovering(false);
    }
  }

  async function handleConnectSource(e: React.FormEvent) {
    e.preventDefault();
    setConnectError("");
    setConnectSuccess("");

    if (!connectName.trim()) {
      setConnectError("Please provide a name for this source.");
      return;
    }
    if (!connectUrl.trim()) {
      setConnectError("Please provide a valid listing URL.");
      return;
    }

    try {
      setLoading(true);
      const rules: Record<string, any> = {
        limit: connectLimit,
      };
      if (connectLocation.trim()) {
        rules.location = connectLocation.trim();
        rules.city = connectLocation.trim();
      }

      const res = await api.post("/sources/", {
        name: connectName.trim(),
        base_url: connectUrl.trim(),
        adapter_key: connectAdapter,
        rules,
      });

      setConnectSuccess(`Successfully connected "${res.data.name}". Initializing background ingestion.`);
      loadSources();
      setActiveTab("active");
    } catch (err: any) {
      console.error(err);
      const msg = err.response?.data?.detail || err.message || "Failed to connect source.";
      setConnectError(msg);
    } finally {
      setLoading(false);
    }
  }

  async function handleRunSource(sourceId: number) {
    try {
      setSyncingId(sourceId);
      await api.post(`/sources/${sourceId}/run`);
      setSources((prev) =>
        prev.map((s) => (s.id === sourceId ? { ...s, last_status: "queued" } : s))
      );
    } catch (err: any) {
      console.error("Sync error:", err);
      alert(err.response?.data?.detail || "Failed to trigger sync");
    } finally {
      setSyncingId(null);
    }
  }

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Please select a PDF file.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      setResult(null);

      const formData = new FormData();
      formData.append("file", file);

      const response = await api.post("/properties/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setResult(response.data);
    } catch (err: any) {
      console.error(err);
      const msg = err.response?.data?.detail || err.message || "Upload failed.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="desk-shell">
      <header className="desk-header">
        <div className="desk-brand">
          <Link to="/dashboard" className="desk-back-btn">
            ← Return to Desk
          </Link>
          <span className="desk-brand-sep">/</span>
          <span className="desk-brand-title">Admin Source Discovery & Ingestion Desk</span>
        </div>
        <div className="desk-actions" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {/* Real-time SSE Stream Health Pill */}
          <div
            className={`ig-live-pill ${streamStatus}`}
            title={
              streamStatus === "live"
                ? "Real-time SSE event stream active"
                : streamStatus === "reconnecting"
                ? "Reconnecting to event stream..."
                : "Checking connection..."
            }
          >
            <span
              className={`ig-live-dot ${
                streamStatus === "live" ? "green" : streamStatus === "reconnecting" ? "amber" : "gray"
              }`}
            />
            <span>{streamStatus === "live" ? "Live Feed" : streamStatus === "reconnecting" ? "Reconnecting" : "Polling"}</span>
          </div>

          <Link to="/dashboard" className="desk-action-pill">
            Live Inventory
          </Link>
        </div>
      </header>

      <main className="desk-main">
        {/* Live Ingestion Pipeline Tracker */}
        {liveIngestion && (
          <div className="live-ingestion-tracker">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <strong style={{ fontSize: 15, color: "var(--text-primary)" }}>
                  Live Ingestion Pipeline: {liveIngestion.source || "Background Worker"}
                </strong>
                {liveIngestion.run_id && (
                  <span className="desk-badge-code">Run #{liveIngestion.run_id}</span>
                )}
              </div>
              <span
                className={`desk-status-pill ${
                  liveIngestion.status === "success"
                    ? "success"
                    : liveIngestion.status === "zero_properties_extracted"
                    ? "pending"
                    : liveIngestion.stage === "completed"
                    ? "neutral"
                    : "pending"
                }`}
              >
                {liveIngestion.status === "zero_properties_extracted"
                  ? "Zero Properties Extracted"
                  : liveIngestion.status?.toUpperCase() || liveIngestion.stage.toUpperCase()}
              </span>
            </div>

            {/* Stage Progress Row */}
            <div className="tracker-stages-row">
              <div
                className={`tracker-stage-step ${
                  liveIngestion.stage === "discovery_started"
                    ? "active"
                    : liveIngestion.stage !== "idle"
                    ? "done"
                    : ""
                }`}
              >
                <div className="tracker-stage-icon">
                  Step 1
                </div>
                <span className="tracker-stage-label">Discovery</span>
                {liveIngestion.discovery_time_ms != null && (
                  <small style={{ fontSize: 11, color: "var(--text-muted)" }}>
                    {liveIngestion.discovery_time_ms}ms
                  </small>
                )}
              </div>

              <div
                className={`tracker-stage-step ${
                  liveIngestion.stage === "documents_discovered"
                    ? "active"
                    : ["extraction_completed", "completed"].includes(liveIngestion.stage)
                    ? "done"
                    : ""
                }`}
              >
                <div className="tracker-stage-icon">
                  Step 2
                </div>
                <span className="tracker-stage-label">Fetching ({liveIngestion.items_found ?? 0})</span>
              </div>

              <div
                className={`tracker-stage-step ${
                  liveIngestion.stage === "extraction_completed"
                    ? "active"
                    : liveIngestion.stage === "completed"
                    ? "done"
                    : ""
                }`}
              >
                <div className="tracker-stage-icon">
                  Step 3
                </div>
                <span className="tracker-stage-label">
                  Extraction ({liveIngestion.items_extracted ?? 0})
                </span>
                {liveIngestion.extraction_time_ms != null && (
                  <small style={{ fontSize: 11, color: "var(--text-muted)" }}>
                    {liveIngestion.extraction_time_ms}ms
                  </small>
                )}
              </div>

              <div
                className={`tracker-stage-step ${
                  liveIngestion.stage === "completed" ? "done" : ""
                }`}
              >
                <div className="tracker-stage-icon">
                  Step 4
                </div>
                <span className="tracker-stage-label">
                  Persistence ({liveIngestion.items_saved ?? 0} saved)
                </span>
              </div>
            </div>

            {/* Truthful Status Messaging */}
            {liveIngestion.status === "zero_properties_extracted" && (
              <div
                style={{
                  background: "rgba(245, 158, 11, 0.12)",
                  border: "1px solid rgba(245, 158, 11, 0.35)",
                  borderRadius: 8,
                  padding: "10px 14px",
                  fontSize: 13,
                  color: "var(--accent-amber)",
                  marginTop: 12,
                }}
              >
                <strong>Truthful Ingestion Report:</strong> Found {liveIngestion.items_found} notice document(s) which were parsed and added to evidence, but 0 eligible residential foreclosure properties were extracted. Marked truthfully as <code>zero_properties_extracted</code> instead of misleading success.
              </div>
            )}

            {/* Latency Metrics Summary */}
            {liveIngestion.latency && (
              <div
                style={{
                  display: "flex",
                  gap: 16,
                  fontSize: 12,
                  color: "var(--text-muted)",
                  marginTop: 10,
                  borderTop: "1px solid var(--border-subtle)",
                  paddingTop: 8,
                }}
              >
                <span>Total Latency: <strong>{liveIngestion.latency.total_time_ms ?? 0}ms</strong></span>
                <span>Fetch: <strong>{liveIngestion.latency.discovery_and_fetch_ms ?? 0}ms</strong></span>
                <span>OCR/Extract: <strong>{liveIngestion.latency.extraction_ms ?? 0}ms</strong></span>
                <span>Commit: <strong>{liveIngestion.latency.commit_time_ms ?? 0}ms</strong></span>
              </div>
            )}
          </div>
        )}
        {/* Navigation Tabs */}
        <div className="desk-tabs-bar">
          <button
            type="button"
            className={`desk-tab-btn ${activeTab === "discover" ? "active" : ""}`}
            onClick={() => setActiveTab("discover")}
          >
            <span>Autonomous Source Discovery</span>
          </button>

          <button
            type="button"
            className={`desk-tab-btn ${activeTab === "active" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("active");
              loadSources();
            }}
          >
            <span>Connected Portals ({sources.length})</span>
          </button>

          <button
            type="button"
            className={`desk-tab-btn ${activeTab === "pdf" ? "active" : ""}`}
            onClick={() => setActiveTab("pdf")}
          >
            <span>Direct PDF Ingest</span>
          </button>
        </div>

        {/* Tab 1: Autonomous Source Discovery & Connection */}
        {activeTab === "discover" && (
          <div className="desk-content-grid">
            <section className="desk-card">
              <div className="desk-card-header">
                <h2>1. Autonomous Source Discovery</h2>
                <p className="desk-card-subtitle">
                  Supply a bank name or auction portal URL. The system inspects navigation menus, sitemaps, SARFAESI tables, and notice documents to find supported routes.
                </p>
              </div>

              {discoveryError && <div className="desk-alert error">{discoveryError}</div>}
              {connectSuccess && <div className="desk-alert success">{connectSuccess}</div>}

              <form onSubmit={handleAutonomousDiscover} className="desk-form">
                <div className="desk-form-row">
                  <label>Bank Name or Website URL</label>
                  <div style={{ display: "flex", gap: 10 }}>
                    <input
                      type="text"
                      value={discoverQuery}
                      onChange={(e) => setDiscoverQuery(e.target.value)}
                      placeholder="e.g. PNB, Punjab National Bank, IBAPI, or https://www.pnb.bank.in"
                      disabled={discovering}
                      style={{ flex: 1 }}
                    />
                    <button
                      type="submit"
                      className="desk-btn-primary"
                      disabled={discovering || !discoverQuery.trim()}
                    >
                      {discovering ? "Inspecting Portal..." : "Discover Endpoints"}
                    </button>
                  </div>
                </div>

                <div className="desk-quick-pills">
                  <span className="desk-pills-label">Quick test:</span>
                  <button type="button" className="desk-mini-pill" onClick={() => { setDiscoverQuery("PNB"); }}>
                    Punjab National Bank (PNB)
                  </button>
                  <button type="button" className="desk-mini-pill" onClick={() => { setDiscoverQuery("IBAPI"); }}>
                    IBAPI (e-Bkray)
                  </button>
                  <button type="button" className="desk-mini-pill" onClick={() => { setDiscoverQuery("https://www.pnb.bank.in/EAuction.aspx"); }}>
                    PNB EAuction.aspx
                  </button>
                </div>
              </form>

              {/* Discovery Verification & Preview Display */}
              {discoveryResult && (
                <div className="discovery-results-panel" style={{ marginTop: 24 }}>
                  <div className="discovery-header-strip">
                    <div>
                      <span className={`discovery-status-badge ${discoveryResult.status}`}>
                        {discoveryResult.status === "discovered" ? "Verified Route Discovered" : discoveryResult.status === "partial" ? "Partial Discovery" : "Discovery Obstacle"}
                      </span>
                      <h3 style={{ margin: "8px 0 4px 0", fontSize: 18 }}>{discoveryResult.source_name}</h3>
                      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                        Best candidate endpoint: <code>{discoveryResult.candidate_url || "None identified"}</code>
                      </p>
                    </div>
                    <div>
                      <span className="discovery-conf-pill">
                        Confidence: <strong>{discoveryResult.confidence.toUpperCase()}</strong>
                      </span>
                    </div>
                  </div>

                  {/* Evidence Section */}
                  <div className="discovery-section">
                    <h4>Discovery Evidence & Network Diagnostics</h4>
                    <ul className="discovery-evidence-list">
                      {discoveryResult.evidence.map((ev, idx) => (
                        <li key={idx}>{ev}</li>
                      ))}
                    </ul>
                  </div>

                  {/* Sample Listings Preview */}
                  {discoveryResult.sample_listings.length > 0 && (
                    <div className="discovery-section">
                      <h4>Representative Auction Listings Preview</h4>
                      <div className="discovery-sample-grid">
                        {discoveryResult.sample_listings.map((item, idx) => (
                          <div key={idx} className="discovery-sample-card">
                            <span className="discovery-sample-title">{item.title}</span>
                            <span className="discovery-sample-desc">{item.details}</span>
                            {item.document_url && (
                              <a href={item.document_url} target="_blank" rel="noreferrer" className="discovery-sample-link">
                                View Notice PDF
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Actionable Guidance on Obstacle / Failure */}
                  {discoveryResult.failure_reason && (
                    <div className="discovery-section obstacle-box">
                      <h4>Obstacle Diagnostics & Guided Setup</h4>
                      <p style={{ color: "var(--accent-red)", marginBottom: 8 }}>{discoveryResult.failure_reason}</p>
                      <pre className="discovery-guidance-pre">{discoveryResult.guidance}</pre>
                      {discoveryResult.suggested_urls && discoveryResult.suggested_urls.length > 0 && (
                        <div style={{ marginTop: 10 }}>
                          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Suggested Direct Endpoints:</span>
                          <div className="desk-quick-pills" style={{ marginTop: 4 }}>
                            {discoveryResult.suggested_urls.map((u, i) => (
                              <button
                                key={i}
                                type="button"
                                className="desk-mini-pill"
                                onClick={() => {
                                  setConnectUrl(u);
                                  setDiscoverQuery(u);
                                }}
                              >
                                {u}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </section>

            {/* Connection Configuration Form */}
            <section className="desk-card">
              <div className="desk-card-header">
                <h2>2. Source Connection & Scheduled Ingestion</h2>
                <p className="desk-card-subtitle">
                  Confirm the discovered route parameters and activate automated periodic ingestion.
                </p>
              </div>

              {connectError && <div className="desk-alert error">{connectError}</div>}

              <form onSubmit={handleConnectSource} className="desk-form">
                <div className="desk-form-row">
                  <label>Connection Name</label>
                  <input
                    type="text"
                    value={connectName}
                    onChange={(e) => setConnectName(e.target.value)}
                    placeholder="e.g. Punjab National Bank - Primary E-Auction"
                    required
                  />
                </div>

                <div className="desk-form-row">
                  <label>Listing Endpoint URL</label>
                  <input
                    type="url"
                    value={connectUrl}
                    onChange={(e) => setConnectUrl(e.target.value)}
                    placeholder="https://www.pnb.bank.in/EAuction.aspx"
                    required
                  />
                </div>

                <div className="desk-form-row">
                  <label>Source Adapter</label>
                  <select
                    value={connectAdapter}
                    onChange={(e: any) => setConnectAdapter(e.target.value)}
                  >
                    <option value="pnb">PNB E-Auction Portal (Verified SARFAESI Table & Notice Adapter)</option>
                    <option value="banknet">BankNet / IBAPI Adapter (Multi-Bank Aggregator)</option>
                    <option value="custom_html">Generic Bank Portal (CSS & Table Extractor)</option>
                  </select>
                </div>

                <div className="desk-form-row">
                  <label>Geographic Ingestion Filter (Optional City or District)</label>
                  <input
                    type="text"
                    value={connectLocation}
                    onChange={(e) => setConnectLocation(e.target.value)}
                    placeholder="e.g. Gurdaspur, Ghaziabad, Pathankot (leave empty for broad sync)"
                  />
                  <small className="muted">Applies source-side query filtering at download time to prevent irrelevant notice fetches.</small>
                </div>

                <div className="desk-form-row">
                  <label>Max Notices per Ingestion Run</label>
                  <input
                    type="number"
                    min={5}
                    max={100}
                    value={connectLimit}
                    onChange={(e) => setConnectLimit(Number(e.target.value))}
                  />
                </div>

                <button
                  type="submit"
                  className="desk-btn-primary"
                  disabled={loading || !connectUrl.trim()}
                  style={{ width: "100%", marginTop: 12, padding: "14px 20px" }}
                >
                  {loading ? "Registering Source..." : "Activate Ingestion & Connect Source"}
                </button>
              </form>
            </section>
          </div>
        )}

        {/* Tab 2: Connected Portals & Live Health */}
        {activeTab === "active" && (
          <section className="desk-card">
            <div className="desk-card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h2>Active Connected Portals</h2>
                <p className="desk-card-subtitle">Manage registered auction sources, view health status, and trigger ad-hoc synchronization.</p>
              </div>
              <button
                type="button"
                className="desk-btn-secondary"
                onClick={loadSources}
                disabled={sourcesLoading}
              >
                {sourcesLoading ? "Refreshing..." : "Refresh Status"}
              </button>
            </div>

            {sources.length === 0 ? (
              <div className="desk-empty-box">
                <p>No auction sources connected yet.</p>
                <button
                  type="button"
                  className="desk-btn-primary"
                  onClick={() => setActiveTab("discover")}
                >
                  Discover & Connect a Bank Portal
                </button>
              </div>
            ) : (
              <div className="desk-sources-table-wrapper">
                <table className="desk-table">
                  <thead>
                    <tr>
                      <th>Source Name</th>
                      <th>Listing Endpoint</th>
                      <th>Adapter</th>
                      <th>Status</th>
                      <th>Last Sync</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sources.map((s) => (
                      <tr key={s.id}>
                        <td>
                          <strong>{s.name}</strong>
                        </td>
                        <td>
                          <a
                            href={s.base_url}
                            target="_blank"
                            rel="noreferrer"
                            className="desk-table-url"
                            title={s.base_url}
                          >
                            {s.base_url.length > 45 ? s.base_url.slice(0, 42) + "..." : s.base_url}
                          </a>
                        </td>
                        <td>
                          <span className="desk-badge-code">{s.adapter_key}</span>
                        </td>
                        <td>
                          <span
                            className={`desk-status-pill ${
                              s.last_status === "completed"
                                ? "success"
                                : s.last_status === "queued" || s.last_status === "running"
                                ? "pending"
                                : "neutral"
                            }`}
                          >
                            {s.last_status || "Idle"}
                          </span>
                        </td>
                        <td>
                          {s.last_run_at ? new Date(s.last_run_at).toLocaleString() : "Never"}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="desk-mini-pill action"
                            onClick={() => handleRunSource(s.id)}
                            disabled={syncingId === s.id || !s.enabled}
                          >
                            {syncingId === s.id ? "Syncing..." : "Sync Now"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* Tab 3: Direct PDF Ingestion */}
        {activeTab === "pdf" && (
          <section className="desk-card" style={{ maxWidth: 700, margin: "0 auto" }}>
            <div className="desk-card-header">
              <h2>Direct Notice PDF Ingestion</h2>
              <p className="desk-card-subtitle">
                Upload a raw bank auction PDF to immediately run OCR, extraction, residential validation, and database persistence.
              </p>
            </div>

            {error && <div className="desk-alert error">{error}</div>}

            <form onSubmit={handleUpload} className="desk-form">
              <div className="desk-form-row">
                <label>Select Auction Notice Document (PDF)</label>
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </div>

              <button
                type="submit"
                className="desk-btn-primary"
                disabled={loading || !file}
                style={{ width: "100%", marginTop: 12 }}
              >
                {loading ? "Extracting & Ingesting..." : "Upload & Ingest Notice"}
              </button>
            </form>

            {result && (
              <div className="desk-alert success" style={{ marginTop: 20 }}>
                <h4>{result.message}</h4>
                <p>
                  Saved <strong>{result.saved_count}</strong> property record(s). Skipped <strong>{result.skipped_count}</strong>.
                </p>
                {result.skipped.length > 0 && (
                  <ul style={{ margin: "8px 0 0 16px" }}>
                    {result.skipped.map((s, idx) => (
                      <li key={idx}>
                        {s.address}: <em>{s.reason}</em>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default Import;
