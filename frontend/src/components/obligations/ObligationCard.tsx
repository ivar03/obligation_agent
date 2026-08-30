"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Clock,
  ArrowRight,
  AlertCircle,
  FileCheck,
  ShieldAlert,
  ExternalLink,
  Trash2,
  Check,
  Ban,
} from "lucide-react";
import { Obligation, ObligationStatus } from "@/lib/types/obligation";
import { StatusBadge } from "../ui/StatusBadge";
import { ConfidenceBadge } from "../ui/ConfidenceBadge";
import { useToast } from "../ui/ToastContext";
import { obligationsApi } from "@/lib/api/obligations";

interface ObligationCardProps {
  obligation: Obligation;
  onStatusChanged?: (updated: Obligation) => void;
  onDeleted?: (id: string) => void;
}

export const ObligationCard: React.FC<ObligationCardProps> = ({
  obligation,
  onStatusChanged,
  onDeleted,
}) => {
  const { toast } = useToast();
  const [updating, setUpdating] = useState(false);

  const isOwedByMe = obligation.obligation_type === "OWED_BY_ME";
  const isBlocked = obligation.status === "BLOCKED";

  // Relationship description
  const relationshipText = isOwedByMe ? (
    <span>
      You owe <span className="font-semibold text-blue-300">{obligation.beneficiary}</span>
    </span>
  ) : (
    <span>
      <span className="font-semibold text-emerald-300">{obligation.owner}</span> owes You
    </span>
  );

  // Deadline formatting
  let deadlineDisplay = "No deadline";
  let isOverdue = false;
  if (obligation.deadline) {
    const d = new Date(obligation.deadline);
    const now = new Date();
    isOverdue = d < now && obligation.status !== "COMPLETED" && obligation.status !== "CANCELLED";
    deadlineDisplay = d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  // Blocker description snippet
  let blockerSummary = "";
  if (isBlocked && obligation.block_reason && typeof obligation.block_reason === "object") {
    const br = obligation.block_reason as { blocked_by?: Array<{ owner: string; action: string }> };
    if (br.blocked_by && br.blocked_by.length > 0) {
      blockerSummary = `Blocked by ${br.blocked_by[0].owner}'s prerequisite`;
    }
  }

  const handleStatusTransition = async (newStatus: ObligationStatus) => {
    try {
      setUpdating(true);
      const updated = await obligationsApi.updateStatus(obligation.id, newStatus);
      toast({
        type: "success",
        title: `Status Updated`,
        description: `Obligation marked as ${newStatus}`,
      });
      if (onStatusChanged) onStatusChanged(updated);
    } catch (err) {
      toast({
        type: "error",
        title: "Status Update Failed",
        description: err instanceof Error ? err.message : "Transition not allowed.",
      });
    } finally {
      setUpdating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this obligation?")) return;
    try {
      setUpdating(true);
      await obligationsApi.delete(obligation.id);
      toast({
        type: "success",
        title: "Obligation Deleted",
      });
      if (onDeleted) onDeleted(obligation.id);
    } catch (err) {
      toast({
        type: "error",
        title: "Delete Failed",
        description: err instanceof Error ? err.message : "Could not delete.",
      });
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div
      className={`relative group bg-zinc-900/70 hover:bg-zinc-900 border rounded-xl p-5 transition-all duration-200 shadow-sm hover:shadow-md ${
        isBlocked
          ? "border-rose-500/50 hover:border-rose-500/70 bg-rose-950/20"
          : obligation.is_at_risk
          ? "border-rose-500/40 hover:border-rose-500/60 bg-rose-950/10"
          : "border-zinc-800 hover:border-zinc-700"
      }`}
    >
      {/* Top row: Relationship & Status badges */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 text-xs font-medium text-zinc-400">
          <span
            className={`w-2 h-2 rounded-full ${
              isOwedByMe ? "bg-blue-400" : "bg-emerald-400"
            }`}
          />
          {relationshipText}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {isBlocked ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse">
              <Ban className="w-3 h-3" />
              Blocked
            </span>
          ) : obligation.is_at_risk ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 animate-pulse">
              <ShieldAlert className="w-3 h-3" />
              At Risk
            </span>
          ) : null}
          <StatusBadge status={obligation.status} size="sm" />
        </div>
      </div>

      {/* Main Action / Duty */}
      <div className="mb-3">
        <Link
          href={`/obligations/${obligation.id}`}
          className="text-base font-semibold text-zinc-100 hover:text-blue-400 transition-colors line-clamp-2 inline-flex items-baseline gap-1"
        >
          <span>{obligation.action}</span>
          <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
        </Link>
      </div>

      {/* Blocker Callout if Blocked */}
      {isBlocked && blockerSummary && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-rose-950/40 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2">
          <Ban className="w-3.5 h-3.5 shrink-0 text-rose-400" />
          <span className="font-medium truncate">{blockerSummary}</span>
        </div>
      )}

      {/* Next Action Callout if available */}
      {obligation.next_action && !isBlocked && (
        <div className="mb-3.5 px-3 py-2 rounded-lg bg-zinc-950/70 border border-zinc-800/80 text-xs">
          <span className="text-zinc-400 font-medium">Next Step: </span>
          <span className="text-zinc-200">{obligation.next_action}</span>
        </div>
      )}

      {/* Conditions pill if present */}
      {obligation.conditions && (
        <div className="mb-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs">
          <AlertCircle className="w-3 h-3 shrink-0" />
          <span className="font-medium">Condition:</span>
          <span className="truncate max-w-xs">{String(obligation.conditions)}</span>
        </div>
      )}

      {/* Metadata footer */}
      <div className="pt-3 border-t border-zinc-800/60 flex flex-wrap items-center justify-between gap-3 text-xs text-zinc-400">
        <div className="flex items-center gap-3">
          {/* Deadline */}
          <div
            className={`flex items-center gap-1.5 ${
              isOverdue ? "text-rose-400 font-semibold" : "text-zinc-400"
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>{deadlineDisplay}</span>
          </div>

          {/* Evidence count */}
          {obligation.evidence && obligation.evidence.length > 0 && (
            <div className="flex items-center gap-1 text-emerald-400 font-medium" title="Evidence attached">
              <FileCheck className="w-3.5 h-3.5" />
              <span>{obligation.evidence.length} evidence</span>
            </div>
          )}

          {/* Confidence Indicator */}
          {obligation.confidence && (
            <ConfidenceBadge confidence={obligation.confidence} showIcon={false} />
          )}
        </div>

        {/* Quick action buttons */}
        <div className="flex items-center gap-1 opacity-90 group-hover:opacity-100 transition-opacity">
          {obligation.status === "CONFIRMED" && (
            <button
              onClick={() => handleStatusTransition("IN_PROGRESS")}
              disabled={updating}
              className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium transition-colors"
            >
              Start
            </button>
          )}

          {obligation.status === "IN_PROGRESS" && (
            <button
              onClick={() => handleStatusTransition("COMPLETED")}
              disabled={updating}
              className="px-2.5 py-1 rounded bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-medium transition-colors inline-flex items-center gap-1"
            >
              <Check className="w-3 h-3" />
              Complete
            </button>
          )}

          <Link
            href={`/obligations/${obligation.id}`}
            className="p-1 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors"
            title="View Details"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>

          <button
            onClick={handleDelete}
            disabled={updating}
            className="p-1 rounded text-zinc-400 hover:text-rose-400 hover:bg-rose-950/20 transition-colors"
            title="Delete Obligation"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
