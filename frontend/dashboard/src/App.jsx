import React, { useEffect, useMemo, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function api(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, options);
  const isJson = (response.headers.get("content-type") || "").includes("application/json");
  const payload = isJson ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "string" ? payload : JSON.stringify(payload);
    throw new Error(`${response.status} ${detail}`);
  }
  return payload;
}

const JOB_LIMIT = 20;

export function App() {
  const [jobs, setJobs] = useState([]);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [jobsOffset, setJobsOffset] = useState(0);
  const [jobsStatus, setJobsStatus] = useState("");
  const [activeJobId, setActiveJobId] = useState("");
  const [activeJobMeta, setActiveJobMeta] = useState("Select a job to load details.");
  const [rejectedRows, setRejectedRows] = useState([]);
  const [leads, setLeads] = useState([]);
  const [uploadStatus, setUploadStatus] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState("No file selected");

  const [minScore, setMinScore] = useState(0);
  const [qualityFilter, setQualityFilter] = useState("");
  const [chatbotFilter, setChatbotFilter] = useState("");
  const [freshnessFilter, setFreshnessFilter] = useState("");

  useEffect(() => {
    loadJobs();
  }, [jobsOffset, jobsStatus]);

  useEffect(() => {
    if (!activeJobId) {
      return undefined;
    }
    let cancelled = false;
    let timeoutId;

    async function poll() {
      try {
        const status = await api(`/jobs/${activeJobId}`);
        if (cancelled) return;
        setActiveJobMeta(`status=${status.status} error=${status.error || "none"}`);
        if (status.status === "processing" || status.status === "uploaded") {
          timeoutId = setTimeout(poll, 2500);
          return;
        }
        if (status.status === "completed") {
          await loadActiveJobDetails(activeJobId);
        }
      } catch (err) {
        if (!cancelled) {
          setActiveJobMeta(`Failed loading job status: ${err.message}`);
        }
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [activeJobId]);

  async function loadJobs() {
    try {
      const query = new URLSearchParams({
        limit: String(JOB_LIMIT),
        offset: String(jobsOffset),
      });
      if (jobsStatus) query.set("status", jobsStatus);
      const payload = await api(`/jobs?${query.toString()}`);
      setJobs(payload.items || []);
      setJobsTotal(Number(payload.total || 0));
    } catch (err) {
      setUploadStatus(`Failed to load jobs: ${err.message}`);
    }
  }

  async function loadActiveJobDetails(jobId) {
    const [results, rejected] = await Promise.all([
      api(`/jobs/${jobId}/results`),
      api(`/jobs/${jobId}/rejected`),
    ]);
    setLeads(results.leads || []);
    setRejectedRows(rejected.rejected_rows || []);
  }

  async function onSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    setIsSubmitting(true);
    setUploadStatus("Uploading...");
    try {
      const payload = await api("/jobs", { method: "POST", body: formData });
      setUploadStatus(`Job ${payload.job_id} started`);
      setActiveJobId(payload.job_id);
      setJobsOffset(0);
      await loadJobs();
    } catch (err) {
      setUploadStatus(`Upload failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  }

  const filteredLeads = useMemo(
    () =>
      leads
        .filter((lead) => Number(lead.lead_score || 0) >= Number(minScore || 0))
        .filter((lead) => (qualityFilter ? String(lead.contact_quality || "") === qualityFilter : true))
        .filter((lead) => {
          if (!chatbotFilter) return true;
          if (chatbotFilter === "yes") return lead.has_chatbot === true;
          return lead.has_chatbot === false;
        })
        .filter((lead) =>
          freshnessFilter ? String(lead.last_updated_signal || "") === freshnessFilter : true,
        )
        .sort((a, b) => Number(b.lead_score || 0) - Number(a.lead_score || 0)),
    [leads, minScore, qualityFilter, chatbotFilter, freshnessFilter],
  );

  const startIdx = jobsTotal === 0 ? 0 : jobsOffset + 1;
  const endIdx = Math.min(jobsOffset + JOB_LIMIT, jobsTotal);
  const recentJobs = jobs.slice(0, 6);
  const activeJob = jobs.find((j) => j.job_id === activeJobId);
  const statusTone = activeJob?.status || "idle";

  const openExport = (format) => {
    if (!activeJobId) return;
    window.open(`${API_BASE}/jobs/${activeJobId}/export?format=${format}`, "_blank");
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-dot">P</div>
          <div>
            <div className="brand-title">PropIntel</div>
            <div className="brand-subtitle">Dashboard Control Center</div>
          </div>
        </div>
        <nav className="nav">
          <button className="nav-item active">Control Panel</button>
          <button className="nav-item">Analytics</button>
          <button className="nav-item">Job History</button>
          <button className="nav-item">Data Explorer</button>
          <button className="nav-item">Engine Settings</button>
        </nav>
      </aside>

      <main className="main">
        <header className="header">
          <span className="status-chip">Live enrichment environment</span>
          <h1>Dashboard Control Center</h1>
          <p>Configure job input, monitor progress, and inspect enriched lead results.</p>
        </header>

        <section className="top-grid">
          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>Main Control Panel</h2>
                <p>Choose input format, upload dataset, and dispatch a new job.</p>
              </div>
              <span className={`telemetry telemetry-${statusTone}`}>{isSubmitting ? "Running" : "Idle"}</span>
            </div>
            <div className="progress-wrap">
              <div className={`progress-line ${statusTone}`} />
              <small>{activeJobMeta}</small>
            </div>
            <form className="control-form" onSubmit={onSubmit}>
              <div className="form-grid">
                <div className="field">
                  <label htmlFor="input_format">Target input</label>
                  <select id="input_format" name="input_format" defaultValue="csv">
                    <option value="csv">CSV</option>
                    <option value="json">JSON</option>
                    <option value="propflux">PropFlux JSON</option>
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="file">Dataset</label>
                  <div className="file-picker">
                    <input
                      id="file"
                      name="file"
                      type="file"
                      required
                      onChange={(e) => setSelectedFileName(e.target.files?.[0]?.name || "No file selected")}
                    />
                    <label htmlFor="file" className="file-trigger">
                      Choose file
                    </label>
                    <span className="file-name">{selectedFileName}</span>
                  </div>
                </div>
              </div>
              <div className="actions-row">
                <button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Running..." : "Run job"}
                </button>
                <button type="button" className="ghost" onClick={loadJobs}>
                  Refresh jobs
                </button>
                <span className="muted">{uploadStatus}</span>
              </div>
            </form>
          </div>

          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>Recent Jobs</h2>
                <p>Snapshot of the latest enrichment runs.</p>
              </div>
              <small className="muted">
                {startIdx}-{endIdx} of {jobsTotal}
              </small>
            </div>
            <div className="jobs-inline-controls">
              <select
                id="status"
                value={jobsStatus}
                onChange={(e) => {
                  setJobsStatus(e.target.value);
                  setJobsOffset(0);
                }}
              >
                <option value="">all statuses</option>
                <option value="uploaded">uploaded</option>
                <option value="processing">processing</option>
                <option value="completed">completed</option>
                <option value="failed">failed</option>
              </select>
              <button type="button" className="ghost" onClick={() => setJobsOffset((v) => Math.max(0, v - JOB_LIMIT))}>
                Prev
              </button>
              <button
                type="button"
                className="ghost"
                onClick={() => setJobsOffset((v) => (v + JOB_LIMIT >= jobsTotal ? v : v + JOB_LIMIT))}
              >
                Next
              </button>
            </div>
            <div className="job-list">
              {recentJobs.length === 0 && <p className="muted">No jobs recorded yet.</p>}
              {recentJobs.map((job) => (
                <button
                  type="button"
                  key={job.job_id}
                  className={`job-list-item ${job.job_id === activeJobId ? "active" : ""}`}
                  onClick={() => setActiveJobId(job.job_id)}
                >
                  <span className="mono">{job.job_id.slice(0, 8)}</span>
                  <span className={`pill pill-${job.status}`}>{job.status}</span>
                  <span>{job.input_format || "-"}</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Latest Listings</h2>
              <p>Filtered lead intelligence grid for the selected job.</p>
            </div>
            <span className="mono">{activeJobId || "none selected"}</span>
          </div>

          <div className="filters">
            <div className="field compact">
              <label htmlFor="minScore">Min score</label>
              <input
                id="minScore"
                type="number"
                min="0"
                max="100"
                value={minScore}
                onChange={(e) => setMinScore(e.target.value)}
                placeholder="0"
              />
            </div>
            <div className="field compact">
              <label htmlFor="quality">Quality</label>
              <select id="quality" value={qualityFilter} onChange={(e) => setQualityFilter(e.target.value)}>
                <option value="">all quality</option>
                <option value="verified">verified</option>
                <option value="likely">likely</option>
                <option value="low">low</option>
              </select>
            </div>
            <div className="field compact">
              <label htmlFor="chatbot">Chatbot</label>
              <select id="chatbot" value={chatbotFilter} onChange={(e) => setChatbotFilter(e.target.value)}>
                <option value="">all</option>
                <option value="yes">has chatbot</option>
                <option value="no">no chatbot</option>
              </select>
            </div>
            <div className="field compact">
              <label htmlFor="freshness">Freshness</label>
              <select id="freshness" value={freshnessFilter} onChange={(e) => setFreshnessFilter(e.target.value)}>
                <option value="">all</option>
                <option value="detected">detected</option>
                <option value="unknown">unknown</option>
              </select>
            </div>
            <button type="button" onClick={() => openExport("json")} disabled={!activeJobId}>
              Export JSON
            </button>
            <button type="button" onClick={() => openExport("csv")} disabled={!activeJobId}>
              Export CSV
            </button>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Listing</th>
                  <th>Status</th>
                  <th>Website</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>Score</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {filteredLeads.length === 0 && (
                  <tr>
                    <td colSpan={7} className="empty-row">
                      No lead rows yet. Select a completed job to inspect results.
                    </td>
                  </tr>
                )}
                {filteredLeads.map((lead, idx) => (
                  <tr key={`${lead.company_name || "row"}-${idx}`}>
                    <td>{lead.company_name || ""}</td>
                    <td>
                      <span className={`pill pill-${lead.contact_quality || "unknown"}`}>
                        {lead.contact_quality || "unknown"}
                      </span>
                    </td>
                    <td>{lead.website || ""}</td>
                    <td>{lead.email || ""}</td>
                    <td>{lead.phone || ""}</td>
                    <td>{lead.lead_score ?? ""}</td>
                    <td>{lead.lead_reason || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <details className="rejected">
            <summary>Rejected Rows</summary>
            <pre>{JSON.stringify(rejectedRows, null, 2)}</pre>
          </details>
        </section>
      </main>
    </div>
  );
}
