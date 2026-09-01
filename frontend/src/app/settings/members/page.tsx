"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { workspacesApi } from "@/lib/api/obligations";
import { Users, UserPlus, Trash2, Copy, Check, Loader2, AlertCircle } from "lucide-react";

interface Member {
  id: string;
  user_id: string;
  email?: string | null;
  display_name?: string | null;
  role: string;
  created_at?: string | null;
}



interface Invitation {
  id: string;
  workspace_id: string;
  invited_email: string;
  role: string;
  status: string;
  expires_at: string;
  created_at: string;
  invitation_token?: string;
}

export default function MembersSettingsPage() {
  const { activeWorkspace } = useAuth();
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("MEMBER");
  const [inviteSuccess, setInviteSuccess] = useState<Invitation | null>(null);
  const [copied, setCopied] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const fetchData = useCallback(async () => {
    if (!activeWorkspace) return;
    try {
      // Fetch members
      const dataMem = await workspacesApi.listMembers(activeWorkspace.id);
      if (dataMem) {
        setMembers(dataMem || []);
      }


      // Fetch invitations
      const dataInv = await workspacesApi.listInvitations<Invitation>(activeWorkspace.id);
      if (dataInv) {
        setInvitations(dataInv || []);
      }
    } catch {}
  }, [activeWorkspace]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim() || !activeWorkspace) return;
    setLoading(true);
    setErrorMsg("");
    setInviteSuccess(null);
    try {
      const data = await workspacesApi.createInvitation<Invitation>(activeWorkspace.id, {
        invited_email: inviteEmail.trim(),
        role: inviteRole,
      });
      setInviteSuccess(data);

      setInviteEmail("");
      fetchData();
    } catch (err: unknown) {
      const error = err as Error;
      setErrorMsg(error.message || "Invitation error.");
    } finally {
      setLoading(false);
    }
  };

  const handleCancelInvite = async (invId: string) => {
    if (!activeWorkspace) return;
    try {
      await workspacesApi.cancelInvitation(activeWorkspace.id, invId);
      fetchData();
    } catch {}
  };

  const handleCopyLink = (token?: string) => {
    if (!token) return;
    const url = `${window.location.origin}/onboarding/accept?token=${token}`;
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };


  return (
    <div className="space-y-6">
      {/* Invite Box */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div>
          <h2 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
            <UserPlus className="w-4 h-4 text-blue-400" />
            <span>Invite Team Member</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">Issue a single-use expirable invitation link with role-based access.</p>
        </div>

        {errorMsg && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSendInvite} className="flex flex-col sm:flex-row gap-2.5 text-xs max-w-xl">
          <input
            type="email"
            required
            placeholder="colleague@company.com"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2 text-zinc-200 focus:outline-none focus:border-blue-500"
          />
          <select
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
            className="bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-200 focus:outline-none focus:border-blue-500"
          >
            <option value="MEMBER">Member (Read & Propose)</option>
            <option value="OPERATOR">Operator (Approve & Execute)</option>
            <option value="ADMIN">Admin (Full Control)</option>
          </select>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl font-semibold shadow transition-all shrink-0"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Send Invite"}
          </button>
        </form>

        {inviteSuccess && inviteSuccess.invitation_token && (
          <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs space-y-2 animate-in fade-in">
            <div className="font-semibold text-emerald-400">Invitation Token Generated!</div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={`${typeof window !== "undefined" ? window.location.origin : ""}/onboarding/accept?token=${inviteSuccess.invitation_token}`}
                className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-zinc-300 font-mono text-[11px]"
              />
              <button
                onClick={() => handleCopyLink(inviteSuccess.invitation_token)}
                className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg font-medium flex items-center gap-1 shrink-0"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? "Copied!" : "Copy Link"}</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Active Members Roster */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden shadow-sm">
        <div className="px-6 py-4 border-b border-zinc-800 bg-zinc-950/60 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
              <Users className="w-4 h-4 text-purple-400" />
              <span>Workspace Members</span>
            </h3>
            <p className="text-xs text-zinc-400">Currently active members and operators in this workspace boundary.</p>
          </div>
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
            {members.length} Total
          </span>
        </div>

        <div className="divide-y divide-zinc-800/60 text-xs">
          {members.length === 0 ? (
            <div className="p-8 text-center text-zinc-500">No members loaded.</div>
          ) : (
            members.map((m) => (
              <div key={m.id} className="p-4 flex items-center justify-between hover:bg-zinc-800/30 transition-colors">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-xs">
                    {(m.display_name || m.email || "U").charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="font-semibold text-zinc-200">{m.display_name || "Workspace Member"}</div>
                    <div className="text-zinc-500 text-[11px]">{m.email || m.user_id}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      m.role === "OWNER"
                        ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                        : m.role === "ADMIN"
                        ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                        : m.role === "OPERATOR"
                        ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                        : "bg-zinc-800 text-zinc-400"
                    }`}
                  >
                    {m.role}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Pending Invitations */}
      {invitations.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-zinc-800 bg-zinc-950/60">
            <h3 className="text-sm font-bold text-zinc-100">Pending & Historical Invitations</h3>
          </div>
          <div className="divide-y divide-zinc-800/60 text-xs">
            {invitations.map((inv) => (
              <div key={inv.id} className="p-4 flex items-center justify-between hover:bg-zinc-800/30 transition-colors">
                <div>
                  <div className="font-medium text-zinc-200">{inv.invited_email}</div>
                  <div className="text-zinc-500 text-[11px]">Role: {inv.role} • Expires: {new Date(inv.expires_at).toLocaleDateString()}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      inv.status === "PENDING"
                        ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                        : inv.status === "ACCEPTED"
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                        : "bg-zinc-800 text-zinc-500"
                    }`}
                  >
                    {inv.status}
                  </span>
                  {inv.status === "PENDING" && (
                    <button
                      onClick={() => handleCancelInvite(inv.id)}
                      className="p-1 text-zinc-500 hover:text-rose-400 transition-colors"
                      title="Revoke Invitation"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
