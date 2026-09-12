"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  AlertTriangle,
  RefreshCw,
  Clock,
  Sparkles,
  ArrowLeft,
  UserCheck,
  Zap,
  Layers,
  ChevronRight,
  GitCommit,
  Check,
  X,
  FileText,
  Send,
  RotateCcw,
  FileCheck,
  ExternalLink,
  ShieldCheck,
  Lock as LockIcon,
} from "lucide-react";
import { decisionApi, executionApi } from "@/lib/api/obligations";
import { HistoricalContextCard } from "@/components/memory/HistoricalContextCard";
import {
  DecisionPlan,
  ResolutionSimulationResponse,
  CandidateStrategyItem,
  ExecutionRecord,
  ExecutionReceipt,
} from "@/lib/types/obligation";

interface CriticalPathNode {
  obligation_id?: string;
  action?: string;
  owner?: string;
  status?: string;
  [key: string]: unknown;
}

interface UnblockedItem {
  owner?: string;
  action?: string;
  previous_status?: string;
  projected_status?: string;
  [key: string]: unknown;
}

export default function DecisionDetailPage() {
  const params = useParams();
  const obligationId = params?.id as string;

  const [plan, setPlan] = useState<DecisionPlan | null>(null);
  const [history, setHistory] = useState<DecisionPlan[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [rejectReason, setRejectReason] = useState<string>("");
  const [showRejectModal, setShowRejectModal] = useState<boolean>(false);
  const [approveNotes, setApproveNotes] = useState<string>("");
  const [showApproveModal, setShowApproveModal] = useState<boolean>(false);

  // Controlled Execution State (Phase 16)
  const [latestExecution, setLatestExecution] = useState<ExecutionRecord | null>(null);
  const [executionHistory, setExecutionHistory] = useState<ExecutionRecord[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>("mock");
  const [showExecuteModal, setShowExecuteModal] = useState<boolean>(false);
  const [showReceiptModal, setShowReceiptModal] = useState<boolean>(false);
  const [executionReceipt, setExecutionReceipt] = useState<ExecutionReceipt | null>(null);
  const [showCancelModal, setShowCancelModal] = useState<boolean>(false);
  const [cancelReason, setCancelReason] = useState<string>("");
  const [executionFeedback, setExecutionFeedback] = useState<string | null>(null);

  // Counterfactual Simulator State
  const [selectedStrategyId, setSelectedStrategyId] = useState<string>("primary");
  const [simulationResult, setSimulationResult] = useState<ResolutionSimulationResponse | null>(null);
  const [simulating, setSimulating] = useState<boolean>(false);

  const fetchPlanData = useCallback(async () => {
    if (!obligationId) return;
    setLoading(true);
    setError(null);
    try {
      const [planRes, historyRes] = await Promise.all([
        decisionApi.get(obligationId),
        decisionApi.getHistory(obligationId).catch(() => []),
      ]);
      setPlan(planRes);
      setHistory(historyRes);
      if (planRes.simulation_summary?.primary_simulation) {
        setSimulationResult(planRes.simulation_summary.primary_simulation as unknown as ResolutionSimulationResponse);
      }
      // Load execution history for this plan
      try {
        const execs = await executionApi.getHistory(planRes.id);
        setExecutionHistory(execs);
        if (execs.length > 0) {
          setLatestExecution(execs[0]);
        }
      } catch {
        // No execution records yet
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load decision plan.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [obligationId]);

  useEffect(() => {
    fetchPlanData();
  }, [fetchPlanData]);

  const handleApprove = async () => {
    if (!plan) return;
    setActionLoading(true);
    try {
      const updated = await decisionApi.approve(plan.id, {
        selected_strategy_id: selectedStrategyId,
        notes: approveNotes,
      });
      setPlan(updated);
      setShowApproveModal(false);
      await fetchPlanData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to approve plan.";
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleAuthorizeExecution = async () => {
    if (!plan) return;
    setActionLoading(true);
    setExecutionFeedback(null);
    try {
      const execRec = await executionApi.authorize(plan.id, {
        provider: selectedProvider,
      });
      setLatestExecution(execRec);
      setExecutionFeedback("Plan execution authorized successfully. Ready for provider dispatch.");
      await fetchPlanData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Execution authorization failed.";
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleExecuteAction = async () => {
    if (!plan) return;
    setActionLoading(true);
    setExecutionFeedback(null);
    try {
      const execRec = await executionApi.execute(plan.id, {
        provider: selectedProvider,
      });
      setLatestExecution(execRec);
      setExecutionFeedback(`Action executed through ${execRec.provider} (Ref: ${execRec.provider_execution_ref || "Generated"}).`);
      await fetchPlanData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Execution failed.";
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleViewReceipt = async (execId: string) => {
    try {
      const rct = await executionApi.getReceipt(execId);
      setExecutionReceipt(rct);
      setShowReceiptModal(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load receipt.";
      setError(msg);
    }
  };

  const handleCancelExec = async (execId: string) => {
    setActionLoading(true);
    try {
      const cancelled = await executionApi.cancel(execId, {
        reason: cancelReason || "Cancelled by operator",
      });
      setLatestExecution(cancelled);
      setShowCancelModal(false);
      await fetchPlanData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to cancel execution.";
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRetryExec = async (execId: string) => {
    setActionLoading(true);
    try {
      const retried = await executionApi.retry(execId);
      setLatestExecution(retried);
      await fetchPlanData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to retry execution.";
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!plan) return;
    setActionLoading(true);
    try {
      const updated = await decisionApi.reject(plan.id, {
        reason: rejectReason || "Rejected by operator.",
      });
      setPlan(updated);
      setShowRejectModal(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to reject plan.";
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRefresh = async () => {
    if (!plan) return;
    setActionLoading(true);
    try {
      const refreshed = await decisionApi.refresh(plan.id);
      setPlan(refreshed);
      await fetchPlanData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to refresh plan.";
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRunSimulation = async (strategyId: string) => {
    if (!plan) return;
    setSimulating(true);
    setSelectedStrategyId(strategyId);
    try {
      const sim = await decisionApi.simulate(plan.id, {
        strategy_id: strategyId === "primary" ? plan.recommended_actions?.strategy_id : strategyId,
      });
      setSimulationResult(sim);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Simulation failed.";
      setError(msg);
    } finally {
      setSimulating(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex flex-col items-center justify-center text-stone-600">
        <RefreshCw className="w-8 h-8 animate-spin mb-3 text-orange-600" />
        <p className="text-sm">Synthesizing Decision Plan & Multi-Source Intelligence...</p>
      </div>
    );
  }

  if (error && !plan) {
    return (
      <div className="min-h-screen bg-stone-50 text-stone-900 p-8">
        <div className="max-w-2xl mx-auto bg-white border border-stone-200 rounded-xl p-6 text-center shadow-sm">
          <AlertTriangle className="w-12 h-12 text-rose-600 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-stone-950 mb-2">Error Loading Decision Plan</h2>
          <p className="text-sm text-stone-600 mb-4">{error}</p>
          <Link
            href="/intelligence/decisions"
            className="inline-flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold rounded-lg text-sm transition shadow-sm"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Decision Center
          </Link>
        </div>
      </div>
    );
  }

  if (!plan) return null;

  const allStrategies: CandidateStrategyItem[] = [
    plan.recommended_actions,
    ...(plan.alternative_actions || []),
  ].filter(Boolean);

  const criticalPathNodes = (plan.critical_path || []) as unknown as CriticalPathNode[];

  return (
    <div className="min-h-screen bg-stone-50 text-stone-900 p-6 md:p-8">
      {/* Top Breadcrumb & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-stone-200/80 gap-4">
        <div>
          <Link
            href="/intelligence/decisions"
            className="inline-flex items-center gap-1.5 text-xs text-stone-600 hover:text-orange-600 transition mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Decision Queue
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-stone-950 flex items-center gap-2">
              <span>Decision Plan</span>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-orange-50 text-orange-700 border border-orange-200 font-mono">
                v{plan.plan_version}
              </span>
              <span
                className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase ${
                  plan.status === "APPROVED"
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : plan.status === "REJECTED"
                    ? "bg-rose-50 text-rose-700 border border-rose-200"
                    : "bg-amber-50 text-amber-700 border border-amber-200"
                }`}
              >
                {plan.status}
              </span>
            </h1>
          </div>
          <p className="text-sm text-stone-600 mt-1 max-w-2xl">
            {plan.primary_objective}
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {plan.status === "GENERATED" || plan.status === "PENDING_REVIEW" ? (
            <>
              <button
                onClick={() => setShowApproveModal(true)}
                disabled={actionLoading}
                className="flex items-center gap-1.5 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold text-sm rounded-lg transition shadow-sm"
              >
                <Check className="w-4 h-4" /> Authorize & Approve
              </button>
              <button
                onClick={() => setShowRejectModal(true)}
                disabled={actionLoading}
                className="flex items-center gap-1.5 px-4 py-2 bg-white hover:bg-rose-50 text-rose-700 border border-stone-200 font-semibold text-sm rounded-lg transition shadow-xs"
              >
                <X className="w-4 h-4" /> Reject Plan
              </button>
            </>
          ) : null}

          <button
            onClick={handleRefresh}
            disabled={actionLoading}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 text-sm font-medium rounded-lg transition shadow-xs"
            title="Recalculate and generate new plan version"
          >
            <RefreshCw className={`w-4 h-4 ${actionLoading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      {/* Staleness Banner */}
      {plan.is_stale && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded-xl text-sm my-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <span>This plan is marked <strong>STALE</strong> due to recent graph state or dependency changes.</span>
          </div>
          <button
            onClick={handleRefresh}
            className="text-xs bg-amber-100 hover:bg-amber-200 text-amber-900 px-3 py-1 rounded-md font-semibold transition"
          >
            Refresh to v{plan.plan_version + 1}
          </button>
        </div>
      )}

      {/* Grid Layout: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 my-6">
        {/* Left Column: Situation, Critical Path, Strategies, Simulator */}
        <div className="lg:col-span-2 space-y-6">
          {/* Situation & Target Obligation */}
          <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-600 mb-3 flex items-center gap-2">
              <Layers className="w-4 h-4 text-stone-500" /> Situation & Commitment State
            </h2>
            <div className="bg-stone-50 border border-stone-200 rounded-lg p-4">
              <div className="text-lg font-bold text-stone-950 mb-2">
                {plan.target_obligation_action}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs text-stone-600">
                <div>
                  <span className="text-stone-500 block">Owner</span>
                  <strong className="text-stone-800">{plan.target_obligation_owner || "Unassigned"}</strong>
                </div>
                <div>
                  <span className="text-stone-500 block">Status</span>
                  <span className="px-2 py-0.5 rounded bg-stone-200 text-stone-800 font-mono text-[11px]">
                    {plan.target_obligation_status}
                  </span>
                </div>
                <div>
                  <span className="text-stone-500 block">Risk Score</span>
                  <strong className={plan.overall_risk >= 0.5 ? "text-rose-700" : "text-stone-800"}>
                    {(plan.overall_risk * 100).toFixed(0)}%
                  </strong>
                </div>
                <div>
                  <span className="text-stone-500 block">Confidence</span>
                  <strong className="text-stone-800">
                    {(plan.decision_confidence * 100).toFixed(0)}%
                  </strong>
                </div>
              </div>
            </div>
          </div>

          {/* Critical Path Visualizer */}
          <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-600 mb-3 flex items-center gap-2">
              <GitCommit className="w-4 h-4 text-orange-600" /> Critical Dependency Path ({criticalPathNodes.length || 1} Hops)
            </h2>
            <div className="flex items-center gap-2 overflow-x-auto py-2">
              {criticalPathNodes.map((node, idx) => (
                <React.Fragment key={node.obligation_id || idx}>
                  <div className={`p-3 rounded-lg border text-xs min-w-[170px] ${
                    idx === 0
                      ? "bg-rose-50 border-rose-200 text-rose-800"
                      : idx === (criticalPathNodes.length - 1)
                      ? "bg-orange-50 border-orange-200 text-orange-800"
                      : "bg-stone-50 border-stone-200 text-stone-700"
                  }`}>
                    <div className="text-[10px] uppercase font-bold text-stone-500 mb-1 flex items-center justify-between">
                      <span>Hop {idx + 1}{idx === 0 ? " (Root)" : ""}</span>
                      <span className="font-mono text-[9px] text-stone-500">{node.status}</span>
                    </div>
                    <div className="font-semibold truncate text-stone-950" title={node.action}>
                      {node.action}
                    </div>
                    <div className="text-[11px] text-stone-600 mt-1">
                      Owner: <strong>{node.owner || "Unassigned"}</strong>
                    </div>
                  </div>
                  {idx < criticalPathNodes.length - 1 && (
                    <ChevronRight className="w-4 h-4 text-stone-400 flex-shrink-0" />
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Resolution Strategies & Ranking */}
          <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-600 mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-orange-600" /> Candidate Resolution Strategies ({allStrategies.length})
            </h2>

            <div className="space-y-3">
              {allStrategies.map((strat, idx) => (
                <div
                  key={strat.strategy_id || idx}
                  className={`p-4 rounded-xl border transition ${
                    strat.is_primary_recommendation
                      ? "bg-[#FFF7ED] border-orange-200 shadow-xs"
                      : "bg-white border-stone-200 hover:border-stone-300"
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      {strat.is_primary_recommendation && (
                        <span className="px-2 py-0.5 rounded-full bg-orange-100 text-orange-800 text-[10px] font-bold uppercase tracking-wider border border-orange-200">
                          Recommended
                        </span>
                      )}
                      <h3 className="font-bold text-stone-950 text-sm">
                        {strat.strategy_name}
                      </h3>
                    </div>

                    <div className="flex items-center gap-2">
                      <div className="text-xs text-stone-600 bg-white px-2.5 py-1 rounded border border-stone-200">
                        Score: <strong className="text-orange-700 font-mono">{strat.decision_score?.toFixed(2)}</strong>
                      </div>
                      <button
                        onClick={() => handleRunSimulation(strat.is_primary_recommendation ? "primary" : strat.strategy_id)}
                        disabled={simulating}
                        className="px-2.5 py-1 bg-white hover:bg-stone-50 text-stone-700 border border-stone-200 text-xs rounded-lg font-medium transition flex items-center gap-1 shadow-2xs"
                      >
                        <Zap className="w-3 h-3 text-orange-600" /> Simulate
                      </button>
                    </div>
                  </div>

                  <p className="text-xs text-stone-700 mb-2">
                    {strat.rationale}
                  </p>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-stone-600 bg-stone-50 p-2.5 rounded border border-stone-200">
                    <div>
                      <span className="text-stone-500 block">Target Owner</span>
                      <strong className="text-stone-800">{strat.target_owner}</strong>
                    </div>
                    <div>
                      <span className="text-stone-500 block">Expected Impact</span>
                      <span className="text-stone-800 font-medium">{strat.expected_impact}</span>
                    </div>
                    <div>
                      <span className="text-stone-500 block">Risk Reduction (Δ)</span>
                      <strong className="text-emerald-700 font-mono">{strat.risk_reduction?.toFixed(2)}</strong>
                    </div>
                    <div>
                      <span className="text-stone-500 block">Projected Unblocks</span>
                      <strong className="text-stone-900">{strat.projected_unblocks_count} obligation(s)</strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Interactive Counterfactual Simulator */}
          <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-600 flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-600" /> Counterfactual Resolution Simulator
              </h2>
              <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-800 text-[10px] font-bold tracking-wider border border-amber-200">
                ⚠️ SIMULATION — NO CHANGES HAVE BEEN MADE TO LIVE STATE
              </span>
            </div>

            {simulationResult ? (
              <div className="bg-stone-50 border border-stone-200 rounded-xl p-4">
                <div className="flex items-center justify-between text-xs text-stone-600 mb-3 pb-2 border-b border-stone-200">
                  <span>Action Simulated: <strong className="text-orange-700">{simulationResult.simulated_action}</strong></span>
                  <span>Risk Delta (Δ): <strong className="text-emerald-700 font-mono">{simulationResult.risk_delta?.toFixed(2)}</strong></span>
                </div>

                <p className="text-xs text-stone-700 mb-3">
                  {simulationResult.explanation}
                </p>

                {simulationResult.unblocked_obligations?.length > 0 && (
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-emerald-700 mb-2">
                      Projected Unblocked Obligations ({simulationResult.unblocked_obligations.length}):
                    </div>
                    <div className="space-y-1.5">
                      {((simulationResult.unblocked_obligations || []) as unknown as UnblockedItem[]).map((unb, idx) => (
                        <div key={idx} className="bg-emerald-50 border border-emerald-200 rounded px-3 py-1.5 text-xs text-emerald-800 flex items-center justify-between">
                          <span>{unb.owner}: {unb.action}</span>
                          <span className="font-mono text-[10px] font-semibold">{unb.previous_status || "BLOCKED"} ➔ {unb.projected_status || "CONFIRMED"}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-6 text-xs text-stone-500">
                Click &quot;Simulate&quot; on any strategy above to view counterfactual graph projections.
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Human Decisions, Explainability, Provenance & History */}
        <div className="space-y-6">
          {/* Phase 16: Controlled Decision Execution Panel */}
          <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm relative overflow-hidden">
            <div className="flex items-center justify-between gap-2 mb-3">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-700 flex items-center gap-2">
                <Send className="w-4 h-4 text-orange-600" /> Controlled Execution Layer
              </h2>
              {latestExecution && (
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                  latestExecution.status === "RESOLVED"
                    ? "bg-emerald-50 border border-emerald-200 text-emerald-700"
                    : latestExecution.status === "FAILED"
                    ? "bg-rose-50 border border-rose-200 text-rose-700"
                    : "bg-orange-50 border border-orange-200 text-orange-700 animate-pulse"
                }`}>
                  {latestExecution.status}
                </span>
              )}
            </div>

            {/* Provider Selector & Action Dispatch */}
            {plan.status === "APPROVED" || plan.status === "PARTIALLY_EXECUTED" ? (
              <div className="space-y-3">
                <div className="bg-stone-50 p-3 rounded-lg border border-stone-200 space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-stone-600">Target Provider</span>
                    <select
                      value={selectedProvider}
                      onChange={(e) => setSelectedProvider(e.target.value)}
                      disabled={actionLoading || Boolean(latestExecution && ["EXECUTING", "RESPONSE_PENDING"].includes(latestExecution.status))}
                      className="bg-white border border-stone-300 text-stone-800 text-xs rounded px-2 py-1 outline-none font-mono"
                    >
                      <option value="mock">Mock Simulator (Deterministic)</option>
                      <option value="slack">Slack Outbound Adapter</option>
                    </select>
                  </div>

                  <div className="flex items-center justify-between text-stone-600">
                    <span>Target Owner</span>
                    <strong className="text-stone-800">{plan.recommended_actions?.target_owner || plan.target_obligation_owner || "Unassigned"}</strong>
                  </div>

                  <div className="space-y-1 pt-1">
                    <span className="text-[11px] text-stone-500 block">Outbound Payload Snippet</span>
                    <p className="text-[11px] text-stone-700 font-mono bg-white p-2 rounded border border-stone-200">
                      {((plan.recommended_actions as unknown as Record<string, unknown>)?.action_summary as string) || plan.recommended_actions?.strategy_name || "Follow up on overdue obligation."}
                    </p>
                  </div>
                </div>

                {/* Execution Controls */}
                <div className="flex items-center gap-2">
                  {!latestExecution || ["PENDING_AUTHORIZATION", "AUTHORIZED"].includes(latestExecution.status) ? (
                    <button
                      onClick={handleExecuteAction}
                      disabled={actionLoading}
                      className="flex-1 py-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold text-xs rounded-lg transition shadow-sm flex items-center justify-center gap-1.5"
                    >
                      <Send className="w-3.5 h-3.5" /> Execute Outbound Action
                    </button>
                  ) : latestExecution.status === "FAILED" && latestExecution.retry_count < latestExecution.max_retries ? (
                    <button
                      onClick={() => handleRetryExec(latestExecution.id)}
                      disabled={actionLoading}
                      className="flex-1 py-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold text-xs rounded-lg transition flex items-center justify-center gap-1.5"
                    >
                      <RotateCcw className="w-3.5 h-3.5" /> Retry Execution ({latestExecution.retry_count}/{latestExecution.max_retries})
                    </button>
                  ) : null}

                  {latestExecution && (
                    <button
                      onClick={() => handleViewReceipt(latestExecution.id)}
                      className="px-3 py-2 bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 text-xs font-semibold rounded-lg transition flex items-center gap-1 shadow-2xs"
                    >
                      <FileCheck className="w-3.5 h-3.5 text-orange-600" /> Receipt
                    </button>
                  )}
                </div>

                {latestExecution && (
                  <div className="flex items-center justify-between text-[11px] text-stone-600 pt-1">
                    <span className="font-mono">Ref: {latestExecution.provider_execution_ref || "None"}</span>
                    <Link
                      href={`/intelligence/execution/${latestExecution.id}`}
                      className="text-orange-600 hover:underline flex items-center gap-1"
                    >
                      Full Details <ExternalLink className="w-3 h-3" />
                    </Link>
                  </div>
                )}

                {executionFeedback && (
                  <div className="p-2.5 rounded bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs">
                    {executionFeedback}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-stone-500 italic p-3 bg-stone-50 rounded-lg border border-stone-200">
                Decision Plan must be <strong>APPROVED</strong> by operator before controlled execution can be dispatched.
              </div>
            )}

            {/* Invariant Note */}
            <div className="mt-3 text-[10px] text-stone-500 leading-normal border-t border-stone-200 pt-2 flex items-center gap-1.5">
              <LockIcon className="w-3 h-3 text-stone-500 flex-shrink-0" />
              <span>Zero-mutation invariant: Outbound execution notifies recipient. Only verified evidence completes the obligation.</span>
            </div>
          </div>

          {/* Human Decisions Required */}
          <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-600 mb-3 flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-amber-600" /> Human Authorization Boundaries
            </h2>

            {plan.human_decisions_required?.length > 0 ? (
              <div className="space-y-2.5">
                {plan.human_decisions_required.map((dec, idx) => (
                  <div key={idx} className="bg-stone-50 border border-stone-200 rounded-lg p-3 text-xs">
                    <div className="flex items-center justify-between text-amber-700 font-semibold mb-1">
                      <span>{dec.decision_type}</span>
                      {dec.requires_admin && (
                        <span className="text-[10px] px-1.5 py-0.2 bg-amber-50 rounded text-amber-800 border border-amber-200">ADMIN</span>
                      )}
                    </div>
                    <p className="text-stone-700 mb-1.5">{dec.reason}</p>
                    <div className="text-[11px] text-stone-500">
                      Consequence: {dec.consequence_of_decision}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-stone-500 italic">No special authorization required.</div>
            )}
          </div>

          {/* Organizational Memory & Semantic Context */}
          <HistoricalContextCard obligationId={plan.target_obligation_id} />

          {/* Explainability Narrative */}
          <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-600 mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4 text-stone-500" /> Explainability Narrative
            </h2>
            <div className="bg-stone-50 border border-stone-200 rounded-lg p-3 text-xs text-stone-700 font-mono whitespace-pre-wrap leading-relaxed">
              {plan.explainability_narrative || "No narrative generated."}
            </div>
          </div>

          {/* Version History & Immutability */}
          <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-600 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-stone-500" /> Immutable Version History ({history.length})
            </h2>
            <div className="space-y-2">
              {history.map((h) => (
                <div
                  key={h.id}
                  className={`p-2.5 rounded-lg border text-xs flex items-center justify-between ${
                    h.id === plan.id
                      ? "bg-orange-50/50 border-orange-200 text-stone-900"
                      : "bg-stone-50 border-stone-200 text-stone-600"
                  }`}
                >
                  <div>
                    <div className="font-semibold text-stone-950">Plan Version v{h.plan_version}</div>
                    <div className="text-[10px] text-stone-500">
                      {new Date(h.generated_at).toLocaleString()}
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-stone-200 text-stone-700">
                    {h.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Approve Modal */}
      {showApproveModal && (
        <div className="fixed inset-0 bg-stone-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-stone-200 rounded-2xl p-6 max-w-md w-full shadow-2xl">
            <h3 className="text-base font-bold text-stone-900 mb-2">Authorize & Approve Decision Plan</h3>
            <p className="text-xs text-stone-600 mb-4">
              Authorizes the primary strategy ({plan.recommended_actions?.strategy_name}).
              This authorizes human execution without autonomous operational mutations.
            </p>
            <textarea
              value={approveNotes}
              onChange={(e) => setApproveNotes(e.target.value)}
              placeholder="Optional operator authorization notes..."
              className="w-full bg-stone-50 border border-stone-200 rounded-lg p-3 text-xs text-stone-800 focus:ring-2 focus:ring-orange-500 outline-none mb-4"
              rows={3}
            />
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setShowApproveModal(false)}
                className="px-3.5 py-2 text-xs font-medium text-stone-600 hover:text-stone-900 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleApprove}
                disabled={actionLoading}
                className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white font-medium text-xs rounded-lg transition shadow-sm disabled:opacity-50"
              >
                Confirm Approval
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-stone-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-stone-200 rounded-2xl p-6 max-w-md w-full shadow-2xl">
            <h3 className="text-base font-bold text-stone-900 mb-2">Reject Decision Plan</h3>
            <p className="text-xs text-stone-600 mb-4">
              Please provide a rationale for rejecting this decision plan.
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Reason for rejection..."
              className="w-full bg-stone-50 border border-stone-200 rounded-lg p-3 text-xs text-stone-800 focus:ring-2 focus:ring-rose-500 outline-none mb-4"
              rows={3}
            />
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setShowRejectModal(false)}
                className="px-3.5 py-2 text-xs font-medium text-stone-600 hover:text-stone-900 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={actionLoading}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white font-medium text-xs rounded-lg transition shadow-sm disabled:opacity-50"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Execution Receipt Modal (Phase 16) */}
      {showReceiptModal && executionReceipt && (
        <div className="fixed inset-0 bg-stone-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-stone-200 rounded-2xl p-6 max-w-lg w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-stone-200 pb-3">
              <div className="flex items-center gap-2">
                <FileCheck className="w-5 h-5 text-orange-600" />
                <h3 className="text-base font-bold text-stone-900">Immutable Execution Receipt</h3>
              </div>
              <button
                onClick={() => setShowReceiptModal(false)}
                className="p-1 rounded text-stone-400 hover:text-stone-700 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="bg-stone-50 p-3 rounded-lg border border-stone-200 space-y-1.5 font-mono">
                <div className="flex justify-between text-stone-600">
                  <span>Execution ID:</span>
                  <span className="text-stone-900 font-bold">{executionReceipt.execution_id}</span>
                </div>
                <div className="flex justify-between text-stone-600">
                  <span>Provider Reference:</span>
                  <span className="text-emerald-700 font-bold">{executionReceipt.provider_execution_ref || "None"}</span>
                </div>
                <div className="flex justify-between text-stone-600">
                  <span>Provider:</span>
                  <span className="text-stone-800 uppercase">{executionReceipt.provider}</span>
                </div>
                <div className="flex justify-between text-stone-600">
                  <span>Delivery Status:</span>
                  <span className="text-stone-800">{executionReceipt.delivery_status}</span>
                </div>
                <div className="flex justify-between text-stone-600">
                  <span>Authorized By:</span>
                  <span className="text-stone-800">{executionReceipt.authorized_by || "Operator"}</span>
                </div>
                <div className="flex justify-between text-stone-600">
                  <span>Executed At:</span>
                  <span className="text-stone-800">
                    {executionReceipt.executed_at ? new Date(executionReceipt.executed_at).toLocaleString() : "N/A"}
                  </span>
                </div>
                <div className="flex justify-between text-stone-600">
                  <span>Retry Count:</span>
                  <span className="text-stone-800">{executionReceipt.retry_count}</span>
                </div>
              </div>

              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-xs">
                <div className="font-semibold flex items-center gap-1.5 mb-1 text-emerald-900">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Redaction Verified
                </div>
                <p className="text-[11px] text-emerald-700">
                  All external credentials and sensitive tokens are strictly redacted from this receipt and audit logs.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-stone-200">
              <Link
                href={`/intelligence/execution/${executionReceipt.execution_id}`}
                className="px-3.5 py-1.5 bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold rounded-lg transition shadow-sm"
              >
                View Full Audit Details
              </Link>
              <button
                onClick={() => setShowReceiptModal(false)}
                className="px-3.5 py-1.5 bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 text-xs rounded-lg transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
