"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Layers,
  AlertTriangle,
  FileCheck,
  Brain,
  Zap,
  Activity,
  Inbox,
  AlertOctagon,
  RotateCcw,
  Trash2,
  CheckCircle2,
  ArrowUpRight,
  Loader2,
  LucideIcon,
  RefreshCw,
  Eye,
  X,
} from "lucide-react";

type QueueTab = "action" | "evidence" | "decisions" | "executions" | "inbox" | "dead_letter" | "activity";

interface QueueItem {
  id: string;
  action?: string;
  owner?: string;
  status?: string;
  is_overdue?: boolean;
  is_blocked?: boolean;
  deadline?: string;
  content?: string;
  evidence_type?: string;
  source_type?: string;
  actor?: string;
  confidence_score?: number;
  primary_objective?: string;
  overall_urgency?: string;
  overall_risk?: number;
  decision_confidence?: number;
  provider?: string;
  source_ref?: string;
  event_type?: string;
  stream_key?: string;
  retry_count?: number;
  attempt_count?: number;
  max_attempts?: number;
  last_error?: string;
  updated_at?: string;
  sender?: string;
  received_at?: string;
  available_at?: string;
  processing_duration_ms?: number;
  payload_metadata?: Record<string, unknown>;
  correlated_obligation_id?: string;

  url?: string;
}

interface TabConfig {
  id: QueueTab;
  label: string;
  icon: LucideIcon;
  color: string;
}

