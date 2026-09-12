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
      setSimulating(label);
      const result = await eventsApi.simulate({ scenario });
      setLastResult(result);
      await loadData();
    } catch (err) {
      console.error("Simulation failed:", err);
    } finally {
      setSimulating(null);
    }
  };

  const handleCustomIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customContent.trim()) return;

    try {
      setSimulating("Custom Ingestion");
      const result = await eventsApi.ingestRaw(customProvider, {
        source_ref: customRef.trim() || undefined,
        sender: customSender.trim() || undefined,
        recipients: customRecipients ? customRecipients.split(",").map((s) => s.trim()) : [],
        content: customContent.trim(),
      });
      setLastResult(result);
      setShowCustomModal(false);
      setCustomContent("");
      setCustomRef("");
      await loadData();
    } catch (err) {
      console.error("Custom ingest failed:", err);
    } finally {
      setSimulating(null);
    }
  };

  const processedCount = events.filter((e) => e.processing_status === "PROCESSED").length;
  const duplicateCount = events.filter((e) => e.processing_status === "DUPLICATE").length;
  const evidenceCount = events.filter((e) => e.evidence_id).length;

  const getRoleBadge = (role?: EventSemanticRole | string) => {
    switch (role) {
      case EventSemanticRole.COMPLETION_SIGNAL:
      case "COMPLETION_SIGNAL":
        return (
          <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
            Completion Signal
          </span>
        );
      case EventSemanticRole.NON_COMPLETION_SIGNAL:
      case "NON_COMPLETION_SIGNAL":
        return (
          <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-rose-50 text-rose-700 border border-rose-200">
            Blocker Detected
          </span>
        );
      case EventSemanticRole.PROGRESS_UPDATE:
      case "PROGRESS_UPDATE":
        return (
          <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-orange-50 text-orange-700 border border-orange-200">
            Progress Update
          </span>
        );
      case EventSemanticRole.COMMITMENT:
      case "COMMITMENT":
        return (
          <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-orange-50 text-orange-700 border border-orange-200">
            Commitment
          </span>
        );
      case EventSemanticRole.REQUEST:
      case "REQUEST":
        return (
          <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-amber-50 text-amber-700 border border-amber-200">
            Request
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-slate-100 text-slate-600 border border-slate-200">
            {role || "Unclassified"}
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "PROCESSED":
        return (
          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
            PROCESSED
          </span>
        );
      case "DUPLICATE":
        return (
          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-amber-50 text-amber-800 border border-amber-200">
            DUPLICATE (SKIPPED)
          </span>
        );
      case "REJECTED":
        return (
          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-rose-50 text-rose-700 border border-rose-200">
            REJECTED
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-slate-100 text-slate-700 border border-slate-200">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 text-[10px] font-bold rounded-full bg-orange-100 text-orange-800 border border-orange-200">
              Activity Stream
            </span>
            <span className="text-xs text-slate-500">• Real-Time Signal Processing</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2.5">
            <Activity className="w-6 h-6 text-orange-600" />
            Activity Center
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Continuous provider signal ingestion, deduplication, semantic correlation, and immutable event logs.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setShowCustomModal(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 transition-colors"
          >
            <Send className="w-3.5 h-3.5 text-orange-600" />
            <span>Simulate Signal</span>
          </button>
          <button
            onClick={loadData}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-orange-600 hover:bg-orange-700 text-white shadow-xs transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh Feed</span>
          </button>
        </div>
      </div>

      {/* Live Simulation Toolbar */}
      <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-3">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 font-bold text-slate-900 text-xs mb-0.5">
              <Sparkles className="w-4 h-4 text-orange-600" />
              <span>Demonstration Scenarios</span>
            </div>
            <p className="text-xs text-slate-500">
              Trigger realistic provider signals to observe automatic semantic extraction and correlation in real time.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => handleSimulate("SCENARIO_A_COMPLETION", "Scenario A")}
              disabled={simulating !== null}
              className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 transition flex items-center gap-1.5 disabled:opacity-50"
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Completion Signal</span>
            </button>

            <button
              onClick={() => handleSimulate("SCENARIO_B_PROGRESS", "Scenario B")}
              disabled={simulating !== null}
              className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-orange-50 hover:bg-orange-100 text-orange-800 border border-orange-200 transition flex items-center gap-1.5 disabled:opacity-50"
            >
              <Clock className="w-3.5 h-3.5 text-orange-600" />
              <span>Progress Update</span>
            </button>

            <button
              onClick={() => handleSimulate("SCENARIO_C_BLOCKER", "Scenario C")}
              disabled={simulating !== null}
              className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-800 border border-rose-200 transition flex items-center gap-1.5 disabled:opacity-50"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
              <span>Blocker Alert</span>
            </button>

            <button
              onClick={() => handleSimulate("SCENARIO_D_REQUEST", "Scenario D")}
              disabled={simulating !== null}
              className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-stone-100 hover:bg-stone-200 text-stone-800 border border-stone-300 transition flex items-center gap-1.5 disabled:opacity-50"
            >
              <MessageSquare className="w-3.5 h-3.5 text-stone-600" />
              <span>Clarification Request</span>
            </button>
          </div>
        </div>

        {/* Last Simulation Toast */}
        {lastResult && (
          <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2.5">
              <span className="text-slate-500 font-medium">Last Result:</span>
              {getStatusBadge(lastResult.status)}
              {getRoleBadge(lastResult.semantic_role)}
              <span className="text-slate-700 italic">{lastResult.message}</span>
            </div>
          </div>
        )}
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs">
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Total Ingested Events</div>
          <div className="text-2xl font-extrabold text-slate-900">{total}</div>
          <div className="text-xs text-orange-600 mt-1 flex items-center gap-1 font-medium">
            <ShieldCheck className="w-3.5 h-3.5" /> Immutable Audit Log
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs">
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Correlated &amp; Processed</div>
          <div className="text-2xl font-extrabold text-emerald-700">{processedCount}</div>
          <div className="text-xs text-slate-500 mt-1">
            {total > 0 ? `${Math.round((processedCount / total) * 100)}% match rate` : "Ready"}
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs">
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Evidence Discovered</div>
          <div className="text-2xl font-extrabold text-slate-900">{evidenceCount}</div>
          <div className="text-xs text-slate-500 mt-1">Grounding commitments</div>
        </div>

        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs">
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Deduplicated</div>
          <div className="text-2xl font-extrabold text-slate-900">{duplicateCount}</div>
          <div className="text-xs text-slate-500 mt-1">Idempotency guaranteed</div>
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
            <Filter className="w-3.5 h-3.5 text-orange-600" />
            Filter:
          </div>

          {/* Provider Filter */}
          <select
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
            aria-label="Filter by provider"
            className="bg-slate-50 border border-slate-200 text-slate-800 text-xs rounded-xl px-3 py-1.5 focus:outline-none focus:border-orange-400"
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
            className="bg-slate-50 border border-slate-200 text-slate-800 text-xs rounded-xl px-3 py-1.5 focus:outline-none focus:border-orange-400"
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
            className="bg-slate-50 border border-slate-200 text-slate-800 text-xs rounded-xl px-3 py-1.5 focus:outline-none focus:border-orange-400"
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
            placeholder="Search reference..."
            value={searchRef}
            onChange={(e) => setSearchRef(e.target.value)}
            className="bg-slate-50 border border-slate-200 text-slate-800 text-xs rounded-xl pl-8 pr-3 py-1.5 w-48 focus:outline-none focus:border-orange-400"
          />
        </div>
      </div>

      {/* Feed List */}
      <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-xs">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <FileText className="w-4 h-4 text-orange-600" />
            Ingested Signals ({events.length})
          </h2>
          <span className="text-xs text-slate-500">Sorted by most recent</span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-orange-600" />
            Loading signals feed...
          </div>
        ) : events.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-xs space-y-2">
            <Activity className="w-8 h-8 mx-auto text-slate-400" />
            <p>No events found matching current criteria.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {events.map((evt) => (
              <div
                key={evt.id}
                className="p-5 hover:bg-slate-50 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-2 flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`px-2 py-0.5 text-[10px] font-bold rounded-md border uppercase ${
                        evt.provider.toLowerCase() === "slack"
                          ? "bg-slate-100 text-slate-700 border-slate-200"
                          : evt.provider.toLowerCase() === "gmail"
                          ? "bg-rose-50 text-rose-700 border-rose-200"
                          : evt.provider.toLowerCase() === "google_calendar" || evt.provider.toLowerCase() === "calendar"
                          ? "bg-amber-50 text-amber-800 border-amber-200"
                          : "bg-slate-100 text-slate-700 border-slate-200"
                      }`}
                    >
                      {evt.provider}
                    </span>
                    {getStatusBadge(evt.processing_status)}
                    {getRoleBadge(evt.semantic_role)}
                    {evt.source_ref && (
                      <span className="text-xs text-slate-500 font-mono">
                        Ref: {evt.source_ref}
                      </span>
                    )}
                  </div>

                  <p className="text-xs font-semibold text-slate-900 leading-relaxed">
                    &ldquo;{evt.content}&rdquo;
                  </p>

                  <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
                    <span>
                      From: <strong className="text-slate-800">{evt.sender || "Unknown"}</strong>
                    </span>
                    {evt.recipients && evt.recipients.length > 0 && (
                      <span>
                        To: <strong className="text-slate-800">{evt.recipients.join(", ")}</strong>
                      </span>
                    )}
                    <span>
                      {new Date(evt.received_at).toLocaleTimeString()} ({new Date(evt.received_at).toLocaleDateString()})
                    </span>
                  </div>

                  {evt.match_explanation && (
                    <div className="text-xs text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-100 flex items-start gap-2">
                      <Info className="w-3.5 h-3.5 text-orange-600 shrink-0 mt-0.5" />
                      <span>{evt.match_explanation}</span>
                    </div>
                  )}
                </div>

                <div className="flex flex-col md:items-end gap-2 shrink-0">
                  {evt.correlated_obligation_id && (
                    <Link
                      href={`/obligations/${evt.correlated_obligation_id}`}
                      className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-orange-50 hover:bg-orange-100 text-orange-800 border border-orange-200 transition-colors flex items-center gap-1.5"
                    >
                      <span>View Obligation</span>
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Custom Event Ingestion Modal */}
      {showCustomModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Send className="w-4 h-4 text-orange-600" />
                <span>Simulate External Signal Ingestion</span>
              </h3>
              <button
                onClick={() => setShowCustomModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCustomIngest} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Provider Source</label>
                  <select
                    value={customProvider}
                    onChange={(e) => setCustomProvider(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-slate-900"
                  >
                    <option value="slack">Slack</option>
                    <option value="gmail">Gmail</option>
                    <option value="google_calendar">Google Calendar</option>
                    <option value="jira">Jira Cloud</option>
                    <option value="mock">Generic Mock</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Source Reference</label>
                  <input
                    type="text"
                    value={customRef}
                    onChange={(e) => setCustomRef(e.target.value)}
                    placeholder="slack-thread-99"
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-slate-900"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Sender</label>
                  <input
                    type="text"
                    value={customSender}
                    onChange={(e) => setCustomSender(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-slate-900"
                  />
                </div>

                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Recipients (comma-separated)</label>
                  <input
                    type="text"
                    value={customRecipients}
                    onChange={(e) => setCustomRecipients(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-slate-900"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Message / Event Content</label>
                <textarea
                  rows={3}
                  value={customContent}
                  onChange={(e) => setCustomContent(e.target.value)}
                  placeholder="e.g. 'Priya Sharma: Benchmark tests finished successfully and metrics are now uploaded.'"
                  required
                  className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-slate-900"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCustomModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={simulating !== null}
                  className="px-5 py-2 rounded-xl bg-orange-600 hover:bg-orange-700 text-white font-semibold"
                >
                  Ingest Signal
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
