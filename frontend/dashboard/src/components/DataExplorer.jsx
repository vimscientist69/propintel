import React, { useEffect, useMemo, useState } from "react";
import { ExternalLink, RefreshCw, Search } from "lucide-react";
import { cn } from "../lib/cn";
import { btnOutline, innerPanel, inputClass, sectionCard, selectClass } from "../lib/propflux-ui";

function ContactQualityPill({ status }) {
  const styles = {
    verified: "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
    likely: "border-indigo-500/40 bg-indigo-500/15 text-indigo-300",
    low: "border-rose-500/40 bg-rose-500/15 text-rose-300",
  };
  const key = String(status || "unknown").toLowerCase();
  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        styles[key] || "border-slate-700 bg-slate-900/80 text-slate-400",
      )}
    >
      {status || "unknown"}
    </span>
  );
}

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

export function DataExplorer({
  jobs,
  explorerJobId,
  setExplorerJobId,
  explorerJobStatus,
  explorerRows,
  explorerLoading,
  minScore,
  setMinScore,
  qualityFilter,
  setQualityFilter,
  chatbotFilter,
  setChatbotFilter,
  freshnessFilter,
  setFreshnessFilter,
  onReload,
  onExport,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [pageSize, setPageSize] = useState(25);
  const [pageOffset, setPageOffset] = useState(0);

  const showPartial =
    explorerJobStatus === "processing" || explorerJobStatus === "uploaded";

  const filteredRows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return explorerRows
      .filter((row) => Number(row.lead_score || 0) >= Number(minScore || 0))
      .filter((row) => (qualityFilter ? String(row.contact_quality || "") === qualityFilter : true))
      .filter((row) => {
        if (!chatbotFilter) return true;
        if (chatbotFilter === "yes") return row.has_chatbot === true;
        return row.has_chatbot === false;
      })
      .filter((row) =>
        freshnessFilter ? String(row.last_updated_signal || "") === freshnessFilter : true,
      )
      .filter((row) => {
        if (!q) return true;
        const haystack = [
          row.company_name,
          row.agent_name,
          row.location,
          row.email,
          row.website,
          row.phone,
          row.lead_reason,
          row.source,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(q);
      });
  }, [explorerRows, minScore, qualityFilter, chatbotFilter, freshnessFilter, searchQuery]);

  useEffect(() => {
    setPageOffset(0);
  }, [searchQuery, minScore, qualityFilter, chatbotFilter, freshnessFilter, pageSize, explorerJobId]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const currentPage = Math.min(pageOffset + 1, totalPages);
  const canGoPrev = pageOffset > 0;
  const canGoNext = pageOffset + 1 < totalPages;

  const paginatedRows = filteredRows.slice(pageOffset * pageSize, pageOffset * pageSize + pageSize);

  const startIdx = filteredRows.length === 0 ? 0 : pageOffset * pageSize + 1;
  const endIdx = Math.min((pageOffset + 1) * pageSize, filteredRows.length);

  const openWebsite = (url) => {
    if (!url) return;
    const href = String(url).startsWith("http") ? url : `https://${url}`;
    window.open(href, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4 md:space-y-6">
      <section className={sectionCard}>
        <header className="border-b border-slate-800/80 px-4 pt-4 pb-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-50">Data Explorer</h2>
              <p className="mt-1 text-xs text-slate-400">Search and inspect lead rows for a selected job.</p>
              {showPartial && (
                <span className="mt-2 inline-flex items-center rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-0.5 text-[10px] text-indigo-300">
                  Showing partial batch results
                </span>
              )}
            </div>
            <button
              type="button"
              className={btnOutline}
              onClick={onReload}
              disabled={!explorerJobId || explorerLoading}
            >
              <RefreshCw className={cn("h-3.5 w-3.5", explorerLoading && "animate-spin")} />
              Reload
            </button>
          </div>
        </header>

        <div className="space-y-4 px-4 py-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[160px]">
                <label htmlFor="explorer-job" className="mb-1 block text-xs font-medium text-slate-300">
                  Selected job
                </label>
                <select
                  id="explorer-job"
                  value={explorerJobId}
                  onChange={(e) => setExplorerJobId(e.target.value)}
                  className={cn(selectClass, "text-[11px] py-1.5")}
                >
                  <option value="">select a job</option>
                  {jobs.map((job) => (
                    <option key={job.job_id} value={job.job_id}>
                      {job.job_id.slice(0, 8)} ({job.status})
                    </option>
                  ))}
                </select>
              </div>
              <div className="min-w-[110px]">
                <label htmlFor="explorer-page-size" className="mb-1 block text-xs font-medium text-slate-300">
                  Per page
                </label>
                <select
                  id="explorer-page-size"
                  value={String(pageSize)}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  className={cn(selectClass, "text-[11px] py-1.5")}
                >
                  {PAGE_SIZE_OPTIONS.map((n) => (
                    <option key={n} value={n}>
                      {n} / page
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search company, location, email, website…"
                className={cn(inputClass, "pl-8 text-sm")}
              />
            </div>
            <span className="shrink-0 font-mono text-[11px] text-slate-500">
              {filteredRows.length} result{filteredRows.length === 1 ? "" : "s"}
            </span>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[90px]">
              <label htmlFor="explorer-min-score" className="mb-1 block text-xs font-medium text-slate-300">
                Min score
              </label>
              <input
                id="explorer-min-score"
                type="number"
                min="0"
                max="100"
                value={minScore}
                onChange={(e) => setMinScore(e.target.value)}
                className={cn(inputClass, "text-[11px] py-1.5")}
              />
            </div>
            <div className="min-w-[120px]">
              <label htmlFor="explorer-quality" className="mb-1 block text-xs font-medium text-slate-300">
                Quality
              </label>
              <select
                id="explorer-quality"
                value={qualityFilter}
                onChange={(e) => setQualityFilter(e.target.value)}
                className={cn(selectClass, "text-[11px] py-1.5")}
              >
                <option value="">all quality</option>
                <option value="verified">verified</option>
                <option value="likely">likely</option>
                <option value="low">low</option>
              </select>
            </div>
            <div className="min-w-[120px]">
              <label htmlFor="explorer-chatbot" className="mb-1 block text-xs font-medium text-slate-300">
                Chatbot
              </label>
              <select
                id="explorer-chatbot"
                value={chatbotFilter}
                onChange={(e) => setChatbotFilter(e.target.value)}
                className={cn(selectClass, "text-[11px] py-1.5")}
              >
                <option value="">all</option>
                <option value="yes">has chatbot</option>
                <option value="no">no chatbot</option>
              </select>
            </div>
            <div className="min-w-[120px]">
              <label htmlFor="explorer-freshness" className="mb-1 block text-xs font-medium text-slate-300">
                Freshness
              </label>
              <select
                id="explorer-freshness"
                value={freshnessFilter}
                onChange={(e) => setFreshnessFilter(e.target.value)}
                className={cn(selectClass, "text-[11px] py-1.5")}
              >
                <option value="">all</option>
                <option value="detected">detected</option>
                <option value="unknown">unknown</option>
              </select>
            </div>
            <div className="flex flex-wrap gap-2 pb-0.5">
              <button
                type="button"
                className={btnOutline}
                disabled={!explorerJobId}
                onClick={() => onExport("json")}
              >
                Export JSON
              </button>
              <button
                type="button"
                className={btnOutline}
                disabled={!explorerJobId}
                onClick={() => onExport("csv")}
              >
                Export CSV
              </button>
            </div>
          </div>

          <div className={cn(innerPanel, "custom-scroll overflow-x-auto")}>
            <table className="min-w-full border-separate border-spacing-y-1 text-xs">
              <thead>
                <tr>
                  {[
                    { label: "Company", className: "" },
                    { label: "Status", className: "" },
                    { label: "Website", className: "hidden md:table-cell" },
                    { label: "Email", className: "" },
                    { label: "Phone", className: "hidden md:table-cell" },
                    { label: "Score", className: "" },
                    { label: "Link", className: "w-12" },
                  ].map(({ label, className }) => (
                    <th
                      key={label}
                      className={cn(
                        "px-3 pb-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500",
                        className,
                      )}
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!explorerJobId && (
                  <tr>
                    <td colSpan={7} className="px-3 py-10 text-center text-xs text-slate-500">
                      Select a job to load lead rows.
                    </td>
                  </tr>
                )}
                {explorerJobId && explorerLoading && paginatedRows.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-3 py-10 text-center text-xs text-slate-500">
                      Loading leads…
                    </td>
                  </tr>
                )}
                {explorerJobId && !explorerLoading && paginatedRows.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-3 py-10 text-center text-xs text-slate-500">
                      No rows match the current filters.
                    </td>
                  </tr>
                )}
                {paginatedRows.map((row, idx) => (
                  <tr key={`${row.company_name || "row"}-${idx}`}>
                    <td className="rounded-xl border border-slate-800/80 bg-slate-950/80 px-3 py-2 font-medium text-slate-100">
                      {row.company_name || "—"}
                    </td>
                    <td className="px-3 py-2">
                      <ContactQualityPill status={row.contact_quality} />
                    </td>
                    <td className="hidden max-w-[180px] px-3 py-2 text-slate-400 break-all md:table-cell">
                      {row.website || "—"}
                    </td>
                    <td className="max-w-[160px] px-3 py-2 text-slate-400 break-all">{row.email || "—"}</td>
                    <td className="hidden px-3 py-2 font-mono text-[11px] text-slate-400 md:table-cell">
                      {row.phone || "—"}
                    </td>
                    <td className="px-3 py-2 font-semibold text-indigo-400">{row.lead_score ?? "—"}</td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-800 bg-slate-900/80 text-slate-400 transition-colors hover:border-indigo-500/50 hover:text-indigo-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:pointer-events-none disabled:opacity-40"
                        disabled={!row.website}
                        onClick={() => openWebsite(row.website)}
                        title={row.website ? "Open website" : "No website"}
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {explorerJobId && filteredRows.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800/80 pt-3">
              <button
                type="button"
                className={btnOutline}
                disabled={!canGoPrev}
                onClick={() => setPageOffset((p) => Math.max(0, p - 1))}
              >
                Prev
              </button>
              <span className="font-mono text-[10px] text-slate-500">
                {startIdx}–{endIdx} of {filteredRows.length} · Page {currentPage} / {totalPages}
              </span>
              <button
                type="button"
                className={btnOutline}
                disabled={!canGoNext}
                onClick={() => setPageOffset((p) => p + 1)}
              >
                Next
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
