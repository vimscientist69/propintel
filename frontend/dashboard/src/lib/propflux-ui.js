import { cn } from "./cn";

export const sectionCard =
  "rounded-2xl border border-slate-800/80 bg-gradient-to-br from-slate-950 via-slate-950 to-slate-900/80 shadow-[0_18px_60px_rgba(15,23,42,0.9)] overflow-hidden";

export const innerPanel = "rounded-xl border border-slate-800/80 bg-slate-950/30 p-3";

export const inputClass =
  "w-full rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 outline-none transition-colors focus-visible:border-indigo-500 focus-visible:ring-2 focus-visible:ring-indigo-500/40";

export const selectClass = cn(
  inputClass,
  "appearance-none bg-[length:14px] bg-[right_12px_center] bg-no-repeat pr-9",
  "bg-[url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E\")]",
);

export const btnPrimary =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-slate-50 shadow-md shadow-indigo-500/30 transition-colors hover:bg-indigo-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:pointer-events-none disabled:opacity-50";

export const btnOutline =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-900/60 px-3 py-2 text-xs font-medium text-slate-100 transition-colors hover:bg-slate-800/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:pointer-events-none disabled:opacity-50";

export const CHART_COLORS = ["#818cf8", "#22c55e", "#38bdf8", "#fb7185", "#f59e0b"];

export const chartTooltipStyle = {
  contentStyle: {
    background: "#0b1220",
    border: "1px solid #1f2937",
    borderRadius: 10,
    fontSize: 12,
    color: "#e2e8f0",
  },
  itemStyle: { color: "#e2e8f0" },
  labelStyle: { color: "#94a3b8" },
};

export const chartAxisTick = { fill: "#94a3b8", fontSize: 10 };
export const chartGridStroke = "#334155";
