"use client";

import React, { useState } from "react";
import {
  Radio,
  Brain,
  GitFork,
  AlertTriangle,
  Sparkles,
  Lock,
  CheckCircle2,
  ArrowRight,
  Zap,
} from "lucide-react";

interface Step {
  id: number;
  name: string;
  tag: string;
  headline: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  runtimeOutput: string;
  guarantee: string;
}

const STEPS: Step[] = [
  {
    id: 1,
    name: "Observe",
    tag: "Multi-Source Ingestion",
    headline: "Continuous Stream Observation",
    description: "Webhooks listen to Slack channels, Gmail threads, Google Calendar meetings, and Jira issue transitions with cryptographic verification.",
    icon: Radio,
    runtimeOutput: "Ingested Slack event: #infra channel thread from @priya",
    guarantee: "Zero-latency observation without requiring team behavior change.",
  },
  {
    id: 2,
    name: "Understand",
    tag: "Semantic Extraction",
    headline: "Unstructured NLP to Atomic Contract",
    description: "Gemini 2.5 extracts semantic obligations, attributing obligor, action, beneficiary, and target deadline with confidence scoring.",
    icon: Brain,
    runtimeOutput: "Extracted Obligation: #OB-002 • 96% Confidence Level",
    guarantee: "Filters conversational noise and chatter; captures only actionable commitments.",
  },
  {
    id: 3,
    name: "Connect",
    tag: "DAG Topology",
    headline: "Causal Dependency Graph Construction",
    description: "Wired into a live directed acyclic graph (DAG). Links prerequisite deliverables, reciprocal obligations, and downstream milestones.",
    icon: GitFork,
    runtimeOutput: "Graph Edge: OB-002 depends on OB-104 (Priya Sharma)",
    guarantee: "Instantly maps blast radiuses across multi-disciplinary teams.",
  },
  {
    id: 4,
    name: "Predict",
    tag: "Bayesian Forecasting",
    headline: "Delay & Failure Risk Simulation",
    description: "Calculates Bayesian failure probabilities using historical owner velocity, sentiment drift, and remaining time buffers.",
    icon: AlertTriangle,
    runtimeOutput: "Risk Escalation: Failure probability surged from 12% → 88%",
    guarantee: "Alerts stakeholders 24-48 hours before deadlines are compromised.",
  },
  {
    id: 5,
    name: "Recommend",
    tag: "Causal Remediation",
    headline: "Highest-Leverage Resolution Synthesis",
    description: "Gemini reasons through the causal bottleneck to propose minimal-friction, high-leverage interventions with drafted messages.",
    icon: Sparkles,
    runtimeOutput: "Plan: Re-route read traffic to replica B & dispatch Slack reminder",
    guarantee: "Actionable, grounded remediation instead of vague alerts.",
  },
  {
    id: 6,
    name: "Authorize",
    tag: "Human Governance",
    headline: "Human-in-the-Loop Sign-Off Checkpoint",
    description: "Consequential actions are paused until an authorized human operator reviews and approves the intervention receipt.",
    icon: Lock,
    runtimeOutput: "Operator Authorization Point: 1-Click Approval Required",
    guarantee: "Zero autonomous execution of impactful actions without human consent.",
  },
  {
    id: 7,
    name: "Verify",
    tag: "Cryptographic Consensus",
    headline: "Evidence Corroboration & Audit Trail",
    description: "Reconciles multi-source proof (PR merge, calendar conclusion, message confirmation) and writes an immutable SHA-256 hash record.",
    icon: CheckCircle2,
    runtimeOutput: "Verified Delivery: SHA-256 Hash b1422611e3... Validated",
    guarantee: "Tamper-evident proof of fulfillment across enterprise audits.",
  },
];

