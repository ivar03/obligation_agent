"use client";

import React, { useState } from "react";
import {
  User,
  CheckCircle2,
  Clock,
  GitFork,
  Scale,
  AlertTriangle,
  Brain,
  Sparkles,
} from "lucide-react";

interface Dimension {
  id: string;
  pillar: string;
  title: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  badge: string;
  description: string;
  dataModelField: string;
  liveExample: string;
  whyItMatters: string;
}

const DIMENSIONS: Dimension[] = [
  {
    id: "who",
    pillar: "WHO",
    title: "The Obligor",
    subtitle: "Explicit Accountable Individual",
    icon: User,
    color: "text-orange-600 bg-orange-50 border-orange-200",
    badge: "Identity & Attribution",
    description: "The specific individual or bounded team responsible for delivering the commitment.",
    dataModelField: "obligation.owner (User ID & Slack Handle)",
    liveExample: "Rahul Verma (@rahul.infra • Tech Lead)",
    whyItMatters: "Eliminates diffused responsibility ('the team will handle it') by anchoring commitment to a named human.",
  },
  {
    id: "what",
    pillar: "WHAT",
    title: "The Action",
    subtitle: "Atomic, Verifiable Deliverable",
    icon: CheckCircle2,
    color: "text-stone-700 bg-stone-100 border-stone-200",
    badge: "Semantic Contract",
    description: "An unambiguous, verifiable outcome with clear conditions of satisfaction.",
    dataModelField: "obligation.action & description",
    liveExample: "Execute Staging Database Benchmark & Submit Latency Report",
    whyItMatters: "Distinguishes actionable commitments from open-ended intentions or conversational chatter.",
  },
  {
    id: "to_whom",
    pillar: "TO WHOM",
    title: "The Beneficiary",
    subtitle: "Relying Stakeholder",
    icon: User,
    color: "text-stone-700 bg-stone-100 border-stone-200",
    badge: "Reciprocal Partner",
    description: "The customer, lead, or team whose downstream milestones depend on this deliverable.",
    dataModelField: "obligation.beneficiary (Stakeholder ID)",
    liveExample: "Sarah Jenkins (VP Engineering • Lead Stakeholder)",
    whyItMatters: "Enforces reciprocity: every obligation has an expectant beneficiary who receives notifications and verifies fulfillment.",
  },
  {
    id: "when",
    pillar: "WHEN",
    title: "Temporal Horizon",
    subtitle: "Explicit Deadline with Drift Alerts",
    icon: Clock,
    color: "text-amber-700 bg-amber-50 border-amber-200",
    badge: "Temporal Engine",
    description: "Calculated target time horizon synchronized with Google Calendar and working schedules.",
    dataModelField: "obligation.deadline (UTC ISO-8601)",
    liveExample: "Today • 5:00 PM UTC (3 hours remaining)",
    whyItMatters: "Enables early drift detection and proactive countdown monitoring long before standard status meetings.",
  },
  {
    id: "depends_on",
    pillar: "DEPENDS ON",
    title: "Causal Graph",
    subtitle: "Upstream Blockers & Downstream Cascade",
    icon: GitFork,
    color: "text-orange-600 bg-orange-50 border-orange-200",
    badge: "DAG Topology",
    description: "Directed acyclic graph edges linking prerequisite deliverables across disparate systems.",
    dataModelField: "obligation_edges (from_id → to_id, type: DEPENDS_ON)",
    liveExample: "Prerequisite: Priya Sharma (Jira INFRA-402 Database Benchmark)",
    whyItMatters: "Reveals hidden blast radiuses: when a low-level task stalls, the system traces every high-level epic at risk.",
  },
  {
    id: "proves_it",
    pillar: "PROVES IT",
    title: "Reconciled Evidence",
    subtitle: "Multi-Source Consensus Verification",
    icon: Scale,
    color: "text-emerald-700 bg-emerald-50 border-emerald-200",
    badge: "Truth Reconciliation",
    description: "Cross-correlated artifacts from Slack messages, PR merges, Jira transitions, and Gmail confirmations.",
    dataModelField: "evidence_records & reconciliation_events",
    liveExample: "Consensus: GitHub PR #842 Merged + Slack Confirmation in #infra",
    whyItMatters: "Prevents false claims of completion by requiring multi-source corroborating proof before marking resolved.",
  },
  {
    id: "at_risk",
    pillar: "AT RISK",
    title: "Predictive Intelligence",
    subtitle: "Bayesian Delay Forecasting",
    icon: AlertTriangle,
    color: "text-rose-700 bg-rose-50 border-rose-200",
    badge: "Adaptive Prediction",
    description: "Calibrated probability of failure computed using historical velocity, workload, and sentiment drift.",
    dataModelField: "predictions (failure_probability: 0.88, confidence: 0.92)",
    liveExample: "88% Failure Probability • Primary Cause: RDS Read Replica Latency",
    whyItMatters: "Allows proactive intervention 24-48 hours before failure, turning reactive firefighting into planned adjustments.",
  },
  {
    id: "next_step",
    pillar: "NEXT STEP",
    title: "Controlled Action",
    subtitle: "Human-Authorized Intervention",
    icon: Brain,
    color: "text-orange-600 bg-orange-50 border-orange-200",
    badge: "Grounded Remediation",
    description: "Contextually synthesized remediation plan ready for 1-click human operator approval.",
    dataModelField: "decision_plans & execution_records",
    liveExample: "Re-route read traffic to secondary replica; notify Priya via Slack",
    whyItMatters: "Closes the loop from observation to action while keeping human judgment strictly in command.",
  },
];

