"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Sparkles,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  Settings2,
  Activity,
  Check,
  ArrowRight,
  FileCheck,
  Paperclip,
} from "lucide-react";
import {
  ExtractionResponse,
  MessageContext,
  EventAnalysisResponse,
  EventIngestionResponse,
} from "@/lib/types/obligation";
import { obligationsApi } from "@/lib/api/obligations";
import { ReviewCard } from "@/components/obligations/ReviewCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/ToastContext";

const CANONICAL_EXTRACTION_SCENARIOS = [
  {
    label: "1. 1st Person (Resolved Date)",
    desc: "Explicit commitment with relative date",
    text: "I will send Rahul the API documentation tomorrow.",
  },
  {
    label: "2. 2nd Person (Rahul Owes)",
    desc: "Direct addressed request",
    text: "Rahul, please send me the database benchmark numbers by Friday.",
  },
  {
    label: "3. Ambiguous Group ('We')",
    desc: "Unassigned team commitment",
    text: "We should probably send this to the client tomorrow.",
  },
  {
    label: "4. Conditional Trigger",
    desc: "Gated by dependency, no fake date",
    text: "Ravi will finish the report once Rahul sends the database numbers.",
  },
  {
    label: "5. Ambiguous Deadline",
    desc: "Vague temporal expression",
    text: "Can you get this done sometime soon?",
  },
];

const CANONICAL_EVENT_SCENARIOS = [
  {
    label: "1. Completion Signal + Attachment",
    desc: "Fulfillment match for Rahul's numbers",
    sender: "Rahul",
    recipients: "Ravi",
    source_type: "slack",
    content: "Attached benchmark_results.csv in #dev-database.",
    has_attachment: true,
    attachment_name: "benchmark_results.csv",
  },
  {
    label: "2. Completion Signal (API Docs)",
    desc: "Fulfillment match for Ravi's docs obligation",
    sender: "Ravi",
    recipients: "Rahul",
    source_type: "email",
    content: "Sent the API documentation to Rahul.",
    has_attachment: false,
    attachment_name: "",
  },
  {
    label: "3. Future Commitment (Not Completion)",
    desc: "Future promise should NOT mark completed",
    sender: "Ravi",
    recipients: "Rahul",
    source_type: "message",
    content: "I will send the project report tomorrow.",
    has_attachment: false,
    attachment_name: "",
  },
  {
    label: "4. Negative / Blocker Signal",
    desc: "Inability/delay signal",
    sender: "Ravi",
    recipients: "Rahul",
    source_type: "message",
    content: "Couldn't send the report because the client rejected the proposal.",
    has_attachment: false,
    attachment_name: "",
  },
];

