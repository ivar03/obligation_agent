"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Activity,
  Zap,
  Filter,
  CheckCircle2,
  Clock,
  AlertTriangle,
  FileText,
  RefreshCw,
  Search,
  ExternalLink,
  ShieldCheck,
  Send,
  MessageSquare,
  Sparkles,
  Info,
} from "lucide-react";
import { eventsApi } from "@/lib/api/obligations";
import {
  IngestedEvent,
  EventSemanticRole,
  ProviderInfo,
  IngestionResultResponse,
} from "@/lib/types/obligation";

export default function EventsActivityCenterPage() {
  const [events, setEvents] = useState<IngestedEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<IngestionResultResponse | null>(null);

  // Filters
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [selectedRole, setSelectedRole] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string>("");
  const [searchRef, setSearchRef] = useState<string>("");

  // Custom Event Modal
  const [showCustomModal, setShowCustomModal] = useState(false);
  const [customProvider, setCustomProvider] = useState("mock");
  const [customSender, setCustomSender] = useState("Rahul");
  const [customRecipients, setCustomRecipients] = useState("Ravi");
  const [customContent, setCustomContent] = useState("");
  const [customRef, setCustomRef] = useState("");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [eventRes, provRes] = await Promise.all([
        eventsApi.list({
          provider: selectedProvider || undefined,
          semantic_role: (selectedRole as EventSemanticRole) || undefined,
          processing_status: selectedStatus || undefined,
          source_ref: searchRef || undefined,
          limit: 50,
        }),
        eventsApi.listProviders().catch(() => []),
      ]);

      setEvents(eventRes.items || []);
      setTotal(eventRes.total || 0);
      setProviders(provRes || []);
    } catch (err) {
      console.error("Failed to load events:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedProvider, selectedRole, selectedStatus, searchRef]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSimulate = async (scenario: string, label: string) => {
    try {
      setSimulating(scenario);
      const result = await eventsApi.simulate({ scenario });
      setLastResult(result);
      await loadData();
    } catch (err) {
      console.error(`Failed to simulate scenario ${label}:`, err);
    } finally {
      setSimulating(null);
    }
  };

  const handleCustomIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customContent.trim()) return;

    try {
      setSimulating("custom");
      const result = await eventsApi.ingestRaw(customProvider, {
        sender: customSender,
        recipients: customRecipients.split(",").map((s) => s.trim()).filter(Boolean),
        content: customContent,
        source_ref: customRef || `manual_${Date.now()}`,
      });
      setLastResult(result);
      setShowCustomModal(false);
      setCustomContent("");
      setCustomRef("");
      await loadData();
    } catch (err) {
      console.error("Failed to ingest custom event:", err);
    } finally {
      setSimulating(null);
    }
  };

  // Metric Computations
  const processedCount = events.filter((e) => e.processing_status === "PROCESSED").length;
  const duplicateCount = events.filter((e) => e.processing_status === "DUPLICATE").length;
  const evidenceCount = events.filter((e) => e.evidence_id).length;

  const getRoleBadge = (role: EventSemanticRole) => {
    switch (role) {
      case EventSemanticRole.COMPLETION_SIGNAL:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/60 text-emerald-300 border border-emerald-800/60">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Completion Signal
          </span>
        );
      case EventSemanticRole.PROGRESS_UPDATE:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-950/60 text-blue-300 border border-blue-800/60">
            <Clock className="w-3 h-3 text-blue-400" /> Progress Update
          </span>
        );
      case EventSemanticRole.NON_COMPLETION_SIGNAL:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-950/60 text-rose-300 border border-rose-800/60">
            <AlertTriangle className="w-3 h-3 text-rose-400" /> Blocker / Non-Completion
          </span>
        );
      case EventSemanticRole.COMMITMENT:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/60 text-amber-300 border border-amber-800/60">
            <Zap className="w-3 h-3 text-amber-400" /> Commitment
          </span>
        );
      case EventSemanticRole.REQUEST:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-950/60 text-purple-300 border border-purple-800/60">
            <MessageSquare className="w-3 h-3 text-purple-400" /> Request
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800/80 text-slate-400 border border-slate-700/60">
            Chatter / Irrelevant
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "PROCESSED":
        return (
          <span className="px-2 py-0.5 text-xs font-bold rounded bg-teal-950 text-teal-300 border border-teal-800/50">
            PROCESSED
          </span>
        );
      case "DUPLICATE":
        return (
          <span className="px-2 py-0.5 text-xs font-bold rounded bg-amber-950/70 text-amber-300 border border-amber-800/50">
            DUPLICATE
          </span>
        );
      case "NO_MATCH":
        return (
          <span className="px-2 py-0.5 text-xs font-bold rounded bg-slate-800 text-slate-400 border border-slate-700">
            NO MATCH
          </span>
        );
      case "REJECTED":
        return (
          <span className="px-2 py-0.5 text-xs font-bold rounded bg-red-950 text-red-400 border border-red-800/50">
            REJECTED
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 text-xs font-bold rounded bg-slate-800 text-slate-300">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 lg:p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2.5 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-600 shadow-lg shadow-cyan-900/30">
                <Activity className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                  Event Activity Center
                  <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800/60">
                    Phase 7 Active
                  </span>
                </h1>
                <p className="text-sm text-slate-400">
                  Continuous provider event ingestion, deduplication, semantic correlation, and immutable audit logs.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowCustomModal(true)}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
            >
              <Send className="w-4 h-4 text-cyan-400" />
              Ingest Custom Event
            </button>
            <button
              onClick={loadData}
              disabled={loading}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white shadow-md shadow-cyan-950 transition disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Refresh Feed
            </button>
          </div>
        </div>

        {/* Live Simulation Toolbar */}
        <div className="p-5 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900 to-slate-950 border border-slate-800 shadow-xl">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 font-semibold text-white text-sm mb-1">
                <Sparkles className="w-4 h-4 text-amber-400" />
                Live Event Simulator Toolbar
              </div>
              <p className="text-xs text-slate-400">
                Trigger canonical provider scenarios to observe automated classification, deduplication, and intervention correlation in real-time.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => handleSimulate("SCENARIO_A_COMPLETION", "Scenario A")}
                disabled={simulating !== null}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-950/70 hover:bg-emerald-900 text-emerald-300 border border-emerald-800/70 transition flex items-center gap-1.5 disabled:opacity-50"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                Scenario A (Completion)
              </button>

              <button
                onClick={() => handleSimulate("SCENARIO_B_PROGRESS", "Scenario B")}
                disabled={simulating !== null}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-950/70 hover:bg-blue-900 text-blue-300 border border-blue-800/70 transition flex items-center gap-1.5 disabled:opacity-50"
              >
                <Clock className="w-3.5 h-3.5" />
                Scenario B (Progress)
              </button>

              <button
                onClick={() => handleSimulate("SCENARIO_C_BLOCKER", "Scenario C")}
                disabled={simulating !== null}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-950/70 hover:bg-rose-900 text-rose-300 border border-rose-800/70 transition flex items-center gap-1.5 disabled:opacity-50"
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                Scenario C (Blocker)
              </button>

              <button
                onClick={() => handleSimulate("SCENARIO_D_REQUEST", "Scenario D")}
                disabled={simulating !== null}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-purple-950/70 hover:bg-purple-900 text-purple-300 border border-purple-800/70 transition flex items-center gap-1.5 disabled:opacity-50"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                Scenario D (Request)
              </button>

              <button
                onClick={() => handleSimulate("SCENARIO_E_CHATTER", "Scenario E")}
                disabled={simulating !== null}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center gap-1.5 disabled:opacity-50"
              >
                <Info className="w-3.5 h-3.5" />
                Scenario E (Chatter)
              </button>
            </div>
          </div>

          {/* Last Simulation Toast */}
          {lastResult && (
            <div className="mt-4 pt-4 border-t border-slate-800 flex items-center justify-between text-xs">
              <div className="flex items-center gap-3">
                <span className="text-slate-400 font-medium">Last Ingestion Result:</span>
                {getStatusBadge(lastResult.status)}
                {getRoleBadge(lastResult.semantic_role)}
                <span className="text-slate-300 italic">{lastResult.message}</span>
              </div>
              <Link
                href={`/events/${lastResult.event_id}`}
                className="text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1"
              >
                Inspect Event Audit <ExternalLink className="w-3 h-3" />
              </Link>
            </div>
          )}
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="text-xs font-medium text-slate-400 mb-1">Total Ingested Events</div>
            <div className="text-2xl font-bold text-white">{total}</div>
            <div className="text-xs text-cyan-400 mt-1 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" /> Immutable Audit Log
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="text-xs font-medium text-slate-400 mb-1">Correlated & Processed</div>
            <div className="text-2xl font-bold text-teal-400">{processedCount}</div>
            <div className="text-xs text-slate-400 mt-1">
              {total > 0 ? `${Math.round((processedCount / total) * 100)}% match rate` : "No events"}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="text-xs font-medium text-slate-400 mb-1">Suggested Evidence Created</div>
            <div className="text-2xl font-bold text-emerald-400">{evidenceCount}</div>
            <div className="text-xs text-slate-400 mt-1">Pending human confirmation</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="text-xs font-medium text-slate-400 mb-1">Deduplicated (Skipped)</div>
            <div className="text-2xl font-bold text-amber-400">{duplicateCount}</div>
            <div className="text-xs text-slate-400 mt-1">Idempotency guaranteed</div>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
              <Filter className="w-3.5 h-3.5 text-cyan-400" />
              Filter By:
            </div>

            {/* Provider Filter */}
            <select
              value={selectedProvider}
              onChange={(e) => setSelectedProvider(e.target.value)}
              aria-label="Filter by provider"
              className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Providers</option>
              {providers.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name.toUpperCase()} (v{p.version})
                </option>
              ))}
            </select>

            {/* Semantic Role Filter */}
            <select
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
              aria-label="Filter by semantic role"
              className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Semantic Roles</option>
              <option value={EventSemanticRole.COMPLETION_SIGNAL}>Completion Signal</option>
              <option value={EventSemanticRole.PROGRESS_UPDATE}>Progress Update</option>
              <option value={EventSemanticRole.NON_COMPLETION_SIGNAL}>Blocker / Non-Completion</option>
              <option value={EventSemanticRole.COMMITMENT}>Commitment</option>
              <option value={EventSemanticRole.REQUEST}>Request</option>
              <option value={EventSemanticRole.IRRELEVANT}>Chatter / Irrelevant</option>
            </select>

            {/* Status Filter */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              aria-label="Filter by processing status"
              className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Statuses</option>
              <option value="PROCESSED">Processed</option>
              <option value="DUPLICATE">Duplicate</option>
              <option value="NO_MATCH">No Match</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </div>

          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search source ref..."
              value={searchRef}
              onChange={(e) => setSearchRef(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg pl-8 pr-3 py-1.5 w-48 focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        {/* Live Ingestion Feed Table */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 overflow-hidden shadow-xl">
          <div className="px-6 py-4 border-b border-slate-800/80 flex items-center justify-between">
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <FileText className="w-4 h-4 text-cyan-400" />
              Event Ingestion Audit Trail ({events.length} records shown)
            </h2>
            <span className="text-xs text-slate-400">Sorted by newest received</span>
          </div>

          {loading ? (
            <div className="p-12 text-center text-slate-400">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-cyan-500" />
              Loading event activity feed...
            </div>
          ) : events.length === 0 ? (
            <div className="p-12 text-center text-slate-500">
              <Activity className="w-8 h-8 mx-auto mb-2 opacity-50 text-slate-600" />
              No events found matching current criteria.
              <div className="mt-3">
                <button
                  onClick={() => handleSimulate("SCENARIO_A_COMPLETION", "Scenario A")}
                  className="text-xs text-cyan-400 hover:underline"
                >
                  Run Simulation Scenario A to populate live data &rarr;
                </button>
              </div>
            </div>
          ) : (
            <div className="divide-y divide-slate-800/60">
              {events.map((evt) => (
                <div
                  key={evt.id}
                  className="p-5 hover:bg-slate-800/40 transition flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="space-y-2 flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="px-2 py-0.5 text-[11px] font-bold rounded bg-slate-800 text-slate-300 border border-slate-700">
                        {evt.provider.toUpperCase()}
                      </span>
                      {getStatusBadge(evt.processing_status)}
                      {getRoleBadge(evt.semantic_role)}
                      {evt.source_ref && (
                        <span className="text-xs text-slate-400 font-mono">
                          Ref: {evt.source_ref}
                        </span>
                      )}
                    </div>

                    <p className="text-sm font-medium text-slate-200 line-clamp-2">
                      &ldquo;{evt.content}&rdquo;
                    </p>

                    <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
                      <span>
                        From: <strong className="text-slate-300">{evt.sender || "Unknown"}</strong>
                      </span>
                      {evt.recipients && evt.recipients.length > 0 && (
                        <span>
                          To: <strong className="text-slate-300">{evt.recipients.join(", ")}</strong>
                        </span>
                      )}
                      <span>
                        Received: {new Date(evt.received_at).toLocaleTimeString()} (
                        {new Date(evt.received_at).toLocaleDateString()})
                      </span>
                    </div>

                    {evt.match_explanation && (
                      <div className="text-xs text-slate-400 bg-slate-950/60 p-2 rounded-lg border border-slate-800/60 flex items-start gap-2">
                        <Info className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0 mt-0.5" />
                        <span>{evt.match_explanation}</span>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col md:items-end gap-2 shrink-0">
                    {evt.correlation_confidence !== null && evt.correlation_confidence !== undefined && (
                      <div className="text-right">
                        <div className="text-[11px] text-slate-400 font-medium">Correlation Confidence</div>
                        <div className="text-sm font-bold text-cyan-300">
                          {Math.round(evt.correlation_confidence * 100)}%
                        </div>
                      </div>
                    )}

                    <div className="flex items-center gap-2">
                      {evt.correlated_obligation_id && (
                        <Link
                          href={`/obligations/${evt.correlated_obligation_id}`}
                          className="px-3 py-1 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center gap-1"
                        >
                          View Obligation <ExternalLink className="w-3 h-3" />
                        </Link>
                      )}

                      <Link
                        href={`/events/${evt.id}`}
                        className="px-3 py-1 text-xs font-semibold rounded-lg bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800/60 transition flex items-center gap-1"
                      >
                        Inspect Audit <ExternalLink className="w-3 h-3" />
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Custom Event Ingestion Modal */}
      {showCustomModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Send className="w-4 h-4 text-cyan-400" />
                Ingest Custom External Event
              </h3>
              <button
                onClick={() => setShowCustomModal(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCustomIngest} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Provider Adapter</label>
                <select
                  value={customProvider}
                  onChange={(e) => setCustomProvider(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value="mock">Mock Provider (Default)</option>
                  <option value="direct">Direct Normalized</option>
                  <option value="slack">Slack Mock Adapter</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Sender Name</label>
                  <input
                    type="text"
                    value={customSender}
                    onChange={(e) => setCustomSender(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Recipient(s)</label>
                  <input
                    type="text"
                    value={customRecipients}
                    onChange={(e) => setCustomRecipients(e.target.value)}
                    placeholder="e.g. Ravi, Team"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Source Reference (Optional)</label>
                <input
                  type="text"
                  value={customRef}
                  onChange={(e) => setCustomRef(e.target.value)}
                  placeholder="e.g. msg_123456"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 font-mono text-xs"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Event Content / Message</label>
                <textarea
                  rows={4}
                  value={customContent}
                  onChange={(e) => setCustomContent(e.target.value)}
                  placeholder="e.g. Sent the database benchmark numbers to the team."
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCustomModal(false)}
                  className="px-4 py-2 text-xs font-medium rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={simulating !== null}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white shadow-md shadow-cyan-950 transition disabled:opacity-50"
                >
                  {simulating ? "Ingesting..." : "Ingest Event"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
