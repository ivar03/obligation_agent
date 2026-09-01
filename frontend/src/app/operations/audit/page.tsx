"use client";

import React, { useState, useEffect, useCallback } from "react";

import Link from "next/link";
import {
  ShieldCheck,
  Search,
  RefreshCw,
  ArrowLeft,
  Filter,
  ArrowUpRight,
  CheckCircle2,
  AlertTriangle,
  Key,
  FileCode,
  X,
} from "lucide-react";
import { opsApi } from "@/lib/api/obligations";

interface AuditRecord {
  id: string;
  timestamp: string;
  event_type: string;
  severity: string;
  actor_type: string;
  actor_id?: string;
  request_id?: string;
  trace_id?: string;
  resource_type?: string;
  resource_id?: string;
  provider?: string;
  action: string;
  result: string;
  error_code?: string;
  metadata: Record<string, unknown>;
  previous_hash: string;
  record_hash: string;
}


interface IntegrityResult {
  verified: boolean;
  total_records: number;
  intact_records: number;
  corrupted_records: number;
  tampered_record_ids: string[];
  verification_duration_ms: number;
}

export default function OperationalAuditExplorerPage() {
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [integrity, setIntegrity] = useState<IntegrityResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  
  // Filters
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRecord, setSelectedRecord] = useState<AuditRecord | null>(null);

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    try {
      const data = await opsApi.listAudit<AuditRecord>({
        event_type: eventTypeFilter || undefined,
        severity: severityFilter || undefined,
        trace_id: searchQuery.trim() || undefined,
        limit: 100,
      });
      setRecords(data || []);
    } catch (err) {
      console.error("Failed to load operational audit records", err);
    } finally {
      setLoading(false);
    }
  }, [eventTypeFilter, severityFilter, searchQuery]);

  const verifyIntegrity = useCallback(async () => {
    setVerifying(true);
    try {
      const data = await opsApi.verifyAuditIntegrity<IntegrityResult>();
      if (data) {
        setIntegrity(data);
      }
    } catch (err) {
      console.error("Integrity check failed", err);
    } finally {
      setVerifying(false);
    }
  }, []);

  useEffect(() => {
    fetchRecords();
    verifyIntegrity();
  }, [fetchRecords, verifyIntegrity]);


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
            <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <ShieldCheck className="w-6 h-6 text-indigo-400" />
              Operational Audit Explorer
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Immutable, append-only operational audit trail secured with link-by-link SHA-256 hash chaining.
          </p>
        </div>

        {/* Cryptographic Integrity Status Card */}
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 text-xs flex items-center gap-3">
            <Key className="w-4 h-4 text-indigo-400" />
            <div>
              <div className="text-[10px] text-slate-500 uppercase font-mono">Hash Chain Integrity</div>
              <div className="font-semibold flex items-center gap-1.5">
                {integrity?.verified ? (
                  <span className="text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> INTACT ({integrity.intact_records}/{integrity.total_records})
                  </span>
                ) : (
                  <span className="text-rose-400 flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" /> CORRUPTED ({integrity?.corrupted_records} broken)
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={verifyIntegrity}
              disabled={verifying}
              className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
              title="Re-verify cryptographic chain"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${verifying ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-slate-400 shrink-0" />
          <input
            type="text"
            placeholder="Search by Trace ID, Request ID, or Resource ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchRecords()}
            className="bg-transparent text-xs text-slate-100 placeholder-slate-500 focus:outline-none flex-1 font-mono"
          />
        </div>

        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
        >
          <option value="">All Severities</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
          <option value="CRITICAL">CRITICAL</option>
        </select>

        <select
          value={eventTypeFilter}
          onChange={(e) => setEventTypeFilter(e.target.value)}
          className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
        >
          <option value="">All Event Types</option>
          <option value="WEBHOOK_ACCEPTED">WEBHOOK_ACCEPTED</option>
          <option value="EVENT_QUEUED">EVENT_QUEUED</option>
          <option value="EVENT_PROCESSED">EVENT_PROCESSED</option>
          <option value="EVENT_DEAD_LETTER">EVENT_DEAD_LETTER</option>
          <option value="CIRCUIT_OPENED">CIRCUIT_OPENED</option>
          <option value="LLM_REQUEST">LLM_REQUEST</option>
          <option value="EXECUTION_DELIVERED">EXECUTION_DELIVERED</option>
          <option value="AUTHENTICATION_FAILURE">AUTHENTICATION_FAILURE</option>
        </select>

        <button
          onClick={fetchRecords}
          className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors"
        >
          <Filter className="w-3.5 h-3.5" /> Filter
        </button>
      </div>

      {/* Audit Records Table */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 border-b border-slate-800 text-slate-400 font-semibold font-mono">
              <tr>
                <th className="p-3">Timestamp</th>
                <th className="p-3">Event Type</th>
                <th className="p-3">Action</th>
                <th className="p-3">Severity</th>
                <th className="p-3">Result</th>
                <th className="p-3">Trace ID</th>
                <th className="p-3">Record Hash</th>
                <th className="p-3 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
              {loading ? (
                <tr>
                  <td colSpan={8} className="p-6 text-center text-slate-500 font-sans">
                    Loading audit events...
                  </td>
                </tr>
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-6 text-center text-slate-500 font-sans">
                    No operational audit records match the selected filters.
                  </td>
                </tr>
              ) : (
                records.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="p-3 text-slate-400">{new Date(r.timestamp).toLocaleTimeString()}</td>
                    <td className="p-3 font-semibold text-slate-200">{r.event_type}</td>
                    <td className="p-3 font-sans text-slate-300">{r.action}</td>
                    <td className="p-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          r.severity === "CRITICAL"
                            ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                            : r.severity === "ERROR"
                            ? "bg-rose-500/10 text-rose-400"
                            : r.severity === "WARNING"
                            ? "bg-amber-500/10 text-amber-400"
                            : "bg-slate-800 text-slate-300"
                        }`}
                      >
                        {r.severity}
                      </span>
                    </td>
                    <td className="p-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] ${
                          r.result === "SUCCESS"
                            ? "text-emerald-400 bg-emerald-500/10"
                            : "text-rose-400 bg-rose-500/10"
                        }`}
                      >
                        {r.result}
                      </span>
                    </td>
                    <td className="p-3">
                      {r.trace_id ? (
                        <Link
                          href={`/operations/traces/${encodeURIComponent(r.trace_id)}`}
                          className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                        >
                          {r.trace_id.slice(0, 10)}... <ArrowUpRight className="w-3 h-3" />
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="p-3 text-slate-500">{r.record_hash.slice(0, 12)}...</td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => setSelectedRecord(r)}
                        className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
                        title="View JSON Payload"
                      >
                        <FileCode className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* JSON Payload Inspector Drawer */}
      {selectedRecord && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-2xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                <FileCode className="w-4 h-4 text-indigo-400" />
                Operational Audit Record Detail
              </h3>
              <button
                onClick={() => setSelectedRecord(null)}
                className="p-1 rounded hover:bg-slate-800 text-slate-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs font-mono bg-slate-950 p-3 rounded-lg border border-slate-800">
              <div>
                <span className="text-slate-500 block">Record ID:</span>
                <span className="text-cyan-400">{selectedRecord.id}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Event Type:</span>
                <span className="text-slate-200">{selectedRecord.event_type}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Actor:</span>
                <span className="text-slate-300">{selectedRecord.actor_id || "SYSTEM"}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Trace ID:</span>
                <span className="text-indigo-400">{selectedRecord.trace_id || "None"}</span>
              </div>
            </div>

            <div>
              <span className="text-xs font-medium text-slate-400 block mb-1.5 font-sans">
                Sanitized Metadata Payload (Credential-Free)
              </span>
              <pre className="bg-slate-950 p-3 rounded-lg text-xs font-mono text-emerald-400 overflow-x-auto max-h-60 border border-slate-800">
                {JSON.stringify(selectedRecord.metadata, null, 2)}
              </pre>
            </div>

            <div className="text-[11px] font-mono text-slate-500 space-y-0.5 pt-2 border-t border-slate-800">
              <div>Prev Hash: {selectedRecord.previous_hash}</div>
              <div>Curr Hash: {selectedRecord.record_hash}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
