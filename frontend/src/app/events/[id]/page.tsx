"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Activity,
  ArrowLeft,
  CheckCircle2,
  Clock,
  AlertTriangle,
  FileText,
  ShieldCheck,
  Zap,
  MessageSquare,
  Sparkles,
  Code2,
  RefreshCw,
  Target,
  User,
  Users,
} from "lucide-react";
import { eventsApi, obligationsApi } from "@/lib/api/obligations";
import {
  IngestedEvent,
  EventSemanticRole,
  Obligation,
  EvidenceResponse,
} from "@/lib/types/obligation";

export default function EventDetailPage() {
  const params = useParams();
  const router = useRouter();
  const eventId = params?.id as string;

  const [event, setEvent] = useState<IngestedEvent | null>(null);
  const [obligation, setObligation] = useState<Obligation | null>(null);
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rawTab, setRawTab] = useState(false);

  const loadEvent = useCallback(async () => {
    if (!eventId) return;
    try {
      setLoading(true);
      setError(null);
      const evt = await eventsApi.getById(eventId);
      setEvent(evt);

      if (evt.correlated_obligation_id) {
        try {
          const [ob, evs] = await Promise.all([
            obligationsApi.getById(evt.correlated_obligation_id),
            obligationsApi.getEvidence(evt.correlated_obligation_id).catch(() => []),
          ]);
          setObligation(ob);
          if (evt.evidence_id) {
            const foundEv = evs.find((e: EvidenceResponse) => e.id === evt.evidence_id);
            if (foundEv) setEvidence(foundEv);
          }
        } catch (e) {
          console.warn("Could not fetch correlated obligation:", e);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load event audit details.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    loadEvent();
  }, [loadEvent]);

  const getRoleBadge = (role: EventSemanticRole) => {
    switch (role) {
      case EventSemanticRole.COMPLETION_SIGNAL:
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950/70 text-emerald-300 border border-emerald-800">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Completion Signal
          </span>
        );
      case EventSemanticRole.PROGRESS_UPDATE:
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-blue-950/70 text-blue-300 border border-blue-800">
            <Clock className="w-3.5 h-3.5 text-blue-400" /> Progress Update
          </span>
        );
      case EventSemanticRole.NON_COMPLETION_SIGNAL:
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-rose-950/70 text-rose-300 border border-rose-800">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-400" /> Blocker / Non-Completion
          </span>
        );
      case EventSemanticRole.COMMITMENT:
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-amber-950/70 text-amber-300 border border-amber-800">
            <Zap className="w-3.5 h-3.5 text-amber-400" /> Future Commitment
          </span>
        );
      case EventSemanticRole.REQUEST:
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-purple-950/70 text-purple-300 border border-purple-800">
            <MessageSquare className="w-3.5 h-3.5 text-purple-400" /> Request / Inquiry
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
            Chatter / Irrelevant
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "PROCESSED":
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-teal-950 text-teal-300 border border-teal-800">
            PROCESSED
          </span>
        );
      case "DUPLICATE":
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-amber-950 text-amber-300 border border-amber-800">
            DUPLICATE (SKIPPED)
          </span>
        );
      case "NO_MATCH":
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-slate-800 text-slate-400 border border-slate-700">
            NO OBLIGATION MATCH
          </span>
        );
      case "REJECTED":
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-red-950 text-red-400 border border-red-800">
            REJECTED
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-slate-800 text-slate-300">
            {status}
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <div className="text-center space-y-3">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-cyan-400" />
          <p className="text-slate-400 text-sm">Loading event audit records...</p>
        </div>
      </div>
    );
  }

  if (error || !event) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-8">
        <div className="max-w-3xl mx-auto space-y-6 text-center">
          <div className="p-4 rounded-xl bg-red-950/40 border border-red-800 text-red-300 text-sm">
            {error || "Event audit record not found."}
          </div>
          <button
            onClick={() => router.push("/events")}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-white"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Event Feed
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 lg:p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center justify-between">
          <Link
            href="/events"
            className="inline-flex items-center gap-2 text-sm font-medium text-slate-400 hover:text-cyan-400 transition"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Event Activity Center
          </Link>
          <div className="flex items-center gap-2 text-xs text-slate-500 font-mono">
            ID: {event.id}
          </div>
        </div>

        {/* Hero Header Card */}
        <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900 to-slate-950 border border-slate-800 shadow-xl space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-cyan-950 border border-cyan-800 text-cyan-400">
                <Activity className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2.5 py-0.5 text-xs font-bold rounded bg-slate-800 text-slate-200 border border-slate-700">
                    PROVIDER: {event.provider.toUpperCase()}
                  </span>
                  {getStatusBadge(event.processing_status)}
                  {getRoleBadge(event.semantic_role)}
                </div>
                <h1 className="text-xl font-bold text-white">Event Audit Inspection</h1>
              </div>
            </div>

            <div className="text-right text-xs text-slate-400 space-y-1">
              <div>
                Received At: <strong className="text-slate-200">{new Date(event.received_at).toLocaleString()}</strong>
              </div>
              <div>
                Source Reference: <span className="font-mono text-cyan-300">{event.source_ref || "None"}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Content & Metadata Card */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Main Event Content */}
          <div className="md:col-span-2 space-y-6">
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                  <FileText className="w-4 h-4 text-cyan-400" />
                  Verbatim Message Content
                </h2>
                <button
                  onClick={() => setRawTab(!rawTab)}
                  className="text-xs text-cyan-400 hover:underline flex items-center gap-1"
                >
                  <Code2 className="w-3.5 h-3.5" />
                  {rawTab ? "View Formatted" : "View Raw Payload"}
                </button>
              </div>

              {rawTab ? (
                <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto">
                  {JSON.stringify(event.raw_payload || event, null, 2)}
                </pre>
              ) : (
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800/80 text-slate-100 text-base leading-relaxed italic">
                  &ldquo;{event.content}&rdquo;
                </div>
              )}

              <div className="grid grid-cols-2 gap-4 pt-2 text-xs">
                <div className="flex items-center gap-2 p-3 rounded-lg bg-slate-950/50 border border-slate-800/50">
                  <User className="w-4 h-4 text-slate-400" />
                  <div>
                    <div className="text-slate-500">Sender / Author</div>
                    <div className="font-semibold text-slate-200">{event.sender || "Unknown"}</div>
                  </div>
                </div>

                <div className="flex items-center gap-2 p-3 rounded-lg bg-slate-950/50 border border-slate-800/50">
                  <Users className="w-4 h-4 text-slate-400" />
                  <div>
                    <div className="text-slate-500">Recipients</div>
                    <div className="font-semibold text-slate-200">
                      {event.recipients && event.recipients.length > 0 ? event.recipients.join(", ") : "None specified"}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Semantic Reasoning & Explanation */}
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg space-y-4">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2 border-b border-slate-800 pb-3">
                <Sparkles className="w-4 h-4 text-amber-400" />
                Semantic Classification & Reasoning
              </h2>

              <div className="space-y-3">
                <div>
                  <div className="text-xs text-slate-400 mb-1">Classifier Explanation</div>
                  <div className="text-sm text-slate-200 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                    {event.match_explanation || "No explanation provided."}
                  </div>
                </div>

                {event.correlation_confidence !== null && event.correlation_confidence !== undefined && (
                  <div>
                    <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                      <span>Correlation Confidence</span>
                      <strong className="text-cyan-300 font-bold">
                        {Math.round(event.correlation_confidence * 100)}%
                      </strong>
                    </div>
                    <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-cyan-500 to-emerald-500 transition-all duration-500"
                        style={{ width: `${Math.round(event.correlation_confidence * 100)}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Impact & Correlation Card */}
          <div className="space-y-6">
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg space-y-4">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2 border-b border-slate-800 pb-3">
                <Target className="w-4 h-4 text-cyan-400" />
                Correlated System Entities
              </h2>

              {/* Correlated Obligation */}
              <div className="space-y-2">
                <div className="text-xs font-medium text-slate-400">Matched Obligation</div>
                {obligation ? (
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                    <div className="text-xs font-semibold text-white line-clamp-2">
                      {obligation.action}
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>Owner: {obligation.owner}</span>
                      <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-bold">
                        {obligation.status}
                      </span>
                    </div>
                    <Link
                      href={`/obligations/${obligation.id}`}
                      className="block text-center text-xs font-semibold text-cyan-400 hover:text-cyan-300 pt-1"
                    >
                      Open Obligation &rarr;
                    </Link>
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 italic p-3 rounded-xl bg-slate-950/40 border border-slate-800/40">
                    No active obligation matched.
                  </div>
                )}
              </div>

              {/* Created Evidence Record */}
              <div className="space-y-2 pt-2 border-t border-slate-800/80">
                <div className="text-xs font-medium text-slate-400">Evidence Record</div>
                {evidence ? (
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Status:</span>
                      <span className="px-2 py-0.5 font-bold rounded bg-amber-950 text-amber-300 border border-amber-800">
                        {evidence.correlation_status}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-slate-400">
                      <span>Type:</span>
                      <span className="text-slate-200">{evidence.evidence_type}</span>
                    </div>
                    <div className="text-[11px] text-emerald-400 flex items-center gap-1 pt-1">
                      <ShieldCheck className="w-3.5 h-3.5" /> Preserved for Human Review
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 italic p-3 rounded-xl bg-slate-950/40 border border-slate-800/40">
                    No evidence record generated.
                  </div>
                )}
              </div>

              {/* Action Taken */}
              <div className="pt-2 border-t border-slate-800/80 space-y-1">
                <div className="text-xs font-medium text-slate-400">Action Taken</div>
                <div className="px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-cyan-300">
                  {event.action_taken || "NONE"}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
