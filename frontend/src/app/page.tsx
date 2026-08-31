"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  ShieldAlert,
  ArrowUpRight,
  ArrowDownLeft,
  CheckCircle2,
  Sparkles,
  RefreshCw,
  Search,
  Inbox,
  AlertTriangle,
  Flame,
  Radio,
  Scale,
  Activity,
  ArrowRight,
  Brain,
} from "lucide-react";
import {
  DashboardSummaryResponse,
  Obligation,
  BulkRiskResponse,
  InterventionQueueResponse,
  Intervention,
  IngestedEvent,
  IntegrationConnection,
  ReconciliationRecord,
  IntelligenceOverviewResponse,
  MonitoringSummaryResponse,
} from "@/lib/types/obligation";
import { ObligationCard } from "@/components/obligations/ObligationCard";
import { RiskCard } from "@/components/obligations/RiskCard";
import { InterventionCard } from "@/components/interventions/InterventionCard";
import { InterventionReviewModal } from "@/components/interventions/InterventionReviewModal";
import { obligationsApi, interventionsApi, eventsApi, integrationsApi, reconciliationApi, intelligenceApi, monitoringApi } from "@/lib/api/obligations";
import { useToast } from "@/components/ui/ToastContext";

export default function DashboardPage() {
  const { toast } = useToast();
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [riskData, setRiskData] = useState<BulkRiskResponse | null>(null);
  const [queueData, setQueueData] = useState<InterventionQueueResponse | null>(null);
  const [recentEvents, setRecentEvents] = useState<IngestedEvent[]>([]);
  const [connections, setConnections] = useState<IntegrationConnection[]>([]);
  const [reconciliations, setReconciliations] = useState<ReconciliationRecord[]>([]);
  const [intelligence, setIntelligence] = useState<IntelligenceOverviewResponse | null>(null);
  const [monitoringSummary, setMonitoringSummary] = useState<MonitoringSummaryResponse | null>(null);
  const [selectedIntervention, setSelectedIntervention] = useState<Intervention | null>(null);
  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"all" | "you_owe" | "others_owe" | "at_risk">("all");

  const loadData = useCallback(async () => {
    try {
      const [summaryRes, riskRes, queueRes, eventsRes, integrationsRes, recRes, intelRes, monRes] = await Promise.all([
        obligationsApi.getDashboardSummary(),
        obligationsApi.getBulkRisks().catch(() => null),
        interventionsApi.getQueue(10).catch(() => null),
        eventsApi.list({ limit: 4 }).catch(() => null),
        integrationsApi.list().catch(() => null),
        reconciliationApi.list({ limit: 4 }).catch(() => null),
        intelligenceApi.getOverview().catch(() => null),
        monitoringApi.getSummary().catch(() => null),
      ]);
      setSummary(summaryRes);
      setRiskData(riskRes);
      setQueueData(queueRes);
      setMonitoringSummary(monRes);
      if (eventsRes?.items) setRecentEvents(eventsRes.items);
      if (integrationsRes?.connections) setConnections(integrationsRes.connections);
      if (recRes?.items) setReconciliations(recRes.items);
      if (intelRes) setIntelligence(intelRes);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load dashboard data.";
      setError(msg);
      toast({
        type: "error",
        title: "Connection Error",
        description: msg,
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Filter helper
  const filterList = (list: Obligation[]) => {
    if (!searchQuery.trim()) return list;
    const q = searchQuery.toLowerCase();
    return list.filter(
      (ob) =>
        ob.action.toLowerCase().includes(q) ||
        ob.owner.toLowerCase().includes(q) ||
        ob.beneficiary.toLowerCase().includes(q) ||
        (ob.next_action && ob.next_action.toLowerCase().includes(q))
    );
  };

  const youOweFiltered = summary ? filterList(summary.you_owe_obligations) : [];
  const othersOweFiltered = summary ? filterList(summary.others_owe_obligations) : [];
  const atRiskFiltered = summary ? filterList(summary.at_risk_obligations) : [];

  // Filter high/critical risk items for the proactive rescue section
  const highAndCriticalRisks = riskData?.items.filter(
    (item) => item.risk_level === "CRITICAL" || item.risk_level === "HIGH"
  ) || [];

  return (
    <div className="space-y-8">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
            Obligation Control Center
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Proactive commitment tracking, graph cascade monitoring, and deadline rescue.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setLoading(true);
              loadData();
            }}
            disabled={loading}
            className="p-2 rounded-lg border border-zinc-800 bg-zinc-900/80 hover:bg-zinc-800 text-zinc-300 transition-colors"
            title="Refresh Ledger"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-blue-400" : ""}`} />
          </button>
          <Link
            href="/capture"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-all shadow-lg shadow-blue-600/20 active:scale-95"
          >
            <Sparkles className="w-4 h-4" />
            <span>Capture New Obligation</span>
          </Link>
        </div>
      </div>

      {/* Connected Sources Status Indicator (Phase 8) */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 rounded-xl bg-zinc-900/70 border border-zinc-800 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-zinc-400 font-semibold flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-purple-400" />
            Connected Sources:
          </span>
          <div className="flex items-center gap-2">
            <Link
              href="/integrations"
              className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-zinc-800 hover:bg-zinc-750 text-zinc-300 font-medium transition"
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  connections.some((c) => c.provider === "slack" && c.status === "CONNECTED")
                    ? "bg-emerald-400 animate-pulse"
                    : "bg-zinc-500"
                }`}
              ></span>
              Slack{" "}
              {connections.some((c) => c.provider === "slack" && c.status === "CONNECTED")
                ? "● Connected"
                : "○ Not Connected"}
            </Link>
            <Link
              href="/integrations"
              className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-zinc-800 hover:bg-zinc-750 text-zinc-300 font-medium transition"
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  connections.some((c) => c.provider === "gmail" && c.status === "CONNECTED")
                    ? "bg-emerald-400 animate-pulse"
                    : "bg-zinc-500"
                }`}
              ></span>
              Gmail{" "}
              {connections.some((c) => c.provider === "gmail" && c.status === "CONNECTED")
                ? "● Connected"
                : "○ Not Connected"}
            </Link>
            <Link
              href="/integrations"
              className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-zinc-800 hover:bg-zinc-750 text-zinc-300 font-medium transition"
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  connections.some((c) => (c.provider === "google_calendar" || c.provider === "calendar") && c.status === "CONNECTED")
                    ? "bg-emerald-400 animate-pulse"
                    : "bg-zinc-500"
                }`}
              ></span>
              Calendar{" "}
              {connections.some((c) => (c.provider === "google_calendar" || c.provider === "calendar") && c.status === "CONNECTED")
                ? "● Connected"
                : "○ Not Connected"}
            </Link>
            <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-zinc-800 text-zinc-300 font-medium">
              <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
              Mock Provider (Dev)
            </span>
          </div>
        </div>

        {recentEvents.length > 0 && (
          <div className="flex items-center gap-2 text-zinc-400 text-xs">
            <span className="text-zinc-500">Recent Event:</span>
            <span className="text-zinc-200 font-medium max-w-sm truncate">
              &ldquo;{recentEvents[0].content}&rdquo;
            </span>
            {recentEvents[0].semantic_role === "COMPLETION_SIGNAL" && (
              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-800/60 shrink-0">
                Completion candidate detected (Human review required)
              </span>
            )}
            <Link
              href="/events"
              className="text-blue-400 hover:text-blue-300 font-semibold ml-1 shrink-0"
            >
              View &rarr;
            </Link>
          </div>
        )}
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* You Owe */}
        <div
          onClick={() => setActiveTab("you_owe")}
          className={`cursor-pointer p-5 rounded-2xl border transition-all ${
            activeTab === "you_owe"
              ? "bg-blue-950/40 border-blue-500 ring-1 ring-blue-500"
              : "bg-zinc-900/60 hover:bg-zinc-900 border-zinc-800"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              You Owe
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
              <ArrowUpRight className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 text-3xl font-extrabold text-white">
            {summary ? summary.you_owe_count : "—"}
          </div>
          <div className="mt-1 text-xs text-zinc-400">Active commitments to others</div>
        </div>

        {/* Others Owe You */}
        <div
          onClick={() => setActiveTab("others_owe")}
          className={`cursor-pointer p-5 rounded-2xl border transition-all ${
            activeTab === "others_owe"
              ? "bg-emerald-950/40 border-emerald-500 ring-1 ring-emerald-500"
              : "bg-zinc-900/60 hover:bg-zinc-900 border-zinc-800"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Others Owe You
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <ArrowDownLeft className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 text-3xl font-extrabold text-white">
            {summary ? summary.others_owe_count : "—"}
          </div>
          <div className="mt-1 text-xs text-zinc-400">Incoming promises & deliverables</div>
        </div>

        {/* At Risk */}
        <div
          onClick={() => setActiveTab("at_risk")}
          className={`cursor-pointer p-5 rounded-2xl border transition-all ${
            activeTab === "at_risk"
              ? "bg-rose-950/40 border-rose-500 ring-1 ring-rose-500"
              : "bg-zinc-900/60 hover:bg-zinc-900 border-zinc-800"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-400 uppercase tracking-wider">
              At Risk
            </span>
            <div className="w-8 h-8 rounded-lg bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <ShieldAlert className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 text-3xl font-extrabold text-rose-300">
            {riskData ? riskData.critical_count + riskData.high_count : summary?.at_risk_count ?? "—"}
          </div>
          <div className="mt-1 text-xs text-zinc-400">
            {riskData?.critical_count ? `${riskData.critical_count} critical, ` : ""}
            {riskData?.high_count ? `${riskData.high_count} high risk` : "Approaching failure"}
          </div>
        </div>

        {/* Completed */}
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Resolved
            </span>
            <div className="w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-400">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 text-3xl font-extrabold text-zinc-300">
            {summary ? summary.completed_count : "—"}
          </div>
          <div className="mt-1 text-xs text-zinc-400">Fulfilled obligations</div>
        </div>
      </div>

      {/* PHASE 17: CONTINUOUS MONITORING HEALTH & ESCALATION WIDGET */}
      {monitoringSummary && (
        <section className="bg-gradient-to-r from-violet-950/30 via-slate-900/80 to-indigo-950/30 border border-violet-500/30 rounded-2xl p-5 shadow-lg space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-violet-500/20 border border-violet-500/40 flex items-center justify-center text-violet-400">
                <Activity className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
                  <span>Continuous Monitoring &amp; Reliability Health</span>
                  {monitoringSummary.open_escalations_count > 0 && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">
                      {monitoringSummary.open_escalations_count} Open Escalations
                    </span>
                  )}
                </h2>
                <p className="text-xs text-zinc-400">
                  Continuous state-diff engine monitoring {monitoringSummary.active_watches_count} active watches across deadlines, risk shifts, and execution queues.
                </p>
              </div>
            </div>

            <Link
              href="/intelligence/monitoring"
              className="px-3.5 py-1.5 bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold rounded-lg transition flex items-center gap-1 shadow"
            >
              <span>Open Monitoring Center</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-xs">
            <div className="bg-slate-950/70 p-2.5 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Active Watches</span>
              <strong className="text-violet-300 font-mono text-sm">{monitoringSummary.active_watches_count}</strong>
            </div>
            <div className="bg-slate-950/70 p-2.5 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Critical Alerts</span>
              <strong className="text-rose-400 font-mono text-sm">{monitoringSummary.critical_events_count}</strong>
            </div>
            <div className="bg-slate-950/70 p-2.5 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Deadline Breaches</span>
              <strong className="text-slate-200 font-mono text-sm">{monitoringSummary.deadline_breaches_count}</strong>
            </div>
            <div className="bg-slate-950/70 p-2.5 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Execution Failures</span>
              <strong className="text-slate-200 font-mono text-sm">{monitoringSummary.execution_failures_count}</strong>
            </div>
          </div>
        </section>
      )}

      {/* PHASE 6: HUMAN-CONTROLLED INTERVENTION ACTION QUEUE */}
      {queueData && queueData.items.length > 0 && (
        <section className="space-y-4 rounded-2xl border border-amber-500/40 bg-gradient-to-b from-amber-950/20 via-zinc-900/80 to-zinc-950 p-5 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
                  <span>Human-Controlled Intervention Queue</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                    {queueData.total_action_required} Action Required
                  </span>
                </h2>
                <p className="text-xs text-zinc-400">
                  Prepared follow-up drafts and coordination tasks requiring explicit human review and execution.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {queueData.pending_review_count > 0 && (
                <span className="px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                  {queueData.pending_review_count} Pending Review
                </span>
              )}
              {queueData.ready_to_execute_count > 0 && (
                <span className="px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  {queueData.ready_to_execute_count} Approved / Ready
                </span>
              )}
              {queueData.scheduled_count > 0 && (
                <span className="px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/30">
                  {queueData.scheduled_count} Scheduled
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {queueData.items.map((intervention) => (
              <InterventionCard
                key={intervention.id}
                intervention={intervention}
                onReview={(inv) => {
                  setSelectedIntervention(inv);
                  setIsReviewModalOpen(true);
                }}
                onExecute={async (inv) => {
                  try {
                    const updated = await interventionsApi.execute(inv.id);
                    toast({
                      type: "success",
                      title: "Executed in Simulation Mode",
                      description: `Follow-up simulated (Ref: ${updated.execution_reference}). No external messages sent.`,
                    });
                    loadData();
                  } catch (err) {
                    toast({
                      type: "error",
                      title: "Execution Failed",
                      description: err instanceof Error ? err.message : "Failed to execute.",
                    });
                  }
                }}
              />
            ))}
          </div>
        </section>
      )}

      {/* PHASE 11: CROSS-PROVIDER RECONCILIATION & CONTRADICTION INTELLIGENCE */}
      {reconciliations.length > 0 && (
        <section className="space-y-4 rounded-2xl border border-indigo-500/30 bg-gradient-to-b from-indigo-950/20 via-zinc-900/60 to-zinc-950 p-5 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
                <Scale className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
                  <span>Cross-Provider Contradiction & Evidence Intelligence</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">
                    Phase 11
                  </span>
                </h2>
                <p className="text-xs text-zinc-400">
                  Cross-referencing Slack, Gmail, and Calendar signals for multi-source consensus and contradiction detection.
                </p>
              </div>
            </div>

            <Link
              href="/reconciliation"
              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
            >
              <span>View All ({reconciliations.length})</span>
              <span>&rarr;</span>
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {reconciliations.slice(0, 2).map((rec) => {
              const isConflicting = rec.status === "CONFLICTING";
              return (
                <div
                  key={rec.id}
                  className={`p-4 rounded-xl border transition-all ${
                    isConflicting
                      ? "bg-rose-950/20 border-rose-500/30"
                      : "bg-zinc-900/80 border-zinc-800"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={`px-2 py-0.5 text-[11px] font-semibold rounded-md ${
                        isConflicting
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                          : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                      }`}
                    >
                      {rec.status.replace("_", " ")}
                    </span>
                    <span className="text-[11px] text-zinc-400">
                      Consistency: {(rec.consistency_score * 100).toFixed(0)}%
                    </span>
                  </div>

                  <p className="text-xs font-semibold text-zinc-200 line-clamp-1 mb-1">
                    {rec.obligation_action || "Target Obligation"}
                  </p>

                  <p className="text-[11px] text-zinc-400 line-clamp-2 mb-3">
                    {rec.explanation && rec.explanation.length > 0 ? rec.explanation[0] : "Evidence reconciled."}
                  </p>

                  <Link
                    href={`/reconciliation/${rec.id}`}
                    className="text-xs font-medium text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                  >
                    <span>Inspect Timeline & Adjudicate</span>
                    <span>&rarr;</span>
                  </Link>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* PHASE 12: PREDICTIVE OBLIGATION INTELLIGENCE */}
      {intelligence && intelligence.predictions.length > 0 && (
        <section className="space-y-4 rounded-2xl border border-indigo-500/30 bg-gradient-to-b from-indigo-950/20 via-zinc-900/70 to-zinc-950 p-5 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
                <Brain className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
                  <span>Predictive Obligation Intelligence</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">
                    Phase 12
                  </span>
                </h2>
                <p className="text-xs text-zinc-400">
                  {intelligence.high_predicted_failure_count} obligations likely to require intervention • {intelligence.likely_to_miss_deadline_count} projected late • {intelligence.high_blockage_risk_count} at blockage risk
                </p>
              </div>
            </div>

            <Link
              href="/intelligence"
              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
            >
              <span>View All Predictions ({intelligence.predictions.length})</span>
              <span>&rarr;</span>
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {intelligence.predictions.slice(0, 2).map((pred) => {
              const failPct = Math.round(pred.failure_probability * 100);
              const isHigh = failPct >= 55;
              return (
                <div
                  key={pred.obligation_id}
                  className="p-4 rounded-xl bg-zinc-900/80 border border-zinc-800 hover:border-slate-700 transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span
                        className={`px-2 py-0.5 text-[11px] font-semibold rounded-md border ${
                          isHigh
                            ? "bg-rose-500/20 text-rose-300 border-rose-500/30"
                            : "bg-amber-500/20 text-amber-300 border-amber-500/30"
                        }`}
                      >
                        {isHigh ? "High Failure Risk" : "Moderate Risk"} ({failPct}%)
                      </span>
                      <span className="text-[11px] text-zinc-400 font-mono">
                        {pred.expected_delay_hours > 0 ? `+${pred.expected_delay_hours}h delay` : "On Time"}
                      </span>
                    </div>

                    <p className="text-xs font-semibold text-zinc-200 line-clamp-1 mb-1">
                      {pred.action || `Obligation ${pred.obligation_id.slice(0, 8)}`}
                    </p>
                    <p className="text-[11px] text-zinc-400 mb-2">
                      Owner: <span className="text-zinc-300 font-medium">{pred.owner || "Unassigned"}</span>
                    </p>

                    {pred.reasons && pred.reasons.length > 0 && (
                      <div className="p-2 rounded bg-zinc-950/40 border border-zinc-800/80 text-[11px] text-zinc-400 line-clamp-2 mb-3">
                        <span className="text-indigo-400 font-semibold">Why: </span>
                        {pred.reasons[0].explanation}
                      </div>
                    )}
                  </div>

                  <div className="pt-2 border-t border-zinc-800 flex items-center justify-between text-xs">
                    <span className="text-zinc-400 truncate text-[11px]">
                      {pred.preventative_recommendation || "Monitor progress"}
                    </span>
                    <Link
                      href={`/obligations/${pred.obligation_id}`}
                      className="text-indigo-400 hover:text-indigo-300 font-medium shrink-0 ml-2"
                    >
                      Details &rarr;
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* PHASE 5: PROACTIVE RISK & DEADLINE RESCUE SECTION */}
      {highAndCriticalRisks.length > 0 && (
        <section className="space-y-4 rounded-2xl border border-red-500/30 bg-gradient-to-b from-red-950/20 via-zinc-900/60 to-zinc-950 p-5 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-red-500/20 border border-red-500/40 flex items-center justify-center text-red-400">
                <Flame className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
                  <span>Proactive Risk & Deadline Rescue</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-500/20 text-red-300 border border-red-500/40">
                    {highAndCriticalRisks.length} Requires Intervention
                  </span>
                </h2>
                <p className="text-xs text-zinc-400">
                  Prioritized by failure probability, deadline urgency, and graph cascade impact.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {riskData && riskData.critical_count > 0 && (
                <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-red-500/10 text-red-400 border border-red-500/30">
                  {riskData.critical_count} Critical
                </span>
              )}
              {riskData && riskData.high_count > 0 && (
                <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                  {riskData.high_count} High
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {highAndCriticalRisks.map((assessment) => (
              <RiskCard key={assessment.obligation_id} assessment={assessment} onRefresh={loadData} />
            ))}
          </div>
        </section>
      )}

      {/* PHASE 4: Evidence Needs Review Callout */}
      {summary && summary.pending_evidence_count && summary.pending_evidence_count > 0 ? (
        <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4 animate-in fade-in">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">
                Evidence Needs Review ({summary.pending_evidence_count} Detected Signal{summary.pending_evidence_count > 1 ? "s" : ""})
              </h3>
              <p className="text-xs text-zinc-400">
                Possible fulfillment observations require human confirmation to mark tasks completed.
              </p>
            </div>
          </div>

          <Link
            href="/capture"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-all shadow-md shadow-emerald-600/20"
          >
            <span>Simulate & Review Events</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      ) : null}

      {/* PHASE 7: CONTINUOUS EVENT INGESTION RECENT ACTIVITY */}
      {recentEvents && recentEvents.length > 0 && (
        <section className="space-y-3 rounded-2xl border border-cyan-900/50 bg-gradient-to-r from-slate-900/90 via-slate-900/60 to-cyan-950/20 p-5 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
                <Activity className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
                  <span>Continuous Event Ingestion Stream</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-950 text-cyan-400 border border-cyan-800/60">
                    Live Stream
                  </span>
                </h2>
                <p className="text-xs text-slate-400">
                  Continuous multi-provider normalized event feeds and automated semantic correlation.
                </p>
              </div>
            </div>

            <Link
              href="/events"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800/60 text-xs font-semibold transition shadow-md shadow-cyan-950"
            >
              <span>Open Activity Center</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
            {recentEvents.map((evt) => (
              <Link
                key={evt.id}
                href={`/events/${evt.id}`}
                className="p-3.5 rounded-xl bg-slate-950/70 hover:bg-slate-900/90 border border-slate-800/80 transition flex flex-col justify-between gap-2 group"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-bold text-cyan-400 uppercase">{evt.provider}</span>
                    <span className="text-slate-400">{new Date(evt.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                  <p className="text-xs text-slate-200 line-clamp-2 italic font-medium group-hover:text-cyan-200 transition">
                    &ldquo;{evt.content}&rdquo;
                  </p>
                </div>

                <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-800/60">
                  <span>From: <strong className="text-slate-300">{evt.sender || "Unknown"}</strong></span>
                  <span className="text-cyan-400 font-semibold group-hover:underline">Audit &rarr;</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Search & Tab Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        {/* Tabs */}
        <div className="flex items-center p-1 bg-zinc-900 border border-zinc-800 rounded-xl overflow-x-auto">
          <button
            onClick={() => setActiveTab("all")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors whitespace-nowrap ${
              activeTab === "all"
                ? "bg-zinc-800 text-white shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            All Feeds
          </button>
          <button
            onClick={() => setActiveTab("you_owe")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors whitespace-nowrap ${
              activeTab === "you_owe"
                ? "bg-blue-600/20 text-blue-300 border border-blue-500/30"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <span>You Owe</span>
            {summary && summary.you_owe_count > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-blue-500/30 text-[10px] text-blue-200 font-bold">
                {summary.you_owe_count}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab("others_owe")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors whitespace-nowrap ${
              activeTab === "others_owe"
                ? "bg-emerald-600/20 text-emerald-300 border border-emerald-500/30"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <span>Others Owe You</span>
            {summary && summary.others_owe_count > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-emerald-500/30 text-[10px] text-emerald-200 font-bold">
                {summary.others_owe_count}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab("at_risk")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors whitespace-nowrap ${
              activeTab === "at_risk"
                ? "bg-rose-600/20 text-rose-300 border border-rose-500/30"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <span>At Risk</span>
            {riskData && (riskData.critical_count + riskData.high_count > 0) && (
              <span className="px-1.5 py-0.2 rounded-full bg-rose-500/30 text-[10px] text-rose-200 font-bold">
                {riskData.critical_count + riskData.high_count}
              </span>
            )}
          </button>
        </div>

        {/* Search input */}
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search action, owner, next step..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-xl bg-zinc-900/80 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>
      </div>

      {/* Main Feed Content */}
      {loading ? (
        <div className="space-y-4">
          <div className="h-28 bg-zinc-900/60 rounded-2xl animate-pulse" />
          <div className="h-28 bg-zinc-900/60 rounded-2xl animate-pulse" />
          <div className="h-28 bg-zinc-900/60 rounded-2xl animate-pulse" />
        </div>
      ) : error ? (
        <div className="p-8 rounded-2xl bg-zinc-900/60 border border-zinc-800 text-center space-y-3">
          <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto" />
          <h3 className="text-sm font-bold text-white">Unable to Load Obligations</h3>
          <p className="text-xs text-zinc-400 max-w-md mx-auto">{error}</p>
          <button
            onClick={loadData}
            className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold"
          >
            Retry Connection
          </button>
        </div>
      ) : (
        <div className="space-y-8">
          {/* View: ALL FEEDS */}
          {activeTab === "all" && (
            <>
              {/* You Owe Section */}
              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-blue-400 text-xs font-bold uppercase tracking-wider">
                    <ArrowUpRight className="w-4 h-4" />
                    <span>Your Commitments to Others ({youOweFiltered.length})</span>
                  </div>
                  <Link
                    href="/obligations?obligation_type=OWED_BY_ME"
                    className="text-xs text-zinc-400 hover:text-zinc-200"
                  >
                    View All &rarr;
                  </Link>
                </div>
                {youOweFiltered.length === 0 ? (
                  <div className="p-8 rounded-2xl bg-zinc-900/40 border border-zinc-800/60 text-center text-xs text-zinc-400">
                    No active outgoing obligations. You are completely caught up!
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {youOweFiltered.map((ob) => (
                      <ObligationCard key={ob.id} obligation={ob} />
                    ))}
                  </div>
                )}
              </section>

              {/* Others Owe You Section */}
              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-emerald-400 text-xs font-bold uppercase tracking-wider">
                    <ArrowDownLeft className="w-4 h-4" />
                    <span>Promises Owed to You ({othersOweFiltered.length})</span>
                  </div>
                  <Link
                    href="/obligations?obligation_type=OWED_TO_ME"
                    className="text-xs text-zinc-400 hover:text-zinc-200"
                  >
                    View All &rarr;
                  </Link>
                </div>
                {othersOweFiltered.length === 0 ? (
                  <div className="p-8 rounded-2xl bg-zinc-900/40 border border-zinc-800/60 text-center text-xs text-zinc-400">
                    No pending deliverables tracked from others.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {othersOweFiltered.map((ob) => (
                      <ObligationCard key={ob.id} obligation={ob} />
                    ))}
                  </div>
                )}
              </section>
            </>
          )}

          {/* View: YOU OWE */}
          {activeTab === "you_owe" && (
            <div className="space-y-4">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <ArrowUpRight className="w-4 h-4 text-blue-400" />
                <span>Your Outgoing Commitments ({youOweFiltered.length})</span>
              </h2>
              {youOweFiltered.length === 0 ? (
                <div className="p-12 rounded-2xl bg-zinc-900/40 border border-zinc-800 text-center space-y-2">
                  <Inbox className="w-8 h-8 text-zinc-600 mx-auto" />
                  <p className="text-xs text-zinc-400">No outgoing commitments match your filter.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {youOweFiltered.map((ob) => (
                    <ObligationCard key={ob.id} obligation={ob} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* View: OTHERS OWE */}
          {activeTab === "others_owe" && (
            <div className="space-y-4">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <ArrowDownLeft className="w-4 h-4 text-emerald-400" />
                <span>Incoming Deliverables Owed to You ({othersOweFiltered.length})</span>
              </h2>
              {othersOweFiltered.length === 0 ? (
                <div className="p-12 rounded-2xl bg-zinc-900/40 border border-zinc-800 text-center space-y-2">
                  <Inbox className="w-8 h-8 text-zinc-600 mx-auto" />
                  <p className="text-xs text-zinc-400">No incoming obligations match your filter.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {othersOweFiltered.map((ob) => (
                    <ObligationCard key={ob.id} obligation={ob} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* View: AT RISK */}
          {activeTab === "at_risk" && (
            <div className="space-y-4">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-400" />
                <span>At Risk Commitments ({riskData?.items.length ?? atRiskFiltered.length})</span>
              </h2>
              {riskData && riskData.items.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {riskData.items.map((assessment) => (
                    <RiskCard key={assessment.obligation_id} assessment={assessment} onRefresh={loadData} />
                  ))}
                </div>
              ) : atRiskFiltered.length === 0 ? (
                <div className="p-12 rounded-2xl bg-zinc-900/40 border border-zinc-800 text-center space-y-2">
                  <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
                  <p className="text-xs text-zinc-400">
                    No obligations are currently at risk or overdue.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {atRiskFiltered.map((ob) => (
                    <ObligationCard key={ob.id} obligation={ob} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Review Modal */}
      <InterventionReviewModal
        intervention={selectedIntervention}
        isOpen={isReviewModalOpen}
        onClose={() => {
          setIsReviewModalOpen(false);
          setSelectedIntervention(null);
        }}
        onUpdated={() => {
          loadData();
        }}
      />
    </div>
  );
}
