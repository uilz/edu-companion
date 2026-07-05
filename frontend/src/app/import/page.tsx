"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { authedFetch } from "@/lib/api/api";
import {
  Upload, FileText, Check, X, AlertTriangle, Loader2,
  ChevronRight, Brain, BookOpen, Sparkles, Edit3, Save,
  Plus, Download, RotateCcw, ArrowLeft, History,
  GripVertical,
} from "lucide-react";
import QuestionStem from "@/components/practice/components/QuestionStem";
import { FileDropZone } from "@/lib/dnd/FileDropZone";

// ── 类型 ──

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

interface ImportHistoryItem {
  id: string;
  bank_id: string;
  bank_name?: string;
  question_count: number;
  created_at: string;
  source_file?: string;
}

// ── 常量 ──

const CORRECT_LETTERS = new Set<string>();

const TYPE_LABELS: Record<string, string> = {
  single: "单选", multiple: "多选", judge: "判断", fill: "填空", essay: "简答",
};

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
  const [showImportHistory, setShowImportHistory] = useState(false);
  const [importHistory, setImportHistory] = useState<ImportHistoryItem[]>([]);

  // 编辑状态
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<PreviewQuestion | null>(null);

  // 新建题库
  const [showNewBank, setShowNewBank] = useState(false);
  const [newBankName, setNewBankName] = useState("");
  const [newBankDesc, setNewBankDesc] = useState("");
  const [creatingBank, setCreatingBank] = useState(false);

  // 修正中
  const [correctingAll, setCorrectingAll] = useState(false);

  // 读取编辑中的题目的正确答案字母集合
  useEffect(() => {
    CORRECT_LETTERS.clear();
    if (editForm?.options) {
      editForm.options.forEach((o) => {
        if (o.is_correct) CORRECT_LETTERS.add(o.label);
      });
    }
  }, [editForm]);

  // ── 预览 ──
  const handlePreview = async () => {
    if (!rawText.trim()) return;
    setLoading(true);
    setError("");
    setImportResult(null);
    try {
      const res = await authedFetch("/api/practice/import/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: rawText }),
      });
      if (!res.ok) throw new Error((await res.text()) || "预览失败");
      const data = await res.json();
      setPreview(data);
      await loadBanks();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const loadBanks = async () => {
    try {
      const res = await authedFetch("/api/practice/banks");
      const data = await res.json();
      setBanks(Array.isArray(data) ? data : []);
    } catch { setBanks([]); }
  };

  const loadImportHistory = async () => {
    try {
      const res = await authedFetch("/api/practice/import/history?limit=10");
      const data = await res.json();
      setImportHistory(data?.items || data || []);
    } catch { setImportHistory([]); }
  };

  // ── 文件上传 ──
  const handleFileSelect = async (file: File) => {
    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const uploadRes = await authedFetch("/api/files/upload", { method: "POST", body: form });
      if (!uploadRes.ok) throw new Error("上传失败");
      const uploadData = await uploadRes.json();
      const res = await authedFetch("/api/practice/import/upload", {
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
      await loadBanks();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // ── 新建题库 ──
  const handleCreateBank = async () => {
    if (!newBankName.trim()) return;
    setCreatingBank(true);
    try {
      const res = await authedFetch("/api/practice/banks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newBankName, description: newBankDesc }),
      });
      if (!res.ok) throw new Error("创建失败");
      const bank = await res.json();
      setSelectedBank(bank.id);
      setNewBankName("");
      setNewBankDesc("");
      setShowNewBank(false);
      await loadBanks();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCreatingBank(false);
    }
  };

  // ── 导入 ──
  const handleImport = async () => {
    if (!selectedBank || !preview) return;
    setImporting(true);
    setError("");
    try {
      const filtered = preview.questions.filter((_, i) => !removedIndices.has(i));
      const res = await authedFetch("/api/practice/import/confirm", {
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

  // ── AI 全部修正 ──
  const handleAiCorrectAll = async () => {
    if (!preview) return;
    setCorrectingAll(true);
    setError("");
    try {
      const res = await authedFetch("/api/practice/import/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: rawText }),
      });
      if (!res.ok) throw new Error((await res.text()) || "修正失败");
      const data = await res.json();
      setPreview(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCorrectingAll(false);
    }
  };

  // ── 删除/编辑 ──
  const [removedIndices, setRemovedIndices] = useState<Set<number>>(new Set());
  const toggleRemove = (idx: number) => {
    setRemovedIndices((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  // ── 内联编辑 ──
  const startEdit = (idx: number) => {
    const origIdx = [...preview!.questions].findIndex((q, i) =>
      !removedIndices.has(i) && [...preview!.questions].filter((_, j) => !removedIndices.has(j))[idx] === q
    );
    const q = preview!.questions[origIdx >= 0 ? origIdx : idx];
    setEditingIdx(idx);
    setEditForm(JSON.parse(JSON.stringify(q)));
  };

  const saveEdit = () => {
    if (!editForm || editingIdx === null) return;
    const displayQuestions = preview!.questions.filter((_, i) => !removedIndices.has(i));
    const displayedQ = displayQuestions[editingIdx];
    const origIdx = preview!.questions.indexOf(displayedQ);
    if (origIdx < 0) return;
    const updated = [...preview!.questions];
    updated[origIdx] = { ...editForm };
    setPreview({ ...preview!, questions: updated });
    setEditingIdx(null);
    setEditForm(null);
  };

  const cancelEdit = () => {
    setEditingIdx(null);
    setEditForm(null);
  };

  const toggleOptionCorrect = (oi: number) => {
    if (!editForm?.options) return;
    const opts = [...editForm.options];
    opts[oi] = { ...opts[oi], is_correct: !opts[oi].is_correct };
    // 单选时只能有一个正确
    if (editForm.question_type === "single" && opts[oi].is_correct) {
      for (let i = 0; i < opts.length; i++) {
        if (i !== oi) opts[i] = { ...opts[i], is_correct: false };
      }
    }
    // 自动更新答案
    const correctLetters = opts.filter((o) => o.is_correct).map((o) => o.label);
    setEditForm({ ...editForm, options: opts, answer: correctLetters.join("") });
  };

  const displayQuestions = preview?.questions.filter((_, i) => !removedIndices.has(i)) || [];
  const removedCount = removedIndices.size;

  return (
    <div className="min-h-screen bg-[var(--color-bg)] px-4 py-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button onClick={() => router.back()}
            className="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">← 返回</button>
          <span className="text-[11px] text-[var(--color-text-muted)]">|</span>
          <div className="flex items-center gap-2">
            <Upload size={16} className="text-[var(--color-accent)]" />
            <h1 className="text-base font-bold text-[var(--color-text)]">题库导入</h1>
          </div>
        </div>
        <button onClick={() => { setShowImportHistory(!showImportHistory); if (!showImportHistory) loadImportHistory(); }}
          className="flex items-center gap-1 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          <History size={12} />
          导入历史
        </button>
      </div>

      {/* 导入历史面板 */}
      {showImportHistory && (
        <div className="mb-6 p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
          <h3 className="text-[11px] font-medium text-[var(--color-text)] mb-3">最近导入记录</h3>
          {importHistory.length === 0 ? (
            <p className="text-[10px] text-[var(--color-text-muted)]">暂无导入记录</p>
          ) : (
            <div className="space-y-2">
              {importHistory.map((h: any) => (
                <div key={h.id} className="flex items-center justify-between text-[10px]">
                  <span className="text-[var(--color-text)]">{(h.bank_name || h.bank_id).slice(0, 30)}</span>
                  <span className="text-[var(--color-text-muted)]">
                    {h.question_count} 题 · {h.created_at?.slice(0, 10)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

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
                placeholder='在此粘贴题目文本...

支持格式:
1. 题干内容
A. 选项A
B. 选项B
C. 选项C
D. 选项D
答案：A
解析：...

也支持 JSON 格式直接粘贴'
                className="w-full h-48 p-4 rounded-xl border border-[var(--color-border)]/60 bg-[var(--color-surface)] text-[13px] text-[var(--color-text)] resize-none focus:outline-none focus:border-[var(--color-accent)] placeholder:text-[var(--color-text-muted)]/50"
              />
              <div className="flex gap-2 mt-3">
                <button onClick={handlePreview} disabled={!rawText.trim() || loading}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-all">
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                  {loading ? "解析中..." : "解析预览"}
                </button>
                <button onClick={() => {
                  setRawText(`1. 一元二次方程 $ax^2+bx+c=0$ (a≠0) 的求根公式是？
A. $x=\\frac{-b\\pm\\sqrt{b^2-4ac}}{2a}$
B. $x=\\frac{b\\pm\\sqrt{b^2-4ac}}{2a}$
C. $x=\\frac{-b\\pm\\sqrt{4ac-b^2}}{2a}$
D. $x=\\frac{-b\\pm\\sqrt{b^2-4ac}}{a}$
答案：A
解析：根据韦达定理和配方法推导可得求根公式。`);
                  setTab("text");
                }}
                  className="px-3 py-3 rounded-lg border border-[var(--color-border)]/50 text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-all whitespace-nowrap">
                  示例
                </button>
              </div>
            </>
          ) : (
            <>
              {/* 文件上传拖拽区 (Task #89 改用 @dnd-kit FileDropZone) */}
              <FileDropZone
                onFiles={(files) => {
                  const file = files[0];
                  if (file) handleFileSelect(file);
                }}
                onClick={() => fileInputRef.current?.click()}
                className="text-center py-12 px-6 rounded-xl border-2 border-dashed transition-all cursor-pointer border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30"
                activeClassName="border-[var(--color-accent)] bg-[var(--color-accent)]/5"
              >
                <input ref={fileInputRef} type="file" accept=".docx,.xlsx,.txt,.json,.pdf"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFileSelect(file);
                  }} />
                <Upload size={32} className="mx-auto mb-3 transition-colors text-[var(--color-text-muted)]" />
                <p className="text-[13px] text-[var(--color-text)] mb-2">
                  拖拽文件到此处或点击选择
                </p>
                <p className="text-[10px] text-[var(--color-text-muted)] mb-4">
                  支持 docx / xlsx / txt / json / pdf，自动解析为题目
                </p>
                <div className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 transition-all">
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                  {loading ? "上传中..." : "选择文件"}
                </div>
              </FileDropZone>
              {/* 模板下载 */}
              <div className="mt-3 flex items-center justify-center gap-4 text-[10px] text-[var(--color-text-muted)]">
                <a href="#" onClick={(e) => {
                  e.preventDefault();
                  const tmpl = `[
  {
    "stem": "题干内容",
    "options": [
      {"label": "A", "content": "选项A", "is_correct": true},
      {"label": "B", "content": "选项B", "is_correct": false},
      {"label": "C", "content": "选项C", "is_correct": false},
      {"label": "D", "content": "选项D", "is_correct": false}
    ],
    "answer": ["A"],
    "analysis": "解析内容",
    "question_type": "single"
  }
]`;
                  const blob = new Blob([tmpl], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url; a.download = "导入模板.json"; a.click();
                  URL.revokeObjectURL(url);
                }} className="hover:text-[var(--color-text)] underline">
                  <Download size={10} /> 下载 JSON 模板
                </a>
                <span>|</span>
                <span>docx 支持富文本题目（带公式/图片）</span>
              </div>
            </>
          )}
        </>
      )}

      {/* 预览结果 */}
      {preview && (
        <>
          {/* 统计栏 */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3 flex-wrap">
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
              {removedCount > 0 && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-600 border border-red-500/30">
                  已移除 {removedCount}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {rawText.trim() && (
                <button onClick={handleAiCorrectAll} disabled={correctingAll}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-[var(--color-border)]/50 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]">
                  {correctingAll ? <Loader2 size={10} className="animate-spin" /> : <RotateCcw size={10} />}
                  全部修正
                </button>
              )}
              <button onClick={() => { setPreview(null); setImportResult(null); }}
                className="text-[10px] text-[var(--color-text-muted)] hover:text-red-500">
                重新导入
              </button>
            </div>
          </div>

          {/* 题库选择 + 新建 */}
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-1.5">
              <p className="text-[10px] text-[var(--color-text-muted)] font-medium">导入到题库</p>
              <button onClick={() => setShowNewBank(!showNewBank)}
                className="flex items-center gap-0.5 text-[10px] text-[var(--color-accent)] hover:underline">
                <Plus size={10} /> 新建
              </button>
            </div>
            {showNewBank && (
              <div className="mb-2 p-3 rounded-lg border border-[var(--color-accent)]/30 bg-[var(--color-accent)]/[0.02] space-y-2">
                <input value={newBankName} onChange={(e) => setNewBankName(e.target.value)}
                  placeholder="题库名称（必填）"
                  className="w-full p-2 rounded-lg border border-[var(--color-border)]/60 bg-[var(--color-surface)] text-[12px] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-accent)]"
                />
                <input value={newBankDesc} onChange={(e) => setNewBankDesc(e.target.value)}
                  placeholder="题库描述（选填）"
                  className="w-full p-2 rounded-lg border border-[var(--color-border)]/60 bg-[var(--color-surface)] text-[12px] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-accent)]"
                />
                <div className="flex gap-2">
                  <button onClick={() => setShowNewBank(false)}
                    className="flex-1 py-2 rounded-lg border border-[var(--color-border)]/50 text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                    取消
                  </button>
                  <button onClick={handleCreateBank} disabled={!newBankName.trim() || creatingBank}
                    className="flex-1 flex items-center justify-center gap-1 py-2 rounded-lg bg-[var(--color-accent)] text-white text-[11px] font-medium hover:opacity-90 disabled:opacity-50">
                    {creatingBank ? <Loader2 size={10} className="animate-spin" /> : <Check size={10} />}
                    创建并选择
                  </button>
                </div>
              </div>
            )}
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
              const isEditing = editingIdx === i;

              if (isEditing && editForm) {
                return (
                  <EditCard
                    key={origIdx}
                    form={editForm}
                    onChange={setEditForm}
                    onSave={saveEdit}
                    onCancel={cancelEdit}
                    onToggleCorrect={toggleOptionCorrect}
                  />
                );
              }

              // 计算正确答案字母
              const answerLetters = new Set(
                (q.answer || "").toUpperCase().split("").filter((ch) => ch >= "A" && ch <= "Z")
              );

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
                      <QuestionStem stem={q.stem} className="text-[12px] text-[var(--color-text)] leading-relaxed mb-2" />

                      {/* 题型标签 */}
                      <span className="inline-block text-[9px] px-1.5 py-0.5 rounded bg-[var(--color-surface)] text-[var(--color-text-muted)] border border-[var(--color-border)]/50 mb-2">
                        {TYPE_LABELS[q.question_type] || q.question_type}
                      </span>

                      {/* 选项 - 正确答案绿色高亮 */}
                      {q.options && q.options.length > 0 && (
                        <div className="grid grid-cols-2 gap-1 mb-2">
                          {q.options.map((opt, oi) => {
                            const isCorrect = answerLetters.has(opt.label.toUpperCase());
                            return (
                              <span key={oi}
                                className={`text-[10px] px-2 py-1 rounded flex items-center gap-1.5 ${
                                  isCorrect
                                    ? "bg-green-500/10 text-green-700 border border-green-500/30"
                                    : "bg-[var(--color-bg)] text-[var(--color-text-muted)] border border-transparent"
                                }`}>
                                {isCorrect && <Check size={8} className="text-green-500 shrink-0" />}
                                {opt.label}. {opt.content}
                              </span>
                            );
                          })}
                        </div>
                      )}

                      {/* 答案/解析 */}
                      <div className="flex items-center gap-3 text-[9px] text-[var(--color-text-muted)] flex-wrap">
                        <span className="text-green-600">答案: {q.answer}</span>
                        {q.analysis && <span className="truncate max-w-[200px]">解析: {q.analysis.slice(0, 50)}...</span>}
                        {q.ai_corrected && <span className="text-blue-500">AI已修</span>}
                        <span className={`ml-auto ${q.confidence >= 0.8 ? "text-green-500" : "text-yellow-500"}`}>
                          {Math.round(q.confidence * 100)}%
                        </span>
                      </div>
                    </div>

                    {/* 操作按钮 */}
                    <div className="flex flex-col gap-1 shrink-0">
                      <button onClick={() => startEdit(i)}
                        className="p-1 rounded hover:bg-blue-500/10 text-[var(--color-text-muted)] hover:text-blue-500">
                        <Edit3 size={11} />
                      </button>
                      <button onClick={() => toggleRemove(origIdx)}
                        className="p-1 rounded hover:bg-red-500/10 text-[var(--color-text-muted)] hover:text-red-500">
                        <X size={11} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* 操作栏 */}
          <div className="sticky bottom-0 pb-4 bg-[var(--color-bg)]">
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

// ── 编辑卡片组件 ──

function EditCard({
  form, onChange, onSave, onCancel, onToggleCorrect,
}: {
  form: PreviewQuestion;
  onChange: (q: PreviewQuestion) => void;
  onSave: () => void;
  onCancel: () => void;
  onToggleCorrect: (oi: number) => void;
}) {
  return (
    <div className="p-4 rounded-xl border-2 border-blue-400/40 bg-blue-500/[0.02] space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium text-blue-500">编辑模式</span>
        <div className="flex gap-1.5">
          <button onClick={onSave}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-blue-500 text-white text-[10px] font-medium hover:opacity-90">
            <Save size={10} /> 保存
          </button>
          <button onClick={onCancel}
            className="px-2.5 py-1.5 rounded-lg border border-[var(--color-border)]/50 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            取消
          </button>
        </div>
      </div>

      {/* 题型选择 */}
      <div className="flex gap-2">
        {["single", "multiple", "judge", "fill", "essay"].map((t) => (
          <button key={t} onClick={() => onChange({ ...form, question_type: t })}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-medium border transition-all ${
              form.question_type === t
                ? "border-blue-400 bg-blue-500/10 text-blue-600"
                : "border-[var(--color-border)]/50 text-[var(--color-text-muted)]"
            }`}>
            {t === "single" ? "单选" : t === "multiple" ? "多选" : t === "judge" ? "判断" : t === "fill" ? "填空" : "简答"}
          </button>
        ))}
      </div>

      {/* 题干 */}
      <div>
        <label className="text-[9px] text-[var(--color-text-muted)] mb-1 block">题干</label>
        <textarea value={form.stem} onChange={(e) => onChange({ ...form, stem: e.target.value })}
          className="w-full p-2 rounded-lg border border-[var(--color-border)]/60 bg-[var(--color-surface)] text-[12px] text-[var(--color-text)] resize-none h-16 focus:outline-none focus:border-blue-400"
        />
      </div>

      {/* 选项 */}
      {form.options && form.options.length > 0 && (
        <div>
          <label className="text-[9px] text-[var(--color-text-muted)] mb-1 block">
            选项（点击标签切换是否正确）
          </label>
          <div className="grid grid-cols-1 gap-1.5">
            {form.options.map((opt, oi) => (
              <div key={oi} className="flex items-center gap-2">
                <button onClick={() => onToggleCorrect(oi)}
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold border shrink-0 ${
                    opt.is_correct
                      ? "bg-green-500 text-white border-green-500"
                      : "bg-[var(--color-surface)] text-[var(--color-text-muted)] border-[var(--color-border)]/50"
                  }`}>
                  {opt.is_correct ? <Check size={8} /> : opt.label}
                </button>
                <input value={opt.content} onChange={(e) => {
                  const opts = [...form.options!];
                  opts[oi] = { ...opts[oi], content: e.target.value };
                  onChange({ ...form, options: opts });
                }}
                  className="flex-1 p-1.5 rounded-lg border border-[var(--color-border)]/60 bg-[var(--color-surface)] text-[11px] text-[var(--color-text)] focus:outline-none focus:border-blue-400"
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 答案 */}
      <div>
        <label className="text-[9px] text-[var(--color-text-muted)] mb-1 block">答案</label>
        <input value={form.answer} onChange={(e) => onChange({ ...form, answer: e.target.value })}
          className="w-full p-2 rounded-lg border border-[var(--color-border)]/60 bg-[var(--color-surface)] text-[12px] text-[var(--color-text)] focus:outline-none focus:border-blue-400"
        />
      </div>

      {/* 解析 */}
      <div>
        <label className="text-[9px] text-[var(--color-text-muted)] mb-1 block">解析</label>
        <textarea value={form.analysis} onChange={(e) => onChange({ ...form, analysis: e.target.value })}
          className="w-full p-2 rounded-lg border border-[var(--color-border)]/60 bg-[var(--color-surface)] text-[12px] text-[var(--color-text)] resize-none h-14 focus:outline-none focus:border-blue-400"
        />
      </div>
    </div>
  );
}
