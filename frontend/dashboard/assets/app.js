const state = {
  activeJobId: null,
  leads: [],
  pollTimer: null,
};

const uploadForm = document.getElementById("uploadForm");
const uploadStatus = document.getElementById("uploadStatus");
const jobsBody = document.querySelector("#jobsTable tbody");
const resultsBody = document.querySelector("#resultsTable tbody");
const rejectedRows = document.getElementById("rejectedRows");
const jobMeta = document.getElementById("jobMeta");
const activeJobLabel = document.getElementById("activeJobLabel");
const minScoreFilter = document.getElementById("minScoreFilter");

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const isJson = (res.headers.get("content-type") || "").includes("application/json");
  const body = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = typeof body === "string" ? body : JSON.stringify(body);
    throw new Error(`${res.status} ${detail}`);
  }
  return body;
}

function renderJobs(items) {
  jobsBody.innerHTML = "";
  for (const j of items) {
    const tr = document.createElement("tr");
    tr.className = "job-row";
    tr.innerHTML = `
      <td class="mono">${j.job_id}</td>
      <td>${j.status}</td>
      <td>${j.input_format || ""}</td>
      <td>${j.created_at || ""}</td>
      <td>${j.counts ? JSON.stringify(j.counts) : ""}</td>
    `;
    tr.addEventListener("click", () => selectJob(j.job_id));
    jobsBody.appendChild(tr);
  }
}

function renderLeads(leads) {
  resultsBody.innerHTML = "";
  for (const lead of leads) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${lead.company_name || ""}</td>
      <td>${lead.website || ""}</td>
      <td>${lead.email || ""}</td>
      <td>${lead.phone || ""}</td>
      <td>${lead.contact_quality || ""}</td>
      <td>${lead.lead_score ?? ""}</td>
      <td>${lead.lead_reason || ""}</td>
    `;
    resultsBody.appendChild(tr);
  }
}

function filteredLeads() {
  const min = Number(minScoreFilter.value || 0);
  return state.leads.filter((l) => Number(l.lead_score || 0) >= min);
}

async function loadJobs() {
  const status = document.getElementById("statusFilter").value;
  const query = new URLSearchParams({ limit: "50", offset: "0" });
  if (status) query.set("status", status);
  const data = await api(`/jobs?${query.toString()}`);
  renderJobs(data.items || []);
}

async function pollActiveJob() {
  if (!state.activeJobId) return;
  const status = await api(`/jobs/${state.activeJobId}`);
  jobMeta.textContent = `status=${status.status} error=${status.error || "none"}`;
  if (status.status === "processing" || status.status === "uploaded") {
    state.pollTimer = setTimeout(pollActiveJob, 2500);
    return;
  }
  if (status.status === "completed") {
    await loadActiveResults();
  }
}

async function loadActiveResults() {
  if (!state.activeJobId) return;
  const data = await api(`/jobs/${state.activeJobId}/results`);
  state.leads = data.leads || [];
  renderLeads(filteredLeads());
  const rej = await api(`/jobs/${state.activeJobId}/rejected`);
  rejectedRows.textContent = JSON.stringify(rej.rejected_rows || [], null, 2);
}

async function selectJob(jobId) {
  state.activeJobId = jobId;
  activeJobLabel.textContent = jobId;
  if (state.pollTimer) {
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }
  await pollActiveJob();
}

uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(uploadForm);
  uploadStatus.textContent = "Uploading...";
  try {
    const res = await api("/jobs", { method: "POST", body: formData });
    uploadStatus.textContent = `Job ${res.job_id} started`;
    await loadJobs();
    await selectJob(res.job_id);
  } catch (err) {
    uploadStatus.textContent = `Upload failed: ${err.message}`;
  }
});

document.getElementById("refreshJobs").addEventListener("click", () => loadJobs());
document.getElementById("statusFilter").addEventListener("change", () => loadJobs());
document.getElementById("applyFilters").addEventListener("click", () => renderLeads(filteredLeads()));

document.getElementById("exportJson").addEventListener("click", () => {
  if (!state.activeJobId) return;
  window.open(`/jobs/${state.activeJobId}/export?format=json`, "_blank");
});

document.getElementById("exportCsv").addEventListener("click", () => {
  if (!state.activeJobId) return;
  window.open(`/jobs/${state.activeJobId}/export?format=csv`, "_blank");
});

loadJobs().catch((e) => {
  uploadStatus.textContent = `Failed to load jobs: ${e.message}`;
});
