"use client";

import React, { useEffect, useState, useCallback, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Send,
  CheckCircle2,
  Layers,
  Sparkles,
  ShieldCheck,
  History,
  MessageSquareText,
  Check,
} from "lucide-react";
import { Intervention, InterventionOutcome } from "@/lib/types/obligation";
import { interventionsApi } from "@/lib/api/obligations";
import { useToast } from "@/components/ui/ToastContext";
import { InterventionReviewModal } from "@/components/interventions/InterventionReviewModal";

export default function InterventionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const interventionId = resolvedParams.id;

  const router = useRouter();
  const { toast } = useToast();

  const [intervention, setIntervention] = useState<Intervention | null>(null);
  const [loading, setLoading] = useState(true);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [recordingOutcome, setRecordingOutcome] = useState(false);
  const [selectedOutcome, setSelectedOutcome] = useState<InterventionOutcome>("ACKNOWLEDGED");
  const [outcomeNotes, setOutcomeNotes] = useState("");

  const loadIntervention = useCallback(async () => {
    try {
      const data = await interventionsApi.getById(interventionId);
      setIntervention(data);
    } catch (err) {
      toast({
        type: "error",
        title: "Failed to Load Intervention",
        description: err instanceof Error ? err.message : "Intervention not found.",
      });
    } finally {
      setLoading(false);
    }
  }, [interventionId, toast]);

  useEffect(() => {
    loadIntervention();
  }, [loadIntervention]);

  const handleRecordOutcome = async () => {
    if (!intervention) return;
    try {
      setRecordingOutcome(true);
      const updated = await interventionsApi.recordOutcome(intervention.id, {
        outcome: selectedOutcome,
        notes: outcomeNotes.trim() ? outcomeNotes.trim() : undefined,
      });
      toast({
        type: "success",
        title: "Outcome Recorded",
        description: `Marked intervention outcome as ${selectedOutcome}.`,
      });
      setIntervention(updated);
      setOutcomeNotes("");
    } catch (err) {
      toast({
        type: "error",
        title: "Outcome Failed",
        description: err instanceof Error ? err.message : "Failed to record outcome.",
      });
    } finally {
      setRecordingOutcome(false);
    }
  };

  const handleExecuteMock = async () => {
    if (!intervention) return;
    try {
      const updated = await interventionsApi.execute(intervention.id);
      toast({
        type: "success",
        title: "Executed in Simulation Mode",
        description: `Follow-up simulated (Ref: ${updated.execution_reference}). No external messages sent.`,
      });
      setIntervention(updated);
    } catch (err) {
      toast({
        type: "error",
        title: "Execution Failed",
        description: err instanceof Error ? err.message : "Failed to execute.",
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-stone-600">Loading intervention audit records...</p>
        </div>
      </div>
    );
  }

  if (!intervention) {
    return (
      <div className="text-center py-16 space-y-4">
        <h2 className="text-xl font-bold text-stone-950">Intervention Not Found</h2>
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-stone-200 hover:bg-stone-300 text-stone-950 text-sm font-semibold transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-12">
      {/* Top Breadcrumb & Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="p-2 rounded-xl border border-stone-200 bg-stone-100 hover:bg-stone-200 text-stone-700 transition-colors"
            title="Go Back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-lg text-xs font-bold uppercase tracking-wider bg-stone-200 text-stone-700 border border-stone-300">
                {intervention.intervention_type.replace(/_/g, " ")}
              </span>
              <span className="text-xs text-stone-600">ID: {intervention.id.slice(0, 8)}...</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-stone-950 tracking-tight mt-1">
              {intervention.title}
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {intervention.status === "APPROVED" && (
            <button
              onClick={handleExecuteMock}
              className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-stone-950 text-xs font-bold transition-all shadow-md shadow-blue-600/20 active:scale-95 flex items-center gap-1.5"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Execute Mock</span>
            </button>
          )}

          {intervention.status !== "RESOLVED" && intervention.status !== "CANCELLED" && (
            <button
              onClick={() => setShowReviewModal(true)}
              className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-stone-50 text-xs font-bold transition-all shadow-md shadow-amber-500/20 active:scale-95 flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Edit / Approve</span>
            </button>
          )}
        </div>
      </div>

      {/* Overview Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Rationale, Messages, Outcomes */}
        <div className="lg:col-span-2 space-y-6">
          {/* Rationale & Grounding Card */}
          <div className="bg-stone-100/80 border border-stone-200 rounded-2xl p-5 space-y-3 shadow-md">
            <h2 className="text-xs font-bold uppercase tracking-wider text-stone-600 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-blue-500" />
              <span>Intervention Rationale & Grounding</span>
            </h2>
            <p className="text-sm text-stone-800 leading-relaxed">{intervention.rationale}</p>
            <div className="pt-2 flex flex-wrap items-center gap-4 text-xs text-stone-600 border-t border-stone-200/80">
              <span>
                Target Owner: <strong className="text-stone-950">{intervention.target_owner}</strong>
              </span>
              <span>
                Beneficiary: <strong className="text-stone-950">{intervention.target_beneficiary}</strong>
              </span>
              <span>
                Urgency: <strong className="text-amber-400">{intervention.urgency}</strong>
              </span>
            </div>
          </div>

          {/* Message Comparison Card: Draft vs Approved */}
          <div className="bg-stone-100/80 border border-stone-200 rounded-2xl p-5 space-y-4 shadow-md">
            <h2 className="text-xs font-bold uppercase tracking-wider text-stone-600 flex items-center gap-2">
              <MessageSquareText className="w-4 h-4 text-amber-400" />
              <span>Message Draft & Human Versioning</span>
            </h2>

            <div className="space-y-3">
              <div className="bg-stone-50 border border-stone-200/80 rounded-xl p-4 space-y-1.5">
                <div className="flex items-center justify-between text-[11px] font-semibold text-stone-600 uppercase tracking-wider">
                  <span>Generated AI Draft (Ground Truth)</span>
                  <span>Deterministic</span>
                </div>
                <p className="text-sm text-stone-700 italic leading-relaxed">
                  &ldquo;{intervention.message_draft}&rdquo;
                </p>
              </div>

              {intervention.approved_message && intervention.approved_message !== intervention.message_draft && (
                <div className="bg-stone-50 border border-emerald-500/30 rounded-xl p-4 space-y-1.5">
                  <div className="flex items-center justify-between text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">
                    <span>Approved Final Message</span>
                    <span>Approved by {intervention.approved_by || "USER"}</span>
                  </div>
                  <p className="text-sm text-stone-950 font-medium italic leading-relaxed">
                    &ldquo;{intervention.approved_message}&rdquo;
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Outcome Recording Panel (If Executed or Awaiting Resolution) */}
          <div className="bg-stone-100/80 border border-stone-200 rounded-2xl p-5 space-y-4 shadow-md">
            <h2 className="text-xs font-bold uppercase tracking-wider text-stone-600 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Record Observed Outcome</span>
            </h2>
            <p className="text-xs text-stone-600">
              Record factual feedback or response received from {intervention.target_owner}:
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-stone-600 block mb-1">Outcome Status</label>
                <select
                  value={selectedOutcome}
                  onChange={(e) => setSelectedOutcome(e.target.value as InterventionOutcome)}
                  className="w-full bg-stone-50 border border-stone-300 rounded-xl px-3 py-2 text-xs text-stone-800 focus:outline-none focus:border-blue-500"
                >
                  <option value="ACKNOWLEDGED">Acknowledged (Owner responded/working on it)</option>
                  <option value="PROGRESS_REPORTED">Progress Reported (Active updates shared)</option>
                  <option value="COMPLETED">Completed (Deliverable fulfilled)</option>
                  <option value="NO_RESPONSE">No Response (Timeout reached)</option>
                  <option value="NEGATIVE_RESPONSE">Negative Response (Blocker/delay reported)</option>
                  <option value="NOT_NEEDED">Not Needed (No longer required)</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-stone-600 block mb-1">Notes / Context (Optional)</label>
                <input
                  type="text"
                  value={outcomeNotes}
                  onChange={(e) => setOutcomeNotes(e.target.value)}
                  placeholder="e.g. Rahul promised numbers by 3 PM"
                  className="w-full bg-stone-50 border border-stone-300 rounded-xl px-3 py-2 text-xs text-stone-800 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={handleRecordOutcome}
                disabled={recordingOutcome}
                className="px-4 py-2 rounded-xl bg-stone-200 hover:bg-stone-300 text-stone-950 text-xs font-semibold transition-colors disabled:opacity-50 flex items-center gap-1.5"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Record Outcome</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right 1 Col: State, Linked Obligation, Immutable Audit Trail */}
        <div className="space-y-6">
          {/* Status & Execution Info */}
          <div className="bg-stone-100/80 border border-stone-200 rounded-2xl p-5 space-y-3.5 shadow-md">
            <h2 className="text-xs font-bold uppercase tracking-wider text-stone-600">Execution State</h2>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-stone-200/80">
                <span className="text-stone-600">Status:</span>
                <span className="font-semibold text-stone-950">{intervention.status}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-stone-200/80">
                <span className="text-stone-600">Execution Mode:</span>
                <span className="font-mono text-stone-700">{intervention.execution_mode}</span>
              </div>
              {intervention.execution_reference && (
                <div className="flex justify-between py-1 border-b border-stone-200/80">
                  <span className="text-stone-600">Reference:</span>
                  <span className="font-mono text-blue-500">{intervention.execution_reference}</span>
                </div>
              )}
              {intervention.approved_at && (
                <div className="flex justify-between py-1 border-b border-stone-200/80">
                  <span className="text-stone-600">Approved:</span>
                  <span className="text-stone-700">{new Date(intervention.approved_at).toLocaleString()}</span>
                </div>
              )}
              {intervention.executed_at && (
                <div className="flex justify-between py-1 border-b border-stone-200/80">
                  <span className="text-stone-600">Executed:</span>
                  <span className="text-stone-700">{new Date(intervention.executed_at).toLocaleString()}</span>
                </div>
              )}
              {intervention.scheduled_for && (
                <div className="flex justify-between py-1 border-b border-stone-200/80">
                  <span className="text-stone-600">Scheduled For:</span>
                  <span className="text-purple-400 font-medium">
                    {new Date(intervention.scheduled_for).toLocaleString()}
                  </span>
                </div>
              )}
              {intervention.outcome && (
                <div className="flex justify-between py-1 border-b border-stone-200/80">
                  <span className="text-stone-600">Outcome:</span>
                  <span className="text-emerald-400 font-semibold">{intervention.outcome}</span>
                </div>
              )}
            </div>

            <div className="pt-2">
              <Link
                href={`/obligations/${intervention.obligation_id}`}
                className="w-full px-3 py-2 rounded-xl bg-stone-50 hover:bg-stone-200 border border-stone-200 text-xs font-semibold text-stone-800 transition-colors flex items-center justify-center gap-1.5"
              >
                <Layers className="w-3.5 h-3.5 text-blue-500" />
                <span>Go to Linked Obligation</span>
              </Link>
            </div>
          </div>

          {/* Immutable Audit Trail Timeline */}
          <div className="bg-stone-100/80 border border-stone-200 rounded-2xl p-5 space-y-4 shadow-md">
            <h2 className="text-xs font-bold uppercase tracking-wider text-stone-600 flex items-center gap-2">
              <History className="w-4 h-4 text-purple-400" />
              <span>Immutable Audit Trail</span>
            </h2>

            <div className="relative pl-4 space-y-4 border-l border-stone-200">
              {(intervention.audit_trail || []).map((entry, idx) => (
                <div key={idx} className="relative space-y-1">
                  <div className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-blue-500 ring-4 ring-stone-100" />
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-stone-800 uppercase tracking-wider">
                      {entry.event}
                    </span>
                    <span className="text-[10px] text-stone-600">
                      {new Date(entry.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-[11px] text-stone-600">
                    Actor: <strong className="text-stone-700">{entry.actor}</strong>
                  </p>
                  {entry.details && Object.keys(entry.details).length > 0 && (
                    <pre className="text-[10px] text-stone-600 bg-stone-50 p-2 rounded-lg border border-stone-200/80 overflow-x-auto">
                      {JSON.stringify(entry.details, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Review & Edit Modal */}
      <InterventionReviewModal
        intervention={intervention}
        isOpen={showReviewModal}
        onClose={() => setShowReviewModal(false)}
        onUpdated={(updated) => setIntervention(updated)}
      />
    </div>
  );
}
