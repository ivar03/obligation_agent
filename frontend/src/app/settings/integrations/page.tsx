"use client";

import React, { useState, useEffect } from "react";
import { CheckCircle2, ShieldCheck, Key, RefreshCw } from "lucide-react";

interface IntegrationItem {
  provider: string;
  is_active: boolean;
}

export default function IntegrationsSettingsPage() {
  const [slackConnected, setSlackConnected] = useState(false);

  useEffect(() => {
    fetch("/api/integrations")
      .then((res) => res.json())
      .then((data: IntegrationItem[]) => {
        const hasSlack = Array.isArray(data) && data.some((i) => i.provider === "slack" && i.is_active);
        setSlackConnected(hasSlack);
      })
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      {/* Slack Integration Card */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#4A154B]/30 border border-[#4A154B]/50 flex items-center justify-center text-amber-300 font-bold">
              #
            </div>
            <div>
              <h2 className="text-sm font-bold text-zinc-100">Slack App & Channel Webhook</h2>
              <p className="text-xs text-zinc-400 mt-0.5">Ingest real communication signals and draft non-autonomous interventions.</p>
            </div>
          </div>
          <span
            className={`px-2.5 py-1 rounded-full text-xs font-semibold border flex items-center gap-1.5 ${
              slackConnected
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                : "bg-zinc-800 text-zinc-400 border-zinc-700"
            }`}
          >
            {slackConnected ? <CheckCircle2 className="w-3.5 h-3.5" /> : null}
            <span>{slackConnected ? "Connected" : "Not Connected"}</span>
          </span>
        </div>

        <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800/80 space-y-3 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-zinc-400 font-medium">Inbound Webhook Endpoint:</span>
            <code className="bg-zinc-900 px-2 py-0.5 rounded text-zinc-300 font-mono text-[11px]">
              /api/webhooks/slack/events
            </code>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-400 font-medium">Signature Verification:</span>
            <span className="text-emerald-400 font-semibold flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" /> HMAC-SHA256 (300s Tolerance)
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-400 font-medium">Credentials at Rest:</span>
            <span className="text-purple-400 font-semibold flex items-center gap-1">
              <Key className="w-3.5 h-3.5" /> Fernet AES-256 Symmetric
            </span>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <a
            href="/integrations"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Manage Integrations</span>
          </a>
        </div>
      </div>
    </div>
  );
}
