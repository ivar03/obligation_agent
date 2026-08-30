"use client";

import React, { useState } from "react";
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
  Activity,
  Scale,
  Radio,
  Brain,
  ChevronDown,
  Building2,
  Plus,
  LogOut,
  User as UserIcon,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

interface SidebarProps {
  counts?: {
    youOwe?: number;
    othersOwe?: number;
    atRisk?: number;
  };
}

export const Sidebar: React.FC<SidebarProps> = ({ counts }) => {
  const pathname = usePathname();
  const { user, workspaces, activeWorkspace, activeRole, switchWorkspace, logout } = useAuth();
  const [wsDropdownOpen, setWsDropdownOpen] = useState(false);

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
    {
      name: "Reconciliation",
      href: "/reconciliation",
      icon: Scale,
      active: pathname.startsWith("/reconciliation"),
      badge: "Phase 11",
    },
    {
      name: "Intelligence & Predictions",
      href: "/intelligence",
      icon: Brain,
      active: pathname.startsWith("/intelligence"),
      badge: "Phase 12",
    },
    {
      name: "Activity Center",
      href: "/events",
      icon: Activity,
      active: pathname.startsWith("/events"),
      badge: "Phase 7",
    },
    {
      name: "Integrations",
      href: "/integrations",
      icon: Radio,
      active: pathname.startsWith("/integrations"),
      badge: "Phase 8",
    },
    {
      name: "Governance & Audit",
      href: "/audit",
      icon: ShieldCheck,
      active: pathname.startsWith("/audit"),
      badge: "Phase 15",
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

  const getRoleBadgeClass = (role: string) => {
    switch (role) {
      case "OWNER":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      case "ADMIN":
        return "bg-blue-500/10 text-blue-400 border-blue-500/30";
      case "MEMBER":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "VIEWER":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      default:
        return "bg-zinc-800 text-zinc-400 border-zinc-700";
    }
  };

  return (
    <aside className="w-64 shrink-0 border-r border-zinc-800 bg-zinc-950 flex flex-col justify-between hidden md:flex min-h-screen select-none">
      <div className="p-4 space-y-5">
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-2 py-1">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-blue-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20 ring-1 ring-white/20">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight text-white flex items-center gap-1.5">
              Obligation<span className="text-blue-400">Agent</span>
            </div>
            <div className="text-[11px] text-zinc-400 font-medium">Reciprocal Commitment OS</div>
          </div>
        </div>

        {/* Phase 14: Workspace Switcher */}
        <div className="relative">
          <button
            onClick={() => setWsDropdownOpen(!wsDropdownOpen)}
            className="w-full flex items-center justify-between p-2.5 rounded-lg bg-zinc-900/80 hover:bg-zinc-900 border border-zinc-800/80 hover:border-zinc-700 transition-all text-left group"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-6 h-6 rounded bg-zinc-800 flex items-center justify-center text-zinc-400 group-hover:text-zinc-200">
                <Building2 className="w-3.5 h-3.5" />
              </div>
              <div className="truncate">
                <div className="text-xs font-semibold text-zinc-200 truncate">
                  {activeWorkspace?.name || "Select Workspace"}
                </div>
                <div className="text-[10px] text-zinc-400 flex items-center gap-1">
                  <span className={`px-1 rounded border text-[9px] font-mono font-medium ${getRoleBadgeClass(activeRole)}`}>
                    {activeRole}
                  </span>
                </div>
              </div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-zinc-500 group-hover:text-zinc-300 shrink-0" />
          </button>

          {wsDropdownOpen && (
            <div className="absolute left-0 right-0 top-full mt-1.5 bg-zinc-900 border border-zinc-800 rounded-lg shadow-2xl py-1 z-50 text-xs divide-y divide-zinc-800/60">
              <div className="max-h-48 overflow-y-auto">
                <div className="px-3 py-1.5 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                  Workspaces
                </div>
                {workspaces.map((ws) => (
                  <button
                    key={ws.id}
                    onClick={() => {
                      switchWorkspace(ws.id);
                      setWsDropdownOpen(false);
                    }}
                    className={`w-full px-3 py-2 text-left flex items-center justify-between hover:bg-zinc-800/60 transition-colors ${
                      ws.id === activeWorkspace?.id ? "bg-blue-600/10 text-blue-400 font-medium" : "text-zinc-300"
                    }`}
                  >
                    <span className="truncate">{ws.name}</span>
                    {ws.role && (
                      <span className="text-[9px] px-1 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700/50">
                        {ws.role}
                      </span>
                    )}
                  </button>
                ))}
              </div>
              <div className="p-1">
                <Link
                  href="/login"
                  onClick={() => setWsDropdownOpen(false)}
                  className="w-full px-2.5 py-1.5 text-left text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40 rounded flex items-center gap-2"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Switch Account / Sign In</span>
                </Link>
              </div>
            </div>
          )}
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

      {/* Phase 14: User Profile & Identity Footer */}
      <div className="p-3 border-t border-zinc-800/80 space-y-2">
        {user ? (
          <div className="flex items-center justify-between p-2 rounded-lg bg-zinc-900/60 border border-zinc-800/80">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white text-xs font-bold">
                {user.display_name?.charAt(0).toUpperCase() || "U"}
              </div>
              <div className="truncate">
                <div className="text-xs font-medium text-zinc-200 truncate">{user.display_name}</div>
                <div className="text-[10px] text-zinc-400 truncate">{user.email}</div>
              </div>
            </div>
            <button
              onClick={() => logout()}
              title="Sign Out"
              className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400 hover:text-rose-400 transition-colors shrink-0"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className="flex items-center justify-center gap-2 w-full py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow transition-colors"
          >
            <UserIcon className="w-3.5 h-3.5" />
            <span>Sign In / Register</span>
          </Link>
        )}
      </div>
    </aside>
  );
};
