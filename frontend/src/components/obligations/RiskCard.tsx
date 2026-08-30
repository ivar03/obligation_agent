import React from "react";
import Link from "next/link";
import { RiskAssessmentResponse, RiskLevel } from "@/lib/types/obligation";

interface RiskCardProps {
  assessment: RiskAssessmentResponse;
  compact?: boolean;
  onRefresh?: () => void;
}

export const RiskCard: React.FC<RiskCardProps> = ({ assessment, compact = false }) => {
  const {
    obligation_id,
    owner,
    beneficiary,
    action,
    risk_level,
    risk_score,
    deadline,
    dependent_count,
    reasons,
    recommended_action,
    action_type,
  } = assessment;

  const scorePct = Math.round(risk_score * 100);

  const getRiskStyle = (level: RiskLevel) => {
    switch (level) {
      case "CRITICAL":
        return {
          border: "border-red-500/40 hover:border-red-500/80 shadow-red-950/20",
          badge: "bg-red-500/10 text-red-400 border-red-500/30",
          bar: "bg-gradient-to-r from-orange-500 to-red-500",
          text: "text-red-400",
          glow: "from-red-900/10 to-transparent",
        };
      case "HIGH":
        return {
          border: "border-amber-500/40 hover:border-amber-500/80 shadow-amber-950/20",
          badge: "bg-amber-500/10 text-amber-400 border-amber-500/30",
          bar: "bg-gradient-to-r from-yellow-500 to-amber-500",
          text: "text-amber-400",
          glow: "from-amber-900/10 to-transparent",
        };
      case "MEDIUM":
        return {
          border: "border-blue-500/40 hover:border-blue-500/80 shadow-blue-950/20",
          badge: "bg-blue-500/10 text-blue-400 border-blue-500/30",
          bar: "bg-blue-500",
          text: "text-blue-400",
          glow: "from-blue-900/10 to-transparent",
        };
      case "LOW":
      default:
        return {
          border: "border-emerald-500/30 hover:border-emerald-500/60 shadow-emerald-950/20",
          badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
          bar: "bg-emerald-500",
          text: "text-emerald-400",
          glow: "from-emerald-900/10 to-transparent",
        };
    }
  };

  const style = getRiskStyle(risk_level);

  const formatDeadline = (iso?: string | null) => {
    if (!iso) return "No calendar deadline";
    const date = new Date(iso);
    const now = new Date();
    const diffHours = Math.round((date.getTime() - now.getTime()) / (1000 * 3600));

    if (diffHours < 0) {
      return `${Math.abs(diffHours)}h overdue`;
    }
    if (diffHours <= 24) {
      return `Due in ${diffHours}h`;
    }
    const days = Math.round(diffHours / 24);
    return `Due in ${days}d (${date.toLocaleDateString(undefined, { month: "short", day: "numeric" })})`;
  };

  const getActionBadge = (type: string) => {
    switch (type) {
      case "RESOLVE_DEPENDENCY":
        return "bg-purple-950/60 text-purple-300 border-purple-800/50";
      case "FOLLOW_UP_OWNER":
        return "bg-indigo-950/60 text-indigo-300 border-indigo-800/50";
      case "START_WORK":
        return "bg-amber-950/60 text-amber-300 border-amber-800/50";
      case "REVIEW_EVIDENCE":
        return "bg-cyan-950/60 text-cyan-300 border-cyan-800/50";
      case "ASSIGN_OWNER":
        return "bg-rose-950/60 text-rose-300 border-rose-800/50";
      case "MONITOR_CONDITION":
        return "bg-teal-950/60 text-teal-300 border-teal-800/50";
      default:
        return "bg-zinc-800 text-zinc-300 border-zinc-700";
    }
  };

  return (
    <div
      className={`relative rounded-xl border bg-zinc-900/90 backdrop-blur-md p-4 transition-all duration-200 hover:shadow-lg ${style.border}`}
    >
      {/* Background radial gradient accent */}
      <div
        className={`pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-br ${style.glow}`}
      />

      <div className="relative z-10 space-y-3">
        {/* Top Header: Risk Level & Score */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide border uppercase ${style.badge}`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
              {risk_level} Risk · {scorePct}%
            </span>

            {dependent_count > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20">
                ⚡ Blocks {dependent_count} {dependent_count === 1 ? "task" : "tasks"}
              </span>
            )}
          </div>

          <span className="text-xs font-mono text-zinc-400">
            {formatDeadline(deadline)}
          </span>
        </div>

        {/* Obligation Description */}
        <div>
          <Link
            href={`/obligations/${obligation_id}`}
            className="group block text-sm font-semibold text-zinc-100 hover:text-white transition-colors line-clamp-2"
          >
            <span className="group-hover:underline">{action}</span>
          </Link>
          <div className="mt-1 flex items-center gap-2 text-xs text-zinc-400">
            <span>
              <strong className="text-zinc-300 font-medium">{owner}</strong> owes{" "}
              <strong className="text-zinc-300 font-medium">{beneficiary}</strong>
            </span>
          </div>
        </div>

        {/* Primary Reasons / Signals */}
        {!compact && reasons && reasons.length > 0 && (
          <div className="space-y-1.5 rounded-lg bg-zinc-950/60 p-2.5 border border-zinc-800/80 text-xs">
            <div className="text-[11px] uppercase tracking-wider font-semibold text-zinc-500">
              Risk Signals & Root Causes:
            </div>
            <ul className="space-y-1 text-zinc-300">
              {reasons.slice(0, 3).map((r, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="text-zinc-500 mt-0.5">▪</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Recommended Action Footer */}
        <div className="pt-2 border-t border-zinc-800 flex items-center justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span
                className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border ${getActionBadge(
                  action_type
                )}`}
              >
                {action_type.replace(/_/g, " ")}
              </span>
              <span className="text-xs text-zinc-300 truncate font-medium">
                {recommended_action}
              </span>
            </div>
          </div>

          <Link
            href={`/obligations/${obligation_id}`}
            className="shrink-0 px-3 py-1 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 hover:text-white transition-colors border border-zinc-700/60"
          >
            Inspect →
          </Link>
        </div>
      </div>
    </div>
  );
};
