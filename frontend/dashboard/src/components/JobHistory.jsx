import React, { useMemo, useState } from "react";
import { Download, RefreshCw, Search } from "lucide-react";
import { cn } from "../lib/cn";
import { btnOutline, innerPanel, inputClass, sectionCard, selectClass } from "../lib/propflux-ui";

function JobStatusPill({ status }) {
  const styles = {
    completed: "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
    processing: "border-indigo-500/40 bg-indigo-500/15 text-indigo-300",
    uploaded: "border-indigo-500/40 bg-indigo-500/15 text-indigo-300",
    failed: "border-rose-500/40 bg-rose-500/15 text-rose-300",
    terminated: "border-rose-500/40 bg-rose-500/15 text-rose-300",
  };
  const key = String(status || "").toLowerCase();
  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        styles[key] || "border-slate-700 bg-slate-900/80 text-slate-400",
      )}
    >
      {status || "—"}
    </span>
  );
}

function formatTimestamp(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatItemCount(counts) {
  if (!counts || typeof counts !== "object") return "—";
  const scored = counts.scored_rows ?? counts.rows_processed;
  const total = counts.rows_total ?? counts.mapped_valid_rows ?? counts.deduped_rows;
  if (scored != null && total != null) return `${scored} / ${total}`;
  const first = Object.entries(counts).find(([, v]) => v != null);
  return first ? `${first[0]}: ${first[1]}` : "—";
}

export function JobHistory({
  jobs,
  jobsTotal,
  jobsOffset,
  jobsPage,
  jobsPageCount,
  startIdx,
  endIdx,
  jobsStatus,
  setJobsStatus,
  setJobsOffset,
  jobLimit,
  isLoadingJobs,
  onRefresh,
  apiBase,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [formatFilter, setFormatFilter] = useState("");

  const canGoPrev = jobsOffset > 0;
  const canGoNext = jobsOffset + jobLimit < jobsTotal;

  const filteredJobs = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return jobs.filter((job) => {
      if (formatFilter && String(job.input_format || "") !== formatFilter) return false;
      if (!q) return true;
      const haystack = [
        job.job_id,
        job.status,
        job.input_format,
        job.created_at,
        job.started_at,
        job.completed_at,
        job.error,
        job.counts ? JSON.stringify(job.counts) : "",
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [jobs, searchQuery, formatFilter]);

  const openJobExport = (jobId, format) => {
    if (!jobId) return;
    const base = (apiBase || "").replace(/\/$/, "");
    window.open(`${base}/jobs/${jobId}/export?format=${format}`, "_blank");
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4 md:space-y-6">
      <section className={sectionCard}>
        <header className="border-b border-slate-800/80 px-4 pt-4 pb-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-50">Job History</h2>
              <p className="mt-1 text-xs text-slate-400">
                Audit and inspect all runs with status and run metadata.
              </p>
            </div>
            <button type="button" className={btnOutline} onClick={onRefresh} disabled={isLoadingJobs}>
              <RefreshCw className={cn("h-3.5 w-3.5", isLoadingJobs && "animate-spin")} />
              Refresh
            </button>
          </div>
        </header>

        <div className="space-y-4 px-4 py-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[130px]">
              <label htmlFor="history-status" className="mb-1 block text-xs font-medium text-slate-300">
                Status
              </label>
              <select
                id="history-status"
                value={jobsStatus}
                onChange={(e) => {
                  setJobsStatus(e.target.value);
                  setJobsOffset(0);
                }}
                className={cn(selectClass, "text-[11px] py-1.5")}
              >
                <option value="">all statuses</option>
                <option value="uploaded">uploaded</option>
                <option value="processing">processing</option>
                <option value="completed">completed</option>
                <option value="failed">failed</option>
                <option value="terminated">terminated</option>
              </select>
            </div>
            <div className="min-w-[120px]">
              <label htmlFor="history-format" className="mb-1 block text-xs font-medium text-slate-300">
                Format
              </label>
              <select
                id="history-format"
                value={formatFilter}
                onChange={(e) => setFormatFilter(e.target.value)}
                className={cn(selectClass, "text-[11px] py-1.5")}
              >
                <option value="">all formats</option>
                <option value="csv">csv</option>
                <option value="json">json</option>
                <option value="propflux">propflux</option>
              </select>
            </div>
            <div className="min-w-[min(100%,280px)] flex-1">
              <label htmlFor="history-search" className="mb-1 block text-xs font-medium text-slate-300">
                Search
              </label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
                <input
                  id="history-search"
                  type="search"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Job ID, status, format…"
                  className={cn(inputClass, "pl-8 text-[11px] py-1.5")}
                />
              </div>
            </div>
            <span className="pb-0.5 font-mono text-[10px] text-slate-500">
              {startIdx}–{endIdx} of {jobsTotal}
            </span>
          </div>

          <div className={cn(innerPanel, "custom-scroll overflow-x-auto")}>
            <table className="min-w-full border-separate border-spacing-y-1 text-xs">
              <thead>
                <tr>
                  {["Job ID", "Status", "Format", "Started", "Ended", "Items", "Export"].map((col) => (
                    <th
                      key={col}
                      className="px-3 pb-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoadingJobs && filteredJobs.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-3 py-10 text-center text-xs text-slate-500">
                      Loading jobs…
                    </td>
                  </tr>
                )}
                {!isLoadingJobs && filteredJobs.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-3 py-10 text-center text-xs text-slate-500">
                      No jobs match the current filters.
                    </td>
                  </tr>
                )}
                {filteredJobs.map((job) => {
                  const canExport = job.status === "completed";
                  return (
                    <tr key={job.job_id} className="group">
                      <td className="px-3 py-2">
                        <span className="font-mono text-[11px] text-slate-300">{job.job_id}</span>
                      </td>
                      <td className="px-3 py-2">
                        <JobStatusPill status={job.status} />
                      </td>
                      <td className="px-3 py-2 text-slate-400">{job.input_format || "—"}</td>
                      <td className="px-3 py-2 font-mono text-[10px] text-slate-500">
                        {formatTimestamp(job.started_at || job.created_at)}
                      </td>
                      <td className="px-3 py-2 font-mono text-[10px] text-slate-500">
                        {formatTimestamp(job.completed_at)}
                      </td>
                      <td className="px-3 py-2 font-mono text-[11px] text-indigo-400">
                        {formatItemCount(job.counts)}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          <button
                            type="button"
                            className={btnOutline}
                            disabled={!canExport}
                            onClick={() => openJobExport(job.job_id, "csv")}
                            title={canExport ? "Export CSV" : "Available when completed"}
                          >
                            <Download className="h-3 w-3" />
                            CSV
                          </button>
                          <button
                            type="button"
                            className={btnOutline}
                            disabled={!canExport}
                            onClick={() => openJobExport(job.job_id, "json")}
                            title={canExport ? "Export JSON" : "Available when completed"}
                          >
                            <Download className="h-3 w-3" />
                            JSON
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800/80 pt-3">
            <button
              type="button"
              className={btnOutline}
              disabled={!canGoPrev || isLoadingJobs}
              onClick={() => setJobsOffset((v) => Math.max(0, v - jobLimit))}
            >
              Prev
            </button>
            <span className="font-mono text-[10px] text-slate-500">
              Page {jobsPage} / {jobsPageCount}
            </span>
            <button
              type="button"
              className={btnOutline}
              disabled={!canGoNext || isLoadingJobs}
              onClick={() => setJobsOffset((v) => v + jobLimit)}
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
