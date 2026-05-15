import React, { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { RefreshCw } from "lucide-react";
import { cn } from "../lib/cn";
import {
  btnOutline,
  chartAxisTick,
  chartGridStroke,
  chartTooltipStyle,
  CHART_COLORS,
  innerPanel,
  sectionCard,
  selectClass,
} from "../lib/propflux-ui";

const SCORE_BUCKETS = [
  { label: "0–20", min: 0, max: 20 },
  { label: "21–40", min: 21, max: 40 },
  { label: "41–60", min: 41, max: 60 },
  { label: "61–80", min: 61, max: 80 },
  { label: "81–100", min: 81, max: 100 },
];

const QUALITY_FIELDS = [
  "email",
  "phone",
  "website",
  "agent_name",
  "location",
  "lead_reason",
  "website_speed_score",
];

function KpiCard({ label, value, hint }) {
  return (
    <div className={cn(innerPanel, "flex flex-col gap-1")}>
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="font-mono text-xl font-semibold text-indigo-400">{value}</p>
      {hint && <p className="text-[10px] text-slate-600">{hint}</p>}
    </div>
  );
}

function ChartBox({ title, subtitle, children }) {
  return (
    <div className={innerPanel}>
      <div className="mb-3">
        <h3 className="text-xs font-semibold text-slate-50">{title}</h3>
        {subtitle && <p className="mt-0.5 text-[10px] text-slate-500">{subtitle}</p>}
      </div>
      <div className="h-56 w-full">{children}</div>
    </div>
  );
}

function heatmapStyle(intensity) {
  const alpha = 0.08 + intensity * 0.42;
  const borderAlpha = 0.18 + intensity * 0.55;
  return {
    background: `rgba(248, 113, 113, ${alpha})`,
    borderColor: `rgba(248, 113, 113, ${borderAlpha})`,
  };
}

function countBy(rows, keyFn) {
  const map = new Map();
  for (const row of rows) {
    const key = keyFn(row);
    map.set(key, (map.get(key) || 0) + 1);
  }
  return Array.from(map.entries()).map(([name, value]) => ({ name, value }));
}

export function Analytics({
  analyticsRows,
  analyticsLoading,
  jobsTotal,
  completedJobsCount,
  jobLimit,
  onJobLimitChange,
  onRefresh,
  rowCountLabel,
}) {
  const metrics = useMemo(() => {
    const n = analyticsRows.length;
    if (n === 0) {
      return {
        avgScore: 0,
        verifiedRate: 0,
        scoreBuckets: SCORE_BUCKETS.map((b) => ({ name: b.label, count: 0 })),
        qualitySplit: [],
        chatbotSplit: [],
        freshnessSplit: [],
        missingFields: [],
      };
    }

    const avgScore = Math.round(
      analyticsRows.reduce((acc, row) => acc + Number(row.lead_score || 0), 0) / n,
    );
    const verifiedCount = analyticsRows.filter((r) => r.contact_quality === "verified").length;
    const verifiedRate = Math.round((verifiedCount / n) * 100);

    const scoreBuckets = SCORE_BUCKETS.map((bucket) => ({
      name: bucket.label,
      count: analyticsRows.filter((r) => {
        const s = Number(r.lead_score || 0);
        return s >= bucket.min && s <= bucket.max;
      }).length,
    }));

    const qualitySplit = countBy(analyticsRows, (r) => {
      const q = String(r.contact_quality || "unknown").toLowerCase();
      return q || "unknown";
    });

    const chatbotSplit = countBy(analyticsRows, (r) => {
      if (r.has_chatbot === true) return "has chatbot";
      if (r.has_chatbot === false) return "no chatbot";
      return "unknown";
    });

    const freshnessSplit = countBy(analyticsRows, (r) => {
      const f = String(r.last_updated_signal || "unknown").toLowerCase();
      return f || "unknown";
    });

    const missingFields = QUALITY_FIELDS.map((field) => {
      const missing = analyticsRows.filter((r) => {
        const v = r[field];
        return v === null || v === undefined || v === "";
      }).length;
      const pct = Math.round((missing / n) * 100);
      return { field, pct, missing };
    }).sort((a, b) => b.pct - a.pct);

    return {
      avgScore,
      verifiedRate,
      scoreBuckets,
      qualitySplit,
      chatbotSplit,
      freshnessSplit,
      missingFields,
    };
  }, [analyticsRows]);

  const empty = !analyticsLoading && analyticsRows.length === 0;

  return (
    <div className="mx-auto max-w-6xl space-y-4 md:space-y-6">
      <section className={sectionCard}>
        <header className="border-b border-slate-800/80 px-4 pt-4 pb-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-50">Analytics Dashboard</h2>
              <p className="mt-1 text-xs text-slate-400">
                Lead quality and pipeline outcomes from completed jobs.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={String(jobLimit)}
                onChange={(e) => onJobLimitChange(Number(e.target.value))}
                className={cn(selectClass, "w-auto min-w-[120px] text-[11px] py-1.5")}
                aria-label="Jobs sample size"
              >
                <option value="10">Last 10 jobs</option>
                <option value="25">Last 25 jobs</option>
                <option value="50">Last 50 jobs</option>
              </select>
              <button type="button" className={btnOutline} onClick={onRefresh} disabled={analyticsLoading}>
                <RefreshCw className={cn("h-3.5 w-3.5", analyticsLoading && "animate-spin")} />
                Refresh
              </button>
            </div>
          </div>
        </header>

        <div className="space-y-4 px-4 py-4">
          {analyticsLoading && (
            <p className="text-xs text-slate-500">Loading analytics from completed jobs…</p>
          )}

          {empty && (
            <div className="rounded-xl border border-slate-800/80 bg-slate-900/80 px-3 py-6 text-center text-xs text-slate-400">
              No completed job data yet. Run and complete a job from the Control Panel to populate analytics.
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard label="Total jobs" value={jobsTotal} hint="All statuses" />
            <KpiCard label="Completed jobs" value={completedJobsCount} hint={`Sample: ${jobLimit} max`} />
            <KpiCard label="Avg lead score" value={metrics.avgScore} hint={rowCountLabel} />
            <KpiCard label="Verified rate" value={`${metrics.verifiedRate}%`} hint="Contact quality" />
          </div>

          {!empty && (
            <>
              <div className="grid gap-4 lg:grid-cols-2">
                <ChartBox title="Lead score distribution" subtitle="Buckets across sampled leads">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={metrics.scoreBuckets} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                      <CartesianGrid stroke={chartGridStroke} strokeDasharray="4 4" opacity={0.35} vertical={false} />
                      <XAxis dataKey="name" tick={chartAxisTick} axisLine={false} tickLine={false} />
                      <YAxis tick={chartAxisTick} axisLine={false} tickLine={false} allowDecimals={false} />
                      <Tooltip {...chartTooltipStyle} />
                      <Bar dataKey="count" fill="#818cf8" radius={[6, 6, 0, 0]} maxBarSize={48} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartBox>

                <ChartBox title="Contact quality" subtitle="Verified / likely / low split">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={metrics.qualitySplit}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius={52}
                        outerRadius={78}
                        paddingAngle={2}
                      >
                        {metrics.qualitySplit.map((_, i) => (
                          <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip {...chartTooltipStyle} />
                    </PieChart>
                  </ResponsiveContainer>
                </ChartBox>

                <ChartBox title="Chatbot signal" subtitle="Detection across leads">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={metrics.chatbotSplit} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                      <CartesianGrid stroke={chartGridStroke} strokeDasharray="4 4" opacity={0.35} vertical={false} />
                      <XAxis dataKey="name" tick={chartAxisTick} axisLine={false} tickLine={false} />
                      <YAxis tick={chartAxisTick} axisLine={false} tickLine={false} allowDecimals={false} />
                      <Tooltip {...chartTooltipStyle} />
                      <Bar dataKey="value" fill="#38bdf8" radius={[6, 6, 0, 0]} maxBarSize={48} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartBox>

                <ChartBox title="Freshness signal" subtitle="Last-updated detection">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={metrics.freshnessSplit} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
                      <CartesianGrid stroke={chartGridStroke} strokeDasharray="4 4" opacity={0.35} vertical={false} />
                      <XAxis dataKey="name" tick={chartAxisTick} axisLine={false} tickLine={false} />
                      <YAxis tick={chartAxisTick} axisLine={false} tickLine={false} allowDecimals={false} />
                      <Tooltip {...chartTooltipStyle} />
                      <Bar dataKey="value" fill="#22c55e" radius={[6, 6, 0, 0]} maxBarSize={48} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartBox>
              </div>

              <div className={innerPanel}>
                <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
                  <div>
                    <h3 className="text-xs font-semibold text-slate-50">Missing fields heatmap</h3>
                    <p className="mt-0.5 text-[10px] text-slate-500">
                      Data completeness across sampled leads
                    </p>
                  </div>
                  <span className="font-mono text-[10px] text-slate-500">{rowCountLabel}</span>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7">
                  {metrics.missingFields.map(({ field, pct }) => (
                    <div
                      key={field}
                      className="rounded-xl border px-2.5 py-2"
                      style={heatmapStyle(pct / 100)}
                    >
                      <p className="font-mono text-[10px] font-semibold text-slate-100">{field}</p>
                      <p className="mt-1 text-[10px] text-slate-400">{pct}% missing</p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
