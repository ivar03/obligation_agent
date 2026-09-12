"use client";

import React, { useState } from "react";
import {
  Brain,
  ArrowRight,
  Zap,
} from "lucide-react";

interface InsightNode {
  id: string;
  stage: string;
  title: string;
  actor: string;
  source: string;
  time: string;
  description: string;
  badge: string;
  badgeColor: string;
  detail: string;
}

const INSIGHTS: InsightNode[] = [
  {
    id: "detect",
    stage: "01. Signal Extraction",
    title: "Commitment Detected",
    actor: "Priya Sharma (@priya)",
    source: "Slack #dev-infra",
    time: "Yesterday, 4:15 PM",
    description: "Extracted promise: 'Will deliver staging database benchmark suite by 10 AM tomorrow.'",
    badge: "NLP Grounded",
    badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    detail: "Gemini isolated obligor (@priya), beneficiary (@rahul), deliverable (benchmark suite), and explicit temporal deadline (10:00 AM).",
  },
  {
    id: "block",
    stage: "02. Graph Correlation",
    title: "Root Blocker Identified",
    actor: "Jira Sync Engine",
    source: "Jira INFRA-402",
    time: "Today, 11:30 AM",
    description: "Issue INFRA-402 transitioned to BLOCKED: RDS IOPS throttled on read replica.",
    badge: "Graph Blocker",
    badgeColor: "bg-rose-50 text-rose-700 border-rose-200",
    detail: "Obligation Agent correlated Jira ticket INFRA-402 to Priya's commitment, automatically flagging an upstream operational block.",
  },
  {
    id: "risk",
    stage: "03. Predictive Reasoning",
    title: "Failure Risk Escalated",
    actor: "Bayesian Forecast Engine",
    source: "Risk Evaluator v1.4",
    time: "Today, 11:45 AM",
    description: "Failure probability surged from 14% → 88%. Blast radius: 3 downstream enterprise cutovers.",
    badge: "Risk: 88%",
    badgeColor: "bg-amber-50 text-amber-700 border-amber-200",
    detail: "Calculated time buffer depletion: with 4.5 hours remaining and a blocked database dependency, milestone failure probability crossed critical threshold.",
  },
  {
    id: "cause",
    stage: "04. Causal Attribution",
    title: "Root Cause Isolated",
    actor: "Graph Topology Reasoner",
    source: "Causal Model Phase 14",
    time: "Today, 11:48 AM",
    description: "Isolated primary driver: Database benchmark suite timed out on replica A (latency spike).",
    badge: "Causal Proof",
    badgeColor: "bg-orange-50 text-orange-700 border-orange-200",
    detail: "Traced dependency path through 3 hops to confirm the root cause is infrastructure resource throttling, not personnel neglect.",
  },
  {
    id: "action",
    stage: "05. Remediation Plan",
    title: "Grounded Action Recommended",
    actor: "Gemini 2.5 Orchestrator",
    source: "Decision Center",
    time: "Today, 11:50 AM",
    description: "Action proposed: Re-run suite on replica cluster B + dispatch pre-drafted Slack reminder.",
    badge: "Human Gated",
    badgeColor: "bg-orange-600 text-white border-orange-600",
    detail: "Prepares 1-click execution receipt protecting downstream cutover schedule. Requires authorized human operator click to dispatch.",
  },
];

