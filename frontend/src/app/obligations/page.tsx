"use client";

import React, { useEffect, useState, useCallback, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Layers,
  Search,
  RefreshCw,
  Sparkles,
  Inbox,
} from "lucide-react";
import { Obligation, ObligationStatus, ObligationType } from "@/lib/types/obligation";
import { ObligationCard } from "@/components/obligations/ObligationCard";
import { obligationsApi } from "@/lib/api/obligations";
import { useToast } from "@/components/ui/ToastContext";

function ObligationsContent() {
  const searchParams = useSearchParams();
  const initialType = (searchParams.get("type") as ObligationType) || undefined;
  const initialAtRisk = searchParams.get("at_risk") === "true";

  const { toast } = useToast();
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters
  const [typeFilter, setTypeFilter] = useState<ObligationType | "ALL">(initialType || "ALL");
  const [statusFilter, setStatusFilter] = useState<ObligationStatus | "ALL">("ALL");
  const [atRiskOnly, setAtRiskOnly] = useState<boolean>(initialAtRisk);
  const [searchTerm, setSearchTerm] = useState("");

  const fetchObligations = useCallback(async () => {
    try {
      const res = await obligationsApi.list({
        obligation_type: typeFilter === "ALL" ? undefined : typeFilter,
        status: statusFilter === "ALL" ? undefined : statusFilter,
        is_at_risk: atRiskOnly ? true : undefined,
        search: searchTerm.trim() ? searchTerm.trim() : undefined,
        limit: 100,
      });
      setObligations(res.items);
      setTotal(res.total);
    } catch (err) {
      toast({
        type: "error",
        title: "Failed to Fetch",
        description: err instanceof Error ? err.message : "Could not load obligations.",
      });
    } finally {
      setLoading(false);
    }
  }, [typeFilter, statusFilter, atRiskOnly, searchTerm, toast]);

  useEffect(() => {
    fetchObligations();
  }, [fetchObligations]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white flex items-center gap-2.5">
            <Layers className="w-7 h-7 text-blue-400" />
            <span>Obligation Ledger</span>
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Complete reciprocal obligation database with multi-dimensional filtering.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setLoading(true);
              fetchObligations();
            }}
            disabled={loading}
            className="p-2 rounded-lg border border-zinc-800 bg-zinc-900/80 hover:bg-zinc-800 text-zinc-300 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-blue-400" : ""}`} />
          </button>
          <Link
            href="/capture"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-all shadow-md shadow-blue-600/20 active:scale-95"
          >
            <Sparkles className="w-4 h-4" />
            <span>Capture Obligation</span>
          </Link>
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div className="bg-zinc-900/70 border border-zinc-800 rounded-2xl p-4 shadow-md space-y-4">
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
          {/* Direction Filter */}
          <div className="flex items-center gap-1 p-1 bg-zinc-950 border border-zinc-800 rounded-xl">
            <button
              onClick={() => setTypeFilter("ALL")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                typeFilter === "ALL"
                  ? "bg-zinc-800 text-white shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              All Types
            </button>
            <button
              onClick={() => setTypeFilter("OWED_BY_ME")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                typeFilter === "OWED_BY_ME"
                  ? "bg-blue-600/20 text-blue-300 border border-blue-500/30"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              You Owe
            </button>
            <button
              onClick={() => setTypeFilter("OWED_TO_ME")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                typeFilter === "OWED_TO_ME"
                  ? "bg-emerald-600/20 text-emerald-300 border border-emerald-500/30"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Others Owe You
            </button>
          </div>

          {/* Status & Risk Filters */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Status Dropdown */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ObligationStatus | "ALL")}
              className="px-3 py-1.5 rounded-xl bg-zinc-950 border border-zinc-800 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="CONFIRMED">Confirmed</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="COMPLETED">Completed</option>
              <option value="OVERDUE">Overdue</option>
              <option value="BLOCKED">Blocked</option>
              <option value="CANCELLED">Cancelled</option>
            </select>

            {/* At Risk Checkbox Toggle */}
            <button
              onClick={() => setAtRiskOnly(!atRiskOnly)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors ${
                atRiskOnly
                  ? "bg-rose-500/20 text-rose-300 border-rose-500/40"
                  : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              At Risk Only
            </button>

            {/* Search Input */}
            <div className="relative w-full sm:w-60">
              <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search action or person..."
                className="w-full pl-8 pr-3 py-1.5 rounded-xl bg-zinc-950 border border-zinc-800 text-xs text-zinc-100 placeholder-zinc-400 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Results Header */}
      <div className="flex items-center justify-between text-xs text-zinc-400">
        <div>
          Showing <span className="font-semibold text-zinc-200">{obligations.length}</span> of{" "}
          <span className="font-semibold text-zinc-200">{total}</span> obligations
        </div>
      </div>

      {/* Obligations Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="h-44 rounded-xl bg-zinc-900/40 border border-zinc-800/60 animate-pulse"
            />
          ))}
        </div>
      ) : obligations.length === 0 ? (
        <div className="p-12 rounded-2xl bg-zinc-900/40 border border-dashed border-zinc-800 text-center space-y-3">
          <Inbox className="w-10 h-10 mx-auto text-zinc-600" />
          <div className="text-sm font-semibold text-zinc-300">No obligations found</div>
          <p className="text-xs text-zinc-400 max-w-sm mx-auto">
            Try adjusting your search query or filters, or capture a new obligation from a message.
          </p>
          <div className="pt-2">
            <Link
              href="/capture"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Capture Message</span>
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {obligations.map((ob) => (
            <ObligationCard
              key={ob.id}
              obligation={ob}
              onStatusChanged={fetchObligations}
              onDeleted={fetchObligations}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ObligationsPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-6 animate-pulse">
          <div className="h-8 w-48 bg-zinc-900 rounded-lg" />
          <div className="h-16 bg-zinc-900 rounded-xl" />
        </div>
      }
    >
      <ObligationsContent />
    </Suspense>
  );
}