export default function CapturePage() {
  const router = useRouter();
  const { toast } = useToast();

  const [mode, setMode] = useState<"extraction" | "event_simulator">("extraction");

  // Extraction Form State
  const [inputMessage, setInputMessage] = useState("");
  const [showContextPanel, setShowContextPanel] = useState(false);
  const [sender, setSender] = useState("");
  const [recipients, setRecipients] = useState("");
  const [refDatetime, setRefDatetime] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [extractionResult, setExtractionResult] = useState<ExtractionResponse | null>(null);

  // Event Simulator Form State
  const [eventSender, setEventSender] = useState("Rahul");
  const [eventRecipients, setEventRecipients] = useState("Ravi");
  const [eventSourceType, setEventSourceType] = useState("slack");
  const [eventSourceRef, setEventSourceRef] = useState("sim_evt_101");
  const [eventContent, setEventContent] = useState("Attached benchmark_results.csv in #dev-database.");
  const [hasAttachment, setHasAttachment] = useState(true);
  const [attachmentName, setAttachmentName] = useState("benchmark_results.csv");
  const [eventAnalysis, setEventAnalysis] = useState<EventAnalysisResponse | null>(null);
  const [eventIngestionResult, setEventIngestionResult] = useState<EventIngestionResponse | null>(null);

  const handleAnalyzeExtraction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim()) return;

    try {
      setAnalyzing(true);
      setExtractionResult(null);

      let contextPayload: MessageContext | null = null;
      if (sender.trim() || recipients.trim()) {
        contextPayload = {
          sender: sender.trim() || undefined,
          recipients: recipients.split(",").map((s) => s.trim()).filter(Boolean),
          current_user: "You",
        };
      }

      const refDateIso = refDatetime ? new Date(refDatetime).toISOString() : null;

      const result = await obligationsApi.extractCandidate(
        inputMessage.trim(),
        contextPayload,
        refDateIso
      );
      setExtractionResult(result);

      if (!result.detected) {
        toast({
          type: "info",
          title: "No Obligation Detected",
          description: result.reason || "The message did not contain an actionable commitment.",
        });
      } else {
        toast({
          type: "success",
          title: "Candidate Extracted & Analyzed",
          description: "Please review ownership reasoning, deadline resolution, and ambiguities.",
        });
      }
    } catch (err) {
      toast({
        type: "error",
        title: "Extraction Failed",
        description: err instanceof Error ? err.message : "Could not analyze message.",
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAnalyzeEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!eventContent.trim()) return;

    try {
      setAnalyzing(true);
      setEventAnalysis(null);
      setEventIngestionResult(null);

      const metadata: Record<string, unknown> = {};
      if (hasAttachment && attachmentName.trim()) {
        metadata.attachments = [{ name: attachmentName.trim(), size: 2048 }];
      }

      const result = await obligationsApi.analyzeEvent({
        source_type: eventSourceType,
        source_ref: eventSourceRef.trim() || undefined,
        sender: eventSender.trim() || undefined,
        recipients: eventRecipients.split(",").map((s) => s.trim()).filter(Boolean),
        content: eventContent.trim(),
        metadata,
      });

      setEventAnalysis(result);
      toast({
        type: "success",
        title: "Event Analyzed",
        description: `Classified as ${result.semantic_role}. Found ${result.matches.length} candidate match(es).`,
      });
    } catch (err) {
      toast({
        type: "error",
        title: "Event Analysis Failed",
        description: err instanceof Error ? err.message : "Could not analyze event.",
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleIngestEvent = async () => {
    if (!eventContent.trim()) return;

    try {
      setAnalyzing(true);
      const metadata: Record<string, unknown> = {};
      if (hasAttachment && attachmentName.trim()) {
        metadata.attachments = [{ name: attachmentName.trim(), size: 2048 }];
      }

      const result = await obligationsApi.ingestEvent({
        source_type: eventSourceType,
        source_ref: eventSourceRef.trim() || `evt_${Date.now()}`,
        sender: eventSender.trim() || undefined,
        recipients: eventRecipients.split(",").map((s) => s.trim()).filter(Boolean),
        content: eventContent.trim(),
        metadata,
      });

      setEventIngestionResult(result);
      toast({
        type: "success",
        title: "Event Ingested",
        description: `Created ${result.evidence_records.length} suggested evidence record(s).`,
      });
    } catch (err) {
      toast({
        type: "error",
        title: "Ingestion Failed",
        description: err instanceof Error ? err.message : "Could not ingest event.",
      });
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
            <Sparkles className="w-7 h-7 text-blue-400" />
            <span>AI Obligation & Event Intelligence</span>
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Extract new obligations or correlate external fulfillment events with existing commitments.
          </p>
        </div>

        {/* Mode Selector Tabs */}
        <div className="flex items-center p-1 bg-zinc-900 border border-zinc-800 rounded-xl">
          <button
            onClick={() => setMode("extraction")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              mode === "extraction"
                ? "bg-blue-600/20 text-blue-300 border border-blue-500/30"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Extract Obligation
          </button>
          <button
            onClick={() => setMode("event_simulator")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              mode === "event_simulator"
                ? "bg-emerald-600/20 text-emerald-300 border border-emerald-500/30"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Event Correlation Simulator
          </button>
        </div>
      </div>

      {/* MODE 1: OBLIGATION EXTRACTION PIPELINE */}
      {mode === "extraction" && (
        <div className="space-y-6">
          {/* Canonical Scenarios Accordion / Chips */}
          <div className="space-y-2">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block">
              Quick Test Scenarios:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
              {CANONICAL_EXTRACTION_SCENARIOS.map((sc, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    setInputMessage(sc.text);
                    setExtractionResult(null);
                  }}
                  className="p-2.5 rounded-xl bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 hover:bg-zinc-850 text-left transition-all text-xs space-y-0.5 group"
                >
                  <div className="font-semibold text-zinc-200 group-hover:text-blue-400 transition-colors">
                    {sc.label}
                  </div>
                  <div className="text-[11px] text-zinc-400 line-clamp-1">{sc.text}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Main Input Form */}
          <form
            onSubmit={handleAnalyzeExtraction}
            className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4"
          >
            <div>
              <label htmlFor="raw-message" className="block text-xs font-semibold text-zinc-300 mb-2">
                Raw Communication Text / Message
              </label>
              <textarea
                id="raw-message"
                rows={4}
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Paste an email, Slack message, or commitment snippet..."
                className="w-full px-4 py-3 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors resize-y font-normal"
                required
              />
            </div>

            {/* Collapsible Context Config */}
            <div className="border border-zinc-800 rounded-xl overflow-hidden bg-zinc-950/60">
              <button
                type="button"
                onClick={() => setShowContextPanel(!showContextPanel)}
                className="w-full px-4 py-2.5 flex items-center justify-between text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Settings2 className="w-3.5 h-3.5 text-blue-400" />
                  <span>Advanced Context & Reference Timestamp</span>
                </div>
                {showContextPanel ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>

              {showContextPanel && (
                <div className="p-4 border-t border-zinc-800/80 grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-zinc-400 mb-1">Sender</label>
                    <input
                      type="text"
                      value={sender}
                      onChange={(e) => setSender(e.target.value)}
                      placeholder="e.g. Rahul"
                      className="w-full px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-200"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-zinc-400 mb-1">
                      Recipients (comma-separated)
                    </label>
                    <input
                      type="text"
                      value={recipients}
                      onChange={(e) => setRecipients(e.target.value)}
                      placeholder="e.g. Ravi, Team"
                      className="w-full px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-200"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-zinc-400 mb-1">
                      Reference Time
                    </label>
                    <input
                      type="datetime-local"
                      value={refDatetime}
                      onChange={(e) => setRefDatetime(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-200"
                    />
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end">
              <button
                type="submit"
                disabled={analyzing || !inputMessage.trim()}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-all shadow-md shadow-blue-600/20 active:scale-95 disabled:opacity-50"
              >
                <Sparkles className={`w-4 h-4 ${analyzing ? "animate-spin" : ""}`} />
                <span>{analyzing ? "Reasoning..." : "Analyze & Extract Obligation"}</span>
              </button>
            </div>
          </form>

          {/* Candidate Review Card */}
          {extractionResult && extractionResult.detected && extractionResult.obligation && (
            <div className="space-y-3 animate-in fade-in">
              <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400">
                <ShieldCheck className="w-4 h-4" />
                <span>Human-in-the-Loop Confirmation Required</span>
              </div>
              <ReviewCard
                candidate={extractionResult.obligation}
                rawText={extractionResult.raw_text || inputMessage}
                onConfirmed={() => router.push("/")}
                onReject={() => setExtractionResult(null)}
              />
            </div>
          )}
        </div>
      )}

      {/* MODE 2: PHASE 4 EVENT CORRELATION SIMULATOR */}
      {mode === "event_simulator" && (
        <div className="space-y-6">
          {/* Canonical Event Scenarios */}
          <div className="space-y-2">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block">
              Test Event Scenarios:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2">
              {CANONICAL_EVENT_SCENARIOS.map((sc, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    setEventSender(sc.sender);
                    setEventRecipients(sc.recipients);
                    setEventSourceType(sc.source_type);
                    setEventContent(sc.content);
                    setHasAttachment(sc.has_attachment);
                    setAttachmentName(sc.attachment_name);
                    setEventAnalysis(null);
                    setEventIngestionResult(null);
                  }}
                  className="p-2.5 rounded-xl bg-zinc-900/80 border border-zinc-800 hover:border-zinc-700 hover:bg-zinc-850 text-left transition-all text-xs space-y-0.5 group"
                >
                  <div className="font-semibold text-zinc-200 group-hover:text-emerald-400 transition-colors">
                    {sc.label}
                  </div>
                  <div className="text-[11px] text-zinc-400 line-clamp-1">{sc.content}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Event Ingestion & Simulation Form */}
          <form
            onSubmit={handleAnalyzeEvent}
            className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4"
          >
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Sender / Actor</label>
                <input
                  type="text"
                  value={eventSender}
                  onChange={(e) => setEventSender(e.target.value)}
                  placeholder="e.g. Rahul"
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Recipients (comma-separated)
                </label>
                <input
                  type="text"
                  value={eventRecipients}
                  onChange={(e) => setEventRecipients(e.target.value)}
                  placeholder="e.g. Ravi"
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Source Type</label>
                <select
                  value={eventSourceType}
                  onChange={(e) => setEventSourceType(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100"
                >
                  <option value="slack">Slack Message</option>
                  <option value="email">Email</option>
                  <option value="file">File Attachment</option>
                  <option value="audit_log">System Audit Log</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Source Ref ID</label>
                <input
                  type="text"
                  value={eventSourceRef}
                  onChange={(e) => setEventSourceRef(e.target.value)}
                  placeholder="e.g. msg_123"
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1">
                Event Content / Observation Text
              </label>
              <textarea
                rows={3}
                value={eventContent}
                onChange={(e) => setEventContent(e.target.value)}
                placeholder="e.g. Attached benchmark_results.csv or Sent the API documentation..."
                className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100 resize-y"
                required
              />
            </div>

            {/* Attachment Config */}
            <div className="flex flex-wrap items-center gap-4 pt-1">
              <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasAttachment}
                  onChange={(e) => setHasAttachment(e.target.checked)}
                  className="rounded border-zinc-800 text-blue-600"
                />
                <span>Includes Attachment</span>
              </label>

              {hasAttachment && (
                <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                  <Paperclip className="w-3.5 h-3.5 text-zinc-500" />
                  <input
                    type="text"
                    value={attachmentName}
                    onChange={(e) => setAttachmentName(e.target.value)}
                    placeholder="e.g. benchmark_results.csv"
                    className="px-2.5 py-1 rounded bg-zinc-950 border border-zinc-800 text-xs text-zinc-200 w-52"
                  />
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-800">
              <button
                type="submit"
                disabled={analyzing || !eventContent.trim()}
                className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold transition-all"
              >
                Analyze Event (Stateless)
              </button>
              <button
                type="button"
                onClick={handleIngestEvent}
                disabled={analyzing || !eventContent.trim()}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all shadow-md shadow-emerald-600/20 active:scale-95"
              >
                <FileCheck className="w-4 h-4" />
                <span>Ingest & Create Suggested Evidence</span>
              </button>
            </div>
          </form>

          {/* Ingestion Success Banner */}
          {eventIngestionResult && (
            <div className="bg-emerald-950/30 border border-emerald-500/40 rounded-2xl p-5 shadow-xl space-y-2 animate-in fade-in">
              <div className="flex items-center gap-2 text-emerald-300 font-bold text-sm">
                <FileCheck className="w-5 h-5 text-emerald-400" />
                <span>Event Ingested Successfully</span>
              </div>
              <p className="text-xs text-zinc-300">
                Created {eventIngestionResult.evidence_records.length} suggested evidence record(s).
                View and confirm completion directly on the obligation page or below.
              </p>
            </div>
          )}

          {/* Event Analysis Results */}
          {eventAnalysis && (
            <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4 animate-in fade-in">
              <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-bold text-white">Event Correlation Results</h3>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  Role: {eventAnalysis.semantic_role}
                </span>
              </div>

              <p className="text-xs text-zinc-300 italic">{eventAnalysis.summary}</p>

              {eventAnalysis.matches.length === 0 ? (
                <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800/60 text-xs text-zinc-500 text-center">
                  No active obligations matched this event.
                </div>
              ) : (
                <div className="space-y-3">
                  {eventAnalysis.matches.map((match) => (
                    <div
                      key={match.obligation_id}
                      className={`p-4 rounded-xl border space-y-2.5 ${
                        match.is_completion_candidate
                          ? "bg-emerald-950/20 border-emerald-500/40"
                          : "bg-zinc-950 border-zinc-800"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-zinc-100">
                            [{match.owner} &rarr; {match.beneficiary}]
                          </span>
                          <StatusBadge status={match.status} />
                        </div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`font-bold ${
                              match.correlation_confidence >= 0.80
                                ? "text-emerald-400"
                                : match.correlation_confidence >= 0.60
                                ? "text-amber-400"
                                : "text-zinc-400"
                            }`}
                          >
                            Match: {Math.round(match.correlation_confidence * 100)}% ({match.confidence_level})
                          </span>
                          <Link
                            href={`/obligations/${match.obligation_id}`}
                            className="inline-flex items-center gap-1 text-blue-400 hover:underline font-semibold"
                          >
                            <span>Open Obligation</span>
                            <ArrowRight className="w-3 h-3" />
                          </Link>
                        </div>
                      </div>

                      <p className="text-xs text-zinc-200 font-medium">{match.action}</p>

                      {/* Signals */}
                      <div className="space-y-1 pt-1 border-t border-zinc-900 text-[11px]">
                        {match.matched_signals.map((s, si) => (
                          <div key={si} className="flex items-center gap-1 text-emerald-300">
                            <Check className="w-3 h-3 shrink-0" />
                            <span>{s}</span>
                          </div>
                        ))}
                        {match.unmatched_signals.map((s, si) => (
                          <div key={si} className="flex items-center gap-1 text-zinc-500">
                            <span className="shrink-0">&times;</span>
                            <span>{s}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
