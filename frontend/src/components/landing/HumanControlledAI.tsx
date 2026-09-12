"use client";

import React from "react";
import { Lock, ArrowRight, ShieldCheck, CheckCircle2, UserCheck, AlertCircle } from "lucide-react";

export const HumanControlledAI: React.FC = () => {
  return (
    <section className="py-20 bg-stone-50/30 border-b border-stone-200/80 backdrop-blur-[1px]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto bg-white/85 backdrop-blur-md rounded-3xl border border-stone-200/90 p-8 sm:p-12 shadow-sm space-y-10">
          {/* Header */}
          <div className="text-center max-w-2xl mx-auto space-y-3">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-50 border border-orange-200 text-orange-800 text-xs font-bold">
              <Lock className="w-3.5 h-3.5 text-orange-600" />
              <span>Enterprise Safety Boundary</span>
            </div>
            <h2 className="text-2xl sm:text-4xl font-extrabold text-stone-900 tracking-tight text-readable-glow">
              AI Reasons and Recommends. <br />
              <span className="text-orange-600">Humans Remain in Command.</span>
            </h2>
            <p className="text-sm text-stone-600 leading-relaxed font-normal text-readable-glow-subtle">
              Autonomous agents must never trigger irreversible organizational actions in secret. Obligation Agent
              enforces an uncompromised human authorization checkpoint for every consequential intervention.
            </p>
          </div>

          {/* 6-Step Safety Architecture Pipeline */}
          <div className="flex flex-col lg:flex-row items-center justify-between gap-3 p-4 rounded-2xl bg-stone-50 border border-stone-200 text-center">
            {/* 1. Gemini */}
            <div className="p-3.5 rounded-xl bg-white border border-stone-200 w-full lg:w-auto flex-1 shadow-2xs">
              <div className="text-[10px] font-mono font-bold text-stone-500 uppercase">Input Engine</div>
              <div className="text-xs font-bold text-stone-900 mt-0.5">Google Gemini 2.5</div>
              <div className="text-[10px] text-stone-500 mt-0.5">Raw Ingestion</div>
            </div>

            <ArrowRight className="w-4 h-4 text-stone-400 rotate-90 lg:rotate-0 shrink-0" />

            {/* 2. Interpretation */}
            <div className="p-3.5 rounded-xl bg-white border border-stone-200 w-full lg:w-auto flex-1 shadow-2xs">
              <div className="text-[10px] font-mono font-bold text-stone-500 uppercase">Semantic Layer</div>
              <div className="text-xs font-bold text-stone-900 mt-0.5">Interpretation</div>
              <div className="text-[10px] text-stone-500 mt-0.5">Confidence Scoring</div>
            </div>

            <ArrowRight className="w-4 h-4 text-stone-400 rotate-90 lg:rotate-0 shrink-0" />

            {/* 3. Grounding & Validation */}
            <div className="p-3.5 rounded-xl bg-white border border-stone-200 w-full lg:w-auto flex-1 shadow-2xs">
              <div className="text-[10px] font-mono font-bold text-stone-500 uppercase">Defense Invariant</div>
              <div className="text-xs font-bold text-stone-900 mt-0.5">Grounding & Check</div>
              <div className="text-[10px] text-stone-500 mt-0.5">Anti-Hallucination</div>
            </div>

            <ArrowRight className="w-4 h-4 text-stone-400 rotate-90 lg:rotate-0 shrink-0" />

            {/* 4. Recommendation */}
            <div className="p-3.5 rounded-xl bg-orange-50 border border-orange-200 w-full lg:w-auto flex-1 shadow-2xs">
              <div className="text-[10px] font-mono font-bold text-orange-700 uppercase">Proposal</div>
              <div className="text-xs font-bold text-orange-950 mt-0.5">Remediation Plan</div>
              <div className="text-[10px] text-orange-700 mt-0.5">Drafted Intervention</div>
            </div>

            <ArrowRight className="w-4 h-4 text-stone-400 rotate-90 lg:rotate-0 shrink-0" />

            {/* 5. Human Authorization (Highlighted Checkpoint) */}
            <div className="p-3.5 rounded-xl bg-white border-2 border-orange-500 ring-4 ring-orange-500/10 w-full lg:w-auto flex-1 shadow-md scale-105">
              <div className="text-[10px] font-mono font-bold text-orange-600 uppercase flex items-center justify-center gap-1">
                <UserCheck className="w-3 h-3" />
                <span>CHECKPOINT</span>
              </div>
              <div className="text-xs font-extrabold text-stone-900 mt-0.5">Human Authorization</div>
              <div className="text-[10px] text-orange-700 font-bold mt-0.5">1-Click Sign-Off</div>
            </div>

            <ArrowRight className="w-4 h-4 text-stone-400 rotate-90 lg:rotate-0 shrink-0" />

            {/* 6. Controlled Execution */}
            <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 w-full lg:w-auto flex-1 shadow-2xs">
              <div className="text-[10px] font-mono font-bold text-emerald-700 uppercase">Audited Dispatch</div>
              <div className="text-xs font-bold text-emerald-950 mt-0.5">Controlled Action</div>
              <div className="text-[10px] text-emerald-700 mt-0.5">SHA-256 Provenance</div>
            </div>
          </div>

          {/* Core Trust Pillars */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-2">
            <div className="p-4 rounded-xl bg-stone-50 border border-stone-200 space-y-1.5">
              <div className="flex items-center gap-2 text-xs font-bold text-stone-900">
                <ShieldCheck className="w-4 h-4 text-orange-600" />
                <span>Deterministic Safety Boundary</span>
              </div>
              <p className="text-xs text-stone-600 leading-relaxed font-normal">
                Strict software invariants forbid autonomous agents from executing Slack DMs, Jira updates, or calendar alterations without affirmative human sign-off.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-stone-50 border border-stone-200 space-y-1.5">
              <div className="flex items-center gap-2 text-xs font-bold text-stone-900">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Immutable Cryptographic Audit</span>
              </div>
              <p className="text-xs text-stone-600 leading-relaxed font-normal">
                Every action proposal, modification, and execution receipt is recorded in an append-only SHA-256 hash ledger with full user attribution.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-stone-50 border border-stone-200 space-y-1.5">
              <div className="flex items-center gap-2 text-xs font-bold text-stone-900">
                <AlertCircle className="w-4 h-4 text-amber-600" />
                <span>Zero Hallucination Tolerance</span>
              </div>
              <p className="text-xs text-stone-600 leading-relaxed font-normal">
                Gemini recommendations must cite explicit upstream graph nodes and verified evidence payloads; ungrounded suggestions are rejected by policy.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
