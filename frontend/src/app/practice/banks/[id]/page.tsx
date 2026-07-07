"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Plus, Search, Trash2, Edit3, Sparkles,
  BookOpen, Star, Eye, Save, ChevronLeft, ChevronRight,
  FileText, X,
} from "lucide-react";
import { PageSkeleton } from "@/components/ui/Skeleton";
import {
  getBank, getBankQuestions, deleteQuestion,
  toggleFavorite, toggleSlash,
  updateQuestion, createQuestion, updateBank,
  type V7Question,
} from "@/lib/api/practice-api";
import QuestionStem from "@/components/practice/components/QuestionStem";
import QuestionEditorModal, { type EditableQuestion } from "@/components/practice/components/QuestionEditorModal";
import QuestionPreviewModal from "@/components/practice/components/QuestionPreviewModal";

const TYPE_LABELS: Record<string, string> = {
  single: "单选", multiple: "多选", judge: "判断",
  choice: "单选", fill: "填空", free_form: "简答", essay: "简答",
};
const TYPE_COLORS: Record<string, string> = {
  single: "bg-info/20 text-info dark:bg-info/10 dark:text-info",
  multiple: "bg-accent/20 text-accent dark:bg-accent/10 dark:text-accent",
  judge: "bg-success/20 text-success dark:bg-success/10 dark:text-success",
  choice: "bg-info/20 text-info dark:bg-info/10 dark:text-info",
  fill: "bg-warning/20 text-warning dark:bg-warning/10 dark:text-warning",
  free_form: "bg-danger/20 text-danger dark:bg-danger/10 dark:text-danger",
  essay: "bg-danger/20 text-danger dark:bg-danger/10 dark:text-danger",
};

