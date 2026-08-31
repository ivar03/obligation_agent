"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Brain,
  AlertTriangle,
  Users,
  BarChart3,
  ShieldCheck,
  RefreshCw,
  Sliders,
  Layers,
  HelpCircle,
  Sparkles,
  Zap,
  GitBranch,
  Network,
  Compass,
  Play,
  ArrowRight,
  Crosshair,
  Route,
} from "lucide-react";
import {
  IntelligenceOverviewResponse,
  HistoricalPatternsResponse,
  OwnerPatternMetric,
  PredictionEvaluationMetrics,
  AdaptiveFeaturePatternsResponse,
  RootCauseAnalysisResponse,
  ImpactAnalysisResponse,
  CriticalPathResponse,
  ResolutionPlanResponse,
  ResolutionSimulationResponse,
  BottleneckAnalysisResponse,
  RiskConcentrationResponse,
  SimulationActionType,
  MemoryRetrievalItem,
  HistoricalPatternItem,
} from "@/lib/types/obligation";
import { intelligenceApi, memoryApi } from "@/lib/api/obligations";
import { PredictionCard } from "@/components/intelligence/PredictionCard";
import { LLMIntelligencePanel } from "@/components/intelligence/LLMIntelligencePanel";

export default function IntelligencePage() {
  const [activeTab, setActiveTab] = useState<
    "FORECASTS" | "ROOT_CAUSE" | "PATTERNS" | "OWNERS" | "CALIBRATION" | "ADAPTIVE" | "MEMORY" | "LLM"
  >("FORECASTS");
  const [overview, setOverview] = useState<IntelligenceOverviewResponse | null>(null);
  const [patterns, setPatterns] = useState<HistoricalPatternsResponse | null>(null);
  const [owners, setOwners] = useState<OwnerPatternMetric[]>([]);
  const [evaluation, setEvaluation] = useState<PredictionEvaluationMetrics | null>(null);
  const [featurePatterns, setFeaturePatterns] = useState<AdaptiveFeaturePatternsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterRisk, setFilterRisk] = useState<"ALL" | "HIGH" | "MODERATE">("ALL");

  // Phase 14 State
  const [bottlenecks, setBottlenecks] = useState<BottleneckAnalysisResponse | null>(null);
  const [riskConcentrations, setRiskConcentrations] = useState<RiskConcentrationResponse | null>(null);
  const [selectedObligationId, setSelectedObligationId] = useState<string>("");
  const [rootCauseData, setRootCauseData] = useState<RootCauseAnalysisResponse | null>(null);
  const [impactData, setImpactData] = useState<ImpactAnalysisResponse | null>(null);
  const [criticalPathData, setCriticalPathData] = useState<CriticalPathResponse | null>(null);
  const [resolutionPlan, setResolutionPlan] = useState<ResolutionPlanResponse | null>(null);
  const [simulationResult, setSimulationResult] = useState<ResolutionSimulationResponse | null>(null);
  const [simAction, setSimAction] = useState<SimulationActionType>("COMPLETE_OBLIGATION");
  const [phase14Loading, setPhase14Loading] = useState(false);
  const [simulating, setSimulating] = useState(false);

  // Phase 16 State
  const [memorySearchQuery, setMemorySearchQuery] = useState("");
  const [memoryTypeFilter, setMemoryTypeFilter] = useState<string>("");
  const [memoriesList, setMemoriesList] = useState<MemoryRetrievalItem[]>([]);
  const [workspacePatterns, setWorkspacePatterns] = useState<HistoricalPatternItem[]>([]);
  const [memoryLoading, setMemoryLoading] = useState(false);

  const fetchMemories = useCallback(async () => {
    setMemoryLoading(true);
    try {
      const [mems, pats] = await Promise.all([
        memoryApi.search({
          query: memorySearchQuery || undefined,
          memory_type: memoryTypeFilter || undefined,
          min_relevance: 0.0,
          limit: 50,
        }).catch(() => []),
        memoryApi.getPatterns().catch(() => []),
      ]);
      setMemoriesList(mems);
      setWorkspacePatterns(pats);
    } catch (err) {
      console.error("Failed to fetch memories", err);
    } finally {
      setMemoryLoading(false);
    }
  }, [memorySearchQuery, memoryTypeFilter]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [ovData, patData, ownData, evalData, , featData, btnkData, concData] =
        await Promise.all([
          intelligenceApi.getOverview().catch(() => null),
          intelligenceApi.getPatterns().catch(() => null),
          intelligenceApi.getOwners().catch(() => []),
          intelligenceApi.getEvaluation().catch(() => null),
          intelligenceApi.getAdaptiveOverview().catch(() => null),
          intelligenceApi.getAdaptiveFeatures().catch(() => null),
          intelligenceApi.getBottlenecks().catch(() => null),
          intelligenceApi.getRiskConcentrations().catch(() => null),
        ]);
      setOverview(ovData);
      setPatterns(patData);
      setOwners(ownData);
      setEvaluation(evalData);
      setFeaturePatterns(featData);
      setBottlenecks(btnkData);
      setRiskConcentrations(concData);

      if (ovData?.predictions && ovData.predictions.length > 0 && !selectedObligationId) {
        setSelectedObligationId(ovData.predictions[0].obligation_id);
      }
    } catch (err) {
      console.error("Failed to load intelligence data", err);
    } finally {
      setLoading(false);
    }
  }, [selectedObligationId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Fetch Phase 14 analysis when selected obligation changes
  useEffect(() => {
    if (!selectedObligationId) return;
    const fetchObligationAnalysis = async () => {
      setPhase14Loading(true);
      setSimulationResult(null);
      try {
        const [rc, imp, cp, plan] = await Promise.all([
          intelligenceApi.getRootCause(selectedObligationId).catch(() => null),
          intelligenceApi.getImpact(selectedObligationId).catch(() => null),
          intelligenceApi.getCriticalPath(selectedObligationId).catch(() => null),
          intelligenceApi.getResolutionPlan(selectedObligationId).catch(() => null),
        ]);
        setRootCauseData(rc);
        setImpactData(imp);
        setCriticalPathData(cp);
        setResolutionPlan(plan);
      } catch (err) {
        console.error("Failed to load root cause & impact analysis", err);
      } finally {
        setPhase14Loading(false);
      }
    };
    fetchObligationAnalysis();
  }, [selectedObligationId]);

  const runSimulation = async () => {
    if (!selectedObligationId) return;
    setSimulating(true);
    try {
      const res = await intelligenceApi.simulateResolution(selectedObligationId, {
        action: simAction,
        target_obligation_id: selectedObligationId,
      });
      setSimulationResult(res);
    } catch (err) {
      console.error("Simulation failed", err);
    } finally {
      setSimulating(false);
    }
  };

  useEffect(() => {
    if (activeTab === "MEMORY") {
      fetchMemories();
    }
  }, [activeTab, fetchMemories]);

  const filteredPredictions =
    overview?.predictions.filter((p) => {
      if (filterRisk === "HIGH") return p.failure_probability >= 0.55;
      if (filterRisk === "MODERATE")
        return p.failure_probability >= 0.35 && p.failure_probability < 0.55;
      return true;
    }) || [];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 text-indigo-400 font-semibold text-xs tracking-wider uppercase">
            <Brain className="w-4 h-4" />
            Phase 14 Root-Cause Analysis & Resolution Planning
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-100 mt-1">
            Obligation Intelligence & Graph Reasoning
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Causal root-cause deduction, blast radius impact mapping, critical-path analysis, and counterfactual simulation.
          </p>
        </div>

        <button
          onClick={fetchData}
          disabled={loading}
          className="self-start sm:self-auto inline-flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-sm font-medium transition-colors border border-slate-700"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh Model
        </button>
      </div>

      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Active Forecasts
            </span>
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-3xl font-bold text-slate-100 font-mono mt-2">
            {overview?.active_obligations_evaluated ?? 0}
          </div>
          <div className="text-xs text-slate-500 mt-1">Obligations actively monitored</div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-400 uppercase tracking-wider">
              Systemic Bottlenecks
            </span>
            <Network className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-3xl font-bold text-rose-400 font-mono mt-2">
            {bottlenecks?.total_bottlenecks ?? 0}
          </div>
          <div className="text-xs text-slate-500 mt-1">Structural dependency choke points</div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">
              Risk Concentrations
            </span>
            <Compass className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-bold text-amber-400 font-mono mt-2">
            {riskConcentrations?.total_concentrations ?? 0}
          </div>
          <div className="text-xs text-slate-500 mt-1">Multi-owner impact clusters</div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
              Intervention Needed
            </span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-bold text-emerald-400 font-mono mt-2">
            {overview?.likely_to_require_intervention_count ?? 0}
          </div>
          <div className="text-xs text-slate-500 mt-1">Follow-up likelihood &ge; 50%</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-800 flex items-center justify-between overflow-x-auto">
        <div className="flex space-x-2 min-w-max">
          <button
            onClick={() => setActiveTab("FORECASTS")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "FORECASTS"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Brain className="w-4 h-4" />
            Active Forecasts ({overview?.predictions.length ?? 0})
          </button>

          <button
            onClick={() => setActiveTab("ROOT_CAUSE")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "ROOT_CAUSE"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <GitBranch className="w-4 h-4" />
            Root Cause & Impact (Phase 14)
          </button>

          <button
            onClick={() => setActiveTab("PATTERNS")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "PATTERNS"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            Historical Patterns
          </button>

          <button
            onClick={() => setActiveTab("OWNERS")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "OWNERS"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Users className="w-4 h-4" />
            Owner Analytics ({owners.length})
          </button>

          <button
            onClick={() => setActiveTab("CALIBRATION")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "CALIBRATION"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Sliders className="w-4 h-4" />
            Model Calibration
          </button>

          <button
            onClick={() => setActiveTab("ADAPTIVE")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "ADAPTIVE"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Sparkles className="w-4 h-4" />
            Adaptive Intelligence
          </button>

          <button
            onClick={() => setActiveTab("MEMORY")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "MEMORY"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Brain className="w-4 h-4 text-purple-400" />
            Organizational Memory
          </button>

          <button
            onClick={() => setActiveTab("LLM")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "LLM"
                ? "border-cyan-500 text-cyan-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Sparkles className="w-4 h-4 text-cyan-400" />
            LLM Intelligence
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* PHASE 14: ROOT CAUSE & IMPACT TAB                                          */}
      {/* ========================================================================= */}
      {activeTab === "ROOT_CAUSE" && (
        <div className="space-y-8">
          {/* Obligation Selector */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  <Crosshair className="w-4 h-4 text-indigo-400" />
                  <span>Select Obligation for Causal Deep Dive</span>
                </h3>
                <p className="text-xs text-slate-400">
                  Inspect upstream root causes, blast radius impact, critical paths, and test resolution simulations.
                </p>
              </div>

              {overview?.predictions && overview.predictions.length > 0 && (
                <div className="w-full sm:w-80">
                  <select
                    value={selectedObligationId}
                    onChange={(e) => setSelectedObligationId(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                  >
                    {overview.predictions.map((p) => (
                      <option key={p.obligation_id} value={p.obligation_id}>
                        {p.owner}: {p.action} ({Math.round(p.failure_probability * 100)}% risk)
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>

          {phase14Loading ? (
            <div className="py-12 flex justify-center items-center text-slate-400 text-sm">
              <RefreshCw className="w-5 h-5 animate-spin mr-2" />
              Computing causal reasoning and dependency topology...
            </div>
          ) : rootCauseData ? (
            <div className="space-y-8">
              {/* Section: WHY IS THIS AT RISK? (Root Cause Explorer) */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-4">
                  <div>
                    <span className="text-[11px] font-mono text-indigo-400 uppercase tracking-wider">
                      Causal Attribution Engine
                    </span>
                    <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2 mt-0.5">
                      <Brain className="w-5 h-5 text-indigo-400" />
                      <span>Why is this commitment at risk?</span>
                    </h2>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2.5 py-1 rounded-full text-xs font-bold font-mono border ${
                        rootCauseData.confidence_level === "HIGH"
                          ? "bg-emerald-950/60 text-emerald-300 border-emerald-500/30"
                          : rootCauseData.confidence_level === "MEDIUM"
                          ? "bg-amber-950/60 text-amber-300 border-amber-500/30"
                          : "bg-slate-800 text-slate-400 border-slate-700"
                      }`}
                    >
                      Confidence: {Math.round(rootCauseData.confidence * 100)}% (
                      {rootCauseData.confidence_level})
                    </span>
                  </div>
                </div>

                {/* Primary Cause Hero Card */}
                <div className="p-5 bg-indigo-950/20 border border-indigo-500/30 rounded-xl space-y-3">
                  <div className="text-xs font-semibold text-indigo-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5" />
                    <span>Primary Root Cause & Explanation</span>
                  </div>
                  <div className="text-base font-bold text-slate-100">
                    {rootCauseData.primary_root_cause}
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {rootCauseData.overall_explanation}
                  </p>

                  {rootCauseData.dependency_path && rootCauseData.dependency_path.length > 1 && (
                    <div className="pt-2 border-t border-indigo-500/20 flex items-center gap-2 text-xs font-mono text-indigo-300">
                      <span className="text-slate-400 font-sans">Causal Path:</span>
                      {rootCauseData.dependency_path.map((nodeId, idx) => (
                        <React.Fragment key={idx}>
                          <span className="px-2 py-0.5 bg-slate-900 rounded border border-slate-700 text-[11px]">
                            {nodeId.substring(0, 8)}...
                          </span>
                          {idx < rootCauseData.dependency_path.length - 1 && (
                            <ArrowRight className="w-3 h-3 text-indigo-400" />
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                  )}
                </div>

                {/* Breakdown Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Upstream & Direct Causes */}
                  <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-3">
                    <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-rose-400" />
                      <span>Direct & Upstream Causes ({rootCauseData.direct_causes.length + rootCauseData.upstream_causes.length})</span>
                    </h4>

                    {[...rootCauseData.upstream_causes, ...rootCauseData.direct_causes].length === 0 ? (
                      <div className="text-xs text-slate-500 italic">No direct blockers detected.</div>
                    ) : (
                      <div className="space-y-2">
                        {[...rootCauseData.upstream_causes, ...rootCauseData.direct_causes].map((c, i) => (
                          <div
                            key={i}
                            className="p-2.5 bg-slate-900/80 rounded-lg border border-slate-800/80 text-xs space-y-1"
                          >
                            <div className="flex items-center justify-between">
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-950/60 text-rose-300 border border-rose-500/30">
                                {c.factor_type}
                              </span>
                              <span className="text-slate-400 text-[11px]">
                                {c.target_owner ? `Owner: ${c.target_owner}` : ""}
                              </span>
                            </div>
                            <div className="text-slate-200">{c.description}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Contributing Factors & Uncertainties */}
                  <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-3">
                    <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                      <HelpCircle className="w-4 h-4 text-amber-400" />
                      <span>Contributing Factors & Context ({rootCauseData.contributing_factors.length})</span>
                    </h4>

                    {rootCauseData.contributing_factors.length === 0 ? (
                      <div className="text-xs text-slate-500 italic">No adverse contributing factors.</div>
                    ) : (
                      <div className="space-y-2">
                        {rootCauseData.contributing_factors.map((cf, i) => (
                          <div
                            key={i}
                            className="p-2.5 bg-slate-900/80 rounded-lg border border-slate-800/80 text-xs space-y-1"
                          >
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-950/60 text-amber-300 border border-amber-500/30">
                              CONTRIBUTING_FACTOR
                            </span>
                            <div className="text-slate-200">{cf.description}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Section: IMPACT ANALYSIS & BLAST RADIUS */}
              {impactData && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
                  <div>
                    <span className="text-[11px] font-mono text-indigo-400 uppercase tracking-wider">
                      Blast Radius Assessment
                    </span>
                    <h3 className="text-base font-bold text-slate-100 flex items-center gap-2 mt-0.5">
                      <Compass className="w-4 h-4 text-indigo-400" />
                      <span>Downstream Blast Radius & Impact Score</span>
                    </h3>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800">
                      <div className="text-xs text-slate-400">Impact Score</div>
                      <div className="text-2xl font-bold font-mono text-indigo-400 mt-1">
                        {impactData.impact_score.toFixed(2)}
                      </div>
                      <div className="text-[10px] text-slate-500 uppercase">{impactData.impact_level} Impact</div>
                    </div>

                    <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800">
                      <div className="text-xs text-slate-400">Total Downstream</div>
                      <div className="text-2xl font-bold font-mono text-slate-100 mt-1">
                        {impactData.total_downstream_dependents_count}
                      </div>
                      <div className="text-[10px] text-slate-500">Dependents affected</div>
                    </div>

                    <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800">
                      <div className="text-xs text-slate-400">Max Dependency Depth</div>
                      <div className="text-2xl font-bold font-mono text-slate-100 mt-1">
                        {impactData.maximum_dependency_depth}
                      </div>
                      <div className="text-[10px] text-slate-500">Graph hops</div>
                    </div>

                    <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800">
                      <div className="text-xs text-slate-400">Affected Owners</div>
                      <div className="text-2xl font-bold font-mono text-slate-100 mt-1">
                        {impactData.affected_owners.length}
                      </div>
                      <div className="text-[10px] text-slate-500">Team members involved</div>
                    </div>
                  </div>

                  {/* Downstream Items list */}
                  {impactData.downstream_items && impactData.downstream_items.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-slate-300">Affected Downstream Commitments:</div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {impactData.downstream_items.map((item: { action?: string; owner?: string; hop_distance?: number; status?: string }, idx) => (
                          <div
                            key={idx}
                            className="p-3 bg-slate-950/80 rounded-lg border border-slate-800 flex items-center justify-between text-xs"
                          >
                            <div>
                              <div className="font-semibold text-slate-200">{item.action}</div>
                              <div className="text-[11px] text-slate-400">Owner: {item.owner} ({item.hop_distance} hop away)</div>
                            </div>
                            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-300 border border-slate-700">
                              {item.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Section: CRITICAL PATH VISUALIZATION */}
              {criticalPathData && criticalPathData.path_details && criticalPathData.path_details.length > 0 && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
                  <div>
                    <span className="text-[11px] font-mono text-indigo-400 uppercase tracking-wider">
                      DAG Dependency Chain
                    </span>
                    <h3 className="text-base font-bold text-slate-100 flex items-center gap-2 mt-0.5">
                      <Route className="w-4 h-4 text-indigo-400" />
                      <span>Critical Path Visualizer (Length: {criticalPathData.critical_path_length})</span>
                    </h3>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed">
                    {criticalPathData.explanation}
                  </p>

                  <div className="space-y-3 pt-2">
                    {criticalPathData.path_details.map((node, idx) => (
                      <div
                        key={node.obligation_id}
                        className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                          node.is_root_blocker
                            ? "bg-rose-950/20 border-rose-500/40"
                            : "bg-slate-950/60 border-slate-800"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-mono font-bold text-slate-200">
                            {idx + 1}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-bold text-slate-100">{node.action}</span>
                              {node.is_root_blocker && (
                                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-950 text-rose-300 border border-rose-500/40">
                                  ROOT BLOCKER
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-slate-400">Owner: {node.owner}</div>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 self-end sm:self-auto font-mono text-xs">
                          <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300">
                            {node.status}
                          </span>
                          <span className="text-slate-400">
                            Risk: {Math.round(node.risk_score * 100)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Section: RESOLUTION PLAN & INTERACTIVE SIMULATOR */}
              {resolutionPlan && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
                  <div>
                    <span className="text-[11px] font-mono text-indigo-400 uppercase tracking-wider">
                      Upstream-First Action Planner
                    </span>
                    <h3 className="text-base font-bold text-slate-100 flex items-center gap-2 mt-0.5">
                      <Play className="w-4 h-4 text-emerald-400" />
                      <span>Highest-Leverage Resolution Recommendation</span>
                    </h3>
                  </div>

                  <div className="p-5 bg-emerald-950/20 border border-emerald-500/30 rounded-xl space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="px-2.5 py-1 rounded text-xs font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-500/40">
                        STRATEGY: {resolutionPlan.strategy}
                      </span>
                      <span className="text-xs text-slate-400 font-mono">
                        Target Owner: {resolutionPlan.target_owner}
                      </span>
                    </div>

                    <div className="text-sm font-bold text-slate-100">
                      Target Action: {resolutionPlan.target_action}
                    </div>

                    <p className="text-xs text-slate-300 leading-relaxed">
                      {resolutionPlan.rationale}
                    </p>

                    <div className="pt-2 border-t border-emerald-500/20 text-xs text-emerald-300 font-medium">
                      Expected Impact: {resolutionPlan.expected_impact}
                    </div>
                  </div>

                  {/* Simulator Control */}
                  <div className="p-5 bg-slate-950/80 rounded-xl border border-slate-800 space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div>
                        <div className="text-sm font-bold text-slate-100 flex items-center gap-2">
                          <Play className="w-4 h-4 text-indigo-400" />
                          <span>Counterfactual Resolution Simulator</span>
                        </div>
                        <div className="text-xs text-slate-400 mt-0.5">
                          Evaluate in-memory cascade unblocking without modifying the live database.
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <select
                          value={simAction}
                          onChange={(e) => setSimAction(e.target.value as SimulationActionType)}
                          className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
                        >
                          <option value="COMPLETE_OBLIGATION">Simulate: Complete Obligation</option>
                          <option value="RESOLVE_BLOCKER">Simulate: Resolve Blocker</option>
                          <option value="ASSIGN_OWNER">Simulate: Assign Owner</option>
                          <option value="CONFIRM_EVIDENCE">Simulate: Confirm Evidence</option>
                          <option value="REMOVE_DEPENDENCY">Simulate: Decouple Dependency</option>
                        </select>

                        <button
                          onClick={runSimulation}
                          disabled={simulating}
                          className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5"
                        >
                          <Play className={`w-3.5 h-3.5 ${simulating ? "animate-spin" : ""}`} />
                          Simulate
                        </button>
                      </div>
                    </div>

                    {/* Simulation Result Output */}
                    {simulationResult && (
                      <div className="p-4 bg-indigo-950/30 border border-indigo-500/40 rounded-xl space-y-3 animate-in fade-in duration-200">
                        {/* Simulation Marker Banner */}
                        <div className="px-3 py-1.5 bg-amber-950/60 border border-amber-500/40 rounded-lg text-[11px] font-mono font-bold text-amber-300 text-center tracking-wider uppercase">
                          ⚠️ SIMULATION — NO CHANGES HAVE BEEN MADE TO LIVE DATABASE
                        </div>

                        <div className="text-xs text-slate-200 leading-relaxed">
                          {simulationResult.explanation}
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2">
                          <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                            <div className="text-[10px] text-slate-400">Projected Status</div>
                            <div className="text-sm font-bold font-mono text-emerald-400 mt-0.5">
                              {String(simulationResult.projected_state.status)}
                            </div>
                          </div>

                          <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                            <div className="text-[10px] text-slate-400">Risk Delta (Δ)</div>
                            <div className="text-sm font-bold font-mono text-indigo-400 mt-0.5">
                              {simulationResult.risk_delta < 0
                                ? `${Math.round(simulationResult.risk_delta * 100)}%`
                                : "0%"}
                            </div>
                          </div>

                          <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                            <div className="text-[10px] text-slate-400">Unblocked Dependents</div>
                            <div className="text-sm font-bold font-mono text-slate-100 mt-0.5">
                              {simulationResult.unblocked_obligations.length}
                            </div>
                          </div>
                        </div>

                        {simulationResult.unblocked_obligations.length > 0 && (
                          <div className="space-y-1.5 pt-2">
                            <div className="text-[11px] font-semibold text-slate-300">Projected Cascading Unblocks:</div>
                            {simulationResult.unblocked_obligations.map((unb: { action?: string; owner?: string; [key: string]: unknown }, idx) => (
                              <div
                                key={idx}
                                className="px-2.5 py-1.5 bg-slate-950 rounded border border-slate-800 flex items-center justify-between text-[11px]"
                              >
                                <span className="text-slate-200">{unb.action} ({unb.owner})</span>
                                <span className="text-emerald-400 font-mono">UNBLOCKED → CONFIRMED</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Section: SYSTEMIC BOTTLENECKS & RISK CONCENTRATION */}
              {bottlenecks && bottlenecks.bottlenecks.length > 0 && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
                  <div>
                    <span className="text-[11px] font-mono text-indigo-400 uppercase tracking-wider">
                      Systemic Graph Health
                    </span>
                    <h3 className="text-base font-bold text-slate-100 flex items-center gap-2 mt-0.5">
                      <Network className="w-4 h-4 text-rose-400" />
                      <span>Organizational Bottlenecks & Risk Concentration Points</span>
                    </h3>
                  </div>

                  <div className="space-y-3">
                    {bottlenecks.bottlenecks.slice(0, 5).map((b) => (
                      <div
                        key={b.obligation_id}
                        className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-100">{b.action}</span>
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-slate-800 text-slate-400">
                              {b.status}
                            </span>
                          </div>
                          <p className="text-slate-400">{b.neutral_summary}</p>
                        </div>

                        <div className="flex items-center gap-3 font-mono self-end sm:self-auto">
                          <span className="text-slate-400">{b.downstream_dependents_count} dependents</span>
                          <span className="px-2 py-0.5 rounded bg-rose-950/60 text-rose-300 border border-rose-500/30 font-bold">
                            Score: {b.bottleneck_score.toFixed(2)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="py-12 text-center text-slate-500 text-sm">
              Select an active obligation above to inspect its causal root causes.
            </div>
          )}
        </div>
      )}

      {/* FORECASTS TAB */}
      {activeTab === "FORECASTS" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Risk Filter:
              </span>
              <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs">
                {(["ALL", "HIGH", "MODERATE"] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setFilterRisk(mode)}
                    className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
                      filterRisk === mode
                        ? "bg-indigo-600 text-white shadow-sm"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>

            <div className="text-xs text-slate-500">
              Showing {filteredPredictions.length} of {overview?.predictions.length ?? 0} active forecasts
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredPredictions.map((pred) => (
              <PredictionCard key={pred.obligation_id} prediction={pred} />
            ))}
          </div>

          {filteredPredictions.length === 0 && (
            <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-12 text-center text-slate-400 space-y-2">
              <Brain className="w-8 h-8 text-slate-600 mx-auto" />
              <div className="text-base font-semibold text-slate-300">No matching forecasts</div>
              <div className="text-xs text-slate-500">
                Try switching the risk filter to view all active obligation evaluations.
              </div>
            </div>
          )}
        </div>
      )}

      {/* PATTERNS TAB */}
      {activeTab === "PATTERNS" && patterns && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="text-xs text-slate-400">Total Recorded Outcomes</div>
              <div className="text-2xl font-bold font-mono text-slate-100 mt-1">
                {patterns.total_historical_snapshots}
              </div>
            </div>
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="text-xs text-slate-400">Overall Completion Rate</div>
              <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
                {Math.round(patterns.completion_rate * 100)}%
              </div>
            </div>
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="text-xs text-slate-400">On-Time Completion Rate</div>
              <div className="text-2xl font-bold font-mono text-indigo-400 mt-1">
                {Math.round(patterns.on_time_completion_rate * 100)}%
              </div>
            </div>
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="text-xs text-slate-400">Average Historical Delay</div>
              <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
                {patterns.avg_delay_hours.toFixed(1)}h
              </div>
            </div>
          </div>
        </div>
      )}

      {/* OWNERS TAB */}
      {activeTab === "OWNERS" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {owners.map((owner) => (
              <div
                key={owner.owner}
                className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-slate-100">{owner.owner}</span>
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-slate-300">
                    {owner.total_obligations} Total
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2 bg-slate-950 rounded">
                    <div className="text-slate-400">On-Time Rate</div>
                    <div className="font-mono font-bold text-emerald-400">
                      {Math.round(owner.on_time_rate * 100)}%
                    </div>
                  </div>
                  <div className="p-2 bg-slate-950 rounded">
                    <div className="text-slate-400">Avg Delay</div>
                    <div className="font-mono font-bold text-amber-400">
                      {owner.avg_delay_hours.toFixed(1)}h
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* CALIBRATION TAB */}
      {activeTab === "CALIBRATION" && evaluation && (
        <div className="space-y-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
            <h3 className="text-base font-bold text-slate-100">Model Evaluation Metrics</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
                <div className="text-xs text-slate-400">Brier Calibration Score</div>
                <div className="text-2xl font-bold font-mono text-indigo-400 mt-1">
                  {evaluation.brier_score != null ? evaluation.brier_score.toFixed(3) : "—"}
                </div>
              </div>
              <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
                <div className="text-xs text-slate-400">High Risk Precision</div>
                <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
                  {evaluation.high_risk_precision != null
                    ? `${Math.round(evaluation.high_risk_precision * 100)}%`
                    : "—"}
                </div>
              </div>
              <div className="p-4 bg-slate-950 rounded-xl border border-slate-800">
                <div className="text-xs text-slate-400">Overdue Recall</div>
                <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
                  {evaluation.overdue_recall != null
                    ? `${Math.round(evaluation.overdue_recall * 100)}%`
                    : "—"}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ADAPTIVE TAB */}
      {activeTab === "ADAPTIVE" && (
        <div className="space-y-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <span>Learned Feature Effectiveness</span>
            </h3>
            <div className="space-y-2">
              {featurePatterns?.features.map((f) => (
                <div
                  key={f.feature}
                  className="p-3 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between text-xs"
                >
                  <span className="font-mono text-slate-300">{f.feature}</span>
                  <span className="font-mono font-bold text-indigo-400">
                    Reliability: {f.reliability_score.toFixed(2)} | Contribution: {f.average_contribution > 0 ? `+${f.average_contribution.toFixed(2)}` : f.average_contribution.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* PHASE 16: ORGANIZATIONAL MEMORY TAB */}
      {activeTab === "MEMORY" && (
        <div className="space-y-8">
          {/* Search & Filter Bar */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  <Brain className="w-4 h-4 text-purple-400" />
                  <span>Organizational Memory & Historical Knowledge Base</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Structured commitment memory, recurring patterns, and strictly neutral historical evidence.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Search deliverables, actions..."
                  value={memorySearchQuery}
                  onChange={(e) => setMemorySearchQuery(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:border-purple-500 outline-none w-56"
                />

                <select
                  value={memoryTypeFilter}
                  onChange={(e) => setMemoryTypeFilter(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:border-purple-500 outline-none"
                >
                  <option value="">All Types</option>
                  <option value="OBLIGATION_OUTCOME">Obligation Outcome</option>
                  <option value="INTERVENTION_OUTCOME">Intervention Outcome</option>
                  <option value="DEPENDENCY_PATTERN">Dependency Cascade</option>
                  <option value="BLOCKER_PATTERN">Blocker Pattern</option>
                </select>

                <button
                  onClick={fetchMemories}
                  disabled={memoryLoading}
                  className="p-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300 transition"
                  title="Refresh Memories"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${memoryLoading ? "animate-spin" : ""}`} />
                </button>
              </div>
            </div>

            {/* Workspace Wide Patterns Strip */}
            {workspacePatterns.length > 0 && (
              <div className="pt-3 border-t border-slate-800/80">
                <div className="text-[11px] font-semibold text-purple-400 uppercase tracking-wider mb-2">
                  Established Workspace Patterns
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {workspacePatterns.map((p, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-purple-950/20 border border-purple-800/30 rounded-lg flex items-center justify-between text-xs"
                    >
                      <div>
                        <div className="font-medium text-slate-200">{p.description}</div>
                        <div className="text-[10px] text-slate-400 mt-0.5">
                          Observations: {p.observation_count} • Confidence: {Math.round(p.confidence * 100)}%
                        </div>
                      </div>
                      <span className="text-[10px] uppercase font-bold px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded border border-purple-500/30">
                        {p.maturity.replace("_", " ")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Memory Records List */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <span>Historical Memory Records ({memoriesList.length})</span>
            </h4>

            {memoriesList.length === 0 ? (
              <div className="p-12 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-2xl">
                No organizational memory records matched the search filters.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {memoriesList.map((item) => (
                  <div
                    key={item.memory.id}
                    className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl hover:border-slate-700 transition space-y-2"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-slate-100">
                            {item.memory.semantic_summary}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                            {item.memory.memory_type}
                          </span>
                          {item.memory.outcome && (
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                                item.memory.outcome.includes("ON_TIME")
                                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                                  : item.memory.outcome.includes("LATE")
                                  ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                                  : "bg-slate-700/20 text-slate-400 border-slate-700/40"
                              }`}
                            >
                              {item.memory.outcome}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                          {item.memory.content}
                        </p>
                      </div>

                      <div className="text-right shrink-0 text-xs text-slate-500">
                        <div>{new Date(item.memory.observed_at).toLocaleDateString()}</div>
                        {item.memory.owner_id && (
                          <div className="text-[11px] text-indigo-400 font-medium mt-0.5">
                            Owner: {item.memory.owner_id}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Entities & Topics */}
                    {(item.memory.entities.length > 0 || item.memory.topics.length > 0) && (
                      <div className="flex flex-wrap gap-1.5 pt-2 border-t border-slate-800/60">
                        {item.memory.entities.map((e, idx) => (
                          <span
                            key={`e-${idx}`}
                            className="text-[10px] bg-slate-950 text-slate-400 px-1.5 py-0.5 rounded border border-slate-800"
                          >
                            entity:{e}
                          </span>
                        ))}
                        {item.memory.topics.map((t, idx) => (
                          <span
                            key={`t-${idx}`}
                            className="text-[10px] bg-slate-950 text-slate-400 px-1.5 py-0.5 rounded border border-slate-800"
                          >
                            topic:{t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* LLM Intelligence Layer Tab */}
      {activeTab === "LLM" && <LLMIntelligencePanel />}
    </div>
  );
}
