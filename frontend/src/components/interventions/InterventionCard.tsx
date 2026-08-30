"use client";

import React from "react";
import Link from "next/link";
import {
  Send,
  CheckCircle2,
  Clock,
  AlertTriangle,
  User,
  Layers,
  ArrowUpRight,
  Sparkles,
  Calendar,
  Flame,
  MessageSquareText,
} from "lucide-react";
import { Intervention } from "@/lib/types/obligation";

interface InterventionCardProps {
  intervention: Intervention;
  onReview?: (intervention: Intervention) => void;
  onExecute?: (intervention: Intervention) => void;
}

export function InterventionCard({
  intervention,
  onReview,
  onExecute,
}: InterventionCardProps) {
  const isUrgent = intervention.urgency === "CRITICAL" || intervention.urgency === "HIGH";

  const getUrgencyBadge = () => {
    switch (intervention.urgency) {
      case "CRITICAL":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
            <Flame className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
            CRITICAL
          </span>
        );
      case "HIGH":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            HIGH
          </span>
        );
      case "MEDIUM":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/20 text-blue-300 border border-blue-500/30">
            MEDIUM
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-800 text-zinc-300 border border-zinc-700">
            LOW
          </span>
        );
    }
  };

  const getStatusBadge = () => {
    switch (intervention.status) {
      case "PENDING_REVIEW":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/30">
            <Clock className="w-3 h-3 text-amber-400" />
            Pending Review
          </span>
        );
      case "APPROVED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            Approved
          </span>
        );
      case "SCHEDULED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-300 border border-purple-500/30">
            <Calendar className="w-3 h-3 text-purple-400" />
            Scheduled
          </span>
        );
      case "EXECUTED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-300 border border-blue-500/30">
            <Send className="w-3 h-3 text-blue-400" />
            Executed
          </span>
        );
      case "ACKNOWLEDGED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
            <MessageSquareText className="w-3 h-3 text-cyan-400" />
            Acknowledged
          </span>
        );
      case "RESOLVED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-zinc-800 text-zinc-400 border border-zinc-700">
            <CheckCircle2 className="w-3 h-3 text-zinc-400" />
            Resolved
          </span>
        );
      case "CANCELLED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-zinc-900 text-zinc-500 border border-zinc-800">
            Cancelled
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-zinc-800 text-zinc-400 border border-zinc-700">
            {intervention.status}
          </span>
        );
    }
  };

  const formattedType = intervention.intervention_type.replace(/_/g, " ");

  return (
    <div
      className={`rounded-2xl border transition-all duration-200 p-5 ${
        isUrgent
          ? "bg-zinc-900/90 border-amber-500/40 hover:border-amber-500/60 shadow-lg shadow-amber-950/20"
          : "bg-zinc-900/70 border-zinc-800/80 hover:border-zinc-700 shadow-md"
      }`}
    >
      {/* Header: Type, Urgency, Status */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 mb-3">
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-0.5 rounded-lg text-xs font-bold uppercase tracking-wider bg-zinc-800 text-zinc-300 border border-zinc-700">
            {formattedType}
          </span>
          {getUrgencyBadge()}
        </div>
        <div>{getStatusBadge()}</div>
      </div>

      {/* Title & Target */}
      <div className="space-y-1 mb-3">
        <h3 className="text-base font-bold text-white tracking-tight flex items-center justify-between gap-2">
          <span>{intervention.title}</span>
          <Link
            href={`/interventions/${intervention.id}`}
            className="text-zinc-400 hover:text-blue-400 transition-colors"
            title="Inspect Audit Detail"
          >
            <ArrowUpRight className="w-4 h-4" />
          </Link>
        </h3>
        <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-400">
          <span className="inline-flex items-center gap-1 font-medium text-zinc-300">
            <User className="w-3.5 h-3.5 text-blue-400" />
            Target: <strong className="text-white font-semibold">{intervention.target_owner}</strong>
          </span>
          {intervention.chain_depth > 1 && (
            <span className="inline-flex items-center gap-1 text-amber-300 font-medium bg-amber-500/10 px-2 py-0.5 rounded-md border border-amber-500/20">
              ⚡ Follow-up #{intervention.chain_depth}
            </span>
          )}
        </div>
      </div>

      {/* Rationale Explanation */}
      <p className="text-xs text-zinc-300 mb-3.5 bg-zinc-950/60 p-2.5 rounded-xl border border-zinc-800/80 leading-relaxed">
        <strong className="text-zinc-400 font-medium">Why: </strong>
        {intervention.rationale}
      </p>

      {/* Suggested / Approved Message Draft Snippet */}
      <div className="mb-4 bg-zinc-950 border border-zinc-800 rounded-xl p-3">
        <div className="flex items-center justify-between text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
          <span className="flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-blue-400" />
            {intervention.approved_message && intervention.status !== "PENDING_REVIEW"
              ? "Approved Message Draft"
              : "Suggested Message Draft"}
          </span>
          <span className="text-zinc-400 lowercase font-normal">human approval required</span>
        </div>
        <p className="text-xs text-zinc-200 italic line-clamp-3 leading-relaxed">
          &ldquo;{intervention.approved_message || intervention.message_draft}&rdquo;
        </p>
      </div>

      {/* Footer & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-zinc-800/80">
        <Link
          href={`/obligations/${intervention.obligation_id}`}
          className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors inline-flex items-center gap-1"
        >
          <Layers className="w-3.5 h-3.5 text-zinc-400" />
          <span>View Linked Obligation</span>
        </Link>

        <div className="flex items-center gap-2">
          {intervention.status === "APPROVED" && onExecute && (
            <button
              onClick={() => onExecute(intervention)}
              className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-sm transition-all active:scale-95 flex items-center gap-1.5"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Execute Mock</span>
            </button>
          )}

          {onReview && intervention.status !== "RESOLVED" && intervention.status !== "CANCELLED" && (
            <button
              onClick={() => onReview(intervention)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all active:scale-95 flex items-center gap-1.5 ${
                intervention.status === "PENDING_REVIEW"
                  ? "bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold shadow-md shadow-amber-500/20"
                  : "bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>
                {intervention.status === "PENDING_REVIEW" ? "Review & Approve" : "Inspect / Edit"}
              </span>
            </button>
          )}

          <Link
            href={`/interventions/${intervention.id}`}
            className="p-1.5 rounded-lg border border-zinc-800 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
            title="Full Audit Details"
          >
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </div>
  );
}
