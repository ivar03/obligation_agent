"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  Bell,
  CheckCircle2,
  Clock,
  ExternalLink,
  Eye,
  Layers,
  Lock,
  Pause,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import { monitoringApi } from "@/lib/api/obligations";
import {
  MonitoringSummaryResponse,
  MonitoringWatch,
  MonitoringEvent,
  EscalationCandidate,
  MonitoringRun,
  WatchType,
  TargetType,
} from "@/lib/types/obligation";

export default function MonitoringCenterPage() {
  const [activeTab, setActiveTab] = useState<"ESCALATIONS" | "EVENTS" | "WATCHES" | "RUNS">("ESCALATIONS");
  const [summary, setSummary] = useState<MonitoringSummaryResponse | null>(null);
  const [watches, setWatches] = useState<MonitoringWatch[]>([]);
  const [events, setEvents] = useState<MonitoringEvent[]>([]);
  const [escalations, setEscalations] = useState<EscalationCandidate[]>([]);
  const [runs, setRuns] = useState<MonitoringRun[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [cycleRunning, setCycleRunning] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  // Watch Creation Modal
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newWatchType, setNewWatchType] = useState<WatchType>("DEADLINE");
  const [newTargetType, setNewTargetType] = useState<TargetType>("OBLIGATION");
  const [newTargetId, setNewTargetId] = useState<string>("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [sumRes, escRes, evRes, wRes, rRes] = await Promise.all([
        monitoringApi.getSummary().catch(() => null),
        monitoringApi.listEscalations({ limit: 50 }).catch(() => ({ items: [], total: 0 })),
        monitoringApi.listEvents({ limit: 50 }).catch(() => ({ items: [], total: 0 })),
        monitoringApi.listWatches({ limit: 50 }).catch(() => ({ items: [], total: 0 })),
        monitoringApi.listRuns(20, 0).catch(() => ({ items: [], total: 0 })),
      ]);
      setSummary(sumRes);
      setEscalations(escRes.items);
      setEvents(evRes.items);
      setWatches(wRes.items);
      setRuns(rRes.items);
    } catch (err: unknown) {
      console.error("Failed to load monitoring data", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleTriggerCycle = async () => {
    setCycleRunning(true);
    setFeedback(null);
    try {
      const run = await monitoringApi.triggerRun({ force_all: true });
      setFeedback(`Monitoring pass completed: ${run.watches_evaluated} evaluated, ${run.events_created} events, ${run.escalations_created} escalations surfaced.`);
      await fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Monitoring pass failed.";
      setFeedback(`Error: ${msg}`);
    } finally {
      setCycleRunning(false);
    }
  };

  const handleAcknowledgeEscalation = async (id: string) => {
    try {
      await monitoringApi.acknowledgeEscalation(id);
      await fetchData();
    } catch (err: unknown) {
      console.error("Failed to acknowledge escalation", err);
    }
  };

  const handleResolveEscalation = async (id: string) => {
    try {
      await monitoringApi.resolveEscalation(id, { resolution_reason: "Resolved by operator" });
      await fetchData();
    } catch (err: unknown) {
      console.error("Failed to resolve escalation", err);
    }
  };

  const handleDismissEscalation = async (id: string) => {
    try {
      await monitoringApi.dismissEscalation(id, { reason: "Dismissed by operator" });
      await fetchData();
    } catch (err: unknown) {
      console.error("Failed to dismiss escalation", err);
    }
  };

  const handlePauseWatch = async (id: string) => {
    try {
      await monitoringApi.pauseWatch(id);
      await fetchData();
    } catch (err: unknown) {
      console.error("Failed to pause watch", err);
    }
  };

  const handleResumeWatch = async (id: string) => {
    try {
      await monitoringApi.resumeWatch(id);
      await fetchData();
    } catch (err: unknown) {
      console.error("Failed to resume watch", err);
    }
  };

  const handleDeleteWatch = async (id: string) => {
    try {
      await monitoringApi.deleteWatch(id);
      await fetchData();
    } catch (err: unknown) {
      console.error("Failed to delete watch", err);
    }
  };

  const handleCreateWatch = async () => {
    if (!newTargetId.trim()) return;
    try {
      await monitoringApi.createWatch({
        watch_type: newWatchType,
        target_type: newTargetType,
        target_id: newTargetId.trim(),
      });
      setShowCreateModal(false);
      setNewTargetId("");
      await fetchData();
    } catch (err: unknown) {
      console.error("Failed to create watch", err);
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case "CRITICAL":
        return "bg-rose-50 border-rose-200 text-rose-700";
      case "HIGH":
        return "bg-amber-50 border-amber-200 text-amber-700";
      case "WARNING":
        return "bg-amber-50 border-amber-200 text-amber-700";
      default:
        return "bg-stone-100 border-stone-200 text-stone-700";
    }
  };

  return (
    <div className="min-h-screen bg-stone-50 text-stone-900 p-4 sm:p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-stone-200 pb-6 mb-6">
        <div>
          <div className="flex items-center gap-2 text-orange-600 font-semibold text-xs tracking-wider uppercase mb-1">
            <Activity className="w-4 h-4" />
            Continuous Monitoring & Reliability
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-stone-950 tracking-tight">
            Continuous Monitoring & Escalation Center
          </h1>
          <p className="text-sm text-stone-600 mt-1">
            Deterministic observation across active obligations, deadlines, causal risk, dependency cascades, and executions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleTriggerCycle}
            disabled={cycleRunning}
            className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold text-xs rounded-lg transition shadow-sm flex items-center gap-2 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${cycleRunning ? "animate-spin" : ""}`} />
            Run Monitoring Cycle
          </button>

          <button
            onClick={() => setShowCreateModal(true)}
            className="px-3.5 py-2 bg-white border border-stone-200 hover:bg-stone-50 text-stone-800 text-xs font-semibold rounded-lg transition flex items-center gap-1.5 shadow-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            New Watch
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto space-y-6">
        {/* Safety Invariant Notice */}
        <div className="bg-orange-50/50 border border-orange-200 rounded-xl p-4 flex items-start gap-3 shadow-xs">
          <Lock className="w-5 h-5 text-orange-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs space-y-0.5">
            <div className="font-bold text-orange-900 uppercase tracking-wider text-[11px]">
              Observational Monitoring & Escalation Invariant
            </div>
            <p className="text-stone-700 leading-relaxed">
              Monitoring events and escalation candidates detect and explain meaningful state changes. <strong>The monitoring engine NEVER performs autonomous operational actions</strong> (cannot complete obligations, alter ownership, send messages, or confirm evidence). Consequential actions remain strictly human-controlled.
            </p>
          </div>
        </div>

        {feedback && (
          <div className="p-3 bg-orange-50 border border-orange-200 rounded-lg text-orange-800 text-xs flex items-center justify-between">
            <span>{feedback}</span>
            <button onClick={() => setFeedback(null)} className="text-orange-600 hover:text-stone-950">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Metric Health Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm">
            <span className="text-[10px] uppercase font-bold text-stone-600 block mb-1">Active Watches</span>
            <div className="text-2xl font-bold text-stone-950">{summary?.active_watches_count ?? watches.length}</div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm">
            <span className="text-[10px] uppercase font-bold text-rose-500 block mb-1">Critical Conditions</span>
            <div className="text-2xl font-bold text-rose-600">{summary?.critical_events_count ?? 0}</div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm">
            <span className="text-[10px] uppercase font-bold text-amber-600 block mb-1">Open Escalations</span>
            <div className="text-2xl font-bold text-amber-600">{summary?.open_escalations_count ?? escalations.filter(e => e.status === "OPEN").length}</div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm">
            <span className="text-[10px] uppercase font-bold text-emerald-600 block mb-1">Healthy Watches</span>
            <div className="text-2xl font-bold text-emerald-600">{summary?.active_watches_count ?? watches.filter(w => w.status === "ACTIVE").length}</div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm">
            <span className="text-[10px] uppercase font-bold text-stone-600 block mb-1">Failed Executions</span>
            <div className="text-2xl font-bold text-stone-800">{summary?.execution_failures_count ?? 0}</div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm">
            <span className="text-[10px] uppercase font-bold text-stone-600 block mb-1">Stale Decision Plans</span>
            <div className="text-2xl font-bold text-stone-800">{summary?.stale_decision_plans_count ?? 0}</div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="border-b border-stone-200 flex items-center justify-between">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab("ESCALATIONS")}
              className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-1.5 ${
                activeTab === "ESCALATIONS"
                  ? "border-orange-500 text-orange-600"
                  : "border-transparent text-stone-600 hover:text-stone-800"
              }`}
            >
              <Bell className="w-3.5 h-3.5" />
              Escalation Queue ({escalations.filter(e => e.status === "OPEN").length})
            </button>

            <button
              onClick={() => setActiveTab("EVENTS")}
              className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-1.5 ${
                activeTab === "EVENTS"
                  ? "border-orange-500 text-orange-600"
                  : "border-transparent text-stone-600 hover:text-stone-800"
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              Live Condition Feed ({events.length})
            </button>

            <button
              onClick={() => setActiveTab("WATCHES")}
              className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-1.5 ${
                activeTab === "WATCHES"
                  ? "border-orange-500 text-orange-600"
                  : "border-transparent text-stone-600 hover:text-stone-800"
              }`}
            >
              <Eye className="w-3.5 h-3.5" />
              Watch Manager ({watches.length})
            </button>

            <button
              onClick={() => setActiveTab("RUNS")}
              className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-1.5 ${
                activeTab === "RUNS"
                  ? "border-orange-500 text-orange-600"
                  : "border-transparent text-stone-600 hover:text-stone-800"
              }`}
            >
              <Clock className="w-3.5 h-3.5" />
              Monitoring Runs ({runs.length})
            </button>
          </div>
        </div>

        {/* Tab 1: Escalation Queue */}
        {activeTab === "ESCALATIONS" && (
          <div className="space-y-3">
            {escalations.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-xl border border-stone-200 text-stone-600 text-xs shadow-sm">
                <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
                No active escalations. The commitment ecosystem is operating within expected thresholds.
              </div>
            ) : (
              escalations.map((esc) => (
                <div
                  key={esc.id}
                  className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm space-y-3"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${getSeverityBadge(esc.severity)}`}>
                        {esc.severity}
                      </span>
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-stone-50 text-stone-600 border border-stone-200">
                        {esc.target_type}: {esc.target_id.slice(0, 14)}...
                      </span>
                      <span className="text-[10px] text-stone-500">
                        {new Date(esc.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {esc.status === "OPEN" && (
                        <>
                          <button
                            onClick={() => handleAcknowledgeEscalation(esc.id)}
                            className="px-2.5 py-1 bg-stone-100 hover:bg-stone-200 text-stone-700 text-xs font-semibold rounded border border-stone-200 transition"
                          >
                            Acknowledge
                          </button>
                          <button
                            onClick={() => handleResolveEscalation(esc.id)}
                            className="px-2.5 py-1 bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold rounded transition shadow-sm"
                          >
                            Resolve
                          </button>
                          <button
                            onClick={() => handleDismissEscalation(esc.id)}
                            className="px-2.5 py-1 bg-white hover:bg-rose-50 text-rose-700 border border-stone-200 text-xs font-semibold rounded transition"
                          >
                            Dismiss
                          </button>
                        </>
                      )}
                      {esc.status === "ACKNOWLEDGED" && (
                        <button
                          onClick={() => handleResolveEscalation(esc.id)}
                          className="px-2.5 py-1 bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold rounded transition shadow-sm"
                        >
                          Mark Resolved
                        </button>
                      )}
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-stone-100 text-stone-700 border border-stone-200">
                        {esc.status}
                      </span>
                    </div>
                  </div>

                  <p className="text-sm font-semibold text-stone-950">
                    {esc.reason}
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs bg-stone-50 p-3 rounded-lg border border-stone-200">
                    <div>
                      <span className="text-stone-500 block text-[10px] uppercase font-bold">Recommended Next Step</span>
                      <strong className="text-stone-900 font-semibold">{esc.recommended_next_step}</strong>
                    </div>
                    <div>
                      <span className="text-stone-500 block text-[10px] uppercase font-bold">Affected Dependents</span>
                      <span className="text-stone-700">{esc.affected_obligations?.length || 0} obligations / {esc.affected_owners?.length || 0} owners</span>
                    </div>
                    <div>
                      <span className="text-stone-500 block text-[10px] uppercase font-bold">Associated Plan</span>
                      {esc.decision_plan_id ? (
                        <Link
                          href={`/intelligence/decisions/${esc.target_id}`}
                          className="text-orange-600 hover:text-orange-700 font-medium flex items-center gap-1 text-xs"
                        >
                          View Decision Plan <ExternalLink className="w-3 h-3" />
                        </Link>
                      ) : (
                        <span className="text-stone-500">None generated</span>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Tab 2: Live Condition Feed */}
        {activeTab === "EVENTS" && (
          <div className="space-y-2.5">
            {events.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-xl border border-stone-200 text-stone-600 text-xs shadow-sm">
                No recent condition events detected.
              </div>
            ) : (
              events.map((ev) => (
                <div
                  key={ev.id}
                  className="bg-white border border-stone-200 rounded-lg p-4 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${getSeverityBadge(ev.severity)}`}>
                        {ev.severity}
                      </span>
                      <strong className="text-stone-950 font-mono">{ev.event_type}</strong>
                      <span className="text-stone-500 text-[10px]">
                        {new Date(ev.detected_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-stone-700">{ev.explanation}</p>
                    <div className="text-[10px] text-stone-500 font-mono">
                      Target: {ev.target_type} ({ev.target_id}) • Provenance: {ev.provenance?.source_service as string || "MonitoringEngine"}
                    </div>
                  </div>

                  <Link
                    href={`/obligations/${ev.target_id}`}
                    className="p-1.5 rounded bg-stone-50 border border-stone-200 text-stone-600 hover:text-stone-950 flex-shrink-0 self-start sm:self-auto"
                    title="View target obligation"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </Link>
                </div>
              ))
            )}
          </div>
        )}

        {/* Tab 3: Watch Manager */}
        {activeTab === "WATCHES" && (
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden shadow-sm">
            <div className="p-4 border-b border-stone-200 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-600">
                Monitored Targets ({watches.length})
              </h2>
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-3 py-1.5 bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold rounded-lg transition flex items-center gap-1 shadow-sm"
              >
                <Plus className="w-3.5 h-3.5" /> Add Target Watch
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-stone-700">
                <thead className="bg-stone-50 text-stone-500 uppercase text-[10px]">
                  <tr>
                    <th className="p-3">Watch Type</th>
                    <th className="p-3">Target</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Last Evaluated</th>
                    <th className="p-3">Trigger Count</th>
                    <th className="p-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {watches.map((w) => (
                    <tr key={w.id} className="hover:bg-stone-50 transition">
                      <td className="p-3 font-semibold text-stone-900">{w.watch_type}</td>
                      <td className="p-3 font-mono text-stone-600">{w.target_type}: {w.target_id.slice(0, 12)}...</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                          w.status === "ACTIVE"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-stone-100 text-stone-600 border border-stone-200"
                        }`}>
                          {w.status}
                        </span>
                      </td>
                      <td className="p-3 text-stone-600">
                        {w.last_evaluated_at ? new Date(w.last_evaluated_at).toLocaleTimeString() : "Pending"}
                      </td>
                      <td className="p-3 font-mono">{w.trigger_count}</td>
                      <td className="p-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {w.status === "ACTIVE" ? (
                            <button
                              onClick={() => handlePauseWatch(w.id)}
                              className="p-1 rounded bg-stone-100 hover:bg-stone-200 text-stone-700 border border-stone-200"
                              title="Pause watch"
                            >
                              <Pause className="w-3.5 h-3.5" />
                            </button>
                          ) : (
                            <button
                              onClick={() => handleResumeWatch(w.id)}
                              className="p-1 rounded bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200"
                              title="Resume watch"
                            >
                              <Play className="w-3.5 h-3.5" />
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteWatch(w.id)}
                            className="p-1 rounded bg-white hover:bg-rose-50 text-rose-600 border border-stone-200"
                            title="Delete watch"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 4: Monitoring Runs */}
        {activeTab === "RUNS" && (
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden shadow-sm">
            <div className="p-4 border-b border-stone-200">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-600">
                Evaluation Pass History ({runs.length})
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-stone-700">
                <thead className="bg-stone-50 text-stone-500 uppercase text-[10px]">
                  <tr>
                    <th className="p-3">Run ID</th>
                    <th className="p-3">Started At</th>
                    <th className="p-3">Watches Evaluated</th>
                    <th className="p-3">Events Created</th>
                    <th className="p-3">Escalations</th>
                    <th className="p-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {runs.map((r) => (
                    <tr key={r.id} className="hover:bg-stone-50 transition">
                      <td className="p-3 font-mono text-stone-600">{r.id.slice(0, 8)}...</td>
                      <td className="p-3">{new Date(r.started_at).toLocaleString()}</td>
                      <td className="p-3 font-mono">{r.watches_evaluated}</td>
                      <td className="p-3 font-mono">{r.events_created}</td>
                      <td className="p-3 font-mono">{r.escalations_created}</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold border ${
                          r.status === "COMPLETED"
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : r.status === "PARTIAL"
                            ? "bg-amber-50 text-amber-700 border-amber-200"
                            : "bg-rose-50 text-rose-700 border-rose-200"
                        }`}>
                          {r.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Create Watch Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-stone-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-stone-200 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-stone-200 pb-3">
              <h3 className="text-base font-bold text-stone-950">Create Target Monitoring Watch</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="p-1 rounded text-stone-400 hover:text-stone-700 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 mb-1 font-semibold">Watch Type</label>
                <select
                  value={newWatchType}
                  onChange={(e) => setNewWatchType(e.target.value as WatchType)}
                  className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-2 text-stone-800 outline-none font-mono focus:ring-2 focus:ring-orange-500"
                >
                  <option value="DEADLINE">DEADLINE (Approaching / Breached)</option>
                  <option value="RISK">RISK (Classification & Shifts)</option>
                  <option value="DEPENDENCY">DEPENDENCY (Blockers & Unblocking)</option>
                  <option value="EXECUTION">EXECUTION (Failures & Timeouts)</option>
                  <option value="RESPONSE">RESPONSE (Owner Responsiveness)</option>
                  <option value="DECISION_PLAN">DECISION_PLAN (Staleness & Resolution)</option>
                  <option value="CRITICAL_PATH">CRITICAL_PATH (Downstream Changes)</option>
                  <option value="BOTTLENECK">BOTTLENECK (Systemic Blockers)</option>
                </select>
              </div>

              <div>
                <label className="block text-stone-600 mb-1 font-semibold">Target Type</label>
                <select
                  value={newTargetType}
                  onChange={(e) => setNewTargetType(e.target.value as TargetType)}
                  className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-2 text-stone-800 outline-none font-mono focus:ring-2 focus:ring-orange-500"
                >
                  <option value="OBLIGATION">OBLIGATION</option>
                  <option value="EXECUTION">EXECUTION</option>
                  <option value="DECISION_PLAN">DECISION_PLAN</option>
                </select>
              </div>

              <div>
                <label className="block text-stone-600 mb-1 font-semibold">Target ID</label>
                <input
                  type="text"
                  value={newTargetId}
                  onChange={(e) => setNewTargetId(e.target.value)}
                  placeholder="Enter Obligation or Target ID..."
                  className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-2 text-stone-800 outline-none font-mono focus:ring-2 focus:ring-orange-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-stone-200">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-3.5 py-1.5 text-xs text-stone-600 hover:text-stone-800 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateWatch}
                className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold rounded-lg transition shadow-sm"
              >
                Create Watch
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
