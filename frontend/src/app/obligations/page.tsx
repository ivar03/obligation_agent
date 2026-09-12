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
  AlertTriangle,
  Clock,
  ArrowRight,
  Filter,
} from "lucide-react";
import { Obligation, ObligationStatus, ObligationType } from "@/lib/types/obligation";
import { ObligationCard } from "@/components/obligations/ObligationCard";
import { obligationsApi } from "@/lib/api/obligations";
import { useToast } from "@/components/ui/ToastContext";

function ObligationsContent() {
  const searchParams = useSearchParams();
  const initialType = (searchParams.get("type") as ObligationType) || undefined;
  const initialAtRisk = searchParams.get("at_risk") === "true";
  const initialStatus = (searchParams.get("status") as ObligationStatus) || "ALL";

  const { toast } = useToast();
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters
  const [typeFilter, setTypeFilter] = useState<ObligationType | "ALL">(initialType || "ALL");
  const [statusFilter, setStatusFilter] = useState<ObligationStatus | "ALL">(initialStatus);
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2.5">
            <Layers className="w-6 h-6 text-orange-600" />
            <span>Obligations Ledger</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Complete reciprocal commitments database with real-time risk, causal dependencies, and evidence consensus.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setLoading(true);
              fetchObligations();
            }}
            disabled={loading}
            className="p-2 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-600 hover:text-slate-900 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-orange-600" : ""}`} />
          </button>
          <Link
            href="/capture"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold shadow-xs transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            <span>Analyze & Capture</span>
          </Link>
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs space-y-3">
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
          {/* Quick Filter Chips */}
          <div className="flex flex-wrap items-center gap-1.5 p-1 bg-slate-50 border border-slate-200 rounded-xl">
            <button
              onClick={() => {
                setTypeFilter("ALL");
                setAtRiskOnly(false);
                setStatusFilter("ALL");
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                typeFilter === "ALL" && !atRiskOnly && statusFilter === "ALL"
                  ? "bg-white text-slate-900 shadow-xs border border-slate-200"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setTypeFilter("OWED_BY_ME")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                typeFilter === "OWED_BY_ME"
                  ? "bg-orange-50 text-orange-700 border border-orange-200"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              You Owe
            </button>
            <button
              onClick={() => setTypeFilter("OWED_TO_ME")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                typeFilter === "OWED_TO_ME"
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Others Owe You
            </button>
            <button
              onClick={() => setAtRiskOnly(!atRiskOnly)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                atRiskOnly
                  ? "bg-amber-50 text-amber-800 border border-amber-200"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              At Risk Only
            </button>
          </div>

          {/* Status Dropdown & Search */}
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ObligationStatus | "ALL")}
              className="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-800 focus:outline-none focus:border-orange-400"
            >
              <option value="ALL">All Statuses</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="BLOCKED">Blocked</option>
              <option value="OVERDUE">Overdue</option>
              <option value="CONFIRMED">Confirmed</option>
              <option value="COMPLETED">Completed</option>
              <option value="CANCELLED">Cancelled</option>
            </select>

            {/* Search Input */}
            <div className="relative min-w-[220px]">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search action or owner..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-8 pr-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-orange-400"
              />
            </div>
          </div>
        </div>

        {/* Active Filters Summary */}
        <div className="text-[11px] text-slate-500 flex items-center justify-between pt-1">
          <span>
            Showing <strong className="text-slate-800 font-semibold">{obligations.length}</strong> of{" "}
            <strong className="text-slate-800 font-semibold">{total}</strong> commitments
          </span>
          {(typeFilter !== "ALL" || statusFilter !== "ALL" || atRiskOnly || searchTerm) && (
            <button
              onClick={() => {
                setTypeFilter("ALL");
                setStatusFilter("ALL");
                setAtRiskOnly(false);
                setSearchTerm("");
              }}
              className="text-orange-600 hover:text-orange-700 font-medium"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Obligations Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-44 rounded-2xl bg-white border border-slate-100 p-6 animate-pulse" />
          ))}
        </div>
      ) : obligations.length === 0 ? (
        /* Meaningful Empty State */
        <div className="p-12 text-center bg-white rounded-3xl border border-slate-200 shadow-xs max-w-lg mx-auto space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-orange-50 border border-orange-200 flex items-center justify-center text-orange-600 mx-auto">
            <Inbox className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">No obligations found</h3>
            <p className="text-xs text-slate-500 mt-1">
              {searchTerm || typeFilter !== "ALL" || statusFilter !== "ALL" || atRiskOnly
                ? "No obligations matched your active filters. Try clearing filters or changing your search terms."
                : "No commitments have been registered in this workspace yet. Connect a workspace integration or capture your first obligation."}
            </p>
          </div>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-2 pt-2">
            <Link
              href="/capture"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold shadow-xs"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Capture Obligation</span>
            </Link>
            <Link
              href="/demo"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 text-xs font-semibold"
            >
              <span>Explore Demo Data</span>
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {obligations.map((obligation) => (
            <ObligationCard key={obligation.id} obligation={obligation} />
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
        <div className="p-8 text-center text-slate-400 text-xs animate-pulse">
          Loading obligations ledger...
        </div>
      }
    >
      <ObligationsContent />
    </Suspense>
  );
}
