"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Activity,
  ShieldCheck,
  AlertTriangle,
  Radio,
  Layers,
  RefreshCw,
  Search,
  Clock,
  Server,
  ArrowUpRight,
  TrendingUp,
  AlertOctagon,
} from "lucide-react";


interface OperationsDashboardData {
  workspace_id: string;
  timestamp: string;
  api_health: string;
  database_backend: string;
  worker_status: string;
  total_queued_events: number;
  dead_letter_depth: number;
  open_alerts_count: number;
  active_circuit_breakers_open: number;
  throughput_rpm: {
    api_rpm: number;
    llm_rpm: number;
    events_total: number;
  };
  latency_percentiles: {
    api: { p50: number | null; p95: number | null; p99: number | null };
    llm: { p50: number | null; p95: number | null; p99: number | null };
  };
  error_rates: Record<string, number>;
  slos: Array<{
    name: string;
    category: string;
    target_percentage: number;
    actual_percentage: number | null;
    status: string;
    sample_count: number;
  }>;
  error_budgets: Array<{
    slo_name: string;
    total_budget_percentage: number;
    consumed_percentage: number | null;
    remaining_percentage: number | null;
    status: string;
    status_reason: string;
  }>;
  provider_health_summary: Record<string, string>;
}

import { opsApi } from "@/lib/api/obligations";