export const InteractiveObligationObject: React.FC = () => {
  const [selectedDimension, setSelectedDimension] = useState<Dimension>(DIMENSIONS[0]);

  return (
    <section id="insight" className="py-20 bg-stone-50/30 border-b border-stone-200/80 backdrop-blur-[1px]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-50 border border-orange-200 text-orange-800 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5 text-orange-600" />
            <span>The Core Insight</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-stone-900 tracking-tight text-readable-glow">
            The Obligation is the Atomic Unit of Work.
          </h2>
          <p className="text-stone-600 text-base leading-relaxed text-readable-glow-subtle">
            Tasks, tickets, and messages are ephemeral representations. The fundamental truth of enterprise execution
            is the reciprocal commitment between two parties. When you model its 8 dimensions, organizational ambiguity vanishes.
          </p>
        </div>

        {/* Interactive Centerpiece Container */}
        <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Left / Center 7 Cols: The 8-Dimension Constellation Grid */}
          <div className="lg:col-span-7 space-y-4">
            <div className="text-xs font-mono font-bold uppercase tracking-wider text-stone-500 mb-2 flex items-center justify-between">
              <span>Select any dimension to inspect the data model:</span>
              <span className="text-orange-600">8 Dimensions Modeled</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {DIMENSIONS.map((dim) => {
                const Icon = dim.icon;
                const isSelected = selectedDimension.id === dim.id;

                return (
                  <button
                    key={dim.id}
                    onClick={() => setSelectedDimension(dim)}
                    onMouseEnter={() => setSelectedDimension(dim)}
                    className={`p-3.5 rounded-xl border text-left transition-all relative flex flex-col justify-between h-28 ${
                      isSelected
                        ? "bg-white/95 backdrop-blur-md border-orange-500 shadow-md ring-2 ring-orange-500/20 scale-[1.02]"
                        : "bg-white/80 backdrop-blur-sm border-stone-200 hover:border-orange-300 hover:bg-white/95"
                    }`}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span
                        className={`text-[10px] font-mono font-black tracking-wider ${
                          isSelected ? "text-orange-600" : "text-stone-400"
                        }`}
                      >
                        {dim.pillar}
                      </span>
                      <div
                        className={`p-1 rounded-md border ${
                          isSelected ? "bg-orange-50 border-orange-200 text-orange-700" : "bg-stone-50 border-stone-200 text-stone-600"
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                      </div>
                    </div>

                    <div>
                      <div className="text-xs font-bold text-stone-900 leading-tight">{dim.title}</div>
                      <div className="text-[10px] text-stone-500 truncate mt-0.5">{dim.badge}</div>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Central Obligation Card Anchor */}
            <div className="p-4 rounded-xl bg-white/85 backdrop-blur-md border border-stone-200 shadow-sm flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-orange-600 text-white flex items-center justify-center font-bold text-xs shadow-2xs">
                  OB
                </div>
                <div>
                  <div className="text-xs font-bold text-stone-900">
                    Live Obligation: #OB-002 (Infrastructure Migration Plan)
                  </div>
                  <div className="text-[11px] text-stone-500">
                    All 8 dimensions continuously synchronized across Slack, Jira, and Calendar
                  </div>
                </div>
              </div>
              <span className="hidden sm:inline-flex px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold font-mono">
                Active Governance
              </span>
            </div>
          </div>

          {/* Right 5 Cols: Deep Inspector Card for Selected Dimension */}
          <div className="lg:col-span-5">
            <div className="p-6 rounded-2xl bg-white/85 backdrop-blur-md border border-stone-200 shadow-lg shadow-stone-900/5 space-y-4 animate-in fade-in duration-200">
              <div className="flex items-center justify-between border-b border-stone-200 pb-3">
                <div className="flex items-center gap-2">
                  <div className={`p-1.5 rounded-lg border ${selectedDimension.color}`}>
                    <selectedDimension.icon className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-orange-600">
                      DIMENSION: {selectedDimension.pillar}
                    </span>
                    <h3 className="text-base font-bold text-stone-900 leading-tight">
                      {selectedDimension.title}
                    </h3>
                  </div>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-stone-100 text-stone-700 font-semibold">
                  {selectedDimension.badge}
                </span>
              </div>

              <p className="text-xs text-stone-700 leading-relaxed font-normal">
                {selectedDimension.description}
              </p>

              {/* Data Model Field */}
              <div className="p-3 rounded-lg bg-stone-50 border border-stone-200 space-y-1">
                <div className="text-[10px] font-mono font-bold uppercase text-stone-500">
                  Data Model Specification
                </div>
                <code className="text-xs font-mono text-orange-700 font-semibold block break-all">
                  {selectedDimension.dataModelField}
                </code>
              </div>

              {/* Live Workspace Instance */}
              <div className="p-3 rounded-lg bg-orange-50/50 border border-orange-200/80 space-y-1">
                <div className="text-[10px] font-mono font-bold uppercase text-orange-800">
                  Concrete Live Instance (#OB-002)
                </div>
                <div className="text-xs font-semibold text-stone-900">
                  {selectedDimension.liveExample}
                </div>
              </div>

              {/* Operational Value */}
              <div className="pt-2 border-t border-stone-200/80 text-xs text-stone-600 leading-relaxed">
                <strong className="text-stone-900">Why It Matters:</strong> {selectedDimension.whyItMatters}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
