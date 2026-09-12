"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Building2,
  CheckCircle2,
  AlertTriangle,
  GitFork,
  Scale,
  Brain,
  Layers,
  ArrowLeft,
  Loader2,
  ShieldAlert,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function DemoOnboardingPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleEnterDemo = async () => {
    setLoading(true);
    setError(null);
    try {
      // Safe login using standard demo credentials from backend configuration
      await login({
        email: "demo@obligation.local",
        password: "demo1234",
      });
      router.push("/dashboard");
    } catch (err: unknown) {
      console.warn("Demo login network fallback:", err);
      // Even if backend is starting up or in offline mock mode, AuthContext sets up default workspace
      router.push("/dashboard");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[85vh] flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 bg-slate-50/50">
      <div className="max-w-3xl mx-auto w-full space-y-8">
        {/* Navigation Breadcrumb */}
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Overview</span>
          </Link>
        </div>

        {/* Title Header */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-100 text-orange-800 text-xs font-bold">
            <Sparkles className="w-3.5 h-3.5 text-orange-600" />
            <span>Interactive Demonstration</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
            Explore Obligation Agent
          </h1>
          <p className="text-sm sm:text-base text-slate-600 max-w-xl mx-auto">
            We&apos;ve prepared a realistic organization workspace so you can experience the system immediately.
          </p>
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Workspace Card */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xl shadow-slate-900/5 p-6 sm:p-8 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-orange-50 border border-orange-200 flex items-center justify-center text-orange-600 shadow-xs">
                <Building2 className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-slate-900">Acme Operations</h2>
                  <span className="px-2 py-0.5 rounded-full bg-orange-100 text-orange-800 border border-orange-200 text-[10px] font-bold">
                    Demo Environment
                  </span>
                </div>
                <p className="text-xs text-slate-500">
                  Engineering, Infrastructure & Compliance Cross-Functional Team
                </p>
              </div>
            </div>

            <div className="text-xs text-slate-600 bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200/80">
              Role: <strong className="text-slate-800">Workspace Owner (Demo Operator)</strong>
            </div>
          </div>

          {/* Dataset Highlights */}
          <div className="space-y-3">
            <div className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              What&apos;s Included in this Workspace:
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-xl border border-slate-100 bg-slate-50/70 flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-slate-800">5+ Realistic Obligations</div>
                  <div className="text-slate-500 text-[11px]">Deliver v2 API spec, SOC2 package, Cutover</div>
                </div>
              </div>

              <div className="p-3 rounded-xl border border-slate-100 bg-slate-50/70 flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-slate-800">Active At-Risk & Blocked Commitments</div>
                  <div className="text-slate-500 text-[11px]">Real upstream blocker chain with delay reasoning</div>
                </div>
              </div>

              <div className="p-3 rounded-xl border border-slate-100 bg-slate-50/70 flex items-start gap-2.5">
                <GitFork className="w-4 h-4 text-orange-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-slate-800">Multi-Hop Dependency Chains</div>
                  <div className="text-slate-500 text-[11px]">Priya DB benchmark ➔ Migration plan ➔ Cutover</div>
                </div>
              </div>

              <div className="p-3 rounded-xl border border-slate-100 bg-slate-50/70 flex items-start gap-2.5">
                <Scale className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-slate-800">Reconciled Multi-Source Evidence</div>
                  <div className="text-slate-500 text-[11px]">Slack threads, Jira tickets, and Google Calendar events</div>
                </div>
              </div>

              <div className="p-3 rounded-xl border border-slate-100 bg-slate-50/70 flex items-start gap-2.5">
                <Brain className="w-4 h-4 text-orange-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-slate-800">Gemini Root-Cause Intelligence</div>
                  <div className="text-slate-500 text-[11px]">Causal explanation of why deadlines are at risk</div>
                </div>
              </div>

              <div className="p-3 rounded-xl border border-slate-100 bg-slate-50/70 flex items-start gap-2.5">
                <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-slate-800">Human Decision & Authorization</div>
                  <div className="text-slate-500 text-[11px]">Interactive review modal before executing resolutions</div>
                </div>
              </div>
            </div>
          </div>

          {/* Action CTAs */}
          <div className="pt-4 flex flex-col sm:flex-row items-center gap-3">
            <button
              onClick={handleEnterDemo}
              disabled={loading}
              className="w-full sm:flex-1 py-3.5 px-6 rounded-xl bg-orange-600 hover:bg-orange-700 text-white font-bold text-sm shadow-md shadow-orange-600/25 transition-all flex items-center justify-center gap-2 active:scale-[0.98] disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Entering Demo Environment...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Enter Demo Workspace</span>
                  <ArrowRight className="w-4 h-4 ml-0.5" />
                </>
              )}
            </button>

            <Link
              href="/login"
              className="w-full sm:w-auto py-3.5 px-5 rounded-xl border border-slate-200 hover:border-slate-300 text-slate-700 font-semibold text-xs text-center hover:bg-slate-50 transition-colors"
            >
              Use My Own Workspace
            </Link>
          </div>

          <div className="text-[11px] text-center text-slate-600 pt-1">
            Demo environment uses preconfigured standard credentials for safe exploration.
          </div>
        </div>
      </div>
    </div>
  );
}
