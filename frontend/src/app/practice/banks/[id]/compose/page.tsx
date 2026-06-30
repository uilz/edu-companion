"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Save, GripVertical, Plus, Copy, Trash2,
  Search, Check, X, Loader2, BookOpen, FileText, Upload,
} from "lucide-react";
import {
  getBank, getBankQuestions,
  createQuestion, deleteQuestion,
  copyQuestionsToBank, reorderQuestionsInBank, updateBank,
  type V7Question, type V7Bank,
} from "@/lib/api/practice-api";
import QuestionStem from "@/components/practice/components/QuestionStem";
import QuestionEditorModal, { type EditableQuestion } from "@/components/practice/components/QuestionEditorModal";

// ── 统一题型标签 ──
const TYPE_LABELS: Record<string, string> = {
  single: "单选", multiple: "多选", judge: "判断",
  choice: "单选", fill: "填空", free_form: "简答", essay: "简答",
};

/** 从已有题库选题的弹窗 */
function QuestionPicker({ bankId, onPick, onClose }: {
  bankId: string;
  onPick: (qids: string[]) => void;
  onClose: () => void;
}) {
  const [banks, setBanks] = useState<V7Bank[]>([]);
  const [selectedBank, setSelectedBank] = useState("");
  const [questions, setQuestions] = useState<V7Question[]>([]);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch("/api/practice/banks").then(r => r.json()).then(data => {
      const items = Array.isArray(data) ? data : (data?.items || []);
      setBanks(items.filter((b: any) => b.id !== bankId));
      if (items.length > 0) setSelectedBank(items[0].id);
    }).catch(() => {});
  }, [bankId]);

  useEffect(() => {
    if (!selectedBank) return;
    getBankQuestions(selectedBank, { page: 1 }).then(data => {
      setQuestions(data.items || []);
    }).catch(() => setQuestions([]));
  }, [selectedBank]);

  const toggle = (qid: string) => {
    setChecked(p => {
      const next = new Set(p);
      if (next.has(qid)) next.delete(qid); else next.add(qid);
      return next;
    });
  };

  const filtered = search
    ? questions.filter(q => q.stem.toLowerCase().includes(search.toLowerCase()))
    : questions;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div className="w-full max-w-3xl max-h-[85vh] flex flex-col rounded-2xl bg-[var(--color-bg)] border border-[var(--color-border)] shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border)]">
          <h3 className="text-sm font-semibold">从已有题库选题</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-[var(--color-surface)] text-[var(--color-text-muted)]">
            <X size={16} />
          </button>
        </div>
        <div className="p-4 space-y-3 flex-1 overflow-y-auto">
          {/* 题库选择+搜索 */}
          <div className="flex gap-2">
            <select value={selectedBank} onChange={e => { setSelectedBank(e.target.value); setChecked(new Set()); }}
              className="flex-1 px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm">
              {banks.map(b => <option key={b.id} value={b.id}>{b.name} ({b.question_count || "?"}题)</option>)}
            </select>
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder="搜索题目..." className="w-full pl-9 pr-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-sm" />
            </div>
          </div>
          {/* 题目列表 */}
          <div className="space-y-1 max-h-[50vh] overflow-y-auto">
            {filtered.map((q, i) => (
              <div key={q.id} onClick={() => toggle(q.id)}
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all text-sm ${
                  checked.has(q.id) ? "border-red-500 bg-red-500/10" : "border-transparent hover:border-[var(--color-border)]"
                }`}>
                <div className={`w-5 h-5 flex-shrink-0 flex items-center justify-center rounded border text-xs ${
                  checked.has(q.id) ? "bg-red-500 text-white border-red-500" : "border-[var(--color-border)]"
                }`}>{checked.has(q.id) ? <Check size={12} /> : i + 1}</div>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium bg-opacity-20 ${
                  q.question_type === "multiple" ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"
                }`}>{TYPE_LABELS[q.question_type] || q.question_type}</span>
                <span className="flex-1 truncate text-[var(--color-text)]">{q.stem.replace(/<[^>]+>/g, "")}</span>
                <div className="flex-shrink-0 text-[10px] text-[var(--color-text-muted)]">{"★".repeat(q.difficulty)}</div>
              </div>
            ))}
            {filtered.length === 0 && (
              <div className="text-center py-8 text-sm text-[var(--color-text-muted)]">该题库暂无题目</div>
            )}
          </div>
        </div>
        <div className="flex items-center justify-between p-4 border-t border-[var(--color-border)]">
          <span className="text-xs text-[var(--color-text-muted)]">已选 {checked.size} 题</span>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text-muted)]">取消</button>
            <button onClick={() => onPick(Array.from(checked))} disabled={checked.size === 0}
              className="px-4 py-2 rounded-lg bg-red-500 text-white text-sm hover:opacity-90 disabled:opacity-30 flex items-center gap-1.5">
              <Copy size={14} />复制选中题目
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 简化的拖拽排序逻辑（上下按钮版，免复杂依赖） ──
function moveItem<T>(arr: T[], from: number, to: number): T[] {
  const next = [...arr];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

export default function ComposePage() {
  const params = useParams();
  const router = useRouter();
  const bankId = params.id as string;

  const [bank, setBank] = useState<V7Bank | null>(null);
  const [questions, setQuestions] = useState<V7Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [showEditor, setShowEditor] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<EditableQuestion | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [bankName, setBankName] = useState("");
  const [bankDesc, setBankDesc] = useState("");

  const autoSaveTimer = useRef<ReturnType<typeof setTimeout>>();
  const reorderTimer = useRef<ReturnType<typeof setTimeout>>();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [bk, qs] = await Promise.all([
        getBank(bankId),
        getBankQuestions(bankId, { page: 1 }),
      ]);
      setBank(bk);
      setBankName(bk.name || "");
      setBankDesc((bk as any).description || "");
      setQuestions(qs.items || []);
    } catch (e) {
      console.error("加载失败", e);
    }
    setLoading(false);
  }, [bankId]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── 自动保存题库名称/描述 ──
  const saveBankMeta = useCallback(async (name: string, desc: string) => {
    setSaving(true);
    try {
      await updateBank(bankId, { name, description: desc });
      setDirty(false);
    } catch (e) {
      console.error("保存失败", e);
    }
    setSaving(false);
  }, [bankId]);

  const onNameChange = (v: string) => {
    setBankName(v);
    setDirty(true);
    clearTimeout(autoSaveTimer.current);
    autoSaveTimer.current = setTimeout(() => saveBankMeta(v, bankDesc), 2000);
  };

  const onDescChange = (v: string) => {
    setBankDesc(v);
    setDirty(true);
    clearTimeout(autoSaveTimer.current);
    autoSaveTimer.current = setTimeout(() => saveBankMeta(bankName, v), 2000);
  };

  // ── 拖拽排序（上下移动） ──
  const moveQuestion = async (idx: number, dir: "up" | "down") => {
    const target = dir === "up" ? idx - 1 : idx + 1;
    if (target < 0 || target >= questions.length) return;
    const reordered = moveItem(questions, idx, target);
    setQuestions(reordered);
    clearTimeout(reorderTimer.current);
    reorderTimer.current = setTimeout(async () => {
      try {
        await reorderQuestionsInBank(bankId, reordered.map(q => q.id));
      } catch (e) {
        console.error("排序保存失败", e);
      }
    }, 1000);
  };

  // ── 删除题目 ──
  const handleDelete = async (qid: string) => {
    try {
      await deleteQuestion(qid);
      setQuestions(p => p.filter(q => q.id !== qid));
    } catch (e) {
      console.error("删除失败", e);
    }
  };

  // ── 从其他题库复制 ──
  const handleCopyFromBank = async (qids: string[]) => {
    if (qids.length === 0) return;
    setShowPicker(false);
    try {
      const result = await copyQuestionsToBank(bankId, qids);
      // 重新加载
      await loadData();
    } catch (e) {
      console.error("复制失败", e);
    }
  };

  // ── 打开新题编辑器 ──
  const openNew = () => {
    setEditingQuestion({
      id: "", stem: "", question_type: "single",
      options: [
        { letter: "A", text: "", is_correct: false },
        { letter: "B", text: "", is_correct: false },
      ],
      answer: [], analysis: "", difficulty: 3,
    });
    setIsNew(true);
    setShowEditor(true);
  };

  // ── 保存题目 ──
  const handleSaveQuestion = async (eq: EditableQuestion) => {
    const { id, stem, question_type, options, answer, analysis, difficulty } = eq;
    if (!stem.trim()) return;
    try {
      if (isNew) {
        await createQuestion(bankId, { stem: stem.trim(), question_type, options, answer, analysis, difficulty });
      } else {
        const { updateQuestion } = await import("@/lib/api/practice-api");
        await updateQuestion(id, { stem: stem.trim(), question_type, options, answer, analysis, difficulty });
      }
      setShowEditor(false);
      await loadData();
    } catch (e) {
      console.error("保存题目失败", e);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto px-4 py-5 space-y-5">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push(`/practice/banks/${bankId}`)} className="p-1.5 rounded-lg hover:bg-[var(--color-surface)] text-[var(--color-text-muted)]">
            <ArrowLeft size={18} />
          </button>
          <BookOpen size={18} className="text-red-500" />
          <h1 className="text-base font-semibold">组卷编辑</h1>
        </div>
        <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
          {dirty && <span className="text-amber-500">● 未保存</span>}
          {saving && <span className="flex items-center gap-1"><Loader2 size={12} className="animate-spin" />保存中...</span>}
          <span>{questions.length} 题</span>
        </div>
      </div>

      {/* 题库名称/描述 */}
      <div className="space-y-2 p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]">
        <input value={bankName} onChange={e => onNameChange(e.target.value)}
          placeholder="题库名称" className="w-full bg-transparent text-lg font-semibold outline-none placeholder:text-[var(--color-text-muted)]" />
        <textarea value={bankDesc} onChange={e => onDescChange(e.target.value)}
          placeholder="题库描述（可选）..." rows={2}
          className="w-full bg-transparent text-xs text-[var(--color-text-muted)] outline-none resize-none placeholder:text-[var(--color-text-muted)]/50" />
      </div>

      {/* 操作按钮 */}
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={() => setShowPicker(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-sm hover:bg-[var(--color-border)]/50">
          <Copy size={14} />从题库选题
        </button>
        <button onClick={openNew}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-sm hover:bg-[var(--color-border)]/50">
          <Plus size={14} />新建题目
        </button>
        <button onClick={() => router.push(`/practice/banks/${bankId}/import`)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-sm hover:bg-[var(--color-border)]/50">
          <Upload size={14} />批量导入
        </button>
      </div>

      {/* 题目列表 */}
      <div className="space-y-1">
        {questions.length === 0 && (
          <div className="text-center py-16 text-sm text-[var(--color-text-muted)]">
            <FileText size={32} className="mx-auto mb-2 opacity-30" />
            题库为空，点击上方按钮添加题目
          </div>
        )}
        {questions.map((q, i) => (
          <div key={q.id}
            className="flex items-center gap-2 p-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] group hover:border-red-500/30 transition-all">
            {/* 排序手柄 */}
            <div className="flex flex-col gap-0.5 opacity-30 group-hover:opacity-60">
              <button onClick={() => moveQuestion(i, "up")} disabled={i === 0}
                className="p-0.5 hover:text-red-500 disabled:opacity-20 disabled:cursor-not-allowed">
                <svg width="10" height="6" viewBox="0 0 10 6" fill="currentColor"><path d="M5 0L10 6H0z"/></svg>
              </button>
              <span className="text-[10px] text-center text-[var(--color-text-muted)] font-mono">{i + 1}</span>
              <button onClick={() => moveQuestion(i, "down")} disabled={i === questions.length - 1}
                className="p-0.5 hover:text-red-500 disabled:opacity-20 disabled:cursor-not-allowed">
                <svg width="10" height="6" viewBox="0 0 10 6" fill="currentColor"><path d="M5 6L10 0H0z"/></svg>
              </button>
            </div>
            {/* 题型标签 */}
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 ${
              q.question_type === "multiple" ? "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300" :
              q.question_type === "judge" ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300" :
              q.question_type === "fill" ? "bg-amber-100 text-amber-700" :
              (q.question_type === "free_form") ? "bg-rose-100 text-rose-700" :
              "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
            }`}>{TYPE_LABELS[q.question_type] || q.question_type}</span>
            {/* 题干预览 */}
            <span className="flex-1 truncate text-sm text-[var(--color-text)] pl-1">
              {q.stem.replace(/<[^>]+>/g, "").replace(/\[.*?\]/g, "").slice(0, 100)}
            </span>
            {/* 难度 */}
            <span className="text-[10px] text-[var(--color-text-muted)] shrink-0">{"★".repeat(q.difficulty).padEnd(5, "☆")}</span>
            {/* 操作 */}
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
              <button onClick={() => handleDelete(q.id)}
                className="p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-[var(--color-text-muted)] hover:text-red-500">
                <X size={13} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* 底部统计 */}
      <div className="text-xs text-[var(--color-text-muted)] text-center pb-8">
        共 {questions.length} 题 · 操作自动保存
      </div>

      {/* 弹窗 */}
      {showPicker && (
        <QuestionPicker bankId={bankId} onPick={handleCopyFromBank} onClose={() => setShowPicker(false)} />
      )}
      {showEditor && editingQuestion && (
        <QuestionEditorModal question={editingQuestion} isNew={isNew} onSave={handleSaveQuestion} onClose={() => setShowEditor(false)} />
      )}
    </div>
  );
}
