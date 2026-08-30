"use client";

import React, { useState } from "react";
import {
  X,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldCheck,
  RotateCcw,
  Sparkles,
  HelpCircle,
} from "lucide-react";
import {
  ReconciliationRecord,
  ReconciliationResolutionAction,
  ReconciliationResolutionRequest,
} from "../../lib/types/obligation";
import { reconciliationApi } from "../../lib/api/obligations";

interface ReconciliationReviewModalProps {
  reconciliation: ReconciliationRecord;
  isOpen: boolean;
  onClose: () => void;
  onResolved: (updated: ReconciliationRecord) => void;
}

export const ReconciliationReviewModal: React.FC<ReconciliationReviewModalProps> = ({
  reconciliation,
  isOpen,
  onClose,
  onResolved,
}) => {
  const [selectedAction, setSelectedAction] = useState<ReconciliationResolutionAction>(
    reconciliation.status === "CONSISTENT"
      ? "CONFIRM_COMPLETION"
      : "KEEP_OBLIGATION_ACTIVE"
  );
  const [operator, setOperator] = useState("Human Operator");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const isCompleted = reconciliation.obligation_status === "COMPLETED";

  const handleResolve = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const payload: ReconciliationResolutionRequest = {
        action: selectedAction,
        operator: operator.trim() || "Human Operator",
        notes: notes.trim() || undefined,
        selected_evidence_id:
          reconciliation.supporting_evidence_ids && reconciliation.supporting_evidence_ids.length > 0
            ? reconciliation.supporting_evidence_ids[0]
            : undefined,
      };
      const updated = await reconciliationApi.resolve(reconciliation.id, payload);
      onResolved(updated);
      onClose();
    } catch (err: unknown) {
      console.error("Failed to resolve reconciliation:", err);
      const msg = err instanceof Error ? err.message : "Failed to execute resolution action.";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDismiss = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const updated = await reconciliationApi.dismiss(reconciliation.id, {
        operator: operator.trim() || "Human Operator",
        reason: notes.trim() || "Dismissed as benign noise",
      });
      onResolved(updated);
      onClose();
    } catch (err: unknown) {
      console.error("Failed to dismiss reconciliation:", err);
      const msg = err instanceof Error ? err.message : "Failed to dismiss contradiction.";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeIn">
      <div className="relative w-full max-w-2xl bg-zinc-900 border border-zinc-700/80 rounded-2xl shadow-2xl overflow-hidden text-zinc-100 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-950/50">
          <div className="flex items-center gap-3">
            <div
              className={`p-2.5 rounded-xl ${
                reconciliation.status === "CONFLICTING"
                  ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                  : reconciliation.status === "CONSISTENT"
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
              }`}
            >
              {reconciliation.status === "CONFLICTING" ? (
                <AlertTriangle className="w-5 h-5" />
              ) : reconciliation.status === "CONSISTENT" ? (
                <CheckCircle2 className="w-5 h-5" />
              ) : (
                <HelpCircle className="w-5 h-5" />
              )}
            </div>
            <div>
              <h2 className="text-lg font-semibold text-zinc-100">
                Cross-Provider Reconciliation Review
              </h2>
              <p className="text-xs text-zinc-400">
                Authoritative Human Safety Gate • Obligation ID: {reconciliation.obligation_id.slice(0, 8)}...
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Content */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1 custom-scrollbar">
          {/* Obligation Summary Banner */}
          <div className="p-4 bg-zinc-950/60 rounded-xl border border-zinc-800/80">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-medium text-indigo-400 uppercase tracking-wider">
                Target Obligation
              </span>
              <span className="px-2 py-0.5 text-xs font-semibold rounded-md bg-zinc-800 text-zinc-300 border border-zinc-700">
                Status: {reconciliation.obligation_status || "ACTIVE"}
              </span>
            </div>
            <p className="text-sm font-semibold text-zinc-100 mb-2">
              {reconciliation.obligation_action || "Obligation Deliverable"}
            </p>
            <div className="flex flex-wrap items-center gap-4 text-xs text-zinc-400">
              <div>
                <span className="text-zinc-500">Owner:</span>{" "}
                <span className="text-zinc-200 font-medium">{reconciliation.obligation_owner || "Unassigned"}</span>
              </div>
              <div>
                <span className="text-zinc-500">Beneficiary:</span>{" "}
                <span className="text-zinc-200 font-medium">{reconciliation.obligation_beneficiary || "You"}</span>
              </div>
              <div>
                <span className="text-zinc-500">Consistency:</span>{" "}
                <span className="text-emerald-400 font-medium">{(reconciliation.consistency_score * 100).toFixed(0)}%</span>
              </div>
              <div>
                <span className="text-zinc-500">Contradiction:</span>{" "}
                <span className="text-rose-400 font-medium">{(reconciliation.contradiction_score * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>

          {/* AI Explanation & Finding Highlights */}
          <div className="p-4 bg-zinc-800/30 rounded-xl border border-zinc-800">
            <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              Intelligence Analysis & Timeline Findings
            </h3>
            <ul className="space-y-1.5">
              {reconciliation.explanation && reconciliation.explanation.length > 0 ? (
                reconciliation.explanation.map((exp, idx) => (
                  <li key={idx} className="text-xs text-zinc-300 flex items-start gap-2">
                    <span className="text-zinc-500 font-mono mt-0.5">•</span>
                    <span>{exp}</span>
                  </li>
                ))
              ) : (
                <li className="text-xs text-zinc-400">Multi-provider evidence evaluated. No unresolved conflicts.</li>
              )}
            </ul>
          </div>

          {/* Decision Selection Options */}
          <div className="space-y-3">
            <label className="block text-xs font-semibold text-zinc-300 uppercase tracking-wider">
              Select Authoritative Human Action
            </label>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {!isCompleted && (
                <>
                  <button
                    type="button"
                    onClick={() => setSelectedAction("CONFIRM_COMPLETION")}
                    className={`p-3 text-left rounded-xl border transition-all ${
                      selectedAction === "CONFIRM_COMPLETION"
                        ? "bg-emerald-500/15 border-emerald-500/50 text-emerald-300 ring-1 ring-emerald-500/30"
                        : "bg-zinc-800/40 border-zinc-700/50 hover:bg-zinc-800 hover:border-zinc-600 text-zinc-300"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-semibold text-xs mb-1">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      Confirm Completion
                    </div>
                    <p className="text-[11px] text-zinc-400">
                      Authoritatively mark complete & cascade-unblock downstream dependents.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedAction("KEEP_OBLIGATION_ACTIVE")}
                    className={`p-3 text-left rounded-xl border transition-all ${
                      selectedAction === "KEEP_OBLIGATION_ACTIVE"
                        ? "bg-amber-500/15 border-amber-500/50 text-amber-300 ring-1 ring-amber-500/30"
                        : "bg-zinc-800/40 border-zinc-700/50 hover:bg-zinc-800 hover:border-zinc-600 text-zinc-300"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-semibold text-xs mb-1">
                      <Clock className="w-4 h-4 text-amber-400" />
                      Keep Active
                    </div>
                    <p className="text-[11px] text-zinc-400">
                      Acknowledge conflicting signals; obligation remains active & in-progress.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedAction("MARK_AS_STALE")}
                    className={`p-3 text-left rounded-xl border transition-all ${
                      selectedAction === "MARK_AS_STALE"
                        ? "bg-blue-500/15 border-blue-500/50 text-blue-300 ring-1 ring-blue-500/30"
                        : "bg-zinc-800/40 border-zinc-700/50 hover:bg-zinc-800 hover:border-zinc-600 text-zinc-300"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-semibold text-xs mb-1">
                      <ShieldCheck className="w-4 h-4 text-blue-400" />
                      Mark Signal Stale
                    </div>
                    <p className="text-[11px] text-zinc-400">
                      Dismiss conflicting blocker as outdated / superseded by newer activity.
                    </p>
                  </button>
                </>
              )}

              {isCompleted && (
                <button
                  type="button"
                  onClick={() => setSelectedAction("REOPEN_OBLIGATION")}
                  className={`p-3 text-left rounded-xl border transition-all ${
                    selectedAction === "REOPEN_OBLIGATION"
                      ? "bg-rose-500/15 border-rose-500/50 text-rose-300 ring-1 ring-rose-500/30"
                      : "bg-zinc-800/40 border-zinc-700/50 hover:bg-zinc-800 hover:border-zinc-600 text-zinc-300"
                  }`}
                >
                  <div className="flex items-center gap-2 font-semibold text-xs mb-1">
                    <RotateCcw className="w-4 h-4 text-rose-400" />
                    Reopen Obligation
                  </div>
                  <p className="text-[11px] text-zinc-400">
                    Reopen completed obligation to IN_PROGRESS due to newer conflicting signals.
                  </p>
                </button>
              )}
            </div>
          </div>

          {/* Operator Name & Notes Input */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-zinc-400 mb-1 font-medium">Operator Identity</label>
              <input
                type="text"
                value={operator}
                onChange={(e) => setOperator(e.target.value)}
                className="w-full px-3 py-2 bg-zinc-950 border border-zinc-700 rounded-lg text-xs text-zinc-100 focus:outline-none focus:border-indigo-500"
                placeholder="Your Name / Operator Role"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1 font-medium">Decision Notes</label>
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full px-3 py-2 bg-zinc-950 border border-zinc-700 rounded-lg text-xs text-zinc-100 focus:outline-none focus:border-indigo-500"
                placeholder="Optional audit justification note..."
              />
            </div>
          </div>

          {error && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-zinc-800 bg-zinc-950/50">
          <button
            type="button"
            onClick={handleDismiss}
            disabled={isSubmitting}
            className="px-3.5 py-2 text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors"
          >
            Dismiss as Noise
          </button>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-medium text-zinc-300 hover:bg-zinc-800 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleResolve}
              disabled={isSubmitting}
              className="px-5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 rounded-lg shadow-lg shadow-indigo-600/20 transition-all flex items-center gap-1.5"
            >
              {isSubmitting ? "Executing..." : "Execute Decision"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