export default function BankDetailPage() {
  const params = useParams();
  const router = useRouter();
  const bankId = params.id as string;

  const [bank, setBank] = useState<any>(null);
  const [questions, setQuestions] = useState<V7Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [filterType, setFilterType] = useState("");
  const [searchText, setSearchText] = useState("");
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editingName, setEditingName] = useState(false);
  const pageSize = 30;

  // 弹窗状态
  const [showEditor, setShowEditor] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<EditableQuestion | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [previewQuestion, setPreviewQuestion] = useState<V7Question | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [b, q] = await Promise.all([
        getBank(bankId),
        getBankQuestions(bankId, { page, page_size: pageSize, question_type: filterType || undefined }),
      ]);
      setBank(b); setEditName(b.name || ""); setEditDesc(b.description || "");
      let items = q.items || [];
      if (searchText) {
        const low = searchText.toLowerCase();
        items = items.filter((qi: V7Question) => qi.stem.toLowerCase().includes(low));
      }
      setQuestions(items);
      setTotal(searchText ? items.length : q.total || 0);
    } catch { router.push("/practice"); }
    finally { setLoading(false); }
  };
  useEffect(() => { loadData(); }, [bankId, page, filterType]);

  const handleUpdateBank = async () => {
    await updateBank(bankId, { name: editName, description: editDesc });
    setEditingName(false); loadData();
  };

  const handleDelete = async (qId: string) => {
    await deleteQuestion(qId); loadData();
  };
  const handleFav = async (qId: string) => {
    await toggleFavorite(qId); loadData();
  };
  const handleSlash = async (qId: string) => {
    await toggleSlash(qId); loadData();
  };

  const openNew = () => {
    setEditingQuestion({
      id: "", stem: "", question_type: "single",
      options: [{ letter: "A", text: "", is_correct: false }, { letter: "B", text: "", is_correct: false }, { letter: "C", text: "", is_correct: false }, { letter: "D", text: "", is_correct: false }],
      answer: [], analysis: "", difficulty: 3,
    });
    setIsNew(true); setShowEditor(true);
  };

  const openEdit = (q: V7Question) => {
    setEditingQuestion({
      id: q.id, stem: q.stem, question_type: q.question_type,
      options: q.options || [], answer: (q as any).answer || [],
      analysis: (q as any).analysis || "", difficulty: q.difficulty || 3,
    });
    setIsNew(false); setShowEditor(true);
  };

  const handleSave = async (eq: EditableQuestion) => {
    const { id, stem, question_type, options, answer, analysis, difficulty } = eq;
    if (!stem.trim()) return;
    if (isNew) {
      await createQuestion(bankId, { stem: stem.trim(), question_type, options, answer, analysis, difficulty });
    } else {
      await updateQuestion(id, { stem: stem.trim(), question_type, options, answer, analysis, difficulty });
    }
    setShowEditor(false); loadData();
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (loading && !bank) return <PageSkeleton />;
  if (!bank) return null;

  return (
    <div className="max-w-5xl mx-auto px-4 py-5 space-y-5">
      {/* 编辑/预览弹窗 */}
      {showEditor && editingQuestion && (
        <QuestionEditorModal question={editingQuestion} isNew={isNew} onSave={handleSave} onClose={() => setShowEditor(false)} />
      )}
      {previewQuestion && (
        <QuestionPreviewModal
          question={previewQuestion}
          onClose={() => setPreviewQuestion(null)}
          onEdit={() => { const q = previewQuestion; setPreviewQuestion(null); openEdit(q); }}
        />
      )}

      {/* 导航 */}
      <div className="flex items-center gap-3">
        <button onClick={() => router.push("/practice")} className="p-2 rounded-lg hover:bg-surface">
          <ArrowLeft size={18} className="text-muted" />
        </button>
        <div className="flex-1 min-w-0">
          {editingName ? (
            <div className="flex items-center gap-2">
              <input value={editName} onChange={e => setEditName(e.target.value)}
                className="flex-1 px-3 py-1.5 rounded-lg border border bg-page text-sm font-medium" autoFocus />
              <button onClick={handleUpdateBank} className="px-3 py-1.5 rounded-lg bg-accent text-white text-xs">保存</button>
              <button onClick={() => setEditingName(false)} className="px-3 py-1.5 rounded-lg border border text-xs">取消</button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold text truncate">{bank.name}</h1>
              <button onClick={() => setEditingName(true)} className="p-1 rounded hover:bg-surface text-muted">
                <Edit3 size={13} />
              </button>
              <span className="text-xs text-muted">{bank.real_count ?? 0} 题</span>
            </div>
          )}
        </div>
      </div>

      {/* 操作栏 */}
      <div className="flex items-center gap-2.5 flex-wrap">
        <div className="relative flex-1 min-w-[160px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input value={searchText} onChange={e => setSearchText(e.target.value)}
            placeholder="搜索..." className="w-full pl-9 pr-3 py-2 rounded-lg border border bg-page text-xs" />
        </div>
        <select value={filterType} onChange={e => { setFilterType(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded-lg border border bg-page text-xs">
          <option value="">全部</option>
          <option value="single">单选</option>
          <option value="multiple">多选</option>
          <option value="judge">判断</option>
          <option value="choice">单选(兼容)</option>
          <option value="fill">填空</option>
          <option value="free_form">简答</option>
        </select>
        <button onClick={openNew}
          className="px-3 py-2 rounded-lg border border-dashed border text-xs text-muted hover:border-accent hover:text-accent flex items-center gap-1.5">
          <Plus size={14} />添加
        </button>
        <button onClick={() => router.push(`/practice?tab=practice&bank=${bankId}`)}
          className="px-3 py-2 rounded-lg bg-accent text-white text-xs font-medium hover:opacity-90 flex items-center gap-1.5">
          <Sparkles size={14} />练习
        </button>
        <button onClick={() => router.push(`/practice/banks/${bankId}/compose`)}
          className="px-3 py-2 rounded-lg border border-danger/30 text-danger text-xs font-medium hover:bg-danger/10 dark:hover:bg-danger/10 flex items-center gap-1.5">
          <Edit3 size={14} />组卷
        </button>
      </div>

      {/* 题目列表 */}
      <div className="space-y-1.5">
        {questions.length === 0 ? (
          <div className="text-center py-16 text-muted">
            <BookOpen size={32} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">题库为空</p>
            <p className="text-xs mt-1">点击「添加」或去对话中说「帮我出题」</p>
          </div>
        ) : (
          questions.map(q => {
            const isFav = !!(q as any).is_favorite;
            const isSlashed = !!(q as any).is_slashed;
            return (
              <div key={q.id}
                className="flex items-start gap-3 p-3 rounded-xl bg-surface border border/50 hover:border-accent/30 transition-all group">
                <span className={`shrink-0 px-2 py-0.5 rounded text-[10px] font-medium ${TYPE_COLORS[q.question_type] || ""}`}>
                  {TYPE_LABELS[q.question_type] || q.question_type}
                </span>
                <button onClick={() => setPreviewQuestion(q)} className="flex-1 min-w-0 text-left">
                  <QuestionStem stem={q.stem} className="text-sm line-clamp-2" />
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`inline-block w-1.5 h-1.5 rounded-full ${q.difficulty >= 4 ? "bg-danger/80" : q.difficulty >= 3 ? "bg-warning/80" : "bg-success/80"}`} />
                    <span className="text-[10px] text-muted">难度 {q.difficulty}/5</span>
                    {isSlashed && <span className="text-[10px] text-muted line-through">已斩</span>}
                  </div>
                </button>
                <div className="shrink-0 flex items-center gap-0.5">
                  <IconBtn onClick={() => setPreviewQuestion(q)} title="预览"><Eye size={14} /></IconBtn>
                  <IconBtn onClick={() => openEdit(q)} title="编辑"><Edit3 size={14} /></IconBtn>
                  <IconBtn onClick={() => handleFav(q.id)} title="收藏" active={isFav} activeColor="text-warning"><Star size={14} fill={isFav ? "currentColor" : "none"} /></IconBtn>
                  <IconBtn onClick={() => handleSlash(q.id)} title="斩题"><X size={14} /></IconBtn>
                  <IconBtn onClick={() => handleDelete(q.id)} title="删除" hoverColor="hover:text-danger"><Trash2 size={14} /></IconBtn>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="p-1.5 rounded-lg border border disabled:opacity-30">
            <ChevronLeft size={14} />
          </button>
          <span className="text-xs text-muted">{page}/{totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
            className="p-1.5 rounded-lg border border disabled:opacity-30">
            <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

function IconBtn({ children, onClick, title, active, activeColor, hoverColor }: {
  children: React.ReactNode; onClick: () => void; title: string;
  active?: boolean; activeColor?: string; hoverColor?: string;
}) {
  return (
    <button onClick={onClick} title={title}
      className={`p-1.5 rounded-lg transition-colors ${
        active ? activeColor || "text-accent" : "text-muted"
      } ${hoverColor || "hover:text"} hover:bg-surface`}>
      {children}
    </button>
  );
}