export const SignalToOutcomeFlow: React.FC = () => {
  const [activeStepId, setActiveStepId] = useState<number>(1);
  const activeStep = STEPS.find((s) => s.id === activeStepId) || STEPS[0];

  return (
    <section id="how-it-works" className="py-20 bg-transparent border-b border-stone-200/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-50 border border-orange-200 text-orange-800 text-xs font-semibold">
            <Zap className="w-3.5 h-3.5 text-orange-600" />
            <span>The 7-Step Autonomous Product Loop</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-stone-900 tracking-tight text-readable-glow">
            From Raw Signal to Verified Outcome.
          </h2>
          <p className="text-stone-600 text-base leading-relaxed text-readable-glow-subtle">
            Unlike static task lists, Obligation Agent provides continuous end-to-end intelligence:
            observing communication channels, modeling dependencies, and guiding execution with human governance.
          </p>
        </div>

        {/* 7-Step Connected Pipeline Visual Path */}
        <div className="max-w-6xl mx-auto space-y-8">
          {/* Horizontal Track for Desktop */}
          <div className="relative">
            {/* Connecting Baseline */}
            <div className="hidden lg:block absolute top-6 left-6 right-6 h-0.5 bg-stone-200 -z-1" />

            {/* Active Progress Overlay line */}
            <div
              className="hidden lg:block absolute top-6 left-6 h-0.5 bg-orange-500 transition-all duration-300 -z-1"
              style={{
                width: `${((activeStepId - 1) / (STEPS.length - 1)) * 96}%`,
              }}
            />

            {/* Stage Selector Buttons */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
              {STEPS.map((step) => {
                const Icon = step.icon;
                const isActive = step.id === activeStepId;
                const isPassed = step.id < activeStepId;

                return (
                  <button
                    key={step.id}
                    onClick={() => setActiveStepId(step.id)}
                    onMouseEnter={() => setActiveStepId(step.id)}
                    className={`p-3 rounded-xl border text-left transition-all relative flex flex-col items-center text-center space-y-2 group ${
                      isActive
                        ? "bg-orange-50/90 backdrop-blur-md border-orange-500 shadow-md ring-2 ring-orange-500/20"
                        : isPassed
                        ? "bg-white/85 backdrop-blur-md border-orange-200 hover:border-orange-300"
                        : "bg-white/80 backdrop-blur-md border-stone-200 hover:border-stone-300"
                    }`}
                  >
                    {/* Step Icon Badge */}
                    <div
                      className={`w-9 h-9 rounded-xl flex items-center justify-center font-mono font-bold text-xs transition-all ${
                        isActive
                          ? "bg-orange-600 text-white shadow-sm shadow-orange-600/30 scale-105"
                          : isPassed
                          ? "bg-orange-100 text-orange-800 border border-orange-200"
                          : "bg-stone-100 text-stone-600 border border-stone-200"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>

                    <div>
                      <div
                        className={`text-xs font-bold transition-colors ${
                          isActive ? "text-orange-950" : "text-stone-800"
                        }`}
                      >
                        {step.id}. {step.name}
                      </div>
                      <div className="text-[10px] text-stone-500 truncate">{step.tag}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Active Stage Inspector Banner */}
          <div className="rounded-2xl border border-stone-200/90 bg-white/85 backdrop-blur-md p-6 sm:p-8 shadow-sm">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
              {/* Left 7 Cols: Detailed Stage Explanation */}
              <div className="lg:col-span-7 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded-full bg-orange-100 text-orange-800 text-[11px] font-mono font-bold">
                    STEP {activeStep.id} OF 7
                  </span>
                  <span className="text-xs font-mono font-semibold text-stone-500 uppercase tracking-wider">
                    {activeStep.tag}
                  </span>
                </div>

                <h3 className="text-xl sm:text-2xl font-extrabold text-stone-900">
                  {activeStep.headline}
                </h3>

                <p className="text-sm text-stone-700 leading-relaxed">
                  {activeStep.description}
                </p>

                <div className="pt-2 text-xs text-stone-600 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span><strong>Operational Guarantee:</strong> {activeStep.guarantee}</span>
                </div>
              </div>

              {/* Right 5 Cols: Live Runtime Telemetry Mock */}
              <div className="lg:col-span-5 bg-white/90 backdrop-blur-sm p-5 rounded-xl border border-stone-200 shadow-sm space-y-3">
                <div className="text-[10px] font-mono uppercase font-bold text-stone-500 flex items-center justify-between">
                  <span>Engine Telemetry Output</span>
                  <span className="text-orange-600 font-bold">STAGE {activeStep.id}</span>
                </div>

                <div className="p-3 rounded-lg bg-stone-50 border border-stone-200 font-mono text-xs text-stone-800 space-y-1">
                  <div className="text-[10px] text-stone-500">Live Snapshot:</div>
                  <div className="text-orange-700 font-semibold">{activeStep.runtimeOutput}</div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-stone-200 text-xs">
                  <span className="text-stone-500 text-[11px]">Advance through workflow:</span>
                  <button
                    onClick={() => setActiveStepId((prev) => (prev % 7) + 1)}
                    className="inline-flex items-center gap-1 font-semibold text-orange-600 hover:text-orange-700 text-xs transition-colors"
                  >
                    <span>Next: Step {(activeStep.id % 7) + 1}</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
