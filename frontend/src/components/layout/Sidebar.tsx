"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Sparkles,
  Layers,
  ShieldCheck,
  ArrowUpRight,
  ArrowDownLeft,
  AlertTriangle,
} from "lucide-react";

interface SidebarProps {
  counts?: {
    youOwe?: number;
    othersOwe?: number;
    atRisk?: number;
  };
}

export const Sidebar: React.FC<SidebarProps> = ({ counts }) => {
  const pathname = usePathname();

  const navItems = [
    {
      name: "Dashboard",
      href: "/",
      icon: LayoutDashboard,
      active: pathname === "/" || pathname === "/dashboard",
    },
    {
      name: "Capture & Analyze",
      href: "/capture",
      icon: Sparkles,
      active: pathname === "/capture",
      badge: "AI Review",
    },
    {
      name: "All Obligations",
      href: "/obligations",
      icon: Layers,
      active: pathname.startsWith("/obligations"),
    },
  ];

  const quickFilters = [
    {
      name: "You Owe",
      href: "/obligations?type=OWED_BY_ME",
      icon: ArrowUpRight,
      color: "text-blue-400",
      count: counts?.youOwe,
    },
    {
      name: "Others Owe You",
      href: "/obligations?type=OWED_TO_ME",
      icon: ArrowDownLeft,
      color: "text-emerald-400",
      count: counts?.othersOwe,
    },
    {
      name: "At Risk",
      href: "/obligations?at_risk=true",
      icon: AlertTriangle,
      color: "text-rose-400",
      count: counts?.atRisk,
    },
  ];

  return (
    <aside className="w-64 shrink-0 border-r border-zinc-800 bg-zinc-950 flex flex-col justify-between hidden md:flex min-h-screen select-none">
      <div className="p-4 space-y-6">
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-2 py-1">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-blue-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20 ring-1 ring-white/20">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight text-white flex items-center gap-1.5">
              Continuity<span className="text-blue-400">Guardian</span>
            </div>
            <div className="text-[11px] text-zinc-400 font-medium">Obligation Intelligence</div>
          </div>
        </div>

        {/* Primary Navigation */}
        <nav className="space-y-1">
          <div className="px-2 py-1 text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
            Workspace
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  item.active
                    ? "bg-zinc-800/80 text-white font-semibold shadow-sm border border-zinc-700/50"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${item.active ? "text-blue-400" : "text-zinc-400"}`} />
                  <span>{item.name}</span>
                </div>
                {item.badge && (
                  <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Obligation Ledgers / Quick Filter */}
        <div className="space-y-1 pt-2">
          <div className="px-2 py-1 text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
            Obligation Feeds
          </div>
          {quickFilters.map((filter) => {
            const Icon = filter.icon;
            return (
              <Link
                key={filter.name}
                href={filter.href}
                className="flex items-center justify-between px-3 py-2 rounded-lg text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${filter.color}`} />
                  <span>{filter.name}</span>
                </div>
                {filter.count !== undefined && filter.count > 0 && (
                  <span className="px-2 py-0.5 text-xs rounded-full bg-zinc-800/80 text-zinc-300 border border-zinc-700/50">
                    {filter.count}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      </div>

      {/* System Status / Phase Info */}
      <div className="p-4 border-t border-zinc-800/80">
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-300">Phase 1: Core Engine</span>
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          </div>
          <p className="text-[11px] text-zinc-400 leading-relaxed">
            Human-in-the-loop obligation extraction, bidirectional modeling & active ledger.
          </p>
        </div>
      </div>
    </aside>
  );
};
