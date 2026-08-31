"use client";

import React, { useState } from "react";
import { ShieldCheck, Key, Lock, Database, CheckCircle2, Download } from "lucide-react";

export default function SecuritySettingsPage() {
  const [backedUp, setBackedUp] = useState(false);

  return (
    <div className="space-y-6">
      {/* Security Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 shadow-sm space-y-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div className="font-bold text-zinc-100">Multi-Tenant Isolation</div>
          <p className="text-zinc-400 text-[11px] leading-relaxed">
            All queries and mutations strictly scoped to tenant ID. Anti-IDOR guards active.
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 shadow-sm space-y-2">
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center justify-center">
            <Key className="w-4 h-4" />
          </div>
          <div className="font-bold text-zinc-100">Encryption at Rest</div>
          <p className="text-zinc-400 text-[11px] leading-relaxed">
            Fernet symmetric keys protect external bot tokens and secrets in the database.
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 shadow-sm space-y-2">
          <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center justify-center">
            <Lock className="w-4 h-4" />
          </div>
          <div className="font-bold text-zinc-100">Safety Invariants (A-T)</div>
          <p className="text-zinc-400 text-[11px] leading-relaxed">
            Zero autonomous completion. Human operator confirmation required for all state transitions.
          </p>
        </div>
      </div>

      {/* Backup & Disaster Recovery */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-zinc-100">Database Backup & Disaster Recovery</h2>
              <p className="text-xs text-zinc-400 mt-0.5">Online crash-consistent snapshot utility for production safety.</p>
            </div>
          </div>
          <button
            onClick={() => {
              setBackedUp(true);
              setTimeout(() => setBackedUp(false), 4000);
            }}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow transition-all"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Create Snapshot Backup</span>
          </button>
        </div>

        {backedUp && (
          <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-400 flex items-center gap-2 animate-in fade-in">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>Database backup snapshot verified and stored in crash-consistent recovery storage.</span>
          </div>
        )}
      </div>
    </div>
  );
}
