"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  Brain,
  MessageSquare,
  Layers,
  Calendar,
  GitFork,
  User,
  ChevronRight,
  Zap,
} from "lucide-react";

export const HeroIntelligenceField: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState({ x: 50, y: 50 }); // percentage
  const [isHovered, setIsHovered] = useState(false);
  const [previewExpanded, setPreviewExpanded] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  // Check prefers-reduced-motion
  useEffect(() => {
    if (typeof window !== "undefined") {
      const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      setPrefersReducedMotion(mediaQuery.matches);
      const handler = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
      mediaQuery.addEventListener("change", handler);
      return () => mediaQuery.removeEventListener("change", handler);
    }
  }, []);

  // Cursor tracking within hero container
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (prefersReducedMotion || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      setMousePos({ x, y });
    },
    [prefersReducedMotion]
  );

  // Calculate subtle parallax offsets based on mouse position
  const calcParallax = (factor: number) => {
    if (prefersReducedMotion || !isHovered) return { transform: "translate(0px, 0px)" };
    const dx = (mousePos.x - 50) * factor;
    const dy = (mousePos.y - 50) * factor;
    return {
      transform: `translate3d(${dx.toFixed(2)}px, ${dy.toFixed(2)}px, 0)`,
      transition: "transform 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
    };
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setMousePos({ x: 50, y: 50 });
      }}
      className="relative overflow-hidden pt-10 pb-20 lg:pt-16 lg:pb-28 border-b border-stone-200/80 bg-transparent"
    >
      {/* 1. Ambient warm orange glow layered over master orange grid */}

      {/* 2. Soft static ambient warm orange glow behind headline */}
      <div
        className="absolute inset-0 pointer-events-none -z-10"
        style={{
          opacity: 0.75,
          background:
            "radial-gradient(ellipse 750px 420px at 50% 28%, rgba(249, 115, 22, 0.10), rgba(254, 215, 170, 0.03) 50%, transparent 75%)",
        }}
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
        {/* Hero Eyebrow, Main Headline & Subtitle */}
        <div className="text-center max-w-3xl mx-auto space-y-6">
          {/* Eyebrow */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-orange-50 border border-orange-200/90 text-orange-800 text-[11px] font-bold uppercase tracking-widest shadow-2xs">
            <Sparkles className="w-3.5 h-3.5 text-orange-600" />
            <span>Intelligence for Organizational Commitments</span>
          </div>

          {/* Main Headline with White Text Glow */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-stone-900 leading-[1.12] text-readable-glow">
            Turn scattered commitments into{" "}
            <span className="text-orange-600 underline decoration-orange-300 decoration-wavy decoration-2 underline-offset-8">
              intelligent accountability.
            </span>
          </h1>

          {/* Supporting Text with Subtle White Glow */}
          <p className="text-base sm:text-lg text-stone-600 leading-relaxed max-w-2xl mx-auto font-normal text-readable-glow-subtle">
            Obligation Agent continuously observes work across conversations, email, calendars, and issue trackers to
            model who owes what, detect what is at risk, explain why, and orchestrate human-authorized action before commitments fail.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-3">
            <Link
              href="/demo"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl bg-orange-600 hover:bg-orange-700 text-white font-semibold text-sm shadow-md shadow-orange-600/20 hover:shadow-lg hover:shadow-orange-600/30 hover:-translate-y-0.5 active:translate-y-0 transition-all"
            >
              <Sparkles className="w-4 h-4" />
              <span>Try the Demo</span>
              <ArrowRight className="w-4 h-4 ml-0.5" />
            </Link>

            <Link
              href="/login"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-white hover:bg-stone-50 text-stone-700 font-semibold text-sm border border-stone-300 shadow-2xs hover:border-stone-400 transition-all"
            >
              <span>Sign In</span>
            </Link>

            <a
              href="#how-it-works"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-4 py-3.5 rounded-xl text-stone-500 hover:text-stone-900 text-xs font-semibold transition-colors"
            >
              <span>See the 7-Step Loop</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </a>
          </div>

          <div className="text-[11px] text-stone-500 font-medium">
            No credit card or setup required • Preloaded with 14 realistic enterprise commitments
          </div>
        </div>

        {/* ========================================================================= */}
        {/* INTERACTIVE OBLIGATION INTELLIGENCE FIELD & PRODUCT PREVIEW              */}
        {/* ========================================================================= */}
        <div className="mt-16 max-w-5xl mx-auto relative">
          {/* Floating Telemetry Chips (Constellation around the preview) */}
          {/* <div
            style={calcParallax(-0.15)}
            className="hidden lg:flex absolute -top-8 -left-8 z-20 items-center gap-2 px-3 py-1.5 rounded-xl bg-white/85 backdrop-blur-md border border-stone-200/90 shadow-md text-xs font-mono font-medium text-stone-800"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-stone-500 text-[10px] uppercase font-bold tracking-wider">OBSERVED:</span>
            <span>Slack promise in #infra</span>
            <span className="px-1.5 py-0.2 rounded bg-orange-50 text-orange-700 text-[10px] font-bold border border-orange-200">
              96% CONF
            </span>
          </div>

          <div
            style={calcParallax(0.2)}
            className="hidden lg:flex absolute -top-6 -right-6 z-20 items-center gap-2 px-3 py-1.5 rounded-xl bg-white/85 backdrop-blur-md border border-stone-200/90 shadow-md text-xs font-mono font-medium text-stone-800"
          >
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
            <span className="text-stone-500 text-[10px] uppercase font-bold tracking-wider">ROOT BLOCKER:</span>
            <span>Jira INFRA-402 Timeout</span>
            <span className="px-1.5 py-0.2 rounded bg-rose-50 text-rose-700 text-[10px] font-bold border border-rose-200">
              OVERDUE
            </span>
          </div>

          <div
            style={calcParallax(-0.1)}
            className="hidden lg:flex absolute -bottom-6 -left-6 z-20 items-center gap-2 px-3 py-1.5 rounded-xl bg-white/85 backdrop-blur-md border border-stone-200/90 shadow-md text-xs font-mono font-medium text-stone-800"
          >
            <GitFork className="w-3.5 h-3.5 text-orange-600" />
            <span className="text-stone-500 text-[10px] uppercase font-bold tracking-wider">DAG TOPOLOGY:</span>
            <span>3 Downstream Releases Protected</span>
          </div>

          <div
            style={calcParallax(0.18)}
            className="hidden lg:flex absolute -bottom-6 -right-8 z-20 items-center gap-2 px-3 py-1.5 rounded-xl bg-white/85 backdrop-blur-md border border-stone-200/90 shadow-md text-xs font-mono font-medium text-stone-800"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span className="text-stone-500 text-[10px] uppercase font-bold tracking-wider">GOVERNANCE:</span>
            <span>Human Authorization Required</span>
          </div> */}

          {/* Interactive Miniature Product Preview Card */}
          <div
            onMouseEnter={() => setPreviewExpanded(true)}
            onMouseLeave={() => setPreviewExpanded(false)}
            className="rounded-2xl border border-stone-200/90 bg-white/85 backdrop-blur-md p-3 sm:p-5 shadow-xl shadow-stone-900/5 transition-all duration-300 hover:border-orange-300 hover:shadow-2xl hover:shadow-orange-500/10 cursor-default"
          >
            {/* Top Toolbar / Status Header */}
            <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-stone-200">
              <div className="flex items-center gap-3">
                <span className="flex h-3 w-3 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-orange-600" />
                </span>
                <div>
                  <div className="text-xs font-bold text-stone-900 uppercase tracking-wider flex items-center gap-1.5">
                    <span>Active Commitment Telemetry</span>
                    <span className="px-1.5 py-0.2 rounded bg-stone-100 text-stone-600 text-[10px] font-mono font-normal">
                      #OB-002
                    </span>
                  </div>
                  <div className="text-[11px] text-stone-500">Continuous causal observation across 4 tools</div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-full bg-rose-50 text-rose-700 border border-rose-200 text-xs font-bold flex items-center gap-1.5 shadow-2xs">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                  <span>BLOCKED (Upstream Failure)</span>
                </span>
                <span className="hidden sm:inline-flex px-2.5 py-1 rounded-full bg-orange-50 text-orange-700 border border-orange-200 text-xs font-bold font-mono">
                  Risk Score: 88%
                </span>
              </div>
            </div>

            {/* Core Card Content Grid */}
            <div className="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-5">
              {/* Left 2 Cols: Obligation + Blocker + AI Recommendation */}
              <div className="lg:col-span-2 space-y-4">
                {/* Obligation Statement */}
                <div className="bg-stone-50/80 p-4 rounded-xl border border-stone-200/80 space-y-1">
                  <div className="flex items-center justify-between text-xs text-stone-500">
                    <span className="font-semibold uppercase tracking-wider text-[10px] text-orange-600">
                      Commitment Under Governance
                    </span>
                    <span className="font-mono text-stone-600 text-[11px]">Due Today • 5:00 PM</span>
                  </div>
                  <div className="text-base sm:text-lg font-bold text-stone-900 leading-snug">
                    Finalize Infrastructure Migration Plan & Cutover Schedule
                  </div>
                  <div className="flex flex-wrap items-center gap-3 pt-1 text-xs text-stone-600">
                    <span className="flex items-center gap-1">
                      <User className="w-3.5 h-3.5 text-stone-400" />
                      Owner: <strong className="text-stone-800">You (Demo Operator)</strong>
                    </span>
                    <span>•</span>
                    <span>
                      Beneficiary: <strong className="text-stone-800">Executive Leadership</strong>
                    </span>
                  </div>
                </div>

                {/* Root Cause Blocker Box */}
                <div className="p-3.5 rounded-xl bg-rose-50/60 border border-rose-200/80 space-y-1.5">
                  <div className="text-xs font-bold text-rose-900 flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                      Primary Root Cause: Upstream Dependency Overdue
                    </span>
                    <span className="text-[10px] font-mono uppercase bg-white/80 px-1.5 py-0.5 rounded text-rose-800 border border-rose-200">
                      1 Hop Upstream
                    </span>
                  </div>
                  <p className="text-xs text-stone-700 leading-relaxed">
                    Blocked by <strong>Priya Sharma</strong> on &ldquo;Provide Staging Database Benchmark Results&rdquo; (overdue by 18 hours). Benchmarking suite timed out on RDS read replicas.
                  </p>
                </div>

                {/* Gemini Recommendation Box */}
                <div className="p-3.5 rounded-xl bg-[#FFF7ED] border border-orange-200 space-y-2">
                  <div className="text-xs font-bold text-orange-900 flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <Brain className="w-3.5 h-3.5 text-orange-700" />
                      Gemini Grounded Remediation Recommendation
                    </span>
                    <span className="text-[10px] font-mono text-orange-800 bg-white px-2 py-0.5 rounded border border-orange-200">
                      Human Sign-Off Needed
                    </span>
                  </div>
                  <p className="text-xs text-stone-800 leading-relaxed">
                    Re-run benchmarking suite against secondary replica with relaxed timeouts before escalating cutover schedule. Protects 2 downstream enterprise releases.
                  </p>

                  <div className="flex items-center justify-between pt-1 border-t border-orange-200/60">
                    <span className="text-[11px] font-mono text-orange-700 font-semibold">
                      Action Type: DISPATCH_SLACK_INTERVENTION
                    </span>
                    <Link
                      href="/demo"
                      className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold shadow-2xs transition-colors"
                    >
                      <Zap className="w-3 h-3" />
                      <span>Review & Authorize</span>
                    </Link>
                  </div>
                </div>
              </div>

              {/* Right Column: Reconciled Evidence & Deep Telemetry */}
              <div className="bg-stone-50/80 p-4 rounded-xl border border-stone-200/80 flex flex-col justify-between space-y-4">
                <div>
                  <div className="text-xs font-bold text-stone-800 uppercase tracking-wider mb-2 flex items-center justify-between">
                    <span>Reconciled Evidence</span>
                    <span className="text-[10px] font-mono text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                      3 Consensus
                    </span>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="flex items-center gap-2 p-2 rounded-lg bg-white border border-stone-200 shadow-2xs">
                      <div className="w-5 h-5 rounded-md bg-[#4A154B]/10 flex items-center justify-center shrink-0">
                        <MessageSquare className="w-3 h-3 text-[#4A154B]" />
                      </div>
                      <div className="truncate">
                        <div className="font-semibold text-stone-800 truncate">Slack #dev-infra</div>
                        <div className="text-[10px] text-stone-500 truncate">&ldquo;Benchmark suite stalled at 82%&rdquo;</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 p-2 rounded-lg bg-white border border-stone-200 shadow-2xs">
                      <div className="w-5 h-5 rounded-md bg-[#0052CC]/10 flex items-center justify-center shrink-0">
                        <Layers className="w-3 h-3 text-[#0052CC]" />
                      </div>
                      <div className="truncate">
                        <div className="font-semibold text-stone-800 truncate">Jira INFRA-402</div>
                        <div className="text-[10px] text-stone-500 truncate">Status: Blocked • Priority: High</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 p-2 rounded-lg bg-white border border-stone-200 shadow-2xs">
                      <div className="w-5 h-5 rounded-md bg-amber-100 flex items-center justify-center shrink-0">
                        <Calendar className="w-3 h-3 text-amber-700" />
                      </div>
                      <div className="truncate">
                        <div className="font-semibold text-stone-800 truncate">Google Calendar</div>
                        <div className="text-[10px] text-stone-500 truncate">Production Cutover (Tomorrow 9am)</div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Expanded Telemetry reveal on hover */}
                <div
                  className={`p-3 rounded-lg bg-white border border-stone-200 text-xs space-y-1.5 transition-all duration-300 ${
                    previewExpanded ? "opacity-100 scale-100" : "opacity-90"
                  }`}
                >
                  <div className="text-[10px] uppercase font-bold text-stone-500 flex items-center justify-between">
                    <span>Deep Graph Telemetry</span>
                    <span className="text-orange-600 font-mono">LIVE</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                    <div>
                      <span className="text-stone-500">Max Depth:</span> <strong className="text-stone-900">3 Hops</strong>
                    </div>
                    <div>
                      <span className="text-stone-500">Blast Radius:</span> <strong className="text-stone-900">4 Owners</strong>
                    </div>
                    <div>
                      <span className="text-stone-500">Calibration:</span> <strong className="text-emerald-700">0.038 Brier</strong>
                    </div>
                    <div>
                      <span className="text-stone-500">Audit Proof:</span> <strong className="text-stone-900">SHA-256</strong>
                    </div>
                  </div>
                </div>

                <Link
                  href="/demo"
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-3.5 rounded-xl bg-orange-600 hover:bg-orange-700 text-white font-semibold text-xs shadow-xs hover:shadow transition-all"
                >
                  <span>Explore in Live Demo</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
