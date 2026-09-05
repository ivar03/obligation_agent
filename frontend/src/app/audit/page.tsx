"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  Lock,
  RefreshCw,
  CheckCircle2,
  FileText,
  User,
  Layers,
  Key,
  Eye,
  X,
} from "lucide-react";
import {
  AuditEvent,
  GovernanceSummaryResponse,
  AuditVerificationResponse,
} from "@/lib/types/obligation";
import { auditApi } from "@/lib/api/obligations";
import { useToast } from "@/components/ui/ToastContext";

export default function GovernanceCenterPage() {
  const { toast } = useToast();

  const [summary, setSummary] = useState<GovernanceSummaryResponse | null>(null);
  const [verification, setVerification] = useState<AuditVerificationResponse | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [totalEvents, setTotalEvents] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [verifying, setVerifying] = useState<boolean>(false);
  const [exporting, setExporting] = useState<boolean>(false);

  // Filters
  const [selectedAction, setSelectedAction] = useState<string>("");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("");
  const [selectedEntityType, setSelectedEntityType] = useState<string>("");
  const [activeTab, setActiveTab] = useState<"all" | "security" | "mutations">("all");
  const [page, setPage] = useState<number>(0);
  const pageSize = 25;

  // Selected event for payload inspector modal
  const [inspectedEvent, setInspectedEvent] = useState<AuditEvent | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Load summary & verification
      const [sumRes, verRes] = await Promise.all([
        auditApi.getSummary().catch((e) => {
          console.error("Failed to load governance summary", e);
          return null;
        }),
        auditApi.verify().catch((e) => {
          console.error("Failed to verify audit chain", e);
          return null;
        }),
      ]);

      setSummary(sumRes);
      setVerification(verRes);

      // Load events based on tab
      if (activeTab === "security") {
        const secRes = await auditApi.listSecurityEvents({ limit: pageSize, offset: page * pageSize });
        setEvents(secRes.items);
        setTotalEvents(secRes.total);
      } else {
        const listRes = await auditApi.list({
          action: selectedAction || undefined,
          severity: selectedSeverity || undefined,
          entity_type: selectedEntityType || undefined,
          limit: pageSize,
          offset: page * pageSize,
        });
        setEvents(listRes.items);
        setTotalEvents(listRes.total);
      }
    } catch (err: unknown) {
      console.error(err);
      toast({
        type: "error",
        title: "Access Restricted",
        description: "Governance center requires ADMIN or OWNER role permissions.",
      });
    } finally {
      setLoading(false);
    }
  }, [activeTab, page, selectedAction, selectedSeverity, selectedEntityType, toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleVerifyChain = async () => {
    setVerifying(true);
    try {
      const res = await auditApi.verify();
      setVerification(res);
      if (res.chain_valid) {
        toast({
          type: "success",
          title: "Cryptographic Chain Verified",
          description: `All ${res.verified_event_count} audit events verified with valid SHA-256 hash chaining.`,
        });
      } else {
        toast({
          type: "error",
          title: "Chain Anomaly Detected",
          description: res.message || "Audit chain integrity failed validation.",
        });
      }
    } catch (err: unknown) {
      toast({
        type: "error",
        title: "Verification Failed",
        description: String(err),
      });
    } finally {
      setVerifying(false);
    }
  };

  const handleExport = async (format: "json" | "csv") => {
    setExporting(true);
    try {
      const exportUrl = auditApi.getExportUrl(format, {
        action: selectedAction || undefined,
        entity_type: selectedEntityType || undefined,
        severity: selectedSeverity || undefined,
      });
      // Fetch and trigger download
      const res = await fetch(exportUrl, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("token") || ""}`,
          "X-Workspace-Id": localStorage.getItem("active_workspace_id") || "",
        },
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit_export_${new Date().toISOString().slice(0, 10)}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast({
        type: "success",
        title: "Audit Trail Exported",
        description: `Exported sanitized audit log in ${format.toUpperCase()} format.`,
      });
    } catch (err) {
      toast({
        type: "error",
        title: "Export Failed",
        description: String(err),
      });
    } finally {
      setExporting(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity.toUpperCase()) {
      case "CRITICAL":
        return "bg-rose-500/20 text-rose-300 border-rose-500/40";
      case "ERROR":
        return "bg-amber-500/20 text-amber-300 border-amber-500/40";
      case "WARNING":
        return "bg-yellow-500/20 text-yellow-300 border-yellow-500/40";
      default:
        return "bg-stone-200 text-stone-700 border-stone-300";
    }
  };

  const getActionColor = (action: string) => {
    if (action.includes("SECURITY") || action.includes("DENIED") || action.includes("FAILED")) {
      return "text-rose-400 bg-rose-950/40 border-rose-500/30";
    }
    if (action.includes("CREATED") || action.includes("CONFIRMED") || action.includes("APPROVED")) {
      return "text-emerald-400 bg-emerald-950/40 border-emerald-500/30";
    }
    if (action.includes("DELETED") || action.includes("REMOVED") || action.includes("CANCELLED")) {
      return "text-amber-400 bg-amber-950/40 border-amber-500/30";
    }
    if (action.includes("AUTH_")) {
      return "text-blue-500 bg-indigo-950/40 border-blue-600/30";
    }
    return "text-sky-400 bg-sky-950/40 border-sky-500/30";
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-16">
      {/* Header Banner */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 p-6 bg-gradient-to-r from-stone-100 via-stone-100/90 to-indigo-950/40 border border-stone-200 rounded-3xl shadow-2xl backdrop-blur-xl">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-700/20 border border-blue-600/30 rounded-2xl">
              <ShieldCheck className="w-6 h-6 text-blue-500" />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight text-stone-950 flex items-center gap-2.5">
                Enterprise Governance & Audit Center
              </h1>
              <p className="text-xs text-stone-600">
                Cryptographic SHA-256 hash-chained provenance ledger with zero-secret sanitization & RBAC attribution.
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Chain Integrity Badge */}
          <div
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl border text-xs font-semibold ${
              verification?.chain_valid
                ? "bg-emerald-950/50 border-emerald-500/40 text-emerald-300"
                : "bg-rose-950/50 border-rose-500/40 text-rose-300"
            }`}
          >
            <Shield className="w-3.5 h-3.5" />
            <span>Chain: {verification?.chain_valid ? "Cryptographically Valid" : "Tamper Detected"}</span>
          </div>

          <button
            onClick={handleVerifyChain}
            disabled={verifying}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-stone-200 hover:bg-stone-300 border border-stone-300 text-stone-800 text-xs font-medium transition-all shadow-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${verifying ? "animate-spin" : ""}`} />
            <span>{verifying ? "Verifying..." : "Verify Hash Chain"}</span>
          </button>

          <div className="flex items-center rounded-xl bg-stone-200/80 border border-stone-300 p-0.5">
            <button
              onClick={() => handleExport("json")}
              disabled={exporting}
              className="px-2.5 py-1 rounded-lg text-xs text-stone-700 hover:text-stone-950 hover:bg-stone-300 transition-colors"
            >
              Export JSON
            </button>
            <button
              onClick={() => handleExport("csv")}
              disabled={exporting}
              className="px-2.5 py-1 rounded-lg text-xs text-stone-700 hover:text-stone-950 hover:bg-stone-300 transition-colors"
            >
              Export CSV
            </button>
          </div>
        </div>
      </div>

      {/* Metric Cards Grid */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 1. Total Audited Events */}
          <div className="p-5 rounded-2xl bg-stone-100/60 border border-stone-200/80 shadow-lg space-y-3 relative overflow-hidden">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-stone-600 uppercase tracking-wider">
                Total Audit Trail
              </span>
              <FileText className="w-4 h-4 text-stone-600" />
            </div>
            <div className="text-3xl font-black text-stone-950 font-mono">
              {summary.total_audit_events.toLocaleString()}
            </div>
            <div className="flex items-center gap-3 text-[11px] text-stone-600 pt-1 border-t border-stone-200/60">
              <span>Today: <strong className="text-stone-800">{summary.events_today}</strong></span>
              <span>•</span>
              <span>Mutations: <strong className="text-stone-800">{summary.mutations_today}</strong></span>
            </div>
          </div>

          {/* 2. Security & Access Control */}
          <div className="p-5 rounded-2xl bg-stone-100/60 border border-stone-200/80 shadow-lg space-y-3 relative overflow-hidden">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-rose-300 uppercase tracking-wider">
                Security & Access
              </span>
              <Lock className="w-4 h-4 text-rose-400" />
            </div>
            <div className="text-3xl font-black text-rose-200 font-mono">
              {summary.security_events_count}
            </div>
            <div className="flex items-center gap-3 text-[11px] text-stone-600 pt-1 border-t border-stone-200/60">
              <span>Denials: <strong className="text-rose-300">{summary.permission_denials_count}</strong></span>
              <span>•</span>
              <span>Failed Logins: <strong className="text-amber-300">{summary.failed_logins_count}</strong></span>
            </div>
          </div>

          {/* 3. Governed Decisions */}
          <div className="p-5 rounded-2xl bg-stone-100/60 border border-stone-200/80 shadow-lg space-y-3 relative overflow-hidden">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-emerald-300 uppercase tracking-wider">
                Governed Actions
              </span>
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-3xl font-black text-emerald-200 font-mono">
              {summary.evidence_confirmations_count + summary.interventions_approved_count}
            </div>
            <div className="flex items-center gap-2 text-[11px] text-stone-600 pt-1 border-t border-stone-200/60">
              <span>Approved: <strong className="text-stone-800">{summary.interventions_approved_count}</strong></span>
              <span>•</span>
              <span>Evidence: <strong className="text-stone-800">{summary.evidence_confirmations_count}</strong></span>
              <span>•</span>
              <span>Reconciled: <strong className="text-stone-800">{summary.reconciliation_decisions_count}</strong></span>
            </div>
          </div>

          {/* 4. Provenance Engine */}
          <div className="p-5 rounded-2xl bg-stone-100/60 border border-stone-200/80 shadow-lg space-y-3 relative overflow-hidden">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-blue-600 uppercase tracking-wider">
                Provenance Engine
              </span>
              <Key className="w-4 h-4 text-blue-500" />
            </div>
            <div className="text-sm font-bold text-stone-800 flex items-center gap-2">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>SHA-256 Immutability</span>
            </div>
            <div className="text-[11px] text-stone-600 pt-1 border-t border-stone-200/60">
              <span>Verified count: <strong className="text-stone-800">{verification?.verified_event_count || summary.total_audit_events}</strong> events</span>
            </div>
          </div>
        </div>
      )}

      {/* Top Actors & Entity Types Breakdown */}
      {summary && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Top Actors */}
          <div className="p-5 rounded-2xl bg-stone-100/50 border border-stone-200/80 space-y-3">
            <h3 className="text-xs font-bold text-stone-700 uppercase tracking-wider flex items-center gap-2">
              <User className="w-4 h-4 text-blue-500" />
              <span>Top Actors by Mutation Volume</span>
            </h3>
            <div className="space-y-2">
              {summary.top_actors.length === 0 ? (
                <div className="text-xs text-stone-500 py-3 italic">No human mutation activity recorded yet.</div>
              ) : (
                summary.top_actors.map((actor, idx) => (
                  <div
                    key={actor.actor_user_id || idx}
                    className="flex items-center justify-between p-2.5 bg-stone-50/60 border border-stone-200/60 rounded-xl text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-blue-600/20 text-blue-600 flex items-center justify-center font-bold text-[10px]">
                        {idx + 1}
                      </span>
                      <div>
                        <div className="font-semibold text-stone-800">{actor.actor_name}</div>
                        {actor.actor_email && (
                          <div className="text-[10px] text-stone-500">{actor.actor_email}</div>
                        )}
                      </div>
                    </div>
                    <span className="font-mono font-bold text-stone-700 bg-stone-200 px-2 py-0.5 rounded text-[11px]">
                      {actor.mutation_count} actions
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Most Modified Entities */}
          <div className="p-5 rounded-2xl bg-stone-100/50 border border-stone-200/80 space-y-3">
            <h3 className="text-xs font-bold text-stone-700 uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-400" />
              <span>Activity by Domain Entity</span>
            </h3>
            <div className="space-y-2">
              {summary.most_modified_entities.length === 0 ? (
                <div className="text-xs text-stone-500 py-3 italic">No entity modifications logged yet.</div>
              ) : (
                summary.most_modified_entities.map((ent) => (
                  <div
                    key={ent.entity_type}
                    className="flex items-center justify-between p-2.5 bg-stone-50/60 border border-stone-200/60 rounded-xl text-xs"
                  >
                    <div className="flex items-center gap-2 capitalize font-semibold text-stone-700">
                      <span className="w-2 h-2 rounded-full bg-emerald-400" />
                      <span>{ent.entity_type}</span>
                    </div>
                    <span className="font-mono font-bold text-stone-700 bg-stone-200 px-2 py-0.5 rounded text-[11px]">
                      {ent.mutation_count} events
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Audit Log Feed Controls & Filters */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-2 border-b border-stone-200">
          {/* Tabs */}
          <div className="flex items-center gap-1.5 p-1 bg-stone-100 border border-stone-200 rounded-xl text-xs">
            <button
              onClick={() => {
                setActiveTab("all");
                setPage(0);
              }}
              className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                activeTab === "all"
                  ? "bg-blue-700 text-stone-950 shadow-sm"
                  : "text-stone-600 hover:text-stone-800"
              }`}
            >
              All Events ({totalEvents})
            </button>
            <button
              onClick={() => {
                setActiveTab("security");
                setPage(0);
              }}
              className={`px-3 py-1.5 rounded-lg font-medium transition-colors flex items-center gap-1.5 ${
                activeTab === "security"
                  ? "bg-rose-600 text-stone-950 shadow-sm"
                  : "text-stone-600 hover:text-rose-300"
              }`}
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>Security Anomaly Feed</span>
            </button>
          </div>

          {/* Filters (Active only on "all" tab) */}
          {activeTab === "all" && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <select
                value={selectedAction}
                onChange={(e) => {
                  setSelectedAction(e.target.value);
                  setPage(0);
                }}
                className="px-2.5 py-1.5 rounded-lg bg-stone-100 border border-stone-200 text-stone-700"
              >
                <option value="">All Action Types</option>
                <option value="OBLIGATION_CREATED">OBLIGATION_CREATED</option>
                <option value="OBLIGATION_STATUS_CHANGED">OBLIGATION_STATUS_CHANGED</option>
                <option value="OBLIGATION_DELETED">OBLIGATION_DELETED</option>
                <option value="EVIDENCE_CONFIRMED">EVIDENCE_CONFIRMED</option>
                <option value="INTERVENTION_APPROVED">INTERVENTION_APPROVED</option>
                <option value="INTERVENTION_EXECUTED">INTERVENTION_EXECUTED</option>
                <option value="RECONCILIATION_RESOLVED">RECONCILIATION_RESOLVED</option>
                <option value="WORKSPACE_MEMBER_INVITED">WORKSPACE_MEMBER_INVITED</option>
                <option value="PERMISSION_DENIED">PERMISSION_DENIED</option>
                <option value="AUTH_LOGIN">AUTH_LOGIN</option>
                <option value="AUTH_LOGIN_FAILED">AUTH_LOGIN_FAILED</option>
              </select>

              <select
                value={selectedSeverity}
                onChange={(e) => {
                  setSelectedSeverity(e.target.value);
                  setPage(0);
                }}
                className="px-2.5 py-1.5 rounded-lg bg-stone-100 border border-stone-200 text-stone-700"
              >
                <option value="">All Severities</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>

              <select
                value={selectedEntityType}
                onChange={(e) => {
                  setSelectedEntityType(e.target.value);
                  setPage(0);
                }}
                className="px-2.5 py-1.5 rounded-lg bg-stone-100 border border-stone-200 text-stone-700"
              >
                <option value="">All Entities</option>
                <option value="obligation">Obligation</option>
                <option value="intervention">Intervention</option>
                <option value="evidence">Evidence</option>
                <option value="reconciliation">Reconciliation</option>
                <option value="workspace">Workspace</option>
                <option value="user">User</option>
              </select>
            </div>
          )}
        </div>

        {/* Audit Log Table */}
        <div className="bg-stone-100/60 border border-stone-200 rounded-2xl shadow-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-stone-50/80 border-b border-stone-200 text-stone-600 font-semibold uppercase tracking-wider">
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Entity</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Source</th>
                  <th className="py-3 px-4">Hash Verification</th>
                  <th className="py-3 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-200/60">
                {loading ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-stone-500">
                      <div className="flex items-center justify-center gap-2">
                        <RefreshCw className="w-4 h-4 animate-spin text-blue-500" />
                        <span>Loading audit records...</span>
                      </div>
                    </td>
                  </tr>
                ) : events.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-stone-500">
                      No audit events match the selected criteria.
                    </td>
                  </tr>
                ) : (
                  events.map((ev) => (
                    <tr
                      key={ev.id}
                      className="hover:bg-stone-200/40 transition-colors group cursor-pointer"
                      onClick={() => setInspectedEvent(ev)}
                    >
                      <td className="py-3 px-4 whitespace-nowrap text-stone-600 font-mono text-[11px]">
                        {new Date(ev.timestamp).toLocaleString()}
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-bold border ${getActionColor(
                            ev.action
                          )}`}
                        >
                          {ev.action}
                        </span>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        {ev.entity_type ? (
                          <div className="flex items-center gap-1.5 text-stone-700">
                            <span className="font-semibold capitalize">{ev.entity_type}</span>
                            {ev.entity_id && (
                              <span className="font-mono text-[10px] text-stone-500">
                                ({ev.entity_id.slice(0, 8)}...)
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-stone-400">—</span>
                        )}
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-stone-800">
                            {ev.actor_name || (ev.source === "SYSTEM_WORKER" ? "System Worker" : "Anonymous")}
                          </span>
                          {ev.actor_role && (
                            <span className="px-1.5 py-0.2 rounded text-[10px] bg-stone-200 text-stone-600 border border-stone-300">
                              {ev.actor_role}
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getSeverityBadge(
                            ev.severity
                          )}`}
                        >
                          {ev.severity}
                        </span>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap text-stone-600 text-[11px]">
                        {ev.source}
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap font-mono text-[11px]">
                        <div className="flex items-center gap-1.5 text-emerald-400">
                          <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
                          <span title={ev.event_hash}>{ev.event_hash.slice(0, 10)}...</span>
                        </div>
                      </td>

                      <td className="py-3 px-4 text-right whitespace-nowrap">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setInspectedEvent(ev);
                          }}
                          className="p-1 rounded hover:bg-stone-300 text-stone-600 hover:text-stone-950 transition-colors"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div className="flex items-center justify-between px-4 py-3 bg-stone-50/60 border-t border-stone-200 text-xs text-stone-600">
            <div>
              Showing {events.length > 0 ? page * pageSize + 1 : 0} to{" "}
              {Math.min((page + 1) * pageSize, totalEvents)} of {totalEvents} records
            </div>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="px-3 py-1 rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 disabled:opacity-40"
              >
                Previous
              </button>
              <button
                disabled={(page + 1) * pageSize >= totalEvents}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1 rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Payload Inspector Modal */}
      {inspectedEvent && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-stone-100 border border-stone-200 rounded-3xl max-w-2xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-bold border ${getActionColor(
                      inspectedEvent.action
                    )}`}
                  >
                    {inspectedEvent.action}
                  </span>
                  <span className="text-xs text-stone-600 font-mono">ID: {inspectedEvent.id}</span>
                </div>
                <h3 className="text-base font-bold text-stone-950">Audit Event Details</h3>
              </div>
              <button
                onClick={() => setInspectedEvent(null)}
                className="p-1 rounded-lg text-stone-600 hover:text-stone-950 hover:bg-stone-200"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Metadata Overview */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-stone-50 rounded-xl border border-stone-200/80 space-y-1">
                <span className="text-stone-500 font-medium">Actor / Attribution</span>
                <div className="font-semibold text-stone-800">
                  {inspectedEvent.actor_name || "System Worker"}
                </div>
                {inspectedEvent.actor_email && (
                  <div className="text-[11px] text-stone-600">{inspectedEvent.actor_email}</div>
                )}
                {inspectedEvent.actor_role && (
                  <div className="text-[10px] text-stone-500">Role: {inspectedEvent.actor_role}</div>
                )}
              </div>

              <div className="p-3 bg-stone-50 rounded-xl border border-stone-200/80 space-y-1">
                <span className="text-stone-500 font-medium">Correlation & Origin</span>
                <div className="text-stone-800">Source: {inspectedEvent.source}</div>
                {inspectedEvent.ip_address && (
                  <div className="text-[11px] text-stone-600 font-mono">IP: {inspectedEvent.ip_address}</div>
                )}
                {inspectedEvent.request_id && (
                  <div className="text-[10px] text-stone-500 font-mono">
                    Req: {inspectedEvent.request_id.slice(0, 16)}...
                  </div>
                )}
              </div>
            </div>

            {/* Reason */}
            {inspectedEvent.reason && (
              <div className="p-3 bg-stone-50 rounded-xl border border-stone-200/80 text-xs">
                <span className="text-stone-500 font-medium block mb-0.5">Stated Reason / Justification:</span>
                <span className="text-stone-800 italic">&ldquo;{inspectedEvent.reason}&rdquo;</span>
              </div>
            )}

            {/* State Diffs: Before & After */}
            {(inspectedEvent.before_state || inspectedEvent.after_state) && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider">
                  State Mutation Diff
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-[11px] font-semibold text-stone-600 block mb-1">
                      Before State
                    </span>
                    <pre className="p-3 bg-stone-50 rounded-xl border border-stone-200 text-[11px] font-mono text-stone-700 overflow-x-auto">
                      {inspectedEvent.before_state
                        ? JSON.stringify(inspectedEvent.before_state, null, 2)
                        : "null"}
                    </pre>
                  </div>
                  <div>
                    <span className="text-[11px] font-semibold text-emerald-400 block mb-1">
                      After State
                    </span>
                    <pre className="p-3 bg-stone-50 rounded-xl border border-stone-200 text-[11px] font-mono text-emerald-300 overflow-x-auto">
                      {inspectedEvent.after_state
                        ? JSON.stringify(inspectedEvent.after_state, null, 2)
                        : "null"}
                    </pre>
                  </div>
                </div>
              </div>
            )}

            {/* Cryptographic Hash Details */}
            <div className="p-3 bg-stone-50 rounded-xl border border-stone-200 space-y-1.5 text-xs font-mono">
              <span className="text-stone-500 font-medium block font-sans">
                Cryptographic SHA-256 Provenance Proof
              </span>
              <div>
                <span className="text-stone-500">Event Hash: </span>
                <span className="text-emerald-400 break-all">{inspectedEvent.event_hash}</span>
              </div>
              <div>
                <span className="text-stone-500">Previous Hash: </span>
                <span className="text-stone-600 break-all">
                  {inspectedEvent.previous_event_hash || "0000000000000000000000000000000000000000000000000000000000000000 (GENESIS)"}
                </span>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setInspectedEvent(null)}
                className="px-4 py-2 rounded-xl bg-stone-200 hover:bg-stone-300 text-stone-800 text-xs font-semibold transition-colors"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
