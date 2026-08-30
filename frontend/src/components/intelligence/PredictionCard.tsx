"use client";

import React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Clock,
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { ObligationPredictionResponse } from "@/lib/types/obligation";

interface PredictionCardProps {
  prediction: ObligationPredictionResponse;
  compact?: boolean;
}

export function PredictionCard({ prediction, compact = false }: PredictionCardProps) {
  const failurePct = Math.round(prediction.failure_probability * 100);
  const completionPct = Math.round(prediction.completion_probability * 100);

  // Status color styles
  const isHighRisk = failurePct >= 65;
  const isModerateRisk = failurePct >= 40 && failurePct < 65;

  const badgeColor = isHighRisk
    ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
    : isModerateRisk
    ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
    : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";

  const progressBg = isHighRisk
    ? "bg-rose-500"
    : isModerateRisk
    ? "bg-amber-500"
    : "bg-emerald-500";

  return (
    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-all shadow-lg flex flex-col justify-between">
      <div>
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${badgeColor}`}>
                {isHighRisk ? "High Failure Probability" : isModerateRisk ? "Elevated Delay Risk" : "Likely On-Time"}
              </span>
              <span className="text-xs text-slate-500 font-mono">
                {prediction.model_version}
              </span>
            </div>
            <Link
              href={`/obligations/${prediction.obligation_id}`}
              className="text-base font-semibold text-slate-200 hover:text-indigo-400 transition-colors line-clamp-1"
            >
              {prediction.action || `Obligation ${prediction.obligation_id.slice(0, 8)}`}
            </Link>
            <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-3">
              <span>Owner: <strong className="text-slate-300 font-medium">{prediction.owner || "Unassigned"}</strong></span>
              {prediction.beneficiary && (
                <span>Beneficiary: <strong className="text-slate-300 font-medium">{prediction.beneficiary}</strong></span>
              )}
            </div>
          </div>

          <div className="text-right">
            <div className="text-2xl font-bold text-slate-100 font-mono">
              {failurePct}%
            </div>
            <div className="text-[11px] text-slate-400">Failure Prob.</div>
          </div>
        </div>

        {/* Probability Meter */}
        <div className="space-y-1.5 my-3">
          <div className="flex justify-between text-xs font-medium text-slate-400">
            <span className="flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              Completion {completionPct}%
            </span>
            <span className="flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
              Failure {failurePct}%
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden flex">
            <div
              className={`${progressBg} h-full transition-all duration-500`}
              style={{ width: `${failurePct}%` }}
            />
          </div>
        </div>

        {/* Projections */}
        <div className="grid grid-cols-2 gap-2 my-3 p-2.5 bg-slate-950/40 rounded-lg border border-slate-800/80 text-xs">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-400 shrink-0" />
            <div>
              <div className="text-slate-400 text-[10px]">Expected Delay</div>
              <div className="font-semibold text-slate-200 font-mono">
                {prediction.expected_delay_hours > 0 ? `+${prediction.expected_delay_hours}h` : "On Schedule"}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400 shrink-0" />
            <div>
              <div className="text-slate-400 text-[10px]">Intervention Need</div>
              <div className="font-semibold text-slate-200 font-mono">
                {Math.round(prediction.intervention_likelihood * 100)}%
              </div>
            </div>
          </div>
        </div>

        {/* Explanations List */}
        {!compact && prediction.reasons && prediction.reasons.length > 0 && (
          <div className="space-y-1.5 my-3">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Why this prediction?
            </div>
            <ul className="space-y-1 text-xs text-slate-300">
              {prediction.reasons.slice(0, 3).map((r, idx) => (
                <li key={idx} className="flex items-start gap-1.5 bg-slate-950/20 p-1.5 rounded border border-slate-800/40">
                  <span className={`text-[10px] font-mono font-bold px-1.5 py-0.2 rounded shrink-0 ${
                    r.impact > 0 ? "bg-rose-500/20 text-rose-300" : "bg-emerald-500/20 text-emerald-300"
                  }`}>
                    {r.impact > 0 ? `+${r.impact}` : r.impact}
                  </span>
                  <span className="line-clamp-2 leading-relaxed">{r.explanation}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Footer / Preventative Action */}
      <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between gap-3 text-xs">
        <div className="text-slate-400 flex items-center gap-1.5 line-clamp-1">
          <ShieldCheck className="w-4 h-4 text-indigo-400 shrink-0" />
          <span className="truncate">
            {prediction.preventative_recommendation || "Maintain standard monitoring."}
          </span>
        </div>
        <Link
          href={`/obligations/${prediction.obligation_id}`}
          className="shrink-0 text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1 group"
        >
          Details
          <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
        </Link>
      </div>
    </div>
  );
}
