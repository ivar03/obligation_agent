"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Radio,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  Zap,
  Lock,
  Copy,
  Check,
  Sparkles,
  ArrowRight,
  Sliders,
  MessageSquare,
  Mail,
  Calendar,
  Layers,
  Cpu,
} from "lucide-react";
import { integrationsApi, jiraApi, llmApi } from "@/lib/api/obligations";
import {
  IntegrationConnection,
  IntegrationTestResponse,
} from "@/lib/types/obligation";

export default function IntegrationsPage() {
  const [connections, setConnections] = useState<IntegrationConnection[]>([]);
  const [llmStatus, setLlmStatus] = useState<{
    provider: string;
    model: string;
    is_ready: boolean;
    rate_limiter?: Record<string, unknown>;
    validation_status?: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<IntegrationTestResponse | null>(null);
  const [copiedSlackWebhook, setCopiedSlackWebhook] = useState(false);
  const [copiedGmailWebhook, setCopiedGmailWebhook] = useState(false);
  const [copiedCalWebhook, setCopiedCalWebhook] = useState(false);
  const [copiedJiraWebhook, setCopiedJiraWebhook] = useState(false);
  const [connectModalProvider, setConnectModalProvider] = useState<"slack" | "gmail" | "google_calendar" | "jira" | null>(null);
  const [connecting, setConnecting] = useState(false);

  // Jira-specific state
  const [jiraSiteUrl, setJiraSiteUrl] = useState("");
  const [jiraEmail, setJiraEmail] = useState("");
  const [jiraApiToken, setJiraApiToken] = useState("");
  const [jiraProjectsModalOpen, setJiraProjectsModalOpen] = useState(false);
  const [availableJiraProjects, setAvailableJiraProjects] = useState<Array<{ key: string; name: string }>>([]);
  const [selectedJiraProjectKeys, setSelectedJiraProjectKeys] = useState<string[]>([]);
  const [syncingJira, setSyncingJira] = useState(false);
  const [jiraSyncMessage, setJiraSyncMessage] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [res, llm] = await Promise.all([
        integrationsApi.list().catch(() => ({ connections: [], registered_providers: [] })),
        llmApi.getStatus().catch(() => null),
      ]);
      setConnections(res.connections || []);
      setLlmStatus(llm);
    } catch (err) {
      console.error("Failed to load integrations:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();

  }, [loadData]);

  const slackConnection = connections.find((c) => c.provider.toLowerCase() === "slack");
  const isSlackConnected = slackConnection?.status === "CONNECTED";

  const gmailConnection = connections.find((c) => c.provider.toLowerCase() === "gmail");
  const isGmailConnected = gmailConnection?.status === "CONNECTED";

  const calConnection = connections.find((c) => c.provider.toLowerCase() === "google_calendar" || c.provider.toLowerCase() === "calendar");
  const isCalConnected = calConnection?.status === "CONNECTED";

  const jiraConnection = connections.find((c) => c.provider.toLowerCase() === "jira");
  const isJiraConnected = jiraConnection?.status === "CONNECTED";

  const handleTestConnection = async (provider: string) => {
    try {
      setTestingProvider(provider);
      setTestResult(null);
      const res = await integrationsApi.test(provider);
      setTestResult(res);
      await loadData();
    } catch (err) {
      console.error(`Failed to test connection for ${provider}:`, err);
      setTestResult({
        provider,
        success: false,
        status: "ERROR",
        message: "Failed to test connection. Make sure backend is running.",
        tested_at: new Date().toISOString(),
      });
    } finally {
      setTestingProvider(null);
    }
  };

  const handleConnect = async (provider: "slack" | "gmail" | "google_calendar") => {
    try {
      setConnecting(true);
      const auth = await integrationsApi.connect(provider);
      if (auth.authorization_url) {
        window.location.href = auth.authorization_url;
      }
    } catch (err) {
      console.error(`Failed to initiate ${provider} OAuth:`, err);
    } finally {
      setConnecting(false);
    }
  };

  const handleConnectJira = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jiraSiteUrl || !jiraEmail || !jiraApiToken) return;
    try {
      setConnecting(true);
      await jiraApi.connectToken({
        site_url: jiraSiteUrl,
        email: jiraEmail,
        api_token: jiraApiToken,
      });
      setConnectModalProvider(null);
      setJiraSiteUrl("");
      setJiraEmail("");
      setJiraApiToken("");
      await loadData();
    } catch (err: unknown) {
      const error = err as Error;
      alert(`Failed to connect Jira: ${error.message}`);
    } finally {
      setConnecting(false);
    }
  };

  const handleOpenProjectSelector = async () => {
    try {
      setJiraProjectsModalOpen(true);
      const projects = await jiraApi.listProjects<{ key: string; name: string }>();
      setAvailableJiraProjects(projects || []);
      const currentSelected = (jiraConnection?.connection_metadata?.selected_projects as string[]) || [];
      setSelectedJiraProjectKeys(
        currentSelected.length ? currentSelected : (projects || []).slice(0, 2).map((p) => p.key)
      );
    } catch (err) {
      console.error("Failed to load Jira projects:", err);
    }
  };


  const handleSaveProjects = async () => {
    try {
      await jiraApi.selectProjects(selectedJiraProjectKeys);
      setJiraProjectsModalOpen(false);
      await loadData();
    } catch (err: unknown) {
      const error = err as Error;
      alert(`Failed to update projects: ${error.message}`);
    }
  };

  const handleTriggerSync = async () => {
    try {
      setSyncingJira(true);
      setJiraSyncMessage(null);
      const res = await jiraApi.triggerSync<{ synced_issues_count: number }>();
      setJiraSyncMessage(`Synced ${res.synced_issues_count || 0} Jira issue(s) successfully.`);
      await loadData();
    } catch (err: unknown) {
      const error = err as Error;
      setJiraSyncMessage(`Sync failed: ${error.message}`);
    } finally {
      setSyncingJira(false);
    }
  };

  const handleDisconnect = async (provider: string) => {
    if (!confirm(`Are you sure you want to disconnect ${provider.toUpperCase()}?`)) return;
    try {
      setLoading(true);
      await integrationsApi.disconnect(provider);
      await loadData();
    } catch (err) {
      console.error(`Failed to disconnect ${provider}:`, err);
    } finally {
      setLoading(false);
    }
  };

  const copySlackWebhookUrl = () => {
    const url = `${window.location.origin.replace(":3000", ":8000")}/api/webhooks/slack`;
    navigator.clipboard.writeText(url);
    setCopiedSlackWebhook(true);
    setTimeout(() => setCopiedSlackWebhook(false), 2500);
  };

  const copyGmailWebhookUrl = () => {
    const url = `${window.location.origin.replace(":3000", ":8000")}/api/webhooks/gmail`;
    navigator.clipboard.writeText(url);
    setCopiedGmailWebhook(true);
    setTimeout(() => setCopiedGmailWebhook(false), 2500);
  };

  const copyCalWebhookUrl = () => {
    const url = `${window.location.origin.replace(":3000", ":8000")}/api/webhooks/google-calendar`;
    navigator.clipboard.writeText(url);
    setCopiedCalWebhook(true);
    setTimeout(() => setCopiedCalWebhook(false), 2500);
  };

  const copyJiraWebhookUrl = () => {
    const url = `${window.location.origin.replace(":3000", ":8000")}/api/webhooks/jira`;
    navigator.clipboard.writeText(url);
    setCopiedJiraWebhook(true);
    setTimeout(() => setCopiedJiraWebhook(false), 2500);
  };


  return (
    <div className="min-h-screen bg-stone-50 text-stone-900 p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-stone-200/80 pb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2.5 rounded-xl bg-gradient-to-tr from-purple-600 via-blue-700 to-emerald-600 shadow-lg shadow-indigo-900/30">
                <Radio className="w-6 h-6 text-stone-950" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-stone-950 flex items-center gap-2">
                  Integrations &amp; Connection Management
                  <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800/60">
                    Phase 10 Temporal Intelligence
                  </span>
                </h1>
                <p className="text-sm text-stone-600">
                  Connect communication and temporal scheduling workspaces (Slack, Gmail, &amp; Google Calendar) for automated event observation with human-authorized action boundaries.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={loadData}
              disabled={loading}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 border border-stone-300 transition disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Refresh Status
            </button>
          </div>
        </div>

        {/* Security & Boundary Notice Banner */}
        <div className="p-4 rounded-2xl bg-gradient-to-r from-stone-100 via-indigo-950/40 to-stone-100 border border-indigo-800/40 shadow-xl flex items-start gap-4">
          <div className="p-2.5 rounded-xl bg-indigo-900/60 text-blue-600 shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div className="space-y-1 text-xs">
            <div className="font-semibold text-stone-950 text-sm flex items-center gap-2">
              Human-Controlled Action Boundary &amp; Multi-Provider Security
            </div>
            <p className="text-stone-700 leading-relaxed">
              Slack, Gmail, and Google Calendar integrations are strictly <strong>READ / INGEST</strong> oriented. Inbound communication and scheduling events are normalized into provider-agnostic events for temporal correlation and risk analysis. <strong>Obligation Agent never sends outbound messages, emails, or modifies calendar events without explicit human authorization</strong>.
            </p>
          </div>
        </div>

        {/* Test Result Toast */}
        {testResult && (
          <div
            className={`p-4 rounded-xl border flex items-center justify-between text-xs transition-all ${
              testResult.success
                ? "bg-emerald-950/60 border-emerald-800/80 text-emerald-300"
                : "bg-rose-950/60 border-rose-800/80 text-rose-300"
            }`}
          >
            <div className="flex items-center gap-3">
              {testResult.success ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
              )}
              <div>
                <span className="font-bold uppercase tracking-wider">{testResult.provider}:</span>{" "}
                {testResult.message}
              </div>
            </div>
            <span className="text-[11px] opacity-70">
              Tested at {new Date(testResult.tested_at).toLocaleTimeString()}
            </span>
          </div>
        )}

        {/* Section 1: External Communication & Scheduling Providers */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-stone-950 flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-purple-400" />
              External Communication &amp; Scheduling Providers
            </h2>
            <span className="text-xs text-stone-600">Live production &amp; dev integrations</span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Slack Workspace Card */}
            <div className="rounded-2xl border border-stone-200 bg-stone-100/80 p-6 shadow-xl space-y-6 flex flex-col justify-between relative overflow-hidden">
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-purple-700 via-blue-700 to-purple-500 flex items-center justify-center shadow-lg shadow-purple-950 border border-purple-400/20 shrink-0">
                      <svg className="w-5 h-5 text-stone-950" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-stone-950">Slack Workspace</h3>
                      <p className="text-xs text-stone-600">Channel &amp; thread events</p>
                    </div>
                  </div>

                  <div>
                    {isSlackConnected ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-800/80">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                        CONNECTED
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-stone-200 text-stone-600 border border-stone-300">
                        NOT CONNECTED
                      </span>
                    )}
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="text-[11px] font-medium text-stone-600 uppercase tracking-wider">
                    Capabilities
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {["Events API", "Channel Messages", "Attachments"].map((cap) => (
                      <span
                        key={cap}
                        className="px-2 py-0.5 text-[11px] rounded bg-stone-200/80 text-stone-700 border border-stone-300/60"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>

                {isSlackConnected && slackConnection && (
                  <div className="p-3 rounded-xl bg-stone-50/60 border border-stone-200/80 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between text-stone-700 font-medium">
                      <span>Account:</span>
                      <strong className="text-purple-300">
                        {slackConnection.external_account_name || "Workspace"}
                      </strong>
                    </div>
                    <div className="flex items-center justify-between text-stone-600 text-[11px]">
                      <span>Security:</span>
                      <span className="text-emerald-400 flex items-center gap-1">
                        <Lock className="w-3 h-3" /> Credentials Encrypted
                      </span>
                    </div>
                  </div>
                )}

                <div className="p-2.5 rounded-xl bg-stone-50/80 border border-stone-200 space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-stone-600">
                    <span>Slack Webhook:</span>
                    <button
                      onClick={copySlackWebhookUrl}
                      className="text-purple-400 hover:text-purple-300 flex items-center gap-1 text-[11px]"
                    >
                      {copiedSlackWebhook ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      Copy
                    </button>
                  </div>
                  <code className="block text-[11px] font-mono text-stone-700 bg-stone-100 p-1.5 rounded border border-stone-200 truncate">
                    http://localhost:8000/api/webhooks/slack
                  </code>
                </div>
              </div>

              <div className="pt-3 border-t border-stone-200/80 flex items-center justify-between gap-2">
                <button
                  onClick={() => handleTestConnection("slack")}
                  disabled={testingProvider === "slack"}
                  className="px-3 py-1 text-xs font-semibold rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 border border-stone-300 transition flex items-center gap-1"
                >
                  <RefreshCw className={`w-3 h-3 ${testingProvider === "slack" ? "animate-spin" : ""}`} />
                  Test
                </button>

                {isSlackConnected ? (
                  <button
                    onClick={() => handleDisconnect("slack")}
                    className="px-3 py-1 text-xs font-semibold rounded-lg bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/60 transition"
                  >
                    Disconnect
                  </button>
                ) : (
                  <button
                    onClick={() => setConnectModalProvider("slack")}
                    className="px-3.5 py-1.5 text-xs font-bold rounded-lg bg-gradient-to-r from-purple-600 to-blue-700 text-stone-950 shadow-md transition"
                  >
                    Connect Slack
                  </button>
                )}
              </div>
            </div>

            {/* Gmail Google Workspace Card */}
            <div className="rounded-2xl border border-stone-200 bg-stone-100/80 p-6 shadow-xl space-y-6 flex flex-col justify-between relative overflow-hidden">
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-red-600 via-rose-600 to-amber-600 flex items-center justify-center shadow-lg shadow-red-950 border border-red-400/20 shrink-0">
                      <Mail className="w-5 h-5 text-stone-950" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-stone-950">Gmail / Workspace</h3>
                      <p className="text-xs text-stone-600">Email &amp; thread events</p>
                    </div>
                  </div>

                  <div>
                    {isGmailConnected ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-800/80">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                        CONNECTED
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-stone-200 text-stone-600 border border-stone-300">
                        NOT CONNECTED
                      </span>
                    )}
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="text-[11px] font-medium text-stone-600 uppercase tracking-wider">
                    Capabilities
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {["Email Ingestion", "Threads", "Attachments", "OAuth Read-Only"].map((cap) => (
                      <span
                        key={cap}
                        className="px-2 py-0.5 text-[11px] rounded bg-stone-200/80 text-stone-700 border border-stone-300/60"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>

                {isGmailConnected && gmailConnection && (
                  <div className="p-3 rounded-xl bg-stone-50/60 border border-stone-200/80 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between text-stone-700 font-medium">
                      <span>Account:</span>
                      <strong className="text-red-300">
                        {gmailConnection.external_account_name || "Google Workspace"}
                      </strong>
                    </div>
                    <div className="flex items-center justify-between text-stone-600 text-[11px]">
                      <span>Security:</span>
                      <span className="text-emerald-400 flex items-center gap-1">
                        <Lock className="w-3 h-3" /> Minimum Read-Only
                      </span>
                    </div>
                  </div>
                )}

                <div className="p-2.5 rounded-xl bg-stone-50/80 border border-stone-200 space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-stone-600">
                    <span>Gmail Pub/Sub Webhook:</span>
                    <button
                      onClick={copyGmailWebhookUrl}
                      className="text-red-400 hover:text-red-300 flex items-center gap-1 text-[11px]"
                    >
                      {copiedGmailWebhook ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      Copy
                    </button>
                  </div>
                  <code className="block text-[11px] font-mono text-stone-700 bg-stone-100 p-1.5 rounded border border-stone-200 truncate">
                    http://localhost:8000/api/webhooks/gmail
                  </code>
                </div>
              </div>

              <div className="pt-3 border-t border-stone-200/80 flex items-center justify-between gap-2">
                <button
                  onClick={() => handleTestConnection("gmail")}
                  disabled={testingProvider === "gmail"}
                  className="px-3 py-1 text-xs font-semibold rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 border border-stone-300 transition flex items-center gap-1"
                >
                  <RefreshCw className={`w-3 h-3 ${testingProvider === "gmail" ? "animate-spin" : ""}`} />
                  Test
                </button>

                {isGmailConnected ? (
                  <button
                    onClick={() => handleDisconnect("gmail")}
                    className="px-3 py-1 text-xs font-semibold rounded-lg bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/60 transition"
                  >
                    Disconnect
                  </button>
                ) : (
                  <button
                    onClick={() => setConnectModalProvider("gmail")}
                    className="px-3.5 py-1.5 text-xs font-bold rounded-lg bg-gradient-to-r from-red-600 to-rose-600 text-stone-950 shadow-md transition"
                  >
                    Connect Gmail
                  </button>
                )}
              </div>
            </div>

            {/* Google Calendar Card (Phase 10) */}
            <div className="rounded-2xl border border-stone-200 bg-stone-100/80 p-6 shadow-xl space-y-6 flex flex-col justify-between relative overflow-hidden">
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-emerald-600 via-teal-600 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-950 border border-emerald-400/20 shrink-0">
                      <Calendar className="w-5 h-5 text-stone-950" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-stone-950">Google Calendar</h3>
                      <p className="text-xs text-stone-600">Temporal &amp; meeting context</p>
                    </div>
                  </div>

                  <div>
                    {isCalConnected ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-800/80">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                        CONNECTED
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-stone-200 text-stone-600 border border-stone-300">
                        NOT CONNECTED
                      </span>
                    )}
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="text-[11px] font-medium text-stone-600 uppercase tracking-wider">
                    Capabilities
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {["Calendar Ingestion", "Meetings & Attendees", "Reschedules", "OAuth Read-Only"].map((cap) => (
                      <span
                        key={cap}
                        className="px-2 py-0.5 text-[11px] rounded bg-stone-200/80 text-stone-700 border border-stone-300/60"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>

                {isCalConnected && calConnection && (
                  <div className="p-3 rounded-xl bg-stone-50/60 border border-stone-200/80 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between text-stone-700 font-medium">
                      <span>Account:</span>
                      <strong className="text-emerald-300">
                        {calConnection.external_account_name || "Google Calendar Account"}
                      </strong>
                    </div>
                    <div className="flex items-center justify-between text-stone-600 text-[11px]">
                      <span>Security:</span>
                      <span className="text-emerald-400 flex items-center gap-1">
                        <Lock className="w-3 h-3" /> Read-Only (No Event Edits)
                      </span>
                    </div>
                  </div>
                )}

                <div className="p-2.5 rounded-xl bg-stone-50/80 border border-stone-200 space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-stone-600">
                    <span>Calendar Webhook:</span>
                    <button
                      onClick={copyCalWebhookUrl}
                      className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1 text-[11px]"
                    >
                      {copiedCalWebhook ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      Copy
                    </button>
                  </div>
                  <code className="block text-[11px] font-mono text-stone-700 bg-stone-100 p-1.5 rounded border border-stone-200 truncate">
                    http://localhost:8000/api/webhooks/google-calendar
                  </code>
                </div>
              </div>

              <div className="pt-3 border-t border-stone-200/80 flex items-center justify-between gap-2">
                <button
                  onClick={() => handleTestConnection("google_calendar")}
                  disabled={testingProvider === "google_calendar"}
                  className="px-3 py-1 text-xs font-semibold rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 border border-stone-300 transition flex items-center gap-1"
                >
                  <RefreshCw className={`w-3 h-3 ${testingProvider === "google_calendar" ? "animate-spin" : ""}`} />
                  Test
                </button>

                {isCalConnected ? (
                  <button
                    onClick={() => handleDisconnect("google_calendar")}
                    className="px-3 py-1 text-xs font-semibold rounded-lg bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/60 transition"
                  >
                    Disconnect
                  </button>
                ) : (
                  <button
                    onClick={() => setConnectModalProvider("google_calendar")}
                    className="px-3.5 py-1.5 text-xs font-bold rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 text-stone-950 shadow-md transition"
                  >
                    Connect Calendar
                  </button>
                )}
              </div>
            </div>

            {/* Jira Cloud Card (First-Class External Work Provider) */}
            <div className="rounded-2xl border border-stone-200 bg-stone-100/80 p-6 shadow-xl space-y-6 flex flex-col justify-between relative overflow-hidden">
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-blue-600 via-blue-700 to-cyan-600 flex items-center justify-center shadow-lg shadow-blue-950 border border-blue-500/20 shrink-0">
                      <Layers className="w-5 h-5 text-stone-950" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-stone-950">Jira Cloud</h3>
                      <p className="text-xs text-stone-600">Issues, transitions &amp; work signals</p>
                    </div>
                  </div>

                  <div>
                    {isJiraConnected ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-800/80">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                        CONNECTED
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-stone-200 text-stone-600 border border-stone-300">
                        NOT CONNECTED
                      </span>
                    )}
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="text-[11px] font-medium text-stone-600 uppercase tracking-wider">
                    Capabilities
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {["Issues & Transitions", "Project Sync", "Comments", "Status Signals"].map((cap) => (
                      <span
                        key={cap}
                        className="px-2 py-0.5 text-[11px] rounded bg-stone-200/80 text-stone-700 border border-stone-300/60"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>

                {isJiraConnected && jiraConnection && (
                  <div className="p-3 rounded-xl bg-stone-50/60 border border-stone-200/80 space-y-2 text-xs">
                    <div className="flex items-center justify-between text-stone-700 font-medium">
                      <span>Site:</span>
                      <strong className="text-blue-600 truncate max-w-[180px]">
                        {jiraConnection.connection_metadata?.site_url
                          ? String(jiraConnection.connection_metadata.site_url)
                          : "Atlassian Cloud"}
                      </strong>
                    </div>

                    <div className="flex items-center justify-between text-stone-600 text-[11px]">
                      <span>Selected Projects:</span>
                      <span className="text-stone-800 font-semibold">
                        {Array.isArray(jiraConnection.connection_metadata?.selected_projects)
                          ? (jiraConnection.connection_metadata.selected_projects as string[]).join(", ")
                          : "All Accessible"}
                      </span>
                    </div>

                    {Boolean(jiraConnection.connection_metadata?.last_synced_at) && (
                      <div className="flex items-center justify-between text-stone-600 text-[10px]">
                        <span>Last Synced:</span>
                        <span>{new Date(String(jiraConnection.connection_metadata?.last_synced_at)).toLocaleTimeString()}</span>
                      </div>
                    )}



                    <div className="pt-1 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={handleOpenProjectSelector}
                        className="flex-1 px-2.5 py-1 text-[11px] font-medium rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 border border-stone-300 transition"
                      >
                        Select Projects
                      </button>
                      <button
                        type="button"
                        onClick={handleTriggerSync}
                        disabled={syncingJira}
                        className="flex-1 px-2.5 py-1 text-[11px] font-medium rounded-lg bg-blue-950/80 hover:bg-blue-900 text-blue-600 border border-blue-800/80 transition flex items-center justify-center gap-1 disabled:opacity-50"
                      >
                        <RefreshCw className={`w-3 h-3 ${syncingJira ? "animate-spin" : ""}`} />
                        {syncingJira ? "Syncing..." : "Sync Now"}
                      </button>
                    </div>

                    {jiraSyncMessage && (
                      <p className="text-[11px] text-emerald-400 font-medium">{jiraSyncMessage}</p>
                    )}
                  </div>
                )}

                <div className="p-2.5 rounded-xl bg-stone-50/80 border border-stone-200 space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-stone-600">
                    <span>Jira Webhook:</span>
                    <button
                      onClick={copyJiraWebhookUrl}
                      className="text-blue-500 hover:text-blue-600 flex items-center gap-1 text-[11px]"
                    >
                      {copiedJiraWebhook ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      Copy
                    </button>
                  </div>
                  <code className="block text-[11px] font-mono text-stone-700 bg-stone-100 p-1.5 rounded border border-stone-200 truncate">
                    http://localhost:8000/api/webhooks/jira
                  </code>
                </div>
              </div>

              <div className="pt-3 border-t border-stone-200/80 flex items-center justify-between gap-2">
                <button
                  onClick={() => handleTestConnection("jira")}
                  disabled={testingProvider === "jira"}
                  className="px-3 py-1 text-xs font-semibold rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 border border-stone-300 transition flex items-center gap-1"
                >
                  <RefreshCw className={`w-3 h-3 ${testingProvider === "jira" ? "animate-spin" : ""}`} />
                  Test
                </button>

                {isJiraConnected ? (
                  <button
                    onClick={() => handleDisconnect("jira")}
                    className="px-3 py-1 text-xs font-semibold rounded-lg bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/60 transition"
                  >
                    Disconnect
                  </button>
                ) : (
                  <button
                    onClick={() => setConnectModalProvider("jira")}
                    className="px-3.5 py-1.5 text-xs font-bold rounded-lg bg-gradient-to-r from-blue-600 to-blue-700 text-stone-950 shadow-md transition"
                  >
                    Connect Jira
                  </button>
                )}
              </div>
            </div>

            {/* Gemini / LLM Intelligence Provider Card */}
            <div className="rounded-2xl border border-stone-200 bg-stone-100/60 p-6 shadow-xl space-y-6 flex flex-col justify-between">
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-purple-600 via-blue-700 to-cyan-500 border border-purple-400/40 flex items-center justify-center text-stone-950 shadow-md shadow-purple-950/40">
                      <Cpu className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-stone-950 text-base">Google Gemini &amp; LLM Core</h3>
                        <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-purple-950 text-purple-300 border border-purple-800/60">
                          Phase 20 Intelligence
                        </span>
                      </div>
                      <p className="text-xs text-stone-600">
                        Hybrid extraction, semantic event understanding, and grounded multi-step reasoning.
                      </p>
                    </div>
                  </div>

                  <span
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${
                      llmStatus?.is_ready
                        ? "bg-emerald-950 text-emerald-400 border-emerald-800"
                        : "bg-amber-950 text-amber-400 border-amber-800"
                    }`}
                  >
                    <span
                      className={`h-2 w-2 rounded-full ${
                        llmStatus?.is_ready ? "bg-emerald-400" : "bg-amber-400"
                      }`}
                    ></span>
                    {llmStatus?.is_ready ? "CONNECTED & READY" : "CONFIG REQUIRED"}
                  </span>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-stone-50 border border-stone-200/80">
                    <span className="text-stone-600">Active Provider / Model:</span>
                    <span className="font-semibold text-purple-300">
                      {llmStatus?.provider?.toUpperCase() || "GEMINI"} ({llmStatus?.model || "gemini-1.5-flash"})
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-stone-50 border border-stone-200/80">
                    <span className="text-stone-600">Grounding &amp; Defense:</span>
                    <span className="font-semibold text-emerald-400 flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" /> PII Scrubbed &amp; Injection Defanged
                    </span>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider">
                    Supported Capabilities
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {["Natural Language Extraction", "Semantic Event Proposal", "Grounded Explanations", "Human Review Triage"].map((c) => (
                      <span
                        key={c}
                        className="px-2 py-0.5 text-[11px] font-medium rounded bg-stone-200/80 text-stone-700 border border-stone-300/80"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-stone-200/80 flex items-center justify-between">
                <Link
                  href="/intelligence"
                  className="text-xs font-semibold text-blue-500 hover:text-blue-600 flex items-center gap-1"
                >
                  <span>Open Intelligence Hub</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
                <button
                  onClick={loadData}
                  className="px-3 py-1 text-xs font-semibold rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 border border-stone-300 transition flex items-center gap-1"
                >
                  <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
                  Check Status
                </button>
              </div>
            </div>
          </div>
        </div>


        {/* Section 2: Development & Simulation */}
        <div className="space-y-4 pt-4 border-t border-stone-200/80">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-stone-950 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-400" />
              Development &amp; Simulation Providers
            </h2>
            <span className="text-xs text-stone-600">Local testing and continuous benchmarks</span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Mock Provider Card */}
            <div className="rounded-2xl border border-stone-200 bg-stone-100/60 p-6 shadow-xl space-y-4 flex flex-col justify-between">
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-amber-950 border border-amber-800/60 flex items-center justify-center text-amber-400">
                      <Sparkles className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-bold text-stone-950">MockProvider</h4>
                        <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-amber-950 text-amber-300 border border-amber-800/60">
                          v1.0.0
                        </span>
                      </div>
                      <p className="text-xs text-stone-600">
                        Deterministic canonical scenarios for continuous testing without external credentials.
                      </p>
                    </div>
                  </div>

                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-800/80">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                    READY
                  </span>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  {["Deterministic Scenarios", "Synthetic Payloads", "Continuous Simulation"].map((c) => (
                    <span
                      key={c}
                      className="px-2 py-0.5 text-[11px] rounded bg-stone-200 text-stone-700 border border-stone-300"
                    >
                      {c}
                    </span>
                  ))}
                </div>
              </div>

              <div className="pt-3 border-t border-stone-200 flex items-center justify-between">
                <button
                  onClick={() => handleTestConnection("mock")}
                  disabled={testingProvider === "mock"}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-700 border border-stone-300 transition"
                >
                  Test Mock Provider
                </button>
                <Link
                  href="/events"
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-amber-950/70 hover:bg-amber-900 text-amber-300 border border-amber-800/70 transition flex items-center gap-1"
                >
                  Open Simulator Toolbar <ExternalLink className="w-3 h-3" />
                </Link>
              </div>
            </div>

            {/* Architecture Card */}
            <div className="rounded-2xl border border-stone-200 bg-stone-100/60 p-6 shadow-xl space-y-4 flex flex-col justify-between">
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-cyan-950 border border-cyan-800/60 text-cyan-400">
                    <Sliders className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="font-bold text-stone-950">Unified Multi-Provider Core</h4>
                    <p className="text-xs text-stone-600">
                      Slack, Gmail, &amp; Google Calendar normalize into identical <code className="text-cyan-400">ExternalEvent</code> objects.
                    </p>
                  </div>
                </div>

                <p className="text-xs text-stone-600 leading-relaxed">
                  All communication and calendar events feed into the unified <strong>EventIngestionService</strong>, executing deterministic deduplication, temporal correlation, meeting-driven risk calculation, and graph cascade unblocking.
                </p>
              </div>

              <div className="pt-3 border-t border-stone-200 flex items-center justify-between text-xs text-stone-600">
                <span>Total Providers: <strong className="text-stone-950">4 (Slack, Gmail, Calendar, Mock)</strong></span>
                <Link
                  href="/events"
                  className="text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1"
                >
                  View Activity Center <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Jira Connect Modal */}
      {connectModalProvider === "jira" && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-stone-100 border border-stone-200 rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-6">
            <div className="flex items-center justify-between border-b border-stone-200 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-900/60 border border-blue-700/60 text-blue-600 flex items-center justify-center">
                  <Layers className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-stone-950">Connect Jira Cloud</h3>
                  <p className="text-xs text-stone-600">Atlassian API Token Authentication</p>
                </div>
              </div>
              <button
                onClick={() => setConnectModalProvider(null)}
                className="text-stone-600 hover:text-stone-950 text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleConnectJira} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-stone-700">
                  Jira Site URL <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="https://your-company.atlassian.net"
                  value={jiraSiteUrl}
                  onChange={(e) => setJiraSiteUrl(e.target.value)}
                  className="w-full px-3.5 py-2 text-xs rounded-xl bg-stone-50 border border-stone-200 text-stone-950 placeholder:text-stone-500 focus:outline-none focus:border-blue-500 transition"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-stone-700">
                  Account Email Address <span className="text-rose-400">*</span>
                </label>
                <input
                  type="email"
                  required
                  placeholder="alex@company.com"
                  value={jiraEmail}
                  onChange={(e) => setJiraEmail(e.target.value)}
                  className="w-full px-3.5 py-2 text-xs rounded-xl bg-stone-50 border border-stone-200 text-stone-950 placeholder:text-stone-500 focus:outline-none focus:border-blue-500 transition"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-stone-700">
                    Atlassian API Token <span className="text-rose-400">*</span>
                  </label>
                  <a
                    href="https://id.atlassian.com/manage-profile/security/api-tokens"
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] text-blue-500 hover:text-blue-600 flex items-center gap-1"
                  >
                    Generate Token <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
                <input
                  type="password"
                  required
                  placeholder="Paste your Atlassian API token..."
                  value={jiraApiToken}
                  onChange={(e) => setJiraApiToken(e.target.value)}
                  className="w-full px-3.5 py-2 text-xs rounded-xl bg-stone-50 border border-stone-200 text-stone-950 placeholder:text-stone-500 focus:outline-none focus:border-blue-500 transition"
                />
              </div>

              <div className="p-3 rounded-xl bg-stone-50/80 border border-stone-200 text-[11px] text-stone-600 space-y-1">
                <div>• Token is encrypted with <strong className="text-emerald-400">AES-128-CBC / Fernet</strong> at rest.</div>
                <div>• Jira work signals are ingested as <strong className="text-stone-800">untrusted observations</strong>.</div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setConnectModalProvider(null)}
                  className="px-4 py-2 text-xs font-medium rounded-lg bg-stone-200 text-stone-700 hover:bg-stone-300 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={connecting}
                  className="px-5 py-2.5 text-xs font-bold rounded-xl text-stone-950 bg-gradient-to-r from-blue-600 to-blue-700 shadow-lg shadow-blue-950 transition flex items-center gap-2 disabled:opacity-50"
                >
                  {connecting ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Verifying Connection...
                    </>
                  ) : (
                    <>
                      <Zap className="w-3.5 h-3.5" /> Save &amp; Connect Jira
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Jira Projects Selector Modal */}
      {jiraProjectsModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-stone-100 border border-stone-200 rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-6">
            <div className="flex items-center justify-between border-b border-stone-200 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-900/60 border border-blue-700/60 text-blue-600 flex items-center justify-center">
                  <Sliders className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-stone-950">Select Jira Projects</h3>
                  <p className="text-xs text-stone-600">Choose which projects to synchronize</p>
                </div>
              </div>
              <button
                onClick={() => setJiraProjectsModalOpen(false)}
                className="text-stone-600 hover:text-stone-950 text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <div className="space-y-3 max-h-60 overflow-y-auto pr-1">
              {availableJiraProjects.length === 0 ? (
                <p className="text-xs text-stone-600 py-4 text-center">Loading accessible Jira projects...</p>
              ) : (
                availableJiraProjects.map((p) => {
                  const isChecked = selectedJiraProjectKeys.includes(p.key);
                  return (
                    <label
                      key={p.key}
                      className={`flex items-center justify-between p-3 rounded-xl border transition cursor-pointer ${
                        isChecked
                          ? "bg-blue-950/40 border-blue-700/60 text-stone-950"
                          : "bg-stone-50 border-stone-200 text-stone-700 hover:border-stone-300"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedJiraProjectKeys([...selectedJiraProjectKeys, p.key]);
                            } else {
                              setSelectedJiraProjectKeys(selectedJiraProjectKeys.filter((k) => k !== p.key));
                            }
                          }}
                          className="rounded text-blue-600 focus:ring-blue-500"
                        />
                        <div>
                          <div className="text-xs font-bold">{p.name}</div>
                          <div className="text-[10px] text-stone-600">Key: {p.key}</div>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-stone-100 border border-stone-200 text-blue-600">
                        {p.key}
                      </span>
                    </label>
                  );
                })
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 border-t border-stone-200">
              <button
                type="button"
                onClick={() => setJiraProjectsModalOpen(false)}
                className="px-4 py-2 text-xs font-medium rounded-lg bg-stone-200 text-stone-700 hover:bg-stone-300 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveProjects}
                className="px-5 py-2 text-xs font-bold rounded-xl text-stone-950 bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-950 transition"
              >
                Save Selection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* OAuth Connect Modal */}
      {connectModalProvider && connectModalProvider !== "jira" && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-stone-100 border border-stone-200 rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-6">
            <div className="flex items-center justify-between border-b border-stone-200 pb-4">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                  connectModalProvider === "slack"
                    ? "bg-purple-900/60 border border-purple-700/60 text-purple-300"
                    : connectModalProvider === "gmail"
                    ? "bg-red-900/60 border border-red-700/60 text-red-300"
                    : "bg-emerald-900/60 border border-emerald-700/60 text-emerald-300"
                }`}>
                  {connectModalProvider === "slack" ? (
                    <Radio className="w-5 h-5" />
                  ) : connectModalProvider === "gmail" ? (
                    <Mail className="w-5 h-5" />
                  ) : (
                    <Calendar className="w-5 h-5" />
                  )}
                </div>
                <div>
                  <h3 className="text-base font-bold text-stone-950">
                    Connect {
                      connectModalProvider === "slack"
                        ? "Slack Workspace"
                        : connectModalProvider === "gmail"
                        ? "Gmail Workspace"
                        : "Google Calendar"
                    }
                  </h3>
                  <p className="text-xs text-stone-600">Secure OAuth 2.0 Read-Only Connection</p>
                </div>
              </div>
              <button
                onClick={() => setConnectModalProvider(null)}
                className="text-stone-600 hover:text-stone-950 text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <div className="p-4 rounded-2xl bg-stone-50 border border-stone-200 space-y-3 text-xs leading-relaxed text-stone-700">
              <div className="font-semibold text-stone-950 text-sm flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Human-Supervised Observation Principle
              </div>
              <p>
                &ldquo;Connect {connectModalProvider === "slack" ? "Slack" : connectModalProvider === "gmail" ? "Gmail" : "Google Calendar"} so Obligation Agent can observe relevant communication and temporal events. Obligation Agent does not automatically send messages or modify calendar events without human approval.&rdquo;
              </p>
              <div className="p-3 rounded-xl bg-stone-100/80 border border-stone-200 space-y-1 text-[11px] text-stone-600">
                <div>
                  • Scopes Requested:{" "}
                  <code className={
                    connectModalProvider === "slack"
                      ? "text-purple-300"
                      : connectModalProvider === "gmail"
                      ? "text-red-300"
                      : "text-emerald-300"
                  }>
                    {connectModalProvider === "slack"
                      ? "channels:history, users:read, team:read"
                      : connectModalProvider === "gmail"
                      ? "https://www.googleapis.com/auth/gmail.readonly"
                      : "https://www.googleapis.com/auth/calendar.readonly"}
                  </code>
                </div>
                <div>• Token Storage: <strong className="text-emerald-400">Encrypted &amp; Isolated</strong></div>
                <div>• Outbound Action: <strong className="text-amber-400">Always Gated by Human Review</strong></div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setConnectModalProvider(null)}
                className="px-4 py-2 text-xs font-medium rounded-lg bg-stone-200 text-stone-700 hover:bg-stone-300 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleConnect(connectModalProvider as "slack" | "gmail" | "google_calendar")}
                disabled={connecting}
                className={`px-5 py-2.5 text-xs font-bold rounded-xl text-stone-950 shadow-lg transition flex items-center gap-2 disabled:opacity-50 ${
                  connectModalProvider === "slack"
                    ? "bg-gradient-to-r from-purple-600 to-blue-700 shadow-purple-950"
                    : connectModalProvider === "gmail"
                    ? "bg-gradient-to-r from-red-600 to-rose-600 shadow-red-950"
                    : "bg-gradient-to-r from-emerald-600 to-teal-600 shadow-emerald-950"
                }`}
              >
                {connecting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Redirecting to OAuth...
                  </>
                ) : (
                  <>
                    <Zap className="w-3.5 h-3.5" /> Authorize with {
                      connectModalProvider === "slack"
                        ? "Slack"
                        : connectModalProvider === "gmail"
                        ? "Gmail"
                        : "Google Calendar"
                    }
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