export const CausalShowcase: React.FC = () => {
  const [selectedInsightId, setSelectedInsightId] = useState<string>("cause");
  const activeInsight = INSIGHTS.find((i) => i.id === selectedInsightId) || INSIGHTS[3];

  return (
    <section id="intelligence" className="py-20 bg-transparent border-b border-stone-200/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-50 border border-orange-200 text-orange-800 text-xs font-semibold">
            <Brain className="w-3.5 h-3.5 text-orange-600" />
            <span>Product Intelligence Showcase</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-stone-900 tracking-tight text-readable-glow">
            Not a Chatbot. A Living Causal Graph.
          </h2>
          <p className="text-stone-600 text-base leading-relaxed text-readable-glow-subtle">
            See how Obligation Agent connects five separate signals across conversations, tickets, and telemetry
            into an actionable chain of enterprise causality.
          </p>
        </div>

        {/* Interactive 5-Node Causal Flow */}
        <div className="max-w-6xl mx-auto space-y-8">
          {/* Causal Sequence Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {INSIGHTS.map((node) => {
              const isSelected = node.id === selectedInsightId;

              return (
                <button
                  key={node.id}
                  onClick={() => setSelectedInsightId(node.id)}
                  onMouseEnter={() => setSelectedInsightId(node.id)}
                  className={`p-4 rounded-xl border text-left transition-all relative flex flex-col justify-between space-y-2.5 h-36 ${
                    isSelected
                      ? "bg-white/95 backdrop-blur-md border-orange-500 shadow-md ring-2 ring-orange-500/20 scale-[1.02]"
                      : "bg-white/80 backdrop-blur-sm border-stone-200 hover:bg-white/95 hover:border-orange-200"
                  }`}
                >
                  <div className="flex items-center justify-between w-full">
                    <span className="text-[10px] font-mono font-bold text-stone-500 uppercase">
                      {node.stage}
                    </span>
                    <span
                      className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${node.badgeColor}`}
                    >
                      {node.badge}
                    </span>
                  </div>

                  <div>
                    <h4 className="text-xs font-bold text-stone-900 leading-snug">{node.title}</h4>
                    <div className="text-[11px] text-stone-500 truncate mt-0.5">{node.source}</div>
                  </div>

                  <div className="text-[10px] text-orange-700 font-semibold flex items-center gap-1 pt-1 border-t border-stone-200/80">
                    <span>Inspect</span>
                    <ArrowRight className="w-2.5 h-2.5" />
                  </div>
                </button>
              );
            })}
          </div>

          {/* Expanded Causal Context Card */}
          <div className="rounded-2xl border border-stone-200/90 bg-white/85 backdrop-blur-md p-6 sm:p-8 shadow-sm">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
              <div className="lg:col-span-7 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-orange-600 uppercase tracking-wider">
                    {activeInsight.stage}
                  </span>
                  <span>•</span>
                  <span className="text-xs text-stone-500 font-mono">{activeInsight.source}</span>
                </div>

                <h3 className="text-xl sm:text-2xl font-bold text-stone-900">
                  {activeInsight.title}
                </h3>

                <p className="text-sm text-stone-700 leading-relaxed font-normal">
                  {activeInsight.description}
                </p>

                <div className="p-3.5 rounded-xl bg-white border border-stone-200 text-xs text-stone-800 leading-relaxed space-y-1">
                  <div className="font-bold text-stone-900 flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-orange-600" />
                    <span>How the Engine Deduce This:</span>
                  </div>
                  <div>{activeInsight.detail}</div>
                </div>
              </div>

              {/* Right 5 Cols: Mocked Raw Ground Truth Payload */}
              <div className="lg:col-span-5 bg-white/90 backdrop-blur-sm p-5 rounded-xl border border-stone-200 shadow-sm space-y-3">
                <div className="text-[10px] font-mono uppercase font-bold text-stone-500 flex items-center justify-between">
                  <span>Structured Artifact Payload</span>
                  <span className="text-emerald-700 font-bold">VERIFIED</span>
                </div>

                <div className="p-3 rounded-lg bg-stone-900 text-stone-100 font-mono text-[11px] space-y-1 overflow-x-auto">
                  <div><span className="text-orange-400">actor:</span> &quot;{activeInsight.actor}&quot;</div>
                  <div><span className="text-orange-400">timestamp:</span> &quot;{activeInsight.time}&quot;</div>
                  <div><span className="text-orange-400">provenance:</span> &quot;SHA-256 Verified&quot;</div>
                  <div><span className="text-orange-400">target_obligation:</span> &quot;#OB-002&quot;</div>
                </div>

                <div className="text-[11px] text-stone-500 italic">
                  Every decision node links back to raw immutable communication evidence.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
