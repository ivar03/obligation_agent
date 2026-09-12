"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { Bell, Save, CheckCircle2, Loader2 } from "lucide-react";

export default function NotificationsSettingsPage() {
  const { activeWorkspace } = useAuth();
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [prefs, setPrefs] = useState({
    critical_risk_detected: true,
    evidence_awaiting_confirmation: true,
    decision_plan_awaiting_approval: true,
    execution_failed: true,
    integration_disconnected: true,
    obligation_approaching_deadline: true,
  });

  useEffect(() => {
    if (activeWorkspace) {
      fetch(`/api/workspaces/${activeWorkspace.id}/settings`)
        .then((res) => res.json())
        .then((data) => {
          if (data.notification_preferences) {
            setPrefs((prev) => ({ ...prev, ...data.notification_preferences }));
          }
        })
        .catch(() => {});
    }
  }, [activeWorkspace]);

  const handleToggle = (key: keyof typeof prefs) => {
    setPrefs((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSave = async () => {
    if (!activeWorkspace) return;
    setLoading(true);
    setSaved(false);
    try {
      const res = await fetch(`/api/workspaces/${activeWorkspace.id}/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notification_preferences: prefs }),
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
      <div className="border-b border-stone-200 pb-4">
        <h2 className="text-sm font-bold text-stone-900 flex items-center gap-2">
          <Bell className="w-4 h-4 text-amber-400" />
          <span>Operator Notification Preferences</span>
        </h2>
        <p className="text-xs text-stone-600 mt-0.5">Control which proactive intelligence events trigger in-app alerts.</p>
      </div>

      <div className="space-y-3 text-xs max-w-xl">
        <label className="flex items-center justify-between p-3.5 rounded-xl bg-stone-50/50 border border-stone-200/80 cursor-pointer">
          <div>
            <div className="font-semibold text-stone-800">Critical Risk & Cascade Detected</div>
            <div className="text-stone-600 text-[11px]">When an upstream blocker endangers dependent deliverables.</div>
          </div>
          <input
            type="checkbox"
            checked={prefs.critical_risk_detected}
            onChange={() => handleToggle("critical_risk_detected")}
            className="rounded text-orange-600 focus:ring-orange-500 bg-stone-100 border-stone-300"
          />
        </label>

        <label className="flex items-center justify-between p-3.5 rounded-xl bg-stone-50/50 border border-stone-200/80 cursor-pointer">
          <div>
            <div className="font-semibold text-stone-800">Evidence Awaiting Confirmation</div>
            <div className="text-stone-600 text-[11px]">When AI correlation suggests completion evidence for human review.</div>
          </div>
          <input
            type="checkbox"
            checked={prefs.evidence_awaiting_confirmation}
            onChange={() => handleToggle("evidence_awaiting_confirmation")}
            className="rounded text-orange-600 focus:ring-orange-500 bg-stone-100 border-stone-300"
          />
        </label>

        <label className="flex items-center justify-between p-3.5 rounded-xl bg-stone-50/50 border border-stone-200/80 cursor-pointer">
          <div>
            <div className="font-semibold text-stone-800">Decision Plan Awaiting Approval</div>
            <div className="text-stone-600 text-[11px]">When a strategic resolution plan is synthesized by the reasoning layer.</div>
          </div>
          <input
            type="checkbox"
            checked={prefs.decision_plan_awaiting_approval}
            onChange={() => handleToggle("decision_plan_awaiting_approval")}
            className="rounded text-orange-600 focus:ring-orange-500 bg-stone-100 border-stone-300"
          />
        </label>

        <label className="flex items-center justify-between p-3.5 rounded-xl bg-stone-50/50 border border-stone-200/80 cursor-pointer">
          <div>
            <div className="font-semibold text-stone-800">Execution Delivery Failed</div>
            <div className="text-stone-600 text-[11px]">When a dispatched intervention encounters rate limits or provider errors.</div>
          </div>
          <input
            type="checkbox"
            checked={prefs.execution_failed}
            onChange={() => handleToggle("execution_failed")}
            className="rounded text-orange-600 focus:ring-orange-500 bg-stone-100 border-stone-300"
          />
        </label>
      </div>

      <div className="pt-2 flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow transition-all"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
          <span>Save Preferences</span>
        </button>
        {saved && (
          <span className="inline-flex items-center gap-1 text-emerald-600 text-xs animate-in fade-in">
            <CheckCircle2 className="w-3.5 h-3.5" /> Preferences saved
          </span>
        )}
      </div>
    </div>
  );
}
