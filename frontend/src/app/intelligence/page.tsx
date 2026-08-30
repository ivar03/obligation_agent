"use client";

import React, { useState, useEffect } from "react";
import {
  Brain,
  AlertTriangle,
  Clock,
  Users,
  BarChart3,
  ShieldCheck,
  RefreshCw,
  Sliders,
  Layers,
  HelpCircle,
  Sparkles,
  Zap,
} from "lucide-react";
import {
  IntelligenceOverviewResponse,
  HistoricalPatternsResponse,
  OwnerPatternMetric,
  PredictionEvaluationMetrics,
  AdaptiveOverviewResponse,
  AdaptiveFeaturePatternsResponse,
} from "@/lib/types/obligation";
import { intelligenceApi } from "@/lib/api/obligations";
import { PredictionCard } from "@/components/intelligence/PredictionCard";

export default function IntelligencePage() {
  const [activeTab, setActiveTab] = useState<"FORECASTS" | "PATTERNS" | "OWNERS" | "CALIBRATION" | "ADAPTIVE">("FORECASTS");
  const [overview, setOverview] = useState<IntelligenceOverviewResponse | null>(null);
  const [patterns, setPatterns] = useState<HistoricalPatternsResponse | null>(null);
  const [owners, setOwners] = useState<OwnerPatternMetric[]>([]);
  const [evaluation, setEvaluation] = useState<PredictionEvaluationMetrics | null>(null);
  const [adaptiveOverview, setAdaptiveOverview] = useState<AdaptiveOverviewResponse | null>(null);
  const [featurePatterns, setFeaturePatterns] = useState<AdaptiveFeaturePatternsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterRisk, setFilterRisk] = useState<"ALL" | "HIGH" | "MODERATE">("ALL");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [ovData, patData, ownData, evalData, adaptOvData, featData] = await Promise.all([
        intelligenceApi.getOverview().catch(() => null),
        intelligenceApi.getPatterns().catch(() => null),
        intelligenceApi.getOwners().catch(() => []),
        intelligenceApi.getEvaluation().catch(() => null),
        intelligenceApi.getAdaptiveOverview().catch(() => null),
        intelligenceApi.getAdaptiveFeatures().catch(() => null),
      ]);
      setOverview(ovData);
      setPatterns(patData);
      setOwners(ownData);
      setEvaluation(evalData);
      setAdaptiveOverview(adaptOvData);
      setFeaturePatterns(featData);
    } catch (err) {
      console.error("Failed to load intelligence data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const filteredPredictions = overview?.predictions.filter((p) => {
    if (filterRisk === "HIGH") return p.failure_probability >= 0.55;
    if (filterRisk === "MODERATE") return p.failure_probability >= 0.35 && p.failure_probability < 0.55;
    return true;
  }) || [];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 text-indigo-400 font-semibold text-xs tracking-wider uppercase">
            <Brain className="w-4 h-4" />
            Phase 12 Predictive Intelligence
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-100 mt-1">
            Obligation Intelligence & Pattern Learning
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Explainable delay forecasting, historical pattern learning, and calibrated risk intelligence.
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
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Active Forecasts</span>
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-3xl font-bold text-slate-100 font-mono mt-2">
            {overview?.active_obligations_evaluated ?? 0}
          </div>
          <div className="text-xs text-slate-500 mt-1">Obligations actively monitored</div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-400 uppercase tracking-wider">High Failure Risk</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-3xl font-bold text-rose-400 font-mono mt-2">
            {overview?.high_predicted_failure_count ?? 0}
          </div>
          <div className="text-xs text-slate-500 mt-1">Probability &ge; 50%</div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">Projected Delays</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-bold text-amber-400 font-mono mt-2">
            {overview?.likely_to_miss_deadline_count ?? 0}
          </div>
          <div className="text-xs text-slate-500 mt-1">Expected latency &gt; 0h</div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">Intervention Needed</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-bold text-emerald-400 font-mono mt-2">
            {overview?.likely_to_require_intervention_count ?? 0}
          </div>
          <div className="text-xs text-slate-500 mt-1">Follow-up likelihood &ge; 50%</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-800 flex items-center justify-between">
        <div className="flex space-x-2">
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
            onClick={() => setActiveTab("PATTERNS")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "PATTERNS"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            Historical Patterns & Trends
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
            <Sparkles className="w-4 h-4 text-indigo-400" />
            Adaptive Intelligence (Phase 13)
          </button>
        </div>

        {activeTab === "FORECASTS" && (
          <div className="flex items-center gap-1.5 text-xs text-slate-400 pb-2">
            <span>Filter:</span>
            <button
              onClick={() => setFilterRisk("ALL")}
              className={`px-2 py-1 rounded ${filterRisk === "ALL" ? "bg-slate-700 text-slate-100 font-semibold" : "hover:bg-slate-800"}`}
            >
              All
            </button>
            <button
              onClick={() => setFilterRisk("HIGH")}
              className={`px-2 py-1 rounded ${filterRisk === "HIGH" ? "bg-rose-500/20 text-rose-300 font-semibold" : "hover:bg-slate-800"}`}
            >
              High Risk
            </button>
            <button
              onClick={() => setFilterRisk("MODERATE")}
              className={`px-2 py-1 rounded ${filterRisk === "MODERATE" ? "bg-amber-500/20 text-amber-300 font-semibold" : "hover:bg-slate-800"}`}
            >
              Moderate
            </button>
          </div>
        )}
      </div>

      {/* Tab Content 1: FORECASTS */}
      {activeTab === "FORECASTS" && (
        <div className="space-y-4">
          {filteredPredictions.length === 0 ? (
            <div className="text-center py-12 bg-slate-900/40 rounded-xl border border-slate-800 text-slate-400">
              <Brain className="w-8 h-8 mx-auto text-slate-500 mb-2" />
              <p>No active obligations match the selected prediction filter.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredPredictions.map((pred) => (
                <PredictionCard key={pred.obligation_id} prediction={pred} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab Content 2: HISTORICAL PATTERNS */}
      {activeTab === "PATTERNS" && patterns && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Historical On-Time Rate</div>
              <div className="text-3xl font-bold text-emerald-400 font-mono mt-2">
                {Math.round(patterns.on_time_completion_rate * 100)}%
              </div>
              <div className="text-xs text-slate-500 mt-1">Across {patterns.total_historical_snapshots} logged outcomes</div>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Average Delay Latency</div>
              <div className="text-3xl font-bold text-amber-400 font-mono mt-2">
                {patterns.avg_delay_hours}h
              </div>
              <div className="text-xs text-slate-500 mt-1">Median: {patterns.median_delay_hours}h</div>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Dependency Bottleneck Rate</div>
              <div className="text-3xl font-bold text-indigo-400 font-mono mt-2">
                {Math.round(patterns.dependency_bottleneck_rate * 100)}%
              </div>
              <div className="text-xs text-slate-500 mt-1">Constrained by prerequisites</div>
            </div>
          </div>

          {/* Delay Distribution */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
            <h3 className="text-base font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <Clock className="w-4 h-4 text-indigo-400" />
              Historical Delay Latency Distribution
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
              <div className="p-4 bg-slate-950/40 rounded-lg border border-slate-800">
                <div className="text-2xl font-bold text-emerald-400 font-mono">
                  {patterns.delay_distribution["ON_TIME"] ?? 0}
                </div>
                <div className="text-xs text-slate-400 mt-1">On-Time / Early</div>
              </div>
              <div className="p-4 bg-slate-950/40 rounded-lg border border-slate-800">
                <div className="text-2xl font-bold text-amber-400 font-mono">
                  {patterns.delay_distribution["UNDER_12_HOURS"] ?? 0}
                </div>
                <div className="text-xs text-slate-400 mt-1">&lt; 12 Hours Late</div>
              </div>
              <div className="p-4 bg-slate-950/40 rounded-lg border border-slate-800">
                <div className="text-2xl font-bold text-orange-400 font-mono">
                  {patterns.delay_distribution["12_TO_48_HOURS"] ?? 0}
                </div>
                <div className="text-xs text-slate-400 mt-1">12 – 48 Hours Late</div>
              </div>
              <div className="p-4 bg-slate-950/40 rounded-lg border border-slate-800">
                <div className="text-2xl font-bold text-rose-400 font-mono">
                  {patterns.delay_distribution["OVER_48_HOURS"] ?? 0}
                </div>
                <div className="text-xs text-slate-400 mt-1">&gt; 48 Hours / Overdue</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab Content 3: OWNER ANALYTICS */}
      {activeTab === "OWNERS" && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
          <div className="p-5 border-b border-slate-800">
            <h3 className="text-base font-semibold text-slate-200">
              Neutral Operational Delivery Patterns
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Objective historical statistics derived strictly from persisted completion records.
            </p>
          </div>

          {owners.length === 0 ? (
            <div className="text-center py-10 text-slate-400 text-sm">
              No historical owner outcome records observed yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-950/50 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="px-5 py-3">Owner</th>
                    <th className="px-5 py-3 text-center">Tracked</th>
                    <th className="px-5 py-3 text-center">On-Time Rate</th>
                    <th className="px-5 py-3 text-center">Avg Latency</th>
                    <th className="px-5 py-3 text-center">Blocker Freq</th>
                    <th className="px-5 py-3">Operational Insights</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {owners.map((o) => (
                    <tr key={o.owner} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-5 py-4 font-semibold text-slate-200">
                        {o.owner}
                      </td>
                      <td className="px-5 py-4 text-center font-mono text-slate-300">
                        {o.total_obligations}
                      </td>
                      <td className="px-5 py-4 text-center font-mono">
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                          o.on_time_rate >= 0.80 ? "bg-emerald-500/20 text-emerald-300" : o.on_time_rate >= 0.50 ? "bg-amber-500/20 text-amber-300" : "bg-rose-500/20 text-rose-300"
                        }`}>
                          {Math.round(o.on_time_rate * 100)}%
                        </span>
                      </td>
                      <td className="px-5 py-4 text-center font-mono text-slate-300">
                        {o.avg_delay_hours > 0 ? `~${o.avg_delay_hours}h` : "0.0h"}
                      </td>
                      <td className="px-5 py-4 text-center font-mono text-slate-300">
                        {Math.round(o.blocker_frequency * 100)}%
                      </td>
                      <td className="px-5 py-4 text-xs text-slate-400">
                        <ul className="space-y-1">
                          {o.insights.map((ins, i) => (
                            <li key={i} className="flex items-center gap-1.5">
                              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                              <span>{ins}</span>
                            </li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab Content 4: CALIBRATION */}
      {activeTab === "CALIBRATION" && evaluation && (
        <div className="space-y-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-semibold text-slate-200">
                  Model Calibration & Evaluation Metrics
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Empirical verification comparing prediction forecasts against observed ground truth outcomes.
                </p>
              </div>
              <span className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${
                evaluation.status === "EVALUATED"
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  : "bg-slate-700/40 text-slate-400 border-slate-600/40"
              }`}>
                {evaluation.status}
              </span>
            </div>

            <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-4 bg-slate-950/40 rounded-lg border border-slate-800">
                <div className="text-xs text-slate-400 font-medium">Predictions Evaluated</div>
                <div className="text-2xl font-bold text-slate-200 font-mono mt-1">
                  {evaluation.total_predictions_evaluated}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">Resolved samples</div>
              </div>

              <div className="p-4 bg-slate-950/40 rounded-lg border border-slate-800">
                <div className="text-xs text-slate-400 font-medium">Brier Score</div>
                <div className="text-2xl font-bold text-indigo-400 font-mono mt-1">
                  {evaluation.brier_score !== null && evaluation.brier_score !== undefined ? evaluation.brier_score : "—"}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">Lower is better (0.0 perfect)</div>
              </div>

              <div className="p-4 bg-slate-950/40 rounded-lg border border-slate-800">
                <div className="text-xs text-slate-400 font-medium">Mean Absolute Error (Delay)</div>
                <div className="text-2xl font-bold text-amber-400 font-mono mt-1">
                  {evaluation.mean_absolute_error_hours !== null && evaluation.mean_absolute_error_hours !== undefined ? `${evaluation.mean_absolute_error_hours}h` : "—"}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">Average forecast variance</div>
              </div>

              <div className="p-4 bg-slate-950/40 rounded-lg border border-slate-800">
                <div className="text-xs text-slate-400 font-medium">High-Risk Precision</div>
                <div className="text-2xl font-bold text-emerald-400 font-mono mt-1">
                  {evaluation.high_risk_precision !== null && evaluation.high_risk_precision !== undefined ? `${Math.round(evaluation.high_risk_precision * 100)}%` : "—"}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">At 50% threshold</div>
              </div>
            </div>

            <div className="mt-6 p-3 bg-slate-950/30 rounded-lg border border-slate-800/80 text-xs text-slate-400 flex items-center gap-2">
              <HelpCircle className="w-4 h-4 text-slate-500 shrink-0" />
              <span>{evaluation.message}</span>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: ADAPTIVE INTELLIGENCE & CALIBRATION (PHASE 13) */}
      {activeTab === "ADAPTIVE" && (
        <div className="space-y-6">
          {/* Data Sufficiency Indicator */}
          <div className={`p-5 rounded-2xl border ${
            adaptiveOverview?.calibration_status === "CALIBRATION_AVAILABLE"
              ? "bg-emerald-950/20 border-emerald-500/40"
              : adaptiveOverview?.calibration_status === "LOW_SAMPLE"
              ? "bg-blue-950/20 border-blue-500/40"
              : "bg-amber-950/20 border-amber-500/40"
          }`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                    <span>Data Sufficiency Status:</span>
                    <span className="font-mono text-indigo-300">
                      {adaptiveOverview?.calibration_status || "INSUFFICIENT_HISTORY"}
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400">
                    {adaptiveOverview?.calibration_metrics.message || "Evaluating historical prediction feedback."}
                  </p>
                </div>
              </div>

              <div className="text-right text-xs">
                <div className="text-slate-200 font-mono font-bold">
                  {adaptiveOverview?.active_evaluations ?? 0} Evaluated Samples
                </div>
                <div className="text-slate-500 text-[11px]">
                  (Minimum {adaptiveOverview?.calibration_metrics.minimum_required ?? 3} required)
                </div>
              </div>
            </div>
          </div>

          {/* Model Comparison Grid */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-indigo-400" />
                  <span>Model Performance Benchmark</span>
                </h3>
                <p className="text-xs text-slate-400">
                  Comparative performance between baseline (predictive-v1) and calibrated (adaptive-v1) providers.
                </p>
              </div>
              <span className="px-2.5 py-0.5 rounded-md text-[11px] font-mono bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
                adaptive-v1 active
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
              <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-1">
                <div className="text-xs text-slate-400 font-medium">Brier Score</div>
                <div className="text-xl font-bold font-mono text-indigo-300">
                  {adaptiveOverview?.calibration_metrics.brier_score !== null && adaptiveOverview?.calibration_metrics.brier_score !== undefined
                    ? adaptiveOverview.calibration_metrics.brier_score
                    : "—"}
                </div>
                <div className="text-[10px] text-slate-500">Lower is better (0.0 perfect)</div>
              </div>

              <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-1">
                <div className="text-xs text-slate-400 font-medium">Mean Delay MAE</div>
                <div className="text-xl font-bold font-mono text-amber-300">
                  {adaptiveOverview?.calibration_metrics.mean_absolute_delay_error !== null && adaptiveOverview?.calibration_metrics.mean_absolute_delay_error !== undefined
                    ? `${adaptiveOverview.calibration_metrics.mean_absolute_delay_error}h`
                    : "—"}
                </div>
                <div className="text-[10px] text-slate-500">Average forecast variance</div>
              </div>

              <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-1">
                <div className="text-xs text-slate-400 font-medium">Calibration Error</div>
                <div className="text-xl font-bold font-mono text-rose-300">
                  {adaptiveOverview?.calibration_metrics.calibration_error !== null && adaptiveOverview?.calibration_metrics.calibration_error !== undefined
                    ? adaptiveOverview.calibration_metrics.calibration_error
                    : "—"}
                </div>
                <div className="text-[10px] text-slate-500">Probabilistic divergence</div>
              </div>

              <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-1">
                <div className="text-xs text-slate-400 font-medium">High-Risk Precision</div>
                <div className="text-xl font-bold font-mono text-emerald-300">
                  {adaptiveOverview?.calibration_metrics.high_risk_precision !== null && adaptiveOverview?.calibration_metrics.high_risk_precision !== undefined
                    ? `${Math.round(adaptiveOverview.calibration_metrics.high_risk_precision * 100)}%`
                    : "—"}
                </div>
                <div className="text-[10px] text-slate-500">At 50% failure threshold</div>
              </div>
            </div>
          </div>

          {/* Learned Feature Effectiveness Table */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-indigo-400" />
                  <span>Learned Feature Effectiveness</span>
                </h3>
                <p className="text-xs text-slate-400">
                  Empirically learned weights and reliability scores derived from historical prediction feedback.
                </p>
              </div>
              <span className="text-xs text-slate-500">
                {featurePatterns?.total_feedback_evaluated ?? 0} feedback observations
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="pb-3 font-semibold">Signal Feature</th>
                    <th className="pb-3 font-semibold">Observations</th>
                    <th className="pb-3 font-semibold">Learned Weight</th>
                    <th className="pb-3 font-semibold">Predictive Direction</th>
                    <th className="pb-3 font-semibold">Outcome Association</th>
                    <th className="pb-3 font-semibold">Reliability</th>
                    <th className="pb-3 font-semibold">Usefulness</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {(featurePatterns?.features || []).map((f) => (
                    <tr key={f.feature} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 font-mono font-medium text-slate-200">{f.feature}</td>
                      <td className="py-3 text-slate-400 font-mono">{f.observation_count}</td>
                      <td className="py-3 font-mono text-indigo-300 font-bold">
                        {featurePatterns?.learned_weights[f.feature] ?? "—"}
                      </td>
                      <td className="py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          f.predictive_direction.includes("INCREASES")
                            ? "bg-rose-500/15 text-rose-300"
                            : f.predictive_direction.includes("DECREASES")
                            ? "bg-emerald-500/15 text-emerald-300"
                            : "bg-slate-700/40 text-slate-400"
                        }`}>
                          {f.predictive_direction.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="py-3 font-mono text-slate-300">
                        {(f.outcome_association * 100).toFixed(0)}%
                      </td>
                      <td className="py-3 font-mono text-emerald-400 font-bold">
                        {(f.reliability_score * 100).toFixed(0)}%
                      </td>
                      <td className="py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          f.historical_usefulness === "HIGHLY_PREDICTIVE"
                            ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                            : "bg-slate-800 text-slate-400"
                        }`}>
                          {f.historical_usefulness.replace(/_/g, " ")}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Intervention Efficacy Analytics */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div>
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Intervention Efficacy Analysis</span>
              </h3>
              <p className="text-xs text-slate-400">
                Objective operational statistics measuring observed completion rates for commitments with vs without human-authorized interventions.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
              <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-1">
                <div className="text-xs text-slate-400 font-medium">Observed Completion (With Follow-up)</div>
                <div className="text-xl font-bold font-mono text-emerald-400">
                  {adaptiveOverview?.intervention_efficacy
                    ? `${Math.round(adaptiveOverview.intervention_efficacy.observed_completion_rate_with_intervention * 100)}%`
                    : "—"}
                </div>
                <div className="text-[10px] text-slate-500">
                  {adaptiveOverview?.intervention_efficacy.completed_after_intervention ?? 0} commitments resolved
                </div>
              </div>

              <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-1">
                <div className="text-xs text-slate-400 font-medium">Observed Completion (No Follow-up)</div>
                <div className="text-xl font-bold font-mono text-slate-300">
                  {adaptiveOverview?.intervention_efficacy
                    ? `${Math.round(adaptiveOverview.intervention_efficacy.observed_completion_rate_without_intervention * 100)}%`
                    : "—"}
                </div>
                <div className="text-[10px] text-slate-500">
                  {adaptiveOverview?.intervention_efficacy.completed_without_intervention ?? 0} commitments resolved
                </div>
              </div>

              <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-1">
                <div className="text-xs text-slate-400 font-medium">Executed Interventions</div>
                <div className="text-xl font-bold font-mono text-indigo-300">
                  {adaptiveOverview?.intervention_efficacy.interventions_executed ?? 0}
                </div>
                <div className="text-[10px] text-slate-500">Human-authorized follow-ups</div>
              </div>
            </div>

            {adaptiveOverview?.intervention_efficacy.insights && adaptiveOverview.intervention_efficacy.insights.length > 0 && (
              <div className="p-3 bg-slate-950/40 rounded-lg border border-slate-800/80 text-xs text-slate-400 space-y-1">
                {adaptiveOverview.intervention_efficacy.insights.map((ins, idx) => (
                  <div key={idx} className="flex items-center gap-2 text-slate-300">
                    <span className="text-indigo-400 font-mono">•</span>
                    <span>{ins}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
