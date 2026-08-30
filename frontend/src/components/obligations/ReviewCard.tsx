"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  Check,
  X,
  AlertTriangle,
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
  const isAmbiguousOwner = conf.owner < 0.6;

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
              <h3 className="text-base font-bold text-white">AI Extraction Review</h3>
              <ConfidenceBadge confidence={conf} field="overall" />
            </div>
            <p className="text-xs text-zinc-400">
              Human-in-the-loop: Review and adjust parameters before confirming persistence.
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
            Reject & Discard
          </button>
        </div>
      </div>

      {/* Ambiguity Alert if present */}
      {isAmbiguousOwner && (
        <div className="flex items-start gap-3 p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-amber-300">Ambiguous Ownership Detected: </span>
            The AI could not confidently identify a single owner from the text. Please explicitly verify who is responsible.
          </div>
        </div>
      )}

      {/* Raw Source Text Reference */}
      <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-3 text-xs">
        <div className="text-zinc-400 font-semibold uppercase tracking-wider mb-1 flex items-center gap-1.5">
          <span>Source Input</span>
        </div>
        <div className="text-zinc-300 italic">&ldquo;{rawText}&rdquo;</div>
      </div>

      {/* Editable Form */}
      <form onSubmit={handleConfirm} className="space-y-4">
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
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold text-zinc-300">
                Owner (Who Owes)
              </label>
              <ConfidenceBadge confidence={conf} field="owner" showIcon={false} />
            </div>
            <input
              type="text"
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 focus:border-blue-500 focus:outline-none text-sm text-zinc-100"
              placeholder="e.g. You, Ravi, Rahul..."
              required
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold text-zinc-300">
                Beneficiary (To Whom)
              </label>
              <ConfidenceBadge confidence={conf} field="beneficiary" showIcon={false} />
            </div>
            <input
              type="text"
              value={beneficiary}
              onChange={(e) => setBeneficiary(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 focus:border-blue-500 focus:outline-none text-sm text-zinc-100"
              placeholder="e.g. Rahul, Client, Professor..."
              required
            />
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

        {/* Deadline & Conditions */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold text-zinc-300">
                Deadline (Optional)
              </label>
              <ConfidenceBadge confidence={conf} field="deadline" showIcon={false} />
            </div>
            <input
              type="datetime-local"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 focus:border-blue-500 focus:outline-none text-sm text-zinc-100"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold text-zinc-300">
                Conditions / Dependencies (Optional)
              </label>
              <ConfidenceBadge confidence={conf} field="conditions" showIcon={false} />
            </div>
            <input
              type="text"
              value={conditions}
              onChange={(e) => setConditions(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 focus:border-blue-500 focus:outline-none text-sm text-zinc-100"
              placeholder="e.g. Once pricing numbers are confirmed..."
            />
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
