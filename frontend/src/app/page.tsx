"use client";

import React from "react";
import Link from "next/link";
import { Sparkles, ArrowRight } from "lucide-react";
import { HeroIntelligenceField } from "@/components/landing/HeroIntelligenceField";
import { TrustProofStrip } from "@/components/landing/TrustProofStrip";
import { BeforeAfterComparison } from "@/components/landing/BeforeAfterComparison";
import { InteractiveObligationObject } from "@/components/landing/InteractiveObligationObject";
import { SignalToOutcomeFlow } from "@/components/landing/SignalToOutcomeFlow";
import { CausalShowcase } from "@/components/landing/CausalShowcase";
import { HumanControlledAI } from "@/components/landing/HumanControlledAI";
import { LandingGridBackground } from "@/components/landing/LandingGridBackground";

export default function LandingPage() {
  return (
    <LandingGridBackground>
      <div className="text-stone-900 selection:bg-orange-100 selection:text-orange-900 min-h-screen">
      {/* 1. HERO SECTION: Cursor-Reactive Constellation, Subtle Grid & Miniature Preview */}
      <HeroIntelligenceField />

      {/* 2. TRUST / PROOF STRIP: Multi-Source Ingestion Integrations */}
      <TrustProofStrip />

      {/* 3. THE PROBLEM: Visual Transformation (Before vs After) */}
      <BeforeAfterComparison />

      {/* 4. THE CORE INSIGHT: Interactive 8-Dimension Obligation Object */}
      <InteractiveObligationObject />

      {/* 5. HOW IT WORKS: 7-Step Autonomous Product Loop */}
      <SignalToOutcomeFlow />

      {/* 6. PRODUCT INTELLIGENCE: Connected Causal Graph Showcase */}
      <CausalShowcase />

      {/* 7. ENTERPRISE SAFETY BOUNDARY: Human-Controlled AI */}
      <HumanControlledAI />

      {/* 8. FINAL CTA: Clean, Focused, Warm Orange Action */}
      <section className="py-20 lg:py-28 bg-gradient-to-b from-white/80 via-orange-50/50 to-orange-100/70 border-t border-stone-200/80">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-50 border border-orange-200 text-orange-800 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5 text-orange-600" />
            <span>Experience Intelligent Accountability</span>
          </div>

          <h2 className="text-3xl sm:text-5xl font-extrabold text-stone-900 tracking-tight leading-tight text-readable-glow">
            See your organization&apos;s commitments clearly.
          </h2>

          <p className="text-stone-600 text-base sm:text-lg max-w-xl mx-auto leading-relaxed font-normal text-readable-glow-subtle">
            Explore a fully populated live enterprise workspace: inspect 14 realistic commitments, navigate the causal dependency chain, verify reconciled evidence, and authorize an AI remediation proposal.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-3">
            <Link
              href="/demo"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-orange-600 hover:bg-orange-700 text-white font-bold text-sm shadow-md shadow-orange-600/20 hover:shadow-xl hover:shadow-orange-600/30 hover:-translate-y-0.5 active:translate-y-0 transition-all"
            >
              <Sparkles className="w-4 h-4" />
              <span>Try the Demo</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </Link>

            <Link
              href="/login"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-7 py-4 rounded-xl bg-white hover:bg-stone-50 text-stone-700 font-semibold text-sm border border-stone-300 shadow-2xs hover:border-stone-400 transition-all"
            >
              <span>Sign In</span>
            </Link>
          </div>

          <div className="text-xs text-stone-500 font-medium pt-2">
            No credit card or setup required • Preloaded with realistic enterprise commitments
          </div>
        </div>
      </section>
      </div>
    </LandingGridBackground>
  );
}
