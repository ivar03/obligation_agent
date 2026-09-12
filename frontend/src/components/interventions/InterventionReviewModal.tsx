"use client";

import React, { useState } from "react";
import {
  X,
  Send,
  CheckCircle2,
  Calendar,
  Sparkles,
  User,
  Layers,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Info,
} from "lucide-react";
import { Intervention } from "@/lib/types/obligation";
import { interventionsApi } from "@/lib/api/obligations";
import { useToast } from "@/components/ui/ToastContext";

interface InterventionReviewModalProps {
  intervention: Intervention | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdated: (updated: Intervention) => void;
}

export function InterventionReviewModal({
  intervention,
  isOpen,
  onClose,
  onUpdated,
}: InterventionReviewModalProps) {
  const { toast } = useToast();

  const [message, setMessage] = useState(
    intervention?.approved_message || intervention?.message_draft || ""
  );
  const [targetOwner, setTargetOwner] = useState(intervention?.target_owner || "");
  const [scheduledFor, setScheduledFor] = useState(intervention?.scheduled_for || "");
  const [showScheduleInput, setShowScheduleInput] = useState(false);
  const [showContextDetails, setShowContextDetails] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Sync state when intervention changes
  React.useEffect(() => {
    if (intervention) {
      setMessage(intervention.approved_message || intervention.message_draft || "");
      setTargetOwner(intervention.target_owner);
      setScheduledFor(intervention.scheduled_for || "");
    }
  }, [intervention]);

  if (!isOpen || !intervention) return null;

  const isUrgent = intervention.urgency === "CRITICAL" || intervention.urgency === "HIGH";

  const handleSaveDraft = async () => {
    try {
      setSubmitting(true);
      const updated = await interventionsApi.update(intervention.id, {
        approved_message: message,
        target_owner: targetOwner,
        scheduled_for: scheduledFor || null,
      });
      toast({
        type: "success",
        title: "Draft Updated",
        description: "Saved custom message edits.",
      });
      onUpdated(updated);
    } catch (err) {
      toast({
        type: "error",
        title: "Update Failed",
        description: err instanceof Error ? err.message : "Failed to update draft.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprove = async () => {
    try {
      setSubmitting(true);
      const updated = await interventionsApi.approve(intervention.id, {
        approved_by: "USER",
        approved_message: message,
      });
      toast({
        type: "success",
        title: "Intervention Approved",
        description: "Intervention is now authorized for execution.",
      });
      onUpdated(updated);
      onClose();
    } catch (err) {
      toast({
        type: "error",
        title: "Approval Failed",
        description: err instanceof Error ? err.message : "Failed to approve intervention.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleApproveAndExecute = async () => {
    try {
      setSubmitting(true);
      // 1. Approve if not already approved
      if (intervention.status === "PENDING_REVIEW") {
        await interventionsApi.approve(intervention.id, {
          approved_by: "USER",
          approved_message: message,
        });
      }
      // 2. Execute simulated mock
      const executed = await interventionsApi.execute(intervention.id);
      toast({
        type: "success",
        title: "Executed in Simulation Mode",
        description: `Follow-up simulated (Ref: ${executed.execution_reference}). No external messages sent.`,
      });
      onUpdated(executed);
      onClose();
    } catch (err) {
      toast({
        type: "error",
        title: "Execution Failed",
        description: err instanceof Error ? err.message : "Failed to execute intervention.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSchedule = async () => {
    if (!scheduledFor) {
      toast({
        type: "error",
        title: "Schedule Date Required",
        description: "Please pick a future date and time.",
      });
      return;
    }
    try {
      setSubmitting(true);
      const updated = await interventionsApi.schedule(intervention.id, {
        scheduled_for: new Date(scheduledFor).toISOString(),
        approved_message: message,
        approved_by: "USER",
      });
      toast({
        type: "success",
        title: "Intervention Scheduled",
        description: `Scheduled follow-up for ${new Date(scheduledFor).toLocaleString()}.`,
      });
      onUpdated(updated);
      onClose();
    } catch (err) {
      toast({
        type: "error",
        title: "Scheduling Failed",
        description: err instanceof Error ? err.message : "Failed to schedule intervention.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async () => {
    try {
      setSubmitting(true);
      const updated = await interventionsApi.cancel(intervention.id, "User dismissed from review modal");
      toast({
        type: "info",
        title: "Intervention Cancelled",
        description: "Intervention marked as cancelled.",
      });
      onUpdated(updated);
      onClose();
    } catch (err) {
      toast({
        type: "error",
        title: "Cancellation Failed",
        description: err instanceof Error ? err.message : "Failed to cancel.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-stone-900/40 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white border border-stone-200 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-xl flex flex-col">
        {/* Modal Header */}
        <div className="p-6 border-b border-stone-200 flex items-center justify-between sticky top-0 bg-white/95 backdrop-blur-md z-10">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-lg text-xs font-semibold uppercase tracking-wider bg-stone-100 text-stone-700 border border-stone-200">
                {intervention.intervention_type.replace(/_/g, " ")}
              </span>
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                  isUrgent
                    ? "bg-rose-50 text-rose-700 border-rose-200"
                    : "bg-orange-50 text-orange-700 border-orange-200"
                }`}
              >
                {intervention.urgency} URGENCY
              </span>
            </div>
            <h2 className="text-lg font-bold text-stone-900 tracking-tight flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-orange-500" />
              <span>Human Review & Authorization</span>
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5 flex-1">
          {/* Grounding & Rationale Banner */}
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 space-y-1.5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-stone-500 flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5 text-orange-600" />
              <span>Why This Intervention Was Planned</span>
            </h3>
            <p className="text-xs text-stone-700 leading-relaxed">{intervention.rationale}</p>
          </div>

          {/* Target & Beneficiary Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-stone-50/60 border border-stone-200 rounded-xl p-3.5">
              <label className="text-xs font-semibold text-stone-600 block mb-1.5">
                Target Recipient / Owner
              </label>
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-stone-400" />
                <input
                  type="text"
                  value={targetOwner}
                  onChange={(e) => setTargetOwner(e.target.value)}
                  className="bg-white border border-stone-200 rounded-lg px-2.5 py-1.5 text-xs text-stone-900 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/20 w-full"
                />
              </div>
            </div>

            <div className="bg-stone-50/60 border border-stone-200 rounded-xl p-3.5">
              <label className="text-xs font-semibold text-stone-600 block mb-1.5">
                Target Beneficiary
              </label>
              <div className="flex items-center gap-2 text-xs text-stone-800 pt-1">
                <Layers className="w-4 h-4 text-stone-400" />
                <span className="font-medium">{intervention.target_beneficiary}</span>
              </div>
            </div>
          </div>

          {/* Editable Suggested Message Textarea */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-wider text-stone-700 flex items-center gap-1.5">
                <Send className="w-3.5 h-3.5 text-orange-500" />
                <span>Editable Follow-Up Message Draft</span>
              </label>
              <button
                type="button"
                onClick={() => setMessage(intervention.message_draft)}
                className="text-xs text-stone-500 hover:text-orange-600 transition-colors inline-flex items-center gap-1"
                title="Reset to generated draft"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Reset to Generated Draft</span>
              </button>
            </div>

            <textarea
              rows={4}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="w-full bg-white border border-stone-200 rounded-xl p-3.5 text-xs text-stone-900 placeholder-stone-400 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/20 leading-relaxed font-sans"
              placeholder="Write follow-up message..."
            />
            <div className="flex items-center justify-between text-[11px] text-stone-500 px-1">
              <span>Grounding verified from obligation state. No hallucinations.</span>
              <span>{message.length} characters</span>
            </div>
          </div>

          {/* Optional Schedule Picker Accordion */}
          <div className="border border-stone-200 rounded-xl overflow-hidden">
            <button
              type="button"
              onClick={() => setShowScheduleInput(!showScheduleInput)}
              className="w-full p-3.5 bg-stone-50 flex items-center justify-between text-xs font-semibold text-stone-700 hover:bg-stone-100/60 transition-colors"
            >
              <span className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-stone-500" />
                <span>Schedule for Future Execution (Optional)</span>
              </span>
              {showScheduleInput ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            {showScheduleInput && (
              <div className="p-4 bg-white border-t border-stone-200 space-y-3">
                <label className="text-xs text-stone-600 block">
                  Select when this follow-up should be triggered for user approval:
                </label>
                <input
                  type="datetime-local"
                  value={scheduledFor ? scheduledFor.slice(0, 16) : ""}
                  onChange={(e) => setScheduledFor(e.target.value)}
                  className="bg-white border border-stone-200 rounded-xl px-3 py-2 text-xs text-stone-900 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/20"
                />
              </div>
            )}
          </div>

          {/* Expandable Context Packet Accordion */}
          <div className="border border-stone-200 rounded-xl overflow-hidden">
            <button
              type="button"
              onClick={() => setShowContextDetails(!showContextDetails)}
              className="w-full p-3.5 bg-stone-50 flex items-center justify-between text-xs font-semibold text-stone-700 hover:bg-stone-100/60 transition-colors"
            >
              <span className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-stone-500" />
                <span>Structured Context Packet & Risk Facts</span>
              </span>
              {showContextDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            {showContextDetails && (
              <div className="p-4 bg-white border-t border-stone-200">
                <pre className="text-xs text-stone-700 overflow-x-auto bg-stone-50 p-3 rounded-lg border border-stone-200 font-mono">
                  {JSON.stringify(intervention.context_data || {}, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer Actions */}
        <div className="p-5 border-t border-stone-200 bg-stone-50/60 flex flex-wrap items-center justify-between gap-3 sticky bottom-0 z-10">
          <button
            type="button"
            onClick={handleCancel}
            disabled={submitting}
            className="px-3.5 py-2 rounded-lg text-xs font-medium text-rose-700 hover:bg-rose-50 border border-rose-200 transition-colors disabled:opacity-50"
          >
            Dismiss / Cancel
          </button>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleSaveDraft}
              disabled={submitting}
              className="px-3.5 py-2 rounded-lg bg-white hover:bg-stone-50 border border-stone-200 text-stone-700 text-xs font-medium transition-colors shadow-sm disabled:opacity-50"
            >
              Save Draft
            </button>

            {showScheduleInput && scheduledFor ? (
              <button
                type="button"
                onClick={handleSchedule}
                disabled={submitting}
                className="px-4 py-2 rounded-lg bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold transition-all shadow-sm active:scale-95 disabled:opacity-50 flex items-center gap-1.5"
              >
                <Calendar className="w-4 h-4" />
                <span>Approve & Schedule</span>
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={handleApprove}
                  disabled={submitting}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-all shadow-sm active:scale-95 disabled:opacity-50 flex items-center gap-1.5"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Approve Intervention</span>
                </button>

                <button
                  type="button"
                  onClick={handleApproveAndExecute}
                  disabled={submitting}
                  className="px-4 py-2 rounded-lg bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold transition-all shadow-sm active:scale-95 disabled:opacity-50 flex items-center gap-1.5"
                >
                  <Send className="w-4 h-4" />
                  <span>Approve & Execute Mock</span>
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
