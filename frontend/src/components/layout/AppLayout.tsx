"use client";

import React, { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { PublicNavbar } from "./PublicNavbar";
import { DemoBanner } from "./DemoBanner";
import { ToastProvider } from "../ui/ToastContext";
import { AuthProvider } from "@/context/AuthContext";
import { obligationsApi } from "@/lib/api/obligations";
import Link from "next/link";
import { ShieldCheck } from "lucide-react";

interface AppLayoutProps {
  children: React.ReactNode;
}

const PUBLIC_ROUTES = ["/", "/demo", "/login", "/register", "/onboarding/accept"];

const AppShell: React.FC<AppLayoutProps> = ({ children }) => {
  const pathname = usePathname();
  const [counts, setCounts] = useState<{ youOwe?: number; othersOwe?: number; atRisk?: number }>({});

  const isPublicRoute = PUBLIC_ROUTES.includes(pathname);

  useEffect(() => {
    if (!isPublicRoute) {
      obligationsApi
        .getDashboardSummary()
        .then((summary) => {
          setCounts({
            youOwe: summary.you_owe_count,
            othersOwe: summary.others_owe_count,
            atRisk: summary.at_risk_count,
          });
        })
        .catch(() => {
          // Ignored if offline or unauthorized
        });
    }
  }, [pathname, isPublicRoute]);

  if (isPublicRoute) {
    return (
      <div className="min-h-screen bg-white text-slate-900 flex flex-col font-sans">
        <PublicNavbar />
        <main className="flex-1 w-full">{children}</main>
        <footer className="border-t border-slate-100 bg-slate-50 py-10 px-4 sm:px-6 lg:px-8">
          <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded-md bg-orange-600 flex items-center justify-center text-white">
                <ShieldCheck className="w-3 h-3 text-white" />
              </div>
              <span className="font-semibold text-slate-700">Obligation Agent</span>
              <span>— Reciprocal Commitment & Accountability OS</span>
            </div>
            <div className="flex items-center gap-6">
              <Link href="/demo" className="text-orange-600 hover:text-orange-700 font-medium">
                Try the Demo
              </Link>
              <Link href="/login" className="hover:text-slate-700">
                Sign In
              </Link>
              <Link href="/register" className="hover:text-slate-700">
                Create Workspace
              </Link>
              <span>Built for high-accountability teams.</span>
            </div>
          </div>
        </footer>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50/50 text-slate-900 antialiased font-sans">
      <Sidebar counts={counts} />
      <div className="flex-1 flex flex-col min-w-0">
        <DemoBanner />
        <Header />
        <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
};

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  return (
    <AuthProvider>
      <ToastProvider>
        <AppShell>{children}</AppShell>
      </ToastProvider>
    </AuthProvider>
  );
};
