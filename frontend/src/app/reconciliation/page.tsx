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
  Info,
  ShieldCheck,
} from "lucide-react";
import {
  ReconciliationRecord,
  ReconciliationStatus,
  ReconciliationListResponse,
} from "../../lib/types/obligation";
import { reconciliationApi } from "../../lib/api/obligations";
import { ReconciliationReviewModal } from "../../components/reconciliation/ReconciliationReviewModal";

export default function ReconciliationPage() {
  const [reconciliations, setReconciliations] = useState<ReconciliationRecord[]>([]);
  const [selectedStatus, setSelectedStatus] = useState<ReconciliationStatus | "ALL">("ALL");
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [counts, setCounts] = useState({
    total: 0,
    conflicting: 0,
    consistent: 0,
    ambiguous: 0,
    resolved: 0,
  });
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

  const handleRefreshSignals = async () => {
    setIsRefreshing(true);
    try {
      const res = await reconciliationApi.refresh();
      if (res && res.items) {
        setReconciliations(res.items);
        setCounts({
          total: res.total,
          conflicting: res.conflicting_count,
          consistent: res.consistent_count,
          ambiguous: res.ambiguous_count,
          resolved: res.resolved_count,
        });
      } else {
        await fetchReconciliations();
      }
    } catch (err) {
      console.error("Failed to re-evaluate signals:", err);
      await fetchReconciliations();
    } finally {
      setIsRefreshing(false);
    }
  };

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
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-rose-50 text-rose-700 border border-rose-200">
            <AlertTriangle className="w-3.5 h-3.5" />
            Contradiction Detected
          </span>
        );
      case "CONSISTENT":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Consistent Evidence
          </span>
        );
      case "AMBIGUOUS":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-50 text-amber-800 border border-amber-200">
            <HelpCircle className="w-3.5 h-3.5" />
            Ambiguous Signals
          </span>
        );
      case "RESOLVED_SUPPORTING":
      case "RESOLVED_CONFLICTING":
      case "DISMISSED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-slate-100 text-slate-700 border border-slate-200">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            {status.replace("_", " ")}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full bg-slate-100 text-slate-700">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 text-[10px] font-bold rounded-full bg-orange-100 text-orange-800 border border-orange-200">
              Cross-Source Truth
            </span>
            <span className="text-xs text-slate-500">• Multi-Source Consensus</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2.5">
            <Scale className="w-6 h-6 text-orange-600" />
            Evidence Reconciliation Center
          </h1>
          <p className="text-xs text-slate-500 mt-1 max-w-3xl">
            Synthesizes signals from Slack, Jira, Gmail, and Google Calendar to detect contradictions, quantify evidence confidence, and guard against premature automated closures.
          </p>
        </div>
        <button
          onClick={() => handleRefreshSignals()}
          disabled={isRefreshing || isLoading}
          className="self-start md:self-auto inline-flex items-center gap-2 px-4 py-2 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-xl border border-slate-200 transition-all shadow-xs disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-orange-600 ${isRefreshing || isLoading ? "animate-spin" : ""}`} />
          <span>Re-Evaluate Signals</span>
        </button>
      </div>

      {/* THREE CORE QUESTIONS CARD: Section 15 UX Principle */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-1">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
            1. What does the system believe?
          </div>
          <div className="text-xs font-semibold text-slate-800 leading-snug">
            Ground-truth commitment state derived from verified completions and multi-channel events.
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-1">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
            2. What sources support that?
          </div>
          <div className="text-xs font-semibold text-slate-800 leading-snug">
            Confirmed PR merges, Jira status changes, calendar milestones, and explicit stakeholder receipts.
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-1">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
            3. Where do sources disagree?
          </div>
          <div className="text-xs font-semibold text-slate-800 leading-snug">
            Flagged contradictions where Slack threads claim delay while Jira cards remain marked done.
          </div>
        </div>
      </div>

      {/* Metrics Overview Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 bg-white rounded-2xl border border-rose-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-rose-700 uppercase tracking-wider">
              Contradictions
            </span>
            <AlertTriangle className="w-4 h-4 text-rose-600" />
          </div>
          <p className="text-2xl font-extrabold text-slate-900 mt-2">
            {counts.conflicting}
          </p>
          <p className="text-xs text-rose-700 mt-1">Requires human review</p>
        </div>

        <div className="p-5 bg-white rounded-2xl border border-emerald-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-emerald-700 uppercase tracking-wider">
              Consistent Evidence
            </span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <p className="text-2xl font-extrabold text-slate-900 mt-2">
            {counts.consistent}
          </p>
          <p className="text-xs text-emerald-700 mt-1">Multi-source verified</p>
        </div>

        <div className="p-5 bg-white rounded-2xl border border-amber-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-700 uppercase tracking-wider">
              Ambiguous Signals
            </span>
            <HelpCircle className="w-4 h-4 text-amber-600" />
          </div>
          <p className="text-2xl font-extrabold text-slate-900 mt-2">
            {counts.ambiguous}
          </p>
          <p className="text-xs text-amber-700 mt-1">Conditional block</p>
        </div>

        <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">
              Resolved &amp; Audited
            </span>
            <Clock className="w-4 h-4 text-slate-500" />
          </div>
          <p className="text-2xl font-extrabold text-slate-900 mt-2">
            {counts.resolved}
          </p>
          <p className="text-xs text-slate-500 mt-1">Historical adjudicated</p>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-3 overflow-x-auto">
        <SlidersHorizontal className="w-4 h-4 text-slate-400 mr-1 shrink-0" />
        {[
          { key: "ALL", label: "All Reconciliations" },
          { key: "CONFLICTING", label: `Conflicting (${counts.conflicting})` },
          { key: "CONSISTENT", label: `Consistent (${counts.consistent})` },
          { key: "AMBIGUOUS", label: `Ambiguous (${counts.ambiguous})` },
          { key: "RESOLVED_SUPPORTING", label: "Resolved" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setSelectedStatus(tab.key as ReconciliationStatus | "ALL")}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-xl whitespace-nowrap transition-all ${
              selectedStatus === tab.key
                ? "bg-orange-600 text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Reconciliation Items List */}
      {isLoading ? (
        <div className="py-16 text-center text-slate-500 flex flex-col items-center gap-3">
          <RefreshCw className="w-6 h-6 animate-spin text-orange-600" />
          <p className="text-xs">Synthesizing cross-provider evidence clusters...</p>
        </div>
      ) : reconciliations.length === 0 ? (
        <div className="py-16 text-center rounded-3xl bg-white border border-slate-200 p-8 shadow-xs max-w-md mx-auto space-y-3">
          <Scale className="w-10 h-10 text-slate-400 mx-auto" />
          <h3 className="text-base font-bold text-slate-900">No Reconciliation Records</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            No evidence clusters match the selected filter. As new signals from Slack, Jira, and Calendar arrive, cross-source evaluation records will appear here.
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
                className={`p-6 rounded-2xl bg-white border transition-all hover:border-slate-300 shadow-xs ${
                  isConflicting
                    ? "border-rose-300 ring-1 ring-rose-300/30"
                    : isConsistent
                    ? "border-emerald-300 ring-1 ring-emerald-300/20"
                    : "border-slate-200"
                }`}
              >
                <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
                  {/* Left Details */}
                  <div className="space-y-3 flex-1">
                    <div className="flex flex-wrap items-center gap-2.5">
                      {getStatusBadge(rec.status)}
                      <span className="text-xs font-mono text-slate-600">
                        Rec ID: {rec.id.slice(0, 8)}...
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 border border-slate-200 font-medium">
                        Target State: {rec.obligation_status || "CONFIRMED"}
                      </span>
                    </div>

                    <div>
                      <Link
                        href={`/obligations/${rec.obligation_id}`}
                        className="text-base font-bold text-slate-900 hover:text-orange-600 transition-colors flex items-center gap-2 group"
                      >
                        <span>{rec.obligation_action || "Target Obligation"}</span>
                        <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-orange-600 group-hover:translate-x-0.5 transition-all" />
                      </Link>
                      <p className="text-xs text-slate-500 mt-1">
                        Owner: <strong className="text-slate-800 font-semibold">{rec.obligation_owner || "Unassigned"}</strong>{" "}
                        • Beneficiary:{" "}
                        <strong className="text-slate-800 font-semibold">{rec.obligation_beneficiary || "You"}</strong>
                      </p>
                    </div>

                    {/* Explanation Reasoning */}
                    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 text-xs text-slate-700 space-y-1.5">
                      <div className="flex items-center gap-1.5 text-slate-800 font-bold text-[11px] uppercase tracking-wider">
                        <Sparkles className="w-3.5 h-3.5 text-orange-600" />
                        Evidence Reasoning &amp; Multi-Source Findings
                      </div>
                      {rec.explanation && rec.explanation.length > 0 ? (
                        rec.explanation.map((exp, idx) => (
                          <p key={idx} className="text-slate-700 flex items-start gap-2">
                            <span className="text-orange-500 font-mono">•</span>
                            <span>{exp}</span>
                          </p>
                        ))
                      ) : (
                        <p className="text-slate-500">Multi-source evidence evaluated.</p>
                      )}
                    </div>
                  </div>

                  {/* Right Metrics & Action */}
                  <div className="lg:w-72 flex flex-col justify-between gap-4 border-t lg:border-t-0 lg:border-l border-slate-200 lg:pl-6 pt-4 lg:pt-0">
                    <div className="space-y-3">
                      <div>
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="text-slate-600 font-medium">Consistency Score</span>
                          <span className="text-emerald-700 font-bold">
                            {(rec.consistency_score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                          <div
                            className="bg-emerald-500 h-2 rounded-full"
                            style={{ width: `${Math.min(100, rec.consistency_score * 100)}%` }}
                          />
                        </div>
                      </div>

                      <div>
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="text-slate-600 font-medium">Contradiction Score</span>
                          <span className="text-rose-700 font-bold">
                            {(rec.contradiction_score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                          <div
                            className="bg-rose-500 h-2 rounded-full"
                            style={{ width: `${Math.min(100, rec.contradiction_score * 100)}%` }}
                          />
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 pt-2">
                      <button
                        onClick={() => setActiveModalRec(rec)}
                        className="w-full py-2.5 px-3 text-xs font-bold text-white bg-orange-600 hover:bg-orange-700 rounded-xl shadow-xs transition-all text-center"
                      >
                        Review &amp; Adjudicate
                      </button>
                      <Link
                        href={`/obligations/${rec.obligation_id}`}
                        className="w-full py-2 px-3 text-xs font-semibold text-slate-700 hover:text-slate-900 bg-slate-50 hover:bg-slate-100 rounded-xl border border-slate-200 transition-all text-center flex items-center justify-center gap-1.5"
                      >
                        <span>Obligation Graph</span>
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

      {/* Human Decision Modal */}
      {activeModalRec && (
        <ReconciliationReviewModal
          reconciliation={activeModalRec}
          isOpen={!!activeModalRec}
          onClose={() => setActiveModalRec(null)}
          onResolved={handleResolved}
        />
      )}
    </div>
  );
}
