"use client";

import React, { useState, useEffect } from "react";

import { CheckCircle2, ShieldCheck, Key, RefreshCw } from "lucide-react";
import { integrationsApi } from "@/lib/api/obligations";

export default function IntegrationsSettingsPage() {
  const [slackConnected, setSlackConnected] = useState(false);

  useEffect(() => {
    integrationsApi
      .list()
      .then((res) => {
        const hasSlack = (res.connections || []).some(
          (i) => i.provider.toLowerCase() === "slack" && i.status === "CONNECTED"
        );
        setSlackConnected(hasSlack);
      })
      .catch(() => {});
  }, []);


  return (
    <div className="space-y-6">
      {/* Slack Integration Card */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white border border-stone-200 shadow-xs flex items-center justify-center text-[#4A154B] font-bold">
              #
            </div>
            <div>
              <h2 className="text-sm font-bold text-stone-900">Slack App & Channel Webhook</h2>
              <p className="text-xs text-stone-600 mt-0.5">Ingest real communication signals and draft non-autonomous interventions.</p>
            </div>
          </div>
          <span
            className={`px-2.5 py-1 rounded-full text-xs font-semibold border flex items-center gap-1.5 ${
              slackConnected
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-stone-100 text-stone-600 border-stone-200"
            }`}
          >
            {slackConnected ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> : null}
            <span>{slackConnected ? "Connected" : "Not Connected"}</span>
          </span>
        </div>

        <div className="p-4 rounded-xl bg-stone-50/60 border border-stone-200/80 space-y-3 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-stone-600 font-medium">Inbound Webhook Endpoint:</span>
            <code className="bg-stone-100 px-2 py-0.5 rounded text-stone-700 font-mono text-[11px] border border-stone-200">
              /api/webhooks/slack/events
            </code>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-stone-600 font-medium">Signature Verification:</span>
            <span className="text-emerald-700 font-semibold flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> HMAC-SHA256 (300s Tolerance)
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-stone-600 font-medium">Credentials at Rest:</span>
            <span className="text-orange-700 font-semibold flex items-center gap-1">
              <Key className="w-3.5 h-3.5 text-orange-600" /> Fernet AES-256 Symmetric
            </span>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <a
            href="/integrations"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-xl text-xs font-semibold shadow transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Manage Integrations</span>
          </a>
        </div>
      </div>
    </div>
  );
}
