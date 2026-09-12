"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Sparkles, X, ArrowRight, Building2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export const DemoBanner: React.FC = () => {
  const [dismissed, setDismissed] = useState(false);
  const { activeWorkspace, user } = useAuth();

  const isDemo =
    activeWorkspace?.id === "ws-default" ||
    activeWorkspace?.slug === "demo-workspace" ||
    activeWorkspace?.name?.toLowerCase().includes("demo") ||
    user?.email === "demo@obligation.local";

  if (!isDemo || dismissed) return null;

  return (
    <div className="bg-gradient-to-r from-orange-50 via-amber-50 to-orange-50 border-b border-orange-200/80 px-4 py-2 text-xs text-slate-800 transition-all">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="flex h-2 w-2 relative shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-orange-500"></span>
          </span>
          <p className="truncate text-xs font-medium text-slate-800">
            <strong className="font-semibold text-orange-950">Demo Environment:</strong> You&apos;re exploring the{" "}
            <span className="font-semibold text-orange-800">Acme Operations</span> realistic workspace with live causal graphs, evidence, and Gemini recommendations.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Link
            href="/obligations/ob-demo-blocked"
            className="hidden sm:inline-flex items-center gap-1 font-semibold text-orange-700 hover:text-orange-900 underline underline-offset-2 transition-colors"
          >
            <span>Inspect Priority Blocker</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
          <button
            onClick={() => setDismissed(true)}
            className="text-slate-400 hover:text-slate-600 p-0.5 rounded transition-colors"
            title="Dismiss notice"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
