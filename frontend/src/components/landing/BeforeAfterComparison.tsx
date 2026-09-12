"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  Sparkles,
  XCircle,
} from "lucide-react";

export const BeforeAfterComparison: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"AFTER" | "BEFORE">("AFTER");

  return (
    <section id="problem" className="py-20 bg-transparent border-b border-stone-200/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-stone-100 text-stone-700 text-xs font-semibold">
            <span>The Organizational Dilemma</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-stone-900 tracking-tight text-readable-glow">
            Workplace commitments break because context fractures.
          </h2>
          <p className="text-stone-600 text-base leading-relaxed text-readable-glow-subtle">
            When commitments live across five disjointed tools, accountability only materializes
            when a deadline has already passed. Here is the operational transformation.
          </p>

          {/* Interactive Toggle Switch */}
          <div className="inline-flex p-1 rounded-xl bg-stone-100/90 backdrop-blur-sm border border-stone-200 text-xs font-semibold mt-4">
            <button
              onClick={() => setActiveTab("BEFORE")}
              className={`px-5 py-2 rounded-lg transition-all flex items-center gap-2 ${
                activeTab === "BEFORE"
                  ? "bg-white text-rose-700 shadow-sm border border-stone-200 font-bold"
                  : "text-stone-600 hover:text-stone-900"
              }`}
            >
              <XCircle className="w-4 h-4 text-rose-500" />
              <span>Before: The Fragmented Reality</span>
            </button>
            <button
              onClick={() => setActiveTab("AFTER")}
              className={`px-5 py-2 rounded-lg transition-all flex items-center gap-2 ${
                activeTab === "AFTER"
                  ? "bg-orange-600 text-white shadow-sm font-bold"
                  : "text-stone-600 hover:text-stone-900"
              }`}
            >
              <Sparkles className="w-4 h-4 text-white" />
              <span>After: Obligation Agent</span>
            </button>
          </div>
        </div>

        {/* Dynamic Interactive Transformation Container */}
        {activeTab === "BEFORE" ? (
          <div className="max-w-5xl mx-auto rounded-2xl border border-rose-200/90 bg-white/85 backdrop-blur-md p-6 sm:p-10 shadow-sm animate-in fade-in duration-300 space-y-8">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rose-200/80 pb-4">
              <div className="flex items-center gap-2 text-rose-800 font-bold text-sm">
                <AlertTriangle className="w-4 h-4 text-rose-600" />
                <span>Status Quo: Information Silos & Silent Failure Cascades</span>
              </div>
              <span className="text-xs font-mono text-rose-700 bg-white px-2.5 py-1 rounded-full border border-rose-200">
                0% Cross-Tool Causal Visibility
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative">
              {/* Step 1: Casual Promises */}
              <div className="p-5 rounded-xl bg-white border border-rose-100 shadow-xs space-y-2.5">
                <div className="w-8 h-8 rounded-lg bg-rose-100 text-rose-700 font-bold text-xs flex items-center justify-center font-mono">
                  01
                </div>
                <h4 className="text-sm font-bold text-stone-900">Ephemeral Promises</h4>
                <p className="text-xs text-stone-600 leading-relaxed">
                  Engineers promise deliverables in Slack threads, managers request estimates over email, verbal commitments vanish after Zoom calls.
                </p>
                <div className="pt-2 text-[11px] font-mono text-rose-700 bg-rose-50 p-2 rounded border border-rose-100">
                  &ldquo;I&apos;ll send benchmark numbers by Tuesday&rdquo; → Unrecorded
                </div>
              </div>

              {/* Step 2: Fragmented Signals */}
              <div className="p-5 rounded-xl bg-white border border-rose-100 shadow-xs space-y-2.5">
                <div className="w-8 h-8 rounded-lg bg-rose-100 text-rose-700 font-bold text-xs flex items-center justify-center font-mono">
                  02
                </div>
                <h4 className="text-sm font-bold text-stone-900">Silent Blockers Accumulate</h4>
                <p className="text-xs text-stone-600 leading-relaxed">
                  An upstream dependency fails. The lead mentions it in an informal channel, but Jira tickets and executive cutover schedules stay unchanged.
                </p>
                <div className="pt-2 text-[11px] font-mono text-rose-700 bg-rose-50 p-2 rounded border border-rose-100">
                  RDS IOPS throttle → Blocker unlinked to milestone
                </div>
              </div>

              {/* Step 3: Failure at the Finish Line */}
              <div className="p-5 rounded-xl bg-white border border-rose-100 shadow-xs space-y-2.5">
                <div className="w-8 h-8 rounded-lg bg-rose-100 text-rose-700 font-bold text-xs flex items-center justify-center font-mono">
                  03
                </div>
                <h4 className="text-sm font-bold text-stone-900">Missed Milestones & Panic</h4>
                <p className="text-xs text-stone-600 leading-relaxed">
                  Executive cutover review arrives. Stakeholders discover critical prerequisites were never satisfied. High-stress emergency meetings ensue.
                </p>
                <div className="pt-2 text-[11px] font-mono text-rose-700 bg-rose-50 p-2 rounded border border-rose-100">
                  Deployment delayed by 2 weeks • Reputation hit
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="max-w-5xl mx-auto rounded-2xl border border-orange-200/90 bg-white/85 backdrop-blur-md p-6 sm:p-10 shadow-sm animate-in fade-in duration-300 space-y-8">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-orange-200/80 pb-4">
              <div className="flex items-center gap-2 text-stone-900 font-bold text-sm">
                <Sparkles className="w-4 h-4 text-orange-600" />
                <span>Obligation Agent: Continuous Causal Intelligence & Unified Governance</span>
              </div>
              <span className="text-xs font-mono text-orange-800 bg-white px-2.5 py-1 rounded-full border border-orange-200 font-semibold">
                100% Deterministic Tracking
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
              {/* Step 1: Semantic Extraction */}
              <div className="p-5 rounded-xl bg-white border border-stone-200 shadow-xs space-y-2.5 hover:border-orange-300 transition-colors">
                <div className="w-8 h-8 rounded-lg bg-orange-50 text-orange-700 font-bold text-xs flex items-center justify-center font-mono border border-orange-200">
                  01
                </div>
                <h4 className="text-sm font-bold text-stone-900">Continuous Observation</h4>
                <p className="text-xs text-stone-600 leading-relaxed">
                  Natural language extraction detects obligations from Slack, Gmail, Calendar, and Jira automatically without manual data entry.
                </p>
                <div className="pt-2 text-[11px] font-mono text-emerald-700 bg-emerald-50 p-2 rounded border border-emerald-200">
                  ✓ Extracted with 95% confidence
                </div>
              </div>

              {/* Step 2: Causal Graph */}
              <div className="p-5 rounded-xl bg-white border border-stone-200 shadow-xs space-y-2.5 hover:border-orange-300 transition-colors">
                <div className="w-8 h-8 rounded-lg bg-orange-50 text-orange-700 font-bold text-xs flex items-center justify-center font-mono border border-orange-200">
                  02
                </div>
                <h4 className="text-sm font-bold text-stone-900">Causal Topology Mapping</h4>
                <p className="text-xs text-stone-600 leading-relaxed">
                  Every commitment is wired into a living dependency graph. The system immediately calculates blast radius across downstream teams.
                </p>
                <div className="pt-2 text-[11px] font-mono text-orange-800 bg-orange-50 p-2 rounded border border-orange-200">
                  ⚡ 3 downstream commitments linked
                </div>
              </div>

              {/* Step 3: Predictive Early Warning */}
              <div className="p-5 rounded-xl bg-white border border-stone-200 shadow-xs space-y-2.5 hover:border-orange-300 transition-colors">
                <div className="w-8 h-8 rounded-lg bg-orange-50 text-orange-700 font-bold text-xs flex items-center justify-center font-mono border border-orange-200">
                  03
                </div>
                <h4 className="text-sm font-bold text-stone-900">Predictive Escalation</h4>
                <p className="text-xs text-stone-600 leading-relaxed">
                  Bayesian forecasting simulates delay probabilities 48 hours in advance, isolating the root cause before failures cascade.
                </p>
                <div className="pt-2 text-[11px] font-mono text-amber-800 bg-amber-50 p-2 rounded border border-amber-200">
                  ▲ Root blocker isolated (RDS IOPS)
                </div>
              </div>

              {/* Step 4: Human-Governed Action */}
              <div className="p-5 rounded-xl bg-white border border-stone-200 shadow-xs space-y-2.5 hover:border-orange-300 transition-colors">
                <div className="w-8 h-8 rounded-lg bg-orange-50 text-orange-700 font-bold text-xs flex items-center justify-center font-mono border border-orange-200">
                  04
                </div>
                <h4 className="text-sm font-bold text-stone-900">Human-Authorized Action</h4>
                <p className="text-xs text-stone-600 leading-relaxed">
                  Generates 1-click remediation proposals. Human operators approve interventions before any consequential action is dispatched.
                </p>
                <div className="pt-2 text-[11px] font-mono text-stone-800 bg-stone-100 p-2 rounded border border-stone-200">
                  🔒 Cryptographically audited execution
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};
