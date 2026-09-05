"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { ToastProvider } from "../ui/ToastContext";
import { AuthProvider } from "@/context/AuthContext";
import { obligationsApi } from "@/lib/api/obligations";

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const [counts, setCounts] = useState<{ youOwe?: number; othersOwe?: number; atRisk?: number }>({});

  useEffect(() => {
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
        // Ignored if offline
      });
  }, []);

  return (
    <AuthProvider>
      <ToastProvider>
        <div className="flex min-h-screen bg-stone-50 text-stone-900 antialiased selection:bg-blue-200 selection:text-blue-950 font-sans">
          <Sidebar counts={counts} />
          <div className="flex-1 flex flex-col min-w-0">
            <Header />
            <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">{children}</main>
          </div>
        </div>
      </ToastProvider>
    </AuthProvider>
  );
};

