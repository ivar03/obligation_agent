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
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
            <Flame className="w-3.5 h-3.5 text-rose-600 animate-pulse" />
            CRITICAL
          </span>
        );
      case "HIGH":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-orange-50 text-orange-700 border border-orange-200">
            <AlertTriangle className="w-3.5 h-3.5 text-orange-600" />
            HIGH
          </span>
        );
      case "MEDIUM":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
            MEDIUM
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-stone-100 text-stone-700 border border-stone-200">
            LOW
          </span>
        );
    }
  };

  const getStatusBadge = () => {
    switch (intervention.status) {
      case "PENDING_REVIEW":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
            <Clock className="w-3 h-3 text-amber-600" />
            Pending Review
          </span>
        );
      case "APPROVED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Approved
          </span>
        );
      case "SCHEDULED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-stone-100 text-stone-700 border border-stone-200">
            <Calendar className="w-3 h-3 text-stone-500" />
            Scheduled
          </span>
        );
      case "EXECUTED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-orange-50 text-orange-800 border border-orange-200">
            <Send className="w-3 h-3 text-orange-600" />
            Executed
          </span>
        );
      case "ACKNOWLEDGED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-stone-100 text-stone-700 border border-stone-200">
            <MessageSquareText className="w-3 h-3 text-stone-500" />
            Acknowledged
          </span>
        );
      case "RESOLVED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-stone-100 text-stone-700 border border-stone-200">
            <CheckCircle2 className="w-3 h-3 text-stone-500" />
            Resolved
          </span>
        );
      case "CANCELLED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-stone-100 text-stone-500 border border-stone-200">
            Cancelled
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-stone-100 text-stone-700 border border-stone-200">
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
          ? "bg-orange-50/20 border-orange-200 hover:border-orange-300 shadow-sm hover:shadow-md"
          : "bg-white border-stone-200 hover:border-stone-300 shadow-sm hover:shadow-md"
      }`}
    >
      {/* Header: Type, Urgency, Status */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 mb-3">
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-0.5 rounded-lg text-xs font-semibold uppercase tracking-wider bg-stone-100 text-stone-700 border border-stone-200">
            {formattedType}
          </span>
          {getUrgencyBadge()}
        </div>
        <div>{getStatusBadge()}</div>
      </div>

      {/* Title & Target */}
      <div className="space-y-1 mb-3">
        <h3 className="text-base font-bold text-stone-900 tracking-tight flex items-center justify-between gap-2">
          <span>{intervention.title}</span>
          <Link
            href={`/interventions/${intervention.id}`}
            className="text-stone-400 hover:text-orange-600 transition-colors"
            title="Inspect Audit Detail"
          >
            <ArrowUpRight className="w-4 h-4" />
          </Link>
        </h3>
        <div className="flex flex-wrap items-center gap-3 text-xs text-stone-600">
          <span className="inline-flex items-center gap-1 font-medium text-stone-700">
            <User className="w-3.5 h-3.5 text-stone-400" />
            Target: <strong className="text-stone-900 font-semibold">{intervention.target_owner}</strong>
          </span>
          {intervention.chain_depth > 1 && (
            <span className="inline-flex items-center gap-1 text-amber-800 font-medium bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200">
              ⚡ Follow-up #{intervention.chain_depth}
            </span>
          )}
        </div>
      </div>

      {/* Rationale Explanation */}
      <p className="text-xs text-stone-700 mb-3.5 bg-stone-50 p-2.5 rounded-xl border border-stone-200 leading-relaxed">
        <strong className="text-stone-600 font-medium">Why: </strong>
        {intervention.rationale}
      </p>

      {/* Suggested / Approved Message Draft Snippet */}
      <div className="mb-4 bg-stone-50 border border-stone-200 rounded-xl p-3">
        <div className="flex items-center justify-between text-[11px] font-semibold text-stone-500 uppercase tracking-wider mb-1.5">
          <span className="flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-orange-500" />
            {intervention.approved_message && intervention.status !== "PENDING_REVIEW"
              ? "Approved Message Draft"
              : "Suggested Message Draft"}
          </span>
          <span className="text-stone-500 lowercase font-normal">human approval required</span>
        </div>
        <p className="text-xs text-stone-800 italic line-clamp-3 leading-relaxed">
          &ldquo;{intervention.approved_message || intervention.message_draft}&rdquo;
        </p>
      </div>

      {/* Footer & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-stone-100">
        <Link
          href={`/obligations/${intervention.obligation_id}`}
          className="text-xs text-stone-500 hover:text-stone-800 transition-colors inline-flex items-center gap-1"
        >
          <Layers className="w-3.5 h-3.5 text-stone-400" />
          <span>View Linked Obligation</span>
        </Link>

        <div className="flex items-center gap-2">
          {intervention.status === "APPROVED" && onExecute && (
            <button
              onClick={() => onExecute(intervention)}
              className="px-3 py-1.5 rounded-lg bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold shadow-sm transition-all active:scale-95 flex items-center gap-1.5"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Execute Mock</span>
            </button>
          )}

          {onReview && intervention.status !== "RESOLVED" && intervention.status !== "CANCELLED" && (
            <button
              onClick={() => onReview(intervention)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all active:scale-95 flex items-center gap-1.5 ${
                intervention.status === "PENDING_REVIEW"
                  ? "bg-orange-600 hover:bg-orange-700 text-white font-semibold shadow-sm"
                  : "bg-white hover:bg-stone-50 border border-stone-200 text-stone-700"
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
            className="p-1.5 rounded-lg border border-stone-200 hover:bg-stone-100 text-stone-500 hover:text-stone-800 transition-colors"
            title="Full Audit Details"
          >
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </div>
  );
}
