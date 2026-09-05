"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldCheck,
  Send,
  FileCheck,
  RotateCcw,
  XCircle,
  ExternalLink,
  MessageSquare,
  Lock,
  Layers,
} from "lucide-react";
import { executionApi } from "@/lib/api/obligations";
import { ExecutionRecord, ExecutionReceipt } from "@/lib/types/obligation";

export default function ExecutionDetailPage() {
  const params = useParams();
  const executionId = params?.id as string;

  const [execution, setExecution] = useState<ExecutionRecord | null>(null);
  const [receipt, setReceipt] = useState<ExecutionReceipt | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [cancelModal, setCancelModal] = useState<boolean>(false);
  const [cancelReason, setCancelReason] = useState<string>("");

  const fetchExecution = useCallback(async () => {
    if (!executionId) return;
    setLoading(true);
    setError(null);
    try {
      const [rec, rct] = await Promise.all([
        executionApi.getById(executionId),
        executionApi.getReceipt(executionId).catch(() => null),
      ]);
      setExecution(rec);
      setReceipt(rct);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load execution record.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [executionId]);

  useEffect(() => {
    fetchExecution();
  }, [fetchExecution]);

  const handleRetry = async () => {
    if (!execution) return;
    setActionLoading(true);
    try {
      const retried = await executionApi.retry(execution.id);
      setExecution(retried);
      await fetchExecution();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to retry execution.";
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!execution) return;
    setActionLoading(true);
    try {
      const cancelled = await executionApi.cancel(execution.id, {
        reason: cancelReason || "Cancelled by operator",
      });
      setExecution(cancelled);
      setCancelModal(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to cancel execution.";
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex flex-col items-center justify-center text-stone-600">
        <RefreshCw className="w-8 h-8 animate-spin mb-3 text-violet-400" />
        <p className="text-sm">Loading execution receipt and outcome provenance...</p>
      </div>
    );
  }

  if (error && !execution) {
    return (
      <div className="min-h-screen bg-stone-50 text-stone-900 p-8">
        <div className="max-w-2xl mx-auto bg-stone-100 border border-stone-200 rounded-xl p-6 text-center">
          <AlertTriangle className="w-12 h-12 text-rose-400 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-stone-950 mb-2">Error Loading Execution Record</h2>
          <p className="text-sm text-stone-600 mb-4">{error}</p>
          <Link
            href="/intelligence"
            className="inline-flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-stone-950 rounded-lg text-sm transition"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Intelligence Center
          </Link>
        </div>
      </div>
    );
  }

  if (!execution) return null;

  return (
    <div className="min-h-screen bg-stone-50 text-stone-900 p-4 sm:p-8">
      {/* Top Navigation */}
      <div className="max-w-5xl mx-auto flex items-center justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <Link
            href="/intelligence"
            className="p-2 rounded-lg bg-stone-100 border border-stone-200 text-stone-600 hover:text-stone-950 hover:bg-stone-200 transition"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="text-xs font-mono uppercase tracking-wider text-stone-600 flex items-center gap-2">
              <span>Phase 16 Controlled Execution</span>
              <span>•</span>
              <span className="text-violet-400">{execution.provider.toUpperCase()} PROVIDER</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-stone-950 tracking-tight flex items-center gap-2">
              Execution Record
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-stone-200 text-stone-700">
                {execution.id}
              </span>
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {execution.status === "FAILED" && execution.retry_count < execution.max_retries && (
            <button
              onClick={handleRetry}
              disabled={actionLoading}
              className="px-3.5 py-1.5 bg-violet-600 hover:bg-violet-500 text-stone-950 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition shadow"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Retry Execution
            </button>
          )}

          {["PENDING_AUTHORIZATION", "AUTHORIZED", "QUEUED"].includes(execution.status) && (
            <button
              onClick={() => setCancelModal(true)}
              disabled={actionLoading}
              className="px-3 py-1.5 bg-stone-200 hover:bg-rose-900/40 text-rose-300 border border-stone-300 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition"
            >
              <XCircle className="w-3.5 h-3.5" /> Cancel
            </button>
          )}

          <button
            onClick={fetchExecution}
            className="p-2 rounded-lg bg-stone-100 border border-stone-200 text-stone-600 hover:text-stone-950 transition"
            title="Refresh status"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="max-w-5xl mx-auto space-y-6">
        {/* Safety Boundary Notice */}
        <div className="bg-gradient-to-r from-violet-950/40 via-stone-100/60 to-indigo-950/40 border border-violet-500/30 rounded-xl p-4 flex items-start gap-3 shadow-lg">
          <ShieldCheck className="w-5 h-5 text-violet-400 flex-shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <div className="font-bold text-violet-200 uppercase tracking-wider text-[11px]">
              Human-Controlled Execution & Verification Invariant
            </div>
            <p className="text-stone-700 leading-relaxed">
              Successful provider delivery notifies the commitment owner. <strong>Provider delivery does NOT complete the obligation.</strong> Obligation completion is strictly gated behind authoritative evidence submission and human confirmation.
            </p>
          </div>
        </div>

        {/* 10-Step Lifecycle State Banner */}
        <div className="bg-stone-100/80 border border-stone-200 rounded-xl p-5 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <span className="text-xs text-stone-600 uppercase tracking-wider block font-semibold">
                Lifecycle State
              </span>
              <div className="text-lg font-bold text-stone-950 flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${
                  execution.status === "RESOLVED"
                    ? "bg-emerald-400"
                    : execution.status === "FAILED" || execution.status === "CANCELLED"
                    ? "bg-rose-400"
                    : execution.status === "OUTCOME_DETECTED"
                    ? "bg-blue-500"
                    : "bg-violet-400 animate-pulse"
                }`} />
                {execution.status}
              </div>
            </div>

            <div className="flex items-center gap-3 text-xs">
              <div className="bg-stone-50/80 px-3 py-1.5 rounded-lg border border-stone-200">
                <span className="text-stone-500 block text-[10px]">Provider Ref</span>
                <strong className="font-mono text-violet-300">{execution.provider_execution_ref || "None"}</strong>
              </div>
              <div className="bg-stone-50/80 px-3 py-1.5 rounded-lg border border-stone-200">
                <span className="text-stone-500 block text-[10px]">Retries</span>
                <strong className="text-stone-800">{execution.retry_count} / {execution.max_retries}</strong>
              </div>
              <div className="bg-stone-50/80 px-3 py-1.5 rounded-lg border border-stone-200">
                <span className="text-stone-500 block text-[10px]">Outcome</span>
                <strong className="text-stone-800">{execution.outcome || "PENDING"}</strong>
              </div>
            </div>
          </div>

          {/* Timeline Progress Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-2 text-[11px] font-medium text-center">
            <div className={`p-2 rounded border ${
              ["AUTHORIZED", "QUEUED", "EXECUTING", "DELIVERED", "RESPONSE_PENDING", "OUTCOME_DETECTED", "RESOLVED"].includes(execution.status)
                ? "bg-emerald-950/30 border-emerald-500/40 text-emerald-300"
                : "bg-stone-50/50 border-stone-200 text-stone-500"
            }`}>
              1. Authorized
            </div>
            <div className={`p-2 rounded border ${
              ["EXECUTING", "DELIVERED", "RESPONSE_PENDING", "OUTCOME_DETECTED", "RESOLVED"].includes(execution.status)
                ? "bg-emerald-950/30 border-emerald-500/40 text-emerald-300"
                : "bg-stone-50/50 border-stone-200 text-stone-500"
            }`}>
              2. Dispatched
            </div>
            <div className={`p-2 rounded border ${
              ["DELIVERED", "RESPONSE_PENDING", "OUTCOME_DETECTED", "RESOLVED"].includes(execution.status)
                ? "bg-emerald-950/30 border-emerald-500/40 text-emerald-300"
                : "bg-stone-50/50 border-stone-200 text-stone-500"
            }`}>
              3. Delivered
            </div>
            <div className={`p-2 rounded border ${
              ["OUTCOME_DETECTED", "RESOLVED"].includes(execution.status)
                ? "bg-indigo-950/30 border-blue-600/40 text-blue-600"
                : "bg-stone-50/50 border-stone-200 text-stone-500"
            }`}>
              4. Response Detected
            </div>
            <div className={`p-2 rounded border ${
              execution.status === "RESOLVED"
                ? "bg-emerald-950/40 border-emerald-400 text-emerald-200 font-bold"
                : "bg-stone-50/50 border-stone-200 text-stone-500"
            }`}>
              5. Final Resolved
            </div>
          </div>
        </div>

        {/* 2-Column Grid: Receipt & Audit Provenance */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Left Column: Immutable Execution Receipt */}
          <div className="bg-stone-100/80 border border-stone-200 rounded-xl p-5 shadow-sm space-y-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-600 flex items-center gap-2">
              <FileCheck className="w-4 h-4 text-violet-400" /> Immutable Execution Receipt
            </h2>

            <div className="space-y-2.5 text-xs">
              <div className="bg-stone-50/70 p-3 rounded-lg border border-stone-200 space-y-1.5">
                <div className="flex justify-between text-stone-600">
                  <span>Decision Plan</span>
                  <Link
                    href={`/intelligence/decisions/${execution.obligation_id}`}
                    className="text-violet-400 hover:underline flex items-center gap-1 font-mono"
                  >
                    View Plan <ExternalLink className="w-3 h-3" />
                  </Link>
                </div>
                <div className="flex justify-between text-stone-600">
                  <span>Target Obligation</span>
                  <Link
                    href={`/obligations/${execution.obligation_id}`}
                    className="text-violet-400 hover:underline flex items-center gap-1 font-mono"
                  >
                    {execution.obligation_id.slice(0, 12)}... <ExternalLink className="w-3 h-3" />
                  </Link>
                </div>
                <div className="flex justify-between text-stone-600">
                  <span>Authorized By</span>
                  <strong className="text-stone-800">{execution.authorized_by || "System"}</strong>
                </div>
                <div className="flex justify-between text-stone-600">
                  <span>Authorized At</span>
                  <span className="text-stone-800">
                    {execution.authorized_at ? new Date(execution.authorized_at).toLocaleString() : "N/A"}
                  </span>
                </div>
                <div className="flex justify-between text-stone-600">
                  <span>Executed At</span>
                  <span className="text-stone-800">
                    {execution.executed_at ? new Date(execution.executed_at).toLocaleString() : "Pending"}
                  </span>
                </div>
                <div className="flex justify-between text-stone-600">
                  <span>Delivery Status</span>
                  <span className="px-2 py-0.5 rounded font-mono text-[10px] bg-stone-200 text-stone-800">
                    {execution.delivery_status || "PENDING"}
                  </span>
                </div>
              </div>

              {/* Action Content */}
              <div className="bg-stone-50/70 p-3 rounded-lg border border-stone-200 space-y-2">
                <span className="text-stone-500 uppercase text-[10px] font-bold block">
                  Dispatched Message Payload
                </span>
                <div className="p-2.5 bg-stone-100 rounded border border-stone-200 text-stone-800 font-mono text-xs leading-relaxed">
                  {(execution.safe_request_metadata?.message_snippet as string) || "No message content recorded."}
                </div>
                <div className="text-[11px] text-stone-600">
                  Recipient: <strong className="text-stone-800">{(execution.safe_request_metadata?.recipient as string) || "Unassigned"}</strong>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Security & Cryptographic Hashes */}
          <div className="bg-stone-100/80 border border-stone-200 rounded-xl p-5 shadow-sm space-y-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-600 flex items-center gap-2">
              <Lock className="w-4 h-4 text-emerald-400" /> Cryptographic Integrity & Redaction
            </h2>

            <div className="space-y-3 text-xs">
              <div className="bg-stone-50/70 p-3 rounded-lg border border-stone-200 space-y-2">
                <div>
                  <span className="text-stone-500 block text-[10px] uppercase font-bold">SHA-256 Idempotency Key</span>
                  <code className="text-stone-700 font-mono text-[11px] break-all block bg-stone-100 p-1.5 rounded mt-1 border border-stone-200/80">
                    {execution.idempotency_key}
                  </code>
                </div>
                <div>
                  <span className="text-stone-500 block text-[10px] uppercase font-bold">Payload Hash</span>
                  <code className="text-stone-700 font-mono text-[11px] break-all block bg-stone-100 p-1.5 rounded mt-1 border border-stone-200/80">
                    {execution.request_payload_hash}
                  </code>
                </div>
              </div>

              <div className="p-3 bg-emerald-950/20 border border-emerald-500/20 rounded-lg text-emerald-300 text-xs space-y-1">
                <div className="font-semibold flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Credential Zero-Leakage Guarantee
                </div>
                <p className="text-[11px] text-emerald-300/80">
                  All API keys, bot tokens, and authentication secrets are redacted prior to payload persistence and receipt generation.
                </p>
              </div>

              {execution.failure_reason && (
                <div className="p-3 bg-rose-950/30 border border-rose-500/30 rounded-lg text-rose-300 text-xs space-y-1">
                  <div className="font-semibold flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-rose-400" /> Failure Reason ({execution.failure_code})
                  </div>
                  <p className="text-[11px] text-rose-200 font-mono">
                    {execution.failure_reason}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Cancel Modal */}
      {cancelModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-stone-100 border border-stone-200 rounded-xl p-6 max-w-md w-full shadow-2xl">
            <h3 className="text-base font-bold text-stone-950 mb-2">Cancel Execution</h3>
            <p className="text-xs text-stone-600 mb-4">
              Cancelling execution halts pending queue dispatch and marks the record CANCELLED.
            </p>
            <textarea
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="Reason for cancellation..."
              className="w-full bg-stone-50 border border-stone-200 rounded-lg p-3 text-xs text-stone-800 focus:ring-2 focus:ring-rose-500 outline-none mb-4"
              rows={3}
            />
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setCancelModal(false)}
                className="px-3 py-1.5 text-xs text-stone-600 hover:text-stone-800"
              >
                Dismiss
              </button>
              <button
                onClick={handleCancel}
                disabled={actionLoading}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-stone-950 font-medium text-xs rounded-lg transition"
              >
                Confirm Cancellation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
