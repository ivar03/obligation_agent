"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
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
      <header className="h-16 border-b border-slate-200 bg-white/95 backdrop-blur-md sticky top-0 z-30 px-6 flex items-center justify-between gap-4">
        {/* Left: Mobile Brand & Search */}
        <div className="flex items-center gap-4 flex-1 max-w-md">
          <Link href="/" className="md:hidden flex items-center gap-2">
            <Image
              src="/logo.png"
              alt="Obligation Agent"
              width={241}
              height={61}
              priority
              className="h-10 w-auto object-contain"
            />
          </Link>

          <form onSubmit={handleSearch} className="relative w-full hidden sm:block">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search obligations, owners, events, decisions..."
              className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-8 pr-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-orange-400 focus:ring-2 focus:ring-orange-500/15 transition-all"
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
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 hover:border-slate-300 rounded-xl text-xs font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-50 transition-colors"
            title="Bulk CSV Ingestion"
          >
            <UploadCloud className="w-3.5 h-3.5 text-slate-500" />
            <span>Import CSV</span>
          </button>

          {/* Backend API status badge */}
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
              apiOnline === true
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : apiOnline === false
                ? "bg-rose-50 text-rose-700 border-rose-200"
                : "bg-slate-100 text-slate-600 border-slate-200"
            }`}
            title={apiOnline === true ? "FastAPI Backend Connected" : "Backend Disconnected"}
          >
            <Activity className={`w-3 h-3 ${apiOnline ? "text-emerald-500 animate-pulse" : "text-slate-500"}`} />
            <span className="hidden md:inline text-[11px] font-semibold">API</span>
            <span className="text-[11px] font-medium">{apiOnline === true ? "Connected" : apiOnline === false ? "Offline" : "Checking..."}</span>
          </div>

          {/* Capture / Analyze Quick Action */}
          <Link
            href="/capture"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-orange-600 hover:bg-orange-700 text-white rounded-xl text-xs font-semibold transition-all shadow-sm shadow-orange-600/20 active:scale-95"
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
