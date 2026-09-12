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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-stone-900/40 backdrop-blur-sm animate-fadeIn">
      <div className="relative w-full max-w-2xl bg-white border border-stone-200 rounded-2xl shadow-xl overflow-hidden text-stone-900 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-stone-200 bg-stone-50/60">
          <div className="flex items-center gap-3">
            <div
              className={`p-2.5 rounded-xl border ${
                reconciliation.status === "CONFLICTING"
                  ? "bg-rose-50 text-rose-700 border-rose-200"
                  : reconciliation.status === "CONSISTENT"
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-amber-50 text-amber-700 border-amber-200"
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
              <h2 className="text-base font-bold text-stone-900">
                Cross-Provider Reconciliation Review
              </h2>
              <p className="text-xs text-stone-500">
                Authoritative Human Safety Gate • Obligation ID: {reconciliation.obligation_id.slice(0, 8)}...
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-stone-400 hover:text-stone-700 hover:bg-stone-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Content */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1 custom-scrollbar">
          {/* Obligation Summary Banner */}
          <div className="p-4 bg-stone-50 rounded-xl border border-stone-200">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-orange-600 uppercase tracking-wider">
                Target Obligation
              </span>
              <span className="px-2 py-0.5 text-xs font-semibold rounded-md bg-stone-200/80 text-stone-700 border border-stone-300">
                Status: {reconciliation.obligation_status || "ACTIVE"}
              </span>
            </div>
            <p className="text-sm font-semibold text-stone-900 mb-2">
              {reconciliation.obligation_action || "Obligation Deliverable"}
            </p>
            <div className="flex flex-wrap items-center gap-4 text-xs text-stone-600">
              <div>
                <span className="text-stone-500">Owner:</span>{" "}
                <span className="text-stone-800 font-medium">{reconciliation.obligation_owner || "Unassigned"}</span>
              </div>
              <div>
                <span className="text-stone-500">Beneficiary:</span>{" "}
                <span className="text-stone-800 font-medium">{reconciliation.obligation_beneficiary || "You"}</span>
              </div>
              <div>
                <span className="text-stone-500">Consistency:</span>{" "}
                <span className="text-emerald-700 font-medium">{(reconciliation.consistency_score * 100).toFixed(0)}%</span>
              </div>
              <div>
                <span className="text-stone-500">Contradiction:</span>{" "}
                <span className="text-rose-700 font-medium">{(reconciliation.contradiction_score * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>

          {/* AI Explanation & Finding Highlights */}
          <div className="p-4 bg-stone-50 rounded-xl border border-stone-200">
            <h3 className="text-xs font-semibold text-stone-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-orange-500" />
              Intelligence Analysis & Timeline Findings
            </h3>
            <ul className="space-y-1.5">
              {reconciliation.explanation && reconciliation.explanation.length > 0 ? (
                reconciliation.explanation.map((exp, idx) => (
                  <li key={idx} className="text-xs text-stone-700 flex items-start gap-2">
                    <span className="text-stone-400 font-mono mt-0.5">•</span>
                    <span>{exp}</span>
                  </li>
                ))
              ) : (
                <li className="text-xs text-stone-500">Multi-provider evidence evaluated. No unresolved conflicts.</li>
              )}
            </ul>
          </div>

          {/* Decision Selection Options */}
          <div className="space-y-3">
            <label className="block text-xs font-semibold text-stone-700 uppercase tracking-wider">
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
                        ? "bg-emerald-50 border-emerald-300 text-emerald-900 ring-1 ring-emerald-500/30"
                        : "bg-white border-stone-200 hover:border-stone-300 text-stone-700"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-semibold text-xs mb-1 text-emerald-700">
                      <CheckCircle2 className="w-4 h-4" />
                      Confirm Completion
                    </div>
                    <p className="text-[11px] text-stone-600">
                      Authoritatively mark complete & cascade-unblock downstream dependents.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedAction("KEEP_OBLIGATION_ACTIVE")}
                    className={`p-3 text-left rounded-xl border transition-all ${
                      selectedAction === "KEEP_OBLIGATION_ACTIVE"
                        ? "bg-amber-50 border-amber-300 text-amber-900 ring-1 ring-amber-500/30"
                        : "bg-white border-stone-200 hover:border-stone-300 text-stone-700"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-semibold text-xs mb-1 text-amber-700">
                      <Clock className="w-4 h-4" />
                      Keep Active
                    </div>
                    <p className="text-[11px] text-stone-600">
                      Acknowledge conflicting signals; obligation remains active & in-progress.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedAction("MARK_AS_STALE")}
                    className={`p-3 text-left rounded-xl border transition-all ${
                      selectedAction === "MARK_AS_STALE"
                        ? "bg-orange-50 border-orange-300 text-orange-900 ring-1 ring-orange-500/30"
                        : "bg-white border-stone-200 hover:border-stone-300 text-stone-700"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-semibold text-xs mb-1 text-orange-700">
                      <ShieldCheck className="w-4 h-4" />
                      Mark Signal Stale
                    </div>
                    <p className="text-[11px] text-stone-600">
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
                      ? "bg-rose-50 border-rose-300 text-rose-900 ring-1 ring-rose-500/30"
                      : "bg-white border-stone-200 hover:border-stone-300 text-stone-700"
                  }`}
                >
                  <div className="flex items-center gap-2 font-semibold text-xs mb-1 text-rose-700">
                    <RotateCcw className="w-4 h-4" />
                    Reopen Obligation
                  </div>
                  <p className="text-[11px] text-stone-600">
                    Reopen completed obligation to IN_PROGRESS due to newer conflicting signals.
                  </p>
                </button>
              )}
            </div>
          </div>

          {/* Operator Name & Notes Input */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-stone-600 mb-1 font-medium">Operator Identity</label>
              <input
                type="text"
                value={operator}
                onChange={(e) => setOperator(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-stone-200 rounded-lg text-xs text-stone-900 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/20"
                placeholder="Your Name / Operator Role"
              />
            </div>
            <div>
              <label className="block text-xs text-stone-600 mb-1 font-medium">Decision Notes</label>
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-stone-200 rounded-lg text-xs text-stone-900 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/20"
                placeholder="Optional audit justification note..."
              />
            </div>
          </div>

          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-stone-200 bg-stone-50/60">
          <button
            type="button"
            onClick={handleDismiss}
            disabled={isSubmitting}
            className="px-3.5 py-2 text-xs font-medium text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-lg transition-colors"
          >
            Dismiss as Noise
          </button>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-medium text-stone-700 hover:bg-stone-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleResolve}
              disabled={isSubmitting}
              className="px-5 py-2 text-xs font-semibold text-white bg-orange-600 hover:bg-orange-700 active:bg-orange-800 disabled:opacity-50 rounded-lg shadow-sm transition-all flex items-center gap-1.5"
            >
              {isSubmitting ? "Executing..." : "Execute Decision"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
