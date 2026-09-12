"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Building2, Users, Radio, Bell, Shield } from "lucide-react";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const tabs = [
    { name: "Workspace", href: "/settings/workspace", icon: Building2 },
    { name: "Members & Roles", href: "/settings/members", icon: Users },
    { name: "Integrations", href: "/settings/integrations", icon: Radio },
    { name: "Notifications", href: "/settings/notifications", icon: Bell },
    { name: "Security & Backup", href: "/settings/security", icon: Shield },
  ];

  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-in fade-in duration-200">
      <div>
        <h1 className="text-xl font-bold text-stone-900">Workspace Settings</h1>
        <p className="text-xs text-stone-600 mt-1">Manage organization policies, team access, and operational boundaries.</p>
      </div>

      {/* Tabs */}
      <div className="border-b border-stone-200 flex items-center gap-1 overflow-x-auto">
        {tabs.map((t) => {
          const Icon = t.icon;
          const isActive = pathname === t.href;
          return (
            <Link
              key={t.href}
              href={t.href}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors shrink-0 ${
                isActive
                  ? "border-orange-500 text-orange-600 font-semibold"
                  : "border-transparent text-stone-600 hover:text-stone-800 hover:border-stone-300"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{t.name}</span>
            </Link>
          );
        })}
      </div>

      <div>{children}</div>
    </div>
  );
}
