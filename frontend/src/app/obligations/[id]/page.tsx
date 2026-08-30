"use client";

import React, { useEffect, useState, useCallback, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Clock,
  User,
  ShieldAlert,
  AlertCircle,
  CheckCircle2,
  PlayCircle,
  FileCheck,
  Edit,
  Trash2,
  ExternalLink,
  Plus,
  X,
} from "lucide-react";
import { Obligation, ObligationStatus, ObligationType } from "@/lib/types/obligation";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ConfidenceBadge } from "@/components/ui/ConfidenceBadge";
import { obligationsApi } from "@/lib/api/obligations";
import { useToast } from "@/components/ui/ToastContext";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function ObligationDetailPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const obligationId = resolvedParams.id;

  const router = useRouter();
  const { toast } = useToast();

  const [obligation, setObligation] = useState<Obligation | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  // Edit Mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editAction, setEditAction] = useState("");
  const [editOwner, setEditOwner] = useState("");
  const [editBeneficiary, setEditBeneficiary] = useState("");
  const [editDeadline, setEditDeadline] = useState("");
  const [editConditions, setEditConditions] = useState("");
  const [editNextAction, setEditNextAction] = useState("");
  const [editType, setEditType] = useState<ObligationType>("OWED_BY_ME");

  // Evidence attachment modal state
  const [showEvidenceModal, setShowEvidenceModal] = useState(false);
  const [evidenceNote, setEvidenceNote] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");

  const loadObligation = useCallback(async () => {
    try {
      const data = await obligationsApi.getById(obligationId);
      setObligation(data);
      // Sync edit form
      setEditAction(data.action);
      setEditOwner(data.owner);
      setEditBeneficiary(data.beneficiary);
      setEditDeadline(data.deadline ? new Date(data.deadline).toISOString().slice(0, 16) : "");
      setEditConditions(data.conditions ? String(data.conditions) : "");
      setEditNextAction(data.next_action || "");
      setEditType(data.obligation_type);
    } catch (err) {
      toast({
        type: "error",
        title: "Not Found",
        description: err instanceof Error ? err.message : "Could not load obligation.",
      });
    } finally {
      setLoading(false);
    }
  }, [obligationId, toast]);

  useEffect(() => {
    loadObligation();
  }, [loadObligation]);

  const handleStatusChange = async (newStatus: ObligationStatus, evidencePayload?: Record<string, unknown>) => {
    try {
      setUpdating(true);
      const updated = await obligationsApi.updateStatus(
        obligationId,
        newStatus,
        undefined,
        evidencePayload
      );
      setObligation(updated);
      toast({
        type: "success",
        title: "Status Transitioned",
        description: `Obligation is now ${newStatus}.`,
      });
      setShowEvidenceModal(false);
      setEvidenceNote("");
      setEvidenceUrl("");
    } catch (err) {
      toast({
        type: "error",
        title: "Transition Rejected",
        description: err instanceof Error ? err.message : "State transition not allowed.",
      });
    } finally {
      setUpdating(false);
    }
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setUpdating(true);
      const updated = await obligationsApi.update(obligationId, {
        action: editAction.trim(),
        owner: editOwner.trim(),
        beneficiary: editBeneficiary.trim(),
        deadline: editDeadline ? new Date(editDeadline).toISOString() : null,
        conditions: editConditions.trim() ? editConditions.trim() : null,
        next_action: editNextAction.trim() ? editNextAction.trim() : null,
        obligation_type: editType,
      });
      setObligation(updated);
      setIsEditing(false);
      toast({
        type: "success",
        title: "Obligation Updated",
      });
    } catch (err) {
      toast({
        type: "error",
        title: "Update Failed",
        description: err instanceof Error ? err.message : "Could not save edits.",
      });
    } finally {
      setUpdating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to permanently delete this obligation?")) return;
    try {
      setUpdating(true);
      await obligationsApi.delete(obligationId);
      toast({
        type: "success",
        title: "Obligation Deleted",
      });
      router.push("/");
    } catch (err) {
      toast({
        type: "error",
        title: "Delete Failed",
        description: err instanceof Error ? err.message : "Could not delete.",
      });
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="h-6 w-32 bg-zinc-900 rounded animate-pulse" />
        <div className="h-80 bg-zinc-900/60 rounded-2xl animate-pulse" />
      </div>
    );
  }

  if (!obligation) {
    return (
      <div className="max-w-xl mx-auto text-center py-16 space-y-4">
        <AlertCircle className="w-12 h-12 text-rose-400 mx-auto" />
        <h2 className="text-lg font-bold text-white">Obligation Not Found</h2>
        <p className="text-sm text-zinc-400">The requested obligation record does not exist or was deleted.</p>
        <Link href="/" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 text-white text-xs">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>
      </div>
    );
  }

  const isOwedByMe = obligation.obligation_type === "OWED_BY_ME";

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Navigation Breadcrumb */}
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-xs font-semibold text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsEditing(!isEditing)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900/80 hover:bg-zinc-800 text-zinc-200 text-xs font-medium transition-colors"
          >
            <Edit className="w-3.5 h-3.5" />
            <span>{isEditing ? "Cancel Edit" : "Edit Details"}</span>
          </button>

          <button
            onClick={handleDelete}
            disabled={updating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-rose-500/30 bg-rose-950/20 hover:bg-rose-950/40 text-rose-300 text-xs font-medium transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Delete</span>
          </button>
        </div>
      </div>

      {/* Main Content Card */}
      {isEditing ? (
        /* Edit Form */
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-5">
          <h2 className="text-lg font-bold text-white pb-3 border-b border-zinc-800">
            Edit Obligation
          </h2>
          <form onSubmit={handleSaveEdit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setEditType("OWED_BY_ME")}
                className={`p-3 rounded-xl border text-left text-xs font-medium ${
                  editType === "OWED_BY_ME"
                    ? "bg-blue-600/20 border-blue-500 text-white"
                    : "bg-zinc-950 border-zinc-800 text-zinc-400"
                }`}
              >
                You Owe (Outgoing)
              </button>
              <button
                type="button"
                onClick={() => setEditType("OWED_TO_ME")}
                className={`p-3 rounded-xl border text-left text-xs font-medium ${
                  editType === "OWED_TO_ME"
                    ? "bg-emerald-600/20 border-emerald-500 text-white"
                    : "bg-zinc-950 border-zinc-800 text-zinc-400"
                }`}
              >
                Others Owe You (Incoming)
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Owner</label>
                <input
                  type="text"
                  value={editOwner}
                  onChange={(e) => setEditOwner(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Beneficiary</label>
                <input
                  type="text"
                  value={editBeneficiary}
                  onChange={(e) => setEditBeneficiary(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1">Action</label>
              <textarea
                rows={2}
                value={editAction}
                onChange={(e) => setEditAction(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100"
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Deadline</label>
                <input
                  type="datetime-local"
                  value={editDeadline}
                  onChange={(e) => setEditDeadline(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Conditions</label>
                <input
                  type="text"
                  value={editConditions}
                  onChange={(e) => setEditConditions(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1">Next Action</label>
              <input
                type="text"
                value={editNextAction}
                onChange={(e) => setEditNextAction(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-800">
              <button
                type="button"
                onClick={() => setIsEditing(false)}
                className="px-4 py-2 rounded-lg text-xs text-zinc-400 hover:text-zinc-200"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={updating}
                className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold"
              >
                Save Changes
              </button>
            </div>
          </form>
        </div>
      ) : (
        /* Detailed View */
        <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-6 sm:p-8 shadow-xl space-y-8">
          {/* Header row */}
          <div className="flex flex-wrap items-start justify-between gap-4 pb-6 border-b border-zinc-800">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-zinc-400">
                <span className={`w-2.5 h-2.5 rounded-full ${isOwedByMe ? "bg-blue-400" : "bg-emerald-400"}`} />
                <span>
                  {isOwedByMe ? "Outgoing Commitment (You Owe)" : "Incoming Commitment (Others Owe You)"}
                </span>
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-white leading-snug">
                {obligation.action}
              </h1>
            </div>

            <div className="flex items-center gap-3">
              {obligation.is_at_risk && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 animate-pulse">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  At Risk
                </span>
              )}
              <StatusBadge status={obligation.status} />
            </div>
          </div>

          {/* Reciprocal Parties Visualization */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                Duty Bearer (Owner)
              </span>
              <div className="text-base font-bold text-zinc-100 flex items-center gap-2">
                <User className="w-4 h-4 text-blue-400" />
                <span>{obligation.owner}</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                Obligee (Beneficiary)
              </span>
              <div className="text-base font-bold text-zinc-100 flex items-center gap-2">
                <User className="w-4 h-4 text-emerald-400" />
                <span>{obligation.beneficiary}</span>
              </div>
            </div>
          </div>

          {/* Temporal & Conditions Block */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                Deadline
              </span>
              <div className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-400" />
                <span>
                  {obligation.deadline
                    ? new Date(obligation.deadline).toLocaleString(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })
                    : "No deadline specified"}
                </span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                Conditions / Triggers
              </span>
              <div className="text-sm text-zinc-300">
                {obligation.conditions ? (
                  <span className="text-amber-300 font-medium">{String(obligation.conditions)}</span>
                ) : (
                  <span className="text-zinc-400 italic">None (Unconditional)</span>
                )}
              </div>
            </div>
          </div>

          {/* Next Action Callout */}
          {obligation.next_action && (
            <div className="p-4 rounded-xl bg-blue-950/30 border border-blue-500/30 space-y-1">
              <span className="text-[11px] font-semibold text-blue-400 uppercase tracking-wider">
                Immediate Next Step
              </span>
              <div className="text-sm text-zinc-200 font-medium">{obligation.next_action}</div>
            </div>
          )}

          {/* Provenance & Confidence */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                Source Reference
              </span>
              <div className="text-xs text-zinc-300">{obligation.source_ref || "Manual Input"}</div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                AI Confidence Breakdown
              </span>
              <div>
                <ConfidenceBadge confidence={obligation.confidence} />
              </div>
            </div>
          </div>

          {/* Evidence Ledger Section */}
          <div className="space-y-3 pt-4 border-t border-zinc-800">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <FileCheck className="w-4 h-4 text-emerald-400" />
                <span>Verification Evidence ({obligation.evidence?.length || 0})</span>
              </h3>
              {obligation.status !== "COMPLETED" && (
                <button
                  onClick={() => setShowEvidenceModal(true)}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium"
                >
                  <Plus className="w-3 h-3" />
                  <span>Attach Evidence</span>
                </button>
              )}
            </div>

            {!obligation.evidence || obligation.evidence.length === 0 ? (
              <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800/60 text-xs text-zinc-400 italic">
                No verification evidence recorded yet. When transitioning status, evidence notes or audit links can be attached.
              </div>
            ) : (
              <div className="space-y-2">
                {obligation.evidence.map((ev, i) => (
                  <div key={i} className="p-3 rounded-xl bg-zinc-950 border border-zinc-800 text-xs space-y-1">
                    <div className="flex items-center justify-between text-[11px] text-zinc-400">
                      <span className="font-semibold text-zinc-300">
                        {ev.type ? String(ev.type).toUpperCase() : "EVIDENCE"}
                      </span>
                      <span>{ev.recorded_at ? new Date(String(ev.recorded_at)).toLocaleString() : ""}</span>
                    </div>
                    {ev.text && <div className="text-zinc-200">{String(ev.text)}</div>}
                    {ev.url && (
                      <a
                        href={String(ev.url)}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-400 hover:underline inline-flex items-center gap-1"
                      >
                        <span>{String(ev.url)}</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Controlled Status Transition Action Bar */}
          <div className="pt-6 border-t border-zinc-800 space-y-3">
            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
              Controlled State Machine Actions
            </span>

            <div className="flex flex-wrap items-center gap-2.5">
              {/* If CONFIRMED */}
              {obligation.status === "CONFIRMED" && (
                <>
                  <button
                    onClick={() => handleStatusChange("IN_PROGRESS")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow-md shadow-amber-600/20 active:scale-95 transition-all"
                  >
                    <PlayCircle className="w-4 h-4" />
                    <span>Start Work (In Progress)</span>
                  </button>
                  <button
                    onClick={() => setShowEvidenceModal(true)}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/20 active:scale-95 transition-all"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Complete & Attach Evidence</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("BLOCKED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors"
                  >
                    <span>Mark Blocked</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("CANCELLED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs font-medium transition-colors"
                  >
                    <span>Cancel Obligation</span>
                  </button>
                </>
              )}

              {/* If IN_PROGRESS */}
              {obligation.status === "IN_PROGRESS" && (
                <>
                  <button
                    onClick={() => setShowEvidenceModal(true)}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/20 active:scale-95 transition-all"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Complete & Attach Evidence</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("BLOCKED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors"
                  >
                    <span>Mark Blocked</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("CANCELLED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs font-medium transition-colors"
                  >
                    <span>Cancel Obligation</span>
                  </button>
                </>
              )}

              {/* If BLOCKED */}
              {obligation.status === "BLOCKED" && (
                <>
                  <button
                    onClick={() => handleStatusChange("IN_PROGRESS")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold transition-all"
                  >
                    <PlayCircle className="w-4 h-4" />
                    <span>Unblock & Resume (In Progress)</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("CONFIRMED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors"
                  >
                    <span>Return to Confirmed</span>
                  </button>
                </>
              )}

              {/* If OVERDUE */}
              {obligation.status === "OVERDUE" && (
                <>
                  <button
                    onClick={() => handleStatusChange("IN_PROGRESS")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold transition-all"
                  >
                    <PlayCircle className="w-4 h-4" />
                    <span>Work on Overdue Item</span>
                  </button>
                  <button
                    onClick={() => setShowEvidenceModal(true)}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-all"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Complete Now</span>
                  </button>
                </>
              )}

              {/* If COMPLETED */}
              {obligation.status === "COMPLETED" && (
                <button
                  onClick={() => handleStatusChange("IN_PROGRESS")}
                  disabled={updating}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors"
                >
                  <span>Reopen Obligation (In Progress)</span>
                </button>
              )}

              {/* If CANCELLED */}
              {obligation.status === "CANCELLED" && (
                <button
                  onClick={() => handleStatusChange("CONFIRMED")}
                  disabled={updating}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors"
                >
                  <span>Reactivate Obligation</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Evidence Completion Modal */}
      {showEvidenceModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <span>Complete Obligation</span>
              </h3>
              <button
                onClick={() => setShowEvidenceModal(false)}
                className="text-zinc-400 hover:text-white p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-zinc-400">
              Attach optional verification evidence or audit notes before completing this obligation.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Evidence Note / Summary
                </label>
                <textarea
                  rows={2}
                  value={evidenceNote}
                  onChange={(e) => setEvidenceNote(e.target.value)}
                  placeholder="e.g. Sent report via email to client, confirmed received."
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Artifact Link / URL (Optional)
                </label>
                <input
                  type="url"
                  value={evidenceUrl}
                  onChange={(e) => setEvidenceUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-800">
              <button
                onClick={() => setShowEvidenceModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs text-zinc-400 hover:text-zinc-200"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  handleStatusChange(
                    "COMPLETED",
                    evidenceNote || evidenceUrl
                      ? { text: evidenceNote, url: evidenceUrl, type: "completion_record" }
                      : undefined
                  )
                }
                disabled={updating}
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-all"
              >
                Confirm Completion
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
