import React from "react";
import { Sparkles, AlertTriangle, CheckCircle2 } from "lucide-react";
import { FieldConfidence } from "@/lib/types/obligation";

interface ConfidenceBadgeProps {
  confidence?: Record<string, unknown> | FieldConfidence | null;
  field?: string;
  showIcon?: boolean;
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({
  confidence,
  field = "overall",
  showIcon = true,
}) => {
  if (!confidence) return null;

  let score = 1.0;
  if (typeof confidence === "object" && confidence !== null) {
    if (field in confidence) {
      const val = (confidence as Record<string, unknown>)[field];
      if (typeof val === "number") score = val;
    } else if ("overall" in confidence) {
      const val = (confidence as Record<string, unknown>).overall;
      if (typeof val === "number") score = val;
    }
  }

  const percentage = Math.round(score * 100);

  let colorClass = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
  let Icon = CheckCircle2;
  let label = "High AI Confidence";

  if (percentage < 60) {
    colorClass = "bg-rose-500/10 text-rose-400 border-rose-500/20";
    Icon = AlertTriangle;
    label = "Ambiguous / Review";
  } else if (percentage < 85) {
    colorClass = "bg-amber-500/10 text-amber-400 border-amber-500/20";
    Icon = Sparkles;
    label = "Moderate Confidence";
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border ${colorClass}`}
      title={`Field: ${field} (${percentage}% confidence)`}
    >
      {showIcon && <Icon className="w-3 h-3" />}
      <span>{percentage}%</span>
      <span className="hidden sm:inline opacity-75">{label}</span>
    </span>
  );
};
