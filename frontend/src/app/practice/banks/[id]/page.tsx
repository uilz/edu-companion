"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Plus, Search, Trash2, Edit3, X,
  BookOpen, Sparkles, Star, FileText,
  Eye, Loader2, Save, ChevronLeft, ChevronRight, Check,
} from "lucide-react";
import {
  getBank, getBankQuestions, deleteQuestion,
  toggleFavorite, toggleSlash,
  updateQuestion, createQuestion, updateBank,
  type V7Question, type V7Option,
} from "@/lib/api/practice-api";
import QuestionStem from "@/components/practice/components/QuestionStem";

// ── 类型 ──

const TYPE_LABELS: Record<string, string> = {
  single: "单选", multiple: "多选", judge: "判断",
  fill: "填空", free_form: "简答", essay: "简答",
};

const TYPE_COLORS: Record<string, string> = {
  single: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  multiple: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  judge: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  fill: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  free_form: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
  essay: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
};

interface EditableQuestion {
  id: string;
  stem: string;
  question_type: string;
  options: V7Option[];
  answer: string[];
  analysis: string;
  difficulty: number;
}

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
  const [editBank, setEditBank] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const pageSize = 30;

  // ── 题目预览/编辑状态 ──
  const [previewQuestion, setPreviewQuestion] = useState<V7Question | null>(null);
  const [editingQuestion, setEditingQuestion] = useState<EditableQuestion | null>(null);
  const [newQuestionMode, setNewQuestionMode] = useState(false);

  // ── 加载数据 ──
  const loadData = async () => {
    setLoading(true);
    try {
      const [b, q] = await Promise.all([
        getBank(bankId),
        getBankQuestions(bankId, {
          page,
          page_size: pageSize,
          question_type: filterType || undefined,
        }),
      ]);
      setBank(b);
      setEditName(b.name || "");
      setEditDesc(b.description || "");

      let items = q.items || [];
      if (searchText) {
        const lower = searchText.toLowerCase();
        items = items.filter((q: V7Question) => q.stem.toLowerCase().includes(lower));
      }
      setQuestions(items);
      setTotal(searchText ? items.length : q.total || 0);
    } catch {
      router.push("/practice");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [bankId, page, filterType, searchText]);

  // ── 编辑题库 ──
  const handleUpdateBank = async () => {
    await updateBank(bankId, { name: editName, description: editDesc });
    setEditBank(false);
    loadData();
  };

  // ── 删除题目 ──
  const handleDelete = async (qId: string) => {
    if (!confirm("确认删除这道题？")) return;
    await deleteQuestion(qId);
    loadData();
  };

  // ── 收藏/斩题 ──
  const handleToggleFav = async (qId: string) => {
    await toggleFavorite(qId);
    loadData();
  };
  const handleToggleSlash = async (qId: string) => {
    await toggleSlash(qId);
    loadData();
  };

  // ── 预览题目 ──
  const handlePreview = async (q: V7Question) => {
    // use the already loaded question data
    setPreviewQuestion(q);
    setEditingQuestion(null);
    setNewQuestionMode(false);
  };

  // ── 编辑题目 ──
  const handleEdit = (q: V7Question) => {
    setEditingQuestion({
      id: q.id,
      stem: q.stem,
      question_type: q.question_type,
      options: q.options || [],
      answer: (q as any).answer || [],
      analysis: (q as any).analysis || "",
      difficulty: q.difficulty || 3,
    });
    setPreviewQuestion(null);
    setNewQuestionMode(false);
  };

  // ── 新建题目 ──
  const handleNewQuestion = () => {
    setEditingQuestion({
      id: "",
      stem: "",
      question_type: "single",
      options: [
        { letter: "A", text: "", is_correct: false },
        { letter: "B", text: "", is_correct: false },
        { letter: "C", text: "", is_correct: false },
        { letter: "D", text: "", is_correct: false },
      ],
      answer: [],
      analysis: "",
      difficulty: 3,
    });
    setPreviewQuestion(null);
    setNewQuestionMode(true);
  };

  // ── 保存题目 ──
  const handleSaveQuestion = async () => {
    if (!editingQuestion) return;
    const { id, stem, question_type, options, answer, analysis, difficulty } = editingQuestion;
    if (!stem.trim()) return;

    try {
      if (newQuestionMode) {
        await createQuestion(bankId, {
          stem: stem.trim(),
          question_type,
          options,
          answer,
          analysis,
          difficulty,
        });
      } else {
        await updateQuestion(id, {
          stem: stem.trim(),
          question_type,
          options,
          answer,
          analysis,
          difficulty,
        });
      }
      setEditingQuestion(null);
      setNewQuestionMode(false);
      loadData();
    } catch (e) {
      console.error("保存失败", e);
    }
  };

  // ── 编辑辅助 ──
  const updateEditingOptions = (letter: string, field: "text" | "is_correct", value: string | boolean) => {
    if (!editingQuestion) return;
    setEditingQuestion({
      ...editingQuestion,
      options: editingQuestion.options.map((o) =>
        o.letter === letter ? { ...o, [field]: value } : o
      ),
    });
  };

  const addOption = () => {
    if (!editingQuestion) return;
    const nextLetter = String.fromCharCode(65 + editingQuestion.options.length);
    setEditingQuestion({
      ...editingQuestion,
      options: [...editingQuestion.options, { letter: nextLetter, text: "", is_correct: false }],
    });
  };

  const removeOption = (letter: string) => {
    if (!editingQuestion || editingQuestion.options.length <= 2) return;
    setEditingQuestion({
      ...editingQuestion,
      options: editingQuestion.options.filter((o) => o.letter !== letter),
    });
  };

  // ── 分页 ──
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (loading && !bank) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (!bank) return null;

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      {/* ── 顶部导航 ── */}
      <div className="flex items-center gap-3">
        <button onClick={() => router.push("/practice")} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          {editBank ? (
            <div className="space-y-2">
              <input value={editName} onChange={(e) => setEditName(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-lg font-semibold" />
              <input value={editDesc} onChange={(e) => setEditDesc(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-500"
                placeholder="题库描述" />
              <div className="flex gap-2">
                <button onClick={handleUpdateBank} className="px-3 py-1 text-sm bg-indigo-500 text-white rounded-lg hover:bg-indigo-600">保存</button>
                <button onClick={() => setEditBank(false)} className="px-3 py-1 text-sm rounded-lg border border-gray-300 dark:border-gray-600">取消</button>
              </div>
            </div>
          ) : (
            <div>
              <h1 className="text-xl font-semibold">{bank.name}</h1>
              {bank.description && <p className="text-sm text-gray-500 mt-1">{bank.description}</p>}
              <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                <span>共 {bank.real_count} 题</span>
                {bank.ref_node_id && <span>关联知识点: {bank.ref_node_id}</span>}
                <button onClick={() => setEditBank(true)} className="text-indigo-500 hover:underline">
                  <Edit3 className="w-3 h-3 inline mr-1" />编辑
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 操作栏 ── */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input value={searchText} onChange={(e) => setSearchText(e.target.value)}
            placeholder="搜索题目..." className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm" />
        </div>
        <select value={filterType} onChange={(e) => { setFilterType(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm">
          <option value="">全部题型</option>
          <option value="single">单选</option>
          <option value="multiple">多选</option>
          <option value="judge">判断</option>
          <option value="fill">填空</option>
          <option value="free_form">简答</option>
        </select>
        <button onClick={handleNewQuestion}
          className="px-3 py-2 rounded-lg border border-dashed border-gray-300 dark:border-gray-600 text-sm text-gray-500 hover:border-indigo-400 hover:text-indigo-500 flex items-center gap-1.5">
          <Plus className="w-4 h-4" />添加题目
        </button>
        <button onClick={() => router.push(`/practice?tab=practice&bank=${bankId}`)}
          className="px-3 py-2 rounded-lg bg-indigo-500 text-white text-sm hover:bg-indigo-600 flex items-center gap-1.5">
          <Sparkles className="w-4 h-4" />开始练习
        </button>
        <button onClick={() => router.push(`/exam?bank=${bankId}`)}
          className="px-3 py-2 rounded-lg bg-red-500 text-white text-sm hover:bg-red-600 flex items-center gap-1.5">
          <FileText className="w-4 h-4" />模拟考试
        </button>
      </div>

      {/* ── 编辑/新建题目弹窗 ── */}
      {editingQuestion && (
        <div className="rounded-2xl border-2 border-indigo-300 dark:border-indigo-700 bg-white dark:bg-gray-800 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-indigo-600 dark:text-indigo-400">
              {newQuestionMode ? "添加新题目" : "编辑题目"}
            </h3>
            <button onClick={() => { setEditingQuestion(null); setNewQuestionMode(false); }}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700">
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* 题型 + 难度 */}
          <div className="flex gap-3">
            <select value={editingQuestion.question_type} onChange={(e) => setEditingQuestion({ ...editingQuestion, question_type: e.target.value })}
              className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm">
              <option value="single">单选</option>
              <option value="multiple">多选</option>
              <option value="judge">判断</option>
              <option value="fill">填空</option>
              <option value="free_form">简答</option>
            </select>
            <select value={editingQuestion.difficulty} onChange={(e) => setEditingQuestion({ ...editingQuestion, difficulty: Number(e.target.value) })}
              className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm">
              {[1, 2, 3, 4, 5].map((d) => (
                <option key={d} value={d}>{"★".repeat(d).padEnd(5, "☆")}</option>
              ))}
            </select>
          </div>

          {/* 题干 */}
          <textarea value={editingQuestion.stem} onChange={(e) => setEditingQuestion({ ...editingQuestion, stem: e.target.value })}
            placeholder="题干（支持 Markdown 和 LaTeX）..." rows={3}
            className="w-full px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 resize-none text-sm" />

          {/* 选项（单选/多选/判断） */}
          {(editingQuestion.question_type === "single" || editingQuestion.question_type === "multiple" || editingQuestion.question_type === "judge") && (
            <div className="space-y-2">
              <label className="text-xs text-gray-400 font-medium">选项配置（点击右侧勾选标记正确答案）</label>
              {editingQuestion.options.map((opt) => (
                <div key={opt.letter} className="flex items-center gap-2">
                  <span className="shrink-0 w-7 text-center text-sm font-bold text-gray-400">{opt.letter}.</span>
                  <input value={opt.text} onChange={(e) => updateEditingOptions(opt.letter, "text", e.target.value)}
                    placeholder={`选项 ${opt.letter}`}
                    className="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm" />
                  <button onClick={() => updateEditingOptions(opt.letter, "is_correct", !opt.is_correct)}
                    className={`p-1.5 rounded-lg border transition-colors ${
                      opt.is_correct ? "border-green-400 bg-green-50 dark:bg-green-900/20 text-green-600" : "border-gray-300 dark:border-gray-600 text-gray-400"
                    }`}>
                    <Check className="w-4 h-4" />
                  </button>
                  <button onClick={() => removeOption(opt.letter)}
                    className="p-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-400 hover:text-red-500">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
              <button onClick={addOption} className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-dashed border-gray-300 dark:border-gray-600 text-xs text-gray-400 hover:border-indigo-400 hover:text-indigo-500">
                <Plus className="w-3 h-3" />添加选项
              </button>
            </div>
          )}

          {/* 答案（填空/简答） */}
          {(editingQuestion.question_type === "fill" || editingQuestion.question_type === "free_form") && (
            <div>
              <label className="text-xs text-gray-400 font-medium block mb-1">参考答案</label>
              <input value={editingQuestion.answer[0] || ""} onChange={(e) => setEditingQuestion({ ...editingQuestion, answer: [e.target.value] })}
                placeholder="输入参考答案..."
                className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm" />
            </div>
          )}

          {/* 解析 */}
          <textarea value={editingQuestion.analysis} onChange={(e) => setEditingQuestion({ ...editingQuestion, analysis: e.target.value })}
            placeholder="题目解析（可选）..." rows={2}
            className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 resize-none text-sm" />

          {/* 保存 */}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => { setEditingQuestion(null); setNewQuestionMode(false); }}
              className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm">取消</button>
            <button onClick={handleSaveQuestion}
              disabled={!editingQuestion.stem.trim()}
              className="px-4 py-2 rounded-lg bg-indigo-500 text-white text-sm hover:bg-indigo-600 disabled:opacity-30 flex items-center gap-1.5">
              <Save className="w-4 h-4" />保存题目
            </button>
          </div>
        </div>
      )}

      {/* ── 题目预览弹窗 ── */}
      {previewQuestion && (
        <div className="rounded-2xl border-2 border-blue-300 dark:border-blue-700 bg-white dark:bg-gray-800 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-blue-600 dark:text-blue-400 flex items-center gap-2">
              <Eye className="w-4 h-4" />题目预览
            </h3>
            <button onClick={() => setPreviewQuestion(null)} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[previewQuestion.question_type] || ""}`}>
              {TYPE_LABELS[previewQuestion.question_type] || previewQuestion.question_type}
            </span>
            <span className="text-xs text-gray-400">难度 {"★".repeat(previewQuestion.difficulty).padEnd(5, "☆")}</span>
          </div>

          <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-900/50">
            <QuestionStem stem={previewQuestion.stem} className="text-base leading-relaxed" />
          </div>

          {(previewQuestion.options || []).length > 0 && (
            <div className="space-y-2">
              <label className="text-xs text-gray-400 font-medium">选项</label>
              {previewQuestion.options.map((opt: V7Option | any) => (
                <div key={opt.letter} className={`flex items-center gap-2 px-4 py-3 rounded-xl border ${
                  opt.is_correct ? "border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/10" : "border-gray-200 dark:border-gray-700"
                }`}>
                  <span className="font-medium mr-2">{opt.letter}.</span>
                  <span>{opt.text}</span>
                  {opt.is_correct && <Check className="w-4 h-4 ml-auto text-green-500" />}
                </div>
              ))}
            </div>
          )}

          {(previewQuestion as any).analysis && (
            <div>
              <label className="text-xs text-gray-400 font-medium block mb-1">解析</label>
              <p className="text-sm text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900/50 p-3 rounded-xl">{(previewQuestion as any).analysis}</p>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setPreviewQuestion(null)}
              className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm">关闭</button>
            <button onClick={() => { handleEdit(previewQuestion); }}
              className="px-4 py-2 rounded-lg bg-indigo-500 text-white text-sm hover:bg-indigo-600 flex items-center gap-1.5">
              <Edit3 className="w-4 h-4" />编辑此题
            </button>
          </div>
        </div>
      )}

      {/* ── 题目列表 ── */}
      <div className="space-y-2">
        {questions.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <BookOpen className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>这个题库还没有题目</p>
            <p className="text-sm mt-1">点击上方「添加题目」或去对话中说「帮我出题」</p>
          </div>
        ) : (
          questions.map((q) => (
            <div key={q.id}
              className="flex items-start gap-3 p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 hover:border-indigo-300 dark:hover:border-indigo-700 transition-colors group">
              {/* 题型标签 */}
              <span className={`shrink-0 px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[q.question_type] || ""}`}>
                {TYPE_LABELS[q.question_type] || q.question_type}
              </span>

              {/* 题干 */}
              <button onClick={() => handlePreview(q)}
                className="flex-1 min-w-0 text-left">
                <QuestionStem stem={q.stem} className="text-sm line-clamp-2" />
                <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-400">
                  <span className={`inline-block w-2 h-2 rounded-full ${q.difficulty >= 4 ? "bg-red-400" : q.difficulty >= 3 ? "bg-amber-400" : "bg-green-400"}`} />
                  难度 {q.difficulty}/5
                  {(q as any).is_slashed && <span className="text-gray-300 line-through">已斩</span>}
                </div>
              </button>

              {/* 操作按钮 */}
              <div className="shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={() => handlePreview(q)} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-blue-500" title="预览">
                  <Eye className="w-4 h-4" />
                </button>
                <button onClick={() => handleEdit(q)} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-indigo-500" title="编辑">
                  <Edit3 className="w-4 h-4" />
                </button>
                <button onClick={() => handleToggleFav(q.id)} className={`p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 ${(q as any).is_favorite ? "text-amber-500" : "text-gray-400"}`} title="收藏">
                  <Star className="w-4 h-4" fill={(q as any).is_favorite ? "currentColor" : "none"} />
                </button>
                <button onClick={() => handleToggleSlash(q.id)} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400" title="斩题">
                  <Eye className="w-4 h-4" />
                </button>
                <button onClick={() => handleDelete(q.id)} className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-500" title="删除">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* ── 分页 ── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-sm disabled:opacity-30">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-gray-500">{page}/{totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
            className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-sm disabled:opacity-30">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}