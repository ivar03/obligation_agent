"use client";

import React, { useState } from "react";
import { Upload, FileSpreadsheet, CheckCircle2, AlertCircle, AlertTriangle, ArrowRight, Loader2, X } from "lucide-react";

interface CsvRowValidation {
  row_index: number;
  is_valid: boolean;
  errors: string[];
  parsed_data?: {
    action: string;
    owner: string;
    beneficiary: string;
    deadline?: string;
    priority: string;
    dependencies: string[];
  };
}

interface PreviewResponse {
  total_rows: number;
  valid_rows_count: number;
  invalid_rows_count: number;
  validation_results: CsvRowValidation[];
  detected_duplicates: string[];
  can_commit: boolean;
}

interface CsvImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const CsvImportModal: React.FC<CsvImportModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [csvText, setCsvText] = useState("");
  const [loading, setLoading] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [skipDuplicates, setSkipDuplicates] = useState(true);

  if (!isOpen) return null;

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      setCsvText(text);
      runPreview(text);
    };
    reader.readAsText(file);
  };

  const runPreview = async (textToPreview: string) => {
    setErrorMsg("");
    if (!textToPreview.trim()) {
      setPreview(null);
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("csv_content", textToPreview);

      const res = await fetch("/api/obligations/import/csv/preview", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to preview CSV.");
      }

      const data: PreviewResponse = await res.json();
      setPreview(data);
    } catch (err: unknown) {
      const error = err as Error;
      setErrorMsg(error.message || "Failed to parse CSV file.");
    } finally {
      setLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!preview) return;
    setCommitting(true);
    setErrorMsg("");
    try {
      const validRows = preview.validation_results
        .filter((r) => r.is_valid && r.parsed_data)
        .map((r) => r.parsed_data);

      const res = await fetch("/api/obligations/import/csv/commit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rows: validRows,
          skip_duplicates: skipDuplicates,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Import failed.");
      }

      onSuccess();
      onClose();
    } catch (err: unknown) {
      const error = err as Error;
      setErrorMsg(error.message || "Failed to commit import.");
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-3xl max-h-[90vh] bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between bg-zinc-950/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center">
              <FileSpreadsheet className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-100">Bulk CSV Ingestion</h2>
              <p className="text-xs text-zinc-400">Import team commitments with validation & duplicate detection</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 text-xs">
          {errorMsg && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Upload Area */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="border-2 border-dashed border-zinc-700 hover:border-blue-500/50 rounded-xl p-6 flex flex-col items-center justify-center text-center cursor-pointer transition-colors bg-zinc-950/30">
              <Upload className="w-6 h-6 text-blue-400 mb-2" />
              <span className="font-medium text-zinc-200">Upload CSV File</span>
              <span className="text-zinc-500 text-[11px] mt-0.5">Click or drag .csv file</span>
              <input type="file" accept=".csv" onChange={handleFileUpload} className="hidden" />
            </label>

            <div className="flex flex-col">
              <label className="text-zinc-400 font-medium mb-1.5">Or Paste Raw CSV Data</label>
              <textarea
                value={csvText}
                onChange={(e) => {
                  setCsvText(e.target.value);
                  runPreview(e.target.value);
                }}
                rows={4}
                placeholder="action,owner,deadline,priority,dependencies&#10;Deploy API,Alice,2026-10-15,HIGH,&#10;Setup Database,Bob,2026-10-10,MEDIUM,"
                className="flex-1 w-full bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 font-mono text-[11px] text-zinc-200 focus:outline-none focus:border-blue-500 resize-none"
              />
            </div>
          </div>

          {/* Preview Table */}
          {loading && (
            <div className="py-8 flex items-center justify-center gap-2 text-zinc-400">
              <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
              <span>Analyzing rows and checking duplicates...</span>
            </div>
          )}

          {preview && !loading && (
            <div className="space-y-4">
              {/* Summary Stats */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-xl bg-zinc-950/50 border border-zinc-800">
                  <div className="text-zinc-500 text-[11px]">Total Rows</div>
                  <div className="text-lg font-bold text-zinc-100 mt-0.5">{preview.total_rows}</div>
                </div>
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                  <div className="text-emerald-400 text-[11px] flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Valid Rows
                  </div>
                  <div className="text-lg font-bold text-emerald-400 mt-0.5">{preview.valid_rows_count}</div>
                </div>
                <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
                  <div className="text-amber-400 text-[11px] flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" /> Issues / Duplicates
                  </div>
                  <div className="text-lg font-bold text-amber-400 mt-0.5">
                    {preview.invalid_rows_count + preview.detected_duplicates.length}
                  </div>
                </div>
              </div>

              {/* Rows List */}
              <div className="border border-zinc-800 rounded-xl overflow-hidden max-h-52 overflow-y-auto">
                <table className="w-full text-left border-collapse">
                  <thead className="bg-zinc-950/80 sticky top-0 text-zinc-400 border-b border-zinc-800 text-[11px]">
                    <tr>
                      <th className="p-2.5">Row</th>
                      <th className="p-2.5">Action</th>
                      <th className="p-2.5">Owner</th>
                      <th className="p-2.5">Deadline</th>
                      <th className="p-2.5">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50">
                    {preview.validation_results.map((row) => (
                      <tr key={row.row_index} className={row.is_valid ? "hover:bg-zinc-800/30" : "bg-rose-500/5"}>
                        <td className="p-2.5 text-zinc-500">#{row.row_index}</td>
                        <td className="p-2.5 font-medium text-zinc-200">{row.parsed_data?.action || "—"}</td>
                        <td className="p-2.5 text-zinc-300">{row.parsed_data?.owner || "—"}</td>
                        <td className="p-2.5 text-zinc-400">{row.parsed_data?.deadline || "—"}</td>
                        <td className="p-2.5">
                          {row.is_valid ? (
                            <span className="inline-flex items-center gap-1 text-emerald-400">
                              <CheckCircle2 className="w-3 h-3" /> Valid
                            </span>
                          ) : (
                            <span className="text-rose-400" title={row.errors.join("; ")}>
                              {row.errors[0]}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Duplicate option */}
              <label className="flex items-center gap-2 text-zinc-300 cursor-pointer pt-1">
                <input
                  type="checkbox"
                  checked={skipDuplicates}
                  onChange={(e) => setSkipDuplicates(e.target.checked)}
                  className="rounded bg-zinc-950 border-zinc-700 text-blue-600 focus:ring-0"
                />
                <span>Skip existing obligations with identical action titles</span>
              </label>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-zinc-800 bg-zinc-950/60 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg border border-zinc-700 hover:bg-zinc-800 text-zinc-300 transition-colors text-xs font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleCommit}
            disabled={!preview?.can_commit || committing}
            className="inline-flex items-center gap-2 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition-all shadow-md shadow-blue-600/20"
          >
            {committing ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Ingesting...</span>
              </>
            ) : (
              <>
                <span>Commit {preview?.valid_rows_count || 0} Valid Obligations</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