export default function OperationalQueuesPage() {
  const [activeTab, setActiveTab] = useState<QueueTab>("action");
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<QueueItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState<QueueItem | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const fetchQueue = async (tab: QueueTab) => {
    setLoading(true);
    try {
      let endpoint = `/api/queues/${tab}`;
      if (tab === "inbox") endpoint = "/api/events/queue";
      else if (tab === "dead_letter") endpoint = "/api/events/dead-letter";

      const res = await fetch(endpoint);
      if (res.ok) {
        const data = await res.json();
        setItems(data.items || []);
        setTotalCount(data.total_count ?? data.total_returned ?? (data.items?.length || 0));
      }
    } catch {} finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue(activeTab);
  }, [activeTab]);

  const handleRetryDLQ = async (eventId: string) => {
    setActionLoading(eventId);
    try {
      const res = await fetch(`/api/events/dead-letter/${eventId}/retry`, { method: "POST" });
      if (res.ok) {
        setFeedbackMsg(`Event ${eventId.slice(0, 8)} successfully re-queued.`);
        fetchQueue(activeTab);
        if (selectedEvent?.id === eventId) setSelectedEvent(null);
      }
    } catch {} finally {
      setActionLoading(null);
    }
  };

  const handleDiscardDLQ = async (eventId: string) => {
    setActionLoading(eventId);
    try {
      const res = await fetch(`/api/events/dead-letter/${eventId}/discard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "Discarded by operator in Queues UI" }),
      });
      if (res.ok) {
        setFeedbackMsg(`Event ${eventId.slice(0, 8)} discarded.`);
        fetchQueue(activeTab);
        if (selectedEvent?.id === eventId) setSelectedEvent(null);
      }
    } catch {} finally {
      setActionLoading(null);
    }
  };

  const tabs: TabConfig[] = [
    { id: "action", label: "Action Queue", icon: AlertTriangle, color: "text-amber-400" },
    { id: "evidence", label: "Evidence Review", icon: FileCheck, color: "text-blue-400" },
    { id: "decisions", label: "Decision Queue", icon: Brain, color: "text-purple-400" },
    { id: "executions", label: "Execution Queue", icon: Zap, color: "text-cyan-400" },
    { id: "inbox", label: "Event Processing", icon: Inbox, color: "text-indigo-400" },
    { id: "dead_letter", label: "Dead Letter Queue", icon: AlertOctagon, color: "text-rose-400" },
    { id: "activity", label: "Activity Feed", icon: Activity, color: "text-emerald-400" },
  ];

  return (
    <div className="space-y-6 max-w-6xl mx-auto animate-in fade-in duration-200">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-400" />
            <span>Operational Queues</span>
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Unified operator center for triage, async event buffers, decision approvals, execution telemetry, and dead-letter recovery.
          </p>
        </div>
        <button
          onClick={() => fetchQueue(activeTab)}
          className="p-2 bg-zinc-900 border border-zinc-800 rounded-xl text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 text-xs flex items-center gap-1.5 transition-colors"
          title="Refresh Queue"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {feedbackMsg && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs rounded-xl flex items-center justify-between">
          <span>{feedbackMsg}</span>
          <button onClick={() => setFeedbackMsg(null)} className="text-emerald-400 hover:text-emerald-200">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto border-b border-zinc-800 pb-3">
        {tabs.map((t) => {
          const Icon = t.icon;
          const isSelected = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all shrink-0 ${
                isSelected
                  ? "bg-zinc-800 text-zinc-100 border border-zinc-700 shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${t.color}`} />
              <span>{t.label}</span>
              {isSelected && (
                <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-zinc-700 text-zinc-300 font-mono">
                  {totalCount}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Queue Items Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden shadow-sm">
        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center gap-2 text-zinc-500 text-xs">
            <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
            <span>Loading queue items...</span>
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center text-zinc-500 text-xs">
            <CheckCircle2 className="w-8 h-8 text-emerald-400/50 mx-auto mb-2" />
            <div className="font-semibold text-zinc-300">Queue is Clear</div>
            <p className="text-[11px] mt-1">No items currently requiring attention in this operational stream.</p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/60 text-xs">
            {/* ACTION QUEUE */}
            {activeTab === "action" &&
              items.map((item) => (
                <div key={item.id} className="p-4 flex items-center justify-between hover:bg-zinc-800/30 transition-colors">
                  <div className="space-y-1 max-w-xl">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-zinc-200">{item.action}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          item.is_overdue
                            ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            : item.is_blocked
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                        }`}
                      >
                        {item.status}
                      </span>
                    </div>
                    <div className="text-zinc-400 text-[11px]">
                      Owner: <span className="text-zinc-300 font-medium">{item.owner}</span> • Due:{" "}
                      {item.deadline ? new Date(item.deadline).toLocaleDateString() : "No deadline"}
                    </div>
                  </div>
                  {item.url && (
                    <Link
                      href={item.url}
                      className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium text-xs shadow transition-colors shrink-0"
                    >
                      <span>View & Resolve</span>
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </Link>
                  )}
                </div>
              ))}

            {/* EVIDENCE REVIEW QUEUE */}
            {activeTab === "evidence" &&
              items.map((item) => (
                <div key={item.id} className="p-4 flex items-center justify-between hover:bg-zinc-800/30 transition-colors">
                  <div className="space-y-1 max-w-xl">
                    <div className="font-semibold text-zinc-200">{item.content}</div>
                    <div className="text-zinc-400 text-[11px]">
                      Type: {item.evidence_type} • Source: {item.source_type} • Actor: {item.actor || "Automated"} • Confidence:{" "}
                      {Math.round((item.confidence_score || 0) * 100)}%
                    </div>
                  </div>
                  {item.url && (
                    <Link
                      href={item.url}
                      className="inline-flex items-center gap-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-medium text-xs shadow transition-colors shrink-0"
                    >
                      <span>Review Evidence</span>
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </Link>
                  )}
                </div>
              ))}

            {/* DECISION QUEUE */}
            {activeTab === "decisions" &&
              items.map((item) => (
                <div key={item.id} className="p-4 flex items-center justify-between hover:bg-zinc-800/30 transition-colors">
                  <div className="space-y-1 max-w-xl">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-zinc-200">{item.primary_objective}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                        {item.status}
                      </span>
                    </div>
                    <div className="text-zinc-400 text-[11px]">
                      Urgency: <span className="font-medium text-zinc-300">{item.overall_urgency}</span> • Risk:{" "}
                      {Math.round((item.overall_risk || 0) * 100)}% • Confidence:{" "}
                      {Math.round((item.decision_confidence || 0) * 100)}%
                    </div>
                  </div>
                  {item.url && (
                    <Link
                      href={item.url}
                      className="inline-flex items-center gap-1 px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-medium text-xs shadow transition-colors shrink-0"
                    >
                      <span>Authorize Plan</span>
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </Link>
                  )}
                </div>
              ))}

            {/* EXECUTION QUEUE */}
            {activeTab === "executions" &&
              items.map((item) => (
                <div key={item.id} className="p-4 flex items-center justify-between hover:bg-zinc-800/30 transition-colors">
                  <div className="space-y-1 max-w-xl">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-zinc-200">Execution #{item.id.slice(0, 8)}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                        {item.status}
                      </span>
                    </div>
                    <div className="text-zinc-400 text-[11px]">
                      Provider: {item.provider} • Retries: {item.retry_count}/{item.max_attempts} • Updated:{" "}
                      {item.updated_at ? new Date(item.updated_at).toLocaleTimeString() : "—"}
                    </div>
                  </div>
                  {item.url && (
                    <Link
                      href={item.url}
                      className="inline-flex items-center gap-1 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg font-medium text-xs transition-colors shrink-0"
                    >
                      <span>Inspect</span>
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </Link>
                  )}
                </div>
              ))}

            {/* EVENT PROCESSING INBOX QUEUE */}
            {activeTab === "inbox" &&
              items.map((item) => (
                <div key={item.id} className="p-4 flex items-center justify-between hover:bg-zinc-800/30 transition-colors">
                  <div className="space-y-1 max-w-xl">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-zinc-200 uppercase text-[11px] px-1.5 py-0.5 bg-zinc-800 border border-zinc-700 rounded">
                        {item.provider}
                      </span>
                      <span className="font-mono text-zinc-300">{item.id.slice(0, 14)}...</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          item.status === "PROCESSING"
                            ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse"
                            : item.status === "RETRY_SCHEDULED"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                        }`}
                      >
                        {item.status}
                      </span>
                    </div>
                    <div className="text-zinc-400 text-[11px]">
                      Stream: <span className="font-mono text-zinc-300">{item.stream_key}</span> • Attempts:{" "}
                      <span className="font-medium text-zinc-300">{item.attempt_count}/{item.max_attempts}</span> • Received:{" "}
                      {item.received_at ? new Date(item.received_at).toLocaleTimeString() : "—"}
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedEvent(item)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg font-medium text-xs transition-colors shrink-0"
                  >
                    <Eye className="w-3.5 h-3.5 text-zinc-400" />
                    <span>Inspect</span>
                  </button>
                </div>
              ))}

            {/* DEAD LETTER QUEUE (DLQ) */}
            {activeTab === "dead_letter" &&
              items.map((item) => (
                <div key={item.id} className="p-4 flex items-center justify-between hover:bg-zinc-800/30 transition-colors">
                  <div className="space-y-1 max-w-xl">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-rose-300 uppercase text-[11px] px-1.5 py-0.5 bg-rose-500/10 border border-rose-500/20 rounded">
                        {item.provider}
                      </span>
                      <span className="font-mono text-zinc-300">{item.id.slice(0, 14)}...</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                        DEAD_LETTER
                      </span>
                    </div>
                    <p className="text-rose-400 text-[11px] font-mono truncate max-w-lg">
                      Error: {item.last_error || "Max retry attempts exhausted."}
                    </p>
                    <div className="text-zinc-500 text-[10px]">
                      Stream: <span className="font-mono text-zinc-400">{item.stream_key}</span> • Attempts: {item.attempt_count}/{item.max_attempts}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => handleRetryDLQ(item.id)}
                      disabled={actionLoading === item.id}
                      className="inline-flex items-center gap-1 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium text-xs shadow transition-colors disabled:opacity-50"
                    >
                      <RotateCcw className={`w-3.5 h-3.5 ${actionLoading === item.id ? "animate-spin" : ""}`} />
                      <span>Retry</span>
                    </button>
                    <button
                      onClick={() => handleDiscardDLQ(item.id)}
                      disabled={actionLoading === item.id}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-zinc-800 hover:bg-rose-900/40 text-zinc-300 hover:text-rose-300 border border-zinc-700 rounded-lg text-xs transition-colors disabled:opacity-50"
                      title="Discard Event Permanently"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => setSelectedEvent(item)}
                      className="p-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 rounded-lg text-xs transition-colors"
                      title="Inspect Metadata"
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}

            {/* ACTIVITY FEED */}
            {activeTab === "activity" &&
              items.map((item) => (
                <div key={item.id} className="p-4 flex items-start justify-between hover:bg-zinc-800/30 transition-colors">
                  <div className="space-y-1 max-w-2xl">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-zinc-200">[{item.provider?.toUpperCase() || "EVENT"}]</span>
                      <span className="text-zinc-400 font-medium">{item.sender}</span>
                      <span className="text-zinc-500 text-[11px]">
                        • {item.received_at ? new Date(item.received_at).toLocaleTimeString() : ""}
                      </span>
                    </div>
                    <p className="text-zinc-300 text-xs leading-relaxed">{item.content}</p>
                  </div>
                  {item.correlated_obligation_id && (
                    <Link
                      href={`/obligations/${item.correlated_obligation_id}`}
                      className="text-blue-400 hover:text-blue-300 text-xs font-medium shrink-0 ml-4"
                    >
                      View Obligation &rarr;
                    </Link>
                  )}
                </div>
              ))}
          </div>
        )}
      </div>

      {/* Event Details Drawer/Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl animate-in zoom-in-95 duration-150">
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Inbox className="w-4 h-4 text-indigo-400" />
                <h3 className="font-bold text-zinc-100 text-sm">Event Inbox Inspector</h3>
                <span className="text-xs font-mono text-zinc-500">#{selectedEvent.id.slice(0, 12)}</span>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="p-1 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-zinc-950/60 border border-zinc-800/80 rounded-xl space-y-1">
                  <div className="text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">Provider & Stream</div>
                  <div className="text-zinc-200 font-medium">{selectedEvent.provider?.toUpperCase()}</div>
                  <div className="font-mono text-zinc-400 text-[11px] truncate">{selectedEvent.stream_key}</div>
                </div>
                <div className="p-3 bg-zinc-950/60 border border-zinc-800/80 rounded-xl space-y-1">
                  <div className="text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">Processing Status</div>
                  <div className="text-zinc-200 font-medium flex items-center gap-1.5">
                    <span className="font-bold">{selectedEvent.status}</span>
                    <span className="text-zinc-400 text-[11px]">• Attempt {selectedEvent.attempt_count || 0}/{selectedEvent.max_attempts || 3}</span>
                  </div>
                  <div className="text-zinc-400 text-[11px]">
                    Latency: {selectedEvent.processing_duration_ms ? `${selectedEvent.processing_duration_ms} ms` : "—"}
                  </div>
                </div>
              </div>

              {selectedEvent.last_error && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl space-y-1">
                  <div className="text-[10px] text-rose-400 font-semibold uppercase">Last Processing Error</div>
                  <pre className="text-rose-300 font-mono text-[11px] whitespace-pre-wrap">{selectedEvent.last_error}</pre>
                </div>
              )}

              <div className="space-y-1.5">
                <div className="text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">Safe Sanitized Metadata</div>
                <pre className="p-3 bg-zinc-950/80 border border-zinc-800 rounded-xl text-zinc-300 font-mono text-[11px] overflow-x-auto max-h-48">
                  {JSON.stringify(selectedEvent.payload_metadata || {}, null, 2)}
                </pre>
              </div>
            </div>
            <div className="p-4 border-t border-zinc-800 flex items-center justify-end gap-2 bg-zinc-950/40">
              {selectedEvent.status === "DEAD_LETTER" && (
                <>
                  <button
                    onClick={() => handleDiscardDLQ(selectedEvent.id)}
                    disabled={actionLoading === selectedEvent.id}
                    className="px-3 py-1.5 bg-zinc-800 hover:bg-rose-900/40 text-zinc-300 hover:text-rose-300 border border-zinc-700 rounded-lg text-xs font-medium transition-colors"
                  >
                    Discard Permanently
                  </button>
                  <button
                    onClick={() => handleRetryDLQ(selectedEvent.id)}
                    disabled={actionLoading === selectedEvent.id}
                    className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium shadow transition-colors"
                  >
                    Re-Queue for Processing
                  </button>
                </>
              )}
              <button
                onClick={() => setSelectedEvent(null)}
                className="px-4 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs font-medium transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
