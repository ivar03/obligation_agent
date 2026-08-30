"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  Info,
  ShieldCheck,
} from "lucide-react";
import { ExtractionResponse } from "@/lib/types/obligation";
import { obligationsApi } from "@/lib/api/obligations";
import { ReviewCard } from "@/components/obligations/ReviewCard";
import { useToast } from "@/components/ui/ToastContext";

const SAMPLE_PROMPTS = [
  {
    label: "You Owe (Friday Deadline)",
    text: "Ravi owes Rahul: Send the API documentation by Friday.",
  },
  {
    label: "Others Owe You (Conditional)",
    text: "Professor owes Ravi: Review the project report after Ravi submits it.",
  },
  {
    label: "Conditional & At Risk",
    text: "Ravi owes the client: Send the revised proposal once the pricing numbers are confirmed.",
  },
  {
    label: "Incoming Blocker",
    text: "Rahul owes Ravi: Send the database numbers before Ravi can finish the report.",
  },
  {
    label: "Ambiguous Ownership",
    text: "We should probably send this to the client tomorrow.",
  },
];

export default function CapturePage() {
  const router = useRouter();
  const { toast } = useToast();

  const [inputMessage, setInputMessage] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [extractionResult, setExtractionResult] = useState<ExtractionResponse | null>(null);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim()) return;

    try {
      setAnalyzing(true);
      setExtractionResult(null);
      const result = await obligationsApi.extractCandidate(inputMessage.trim());
      setExtractionResult(result);

      if (!result.detected) {
        toast({
          type: "info",
          title: "No Obligation Detected",
          description: result.reason || "The message did not contain an actionable commitment.",
        });
      } else {
        toast({
          type: "success",
          title: "Candidate Extracted",
          description: "Please review and confirm the structured obligation.",
        });
      }
    } catch (err) {
      toast({
        type: "error",
        title: "Extraction Error",
        description: err instanceof Error ? err.message : "Failed to analyze message.",
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleReset = () => {
    setExtractionResult(null);
    setInputMessage("");
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Title */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-semibold mb-3">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Human-in-the-Loop Extraction Pipeline</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
          Capture & Analyze Obligation
        </h1>
        <p className="text-sm text-zinc-400 mt-1">
          Paste an email, Slack snippet, or meeting note. The AI extracts structured duties, relationships, and deadlines for your review.
        </p>
      </div>

      {/* Input Message Form */}
      <div className="bg-zinc-900/70 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-5">
        <form onSubmit={handleAnalyze} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-2">
              Source Message / Note
            </label>
            <textarea
              rows={4}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Paste communication text here... (e.g. 'I will send the revised architecture doc to Rahul by tomorrow 5pm once the database schema is confirmed')"
              className="w-full p-4 rounded-xl bg-zinc-950 border border-zinc-800 focus:border-blue-500 focus:outline-none text-sm text-zinc-100 placeholder-zinc-400 resize-none transition-colors"
              required
            />
          </div>

          {/* Sample Prompts */}
          <div>
            <div className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">
              Or load sample scenario:
            </div>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_PROMPTS.map((sample, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setInputMessage(sample.text)}
                  className="px-3 py-1.5 rounded-lg text-xs bg-zinc-950 border border-zinc-800 hover:border-zinc-700 text-zinc-300 hover:text-white transition-colors text-left"
                >
                  {sample.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-zinc-800/80">
            <div className="text-xs text-zinc-400 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
              <span>Results are never auto-saved without your explicit confirmation.</span>
            </div>

            <button
              type="submit"
              disabled={analyzing || !inputMessage.trim()}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-all shadow-lg shadow-blue-600/25 active:scale-95 disabled:opacity-50"
            >
              <Sparkles className={`w-4 h-4 ${analyzing ? "animate-spin" : ""}`} />
              <span>{analyzing ? "Analyzing Message..." : "Analyze Message"}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Non-obligation Result */}
      {extractionResult && !extractionResult.detected && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-lg space-y-3 animate-in fade-in">
          <div className="flex items-center gap-2 text-zinc-300 font-semibold text-sm">
            <Info className="w-4 h-4 text-blue-400" />
            <span>No Actionable Obligation Found</span>
          </div>
          <p className="text-xs text-zinc-400 leading-relaxed">
            {extractionResult.reason || "The input message was analyzed and does not appear to contain a concrete commitment or reciprocal duty."}
          </p>
          <div className="pt-2">
            <button
              onClick={handleReset}
              className="px-3 py-1.5 rounded-lg text-xs bg-zinc-800 text-zinc-300 hover:text-white"
            >
              Try Another Text
            </button>
          </div>
        </div>
      )}

      {/* Candidate Review Card */}
      {extractionResult && extractionResult.detected && extractionResult.obligation && (
        <ReviewCard
          candidate={extractionResult.obligation}
          rawText={inputMessage}
          onReject={handleReset}
          onConfirmed={() => router.push("/")}
        />
      )}
    </div>
  );
}
