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
          border: "border-red-200 hover:border-red-300",
          badge: "bg-red-50 text-red-700 border-red-200",
          bar: "bg-red-500",
          text: "text-red-700",
          glow: "from-red-500/5 to-transparent",
        };
      case "HIGH":
        return {
          border: "border-orange-200 hover:border-orange-300",
          badge: "bg-orange-50 text-orange-700 border-orange-200",
          bar: "bg-orange-500",
          text: "text-orange-700",
          glow: "from-orange-500/5 to-transparent",
        };
      case "MEDIUM":
        return {
          border: "border-amber-200 hover:border-amber-300",
          badge: "bg-amber-50 text-amber-700 border-amber-200",
          bar: "bg-amber-500",
          text: "text-amber-700",
          glow: "from-amber-500/5 to-transparent",
        };
      case "LOW":
      default:
        return {
          border: "border-emerald-200 hover:border-emerald-300",
          badge: "bg-emerald-50 text-emerald-700 border-emerald-200",
          bar: "bg-emerald-500",
          text: "text-emerald-700",
          glow: "from-emerald-500/5 to-transparent",
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
        return "bg-orange-50 text-orange-700 border-orange-200";
      case "FOLLOW_UP_OWNER":
        return "bg-orange-50 text-orange-700 border-orange-200";
      case "START_WORK":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "REVIEW_EVIDENCE":
        return "bg-stone-100 text-stone-700 border-stone-200";
      case "ASSIGN_OWNER":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "MONITOR_CONDITION":
        return "bg-stone-100 text-stone-700 border-stone-200";
      default:
        return "bg-stone-100 text-stone-700 border-stone-200";
    }
  };

  return (
    <div
      className={`relative rounded-xl border bg-white p-4 transition-all duration-200 hover:shadow-md ${style.border}`}
    >
      {/* Background soft accent */}
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
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
                ⚡ Blocks {dependent_count} {dependent_count === 1 ? "task" : "tasks"}
              </span>
            )}
          </div>

          <span className="text-xs font-mono text-stone-500">
            {formatDeadline(deadline)}
          </span>
        </div>

        {/* Obligation Description */}
        <div>
          <Link
            href={`/obligations/${obligation_id}`}
            className="group block text-sm font-semibold text-stone-900 hover:text-orange-600 transition-colors line-clamp-2"
          >
            <span className="group-hover:underline">{action}</span>
          </Link>
          <div className="mt-1 flex items-center gap-2 text-xs text-stone-600">
            <span>
              <strong className="text-stone-700 font-medium">{owner}</strong> owes{" "}
              <strong className="text-stone-700 font-medium">{beneficiary}</strong>
            </span>
          </div>
        </div>

        {/* Primary Reasons / Signals */}
        {!compact && reasons && reasons.length > 0 && (
          <div className="space-y-1.5 rounded-lg bg-stone-50 p-2.5 border border-stone-200 text-xs">
            <div className="text-[11px] uppercase tracking-wider font-semibold text-stone-500">
              Risk Signals & Root Causes:
            </div>
            <ul className="space-y-1 text-stone-700">
              {reasons.slice(0, 3).map((r, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="text-stone-400 mt-0.5">▪</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Recommended Action Footer */}
        <div className="pt-2 border-t border-stone-100 flex items-center justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span
                className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border ${getActionBadge(
                  action_type
                )}`}
              >
                {action_type.replace(/_/g, " ")}
              </span>
              <span className="text-xs text-stone-700 truncate font-medium">
                {recommended_action}
              </span>
            </div>
          </div>

          <Link
            href={`/obligations/${obligation_id}`}
            className="shrink-0 px-3 py-1 text-xs font-medium rounded-lg bg-white hover:bg-stone-50 text-stone-700 hover:text-stone-900 transition-colors border border-stone-200 shadow-sm"
          >
            Inspect →
          </Link>
        </div>
      </div>
    </div>
  );
};
