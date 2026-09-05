"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { workspacesApi } from "@/lib/api/obligations";
import { CheckCircle2, AlertCircle, Loader2, UserCheck, ShieldCheck, ArrowRight } from "lucide-react";
import Link from "next/link";

function AcceptInvitationContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, isAuthenticated, refreshWorkspaces, switchWorkspace } = useAuth();

  const tokenParam = searchParams.get("token") || "";

  const [token, setToken] = useState(tokenParam);
  const [displayName, setDisplayName] = useState(user?.display_name || "");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [success, setSuccess] = useState(false);
  const [acceptedWorkspaceId, setAcceptedWorkspaceId] = useState("");

  useEffect(() => {
    if (tokenParam) {
      setToken(tokenParam);
    }
  }, [tokenParam]);

  const handleAccept = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token.trim()) {
      setErrorMsg("Invitation token is required.");
      return;
    }

    setLoading(true);
    setErrorMsg("");

    try {
      const payload: { token: string; display_name?: string; password?: string } = {
        token: token.trim(),
      };
      if (!isAuthenticated) {
        if (!displayName.trim()) {
          throw new Error("Please provide your display name.");
        }
        if (!password || password.length < 8) {
          throw new Error("Password must be at least 8 characters.");
        }
        payload.display_name = displayName.trim();
        payload.password = password;
      }

      const res = await workspacesApi.acceptInvitation(payload);
      setSuccess(true);
      setAcceptedWorkspaceId(res.workspace_id);

      if (refreshWorkspaces) {
        await refreshWorkspaces();
      }
      if (switchWorkspace && res.workspace_id) {
        switchWorkspace(res.workspace_id);
      }

      setTimeout(() => {
        router.push("/obligations");
      }, 2000);
    } catch (err: unknown) {
      const error = err as Error;
      setErrorMsg(error.message || "Failed to accept invitation. Token may be invalid or expired.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-stone-50 text-stone-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-stone-100 border border-stone-200 rounded-xl p-8 shadow-2xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-lg bg-blue-700/20 border border-blue-600/30 flex items-center justify-center text-blue-500">
            <UserCheck className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-stone-900">Accept Team Invitation</h1>
            <p className="text-xs text-stone-600">Join your team workspace on Obligation Agent</p>
          </div>
        </div>

        {success ? (
          <div className="bg-emerald-950/40 border border-emerald-500/30 rounded-lg p-5 text-center space-y-3">
            <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
            <h3 className="text-base font-semibold text-emerald-200">Invitation Accepted!</h3>
            <p className="text-xs text-stone-700">
              You have joined workspace <span className="font-mono text-emerald-400">{acceptedWorkspaceId}</span>.
              Redirecting to obligations dashboard...
            </p>
            <div className="pt-2">
              <Link
                href="/obligations"
                className="inline-flex items-center gap-2 text-xs font-semibold text-emerald-400 hover:text-emerald-300"
              >
                Go to Obligations <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleAccept} className="space-y-4">
            {errorMsg && (
              <div className="bg-rose-950/50 border border-rose-500/30 rounded-lg p-3 text-xs text-rose-300 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span>{errorMsg}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-stone-700 mb-1">Invitation Token</label>
              <input
                type="text"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste invitation token here"
                required
                className="w-full bg-stone-200 border border-stone-300 rounded-lg px-3 py-2 text-xs text-stone-800 focus:outline-none focus:border-blue-600 font-mono"
              />
            </div>

            {!isAuthenticated ? (
              <>
                <div className="p-3 bg-stone-200/60 border border-stone-300/50 rounded-lg text-xs text-stone-700 flex items-start gap-2">
                  <ShieldCheck className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                  <span>Create your account to accept this invitation and join the workspace.</span>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-stone-700 mb-1">Your Name</label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="e.g. Alex Johnson"
                    required
                    className="w-full bg-stone-200 border border-stone-300 rounded-lg px-3 py-2 text-xs text-stone-800 focus:outline-none focus:border-blue-600"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-stone-700 mb-1">Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    required
                    minLength={8}
                    className="w-full bg-stone-200 border border-stone-300 rounded-lg px-3 py-2 text-xs text-stone-800 focus:outline-none focus:border-blue-600"
                  />
                </div>
              </>
            ) : (
              <div className="p-3 bg-indigo-950/30 border border-blue-600/20 rounded-lg text-xs text-blue-600">
                Logged in as <span className="font-semibold text-blue-700">{user?.email}</span> ({user?.display_name}). This account will be linked to the workspace.
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !token.trim()}
              className="w-full bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-stone-950 text-xs font-semibold py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Accepting Invitation...</span>
                </>
              ) : (
                <span>Accept & Join Workspace</span>
              )}
            </button>

            {!isAuthenticated && (
              <div className="text-center pt-2 text-xs text-stone-600">
                Already have an account?{" "}
                <Link href="/login" className="text-blue-500 hover:underline">
                  Log in first
                </Link>
              </div>
            )}
          </form>
        )}
      </div>
    </div>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-stone-50 flex items-center justify-center text-stone-600">Loading invitation...</div>}>
      <AcceptInvitationContent />
    </Suspense>
  );
}
