"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  Check,
  X,
  Clock,
  User,
  ShieldAlert,
  GitBranch,
} from "lucide-react";
import { ObligationCandidate, ObligationCreate, ObligationType } from "@/lib/types/obligation";
import { ConfidenceBadge } from "../ui/ConfidenceBadge";
import { useToast } from "../ui/ToastContext";
import { obligationsApi } from "@/lib/api/obligations";

interface ReviewCardProps {
  candidate: ObligationCandidate;
  rawText: string;
  onReject: () => void;
  onConfirmed?: () => void;
}

export const ReviewCard: React.FC<ReviewCardProps> = ({
  candidate,
  rawText,
  onReject,
  onConfirmed,
}) => {
  const router = useRouter();
  const { toast } = useToast();
  const [submitting, setSubmitting] = useState(false);

  // Editable candidate state
  const [owner, setOwner] = useState(candidate.owner);
  const [beneficiary, setBeneficiary] = useState(candidate.beneficiary);
  const [action, setAction] = useState(candidate.action);
  const [deadline, setDeadline] = useState(
    candidate.deadline ? new Date(candidate.deadline).toISOString().slice(0, 16) : ""
  );
  const [conditions, setConditions] = useState(
    candidate.conditions ? String(candidate.conditions) : ""
  );
  const [nextAction, setNextAction] = useState(candidate.next_action || "");
  const [obligationType, setObligationType] = useState<ObligationType>(candidate.obligation_type);

  const conf = candidate.confidence;
  const resolution = candidate.resolution;
  const ambiguities = resolution?.ambiguities || [];
  const reviewRequired = resolution?.review_required || conf.owner < 0.6 || conf.deadline < 0.6;

  const isOwnerAmbiguous = conf.owner < 0.6 || resolution?.ownership?.ambiguous;
  const isDeadlineAmbiguous = conf.deadline < 0.6 || resolution?.deadline?.ambiguous;
  const isConditionalDeadline = candidate.deadline_type === "CONDITIONAL" || Boolean(conditions);

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!owner.trim() || !beneficiary.trim() || !action.trim()) {
      toast({
        type: "error",
        title: "Missing Required Fields",
        description: "Owner, Beneficiary, and Action are required.",
      });
      return;
    }

    try {
      setSubmitting(true);
      const payload: ObligationCreate = {
        owner: owner.trim(),
        beneficiary: beneficiary.trim(),
        action: action.trim(),
        deadline: deadline ? new Date(deadline).toISOString() : null,
        conditions: conditions.trim() ? conditions.trim() : null,
        next_action: nextAction.trim() ? nextAction.trim() : null,
        source_ref: candidate.source_ref || "Manual Message Extraction",
        obligation_type: obligationType,
        confidence: candidate.confidence as unknown as Record<string, unknown>,
      };

      await obligationsApi.create(payload);

      toast({
        type: "success",
        title: "Obligation Confirmed & Saved",
        description: `Persisted to ${obligationType === "OWED_BY_ME" ? "You Owe" : "Others Owe You"}.`,
      });

      if (onConfirmed) {
        onConfirmed();
      } else {
        router.push("/");
      }
    } catch (err) {
      toast({
        type: "error",
        title: "Failed to Save",
        description: err instanceof Error ? err.message : "Persistence failed.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-zinc-900 border-2 border-blue-500/30 rounded-2xl p-6 shadow-2xl space-y-6 animate-in fade-in slide-in-from-top-2">
      {/* Review Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-white">AI Extraction & Reasoning Review</h3>
              <ConfidenceBadge confidence={conf} field="overall" />
            </div>
            <p className="text-xs text-zinc-400">
              Phase 2 Reasoning: Review ownership, deadline resolution, and ambiguities before saving.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onReject}
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-700 bg-zinc-800/80 hover:bg-zinc-800 text-zinc-300 text-xs font-medium transition-colors"
          >
            <X className="w-3.5 h-3.5" />
            <span>Discard</span>
          </button>
        </div>
      </div>

      {/* Ambiguity Alert Banners */}
      {reviewRequired && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-2">
          <div className="flex items-center gap-2 text-amber-300 text-xs font-bold uppercase tracking-wider">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            <span>Human Review Required — Ambiguities Detected</span>
          </div>
          <div className="space-y-1.5">
            {ambiguities.length > 0 ? (
              ambiguities.map((amb, i) => (
                <div key={i} className="text-xs text-amber-200/90 flex items-start gap-2">
                  <span className="font-semibold text-amber-300 uppercase shrink-0">[{amb.field}]:</span>
                  <span>{amb.reason}</span>
                </div>
              ))
            ) : (
              <p className="text-xs text-amber-200/90">
                Certain field confidence scores are below threshold. Please review the highlighted parameters below.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Raw Source Text Reference */}
      <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-3 text-xs">
        <div className="text-zinc-400 font-semibold uppercase tracking-wider mb-1 flex items-center gap-1.5">
          <span>Source Input Message</span>
        </div>
        <div className="text-zinc-300 italic">&ldquo;{rawText}&rdquo;</div>
      </div>

      {/* Editable Form */}
      <form onSubmit={handleConfirm} className="space-y-5">
        {/* Direction Selector */}
        <div>
          <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
            Obligation Relationship Type
          </label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setObligationType("OWED_BY_ME")}
              className={`p-3 rounded-xl border text-left text-xs font-medium transition-all ${
                obligationType === "OWED_BY_ME"
                  ? "bg-blue-600/15 border-blue-500 text-white ring-1 ring-blue-500"
                  : "bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700"
              }`}
            >
              <div className="font-semibold text-sm text-blue-400">You Owe (Outgoing)</div>
              <div className="text-[11px] opacity-80 mt-0.5">You are responsible for delivering this to someone</div>
            </button>

            <button
              type="button"
              onClick={() => setObligationType("OWED_TO_ME")}
              className={`p-3 rounded-xl border text-left text-xs font-medium transition-all ${
                obligationType === "OWED_TO_ME"
                  ? "bg-emerald-600/15 border-emerald-500 text-white ring-1 ring-emerald-500"
                  : "bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700"
              }`}
            >
              <div className="font-semibold text-sm text-emerald-400">Others Owe You (Incoming)</div>
              <div className="text-[11px] opacity-80 mt-0.5">Another party owes this deliverable to you</div>
            </button>
          </div>
        </div>

        {/* Parties: Owner & Beneficiary */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Owner Field */}
          <div className={`p-3.5 rounded-xl border ${isOwnerAmbiguous ? "bg-amber-950/20 border-amber-500/40" : "bg-zinc-950/40 border-zinc-800"}`}>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-blue-400" />
                <span>Duty Bearer (Owner)</span>
              </label>
              <ConfidenceBadge confidence={conf} field="owner" showIcon={false} />
            </div>

            <input
              type="text"
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 focus:border-blue-500 focus:outline-none text-sm text-zinc-100 mb-2"
              placeholder="e.g. You, Rahul, Alex..."
              required
            />

            {/* Quick Assignment Shortcuts */}
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[10px] text-zinc-400 font-medium">Quick assign:</span>
              <button
                type="button"
                onClick={() => {
                  setOwner("You");
                  setObligationType("OWED_BY_ME");
                }}
                className="px-2 py-0.5 rounded text-[11px] bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
              >
                Assign to Me
              </button>
              {resolution?.ownership?.suggested_assignees?.map((suggested, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setOwner(suggested)}
                  className="px-2 py-0.5 rounded text-[11px] bg-zinc-800 hover:bg-zinc-700 text-blue-300"
                >
                  {suggested}
                </button>
              ))}
            </div>

            {resolution?.ownership?.reasoning && (
              <div className="mt-2 text-[11px] text-zinc-400 italic">
                <span className="font-semibold text-zinc-300">Reasoning:</span> {resolution.ownership.reasoning}
              </div>
            )}
          </div>

          {/* Beneficiary Field */}
          <div className="p-3.5 rounded-xl bg-zinc-950/40 border border-zinc-800">
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-emerald-400" />
                <span>Obligee (Beneficiary)</span>
              </label>
              <ConfidenceBadge confidence={conf} field="beneficiary" showIcon={false} />
            </div>

            <input
              type="text"
              value={beneficiary}
              onChange={(e) => setBeneficiary(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 focus:border-blue-500 focus:outline-none text-sm text-zinc-100"
              placeholder="e.g. Rahul, Client, Team..."
              required
            />
            <p className="text-[11px] text-zinc-400 mt-2">
              The person or party to whom the commitment is owed.
            </p>
          </div>
        </div>

        {/* Action Duty */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-semibold text-zinc-300">
              Owed Action / Commitment
            </label>
            <ConfidenceBadge confidence={conf} field="action" showIcon={false} />
          </div>
          <textarea
            rows={2}
            value={action}
            onChange={(e) => setAction(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 focus:border-blue-500 focus:outline-none text-sm text-zinc-100 resize-none"
            placeholder="Describe the exact deliverable or duty..."
            required
          />
        </div>

        {/* Deadline & Conditions Block */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Deadline Field */}
          <div className={`p-3.5 rounded-xl border ${isDeadlineAmbiguous ? "bg-amber-950/20 border-amber-500/40" : "bg-zinc-950/40 border-zinc-800"}`}>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-amber-400" />
                <span>Target Calendar Deadline</span>
              </label>
              <ConfidenceBadge confidence={conf} field="deadline" showIcon={false} />
            </div>

            <input
              type="datetime-local"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 focus:border-blue-500 focus:outline-none text-sm text-zinc-100"
            />

            {candidate.deadline_type && (
              <div className="mt-2 flex items-center gap-1.5 text-[11px]">
                <span className="text-zinc-400 font-medium">Type:</span>
                <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono text-[10px]">
                  {candidate.deadline_type}
                </span>
              </div>
            )}

            {resolution?.deadline?.reasoning && (
              <div className="mt-1.5 text-[11px] text-zinc-400 italic">
                <span className="font-semibold text-zinc-300">Reasoning:</span> {resolution.deadline.reasoning}
              </div>
            )}
          </div>

          {/* Conditions Field */}
          <div className={`p-3.5 rounded-xl border ${isConditionalDeadline ? "bg-blue-950/20 border-blue-500/40" : "bg-zinc-950/40 border-zinc-800"}`}>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5">
                <GitBranch className="w-3.5 h-3.5 text-blue-400" />
                <span>Conditions / Trigger Dependency</span>
              </label>
              <ConfidenceBadge confidence={conf} field="conditions" showIcon={false} />
            </div>

            <input
              type="text"
              value={conditions}
              onChange={(e) => setConditions(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 focus:border-blue-500 focus:outline-none text-sm text-zinc-100"
              placeholder="e.g. Once Rahul sends the database numbers..."
            />

            {isConditionalDeadline && (
              <div className="mt-2 p-2 rounded-lg bg-blue-900/30 border border-blue-500/30 text-[11px] text-blue-200">
                <span className="font-semibold">Condition:</span> Waiting for dependency to fire before obligation becomes actionable.
              </div>
            )}
          </div>
        </div>

        {/* Suggested Next Action */}
        <div>
          <label className="block text-xs font-semibold text-zinc-300 mb-1">
            Suggested Next Immediate Step
          </label>
          <input
            type="text"
            value={nextAction}
            onChange={(e) => setNextAction(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 focus:border-blue-500 focus:outline-none text-sm text-zinc-100"
            placeholder="e.g. Email Rahul the draft PDF..."
          />
        </div>

        {/* Submit Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-zinc-800">
          <button
            type="button"
            onClick={onReject}
            disabled={submitting}
            className="px-4 py-2 rounded-lg text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60 transition-colors"
          >
            Discard
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-all shadow-lg shadow-blue-600/20 active:scale-95 disabled:opacity-50"
          >
            <Check className="w-4 h-4" />
            <span>{submitting ? "Persisting..." : "Confirm & Save Obligation"}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
