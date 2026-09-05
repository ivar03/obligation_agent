"use client";

import React, { useEffect, useState } from "react";
import { memoryApi } from "../../lib/api/obligations";
import {
  MemoryContextResponse,
  MemoryRetrievalItem,
  HistoricalPatternItem,
} from "../../lib/types/obligation";

interface Props {
  obligationId: string;
}

export const HistoricalContextCard: React.FC<Props> = ({ obligationId }) => {
  const [data, setData] = useState<MemoryContextResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<"similar" | "patterns" | "owner" | "semantic">("similar");

  useEffect(() => {
    let isMounted = true;
    const fetchContext = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await memoryApi.getContext(obligationId);
        if (isMounted) setData(res);
      } catch (err: unknown) {
        if (isMounted) setError((err as Error).message || "Failed to load organizational memory context");
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    fetchContext();
    return () => {
      isMounted = false;
    };
  }, [obligationId]);

  if (loading) {
    return (
      <div className="bg-stone-100/80 border border-stone-200 rounded-xl p-5 animate-pulse text-stone-600 text-sm">
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
          <span>Retrieving organizational memory & historical patterns...</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-stone-100/60 border border-stone-200 rounded-xl p-4 text-xs text-stone-600">
        <span className="font-semibold text-stone-700">Organizational Memory:</span>{" "}
        {error || "No memory context available for this obligation."}
      </div>
    );
  }

  const hasSimilar = data.similar_obligations && data.similar_obligations.length > 0;
  const hasPatterns = data.historical_patterns && data.historical_patterns.length > 0;
  const ownerStats = data.owner_analytics;
  const sem = data.semantic_representation;

  return (
    <div className="bg-gradient-to-b from-stone-100/90 to-stone-50/90 border border-blue-600/20 rounded-xl shadow-xl backdrop-blur-md overflow-hidden">
      {/* Header */}
      <div className="p-4 sm:p-5 border-b border-stone-200/80 flex flex-wrap items-center justify-between gap-3 bg-indigo-950/20">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600/10 border border-blue-600/30 flex items-center justify-center text-blue-500 font-bold text-sm">
            🧠
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-stone-900 text-base tracking-tight">
                Organizational Memory & Context
              </h3>
              <span
                className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${
                  data.context_status === "AVAILABLE"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    : "bg-stone-300/30 text-stone-600 border-stone-300/50"
                }`}
              >
                {data.context_status === "AVAILABLE" ? "Context Available" : "No Comparable History"}
              </span>
            </div>
            <p className="text-xs text-stone-600 mt-0.5">{data.explanation}</p>
          </div>
        </div>

        {/* Sub-tabs */}
        <div className="flex items-center gap-1 bg-stone-50/60 p-1 rounded-lg border border-stone-200">
          <button
            onClick={() => setActiveSubTab("similar")}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
              activeSubTab === "similar"
                ? "bg-blue-700 text-stone-950 shadow"
                : "text-stone-600 hover:text-stone-800"
            }`}
          >
            Similar Commitments ({data.similar_obligations.length})
          </button>
          <button
            onClick={() => setActiveSubTab("patterns")}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
              activeSubTab === "patterns"
                ? "bg-blue-700 text-stone-950 shadow"
                : "text-stone-600 hover:text-stone-800"
            }`}
          >
            Patterns ({data.historical_patterns.length})
          </button>
          {ownerStats && (
            <button
              onClick={() => setActiveSubTab("owner")}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                activeSubTab === "owner"
                  ? "bg-blue-700 text-stone-950 shadow"
                  : "text-stone-600 hover:text-stone-800"
              }`}
            >
              Owner History
            </button>
          )}
          <button
            onClick={() => setActiveSubTab("semantic")}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
              activeSubTab === "semantic"
                ? "bg-blue-700 text-stone-950 shadow"
                : "text-stone-600 hover:text-stone-800"
            }`}
          >
            Semantic Labels
          </button>
        </div>
      </div>

      {/* Body Content */}
      <div className="p-4 sm:p-5">
        {/* TAB 1: SIMILAR COMMITMENTS */}
        {activeSubTab === "similar" && (
          <div>
            {!hasSimilar ? (
              <div className="p-6 text-center text-xs text-stone-500 border border-dashed border-stone-200 rounded-lg">
                No historically similar commitments found above the relevance threshold.
              </div>
            ) : (
              <div className="space-y-3">
                {data.similar_obligations.map((item: MemoryRetrievalItem) => (
                  <div
                    key={item.memory.id}
                    className="p-3.5 bg-stone-100/60 border border-stone-200/80 rounded-lg hover:border-stone-300 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-stone-800 text-xs">
                            {item.memory.semantic_summary}
                          </span>
                          <span
                            className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                              item.memory.outcome === "COMPLETED_ON_TIME"
                                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                                : item.memory.outcome === "COMPLETED_LATE"
                                ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                                : "bg-stone-300/20 text-stone-600 border-stone-300/40"
                            }`}
                          >
                            {item.memory.outcome || "COMPLETED"}
                          </span>
                        </div>
                        <p className="text-xs text-stone-600 mt-1 leading-relaxed">
                          {item.memory.content}
                        </p>
                      </div>

                      <div className="text-right shrink-0">
                        <div className="text-xs font-bold text-blue-500">
                          {Math.round(item.relevance_score * 100)}% match
                        </div>
                        <div className="text-[10px] text-stone-500">
                          {new Date(item.memory.observed_at).toLocaleDateString()}
                        </div>
                      </div>
                    </div>

                    {/* Match Reasons */}
                    {item.match_reasons.length > 0 && (
                      <div className="mt-2.5 pt-2 border-t border-stone-200/60 flex flex-wrap items-center gap-1.5">
                        <span className="text-[10px] text-stone-500 uppercase tracking-wider font-semibold">
                          Match Factors:
                        </span>
                        {item.match_reasons.map((reason, idx) => (
                          <span
                            key={idx}
                            className="text-[10px] bg-stone-200 text-stone-700 px-2 py-0.5 rounded border border-stone-300/50"
                          >
                            {reason}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: PATTERNS */}
        {activeSubTab === "patterns" && (
          <div>
            {!hasPatterns ? (
              <div className="p-6 text-center text-xs text-stone-500 border border-dashed border-stone-200 rounded-lg">
                No recurring delay or blocker patterns identified for this commitment.
              </div>
            ) : (
              <div className="space-y-3">
                {data.historical_patterns.map((pat: HistoricalPatternItem, idx: number) => (
                  <div
                    key={idx}
                    className="p-3.5 bg-stone-100/60 border border-stone-200/80 rounded-lg flex items-start justify-between gap-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-stone-800">
                          {pat.description}
                        </span>
                        <span
                          className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                            pat.maturity === "ESTABLISHED_PATTERN"
                              ? "bg-purple-500/10 text-purple-400 border-purple-500/30"
                              : pat.maturity === "EMERGING_PATTERN"
                              ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                              : "bg-stone-300/20 text-stone-600 border-stone-300/40"
                          }`}
                        >
                          {pat.maturity.replace("_", " ")}
                        </span>
                      </div>
                      <div className="text-[11px] text-stone-600 flex items-center gap-3">
                        <span>Observations: {pat.observation_count}</span>
                        <span>Confidence: {Math.round(pat.confidence * 100)}%</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Recurring Cadence Notice if present */}
            {data.recurring_commitment && (
              <div className="mt-4 p-3 bg-indigo-950/30 border border-blue-600/20 rounded-lg flex items-center justify-between">
                <div>
                  <div className="text-xs font-semibold text-blue-600">
                    Recurring Commitment Cadence: {data.recurring_commitment.recurrence_type}
                  </div>
                  <div className="text-[11px] text-stone-600">
                    {data.recurring_commitment.description}
                  </div>
                </div>
                {data.recurring_commitment.next_predicted_date && (
                  <div className="text-right text-[11px] text-stone-600">
                    Next cycle projected:{" "}
                    <span className="font-semibold text-blue-500">
                      {new Date(data.recurring_commitment.next_predicted_date).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: OWNER HISTORY */}
        {activeSubTab === "owner" && ownerStats && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 bg-stone-100/60 border border-stone-200 rounded-lg">
                <div className="text-[10px] uppercase tracking-wider text-stone-500 font-semibold">
                  Observed Commitments
                </div>
                <div className="text-lg font-bold text-stone-900 mt-0.5">
                  {ownerStats.total_commitments_observed}
                </div>
              </div>
              <div className="p-3 bg-stone-100/60 border border-stone-200 rounded-lg">
                <div className="text-[10px] uppercase tracking-wider text-stone-500 font-semibold">
                  Completion Rate
                </div>
                <div className="text-lg font-bold text-emerald-400 mt-0.5">
                  {Math.round(ownerStats.completion_rate * 100)}%
                </div>
              </div>
              <div className="p-3 bg-stone-100/60 border border-stone-200 rounded-lg">
                <div className="text-[10px] uppercase tracking-wider text-stone-500 font-semibold">
                  On-Time Rate
                </div>
                <div className="text-lg font-bold text-blue-500 mt-0.5">
                  {Math.round(ownerStats.on_time_completion_rate * 100)}%
                </div>
              </div>
              <div className="p-3 bg-stone-100/60 border border-stone-200 rounded-lg">
                <div className="text-[10px] uppercase tracking-wider text-stone-500 font-semibold">
                  Median Delay
                </div>
                <div className="text-lg font-bold text-amber-400 mt-0.5">
                  {ownerStats.median_delay_hours > 0
                    ? `${ownerStats.median_delay_hours}h`
                    : "0h"}
                </div>
              </div>
            </div>

            <div className="p-3 bg-stone-100/80 border border-stone-200 rounded-lg text-xs text-stone-700 leading-relaxed">
              <div className="font-semibold text-stone-800 mb-1">Factual Observational Summary:</div>
              {ownerStats.neutral_summary}
            </div>

            {!ownerStats.has_sufficient_history && (
              <div className="text-[11px] text-amber-400/90 italic">
                * Note: Sample size is less than 3 observations (INSUFFICIENT_HISTORY). Metrics are exploratory.
              </div>
            )}
          </div>
        )}

        {/* TAB 4: SEMANTIC LABELS */}
        {activeSubTab === "semantic" && sem && (
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="p-3 bg-stone-100/60 border border-stone-200 rounded-lg">
                <div className="text-[10px] text-stone-500 uppercase font-semibold">Extracted Action</div>
                <div className="text-stone-800 font-medium mt-1">{sem.action || "None"}</div>
              </div>
              <div className="p-3 bg-stone-100/60 border border-stone-200 rounded-lg">
                <div className="text-[10px] text-stone-500 uppercase font-semibold">Deliverable</div>
                <div className="text-stone-800 font-medium mt-1">{sem.deliverable || "None"}</div>
              </div>
            </div>

            <div className="p-3 bg-stone-100/60 border border-stone-200 rounded-lg">
              <div className="text-[10px] text-stone-500 uppercase font-semibold mb-1.5">
                Entities & Topics
              </div>
              <div className="flex flex-wrap gap-1.5">
                {sem.entities.map((e, idx) => (
                  <span
                    key={`e-${idx}`}
                    className="text-[11px] bg-indigo-950/60 text-blue-600 border border-indigo-800/40 px-2 py-0.5 rounded"
                  >
                    entity:{e}
                  </span>
                ))}
                {sem.topics.map((t, idx) => (
                  <span
                    key={`t-${idx}`}
                    className="text-[11px] bg-purple-950/60 text-purple-300 border border-purple-800/40 px-2 py-0.5 rounded"
                  >
                    topic:{t}
                  </span>
                ))}
                {sem.entities.length === 0 && sem.topics.length === 0 && (
                  <span className="text-stone-500">None detected</span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Safety Notice Footer */}
      <div className="px-5 py-2.5 bg-stone-50 border-t border-stone-200/60 text-[10px] text-stone-500 flex items-center justify-between">
        <span>🛡️ Strict Invariant: Contextual evidence only. No autonomous decisions or judgments.</span>
        <span>Append-Only Historical Ledger</span>
      </div>
    </div>
  );
};
