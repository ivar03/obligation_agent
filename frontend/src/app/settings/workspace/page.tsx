"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { Save, Loader2, CheckCircle2 } from "lucide-react";

export default function WorkspaceSettingsPage() {
  const { activeWorkspace, activeRole } = useAuth();
  const [timezone, setTimezone] = useState("UTC");
  const [retentionDays, setRetentionDays] = useState(90);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (activeWorkspace) {
      fetch(`/api/workspaces/${activeWorkspace.id}/settings`)
        .then((res) => res.json())
        .then((data) => {
          if (data.timezone) setTimezone(data.timezone);
          if (data.retention_days) setRetentionDays(data.retention_days);
        })
        .catch(() => {});
    }
  }, [activeWorkspace]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace) return;
    setLoading(true);
    setSaved(false);
    try {
      const res = await fetch(`/api/workspaces/${activeWorkspace.id}/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timezone, retention_days: retentionDays }),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      }
    } catch {} finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-stone-100 border border-stone-200 rounded-2xl p-6 shadow-sm space-y-6">
      <div className="flex items-center justify-between border-b border-stone-200 pb-4">
        <div>
          <h2 className="text-sm font-bold text-stone-900">General Workspace Configuration</h2>
          <p className="text-xs text-stone-600 mt-0.5">Timezone, identifiers, and historical data retention windows.</p>
        </div>
        <span className="px-2.5 py-1 rounded text-[11px] font-semibold bg-stone-200 text-stone-700 border border-stone-300">
          Role: {activeRole || "OWNER"}
        </span>
      </div>

      <form onSubmit={handleSave} className="space-y-4 text-xs max-w-lg">
        <div>
          <label className="block font-medium text-stone-700 mb-1.5">Workspace Name</label>
          <input
            type="text"
            disabled
            value={activeWorkspace?.name || "Default Workspace"}
            className="w-full bg-stone-50/60 border border-stone-200/80 rounded-xl px-3.5 py-2.5 text-stone-600 cursor-not-allowed"
          />
        </div>

        <div>
          <label className="block font-medium text-stone-700 mb-1.5">Workspace Slug / ID</label>
          <input
            type="text"
            disabled
            value={activeWorkspace?.slug || activeWorkspace?.id || "ws-default"}
            className="w-full bg-stone-50/60 border border-stone-200/80 rounded-xl px-3.5 py-2.5 text-stone-600 cursor-not-allowed font-mono text-[11px]"
          />
        </div>

        <div>
          <label className="block font-medium text-stone-700 mb-1.5">Operating Timezone</label>
          <select
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3.5 py-2.5 text-stone-800 focus:outline-none focus:border-blue-500"
          >
            <option value="UTC">UTC (Coordinated Universal Time)</option>
            <option value="America/New_York">America/New_York (EST/EDT)</option>
            <option value="America/Chicago">America/Chicago (CST/CDT)</option>
            <option value="America/Los_Angeles">America/Los_Angeles (PST/PDT)</option>
            <option value="Europe/London">Europe/London (GMT/BST)</option>
            <option value="Europe/Berlin">Europe/Berlin (CET/CEST)</option>
            <option value="Asia/Tokyo">Asia/Tokyo (JST)</option>
          </select>
        </div>

        <div>
          <label className="block font-medium text-stone-700 mb-1.5">Data Retention Window (Days)</label>
          <input
            type="number"
            min={30}
            max={365}
            value={retentionDays}
            onChange={(e) => setRetentionDays(Number(e.target.value))}
            className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3.5 py-2.5 text-stone-800 focus:outline-none focus:border-blue-500"
          />
          <p className="text-[11px] text-stone-500 mt-1">Audit logs, event telemetry, and completed plans are preserved for this period.</p>
        </div>

        <div className="pt-2 flex items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-stone-950 rounded-xl text-xs font-semibold shadow-md transition-all active:scale-95"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            <span>Save Settings</span>
          </button>
          {saved && (
            <span className="inline-flex items-center gap-1 text-emerald-400 text-xs animate-in fade-in">
              <CheckCircle2 className="w-3.5 h-3.5" /> Saved successfully
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