export default function OperationsDashboardPage() {
  const [data, setData] = useState<OperationsDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTraceId, setSearchTraceId] = useState("");

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const json = await opsApi.getDashboardMetrics<OperationsDashboardData>();
      if (json) {
        setData(json);
      }
    } catch (err) {
      console.error("Failed to load operations dashboard", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const timer = setInterval(fetchMetrics, 15000);
    return () => clearInterval(timer);
  }, []);


  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-stone-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-orange-50 text-orange-700 border border-orange-200">
              Phase 21
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-stone-900 flex items-center gap-2">
              <Activity className="w-6 h-6 text-orange-600" />
              Operations & Observability Control Center
            </h1>
          </div>
          <p className="text-xs text-stone-600 mt-1">
            Real-time telemetry, distributed trace explorer, operational audit trails, and SLO error budgets.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/operations/audit"
            className="px-3 py-1.5 rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 text-xs font-semibold border border-stone-300 transition-colors flex items-center gap-1.5"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-orange-600" />
            Audit Explorer
          </Link>
          <Link
            href="/operations/incidents"
            className="px-3 py-1.5 rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 text-xs font-semibold border border-stone-300 transition-colors flex items-center gap-1.5"
          >
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            Alerts & Incidents
          </Link>
          <button
            onClick={fetchMetrics}
            disabled={loading}
            className="p-2 rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-700 border border-stone-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Quick Trace Search Bar */}
      <div className="bg-stone-100/60 border border-stone-200 rounded-xl p-4 flex items-center gap-3">
        <Search className="w-4 h-4 text-stone-600 shrink-0" />
        <input
          type="text"
          placeholder="Lookup end-to-end trace by Trace ID or Request ID (e.g. 5d1e2f8a...)..."
          value={searchTraceId}
          onChange={(e) => setSearchTraceId(e.target.value)}
          className="bg-transparent text-xs text-stone-900 placeholder-stone-500 focus:outline-none flex-1 font-mono"
        />
        {searchTraceId.trim() && (
          <Link
            href={`/operations/traces/${encodeURIComponent(searchTraceId.trim())}`}
            className="px-3.5 py-1.5 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1 transition-colors shadow-sm"
          >
            Explore Trace <ArrowUpRight className="w-3 h-3" />
          </Link>
        )}
      </div>

      {/* Top Telemetry KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-stone-100/60 border border-stone-200 rounded-xl p-4">
          <div className="flex items-center justify-between text-xs text-stone-600">
            <span>System Health</span>
            <Server className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 mt-2 font-mono flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            {data?.api_health || "HEALTHY"}
          </div>
          <div className="text-[11px] text-stone-500 mt-1">
            Backend: {data?.database_backend.toUpperCase()} • Worker: {data?.worker_status}
          </div>
        </div>

        <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-stone-600">
            <span>Queue Depth & DLQ</span>
            <Layers className="w-4 h-4 text-orange-600" />
          </div>
          <div className="text-2xl font-bold text-stone-900 mt-2 font-mono">
            {data?.total_queued_events || 0}
            <span className="text-xs font-normal text-stone-600 ml-1">inbox</span>
          </div>
          <div className="text-[11px] text-stone-500 mt-1 flex items-center gap-1">
            DLQ Depth:{" "}
            <span
              className={`font-semibold ${(data?.dead_letter_depth || 0) > 0 ? "text-rose-400" : "text-stone-600"}`}
            >
              {data?.dead_letter_depth || 0}
            </span>
          </div>
        </div>

        <div className="bg-stone-100/60 border border-stone-200 rounded-xl p-4">
          <div className="flex items-center justify-between text-xs text-stone-600">
            <span>API Latency (p95)</span>
            <Clock className="w-4 h-4 text-orange-600" />
          </div>
          <div className="text-2xl font-bold text-stone-900 mt-2 font-mono">
            {data?.latency_percentiles?.api?.p95 !== null && data?.latency_percentiles?.api?.p95 !== undefined
              ? `${data.latency_percentiles.api.p95}ms`
              : "—"}
          </div>
          <div className="text-[11px] text-stone-500 mt-1">
            p50: {data?.latency_percentiles?.api?.p50 || "—"}ms • p99: {data?.latency_percentiles?.api?.p99 || "—"}ms
          </div>
        </div>

        <div className="bg-stone-100/60 border border-stone-200 rounded-xl p-4">
          <div className="flex items-center justify-between text-xs text-stone-600">
            <span>Open Incidents & Breakers</span>
            <AlertOctagon className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400 mt-2 font-mono">
            {data?.open_alerts_count || 0}
            <span className="text-xs font-normal text-stone-600 ml-1">alerts</span>
          </div>
          <div className="text-[11px] text-stone-500 mt-1">
            Circuit Breakers Open: {data?.active_circuit_breakers_open || 0}
          </div>
        </div>
      </div>

      {/* Grid: SLO Compliance & Error Budgets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: SLO Compliance Table */}
        <div className="bg-stone-100/60 border border-stone-200 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-stone-900 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Service Level Objectives (SLOs)
            </h3>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Live Monitoring
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-stone-200 text-stone-600">
                <tr>
                  <th className="pb-2">Objective</th>
                  <th className="pb-2">Target</th>
                  <th className="pb-2">Actual</th>
                  <th className="pb-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-200/60 font-mono">
                {(data?.slos || []).map((s, idx) => (
                  <tr key={idx} className="hover:bg-stone-200/20">
                    <td className="py-2.5 font-sans font-medium text-stone-800">{s.name}</td>
                    <td className="py-2.5 text-stone-600">{s.target_percentage}%</td>
                    <td className="py-2.5 font-semibold text-stone-900">
                      {s.actual_percentage !== null ? `${s.actual_percentage}%` : "—"}
                    </td>
                    <td className="py-2.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          s.status === "HEALTHY"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : s.status === "WARNING"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : s.status === "BREACHED"
                            ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            : "bg-stone-200 text-stone-600"
                        }`}
                      >
                        {s.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: Error Budget Burn Table */}
        <div className="bg-white border border-stone-200 rounded-xl p-5 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-stone-900 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-orange-500" />
              Error Budget Consumption
            </h3>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-orange-50 text-orange-700 border border-orange-200 font-semibold">
              Budget Burn
            </span>
          </div>

          <div className="space-y-3">
            {(data?.error_budgets || []).map((b, idx) => (
              <div key={idx} className="p-3 rounded-lg bg-stone-50 border border-stone-200 text-xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-stone-800">{b.slo_name}</span>
                  <span className="font-mono text-orange-600 font-bold">
                    {b.remaining_percentage !== null ? `${b.remaining_percentage}% remaining` : "INSUFFICIENT DATA"}
                  </span>
                </div>
                {b.remaining_percentage !== null && (
                  <div className="w-full h-1.5 bg-stone-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${
                        b.remaining_percentage > 50
                          ? "bg-emerald-500"
                          : b.remaining_percentage > 10
                          ? "bg-amber-500"
                          : "bg-rose-500"
                      }`}
                      style={{ width: `${b.remaining_percentage}%` }}
                    />
                  </div>
                )}
                <div className="text-[11px] text-stone-500">{b.status_reason}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Provider Health State */}
      <div className="bg-stone-100/60 border border-stone-200 rounded-xl p-5 space-y-3">
        <h3 className="text-sm font-semibold text-stone-900 flex items-center gap-2">
          <Radio className="w-4 h-4 text-orange-600" />
          Provider Health & Circuit Breaker States
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Object.entries(data?.provider_health_summary || {}).map(([p, state]) => (
            <div key={p} className="p-3 rounded-lg bg-stone-50 border border-stone-200 text-xs">
              <span className="text-[10px] uppercase text-stone-500 block font-mono">Provider</span>
              <span className="font-semibold text-stone-800">{p}</span>
              <div className="mt-1 flex items-center gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full ${
                    state === "CLOSED" || state === "CONNECTED"
                      ? "bg-emerald-400"
                      : state === "HALF_OPEN"
                      ? "bg-amber-400 animate-pulse"
                      : "bg-rose-400"
                  }`}
                />
                <span className="font-mono text-[11px] text-stone-600">{state}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
