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
  CheckCircle2,
  ArrowUpRight,
  Loader2,
  LucideIcon,
} from "lucide-react";

type QueueTab = "action" | "evidence" | "decisions" | "executions" | "activity";

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
  retry_count?: number;
  max_retries?: number;
  updated_at?: string;
  sender?: string;
  received_at?: string;
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

  const fetchQueue = async (tab: QueueTab) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/queues/${tab}`);
      if (res.ok) {
        const data = await res.json();
        setItems(data.items || []);
        setTotalCount(data.total_count || 0);
      }
    } catch {} finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue(activeTab);
  }, [activeTab]);

  const tabs: TabConfig[] = [
    { id: "action", label: "Action Queue", icon: AlertTriangle, color: "text-amber-400" },
    { id: "evidence", label: "Evidence Review", icon: FileCheck, color: "text-blue-400" },
    { id: "decisions", label: "Decision Queue", icon: Brain, color: "text-purple-400" },
    { id: "executions", label: "Execution Queue", icon: Zap, color: "text-cyan-400" },
    { id: "activity", label: "Activity Feed", icon: Activity, color: "text-emerald-400" },
  ];

  return (
    <div className="space-y-6 max-w-6xl mx-auto animate-in fade-in duration-200">
      <div>
        <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
          <Layers className="w-5 h-5 text-blue-400" />
          <span>Operational Queues</span>
        </h1>
        <p className="text-xs text-zinc-400 mt-1">
          Unified operator workflow center for triage, evidence confirmation, decision authorization, and execution tracking.
        </p>
      </div>

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
                <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-zinc-700 text-zinc-300">
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
                      Provider: {item.provider} • Retries: {item.retry_count}/{item.max_retries} • Updated:{" "}
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
    </div>
  );
}
