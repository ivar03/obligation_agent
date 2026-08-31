"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Brain,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  RefreshCw,
  Clock,
  Sparkles,
  Layers,
  Search,
  UserCheck,
} from "lucide-react";
import { decisionApi, obligationsApi } from "@/lib/api/obligations";
import { DecisionPlanSummary, Obligation } from "@/lib/types/obligation";

export default function DecisionCenterPage() {
  const [plans, setPlans] = useState<DecisionPlanSummary[]>([]);
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFilter, setSelectedFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [selectedObIdToGenerate, setSelectedObIdToGenerate] = useState<string>("");

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [queueRes, obsRes] = await Promise.all([
        decisionApi.getQueue(),
        obligationsApi.list({ limit: 100 }),
      ]);
      setPlans(queueRes.items || []);
      setObligations(obsRes.items || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load decision queue.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleGenerate = async (obligationId: string) => {
    if (!obligationId) return;
    setIsGenerating(true);
    try {
      await decisionApi.generate(obligationId);
      await fetchData();
      setSelectedObIdToGenerate("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate decision plan.";
      setError(msg);
    } finally {
      setIsGenerating(false);
    }
  };

  const filteredPlans = plans.filter((plan) => {
    const matchesSearch =
      plan.target_obligation_action.toLowerCase().includes(searchQuery.toLowerCase()) ||
      plan.target_obligation_owner.toLowerCase().includes(searchQuery.toLowerCase()) ||
      plan.primary_objective.toLowerCase().includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;

    if (selectedFilter === "CRITICAL") {
      return plan.overall_urgency === "CRITICAL" || plan.overall_risk >= 0.6;
    }
    if (selectedFilter === "PENDING_REVIEW") {
      return plan.status === "GENERATED" || plan.status === "PENDING_REVIEW";
    }
    if (selectedFilter === "APPROVED") {
      return plan.status === "APPROVED";
    }
    if (selectedFilter === "STALE") {
      return plan.is_stale;
    }
    return true;
  });

  const criticalCount = plans.filter((p) => p.overall_urgency === "CRITICAL" || p.overall_risk >= 0.6).length;
  const pendingReviewCount = plans.filter((p) => p.status === "GENERATED" || p.status === "PENDING_REVIEW").length;
  const approvedCount = plans.filter((p) => p.status === "APPROVED").length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-800/80 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400">
              <Brain className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Decision Center</h1>
              <p className="text-sm text-slate-400">
                Multi-Source Intelligence Orchestrator & Action Authorization Layer
              </p>
            </div>
          </div>
        </div>

        {/* Generate / Refresh controls */}
        <div className="flex items-center gap-3">
          <select
            value={selectedObIdToGenerate}
            onChange={(e) => setSelectedObIdToGenerate(e.target.value)}
            className="bg-slate-900 border border-slate-700/80 text-sm text-slate-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-violet-500 outline-none max-w-[240px]"
          >
            <option value="">Select commitment to plan...</option>
            {obligations.map((ob) => (
              <option key={ob.id} value={ob.id}>
                {ob.owner ? `${ob.owner}: ` : ""}{ob.action.slice(0, 35)}
              </option>
            ))}
          </select>
          <button
            onClick={() => handleGenerate(selectedObIdToGenerate)}
            disabled={!selectedObIdToGenerate || isGenerating}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:opacity-50 text-white font-medium text-sm rounded-lg transition shadow-lg shadow-violet-950/40"
          >
            {isGenerating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            Synthesize Plan
          </button>
          <button
            onClick={fetchData}
            className="p-2 bg-slate-900 border border-slate-800 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
            title="Refresh queue"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 my-6">
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-xl p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Active Decision Plans</span>
            <Layers className="w-4 h-4 text-violet-400" />
          </div>
          <div className="text-2xl font-bold text-white">{plans.length}</div>
          <div className="text-xs text-slate-500 mt-1">Workspace-wide synthesized plans</div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-xl p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Critical & High Risk</span>
            <ShieldAlert className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-rose-400">{criticalCount}</div>
          <div className="text-xs text-slate-500 mt-1">Requires immediate human resolution</div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-xl p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Awaiting Authorization</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400">{pendingReviewCount}</div>
          <div className="text-xs text-slate-500 mt-1">Recommended strategy ready for review</div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-xl p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Authorized & Approved</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400">{approvedCount}</div>
          <div className="text-xs text-slate-500 mt-1">Human operator approved</div>
        </div>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-2 overflow-x-auto w-full md:w-auto pb-2 md:pb-0">
          {[
            { id: "ALL", label: "All Decisions", count: plans.length },
            { id: "CRITICAL", label: "Critical Risk", count: criticalCount },
            { id: "PENDING_REVIEW", label: "Pending Review", count: pendingReviewCount },
            { id: "APPROVED", label: "Approved", count: approvedCount },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSelectedFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 whitespace-nowrap ${
                selectedFilter === tab.id
                  ? "bg-violet-600 text-white shadow-sm"
                  : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              {tab.label}
              <span className="px-1.5 py-0.2 text-[10px] rounded-full bg-black/30 font-semibold">
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        <div className="relative w-full md:w-64">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search decisions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 focus:ring-2 focus:ring-violet-500 outline-none placeholder:text-slate-500"
          />
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-rose-500/10 border border-rose-500/20 text-rose-300 px-4 py-3 rounded-lg text-sm mb-6 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-200 text-xs font-semibold">
            Dismiss
          </button>
        </div>
      )}

      {/* Decision Queue Grid */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-400">
          <RefreshCw className="w-8 h-8 animate-spin mb-3 text-violet-400" />
          <p className="text-sm">Synthesizing multi-source decision queue...</p>
        </div>
      ) : filteredPlans.length === 0 ? (
        <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-12 text-center">
          <Brain className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-white">No Decision Plans Found</h3>
          <p className="text-sm text-slate-400 max-w-md mx-auto mt-1 mb-4">
            Select an active obligation above and click &quot;Synthesize Plan&quot; to generate an intelligent resolution decision.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredPlans.map((plan) => (
            <div
              key={plan.id}
              className="bg-slate-900/90 border border-slate-800/80 hover:border-violet-500/40 rounded-xl p-5 flex flex-col justify-between transition-all duration-200 shadow-sm hover:shadow-violet-950/20 backdrop-blur-sm group"
            >
              <div>
                {/* Status & Urgency Header */}
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                      plan.overall_urgency === "CRITICAL"
                        ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                        : plan.overall_urgency === "HIGH"
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                        : "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                    }`}
                  >
                    {plan.overall_urgency} URGENCY
                  </span>

                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-slate-400 font-mono">v{plan.plan_version}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        plan.status === "APPROVED"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : plan.status === "REJECTED"
                          ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                          : "bg-violet-500/10 text-violet-400 border border-violet-500/20"
                      }`}
                    >
                      {plan.status}
                    </span>
                  </div>
                </div>

                {/* Target Obligation */}
                <h3 className="font-semibold text-white text-base group-hover:text-violet-300 transition-colors line-clamp-2 mb-1">
                  {plan.target_obligation_action}
                </h3>
                <div className="flex items-center gap-2 text-xs text-slate-400 mb-3">
                  <span>Owner: <strong className="text-slate-200">{plan.target_obligation_owner}</strong></span>
                  <span>•</span>
                  <span>Status: <span className="text-slate-300 font-mono text-[11px]">{plan.target_obligation_status}</span></span>
                </div>

                {/* Primary Strategy Recommendation */}
                <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-3 mb-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-violet-400 flex items-center gap-1 mb-1">
                    <Sparkles className="w-3 h-3" /> Recommended Strategy
                  </div>
                  <div className="text-xs font-medium text-slate-200 mb-0.5">
                    {plan.recommended_strategy_name}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Target: <strong className="text-slate-300">{plan.target_owner}</strong>
                  </div>
                </div>

                {/* Risk & Confidence metrics */}
                <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 mb-3">
                  <div className="bg-slate-950/40 rounded px-2.5 py-1.5 border border-slate-800/60">
                    <span className="text-[10px] text-slate-500 uppercase block">Risk Score</span>
                    <strong className={plan.overall_risk >= 0.5 ? "text-rose-400" : "text-slate-200"}>
                      {(plan.overall_risk * 100).toFixed(0)}%
                    </strong>
                  </div>
                  <div className="bg-slate-950/40 rounded px-2.5 py-1.5 border border-slate-800/60">
                    <span className="text-[10px] text-slate-500 uppercase block">Confidence</span>
                    <strong className="text-slate-200">
                      {(plan.decision_confidence * 100).toFixed(0)}%
                    </strong>
                  </div>
                </div>

                {/* Human Decision Badge */}
                {plan.human_decisions_count > 0 && (
                  <div className="flex items-center gap-1.5 text-xs text-amber-400/90 mb-2">
                    <UserCheck className="w-3.5 h-3.5" />
                    <span>{plan.human_decisions_count} human authorization point(s)</span>
                  </div>
                )}
              </div>

              {/* Action Button */}
              <div className="pt-3 border-t border-slate-800/80 mt-2 flex items-center justify-between">
                <span className="text-[10px] text-slate-500 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {new Date(plan.generated_at).toLocaleDateString()}
                </span>
                <Link
                  href={`/intelligence/decisions/${plan.target_obligation_id}`}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-violet-400 hover:text-violet-300 transition"
                >
                  Review Decision Plan <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
