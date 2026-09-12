"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  Scale,
  Clock,
  MessageSquare,
  ArrowRight,
  Shield,
  Layers,
  FileCheck,
  Zap,
} from "lucide-react";
import { ReconciliationRecord } from "@/lib/types/obligation";
import { reconciliationApi } from "@/lib/api/obligations";
import { ReconciliationReviewModal } from "@/components/reconciliation/ReconciliationReviewModal";

export default function ReconciliationDetailPage() {
  const params = useParams();
  const id = params?.id as string;

  const [reconciliation, setReconciliation] = useState<ReconciliationRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchRecord = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await reconciliationApi.get(id);
      setReconciliation(data);
    } catch (err: unknown) {
      console.error("Failed to load reconciliation record:", err);
      const msg = err instanceof Error ? err.message : "Failed to load record.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchRecord();
  }, [fetchRecord]);

  const getProviderIcon = (provider: string) => {
    switch (provider?.toLowerCase()) {
      case "slack":
        return <MessageSquare className="w-4 h-4 text-emerald-600" />;
      case "jira":
        return <Layers className="w-4 h-4 text-orange-600" />;
      case "github":
        return <FileCheck className="w-4 h-4 text-stone-700" />;
      case "calendar":
      case "google_calendar":
        return <Clock className="w-4 h-4 text-amber-600" />;
      default:
        return <Zap className="w-4 h-4 text-stone-400" />;
    }
  };

  const getSemanticBadge = (role?: string) => {
    if (!role) return null;
    let color = "bg-stone-100 text-stone-600 border-stone-200";
    if (role === "BLOCKER_SIGNAL") color = "bg-rose-50 text-rose-700 border-rose-200";
    if (role === "COMPLETION_SIGNAL") color = "bg-emerald-50 text-emerald-700 border-emerald-200";
    if (role === "PROGRESS_SIGNAL") color = "bg-amber-50 text-amber-700 border-amber-200";

    return (
      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${color} uppercase tracking-wider`}>
        {role.replace("_", " ")}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center space-y-4">
        <div className="w-8 h-8 border-2 border-orange-600 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-xs text-stone-500">Loading reconciliation analysis details...</p>
      </div>
    );
  }

  if (error || !reconciliation) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center space-y-4">
        <AlertTriangle className="w-10 h-10 text-rose-600 mx-auto" />
        <h2 className="text-lg font-semibold text-stone-800">Reconciliation Record Not Found</h2>
        <p className="text-xs text-stone-500">{error || "Could not find the requested record."}</p>
        <Link
          href="/reconciliation"
          className="inline-flex items-center gap-2 px-4 py-2 bg-white hover:bg-stone-50 border border-stone-200 text-stone-800 text-xs font-medium rounded-lg transition-all shadow-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Reconciliation
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-8">
      {/* Navigation Breadcrumb */}
      <div className="flex items-center justify-between">
        <Link
          href="/reconciliation"
          className="inline-flex items-center gap-2 text-xs font-medium text-stone-600 hover:text-stone-900 transition-colors group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to Reconciliations
        </Link>
        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-all flex items-center gap-1.5"
        >
          <Scale className="w-3.5 h-3.5" />
          Adjudicate Decision
        </button>
      </div>

      {/* Header Summary Banner */}
      <div className="p-6 rounded-2xl bg-white border border-stone-200 space-y-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span
              className={`px-3 py-1 text-xs font-semibold rounded-full border ${
                reconciliation.status === "CONFLICTING"
                  ? "bg-rose-50 text-rose-700 border-rose-200"
                  : reconciliation.status === "CONSISTENT"
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-amber-50 text-amber-700 border-amber-200"
              }`}
            >
              {reconciliation.status.replace("_", " ")}
            </span>
            <span className="text-xs text-stone-400 font-mono">
              ID: {reconciliation.id}
            </span>
          </div>

          <Link
            href={`/obligations/${reconciliation.obligation_id}`}
            className="text-xs font-medium text-orange-600 hover:text-orange-700 transition-colors flex items-center gap-1"
          >
            <span>View Obligation Details</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-stone-900">
            {reconciliation.obligation_action || "Target Obligation Action"}
          </h1>
          <p className="text-xs text-stone-600 mt-1">
            <span className="text-stone-500">Owner:</span>{" "}
            <span className="text-stone-800 font-medium">{reconciliation.obligation_owner || "Unassigned"}</span>{" "}
            • <span className="text-stone-500">Beneficiary:</span>{" "}
            <span className="text-stone-800 font-medium">{reconciliation.obligation_beneficiary || "You"}</span>{" "}
            • <span className="text-stone-500">Status:</span>{" "}
            <span className="text-stone-800 font-semibold">{reconciliation.obligation_status || "CONFIRMED"}</span>
          </p>
        </div>

        {/* Scores Overview Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
          <div className="p-3 bg-stone-50 rounded-xl border border-stone-200">
            <span className="text-[11px] text-stone-500 font-medium block">Consistency Score</span>
            <span className="text-lg font-bold text-emerald-700">
              {(reconciliation.consistency_score * 100).toFixed(0)}%
            </span>
          </div>
          <div className="p-3 bg-stone-50 rounded-xl border border-stone-200">
            <span className="text-[11px] text-stone-500 font-medium block">Contradiction Score</span>
            <span className="text-lg font-bold text-rose-700">
              {(reconciliation.contradiction_score * 100).toFixed(0)}%
            </span>
          </div>
          <div className="p-3 bg-stone-50 rounded-xl border border-stone-200">
            <span className="text-[11px] text-stone-500 font-medium block">AI Reasoning Confidence</span>
            <span className="text-lg font-bold text-orange-600">
              {(reconciliation.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>

      {/* AI Explanations Box */}
      <div className="p-5 rounded-2xl bg-white border border-stone-200 space-y-3 shadow-sm">
        <h2 className="text-xs font-semibold text-stone-700 uppercase tracking-wider flex items-center gap-1.5">
          <Shield className="w-4 h-4 text-orange-600" />
          Cross-Source Contradiction Reasoning
        </h2>
        <div className="space-y-2">
          {reconciliation.explanation && reconciliation.explanation.length > 0 ? (
            reconciliation.explanation.map((exp, idx) => (
              <div key={idx} className="p-3 rounded-xl bg-stone-50 border border-stone-200 text-xs text-stone-700 flex items-start gap-2.5">
                <span className="text-orange-600 font-mono font-bold mt-0.5">#{idx + 1}</span>
                <span>{exp}</span>
              </div>
            ))
          ) : (
            <p className="text-xs text-stone-500">All evidence signals are consistent.</p>
          )}
        </div>
      </div>

      {/* Chronological Evidence Timeline */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-stone-800 flex items-center gap-2">
            <Clock className="w-4 h-4 text-orange-600" />
            Chronological Evidence Provenance Timeline
          </h2>
          <span className="text-xs text-stone-500">
            {reconciliation.evidence_timeline?.length || 0} observations recorded
          </span>
        </div>

        <div className="relative border-l border-stone-200 ml-4 pl-6 space-y-6">
          {reconciliation.evidence_timeline && reconciliation.evidence_timeline.length > 0 ? (
            reconciliation.evidence_timeline.map((ev, idx) => {
              const isSupp = ev.is_supporting;
              const isConf = ev.is_conflicting;

              return (
                <div key={ev.evidence_id || idx} className="relative group">
                  {/* Dot on timeline */}
                  <div
                    className={`absolute -left-[31px] top-4 w-4 h-4 rounded-full border-2 bg-white transition-transform group-hover:scale-125 ${
                      isConf
                        ? "border-rose-500"
                        : isSupp
                        ? "border-emerald-500"
                        : "border-stone-400"
                    }`}
                  />

                  {/* Evidence Card */}
                  <div
                    className={`p-4 rounded-xl border transition-all shadow-sm ${
                      isConf
                        ? "bg-rose-50/40 border-rose-200"
                        : isSupp
                        ? "bg-emerald-50/40 border-emerald-200"
                        : "bg-white border-stone-200"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="p-1.5 rounded-lg bg-stone-100 border border-stone-200">
                          {getProviderIcon(ev.provider || ev.source_type)}
                        </span>
                        <span className="text-xs font-semibold text-stone-800 capitalize">
                          {ev.provider || ev.source_type}
                        </span>
                        <span className="text-stone-400 text-xs">•</span>
                        <span className="text-xs text-stone-500">
                          {new Date(ev.observed_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {getSemanticBadge(ev.semantic_role)}
                        <span className="text-xs text-stone-500 font-mono">
                          {(ev.correlation_confidence * 100).toFixed(0)}% Match
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-stone-800 font-mono bg-stone-50 p-3 rounded-lg border border-stone-200 mb-2 whitespace-pre-wrap">
                      {ev.content}
                    </p>

                    <div className="flex flex-wrap items-center gap-4 text-xs text-stone-600">
                      {ev.actor && (
                        <div>
                          <span className="text-stone-500">Actor/Sender:</span>{" "}
                          <span className="text-stone-700 font-medium">{ev.actor}</span>
                        </div>
                      )}
                      {ev.source_ref && (
                        <div>
                          <span className="text-stone-500">Source Ref:</span>{" "}
                          <span className="text-stone-600 font-mono">{ev.source_ref}</span>
                        </div>
                      )}
                      {isConf && (
                        <span className="text-rose-700 font-semibold flex items-center gap-1">
                          <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                          Conflicting Signal
                        </span>
                      )}
                      {isSupp && (
                        <span className="text-emerald-700 font-semibold flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          Supporting Signal
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          ) : (
            <p className="text-xs text-stone-400">No evidence timeline observations found.</p>
          )}
        </div>
      </div>

      {/* Decision Review Modal */}
      {isModalOpen && (
        <ReconciliationReviewModal
          reconciliation={reconciliation}
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onResolved={(updated) => {
            setReconciliation(updated);
            fetchRecord();
          }}
        />
      )}
    </div>
  );
}
