"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ShieldCheck, LogIn, Lock, Mail, AlertCircle, Sparkles } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login({ email, password });
      router.push("/");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to sign in. Please check your credentials.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDemoFill = () => {
    setEmail("demo@obligation.local");
    setPassword("demo1234");
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 bg-stone-100/80 backdrop-blur-xl p-8 rounded-2xl border border-stone-200 shadow-2xl shadow-black/50">
        <div className="text-center space-y-3">
          <div className="mx-auto w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600 to-blue-700 flex items-center justify-center shadow-lg shadow-blue-500/20 ring-1 ring-blue-100/20">
            <ShieldCheck className="w-7 h-7 text-stone-950" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-stone-950">
            Sign in to Obligation Agent
          </h2>
          <p className="text-xs text-stone-600">
            Enterprise Reciprocal Commitment & Intelligence Platform
          </p>
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-3 text-rose-400 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-stone-500">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="operator@company.com"
                  className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-stone-50/80 border border-stone-200 text-stone-900 text-sm placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1.5">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-stone-500">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-stone-50/80 border border-stone-200 text-stone-900 text-sm placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-stone-950 text-sm font-semibold shadow-lg shadow-blue-500/25 transition-all disabled:opacity-50"
          >
            {loading ? (
              <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                <LogIn className="w-4 h-4" />
                <span>Sign In</span>
              </>
            )}
          </button>
        </form>

        <div className="pt-2 border-t border-stone-200/80 flex flex-col items-center gap-3">
          <button
            type="button"
            onClick={handleDemoFill}
            className="flex items-center gap-1.5 text-xs text-blue-500 hover:text-blue-600 font-medium transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Use Default Demo Account</span>
          </button>

          <div className="text-xs text-stone-600">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="text-blue-500 hover:text-blue-600 font-medium">
              Create workspace
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
