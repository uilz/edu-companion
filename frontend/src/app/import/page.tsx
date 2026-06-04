"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Upload, FileText, Check, X, AlertTriangle, Loader2,
  ChevronRight, Brain, BookOpen, Sparkles,
} from "lucide-react";

interface PreviewQuestion {
  stem: string;
  options?: { label: string; content: string; is_correct?: boolean }[];
  answer: string;
  analysis: string;
  question_type: string;
  confidence: number;
  suggested_node_ids?: string[];
  ai_corrected?: boolean;
  source_line?: number;
}

interface PreviewResult {
  questions: PreviewQuestion[];
  stats: { total: number; high_confidence: number; low_confidence: number };
  source_file?: string;
  suggestions?: { suggested_bank?: string };
}

export default function ImportPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<"text" | "file">("text");
  const [rawText, setRawText] = useState("");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [banks, setBanks] = useState<any[]>([]);
  const [selectedBank, setSelectedBank] = useState("");
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [importResult, setImportResult] = useState<any>(null);
  const [removedIndices, setRemovedIndices] = useState<Set<number>>(new Set());

  // ── 预览 ──
  const handlePreview = async () => {
    if (!rawText.trim()) return;
    setLoading(true);
    setError("");
    setImportResult(null);
    try {
      const res = await fetch("/api/v7/practice/import/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: rawText }),
      });
      if (!res.ok) throw new Error((await res.text()) || "预览失败");
      const data = await res.json();
      setPreview(data);
      setRemovedIndices(new Set());
      // 加载题库列表用于选择
      const banksRes = await fetch("/api/v7/practice/banks");
      const banksData = await banksRes.json();
      setBanks(Array.isArray(banksData) ? banksData : []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // ── 确认导入 ──
  const handleImport = async () => {
    if (!selectedBank || !preview) return;
    setImporting(true);
    setError("");
    try {
      const filtered = preview.questions.filter((_, i) => !removedIndices.has(i));
      const res = await fetch("/api/v7/practice/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bank_id: selectedBank, questions: filtered }),
      });
      if (!res.ok) throw new Error((await res.text()) || "导入失败");
      const data = await res.json();
      setImportResult(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setImporting(false);
    }
  };

  // ── 移除题目 ──
  const toggleRemove = (idx: number) => {
    setRemovedIndices((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const displayQuestions = preview?.questions.filter((_, i) => !removedIndices.has(i)) || [];
  const removedCount = removedIndices.size;

  return (
    <div className="min-h-screen bg-[var(--color-bg)] px-4 py-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => router.back()}
          className="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">← 返回</button>
        <span className="text-[11px] text-[var(--color-text-muted)]">|</span>
        <div className="flex items-center gap-2">
          <Upload size={16} className="text-[var(--color-accent)]" />
          <h1 className="text-base font-bold text-[var(--color-text)]">题库导入</h1>
        </div>
      </div>

      {/* 未预览状态 */}
      {!preview && (
        <>
          {/* 输入方式切换 */}
          <div className="flex gap-2 mb-4">
            <button onClick={() => setTab("text")}
              className={`flex-1 py-2.5 rounded-lg text-sm font-medium border transition-all ${
                tab === "text" ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                : "border-[var(--color-border)]/50 bg-[var(--color-surface)] text-[var(--color-text)]"
              }`}>粘贴文本</button>
            <button onClick={() => setTab("file")}
              className={`flex-1 py-2.5 rounded-lg text-sm font-medium border transition-all ${
                tab === "file" ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                : "border-[var(--color-border)]/50 bg-[var(--color-surface)] text-[var(--color-text)]"
              }`}>上传文件</button>
          </div>

          {tab === "text" ? (
            <>
              <textarea value={rawText} onChange={(e) => setRawText(e.target.value)}
                placeholder="在此粘贴题目文本...&#10;&#10;支持格式:&#10;1. 题干内容&#10;A. 选项A&#10;B. 选项B&#10;C. 选项C&#10;D. 选项D&#10;答案：A&#10;解析：...&#10;&#10;也支持 JSON 格式直接粘贴"
                className="w-full h-48 p-4 rounded-xl border border-[var(--color-border)]/60 bg-[var(--color-surface)] text-[13px] text-[var(--color-text)] resize-none focus:outline-none focus:border-[var(--color-accent)] placeholder:text-[var(--color-text-muted)]/50"
              />
              <button onClick={handlePreview} disabled={!rawText.trim() || loading}
                className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-all">
                {loading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                {loading ? "解析中..." : "解析预览"}
              </button>
            </>
          ) : (
            <div className="text-center py-12 px-6 rounded-xl border-2 border-dashed border-[var(--color-border)]/50">
              <Upload size={32} className="mx-auto text-[var(--color-text-muted)] mb-3" />
              <p className="text-[13px] text-[var(--color-text-muted)] mb-2">上传文件（docx / xlsx / txt / json）</p>
              <p className="text-[10px] text-[var(--color-text-muted)] mb-4">
                文件上传后自动解析为题目列表，支持 word 文档和 Excel 表格
              </p>
              <input ref={fileInputRef} type="file" accept=".docx,.xlsx,.txt,.json"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  setLoading(true);
                  setError("");
                  try {
                    // 用已有上传接口
                    const form = new FormData();
                    form.append("file", file);
                    const uploadRes = await fetch("/api/files/upload", { method: "POST", body: form });
                    if (!uploadRes.ok) throw new Error("上传失败");
                    const uploadData = await uploadRes.json();
                    // 解析
                    const res = await fetch("/api/v7/practice/import/upload", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        file_path: uploadData.storage_path || uploadData.file_path,
                        file_type: file.name.split(".").pop() || "",
                      }),
                    });
                    if (!res.ok) throw new Error((await res.text()) || "解析失败");
                    const data = await res.json();
                    setPreview(data);
                    setRemovedIndices(new Set());
                    const banksRes = await fetch("/api/v7/practice/banks");
                    const banksData = await banksRes.json();
                    setBanks(Array.isArray(banksData) ? banksData : []);
                  } catch (e: any) {
                    setError(e.message);
                  } finally {
                    setLoading(false);
                  }
                }} />
              <button onClick={() => fileInputRef.current?.click()} disabled={loading}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-all">
                {loading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                {loading ? "上传中..." : "选择文件"}
              </button>
            </div>
          )}
        </>
      )}

      {/* 预览结果 */}
      {preview && (
        <>
          {/* 统计 */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="text-[11px] text-[var(--color-text-muted)]">
                共 {preview.stats.total} 题
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-500/10 text-green-600 border border-green-500/30">
                高置信 {preview.stats.high_confidence}
              </span>
              {preview.stats.low_confidence > 0 && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-600 border border-yellow-500/30">
                  需修正 {preview.stats.low_confidence}
                </span>
              )}
            </div>
            <button onClick={() => { setPreview(null); setImportResult(null); }}
              className="text-[10px] text-[var(--color-text-muted)] hover:text-red-500">
              重新导入
            </button>
          </div>

          {/* 题库选择 */}
          <div className="mb-4">
            <p className="text-[10px] text-[var(--color-text-muted)] mb-1.5 font-medium">导入到题库</p>
            <select value={selectedBank} onChange={(e) => setSelectedBank(e.target.value)}
              className="w-full p-2.5 rounded-lg border border-[var(--color-border)]/60 bg-[var(--color-surface)] text-[12px] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-accent)]">
              <option value="">-- 选择题库 --</option>
              {banks.map((b: any) => (
                <option key={b.id} value={b.id}>{b.name} ({b.question_count || 0}题)</option>
              ))}
            </select>
          </div>

          {/* 题目列表 */}
          <div className="space-y-3 mb-6">
            {displayQuestions.map((q, i) => {
              const origIdx = preview.questions.indexOf(q);
              return (
                <div key={origIdx}
                  className={`p-4 rounded-xl border transition-all ${
                    q.confidence >= 0.8
                      ? "border-green-500/20 bg-green-500/[0.02]"
                      : "border-yellow-500/20 bg-yellow-500/[0.02]"
                  }`}>
                  <div className="flex items-start gap-2">
                    <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-[var(--color-surface)] text-[9px] text-[var(--color-text-muted)] border border-[var(--color-border)]">
                      {origIdx + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      {/* 题干 */}
                      <p className="text-[12px] text-[var(--color-text)] leading-relaxed mb-2">{q.stem}</p>
                      {/* 选项 */}
                      {q.options && q.options.length > 0 && (
                        <div className="grid grid-cols-2 gap-1 mb-2">
                          {q.options.map((opt, oi) => (
                            <span key={oi} className="text-[10px] text-[var(--color-text-muted)] px-2 py-0.5 rounded bg-[var(--color-bg)]">
                              {opt.label}. {opt.content}
                            </span>
                          ))}
                        </div>
                      )}
                      {/* 答案/解析 */}
                      <div className="flex items-center gap-3 text-[9px] text-[var(--color-text-muted)]">
                        <span className="text-green-600">答案: {q.answer}</span>
                        {q.analysis && <span className="truncate">解析: {q.analysis.slice(0, 40)}...</span>}
                        {q.ai_corrected && <span className="text-blue-500">AI已修正</span>}
                        <span className={`ml-auto ${q.confidence >= 0.8 ? "text-green-500" : "text-yellow-500"}`}>
                          {Math.round(q.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                    {/* 删除按钮 */}
                    <button onClick={() => toggleRemove(origIdx)}
                      className="flex-shrink-0 p-1 rounded hover:bg-red-500/10 text-[var(--color-text-muted)] hover:text-red-500">
                      <X size={12} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* 操作栏 */}
          <div className="sticky bottom-0 pb-4 bg-[var(--color-bg)]">
            {removedCount > 0 && (
              <p className="text-[10px] text-red-500 mb-2">已移除 {removedCount} 题</p>
            )}
            <div className="flex gap-3">
              <button onClick={() => { setPreview(null); setImportResult(null); }}
                className="flex-1 py-3 rounded-lg border border-[var(--color-border)]/50 text-sm text-[var(--color-text)] hover:bg-[var(--color-surface)]">
                取消
              </button>
              <button onClick={handleImport} disabled={!selectedBank || importing || displayQuestions.length === 0}
                className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50">
                {importing ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                {importing ? "导入中..." : `导入 ${displayQuestions.length} 题`}
              </button>
            </div>
          </div>
        </>
      )}

      {/* 导入结果 */}
      {importResult && (
        <div className="mt-4 p-6 rounded-xl bg-green-500/5 border border-green-500/20 text-center">
          <div className="w-12 h-12 rounded-full bg-green-500/10 flex items-center justify-center mx-auto mb-3">
            <Check size={20} className="text-green-500" />
          </div>
          <h3 className="text-base font-bold text-[var(--color-text)] mb-1">导入完成</h3>
          <p className="text-[11px] text-[var(--color-text-muted)] mb-4">
            成功导入 {importResult.imported} 题
            {importResult.error_count > 0 && `，${importResult.error_count} 题失败`}
          </p>
          {importResult.errors?.length > 0 && (
            <div className="mb-4 text-left max-h-32 overflow-y-auto">
              {importResult.errors.slice(0, 5).map((err: any, i: number) => (
                <p key={i} className="text-[10px] text-red-500">#{err.index}: {err.reason}</p>
              ))}
            </div>
          )}
          <div className="flex gap-3">
            <button onClick={() => { setPreview(null); setImportResult(null); setRawText(""); }}
              className="flex-1 py-3 rounded-lg border border-[var(--color-border)]/50 text-sm text-[var(--color-text)] hover:bg-[var(--color-surface)]">
              继续导入
            </button>
            <button onClick={() => router.push("/practice")}
              className="flex-1 py-3 rounded-lg bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90">
              去练习
            </button>
          </div>
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
          <div className="flex items-center gap-2">
            <AlertTriangle size={14} className="text-red-500" />
            <span className="text-[11px] text-red-600">{error}</span>
          </div>
        </div>
      )}
    </div>
  );
}
