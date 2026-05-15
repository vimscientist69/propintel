import React, { useEffect, useMemo, useState } from "react";
import { Analytics } from "./components/Analytics";
import { AppShell } from "./components/AppShell";
import { ControlPanel } from "./components/ControlPanel";
import { JobHistory } from "./components/JobHistory";

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
  const [activeTab, setActiveTab] = useState("control");
  const [jobs, setJobs] = useState([]);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [jobsOffset, setJobsOffset] = useState(0);
  const [jobsStatus, setJobsStatus] = useState("");
  const [activeJobId, setActiveJobId] = useState("");
  const [activeJobStatus, setActiveJobStatus] = useState("");
  const [activeJobMeta, setActiveJobMeta] = useState("Select a job to load details.");
  const [activeBatchesStarted, setActiveBatchesStarted] = useState(0);
  const [activeBatchesCompleted, setActiveBatchesCompleted] = useState(0);
  const [activeBatchesTotal, setActiveBatchesTotal] = useState(0);
  const [rejectedRows, setRejectedRows] = useState([]);
  const [leads, setLeads] = useState([]);
  const [uploadStatus, setUploadStatus] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState("No file selected");
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);

  const [minScore, setMinScore] = useState(0);
  const [qualityFilter, setQualityFilter] = useState("");
  const [chatbotFilter, setChatbotFilter] = useState("");
  const [freshnessFilter, setFreshnessFilter] = useState("");
  const [explorerJobId, setExplorerJobId] = useState("");
  const [explorerRows, setExplorerRows] = useState([]);
  const [settingsName, setSettingsName] = useState("custom");
  const [settingsPayloadText, setSettingsPayloadText] = useState("{}");
  const [settingsStatus, setSettingsStatus] = useState("");
  const [settingsProfiles, setSettingsProfiles] = useState([]);
  const [deleteConfirmName, setDeleteConfirmName] = useState("");
  const [analyticsRows, setAnalyticsRows] = useState([]);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsJobLimit, setAnalyticsJobLimit] = useState(10);

  useEffect(() => {
    loadJobs();
  }, [jobsOffset, jobsStatus]);

  useEffect(() => {
    if (activeTab === "settings") {
      loadSettings();
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === "analytics") {
      loadAnalyticsRows();
    }
  }, [activeTab, analyticsJobLimit]);

  useEffect(() => {
    if (activeTab === "explorer" && explorerJobId) {
      loadExplorerRows();
    }
  }, [activeTab, explorerJobId]);

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
        setActiveJobStatus(status.status || "");
        setActiveBatchesStarted(Number(status.batches_started || 0));
        setActiveBatchesCompleted(Number(status.batches_completed || 0));
        setActiveBatchesTotal(Number(status.batches_total || 0));
        const batchProgress = `${status.batches_started || 0}/${status.batches_total || 0}`;
        setActiveJobMeta(
          `status=${status.status} batches_started=${batchProgress} batches_completed=${status.batches_completed || 0}/${status.batches_total || 0} rows=${status.rows_processed || 0}/${status.rows_total || 0} error=${status.error || "none"}`,
        );
        if (status.status === "processing" || status.status === "uploaded") {
          await loadActiveJobDetails(activeJobId);
          if (explorerJobId && explorerJobId === activeJobId) {
            await loadExplorerRows();
          }
          await loadJobs();
          timeoutId = setTimeout(poll, 2500);
          return;
        }
        if (status.status === "completed") {
          await Promise.all([loadActiveJobDetails(activeJobId), loadJobs()]);
          if (explorerJobId && explorerJobId === activeJobId) {
            await loadExplorerRows();
          }
          if (activeTab === "analytics") {
            await loadAnalyticsRows();
          }
          return;
        }
        if (status.status === "failed" || status.status === "terminated") {
          await loadJobs();
          if (activeTab === "analytics") {
            await loadAnalyticsRows();
          }
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
      setIsLoadingJobs(true);
      const query = new URLSearchParams({
        limit: String(JOB_LIMIT),
        offset: String(jobsOffset),
      });
      if (jobsStatus) query.set("status", jobsStatus);
      const payload = await api(`/jobs?${query.toString()}`);
      setJobs(payload.items || []);
      setJobsTotal(Number(payload.total || 0));
      if (!explorerJobId && payload.items && payload.items.length > 0) {
        setExplorerJobId(payload.items[0].job_id);
      }
    } catch (err) {
      setUploadStatus(`Failed to load jobs: ${err.message}`);
    } finally {
      setIsLoadingJobs(false);
    }
  }

  async function loadActiveJobDetails(jobId) {
    const results = await api(`/jobs/${jobId}/results`);
    setLeads(results.leads || []);
    if (results.status === "completed" || results.status === "failed" || results.status === "terminated") {
      const rejected = await api(`/jobs/${jobId}/rejected`);
      setRejectedRows(rejected.rejected_rows || []);
    }
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
      setActiveJobStatus(payload.status || "processing");
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
  const jobsPageCount = jobsTotal === 0 ? 1 : Math.ceil(jobsTotal / JOB_LIMIT);
  const jobsPage = jobsTotal === 0 ? 1 : Math.floor(jobsOffset / JOB_LIMIT) + 1;
  const activeJob = jobs.find((j) => j.job_id === activeJobId);
  const explorerJob = jobs.find((j) => j.job_id === explorerJobId);
  const statusTone = activeJob?.status || "idle";
  const startedPct =
    activeBatchesTotal > 0 ? Math.min(100, Math.round((activeBatchesStarted / activeBatchesTotal) * 100)) : 0;
  const completedPct =
    activeBatchesTotal > 0 ? Math.min(100, Math.round((activeBatchesCompleted / activeBatchesTotal) * 100)) : 0;
  const canTerminate = activeJobId && (activeJobStatus === "processing" || activeJobStatus === "uploaded");
  const canResume = activeJobId && (activeJobStatus === "failed" || activeJobStatus === "terminated");

  const openExport = (format) => {
    if (!activeJobId) return;
    window.open(`${API_BASE}/jobs/${activeJobId}/export?format=${format}`, "_blank");
  };

  const terminateActiveJob = async () => {
    if (!activeJobId) return;
    try {
      const payload = await api(`/jobs/${activeJobId}/terminate`, { method: "POST" });
      setActiveJobStatus(payload.status || "terminated");
      setActiveJobMeta("status=terminated error=terminated_by_user");
      setUploadStatus(`Job ${activeJobId} terminated`);
      await loadJobs();
    } catch (err) {
      setUploadStatus(`Terminate failed: ${err.message}`);
    }
  };

  const resumeActiveJob = async () => {
    if (!activeJobId) return;
    try {
      const payload = await api(`/jobs/${activeJobId}/resume`, { method: "POST" });
      setActiveJobStatus(payload.status || "processing");
      setUploadStatus(`Job ${activeJobId} resumed`);
      await loadJobs();
    } catch (err) {
      setUploadStatus(`Resume failed: ${err.message}`);
    }
  };

  const loadExplorerRows = async () => {
    if (!explorerJobId) return;
    try {
      const payload = await api(`/jobs/${explorerJobId}/results`);
      setExplorerRows(payload.leads || []);
    } catch {
      setExplorerRows([]);
    }
  };

  const loadSettings = async () => {
    try {
      const payload = await api("/settings");
      const active = payload.active || { name: "custom", payload: {} };
      setSettingsProfiles(payload.profiles || []);
      setSettingsName(String(active.name || "custom"));
      setSettingsPayloadText(JSON.stringify(active.payload || {}, null, 2));
      setSettingsStatus("");
    } catch (err) {
      setSettingsStatus(`Failed loading settings: ${err.message}`);
    }
  };

  const loadAnalyticsRows = async () => {
    try {
      setAnalyticsLoading(true);
      const jobsPayload = await api(`/jobs?limit=${analyticsJobLimit}&offset=0&status=completed`);
      const completedIds = (jobsPayload.items || []).map((item) => item.job_id).filter(Boolean);
      if (completedIds.length === 0) {
        setAnalyticsRows([]);
        return;
      }
      const perJobRows = await Promise.all(
        completedIds.map(async (jobId) => {
          try {
            const payload = await api(`/jobs/${jobId}/results`);
            return payload.status === "completed" ? payload.leads || [] : [];
          } catch {
            return [];
          }
        }),
      );
      setAnalyticsRows(perJobRows.flat());
    } catch (err) {
      setAnalyticsRows([]);
      setUploadStatus(`Analytics load failed: ${err.message}`);
    } finally {
      setAnalyticsLoading(false);
    }
  };

  const validateSettings = async () => {
    try {
      const parsed = JSON.parse(settingsPayloadText);
      const payload = await api("/settings/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      setSettingsStatus(payload.ok ? "Settings payload is valid." : `Validation failed: ${(payload.errors || []).join(", ")}`);
    } catch (err) {
      setSettingsStatus(`Validation error: ${err.message}`);
    }
  };

  const saveSettings = async () => {
    try {
      const parsed = JSON.parse(settingsPayloadText);
      await api("/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: settingsName || "custom", payload: parsed, activate: true }),
      });
      setSettingsStatus("Settings saved and activated.");
      await loadSettings();
    } catch (err) {
      setSettingsStatus(`Save failed: ${err.message}`);
    }
  };

  const activateProfile = async (name) => {
    try {
      await api("/settings/activate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      setSettingsStatus(`Activated profile: ${name}`);
      await loadSettings();
    } catch (err) {
      setSettingsStatus(`Activate failed: ${err.message}`);
    }
  };

  const deleteProfile = async () => {
    if (!deleteConfirmName) return;
    try {
      await api(`/settings/${encodeURIComponent(deleteConfirmName)}`, { method: "DELETE" });
      setSettingsStatus(`Deleted profile: ${deleteConfirmName}`);
      setDeleteConfirmName("");
      await loadSettings();
    } catch (err) {
      setSettingsStatus(`Delete failed: ${err.message}`);
    }
  };

  return (
    <AppShell activeTab={activeTab} onTabChange={setActiveTab}>
      {activeTab === "control" ? (
        <ControlPanel
          activeJobStatus={activeJobStatus}
          activeJobMeta={activeJobMeta}
          statusTone={statusTone}
          startedPct={startedPct}
          completedPct={completedPct}
          isSubmitting={isSubmitting}
          onSubmit={onSubmit}
          selectedFileName={selectedFileName}
          setSelectedFileName={setSelectedFileName}
          uploadStatus={uploadStatus}
          canTerminate={canTerminate}
          canResume={canResume}
          terminateActiveJob={terminateActiveJob}
          resumeActiveJob={resumeActiveJob}
          loadJobs={loadJobs}
          jobs={jobs}
          jobsOffset={jobsOffset}
          jobsPage={jobsPage}
          jobsPageCount={jobsPageCount}
          isLoadingJobs={isLoadingJobs}
          activeJobId={activeJobId}
          setActiveJobId={setActiveJobId}
          activeBatchesTotal={activeBatchesTotal}
          activeBatchesCompleted={activeBatchesCompleted}
          jobsStatus={jobsStatus}
          setJobsStatus={setJobsStatus}
          setJobsOffset={setJobsOffset}
          jobsTotal={jobsTotal}
          startIdx={startIdx}
          endIdx={endIdx}
          filteredLeads={filteredLeads}
          minScore={minScore}
          setMinScore={setMinScore}
          qualityFilter={qualityFilter}
          setQualityFilter={setQualityFilter}
          chatbotFilter={chatbotFilter}
          setChatbotFilter={setChatbotFilter}
          freshnessFilter={freshnessFilter}
          setFreshnessFilter={setFreshnessFilter}
          openExport={openExport}
          rejectedRows={rejectedRows}
          jobLimit={JOB_LIMIT}
        />
      ) : activeTab === "analytics" ? (
        <Analytics
          analyticsRows={analyticsRows}
          analyticsLoading={analyticsLoading}
          jobsTotal={jobsTotal}
          completedJobsCount={jobs.filter((j) => j.status === "completed").length}
          jobLimit={analyticsJobLimit}
          onJobLimitChange={setAnalyticsJobLimit}
          onRefresh={loadAnalyticsRows}
          rowCountLabel={`${analyticsRows.length} rows`}
        />
      ) : activeTab === "history" ? (
        <JobHistory
          jobs={jobs}
          jobsTotal={jobsTotal}
          jobsOffset={jobsOffset}
          jobsPage={jobsPage}
          jobsPageCount={jobsPageCount}
          startIdx={startIdx}
          endIdx={endIdx}
          jobsStatus={jobsStatus}
          setJobsStatus={setJobsStatus}
          setJobsOffset={setJobsOffset}
          jobLimit={JOB_LIMIT}
          isLoadingJobs={isLoadingJobs}
          onRefresh={loadJobs}
          apiBase={API_BASE}
        />
      ) : (
        <div className="legacy-tab">
                {activeTab === "explorer" && (
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Data Explorer</h2>
                <p>Search and inspect lead rows for a selected job.</p>
                {(explorerJob?.status === "processing" || explorerJob?.status === "uploaded") && (
                  <span className="status-chip partial-chip">Showing partial batch results</span>
                )}
              </div>
              <button type="button" className="ghost" onClick={loadExplorerRows}>
                Reload
              </button>
            </div>
            <div className="filters">
              <div className="field compact">
                <label htmlFor="explorerJob">Job</label>
                <select id="explorerJob" value={explorerJobId} onChange={(e) => setExplorerJobId(e.target.value)}>
                  <option value="">select a job</option>
                  {jobs.map((job) => (
                    <option key={job.job_id} value={job.job_id}>
                      {job.job_id.slice(0, 8)} ({job.status})
                    </option>
                  ))}
                </select>
              </div>
              <div className="field compact">
                <label htmlFor="minScoreExplorer">Min score</label>
                <input
                  id="minScoreExplorer"
                  type="number"
                  min="0"
                  max="100"
                  value={minScore}
                  onChange={(e) => setMinScore(e.target.value)}
                />
              </div>
            </div>
            <div className="table-wrap">
              <table className="explorer-table">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Status</th>
                    <th>Website</th>
                    <th>Email</th>
                    <th>Phone</th>
                    <th>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {explorerRows
                    .filter((row) => Number(row.lead_score || 0) >= Number(minScore || 0))
                    .map((row, idx) => (
                      <tr key={`${row.company_name || "row"}-${idx}`}>
                        <td data-label="Company">{row.company_name || ""}</td>
                        <td data-label="Status"><span className={`pill pill-${row.contact_quality || "unknown"}`}>{row.contact_quality || "unknown"}</span></td>
                        <td data-label="Website">{row.website || ""}</td>
                        <td data-label="Email">{row.email || ""}</td>
                        <td data-label="Phone">{row.phone || ""}</td>
                        <td data-label="Score">{row.lead_score ?? ""}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {activeTab === "settings" && (
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Engine Settings</h2>
                <p>Manage active enrichment/scoring profiles without editing YAML directly.</p>
              </div>
            </div>
            <div className="filters">
              <div className="field compact settings-name-field">
                <label htmlFor="settingsName">Profile name</label>
                <input
                  id="settingsName"
                  value={settingsName}
                  onChange={(e) => setSettingsName(e.target.value)}
                />
                <div className="settings-name-actions">
                  <button type="button" onClick={validateSettings}>Validate</button>
                  <button type="button" onClick={saveSettings}>Save + Activate</button>
                </div>
              </div>
            </div>
            <textarea
              className="settings-editor"
              value={settingsPayloadText}
              onChange={(e) => setSettingsPayloadText(e.target.value)}
              rows={14}
            />
            {String(settingsPayloadText || "").trim() === "{}" && (
              <p className="muted">
                Minimal template: {"{"}"runtime":{"{"}"worker_concurrency":6,"providers":{"{"}"google_maps":{"{"}"requests_per_second":2.0,"max_concurrent":2{"}"},"serper":{"{"}"requests_per_second":1.5,"max_concurrent":2{"}"}{"}"}{"}"}{"}"}
              </p>
            )}
            <p className="muted">{settingsStatus}</p>
            <details className="rejected" open>
              <summary>Profiles</summary>
              <div className="table-wrap">
                <table className="settings-profiles-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Active</th>
                      <th>Updated</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {settingsProfiles.length === 0 && (
                      <tr>
                        <td colSpan={4} className="empty-row">
                          No profiles saved yet.
                        </td>
                      </tr>
                    )}
                    {settingsProfiles.map((profile) => (
                      <tr key={profile.name}>
                        <td className="mono" data-label="Name">{profile.name}</td>
                        <td data-label="Active">
                          <span className={`pill ${profile.is_active ? "pill-completed" : ""}`}>
                            {profile.is_active ? "active" : "inactive"}
                          </span>
                        </td>
                        <td data-label="Updated">{profile.updated_at || "-"}</td>
                        <td data-label="Action" className="profile-actions">
                          <button
                            type="button"
                            className="ghost"
                            disabled={profile.is_active}
                            onClick={() => activateProfile(profile.name)}
                          >
                            Activate
                          </button>
                          <button
                            type="button"
                            className="ghost danger"
                            onClick={() => setDeleteConfirmName(profile.name)}
                            style={{ marginLeft: "8px" }}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
            {deleteConfirmName && (
              <div className="modal-overlay" role="dialog" aria-modal="true">
                <div className="modal-card">
                  <h3>Delete settings profile?</h3>
                  <p>
                    This will permanently remove <span className="mono">{deleteConfirmName}</span>.
                    This action cannot be undone.
                  </p>
                  <div className="actions-row">
                    <button type="button" className="ghost" onClick={() => setDeleteConfirmName("")}>
                      Cancel
                    </button>
                    <button type="button" className="danger" onClick={deleteProfile}>
                      Delete profile
                    </button>
                  </div>
                </div>
              </div>
            )}
          </section>
        )}
        </div>
      )}
    </AppShell>
  );
}
