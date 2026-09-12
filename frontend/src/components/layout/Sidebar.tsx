"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
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
  Sparkles,
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
      href: "/dashboard",
      icon: LayoutDashboard,
      active: pathname === "/dashboard" || pathname === "/",
    },
    {
      name: "Obligations",
      href: "/obligations",
      icon: Layers,
      active: pathname.startsWith("/obligations"),
    },
    {
      name: "Intelligence",
      href: "/intelligence",
      icon: Brain,
      active: pathname === "/intelligence" || (pathname.startsWith("/intelligence") && !pathname.startsWith("/intelligence/decisions")),
      badge: "AI",
    },
    {
      name: "Reconciliation",
      href: "/reconciliation",
      icon: Scale,
      active: pathname.startsWith("/reconciliation"),
    },
    {
      name: "Activity Center",
      href: "/events",
      icon: Activity,
      active: pathname.startsWith("/events"),
    },
    {
      name: "Decision Center",
      href: "/intelligence/decisions",
      icon: Sparkles,
      active: pathname.startsWith("/intelligence/decisions"),
    },
    {
      name: "Integrations",
      href: "/integrations",
      icon: Radio,
      active: pathname.startsWith("/integrations"),
    },
    {
      name: "Audit & Governance",
      href: "/audit",
      icon: ShieldCheck,
      active: pathname === "/audit" || pathname.startsWith("/operations/audit"),
    },
  ];

  const quickFilters = [
    {
      name: "You Owe",
      href: "/obligations?type=OWED_BY_ME",
      icon: ArrowUpRight,
      color: "text-orange-600",
      count: counts?.youOwe,
    },
    {
      name: "Others Owe You",
      href: "/obligations?type=OWED_TO_ME",
      icon: ArrowDownLeft,
      color: "text-emerald-600",
      count: counts?.othersOwe,
    },
    {
      name: "At Risk",
      href: "/obligations?at_risk=true",
      icon: AlertTriangle,
      color: "text-amber-600",
      count: counts?.atRisk,
    },
  ];

  const getRoleBadgeClass = (role: string) => {
    switch (role) {
      case "OWNER":
        return "bg-orange-100 text-orange-800 border-orange-200";
      case "ADMIN":
        return "bg-slate-100 text-slate-800 border-slate-200";
      case "MEMBER":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      default:
        return "bg-slate-100 text-slate-600 border-slate-200";
    }
  };

  return (
    <aside className="w-64 shrink-0 border-r border-slate-200 bg-white flex flex-col justify-between hidden md:flex min-h-screen select-none">
      <div className="p-4 space-y-5">
        {/* Brand Header */}
        <Link href="/" className="flex items-center gap-3 px-2 py-1 group">
          <div className="w-9 h-9 rounded-xl bg-orange-600 flex items-center justify-center shadow-sm shadow-orange-500/20 group-hover:bg-orange-700 transition-colors">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight text-slate-900 flex items-center gap-1">
              Obligation<span className="text-orange-600">Agent</span>
            </div>
            <div className="text-[10px] text-slate-600 font-medium">Commitment Intelligence</div>
          </div>
        </Link>

        {/* Workspace Switcher */}
        <div className="relative">
          <button
            onClick={() => setWsDropdownOpen(!wsDropdownOpen)}
            className="w-full flex items-center justify-between p-2.5 rounded-xl bg-slate-50 hover:bg-slate-100 border border-slate-200 transition-all text-left group"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-slate-600 group-hover:text-slate-900 shadow-xs">
                <Building2 className="w-4 h-4" />
              </div>
              <div className="truncate">
                <div className="text-xs font-semibold text-slate-800 truncate">
                  {activeWorkspace?.name || "Acme Operations"}
                </div>
                <div className="text-[10px] text-slate-600 flex items-center gap-1 mt-0.5">
                  <span className={`px-1.5 py-0.2 rounded border text-[9px] font-mono font-medium ${getRoleBadgeClass(activeRole)}`}>
                    {activeRole}
                  </span>
                </div>
              </div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-600 shrink-0" />
          </button>

          {wsDropdownOpen && (
            <div className="absolute left-0 right-0 top-full mt-1.5 bg-white border border-slate-200 rounded-xl shadow-xl py-1 z-50 text-xs divide-y divide-slate-100">
              <div className="max-h-48 overflow-y-auto">
                <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-600 uppercase tracking-wider">
                  Workspaces
                </div>
                {workspaces.map((ws) => (
                  <button
                    key={ws.id}
                    onClick={() => {
                      switchWorkspace(ws.id);
                      setWsDropdownOpen(false);
                    }}
                    className={`w-full px-3 py-2 text-left flex items-center justify-between hover:bg-slate-50 transition-colors ${
                      ws.id === activeWorkspace?.id ? "bg-orange-50/70 text-orange-700 font-semibold" : "text-slate-700"
                    }`}
                  >
                    <span className="truncate">{ws.name}</span>
                    {ws.role && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                        {ws.role}
                      </span>
                    )}
                  </button>
                ))}
              </div>
              <div className="p-1">
                <Link
                  href="/demo"
                  onClick={() => setWsDropdownOpen(false)}
                  className="w-full px-2.5 py-1.5 text-left text-orange-600 hover:bg-orange-50 rounded-lg flex items-center gap-2 font-medium"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Demo Workspace (Acme)</span>
                </Link>
                <Link
                  href="/login"
                  onClick={() => setWsDropdownOpen(false)}
                  className="w-full px-2.5 py-1.5 text-left text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-lg flex items-center gap-2"
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
          <div className="px-2 py-1 text-[10px] font-semibold text-slate-600 uppercase tracking-wider">
            Workspace
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center justify-between px-3 py-2.2 rounded-xl text-xs font-medium transition-all ${
                  item.active
                    ? "bg-orange-50 text-orange-700 font-semibold border border-orange-200/80 shadow-xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${item.active ? "text-orange-600" : "text-slate-600"}`} />
                  <span>{item.name}</span>
                </div>
                {item.badge && (
                  <span className="px-1.5 py-0.5 text-[9px] font-bold bg-orange-100 text-orange-700 border border-orange-200 rounded-md">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Quick Feeds */}
        <div className="space-y-1 pt-1">
          <div className="px-2 py-1 text-[10px] font-semibold text-slate-600 uppercase tracking-wider">
            Obligation Feeds
          </div>
          {quickFilters.map((filter) => {
            const Icon = filter.icon;
            return (
              <Link
                key={filter.name}
                href={filter.href}
                className="flex items-center justify-between px-3 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${filter.color}`} />
                  <span>{filter.name}</span>
                </div>
                {filter.count !== undefined && filter.count > 0 && (
                  <span className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                    {filter.count}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      </div>

      {/* User Profile & Identity Footer */}
      <div className="p-3 border-t border-slate-200 space-y-2">
        {user ? (
          <div className="flex items-center justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-orange-100 border border-orange-200 flex items-center justify-center text-orange-700 text-xs font-bold shrink-0">
                {user.display_name?.charAt(0).toUpperCase() || "U"}
              </div>
              <div className="truncate">
                <div className="text-xs font-semibold text-slate-800 truncate">{user.display_name}</div>
                <div className="text-[10px] text-slate-600 truncate">{user.email}</div>
              </div>
            </div>
            <button
              onClick={() => logout()}
              title="Sign Out"
              className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-rose-600 transition-colors shrink-0"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className="flex items-center justify-center gap-2 w-full py-2 px-3 rounded-xl bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold shadow-xs transition-colors"
          >
            <UserIcon className="w-3.5 h-3.5" />
            <span>Sign In / Register</span>
          </Link>
        )}
      </div>
    </aside>
  );
};
