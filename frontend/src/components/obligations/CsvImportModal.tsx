"use client";

import React, { useState } from "react";
import {
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Loader2,
  X,
  Download,
  FileCode,
  Info,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { importExportApi } from "@/lib/api/obligations";

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
    obligation_type?: string;
    description?: string;
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

const SAMPLE_CSV = `action,owner,beneficiary,deadline,priority,obligation_type,description,dependencies
Deliver Q3 Financial Audit Report,alice@company.com,sarah@company.com,2026-09-30,HIGH,OWED_BY_ME,Complete and sign off on Q3 revenue reconciliation,
Deploy Database Migration,bob@company.com,dev-team,2026-09-15,CRITICAL,OWED_BY_ME,Apply schema updates in staging,
Verify Security Compliance,charlie@company.com,Compliance Board,2026-10-15,MEDIUM,OWED_BY_ME,Annual access audit and log review,Deliver Q3 Financial Audit Report
Provide Vendor Security Review,vendor@partner.com,alice@company.com,2026-09-20,MEDIUM,OWED_TO_ME,Third-party SOC2 compliance package,`;

export const CsvImportModal: React.FC<CsvImportModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [csvText, setCsvText] = useState("");
  const [loading, setLoading] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [showFormatGuide, setShowFormatGuide] = useState(false);

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

      const data = await importExportApi.previewCsv<PreviewResponse>(formData);
      setPreview(data);

    } catch (err: unknown) {
      const error = err as Error;
      setErrorMsg(error.message || "Failed to parse CSV file. Please check row structure.");
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

      await importExportApi.commitCsv({
        rows: validRows,
        skip_duplicates: skipDuplicates,
      });

      onSuccess();
      onClose();
    } catch (err: unknown) {
      const error = err as Error;
      setErrorMsg(error.message || "Failed to commit import.");
    } finally {
      setCommitting(false);
    }
  };

  const handleDownloadTemplate = () => {
    const blob = new Blob([SAMPLE_CSV], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "obligations_template.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleLoadSample = () => {
    setCsvText(SAMPLE_CSV);
    runPreview(SAMPLE_CSV);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-3xl max-h-[90vh] bg-stone-100 border border-stone-200 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-stone-200 flex items-center justify-between bg-stone-50/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 text-blue-500 border border-blue-500/30 flex items-center justify-center">
              <FileSpreadsheet className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-stone-900">Bulk CSV Ingestion</h2>
              <p className="text-xs text-stone-600">Import team commitments with validation & duplicate detection</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-stone-600 hover:text-stone-900 hover:bg-stone-200 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Template & Helper Bar */}
          <div className="bg-stone-200/60 border border-stone-300/60 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2 text-stone-700">
              <Info className="w-4 h-4 text-blue-500 shrink-0" />
              <span>Format: <code className="bg-stone-100 px-1.5 py-0.5 rounded text-blue-600">action, owner, beneficiary, deadline, priority...</code></span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowFormatGuide(!showFormatGuide)}
                className="px-2.5 py-1.5 bg-stone-200 hover:bg-stone-300 border border-stone-400 rounded-lg text-stone-800 font-medium flex items-center gap-1.5 transition-colors"
              >
                <span>Format Guide</span>
                {showFormatGuide ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
              <button
                type="button"
                onClick={handleLoadSample}
                className="px-2.5 py-1.5 bg-indigo-950/60 hover:bg-indigo-900/80 border border-blue-600/30 rounded-lg text-blue-600 font-medium flex items-center gap-1.5 transition-colors"
              >
                <FileCode className="w-3.5 h-3.5" />
                <span>Load Sample</span>
              </button>
              <button
                type="button"
                onClick={handleDownloadTemplate}
                className="px-2.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-stone-950 rounded-lg font-medium flex items-center gap-1.5 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download Template</span>
              </button>
            </div>
          </div>

          {/* Expandable Format Guide */}
          {showFormatGuide && (
            <div className="bg-stone-50/80 border border-stone-200 rounded-xl p-4 text-xs space-y-2.5">
              <h4 className="font-semibold text-stone-800">Required & Optional CSV Columns</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-stone-700">
                <div className="p-2 bg-stone-100 rounded border border-stone-200">
                  <span className="font-mono text-emerald-400 font-semibold">action</span> <span className="text-rose-400 font-bold">*Required</span>
                  <p className="text-[11px] text-stone-600">Actionable obligation commitment description.</p>
                </div>
                <div className="p-2 bg-stone-100 rounded border border-stone-200">
                  <span className="font-mono text-emerald-400 font-semibold">owner</span> <span className="text-rose-400 font-bold">*Required</span>
                  <p className="text-[11px] text-stone-600">Owner email address or assignee identifier.</p>
                </div>
                <div className="p-2 bg-stone-100 rounded border border-stone-200">
                  <span className="font-mono text-blue-600 font-semibold">beneficiary</span> <span className="text-stone-500">Optional (default: Company)</span>
                  <p className="text-[11px] text-stone-600">Recipient or stakeholder name.</p>
                </div>
                <div className="p-2 bg-stone-100 rounded border border-stone-200">
                  <span className="font-mono text-blue-600 font-semibold">deadline</span> <span className="text-stone-500">Optional</span>
                  <p className="text-[11px] text-stone-600">Format: <code className="text-stone-700">YYYY-MM-DD</code></p>
                </div>
                <div className="p-2 bg-stone-100 rounded border border-stone-200">
                  <span className="font-mono text-blue-600 font-semibold">priority</span> <span className="text-stone-500">Optional (default: MEDIUM)</span>
                  <p className="text-[11px] text-stone-600">Allowed: <code className="text-stone-700">LOW, MEDIUM, HIGH, CRITICAL</code></p>
                </div>
                <div className="p-2 bg-stone-100 rounded border border-stone-200">
                  <span className="font-mono text-blue-600 font-semibold">dependencies</span> <span className="text-stone-500">Optional</span>
                  <p className="text-[11px] text-stone-600">Comma-separated matching actions for prerequisites.</p>
                </div>
              </div>
            </div>
          )}

          {errorMsg && (
            <div className="p-3 bg-rose-950/40 border border-rose-500/30 rounded-xl text-rose-300 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Upload and Text Area */}
          <div className="grid grid-cols-1 gap-4">
            <label className="border-2 border-dashed border-stone-300 hover:border-blue-500/50 bg-stone-50/40 hover:bg-stone-50/80 rounded-xl p-4 flex flex-col items-center justify-center cursor-pointer transition-colors text-center">
              <Upload className="w-5 h-5 text-stone-600 mb-1.5" />
              <span className="font-medium text-xs text-stone-800">Click or drag .csv file to upload</span>
              <input type="file" accept=".csv,text/csv" onChange={handleFileUpload} className="hidden" />
            </label>

            <div>
              <label className="block text-xs font-semibold text-stone-700 mb-1.5">Or Paste Raw CSV Data</label>
              <textarea
                value={csvText}
                onChange={(e) => {
                  setCsvText(e.target.value);
                  runPreview(e.target.value);
                }}
                placeholder="action,owner,beneficiary,deadline,priority,obligation_type..."
                rows={5}
                className="w-full bg-stone-50 border border-stone-200 rounded-xl p-3 text-xs font-mono text-stone-800 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          {/* Loading Indicator */}
          {loading && (
            <div className="flex items-center justify-center py-4 text-xs text-stone-600 gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
              <span>Validating CSV rows...</span>
            </div>
          )}

          {/* Preview Results */}
          {preview && !loading && (
            <div className="space-y-4">
              <div className="flex items-center justify-between bg-stone-50 border border-stone-200 rounded-xl p-3.5 text-xs">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>{preview.valid_rows_count} Valid</span>
                  </div>
                  {preview.invalid_rows_count > 0 && (
                    <div className="flex items-center gap-1.5 text-rose-400 font-medium">
                      <AlertCircle className="w-4 h-4" />
                      <span>{preview.invalid_rows_count} Invalid</span>
                    </div>
                  )}
                  {preview.detected_duplicates.length > 0 && (
                    <div className="flex items-center gap-1.5 text-amber-400 font-medium">
                      <AlertTriangle className="w-4 h-4" />
                      <span>{preview.detected_duplicates.length} Duplicate(s)</span>
                    </div>
                  )}
                </div>
                <label className="flex items-center gap-2 cursor-pointer text-stone-700">
                  <input
                    type="checkbox"
                    checked={skipDuplicates}
                    onChange={(e) => setSkipDuplicates(e.target.checked)}
                    className="rounded border-stone-300 bg-stone-200 text-blue-600 focus:ring-0"
                  />
                  <span>Skip Duplicate Commitments</span>
                </label>
              </div>

              {/* Rows Table */}
              <div className="border border-stone-200 rounded-xl overflow-hidden max-h-60 overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-stone-50/80 border-b border-stone-200 sticky top-0">
                    <tr>
                      <th className="py-2.5 px-3 font-semibold text-stone-600 w-12">Row</th>
                      <th className="py-2.5 px-3 font-semibold text-stone-600">Action</th>
                      <th className="py-2.5 px-3 font-semibold text-stone-600">Owner</th>
                      <th className="py-2.5 px-3 font-semibold text-stone-600">Deadline</th>
                      <th className="py-2.5 px-3 font-semibold text-stone-600">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-200/50 bg-stone-100/40">
                    {preview.validation_results.map((res) => (
                      <tr key={res.row_index} className={res.is_valid ? "" : "bg-rose-950/20"}>
                        <td className="py-2 px-3 font-mono text-stone-500">{res.row_index}</td>
                        <td className="py-2 px-3 text-stone-800">
                          {res.parsed_data?.action || <span className="text-rose-400 italic">Empty Action</span>}
                          {res.errors.length > 0 && (
                            <div className="text-[11px] text-rose-400 mt-0.5 font-sans">
                              {res.errors.join(", ")}
                            </div>
                          )}
                        </td>
                        <td className="py-2 px-3 text-stone-700 font-mono text-[11px]">
                          {res.parsed_data?.owner || "-"}
                        </td>
                        <td className="py-2 px-3 text-stone-600">
                          {res.parsed_data?.deadline || "-"}
                        </td>
                        <td className="py-2 px-3">
                          {res.is_valid ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              Ready
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
                              Invalid
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-stone-200 flex items-center justify-between bg-stone-50/60">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-stone-700 hover:text-stone-900 hover:bg-stone-200 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleCommit}
            disabled={!preview?.can_commit || committing || preview.valid_rows_count === 0}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-stone-950 text-xs font-semibold rounded-lg shadow-sm transition-colors flex items-center gap-2"
          >
            {committing ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Ingesting Obligations...</span>
              </>
            ) : (
              <>
                <span>Commit {preview?.valid_rows_count || 0} Obligations</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
