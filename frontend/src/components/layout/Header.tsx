"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Sparkles, Activity, Search, UploadCloud } from "lucide-react";
import { obligationsApi } from "@/lib/api/obligations";
import { NotificationCenter } from "./NotificationCenter";
import { CsvImportModal } from "../obligations/CsvImportModal";

export const Header: React.FC = () => {
  const router = useRouter();
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [importModalOpen, setImportModalOpen] = useState(false);

  useEffect(() => {
    obligationsApi
      .checkHealth()
      .then(() => setApiOnline(true))
      .catch(() => setApiOnline(false));
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  return (
    <>
      <header className="h-16 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md sticky top-0 z-30 px-6 flex items-center justify-between gap-4">
        {/* Left: Mobile Brand & Search */}
        <div className="flex items-center gap-4 flex-1 max-w-md">
          <div className="md:hidden flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white text-sm">
              OA
            </div>
            <span className="font-bold text-white text-sm">Obligation Agent</span>
          </div>

          <form onSubmit={handleSearch} className="relative w-full hidden sm:block">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search obligations, people, events, decisions..."
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-zinc-700"
            />
          </form>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-3">
          {/* In-App Notifications */}
          <NotificationCenter />

          {/* CSV Import */}
          <button
            onClick={() => setImportModalOpen(true)}
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 border border-zinc-800 hover:border-zinc-700 rounded-lg text-xs font-medium text-zinc-300 hover:text-zinc-100 transition-colors"
            title="Bulk CSV Ingestion"
          >
            <UploadCloud className="w-3.5 h-3.5 text-zinc-400" />
            <span>Import CSV</span>
          </button>

          {/* Backend API status badge */}
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
              apiOnline === true
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                : apiOnline === false
                ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                : "bg-zinc-800 text-zinc-400 border-zinc-700"
            }`}
            title={apiOnline === true ? "FastAPI Backend Connected" : "Backend Disconnected"}
          >
            <Activity className={`w-3 h-3 ${apiOnline ? "text-emerald-400 animate-pulse" : "text-zinc-400"}`} />
            <span className="hidden md:inline">API</span>
            <span>{apiOnline === true ? "Connected" : apiOnline === false ? "Offline" : "Checking..."}</span>
          </div>

          {/* Capture / Analyze Quick Action */}
          <Link
            href="/capture"
            className="inline-flex items-center gap-2 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition-all shadow-md shadow-blue-600/20 active:scale-95"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Analyze Message</span>
          </Link>
        </div>
      </header>

      {/* CSV Import Modal */}
      <CsvImportModal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onSuccess={() => router.refresh()}
      />
    </>
  );
};
