"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Activity,
  ArrowLeft,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Layers,
  Brain,
  Zap,
  Radio,
  FileCheck,
} from "lucide-react";

interface TraceNode {
  node_id: string;
  span_id?: string;
  component: string;
  step_name: string;
  status: string;
  timestamp: string;
  duration_ms?: number;
  resource_id?: string;
  error_message?: string;
  metadata: Record<string, unknown>;
}


interface TraceWorkflowGraph {
  trace_id: string;
  workspace_id: string;
  root_event_type?: string;
  start_time: string;
  end_time?: string;
  total_duration_ms?: number;
  node_count: number;
  nodes: TraceNode[];
  is_complete: boolean;
  has_errors: boolean;
  related_obligation_ids: string[];
  related_decision_ids: string[];
}

import { opsApi } from "@/lib/api/obligations";

export default function TraceGraphExplorerPage() {
  const params = useParams();
  const traceId = params?.trace_id as string;
  const [traceData, setTraceData] = useState<TraceWorkflowGraph | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchTrace = async () => {
    if (!traceId) return;
    setLoading(true);
    try {
      const json = await opsApi.getTrace<TraceWorkflowGraph>(traceId);
      if (json) {
        setTraceData(json);
      }
    } catch (err) {
      console.error("Failed to load trace graph", err);
    } finally {
      setLoading(false);
    }
  };


  useEffect(() => {
    fetchTrace();
  }, [traceId]);

  const getComponentIcon = (comp: string) => {
    switch (comp.toUpperCase()) {
      case "WEBHOOK":
      case "INBOX":
        return <Radio className="w-4 h-4 text-cyan-400" />;
      case "WORKER":
        return <Layers className="w-4 h-4 text-amber-400" />;
      case "LLM":
        return <Brain className="w-4 h-4 text-purple-400" />;
      case "OBLIGATION":
        return <FileCheck className="w-4 h-4 text-emerald-400" />;
      case "DECISION":
      case "EXECUTION":
        return <Zap className="w-4 h-4 text-indigo-400" />;
      default:
        return <Activity className="w-4 h-4 text-slate-400" />;
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Link
              href="/operations"
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors mr-1"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <Activity className="w-5 h-5 text-cyan-400" />
              Distributed Trace DAG: <span className="font-mono text-cyan-300">{traceId}</span>
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            End-to-end execution path reconstructed across Webhooks, Ingestion, Workers, LLMs, Decisions, and Executions.
          </p>
        </div>

        <button
          onClick={fetchTrace}
          disabled={loading}
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Trace Overview Card */}
      {traceData && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
            <span className="text-[10px] text-slate-500 uppercase font-mono block">Root Event</span>
            <span className="font-semibold text-slate-200">{traceData.root_event_type}</span>
          </div>
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
            <span className="text-[10px] text-slate-500 uppercase font-mono block">Total Duration</span>
            <span className="font-semibold text-cyan-400 font-mono">
              {traceData.total_duration_ms !== null ? `${traceData.total_duration_ms}ms` : "—"}
            </span>
          </div>
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
            <span className="text-[10px] text-slate-500 uppercase font-mono block">Node Count</span>
            <span className="font-semibold text-slate-200">{traceData.node_count} spans</span>
          </div>
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
            <span className="text-[10px] text-slate-500 uppercase font-mono block">Trace Status</span>
            <span
              className={`font-semibold flex items-center gap-1 ${
                traceData.has_errors ? "text-rose-400" : "text-emerald-400"
              }`}
            >
              {traceData.has_errors ? <AlertTriangle className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
              {traceData.has_errors ? "Errors Encountered" : "Execution Successful"}
            </span>
          </div>
        </div>
      )}

      {/* Trace DAG Chronological Flow */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-6">
        <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2 border-b border-slate-800 pb-3">
          <Clock className="w-4 h-4 text-indigo-400" />
          Chronological Execution Timeline
        </h3>

        {loading ? (
          <div className="py-12 text-center text-xs text-slate-500">Reconstructing trace graph...</div>
        ) : !traceData || traceData.nodes.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500">
            No execution nodes found for trace ID: {traceId}
          </div>
        ) : (
          <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
            {traceData.nodes.map((node) => (
              <div key={node.node_id} className="relative group">

                {/* Node icon / indicator */}
                <div className="absolute -left-[27px] top-1 w-5 h-5 rounded-full bg-slate-950 border-2 border-slate-700 flex items-center justify-center group-hover:border-cyan-400 transition-colors">
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      node.status === "SUCCESS" || node.status === "PROCESSED"
                        ? "bg-emerald-400"
                        : node.status === "FAILURE" || node.status === "DEAD_LETTER"
                        ? "bg-rose-400"
                        : "bg-amber-400"
                    }`}
                  />
                </div>

                {/* Node Card */}
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800/80 hover:border-slate-700 transition-colors space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getComponentIcon(node.component)}
                      <span className="text-xs font-semibold text-slate-200">{node.step_name}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                        {node.component}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs font-mono">
                      {node.duration_ms !== null && node.duration_ms !== undefined && (
                        <span className="text-cyan-400 font-bold">{node.duration_ms}ms</span>
                      )}
                      <span className="text-slate-500">{new Date(node.timestamp).toLocaleTimeString()}</span>
                    </div>
                  </div>

                  {node.error_message && (
                    <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 font-mono">
                      Error: {node.error_message}
                    </div>
                  )}

                  {node.metadata && Object.keys(node.metadata).length > 0 && (
                    <div className="pt-2 border-t border-slate-900 flex flex-wrap gap-2 text-[11px] font-mono text-slate-400">
                      {Object.entries(node.metadata).map(([k, v]) => (
                        <span key={k} className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800">
                          {k}: <span className="text-slate-200">{String(v)}</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
