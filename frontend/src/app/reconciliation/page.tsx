"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Scale,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Clock,
  Sparkles,
  ArrowRight,
  RefreshCw,
  SlidersHorizontal,
} from "lucide-react";
import { AppLayout } from "../../components/layout/AppLayout";
import {
  ReconciliationRecord,
  ReconciliationStatus,
  ReconciliationListResponse,
} from "../../lib/types/obligation";
import { reconciliationApi } from "../../lib/api/obligations";
import { ReconciliationReviewModal } from "../../components/reconciliation/ReconciliationReviewModal";

export default function ReconciliationPage() {
  const [reconciliations, setReconciliations] = useState<ReconciliationRecord[]>([]);
  const [counts, setCounts] = useState({
    total: 0,
    conflicting: 0,
    consistent: 0,
    ambiguous: 0,
    resolved: 0,
  });
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [isLoading, setIsLoading] = useState(true);
  const [activeModalRec, setActiveModalRec] = useState<ReconciliationRecord | null>(null);

  const fetchReconciliations = useCallback(async () => {
    setIsLoading(true);
    try {
      const res: ReconciliationListResponse = await reconciliationApi.list({
        status: selectedStatus === "ALL" ? undefined : selectedStatus,
        limit: 50,
      });
      setReconciliations(res.items || []);
      setCounts({
        total: res.total,
        conflicting: res.conflicting_count,
        consistent: res.consistent_count,
        ambiguous: res.ambiguous_count,
        resolved: res.resolved_count,
      });
    } catch (err) {
      console.error("Failed to load reconciliations:", err);
    } finally {
      setIsLoading(false);
    }
  }, [selectedStatus]);

  useEffect(() => {
    fetchReconciliations();
  }, [fetchReconciliations]);

  const handleResolved = (updated: ReconciliationRecord) => {
    setReconciliations((prev) =>
      prev.map((r) => (r.id === updated.id ? updated : r))
    );
    fetchReconciliations();
  };

  const getStatusBadge = (status: ReconciliationStatus) => {
    switch (status) {
      case "CONFLICTING":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-rose-500/15 text-rose-400 border border-rose-500/30">
            <AlertTriangle className="w-3.5 h-3.5" />
            Contradiction Detected
          </span>
        );
      case "CONSISTENT":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Consistent Evidence
          </span>
        );
      case "AMBIGUOUS":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
            <HelpCircle className="w-3.5 h-3.5" />
            Ambiguous Signals
          </span>
        );
      case "RESOLVED_SUPPORTING":
      case "RESOLVED_CONFLICTING":
      case "DISMISSED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
            <Clock className="w-3.5 h-3.5" />
            {status.replace("_", " ")}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-zinc-800 text-zinc-300">
            {status}
          </span>
        );
    }
  };

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Phase 11 Intelligence
              </span>
              <span className="text-xs text-zinc-500">• Cross-Provider Reconciliation</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-zinc-100 flex items-center gap-3">
              <Scale className="w-7 h-7 text-indigo-400" />
              Contradiction & Reconciliation Intelligence
            </h1>
            <p className="text-sm text-zinc-400 mt-1 max-w-3xl">
              Cross-source reasoning synthesizing Slack, Gmail, and Google Calendar signals to detect contradictions, quantify consistency, and ensure zero unverified auto-completions.
            </p>
          </div>
          <button
            onClick={() => fetchReconciliations()}
            className="self-start md:self-auto inline-flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-xl border border-zinc-700 transition-all shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            Refresh Signals
          </button>
        </div>

        {/* Metrics Overview Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 bg-zinc-900/60 rounded-2xl border border-rose-500/20 shadow-sm relative overflow-hidden">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-rose-400 uppercase tracking-wider">
                Unresolved Conflicts
              </span>
              <AlertTriangle className="w-5 h-5 text-rose-400" />
            </div>
            <p className="text-2xl sm:text-3xl font-bold text-zinc-100 mt-2">
              {counts.conflicting}
            </p>
            <p className="text-xs text-zinc-500 mt-1">Requires human adjudication</p>
          </div>

          <div className="p-5 bg-zinc-900/60 rounded-2xl border border-emerald-500/20 shadow-sm relative overflow-hidden">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-emerald-400 uppercase tracking-wider">
                Consistent Clusters
              </span>
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            </div>
            <p className="text-2xl sm:text-3xl font-bold text-zinc-100 mt-2">
              {counts.consistent}
            </p>
            <p className="text-xs text-zinc-500 mt-1">Multi-source verified</p>
          </div>

          <div className="p-5 bg-zinc-900/60 rounded-2xl border border-amber-500/20 shadow-sm relative overflow-hidden">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-amber-400 uppercase tracking-wider">
                Ambiguous Signals
              </span>
              <HelpCircle className="w-5 h-5 text-amber-400" />
            </div>
            <p className="text-2xl sm:text-3xl font-bold text-zinc-100 mt-2">
              {counts.ambiguous}
            </p>
            <p className="text-xs text-zinc-500 mt-1">Prerequisite / conditional block</p>
          </div>

          <div className="p-5 bg-zinc-900/60 rounded-2xl border border-indigo-500/20 shadow-sm relative overflow-hidden">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-indigo-400 uppercase tracking-wider">
                Resolved & Audited
              </span>
              <Clock className="w-5 h-5 text-indigo-400" />
            </div>
            <p className="text-2xl sm:text-3xl font-bold text-zinc-100 mt-2">
              {counts.resolved}
            </p>
            <p className="text-xs text-zinc-500 mt-1">Historical human decisions</p>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-2 border-b border-zinc-800 pb-3 overflow-x-auto">
          <SlidersHorizontal className="w-4 h-4 text-zinc-500 mr-1 flex-shrink-0" />
          {[
            { key: "ALL", label: "All Reconciliations" },
            { key: "CONFLICTING", label: `Conflicting (${counts.conflicting})` },
            { key: "CONSISTENT", label: `Consistent (${counts.consistent})` },
            { key: "AMBIGUOUS", label: `Ambiguous (${counts.ambiguous})` },
            { key: "RESOLVED_SUPPORTING", label: "Resolved" },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setSelectedStatus(tab.key)}
              className={`px-3.5 py-1.5 text-xs font-medium rounded-xl whitespace-nowrap transition-all ${
                selectedStatus === tab.key
                  ? "bg-zinc-100 text-zinc-900 font-semibold shadow"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Reconciliation List */}
        {isLoading ? (
          <div className="py-16 text-center text-zinc-500 flex flex-col items-center gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
            <p className="text-sm">Synthesizing cross-provider evidence clusters...</p>
          </div>
        ) : reconciliations.length === 0 ? (
          <div className="py-16 text-center rounded-2xl bg-zinc-900/30 border border-zinc-800/80 p-8">
            <Scale className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
            <h3 className="text-base font-semibold text-zinc-200">No Reconciliation Records</h3>
            <p className="text-xs text-zinc-500 max-w-sm mx-auto mt-1">
              No evidence clusters match the selected filter. As new messages, emails, and meetings arrive, reconciliation analysis will appear here.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {reconciliations.map((rec) => {
              const isConflicting = rec.status === "CONFLICTING";
              const isConsistent = rec.status === "CONSISTENT";

              return (
                <div
                  key={rec.id}
                  className={`p-6 rounded-2xl bg-zinc-900/70 border transition-all hover:border-zinc-700 shadow-sm ${
                    isConflicting
                      ? "border-rose-500/30 bg-rose-950/5"
                      : isConsistent
                      ? "border-emerald-500/25 bg-emerald-950/5"
                      : "border-zinc-800"
                  }`}
                >
                  <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                    {/* Left details */}
                    <div className="space-y-3 flex-1">
                      <div className="flex flex-wrap items-center gap-2.5">
                        {getStatusBadge(rec.status)}
                        <span className="text-xs font-mono text-zinc-500">
                          Rec ID: {rec.id.slice(0, 8)}...
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-300 border border-zinc-700">
                          Status: {rec.obligation_status || "CONFIRMED"}
                        </span>
                      </div>

                      <div>
                        <Link
                          href={`/obligations/${rec.obligation_id}`}
                          className="text-base font-semibold text-zinc-100 hover:text-indigo-300 transition-colors flex items-center gap-2 group"
                        >
                          <span>{rec.obligation_action || "Target Obligation"}</span>
                          <ArrowRight className="w-4 h-4 text-zinc-500 group-hover:text-indigo-400 group-hover:translate-x-0.5 transition-all" />
                        </Link>
                        <p className="text-xs text-zinc-400 mt-0.5">
                          <span className="text-zinc-500">Owner:</span>{" "}
                          <span className="text-zinc-300 font-medium">{rec.obligation_owner || "Unassigned"}</span>{" "}
                          • <span className="text-zinc-500">Beneficiary:</span>{" "}
                          <span className="text-zinc-300 font-medium">{rec.obligation_beneficiary || "You"}</span>
                        </p>
                      </div>

                      {/* Explanation bullets */}
                      <div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800/80 text-xs text-zinc-300 space-y-1.5">
                        <div className="flex items-center gap-1.5 text-zinc-400 font-semibold text-[11px] uppercase tracking-wider">
                          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                          Evidence Reasoning & Contradiction Findings
                        </div>
                        {rec.explanation && rec.explanation.length > 0 ? (
                          rec.explanation.map((exp, idx) => (
                            <p key={idx} className="text-zinc-300 flex items-start gap-2">
                              <span className="text-zinc-500 font-mono">•</span>
                              <span>{exp}</span>
                            </p>
                          ))
                        ) : (
                          <p className="text-zinc-400">Multi-source evidence evaluated.</p>
                        )}
                      </div>
                    </div>

                    {/* Right action & metrics */}
                    <div className="lg:w-72 flex flex-col justify-between gap-4 border-t lg:border-t-0 lg:border-l border-zinc-800 lg:pl-6 pt-4 lg:pt-0">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-zinc-400">Consistency Score</span>
                          <span className="text-emerald-400 font-semibold">
                            {(rec.consistency_score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-emerald-500 h-1.5 rounded-full"
                            style={{ width: `${Math.min(100, rec.consistency_score * 100)}%` }}
                          />
                        </div>

                        <div className="flex items-center justify-between text-xs pt-1">
                          <span className="text-zinc-400">Contradiction Score</span>
                          <span className="text-rose-400 font-semibold">
                            {(rec.contradiction_score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-rose-500 h-1.5 rounded-full"
                            style={{ width: `${Math.min(100, rec.contradiction_score * 100)}%` }}
                          />
                        </div>
                      </div>

                      {/* Buttons */}
                      <div className="flex flex-col gap-2">
                        <button
                          onClick={() => setActiveModalRec(rec)}
                          className="w-full py-2 px-3 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 rounded-xl shadow-sm transition-all text-center"
                        >
                          Review & Adjudicate
                        </button>
                        <Link
                          href={`/reconciliation/${rec.id}`}
                          className="w-full py-2 px-3 text-xs font-medium text-zinc-300 hover:text-white bg-zinc-800 hover:bg-zinc-700 rounded-xl border border-zinc-700 transition-all text-center flex items-center justify-center gap-1.5"
                        >
                          <span>Evidence Timeline</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </Link>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Human Decision Modal */}
      {activeModalRec && (
        <ReconciliationReviewModal
          reconciliation={activeModalRec}
          isOpen={!!activeModalRec}
          onClose={() => setActiveModalRec(null)}
          onResolved={handleResolved}
        />
      )}
    </AppLayout>
  );
}
