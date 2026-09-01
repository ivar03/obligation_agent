"use client";

import React, { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import {
  Scale,
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Sparkles,
  Calendar,
  Mail,
  MessageSquare,
  FileText,
  ArrowRight,
  RefreshCw,
} from "lucide-react";
import {
  ReconciliationRecord,
} from "../../../lib/types/obligation";

import { reconciliationApi } from "../../../lib/api/obligations";
import { ReconciliationReviewModal } from "../../../components/reconciliation/ReconciliationReviewModal";

export default function ReconciliationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const reconciliationId = resolvedParams.id;

  const [reconciliation, setReconciliation] = useState<ReconciliationRecord | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchRecord = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await reconciliationApi.getById(reconciliationId);
      setReconciliation(data);
    } catch (err: unknown) {
      console.error("Failed to load reconciliation detail:", err);
      const msg = err instanceof Error ? err.message : "Failed to load reconciliation record.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [reconciliationId]);

  useEffect(() => {
    fetchRecord();
  }, [fetchRecord]);

  const getProviderIcon = (provider: string) => {
    const p = provider.toLowerCase();
    if (p.includes("slack")) return <MessageSquare className="w-4 h-4 text-purple-400" />;
    if (p.includes("gmail") || p.includes("email")) return <Mail className="w-4 h-4 text-rose-400" />;
    if (p.includes("calendar")) return <Calendar className="w-4 h-4 text-emerald-400" />;
    return <FileText className="w-4 h-4 text-blue-400" />;
  };

  const getSemanticBadge = (role: string) => {
    switch (role) {
      case "COMPLETION_SIGNAL":
        return (
          <span className="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
            COMPLETION SIGNAL
          </span>
        );
      case "NON_COMPLETION_SIGNAL":
        return (
          <span className="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-rose-500/15 text-rose-300 border border-rose-500/30">
            NEGATIVE / BLOCKER
          </span>
        );
      case "PROGRESS_UPDATE":
        return (
          <span className="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-blue-500/15 text-blue-300 border border-blue-500/30">
            PROGRESS UPDATE
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-zinc-800 text-zinc-400">
            {role}
          </span>
        );
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center text-zinc-500 flex flex-col items-center gap-3">
        <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
        <p className="text-sm">Loading reconciliation provenance timeline...</p>
      </div>
    );
  }

  if (error || !reconciliation) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center space-y-4">
        <AlertTriangle className="w-10 h-10 text-rose-400 mx-auto" />
        <h2 className="text-lg font-semibold text-zinc-200">Reconciliation Record Not Found</h2>
        <p className="text-xs text-zinc-400">{error || "Could not find the requested record."}</p>
        <Link
          href="/reconciliation"
          className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-xl transition-all"
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
            className="inline-flex items-center gap-2 text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors group"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
            Back to Reconciliations
          </Link>
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-md shadow-indigo-600/20 transition-all flex items-center gap-1.5"
          >
            <Scale className="w-3.5 h-3.5" />
            Adjudicate Decision
          </button>
        </div>

        {/* Header Summary Banner */}
        <div className="p-6 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span
                className={`px-3 py-1 text-xs font-semibold rounded-full border ${
                  reconciliation.status === "CONFLICTING"
                    ? "bg-rose-500/15 text-rose-400 border-rose-500/30"
                    : reconciliation.status === "CONSISTENT"
                    ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                    : "bg-amber-500/15 text-amber-400 border-amber-500/30"
                }`}
              >
                {reconciliation.status.replace("_", " ")}
              </span>
              <span className="text-xs text-zinc-500 font-mono">
                ID: {reconciliation.id}
              </span>
            </div>
            <Link
              href={`/obligations/${reconciliation.obligation_id}`}
              className="text-xs font-medium text-indigo-400 hover:text-indigo-300 transition-colors flex items-center gap-1"
            >
              <span>View Obligation Details</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-zinc-100">
              {reconciliation.obligation_action || "Target Obligation Action"}
            </h1>
            <p className="text-xs text-zinc-400 mt-1">
              <span className="text-zinc-500">Owner:</span>{" "}
              <span className="text-zinc-200 font-medium">{reconciliation.obligation_owner || "Unassigned"}</span>{" "}
              • <span className="text-zinc-500">Beneficiary:</span>{" "}
              <span className="text-zinc-200 font-medium">{reconciliation.obligation_beneficiary || "You"}</span>{" "}
              • <span className="text-zinc-500">Status:</span>{" "}
              <span className="text-zinc-200 font-semibold">{reconciliation.obligation_status || "CONFIRMED"}</span>
            </p>
          </div>

          {/* Scores Overview Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
            <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800">
              <span className="text-[11px] text-zinc-400 font-medium block">Consistency Score</span>
              <span className="text-lg font-bold text-emerald-400">
                {(reconciliation.consistency_score * 100).toFixed(0)}%
              </span>
            </div>
            <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800">
              <span className="text-[11px] text-zinc-400 font-medium block">Contradiction Score</span>
              <span className="text-lg font-bold text-rose-400">
                {(reconciliation.contradiction_score * 100).toFixed(0)}%
              </span>
            </div>
            <div className="p-3 bg-zinc-950/60 rounded-xl border border-zinc-800">
              <span className="text-[11px] text-zinc-400 font-medium block">AI Reasoning Confidence</span>
              <span className="text-lg font-bold text-indigo-400">
                {(reconciliation.confidence * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>

        {/* AI Explanations Box */}
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-3">
          <h2 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-amber-400" />
            Cross-Source Contradiction Reasoning
          </h2>
          <div className="space-y-2">
            {reconciliation.explanation && reconciliation.explanation.length > 0 ? (
              reconciliation.explanation.map((exp, idx) => (
                <div key={idx} className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 text-xs text-zinc-300 flex items-start gap-2.5">
                  <span className="text-indigo-400 font-mono font-bold mt-0.5">#{idx + 1}</span>
                  <span>{exp}</span>
                </div>
              ))
            ) : (
              <p className="text-xs text-zinc-400">All evidence signals are consistent.</p>
            )}
          </div>
        </div>

        {/* Chronological Evidence Timeline */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
              <Clock className="w-4 h-4 text-indigo-400" />
              Chronological Evidence Provenance Timeline
            </h2>
            <span className="text-xs text-zinc-500">
              {reconciliation.evidence_timeline?.length || 0} observations recorded
            </span>
          </div>

          <div className="relative border-l border-zinc-800 ml-4 pl-6 space-y-6">
            {reconciliation.evidence_timeline && reconciliation.evidence_timeline.length > 0 ? (
              reconciliation.evidence_timeline.map((ev, idx) => {
                const isSupp = ev.is_supporting;
                const isConf = ev.is_conflicting;

                return (
                  <div key={ev.evidence_id || idx} className="relative group">
                    {/* Dot on timeline */}
                    <div
                      className={`absolute -left-[31px] top-4 w-4 h-4 rounded-full border-2 bg-zinc-950 transition-transform group-hover:scale-125 ${
                        isConf
                          ? "border-rose-500 text-rose-500"
                          : isSupp
                          ? "border-emerald-500 text-emerald-500"
                          : "border-zinc-600 text-zinc-600"
                      }`}
                    />

                    {/* Evidence Card */}
                    <div
                      className={`p-4 rounded-xl border transition-all ${
                        isConf
                          ? "bg-rose-950/10 border-rose-500/30"
                          : isSupp
                          ? "bg-emerald-950/10 border-emerald-500/30"
                          : "bg-zinc-900 border-zinc-800"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="p-1.5 rounded-lg bg-zinc-800">
                            {getProviderIcon(ev.provider || ev.source_type)}
                          </span>
                          <span className="text-xs font-semibold text-zinc-200 capitalize">
                            {ev.provider || ev.source_type}
                          </span>
                          <span className="text-zinc-500 text-xs">•</span>
                          <span className="text-xs text-zinc-400">
                            {new Date(ev.observed_at).toLocaleString()}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {getSemanticBadge(ev.semantic_role)}
                          <span className="text-xs text-zinc-400 font-mono">
                            {(ev.correlation_confidence * 100).toFixed(0)}% Match
                          </span>
                        </div>
                      </div>

                      <p className="text-sm text-zinc-100 font-mono bg-zinc-950/80 p-3 rounded-lg border border-zinc-800/80 mb-2 whitespace-pre-wrap">
                        {ev.content}
                      </p>

                      <div className="flex flex-wrap items-center gap-4 text-xs text-zinc-400">
                        {ev.actor && (
                          <div>
                            <span className="text-zinc-500">Actor/Sender:</span>{" "}
                            <span className="text-zinc-300 font-medium">{ev.actor}</span>
                          </div>
                        )}
                        {ev.source_ref && (
                          <div>
                            <span className="text-zinc-500">Source Ref:</span>{" "}
                            <span className="text-zinc-400 font-mono">{ev.source_ref}</span>
                          </div>
                        )}
                        {isConf && (
                          <span className="text-rose-400 font-semibold flex items-center gap-1">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            Conflicting Signal
                          </span>
                        )}
                        {isSupp && (
                          <span className="text-emerald-400 font-semibold flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            Supporting Signal
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="text-xs text-zinc-500">No evidence timeline observations found.</p>
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


