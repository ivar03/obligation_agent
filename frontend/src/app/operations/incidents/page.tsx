"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  RefreshCw,
  CheckCircle2,
  Sliders,
  ArrowUpRight,
} from "lucide-react";

interface OperationalAlert {
  id: string;
  alert_name: string;
  alert_type: string;
  severity: string;
  status: string;
  summary: string;
  details: Record<string, unknown>;
  fingerprint: string;
  trace_id?: string;
  acknowledged_by?: string;
  acknowledged_at?: string;
  resolved_at?: string;
  created_at: string;
}


import { opsApi } from "@/lib/api/obligations";

export default function OperationalIncidentsPage() {
  const [alerts, setAlerts] = useState<OperationalAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const json = await opsApi.getAlerts<OperationalAlert>();
      setAlerts(json || []);
    } catch (err) {
      console.error("Failed to load operational alerts", err);
    } finally {
      setLoading(false);
    }
  };

  const evaluateAlerts = async () => {
    setEvaluating(true);
    try {
      await opsApi.evaluateAlerts();
      await fetchAlerts();
    } catch (err) {
      console.error("Failed to evaluate alerts", err);
    } finally {
      setEvaluating(false);
    }
  };

  const handleAction = async (alertId: string, action: string) => {
    setActionLoading(alertId);
    try {
      await opsApi.actionAlert(alertId, { action, reason: "Operator manual action" });
      await fetchAlerts();
    } catch (err) {
      console.error("Failed to update alert status", err);
    } finally {
      setActionLoading(null);
    }
  };


  useEffect(() => {
    fetchAlerts();
  }, []);

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-stone-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Link
              href="/operations"
              className="p-1.5 rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-700 border border-stone-300 transition-colors mr-1"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <h1 className="text-2xl font-bold tracking-tight text-stone-900 flex items-center gap-2">
              <AlertTriangle className="w-6 h-6 text-amber-400" />
              Operational Alerts & Incident Triage
            </h1>
          </div>
          <p className="text-xs text-stone-600 mt-1">
            Deterministic alert evaluation engine for DLQ backlogs, queue latency, circuit breakers, and worker staleness.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={evaluateAlerts}
            disabled={evaluating}
            className="px-3 py-1.5 rounded-lg bg-blue-700 hover:bg-blue-600 text-stone-950 text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <Sliders className={`w-3.5 h-3.5 ${evaluating ? "animate-spin" : ""}`} />
            Evaluate Alert Rules
          </button>
          <button
            onClick={fetchAlerts}
            disabled={loading}
            className="p-2 rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-700 border border-stone-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Alert List */}
      <div className="space-y-4">
        {loading ? (
          <div className="py-12 text-center text-xs text-stone-500 bg-stone-100/40 rounded-xl border border-stone-200">
            Loading operational alerts...
          </div>
        ) : alerts.length === 0 ? (
          <div className="py-12 text-center text-xs text-stone-600 bg-stone-100/40 rounded-xl border border-stone-200 space-y-2">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
            <div className="font-semibold text-stone-800">Zero Active Incidents</div>
            <p className="text-stone-500">All subsystems are operating normally within threshold bounds.</p>
          </div>
        ) : (
          alerts.map((a) => (
            <div
              key={a.id}
              className={`p-5 rounded-xl border transition-colors ${
                a.status === "OPEN"
                  ? "bg-stone-100/90 border-amber-500/40 shadow-lg shadow-amber-950/10"
                  : a.status === "ACKNOWLEDGED"
                  ? "bg-stone-100/60 border-blue-600/30"
                  : "bg-stone-100/30 border-stone-200 opacity-70"
              }`}
            >
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-stone-200/80 pb-3">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono ${
                      a.severity === "CRITICAL"
                        ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                        : a.severity === "ERROR"
                        ? "bg-rose-500/10 text-rose-400"
                        : "bg-amber-500/10 text-amber-400"
                    }`}
                  >
                    {a.severity}
                  </span>
                  <span className="text-sm font-semibold text-stone-900">{a.alert_name}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-stone-200 text-stone-600 border border-stone-300">
                    {a.alert_type}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-semibold font-mono ${
                      a.status === "OPEN"
                        ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                        : a.status === "ACKNOWLEDGED"
                        ? "bg-blue-600/10 text-blue-500 border border-blue-600/20"
                        : "bg-emerald-500/10 text-emerald-400"
                    }`}
                  >
                    {a.status}
                  </span>
                </div>
              </div>

              <div className="py-3 text-xs text-stone-700 font-sans">{a.summary}</div>

              {a.details && Object.keys(a.details).length > 0 && (
                <pre className="p-2.5 rounded bg-stone-50 border border-stone-200 text-[11px] font-mono text-stone-600 overflow-x-auto max-h-32 mb-3">
                  {JSON.stringify(a.details, null, 2)}
                </pre>
              )}

              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-3 border-t border-stone-200/60 text-[11px] font-mono text-stone-500">
                <div className="flex items-center gap-3">
                  <span>Fingerprint: {a.fingerprint.slice(0, 10)}...</span>
                  <span>Created: {new Date(a.created_at).toLocaleTimeString()}</span>
                  {a.trace_id && (
                    <Link
                      href={`/operations/traces/${encodeURIComponent(a.trace_id)}`}
                      className="text-cyan-400 hover:text-cyan-300 flex items-center gap-0.5"
                    >
                      Trace <ArrowUpRight className="w-3 h-3" />
                    </Link>
                  )}
                </div>

                {/* Operator Triage Actions */}
                <div className="flex items-center gap-2">
                  {a.status === "OPEN" && (
                    <button
                      onClick={() => handleAction(a.id, "acknowledge")}
                      disabled={actionLoading === a.id}
                      className="px-2.5 py-1 rounded bg-blue-700/20 hover:bg-blue-700/30 text-blue-600 border border-blue-600/30 text-xs font-semibold transition-colors"
                    >
                      Acknowledge
                    </button>
                  )}
                  {a.status !== "RESOLVED" && (
                    <button
                      onClick={() => handleAction(a.id, "resolve")}
                      disabled={actionLoading === a.id}
                      className="px-2.5 py-1 rounded bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-semibold transition-colors"
                    >
                      Resolve
                    </button>
                  )}
                  {a.status !== "SUPPRESSED" && (
                    <button
                      onClick={() => handleAction(a.id, "suppress")}
                      disabled={actionLoading === a.id}
                      className="px-2.5 py-1 rounded bg-stone-200 hover:bg-stone-300 text-stone-600 text-xs transition-colors"
                    >
                      Suppress
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
