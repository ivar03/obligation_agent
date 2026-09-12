"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  RefreshCw,
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  Sliders,
} from "lucide-react";
import { opsApi } from "@/lib/api/obligations";

interface AlertRecord {
  id: string;
  fingerprint: string;
  alert_name: string;
  alert_type: string;
  severity: "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  status: "OPEN" | "ACKNOWLEDGED" | "RESOLVED" | "SUPPRESSED";
  summary: string;
  details: Record<string, unknown>;
  trace_id?: string;
  created_at: string;
  acknowledged_at?: string;
  resolved_at?: string;
}

export default function IncidentsTriagePage() {
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await opsApi.listAlerts<AlertRecord>({ limit: 50 });
      setAlerts(data || []);
    } catch (err) {
      console.error("Failed to fetch alerts", err);
    } finally {
      setLoading(false);
    }
  }, []);

  const evaluateAlerts = useCallback(async () => {
    setEvaluating(true);
    try {
      await opsApi.evaluateAlerts();
      await fetchAlerts();
    } catch (err) {
      console.error("Evaluation failed", err);
    } finally {
      setEvaluating(false);
    }
  }, [fetchAlerts]);

  const handleAction = async (id: string, action: "acknowledge" | "resolve") => {
    setActionLoading(id);
    try {
      if (action === "acknowledge") {
        await opsApi.acknowledgeAlert(id, "operator-web");
      } else {
        await opsApi.resolveAlert(id, "operator-web");
      }
      await fetchAlerts();
    } catch (err) {
      console.error(`Failed to ${action} alert`, err);
    } finally {
      setActionLoading(null);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-stone-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Link
              href="/operations"
              className="p-1.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-700 border border-stone-200 transition-colors mr-1"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <h1 className="text-2xl font-bold tracking-tight text-stone-900 flex items-center gap-2">
              <AlertTriangle className="w-6 h-6 text-amber-600" />
              Operational Alerts & Incident Triage
            </h1>
          </div>
          <p className="text-xs text-stone-500 mt-1">
            Deterministic alert evaluation engine for DLQ backlogs, queue latency, circuit breakers, and worker staleness.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={evaluateAlerts}
            disabled={evaluating}
            className="px-3.5 py-1.5 rounded-lg bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <Sliders className={`w-3.5 h-3.5 ${evaluating ? "animate-spin" : ""}`} />
            Evaluate Alert Rules
          </button>
          <button
            onClick={fetchAlerts}
            disabled={loading}
            className="p-2 rounded-lg bg-white hover:bg-stone-50 text-stone-700 border border-stone-200 transition-colors shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Alert List */}
      <div className="space-y-4">
        {loading ? (
          <div className="py-12 text-center text-xs text-stone-400 bg-white rounded-xl border border-stone-200">
            Loading operational alerts...
          </div>
        ) : alerts.length === 0 ? (
          <div className="py-12 text-center text-xs text-stone-600 bg-white rounded-xl border border-stone-200 space-y-2 shadow-sm">
            <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto" />
            <div className="font-semibold text-stone-800">Zero Active Incidents</div>
            <p className="text-stone-500">All subsystems are operating normally within threshold bounds.</p>
          </div>
        ) : (
          alerts.map((a) => (
            <div
              key={a.id}
              className={`p-5 rounded-xl border transition-colors shadow-sm ${
                a.status === "OPEN"
                  ? "bg-white border-amber-300 shadow-amber-500/5"
                  : a.status === "ACKNOWLEDGED"
                  ? "bg-white border-orange-200"
                  : "bg-stone-50 border-stone-200 opacity-70"
              }`}
            >
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-stone-100 pb-3">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono border ${
                      a.severity === "CRITICAL"
                        ? "bg-rose-50 text-rose-700 border-rose-200"
                        : a.severity === "ERROR"
                        ? "bg-rose-50 text-rose-700 border-rose-200"
                        : "bg-amber-50 text-amber-700 border-amber-200"
                    }`}
                  >
                    {a.severity}
                  </span>
                  <span className="text-sm font-semibold text-stone-900">{a.alert_name}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-stone-100 text-stone-600 border border-stone-200">
                    {a.alert_type}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-semibold font-mono border ${
                      a.status === "OPEN"
                        ? "bg-amber-50 text-amber-700 border-amber-200"
                        : a.status === "ACKNOWLEDGED"
                        ? "bg-orange-50 text-orange-700 border-orange-200"
                        : "bg-emerald-50 text-emerald-700 border-emerald-200"
                    }`}
                  >
                    {a.status}
                  </span>
                </div>
              </div>

              <div className="py-3 text-xs text-stone-700 font-sans">{a.summary}</div>

              {a.details && Object.keys(a.details).length > 0 && (
                <pre className="p-2.5 rounded bg-stone-50 border border-stone-200 text-[11px] font-mono text-stone-700 overflow-x-auto max-h-32 mb-3">
                  {JSON.stringify(a.details, null, 2)}
                </pre>
              )}

              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-3 border-t border-stone-100 text-[11px] font-mono text-stone-500">
                <div className="flex items-center gap-3">
                  <span>Fingerprint: {a.fingerprint.slice(0, 10)}...</span>
                  <span>Created: {new Date(a.created_at).toLocaleTimeString()}</span>
                  {a.trace_id && (
                    <Link
                      href={`/operations/traces/${encodeURIComponent(a.trace_id)}`}
                      className="text-orange-600 hover:text-orange-700 flex items-center gap-0.5 font-medium"
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
                      className="px-2.5 py-1 rounded bg-orange-50 hover:bg-orange-100 text-orange-700 border border-orange-200 text-xs font-medium transition-colors"
                    >
                      Acknowledge
                    </button>
                  )}
                  {a.status !== "RESOLVED" && (
                    <button
                      onClick={() => handleAction(a.id, "resolve")}
                      disabled={actionLoading === a.id}
                      className="px-2.5 py-1 rounded bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-xs font-medium transition-colors"
                    >
                      Resolve
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
