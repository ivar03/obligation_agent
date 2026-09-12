"use client";

import React from "react";
import { MessageSquare, Mail, Calendar, Layers, Cpu, CheckCircle2 } from "lucide-react";

export const TrustProofStrip: React.FC = () => {
  const integrations = [
    {
      name: "Slack",
      role: "Conversations & Threads",
      desc: "Zero-latency promise & progress extraction",
      icon: MessageSquare,
      iconColor: "text-[#4A154B]",
      tag: "Live Sync",
    },
    {
      name: "Gmail",
      role: "Email & Deliverables",
      desc: "Formal deliverables, receipts & attachments",
      icon: Mail,
      iconColor: "text-[#EA4335]",
      tag: "OAuth2 Ready",
    },
    {
      name: "Google Calendar",
      role: "Meetings & Horizons",
      desc: "Meeting context & temporal milestone synchronization",
      icon: Calendar,
      iconColor: "text-[#FBBC05]",
      tag: "Temporal Engine",
    },
    {
      name: "Jira Cloud",
      role: "Issue Trackers",
      desc: "Automated issue, blocker & dependency correlation",
      icon: Layers,
      iconColor: "text-[#0052CC]",
      tag: "Bi-directional",
    },
    {
      name: "Google Gemini",
      role: "Cognitive Intelligence",
      desc: "Grounded causal reasoning & semantic structuring",
      icon: Cpu,
      iconColor: "text-orange-600",
      tag: "Gemini 2.5",
    },
  ];

  return (
    <section id="integrations" className="py-12 border-b border-stone-200/80 bg-stone-50/35 backdrop-blur-[1px]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <span className="text-[11px] font-mono font-bold uppercase tracking-widest text-orange-600 block">
              Continuous Multi-Source Ingestion
            </span>
            <h2 className="text-base sm:text-lg font-bold text-stone-900 mt-0.5 text-readable-glow-subtle">
              Zero New Apps to Learn. Native Ingestion Across Your Stack.
            </h2>
          </div>
          <div className="flex items-center gap-2 text-xs text-stone-600 font-medium">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>Cryptographic hash attribution on all ingested events</span>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {integrations.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.name}
                className="p-4 rounded-xl bg-white/85 backdrop-blur-md border border-stone-200/80 hover:border-orange-300 hover:shadow-md transition-all flex flex-col justify-between space-y-3 group"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="w-8 h-8 rounded-lg bg-stone-50 border border-stone-200 flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                    <Icon className={`w-4 h-4 ${item.iconColor}`} />
                  </div>
                  <span className="text-[9px] font-mono font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-stone-100 text-stone-600 border border-stone-200">
                    {item.tag}
                  </span>
                </div>

                <div>
                  <div className="text-sm font-bold text-stone-900 leading-snug">{item.name}</div>
                  <div className="text-[11px] font-medium text-orange-700/90 mt-0.5">{item.role}</div>
                  <p className="text-[11px] text-stone-500 mt-1 leading-snug">{item.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
