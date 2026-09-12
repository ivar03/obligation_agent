"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ShieldCheck, ArrowRight, Menu, X, Sparkles, LayoutDashboard } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export const PublicNavbar: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user } = useAuth();

  const navLinks = [
    { name: "Problem", href: "#problem" },
    { name: "The Core Insight", href: "#insight" },
    { name: "How It Works", href: "#how-it-works" },
    { name: "Product Intelligence", href: "#intelligence" },
    { name: "Integrations", href: "#integrations" },
  ];

  return (
    <header className="sticky top-0 z-50 bg-white/50 backdrop-blur-md border-b border-stone-200/50 shadow-2xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-9 h-9 rounded-xl bg-orange-600 flex items-center justify-center text-white shadow-sm shadow-orange-500/20 group-hover:bg-orange-700 transition-colors">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div className="flex flex-col">
            <span className="text-base font-bold tracking-tight text-slate-900 leading-tight">
              Obligation<span className="text-orange-600">Agent</span>
            </span>
            <span className="text-[10px] font-medium text-slate-500 tracking-wide">
              Intelligent Workplace Commitments
            </span>
          </div>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-7">
          {navLinks.map((link) => (
            <a
              key={link.name}
              href={link.href}
              className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
            >
              {link.name}
            </a>
          ))}
        </nav>

        {/* Desktop CTA actions */}
        <div className="hidden sm:flex items-center gap-3">
          {user ? (
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-orange-50 border border-orange-200 text-xs font-semibold text-orange-800 hover:bg-orange-100 transition-all"
            >
              <LayoutDashboard className="w-3.5 h-3.5 text-orange-600" />
              <span>Go to Workspace</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className="text-xs font-semibold text-slate-700 hover:text-slate-900 px-3 py-1.5 rounded-lg hover:bg-slate-100 transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/demo"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold shadow-sm shadow-orange-600/20 hover:shadow transition-all"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Try the Demo</span>
              </Link>
            </>
          )}
        </div>

        {/* Mobile menu button */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="md:hidden p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100"
          aria-label="Toggle Navigation Menu"
        >
          {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-stone-200/60 bg-white/70 backdrop-blur-lg px-4 pt-3 pb-5 space-y-3">
          <div className="space-y-1">
            {navLinks.map((link) => (
              <a
                key={link.name}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                {link.name}
              </a>
            ))}
          </div>
          <div className="pt-3 border-t border-slate-100 flex flex-col gap-2">
            <Link
              href="/demo"
              onClick={() => setMobileMenuOpen(false)}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-orange-600 text-white text-xs font-semibold shadow-sm"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Try the Demo</span>
            </Link>
            <Link
              href="/login"
              onClick={() => setMobileMenuOpen(false)}
              className="w-full text-center py-2 px-4 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700"
            >
              Sign In
            </Link>
          </div>
        </div>
      )}
    </header>
  );
};
