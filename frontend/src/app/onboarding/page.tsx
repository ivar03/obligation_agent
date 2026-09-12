"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Sparkles,
  Building2,
  Users,
  Radio,
  Bell,
  FileSpreadsheet,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { CsvImportModal } from "@/components/obligations/CsvImportModal";

const STEPS = [
  { id: "WELCOME", title: "Welcome", icon: Sparkles },
  { id: "CREATE_WORKSPACE", title: "Workspace", icon: Building2 },
  { id: "INVITE_TEAM", title: "Invite Team", icon: Users },
  { id: "CONNECT_SLACK", title: "Connect Slack", icon: Radio },
  { id: "MONITORING_PREFS", title: "Alert Preferences", icon: Bell },
  { id: "IMPORT_OBLIGATIONS", title: "Import Data", icon: FileSpreadsheet },
  { id: "COMPLETED", title: "Ready", icon: CheckCircle2 },
];

export default function OnboardingPage() {
  const { activeWorkspace } = useAuth();
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);

  // Form states
  const [workspaceName, setWorkspaceName] = useState("Acme Engineering");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("MEMBER");
  const [invitationsSent, setInvitationsSent] = useState<string[]>([]);
  const [timezone, setTimezone] = useState("UTC");
  const [alertsEnabled, setAlertsEnabled] = useState({
    critical_risk: true,
    evidence_confirmation: true,
    decision_approval: true,
  });

  // Fetch persistent progress
  useEffect(() => {
    if (activeWorkspace) {
      fetch(`/api/workspaces/${activeWorkspace.id}/onboarding`)
        .then((res) => res.json())
        .then((data) => {
          if (data.current_step) {
            const idx = STEPS.findIndex((s) => s.id === data.current_step);
            if (idx >= 0) setCurrentStepIndex(idx);
          }
        })
        .catch(() => {});
    }
  }, [activeWorkspace]);

  const advanceStep = async (nextIndex: number) => {
    const target = Math.min(nextIndex, STEPS.length - 1);
    setCurrentStepIndex(target);

    if (activeWorkspace) {
      try {
        await fetch(`/api/workspaces/${activeWorkspace.id}/onboarding`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ step: STEPS[target].id }),
        });
      } catch {}
    }
  };

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim() || !activeWorkspace) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/workspaces/${activeWorkspace.id}/invitations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ invited_email: inviteEmail.trim(), role: inviteRole }),
      });
      if (res.ok) {
        setInvitationsSent([...invitationsSent, inviteEmail.trim()]);
        setInviteEmail("");
      }
    } catch {} finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-8 space-y-8 animate-in fade-in duration-300">
      {/* Step Header Indicator */}
      <div className="bg-stone-100/60 border border-stone-200 rounded-2xl p-4">
        <div className="flex items-center justify-between overflow-x-auto gap-2 pb-2">
          {STEPS.map((step, idx) => {
            const Icon = step.icon;
            const isDone = idx < currentStepIndex;
            const isCurrent = idx === currentStepIndex;

            return (
              <button
                key={step.id}
                onClick={() => advanceStep(idx)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors shrink-0 ${
                  isCurrent
                    ? "bg-orange-600 text-white shadow-md shadow-orange-600/20"
                    : isDone
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "text-stone-500 hover:text-stone-700"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{step.title}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Wizard Content Cards */}
      <div className="bg-white border border-stone-200 rounded-2xl p-8 shadow-sm">
        {/* STEP 0: Welcome */}
        {currentStepIndex === 0 && (
          <div className="space-y-6 text-center py-4">
            <div className="w-16 h-16 rounded-2xl bg-orange-50 text-orange-600 border border-orange-200 flex items-center justify-center mx-auto shadow-sm">
              <Sparkles className="w-8 h-8" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-stone-900">Welcome to Obligation Agent</h1>
              <p className="text-stone-600 text-sm mt-2 max-w-md mx-auto leading-relaxed">
                Transform real organization communications into transparent commitments, graph intelligence, and controlled decision workflows.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 text-left">
              <div className="p-4 rounded-xl bg-stone-50 border border-stone-200">
                <div className="font-semibold text-stone-800 text-xs mb-1">Atomic Obligations</div>
                <div className="text-stone-600 text-[11px]">Unambiguous tracking where reciprocal commitment is the core unit.</div>
              </div>
              <div className="p-4 rounded-xl bg-stone-50 border border-stone-200">
                <div className="font-semibold text-stone-800 text-xs mb-1">Human-in-the-Loop</div>
                <div className="text-stone-600 text-[11px]">Mandatory human approval for all interventions and resolutions.</div>
              </div>
              <div className="p-4 rounded-xl bg-stone-50 border border-stone-200">
                <div className="font-semibold text-stone-800 text-xs mb-1">Graph Intelligence</div>
                <div className="text-stone-600 text-[11px]">Proactive root-cause analysis and critical path risk prediction.</div>
              </div>
            </div>
            <button
              onClick={() => advanceStep(1)}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-orange-600 hover:bg-orange-700 text-white rounded-xl text-xs font-semibold shadow transition-all active:scale-95"
            >
              <span>Get Started</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* STEP 1: Workspace */}
        {currentStepIndex === 1 && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 border-b border-stone-200 pb-4">
              <Building2 className="w-6 h-6 text-orange-600" />
              <div>
                <h2 className="text-lg font-bold text-stone-900">Set Up Your Workspace</h2>
                <p className="text-xs text-stone-600">Configure your organization tenant boundary and timezone.</p>
              </div>
            </div>
            <div className="space-y-4 text-xs">
              <div>
                <label className="block font-medium text-stone-700 mb-1.5">Workspace Name</label>
                <input
                  type="text"
                  value={workspaceName}
                  onChange={(e) => setWorkspaceName(e.target.value)}
                  className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3.5 py-2.5 text-stone-800 focus:outline-none focus:border-orange-500"
                />
              </div>
              <div>
                <label className="block font-medium text-stone-700 mb-1.5">Default Timezone</label>
                <select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3.5 py-2.5 text-stone-800 focus:outline-none focus:border-orange-500"
                >
                  <option value="UTC">UTC (Coordinated Universal Time)</option>
                  <option value="America/New_York">America/New_York (EST/EDT)</option>
                  <option value="America/Los_Angeles">America/Los_Angeles (PST/PDT)</option>
                  <option value="Europe/London">Europe/London (GMT/BST)</option>
                  <option value="Asia/Tokyo">Asia/Tokyo (JST)</option>
                </select>
              </div>
            </div>
            <div className="flex justify-between pt-4">
              <button
                onClick={() => advanceStep(0)}
                className="inline-flex items-center gap-1.5 px-4 py-2 border border-stone-200 text-stone-600 hover:text-stone-800 rounded-xl text-xs"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Back
              </button>
              <button
                onClick={() => advanceStep(2)}
                className="inline-flex items-center gap-1.5 px-6 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-xl text-xs font-semibold shadow"
              >
                Continue <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: Invite Team */}
        {currentStepIndex === 2 && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 border-b border-stone-200 pb-4">
              <Users className="w-6 h-6 text-orange-600" />
              <div>
                <h2 className="text-lg font-bold text-stone-900">Invite Your Team</h2>
                <p className="text-xs text-stone-600">Issue single-use secure invite tokens with granular roles.</p>
              </div>
            </div>
            <form onSubmit={handleSendInvite} className="flex gap-2 text-xs">
              <input
                type="email"
                required
                placeholder="colleague@company.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                className="flex-1 bg-stone-50 border border-stone-200 rounded-xl px-3.5 py-2 text-stone-800 focus:outline-none focus:border-orange-500"
              />
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-stone-800 focus:outline-none focus:border-orange-500"
              >
                <option value="MEMBER">Member</option>
                <option value="OPERATOR">Operator</option>
                <option value="ADMIN">Admin</option>
              </select>
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white rounded-xl font-medium shadow"
              >
                {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Send Invite"}
              </button>
            </form>
            {invitationsSent.length > 0 && (
              <div className="space-y-2 text-xs">
                <div className="text-stone-600 font-medium">Invitations Issued:</div>
                <div className="divide-y divide-stone-200/60 border border-stone-200 rounded-xl bg-stone-50/40">
                  {invitationsSent.map((em) => (
                    <div key={em} className="p-2.5 flex items-center justify-between">
                      <span className="text-stone-800">{em}</span>
                      <span className="text-emerald-700 flex items-center gap-1 text-[11px] font-medium">
                        <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Token Created
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="flex justify-between pt-4">
              <button
                onClick={() => advanceStep(1)}
                className="inline-flex items-center gap-1.5 px-4 py-2 border border-stone-200 text-stone-600 hover:text-stone-800 rounded-xl text-xs"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Back
              </button>
              <button
                onClick={() => advanceStep(3)}
                className="inline-flex items-center gap-1.5 px-6 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-xl text-xs font-semibold shadow"
              >
                Continue <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: Slack Integration */}
        {currentStepIndex === 3 && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 border-b border-stone-200 pb-4">
              <Radio className="w-6 h-6 text-orange-600" />
              <div>
                <h2 className="text-lg font-bold text-stone-900">Connect Slack Communication</h2>
                <p className="text-xs text-stone-600">Ingest real work signals with HMAC signature verification.</p>
              </div>
            </div>
            <div className="p-6 rounded-2xl bg-stone-50 border border-stone-200 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div>
                <div className="font-semibold text-stone-900 text-sm">Slack Workspace App</div>
                <p className="text-stone-600 text-xs mt-1">Connect Slack OAuth to monitor commitments across designated channels.</p>
              </div>
              <Link
                href="/integrations"
                className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-xl text-xs font-semibold shrink-0 shadow-sm transition"
              >
                Configure Integration &rarr;
              </Link>
            </div>
            <div className="flex justify-between pt-4">
              <button
                onClick={() => advanceStep(2)}
                className="inline-flex items-center gap-1.5 px-4 py-2 border border-stone-200 text-stone-600 hover:text-stone-800 rounded-xl text-xs"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Back
              </button>
              <button
                onClick={() => advanceStep(4)}
                className="inline-flex items-center gap-1.5 px-6 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-xl text-xs font-semibold shadow"
              >
                Continue <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 4: Monitoring Preferences */}
        {currentStepIndex === 4 && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 border-b border-stone-200 pb-4">
              <Bell className="w-6 h-6 text-orange-600" />
              <div>
                <h2 className="text-lg font-bold text-stone-900">Alert & Notification Policies</h2>
                <p className="text-xs text-stone-600">Customize proactive alert conditions for human operators.</p>
              </div>
            </div>
            <div className="space-y-3 text-xs">
              <label className="flex items-center justify-between p-3.5 rounded-xl bg-stone-50 border border-stone-200 cursor-pointer">
                <div>
                  <div className="font-medium text-stone-800">Critical Risk & Cascade Alerts</div>
                  <div className="text-stone-600 text-[11px]">Notify when dependency risk crosses critical probability thresholds.</div>
                </div>
                <input
                  type="checkbox"
                  checked={alertsEnabled.critical_risk}
                  onChange={(e) => setAlertsEnabled({ ...alertsEnabled, critical_risk: e.target.checked })}
                  className="rounded text-orange-600 focus:ring-orange-500 bg-stone-100 border-stone-300"
                />
              </label>
              <label className="flex items-center justify-between p-3.5 rounded-xl bg-stone-50 border border-stone-200 cursor-pointer">
                <div>
                  <div className="font-medium text-stone-800">Evidence Review Required</div>
                  <div className="text-stone-600 text-[11px]">Alert operators when suggested completion evidence requires human verification.</div>
                </div>
                <input
                  type="checkbox"
                  checked={alertsEnabled.evidence_confirmation}
                  onChange={(e) => setAlertsEnabled({ ...alertsEnabled, evidence_confirmation: e.target.checked })}
                  className="rounded text-orange-600 focus:ring-orange-500 bg-stone-100 border-stone-300"
                />
              </label>
              <label className="flex items-center justify-between p-3.5 rounded-xl bg-stone-50 border border-stone-200 cursor-pointer">
                <div>
                  <div className="font-medium text-stone-800">Decision Plan Authorizations</div>
                  <div className="text-stone-600 text-[11px]">Notify operators when new strategic Decision Plans are generated.</div>
                </div>
                <input
                  type="checkbox"
                  checked={alertsEnabled.decision_approval}
                  onChange={(e) => setAlertsEnabled({ ...alertsEnabled, decision_approval: e.target.checked })}
                  className="rounded text-orange-600 focus:ring-orange-500 bg-stone-100 border-stone-300"
                />
              </label>
            </div>
            <div className="flex justify-between pt-4">
              <button
                onClick={() => advanceStep(3)}
                className="inline-flex items-center gap-1.5 px-4 py-2 border border-stone-200 text-stone-600 hover:text-stone-800 rounded-xl text-xs"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Back
              </button>
              <button
                onClick={() => advanceStep(5)}
                className="inline-flex items-center gap-1.5 px-6 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-xl text-xs font-semibold shadow"
              >
                Continue <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 5: Import Obligations */}
        {currentStepIndex === 5 && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 border-b border-stone-200 pb-4">
              <FileSpreadsheet className="w-6 h-6 text-emerald-600" />
              <div>
                <h2 className="text-lg font-bold text-stone-900">Import Initial Obligations</h2>
                <p className="text-xs text-stone-600">Bulk upload commitments via CSV or capture from unstructured text.</p>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div
                onClick={() => setImportModalOpen(true)}
                className="p-6 rounded-2xl bg-stone-50 border border-stone-200 hover:border-orange-500/50 cursor-pointer transition-colors text-center flex flex-col items-center justify-center"
              >
                <FileSpreadsheet className="w-8 h-8 text-emerald-600 mb-2" />
                <span className="font-semibold text-stone-800">Bulk CSV Ingestion</span>
                <span className="text-stone-500 text-[11px] mt-0.5">Upload spreadsheet with owners & deadlines</span>
              </div>
              <Link
                href="/capture"
                className="p-6 rounded-2xl bg-stone-50 border border-stone-200 hover:border-orange-500/50 cursor-pointer transition-colors text-center flex flex-col items-center justify-center"
              >
                <Sparkles className="w-8 h-8 text-orange-600 mb-2" />
                <span className="font-semibold text-stone-800">AI Message Capture</span>
                <span className="text-stone-500 text-[11px] mt-0.5">Extract obligations from emails or chat transcripts</span>
              </Link>
            </div>
            <div className="flex justify-between pt-4">
              <button
                onClick={() => advanceStep(4)}
                className="inline-flex items-center gap-1.5 px-4 py-2 border border-stone-200 text-stone-600 hover:text-stone-800 rounded-xl text-xs"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Back
              </button>
              <button
                onClick={() => advanceStep(6)}
                className="inline-flex items-center gap-1.5 px-6 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-xl text-xs font-semibold shadow"
              >
                Finish Setup <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 6: Completed */}
        {currentStepIndex === 6 && (
          <div className="space-y-6 text-center py-6">
            <div className="w-16 h-16 rounded-2xl bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center justify-center mx-auto shadow-sm">
              <ShieldCheck className="w-8 h-8" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-stone-900">Setup Complete & Beta Ready</h1>
              <p className="text-stone-600 text-sm mt-2 max-w-md mx-auto leading-relaxed">
                Your workspace is operational. Start discovering commitments, monitoring causal risks, and authorizing strategic decision plans.
              </p>
            </div>
            <div className="flex items-center justify-center gap-3 pt-4">
              <Link
                href="/queues"
                className="px-5 py-2.5 bg-stone-100 hover:bg-stone-200 text-stone-800 border border-stone-200 rounded-xl text-xs font-semibold transition-colors"
              >
                View Operational Queues
              </Link>
              <Link
                href="/intelligence/decisions"
                className="px-6 py-2.5 bg-orange-600 hover:bg-orange-700 text-white rounded-xl text-xs font-semibold shadow transition-colors"
              >
                Launch Decision Center &rarr;
              </Link>
            </div>
          </div>
        )}
      </div>

      {/* CSV Import Modal */}
      <CsvImportModal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onSuccess={() => advanceStep(6)}
      />
    </div>
  );
}
