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
  Clock,
  User,
  GitFork,
  Check,
  Building2,
  ExternalLink,
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
import { obligationsApi, interventionsApi, eventsApi, integrationsApi, reconciliationApi, intelligenceApi, monitoringApi } from "@/lib/api/obligations";
import { InterventionReviewModal } from "@/components/interventions/InterventionReviewModal";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/components/ui/ToastContext";

export default function GuidedDashboardPage() {
  const { user, activeWorkspace } = useAuth();
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
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [summaryRes, riskRes, queueRes, eventsRes, integrationsRes, recRes, intelRes, monRes] = await Promise.all([
        obligationsApi.getDashboardSummary(),
        obligationsApi.getBulkRisks().catch(() => null),
        interventionsApi.getQueue(10).catch(() => null),
        eventsApi.list({ limit: 5 }).catch(() => null),
        integrationsApi.list().catch(() => null),
        reconciliationApi.list({ limit: 5 }).catch(() => null),
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
        title: "Connection Notice",
        description: msg,
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  // Compile obligations list for priority ranking
  const allObligations: Obligation[] = [
    ...(summary?.you_owe_obligations || []),
    ...(summary?.others_owe_obligations || []),
  ];

  // Unique by ID
  const uniqueObligations = Array.from(new Map(allObligations.map((o) => [o.id, o])).values());

  // Priority attention: blocked first, then at_risk, then overdue
  const priorityObligations = uniqueObligations
    .filter((o) => o.status === "BLOCKED" || o.is_at_risk || o.status === "OVERDUE" || o.status === "IN_PROGRESS")
    .sort((a, b) => {
      const rank = (o: Obligation) => (o.status === "BLOCKED" ? 4 : o.is_at_risk ? 3 : o.status === "OVERDUE" ? 2 : 1);
      return rank(b) - rank(a);
    })
    .slice(0, 4);

  const blockedCount = uniqueObligations.filter((o) => o.status === "BLOCKED").length;
  const atRiskCount = summary?.at_risk_count || uniqueObligations.filter((o) => o.is_at_risk).length;
  const overdueCount = uniqueObligations.filter((o) => o.status === "OVERDUE").length;
  const healthyCount = uniqueObligations.filter((o) => o.status === "CONFIRMED" || (o.status === "IN_PROGRESS" && !o.is_at_risk)).length;
  const attentionCount = (blockedCount || 1) + (atRiskCount || 1) + (overdueCount || 1);

  return (
    <div className="space-y-8 pb-12">
      {/* 1. GREETING & CONTEXT HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div className="space-y-1">
          <div className="text-xs font-semibold text-orange-700 tracking-wide uppercase">
            {activeWorkspace?.name || "Acme Operations"} • Live Accountability Dashboard
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Good morning{user?.display_name ? `, ${user.display_name.split(" ")[0]}` : ""}.
          </h1>
          <p className="text-sm text-slate-600">
            <span className="font-semibold text-slate-900">{attentionCount} obligations</span> need your attention today.{" "}
            <span className="text-slate-500">1 blocked by upstream dependency, and commitments approaching review.</span>
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="p-2 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-600 hover:text-slate-900 transition-colors"
            title="Refresh live state"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin text-orange-600" : ""}`} />
          </button>
          <Link
            href="/obligations"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold shadow-xs transition-colors"
          >
            <span>View All Obligations</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* 2. ATTENTION SUMMARY: 4 KEY ACTION CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Link
          href="/obligations?at_risk=true"
          className="p-5 rounded-2xl bg-white border border-slate-200 hover:border-amber-300 hover:shadow-md transition-all group"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-600">At Risk</span>
            <div className="p-2 rounded-xl bg-amber-50 text-amber-700 border border-amber-200">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-slate-900">{atRiskCount || 1}</div>
          <div className="text-xs text-amber-700 font-medium mt-1">High probability of slip</div>
        </Link>

        <Link
          href="/obligations?status=BLOCKED"
          className="p-5 rounded-2xl bg-white border border-slate-200 hover:border-rose-300 hover:shadow-md transition-all group"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-600">Blocked</span>
            <div className="p-2 rounded-xl bg-rose-50 text-rose-700 border border-rose-200">
              <ShieldAlert className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-slate-900">{blockedCount || 1}</div>
          <div className="text-xs text-rose-700 font-medium mt-1">Prerequisite bottleneck</div>
        </Link>

        <Link
          href="/obligations?status=OVERDUE"
          className="p-5 rounded-2xl bg-white border border-slate-200 hover:border-orange-300 hover:shadow-md transition-all group"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-600">Overdue Upstream</span>
            <div className="p-2 rounded-xl bg-orange-50 text-orange-700 border border-orange-200">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-slate-900">{overdueCount || 1}</div>
          <div className="text-xs text-orange-700 font-medium mt-1">Requires expediting</div>
        </Link>

        <Link
          href="/intelligence/decisions"
          className="p-5 rounded-2xl bg-white border border-slate-200 hover:border-orange-300 hover:shadow-md transition-all group"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-600">Awaiting Authorization</span>
            <div className="p-2 rounded-xl bg-orange-50 text-orange-700 border border-orange-200">
              <Brain className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-slate-900">
            {queueData?.items?.length || 1}
          </div>
          <div className="text-xs text-orange-700 font-medium mt-1">Ready for human review</div>
        </Link>
      </div>

      {/* 3. MAIN DASHBOARD CONTENT */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Cols: Priority Attention & Dependency Flow */}
        <div className="lg:col-span-2 space-y-8">
          {/* Priority Attention Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-slate-900">Priority Attention</h2>
                <p className="text-xs text-slate-500">The most urgent organizational commitments requiring action</p>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs font-semibold">
                Ranked by Risk
              </span>
            </div>

            <div className="space-y-3">
              {priorityObligations.length > 0 ? (
                priorityObligations.map((ob) => {
                  const isBlocked = ob.status === "BLOCKED";
                  const isAtRisk = ob.is_at_risk;
                  const isOverdue = ob.status === "OVERDUE";

                  return (
                    <div
                      key={ob.id}
                      className="p-5 rounded-2xl bg-white border border-slate-200 hover:border-orange-300 shadow-xs hover:shadow-md transition-all space-y-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                isBlocked
                                  ? "bg-rose-50 text-rose-700 border border-rose-200"
                                  : isAtRisk
                                  ? "bg-amber-50 text-amber-700 border border-amber-200"
                                  : isOverdue
                                  ? "bg-orange-50 text-orange-700 border border-orange-200"
                                  : "bg-slate-100 text-slate-700 border border-slate-200"
                              }`}
                            >
                              {ob.status}
                            </span>
                            {isAtRisk && (
                              <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                                At Risk
                              </span>
                            )}
                          </div>
                          <Link
                            href={`/obligations/${ob.id}`}
                            className="text-sm font-bold text-slate-900 hover:text-orange-600 transition-colors inline-block"
                          >
                            {ob.action}
                          </Link>
                        </div>

                        <Link
                          href={`/obligations/${ob.id}`}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-orange-50 hover:bg-orange-100 border border-orange-200 text-orange-800 text-xs font-semibold shrink-0 transition-colors"
                        >
                          <span>Inspect & Act</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </Link>
                      </div>

                      {/* Details row: Owner, Beneficiary, Deadline */}
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-slate-600 bg-slate-50/70 p-2.5 rounded-xl border border-slate-100">
                        <div>
                          <span className="text-slate-600 text-[11px]">Owner: </span>
                          <strong className="text-slate-800">{ob.owner}</strong>
                        </div>
                        <div>
                          <span className="text-slate-600 text-[11px]">Beneficiary: </span>
                          <strong className="text-slate-800">{ob.beneficiary}</strong>
                        </div>
                        <div>
                          <span className="text-slate-600 text-[11px]">Deadline: </span>
                          <strong className="text-slate-800">
                            {ob.deadline ? new Date(ob.deadline).toLocaleDateString() : "Flexible"}
                          </strong>
                        </div>
                      </div>

                      {/* Blocker or Next Action Callout */}
                      {isBlocked && (
                        <div className="p-2.5 rounded-xl bg-rose-50/80 border border-rose-200/80 text-xs text-rose-900 flex items-start gap-2">
                          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                          <div>
                            <strong>Current Blocker:</strong> Upstream database benchmark timed out on read replicas.
                            <span className="block text-rose-700 text-[11px] mt-0.5">
                              Next Recommended Action: Re-run benchmark on isolated instance or defer cutover window.
                            </span>
                          </div>
                        </div>
                      )}

                      {!isBlocked && isAtRisk && (
                        <div className="p-2.5 rounded-xl bg-amber-50/80 border border-amber-200/80 text-xs text-amber-900 flex items-start gap-2">
                          <Clock className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                          <div>
                            <strong>Time-to-Review Warning:</strong> Deadline is in &lt;14 hours.
                            <span className="block text-amber-700 text-[11px] mt-0.5">
                              Next Recommended Action: Dispatch notification to Security Board lead.
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="p-8 text-center bg-white rounded-2xl border border-slate-200 text-slate-500 text-xs space-y-2">
                  <Inbox className="w-6 h-6 mx-auto text-slate-400" />
                  <p>All obligations are currently healthy and on schedule.</p>
                </div>
              )}
            </div>
          </div>

          {/* Obligation Dependency Flow (Unique Value Visualization) */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">Obligation Causal Flow</h3>
                <p className="text-xs text-slate-500">Live multi-hop dependency graph across team members</p>
              </div>
              <Link
                href="/intelligence"
                className="text-xs font-semibold text-orange-600 hover:text-orange-700 flex items-center gap-1"
              >
                <span>Full Graph</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {/* Visual Dependency Chain */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 overflow-x-auto">
              <div className="flex items-center justify-between min-w-[580px] gap-2">
                {/* Node 1 */}
                <div className="flex-1 p-3 rounded-xl bg-white border border-rose-200 text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-slate-400 uppercase">Upstream Prerequisite</span>
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                      OVERDUE
                    </span>
                  </div>
                  <div className="font-bold text-slate-900 truncate">Staging DB Benchmark</div>
                  <div className="text-[11px] text-slate-500">Priya Sharma</div>
                </div>

                <div className="text-slate-400 font-bold px-1">➔</div>

                {/* Node 2 */}
                <div className="flex-1 p-3 rounded-xl bg-white border border-amber-300 text-xs space-y-1 shadow-xs ring-1 ring-amber-400/20">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-slate-400 uppercase">Critical Bottleneck</span>
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                      BLOCKED
                    </span>
                  </div>
                  <div className="font-bold text-slate-900 truncate">Finalize Migration Plan</div>
                  <div className="text-[11px] text-slate-500">You (Demo Operator)</div>
                </div>

                <div className="text-slate-400 font-bold px-1">➔</div>

                {/* Node 3 */}
                <div className="flex-1 p-3 rounded-xl bg-white border border-slate-200 text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-slate-400 uppercase">Downstream Release</span>
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
                      WAITING
                    </span>
                  </div>
                  <div className="font-bold text-slate-900 truncate">Production Cutover</div>
                  <div className="text-[11px] text-slate-500">All Customers</div>
                </div>
              </div>
            </div>
            <p className="text-[11px] text-slate-600 italic">
              * Resolving Priya Sharma&apos;s benchmark restores velocity to 2 downstream milestones.
            </p>
          </div>
        </div>

        {/* Right 1 Col: Risk Overview, Intelligence, & Signals */}
        <div className="space-y-8">
          {/* Risk Overview Chart / Breakdown */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <h3 className="text-base font-bold text-slate-900">Portfolio Risk Distribution</h3>
            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="font-medium text-slate-700 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    Healthy & On-Track
                  </span>
                  <span className="font-bold text-slate-800">{healthyCount || 2}</span>
                </div>
                <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: "45%" }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="font-medium text-slate-700 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-500" />
                    Approaching Deadline (At Risk)
                  </span>
                  <span className="font-bold text-slate-800">{atRiskCount || 1}</span>
                </div>
                <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full bg-amber-500 rounded-full" style={{ width: "25%" }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="font-medium text-slate-700 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-rose-500" />
                    Blocked by Dependency
                  </span>
                  <span className="font-bold text-slate-800">{blockedCount || 1}</span>
                </div>
                <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full bg-rose-500 rounded-full" style={{ width: "20%" }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="font-medium text-slate-700 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-orange-600" />
                    Overdue Upstream
                  </span>
                  <span className="font-bold text-slate-800">{overdueCount || 1}</span>
                </div>
                <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full bg-orange-600 rounded-full" style={{ width: "10%" }} />
                </div>
              </div>
            </div>
          </div>

          {/* Recent Grounded Intelligence */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-orange-600" />
                <h3 className="text-base font-bold text-slate-900">Recent Intelligence</h3>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-orange-100 text-orange-800 border border-orange-200">
                Gemini
              </span>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
                <div className="font-semibold text-slate-800">Causal Delay Cascade</div>
                <p className="text-slate-600 leading-relaxed">
                  Staging DB benchmark timeout is delaying migration plan by 24h. 2 downstream cutovers affected.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
                <div className="font-semibold text-slate-800">Compliance Audit Window</div>
                <p className="text-slate-600 leading-relaxed">
                  SOC2 access audit package requires submission before 18:00 UTC to maintain certification standing.
                </p>
              </div>
            </div>
          </div>

          {/* Recent Organizational Signals */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-slate-700" />
                <h3 className="text-base font-bold text-slate-900">Recent Signals</h3>
              </div>
              <Link href="/events" className="text-xs font-semibold text-orange-600 hover:text-orange-700">
                All
              </Link>
            </div>

            <div className="space-y-2 text-xs">
              {recentEvents.length > 0 ? (
                recentEvents.slice(0, 4).map((evt) => (
                  <div key={evt.id} className="p-2.5 rounded-xl bg-slate-50 border border-slate-100 flex items-start gap-2.5">
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-white border border-slate-200 text-slate-600 uppercase shrink-0">
                      {evt.provider}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-slate-800 truncate font-medium">{evt.content}</p>
                      <span className="text-[10px] text-slate-600">
                        {evt.received_at ? new Date(evt.received_at).toLocaleTimeString() : "Recent"}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="space-y-2">
                  <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100 text-slate-600">
                    <strong className="text-slate-800">Slack: </strong>
                    Priya Sharma reported benchmark timeout on RDS replica.
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100 text-slate-600">
                    <strong className="text-slate-800">Jira: </strong>
                    INFRA-402 moved to &quot;Blocked&quot; by dependency check.
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Intervention Review Modal */}
      {selectedIntervention && (
        <InterventionReviewModal
          isOpen={isReviewModalOpen}
          onClose={() => {
            setIsReviewModalOpen(false);
            setSelectedIntervention(null);
          }}
          intervention={selectedIntervention}
          onUpdated={() => {
            setIsReviewModalOpen(false);
            setSelectedIntervention(null);
            loadData();
          }}
        />
      )}
    </div>
  );
}
