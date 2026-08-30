"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Sparkles, Activity } from "lucide-react";
import { obligationsApi } from "@/lib/api/obligations";

export const Header: React.FC = () => {
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  useEffect(() => {
    obligationsApi
      .checkHealth()
      .then(() => setApiOnline(true))
      .catch(() => setApiOnline(false));
  }, []);

  return (
    <header className="h-16 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md sticky top-0 z-30 px-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="md:hidden flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white text-sm">
            OA
          </div>
          <span className="font-bold text-white text-sm">Obligation Agent</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Backend API status badge */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
            apiOnline === true
              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
              : apiOnline === false
              ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
              : "bg-zinc-800 text-zinc-400 border-zinc-700"
          }`}
          title={apiOnline === true ? "FastAPI Backend Connected" : "Backend Disconnected"}
        >
          <Activity className={`w-3 h-3 ${apiOnline ? "text-emerald-400 animate-pulse" : "text-zinc-400"}`} />
          <span className="hidden sm:inline">API</span>
          <span>{apiOnline === true ? "Connected" : apiOnline === false ? "Offline" : "Checking..."}</span>
        </div>

        {/* Capture / Analyze Quick Action */}
        <Link
          href="/capture"
          className="inline-flex items-center gap-2 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition-all shadow-md shadow-blue-600/20 active:scale-95"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Analyze Message</span>
        </Link>
      </div>
    </header>
  );
};
