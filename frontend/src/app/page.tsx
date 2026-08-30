"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  ShieldAlert,
  ArrowUpRight,
  ArrowDownLeft,
  CheckCircle2,
  Sparkles,
  RefreshCw,
  Search,
  Inbox,
  AlertTriangle,
} from "lucide-react";
import { DashboardSummaryResponse, Obligation } from "@/lib/types/obligation";
import { ObligationCard } from "@/components/obligations/ObligationCard";
import { obligationsApi } from "@/lib/api/obligations";
import { useToast } from "@/components/ui/ToastContext";

export default function DashboardPage() {
  const { toast } = useToast();
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"all" | "you_owe" | "others_owe" | "at_risk">("all");

  const loadData = useCallback(async () => {
    try {
      const data = await obligationsApi.getDashboardSummary();
      setSummary(data);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load dashboard data.";
      setError(msg);
      toast({
        type: "error",
        title: "Connection Error",
        description: msg,
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Filter helper
  const filterList = (list: Obligation[]) => {
    if (!searchQuery.trim()) return list;
    const q = searchQuery.toLowerCase();
    return list.filter(
      (ob) =>
        ob.action.toLowerCase().includes(q) ||
        ob.owner.toLowerCase().includes(q) ||
        ob.beneficiary.toLowerCase().includes(q) ||
        (ob.next_action && ob.next_action.toLowerCase().includes(q))
    );
  };

  const youOweFiltered = summary ? filterList(summary.you_owe_obligations) : [];
  const othersOweFiltered = summary ? filterList(summary.others_owe_obligations) : [];
  const atRiskFiltered = summary ? filterList(summary.at_risk_obligations) : [];

  return (
    <div className="space-y-8">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
            Obligation Control Center
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Tracking reciprocal commitments, ownership dependencies, and deadline risks.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setLoading(true);
              loadData();
            }}
            disabled={loading}
            className="p-2 rounded-lg border border-zinc-800 bg-zinc-900/80 hover:bg-zinc-800 text-zinc-300 transition-colors"
            title="Refresh Ledger"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-blue-400" : ""}`} />
          </button>
          <Link
            href="/capture"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-all shadow-lg shadow-blue-600/20 active:scale-95"
          >
            <Sparkles className="w-4 h-4" />
            <span>Capture New Obligation</span>
          </Link>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* You Owe */}
        <div
          onClick={() => setActiveTab("you_owe")}
          className={`cursor-pointer p-5 rounded-2xl border transition-all ${
            activeTab === "you_owe"
              ? "bg-blue-950/40 border-blue-500 ring-1 ring-blue-500"
              : "bg-zinc-900/60 hover:bg-zinc-900 border-zinc-800"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              You Owe
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
              <ArrowUpRight className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 text-3xl font-extrabold text-white">
            {summary ? summary.you_owe_count : "—"}
          </div>
          <div className="mt-1 text-xs text-zinc-400">Active commitments to others</div>
        </div>

        {/* Others Owe You */}
        <div
          onClick={() => setActiveTab("others_owe")}
          className={`cursor-pointer p-5 rounded-2xl border transition-all ${
            activeTab === "others_owe"
              ? "bg-emerald-950/40 border-emerald-500 ring-1 ring-emerald-500"
              : "bg-zinc-900/60 hover:bg-zinc-900 border-zinc-800"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Others Owe You
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <ArrowDownLeft className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 text-3xl font-extrabold text-white">
            {summary ? summary.others_owe_count : "—"}
          </div>
          <div className="mt-1 text-xs text-zinc-400">Incoming promises & deliverables</div>
        </div>

        {/* At Risk */}
        <div
          onClick={() => setActiveTab("at_risk")}
          className={`cursor-pointer p-5 rounded-2xl border transition-all ${
            activeTab === "at_risk"
              ? "bg-rose-950/40 border-rose-500 ring-1 ring-rose-500"
              : "bg-zinc-900/60 hover:bg-zinc-900 border-zinc-800"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-400 uppercase tracking-wider">
              At Risk
            </span>
            <div className="w-8 h-8 rounded-lg bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <ShieldAlert className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 text-3xl font-extrabold text-rose-300">
            {summary ? summary.at_risk_count : "—"}
          </div>
          <div className="mt-1 text-xs text-zinc-400">Overdue or &lt;48h to deadline</div>
        </div>

        {/* Completed */}
        <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Resolved
            </span>
            <div className="w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-400">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 text-3xl font-extrabold text-zinc-300">
            {summary ? summary.completed_count : "—"}
          </div>
          <div className="mt-1 text-xs text-zinc-400">Fulfilled obligations</div>
        </div>
      </div>

      {/* Search & Tab Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        {/* Tabs */}
        <div className="flex items-center p-1 bg-zinc-900 border border-zinc-800 rounded-xl overflow-x-auto">
          <button
            onClick={() => setActiveTab("all")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors whitespace-nowrap ${
              activeTab === "all"
                ? "bg-zinc-800 text-white shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            All Feeds
          </button>
          <button
            onClick={() => setActiveTab("you_owe")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors whitespace-nowrap ${
              activeTab === "you_owe"
                ? "bg-blue-600/20 text-blue-300 border border-blue-500/30"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <span>You Owe</span>
            {summary && summary.you_owe_count > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-blue-500/30 text-[10px] text-blue-200 font-bold">
                {summary.you_owe_count}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab("others_owe")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors whitespace-nowrap ${
              activeTab === "others_owe"
                ? "bg-emerald-600/20 text-emerald-300 border border-emerald-500/30"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <span>Others Owe You</span>
            {summary && summary.others_owe_count > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-emerald-500/30 text-[10px] text-emerald-200 font-bold">
                {summary.others_owe_count}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab("at_risk")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors whitespace-nowrap ${
              activeTab === "at_risk"
                ? "bg-rose-600/20 text-rose-300 border border-rose-500/30"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <span>At Risk</span>
            {summary && summary.at_risk_count > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-rose-500/30 text-[10px] text-rose-200 font-bold">
                {summary.at_risk_count}
              </span>
            )}
          </button>
        </div>

        {/* Search Box */}
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search action or person..."
            className="w-full pl-9 pr-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-400 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-500/40 text-rose-300 text-sm flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
            <div>{error}</div>
          </div>
          <button
            onClick={() => {
              setLoading(true);
              loadData();
            }}
            className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold"
          >
            Retry
          </button>
        </div>
      )}

      {/* Main Sections */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="h-44 rounded-xl bg-zinc-900/40 border border-zinc-800/60 animate-pulse"
            />
          ))}
        </div>
      ) : (
        <div className="space-y-10">
          {/* Section: At Risk (If any exist and tab allows) */}
          {(activeTab === "all" || activeTab === "at_risk") && atRiskFiltered.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-rose-500 animate-ping" />
                  <h2 className="text-lg font-bold text-rose-300 flex items-center gap-2">
                    <span>At Risk Obligations</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30 font-medium">
                      Requires Immediate Attention
                    </span>
                  </h2>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {atRiskFiltered.map((ob) => (
                  <ObligationCard
                    key={ob.id}
                    obligation={ob}
                    onStatusChanged={loadData}
                    onDeleted={loadData}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Section: You Owe */}
          {(activeTab === "all" || activeTab === "you_owe") && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <ArrowUpRight className="w-5 h-5 text-blue-400" />
                  <span>You Owe</span>
                  <span className="text-xs font-normal text-zinc-400">
                    ({youOweFiltered.length} items)
                  </span>
                </h2>
                <Link
                  href="/obligations?type=OWED_BY_ME"
                  className="text-xs text-blue-400 hover:text-blue-300 font-medium"
                >
                  View full feed &rarr;
                </Link>
              </div>

              {youOweFiltered.length === 0 ? (
                <div className="p-8 rounded-2xl bg-zinc-900/30 border border-dashed border-zinc-800 text-center text-zinc-400 space-y-2">
                  <Inbox className="w-8 h-8 mx-auto text-zinc-600" />
                  <div className="text-sm font-medium">No outgoing obligations</div>
                  <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                    You have no active obligations owed to others right now.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {youOweFiltered.map((ob) => (
                    <ObligationCard
                      key={ob.id}
                      obligation={ob}
                      onStatusChanged={loadData}
                      onDeleted={loadData}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Section: Others Owe You */}
          {(activeTab === "all" || activeTab === "others_owe") && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <ArrowDownLeft className="w-5 h-5 text-emerald-400" />
                  <span>Others Owe You</span>
                  <span className="text-xs font-normal text-zinc-400">
                    ({othersOweFiltered.length} items)
                  </span>
                </h2>
                <Link
                  href="/obligations?type=OWED_TO_ME"
                  className="text-xs text-emerald-400 hover:text-emerald-300 font-medium"
                >
                  View full feed &rarr;
                </Link>
              </div>

              {othersOweFiltered.length === 0 ? (
                <div className="p-8 rounded-2xl bg-zinc-900/30 border border-dashed border-zinc-800 text-center text-zinc-400 space-y-2">
                  <Inbox className="w-8 h-8 mx-auto text-zinc-600" />
                  <div className="text-sm font-medium">No incoming obligations</div>
                  <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                    No pending deliverables or commitments tracked from others.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {othersOweFiltered.map((ob) => (
                    <ObligationCard
                      key={ob.id}
                      obligation={ob}
                      onStatusChanged={loadData}
                      onDeleted={loadData}
                    />
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
