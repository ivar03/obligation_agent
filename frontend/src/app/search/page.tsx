"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Search,
  Layers,
  Users,
  Brain,
  Activity,
  ArrowUpRight,
  Loader2,
} from "lucide-react";

interface SearchMatchObligation {
  id: string;
  action: string;
  owner: string;
  beneficiary: string;
  status: string;
  deadline?: string;
  url: string;
}

interface SearchMatchUser {
  id: string;
  email: string;
  display_name: string;
  role: string;
}

interface SearchMatchDecision {
  id: string;
  primary_objective: string;
  status: string;
  urgency: string;
  overall_risk: number;
  url: string;
}

interface SearchMatchEvent {
  id: string;
  provider: string;
  sender: string;
  content_snippet: string;
  received_at: string;
}

interface SearchResponse {
  query: string;
  obligations: SearchMatchObligation[];
  people: SearchMatchUser[];
  decisions: SearchMatchDecision[];
  events: SearchMatchEvent[];
}

function SearchContent() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams?.get("q") || "";

  const [query, setQuery] = useState(initialQuery);
  const [loading, setLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState<"all" | "obligations" | "people" | "decisions" | "events">("all");
  const [results, setResults] = useState<SearchResponse>({
    query: "",
    obligations: [],
    people: [],
    decisions: [],
    events: [],
  });

  const performSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults({ query: "", obligations: [], people: [], decisions: [], events: [] });
      return;
    }

    try {
      setLoading(true);
      const res = await fetch(`/api/search?q=${encodeURIComponent(searchQuery)}`);
      if (res.ok) {
        const data = await res.json();
        setResults(data);
      }
    } catch (err) {
      console.error("Search execution failed", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialQuery) {
      performSearch(initialQuery);
    }
  }, [initialQuery, performSearch]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    performSearch(query);
  };

  const totalMatches =
    results.obligations.length +
    results.people.length +
    results.decisions.length +
    results.events.length;

  const categories = [
    { id: "all", label: "All Results", count: totalMatches },
    { id: "obligations", label: "Obligations", count: results.obligations.length },
    { id: "people", label: "People", count: results.people.length },
    { id: "decisions", label: "Decisions", count: results.decisions.length },
    { id: "events", label: "Activity", count: results.events.length },
  ] as const;

  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-in fade-in duration-200">
      {/* Search Input Box */}
      <form onSubmit={handleSearchSubmit} className="relative">
        <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-stone-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search obligations, assignees, telemetry events, decision plans, evidence..."
          className="w-full bg-white border border-stone-200 rounded-2xl pl-12 pr-28 py-3.5 text-sm text-stone-900 placeholder-stone-400 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/20 shadow-sm"
        />
        <button
          type="submit"
          disabled={loading}
          className="absolute right-3 top-1/2 -translate-y-1/2 px-4 py-1.5 bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold rounded-xl transition-all shadow-sm"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Search"}
        </button>
      </form>

      {/* Category Filter Pills */}
      <div className="flex items-center gap-2 overflow-x-auto border-b border-stone-200 pb-3 text-xs">
        {categories.map((c) => {
          const isSelected = activeCategory === c.id;
          return (
            <button
              key={c.id}
              onClick={() => setActiveCategory(c.id)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-xl font-medium transition-colors shrink-0 ${
                isSelected
                  ? "bg-orange-50 text-orange-700 border border-orange-200 shadow-sm"
                  : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
              }`}
            >
              <span>{c.label}</span>
              <span className={`px-1.5 py-0.2 rounded-full text-[10px] ${
                isSelected ? "bg-orange-100 text-orange-800" : "bg-stone-100 text-stone-600"
              }`}>
                {c.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Results Container */}
      <div className="space-y-6">
        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center gap-2 text-stone-400 text-xs">
            <Loader2 className="w-5 h-5 animate-spin text-orange-600" />
            <span>Searching workspace entities...</span>
          </div>
        ) : totalMatches === 0 ? (
          <div className="py-16 text-center text-stone-400 text-xs">
            {query.trim() ? "No matching records found across your workspace." : "Enter a search query to inspect workspace entities."}
          </div>
        ) : (
          <div className="space-y-6">
            {/* OBLIGATIONS */}
            {(activeCategory === "all" || activeCategory === "obligations") && results.obligations.length > 0 && (
              <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden shadow-sm">
                <div className="px-5 py-3 border-b border-stone-200 bg-stone-50/60 flex items-center justify-between text-xs font-bold text-stone-800">
                  <span className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-orange-600" /> Obligations ({results.obligations.length})
                  </span>
                </div>
                <div className="divide-y divide-stone-100 text-xs">
                  {results.obligations.map((o) => (
                    <div key={o.id} className="p-3.5 flex items-center justify-between hover:bg-stone-50">
                      <div>
                        <div className="font-semibold text-stone-900">{o.action}</div>
                        <div className="text-stone-500 text-[11px] mt-0.5">
                          Owner: {o.owner} • Status: {o.status} • Due: {o.deadline ? new Date(o.deadline).toLocaleDateString() : "None"}
                        </div>
                      </div>
                      <Link href={o.url} className="text-orange-600 hover:text-orange-700 font-medium flex items-center gap-1">
                        <span>View</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* PEOPLE */}
            {(activeCategory === "all" || activeCategory === "people") && results.people.length > 0 && (
              <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden shadow-sm">
                <div className="px-5 py-3 border-b border-stone-200 bg-stone-50/60 flex items-center justify-between text-xs font-bold text-stone-800">
                  <span className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-orange-600" /> People ({results.people.length})
                  </span>
                </div>
                <div className="divide-y divide-stone-100 text-xs">
                  {results.people.map((p) => (
                    <div key={p.id} className="p-3.5 flex items-center justify-between hover:bg-stone-50">
                      <div>
                        <div className="font-semibold text-stone-900">{p.display_name}</div>
                        <div className="text-stone-500 text-[11px] mt-0.5">{p.email}</div>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-stone-100 text-stone-700 border border-stone-200">
                        {p.role}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* DECISIONS */}
            {(activeCategory === "all" || activeCategory === "decisions") && results.decisions.length > 0 && (
              <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden shadow-sm">
                <div className="px-5 py-3 border-b border-stone-200 bg-stone-50/60 flex items-center justify-between text-xs font-bold text-stone-800">
                  <span className="flex items-center gap-2">
                    <Brain className="w-4 h-4 text-orange-600" /> Decision Plans ({results.decisions.length})
                  </span>
                </div>
                <div className="divide-y divide-stone-100 text-xs">
                  {results.decisions.map((d) => (
                    <div key={d.id} className="p-3.5 flex items-center justify-between hover:bg-stone-50">
                      <div>
                        <div className="font-semibold text-stone-900">{d.primary_objective}</div>
                        <div className="text-stone-500 text-[11px] mt-0.5">
                          Status: {d.status} • Urgency: {d.urgency} • Risk: {Math.round((d.overall_risk || 0) * 100)}%
                        </div>
                      </div>
                      <Link href={d.url} className="text-orange-600 hover:text-orange-700 font-medium flex items-center gap-1">
                        <span>Review</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* EVENTS */}
            {(activeCategory === "all" || activeCategory === "events") && results.events.length > 0 && (
              <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden shadow-sm">
                <div className="px-5 py-3 border-b border-stone-200 bg-stone-50/60 flex items-center justify-between text-xs font-bold text-stone-800">
                  <span className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-orange-600" /> Activity Events ({results.events.length})
                  </span>
                </div>
                <div className="divide-y divide-stone-100 text-xs">
                  {results.events.map((ev) => (
                    <div key={ev.id} className="p-3.5 hover:bg-stone-50">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-semibold text-stone-800 text-xs">[{ev.provider.toUpperCase()}]</span>
                        <span className="text-stone-600 text-xs">{ev.sender}</span>
                        <span className="text-stone-400 text-[10px]">• {new Date(ev.received_at).toLocaleTimeString()}</span>
                      </div>
                      <p className="text-stone-700 text-xs">{ev.content_snippet}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="p-8 text-xs text-stone-400">Loading search...</div>}>
      <SearchContent />
    </Suspense>
  );
}
