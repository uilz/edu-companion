"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Plus, Search, Filter, Trash2, Edit3,
  BookOpen, Sparkles, Download, Clock, Star,
  Type, Eye, Loader2,
} from "lucide-react";

// ── 类型 ──

interface BankDetail {
  id: string;
  name: string;
  description: string;
  real_count: number;
  auto_created: boolean;
  ref_node_id: string | null;
  ref_node_level: string | null;
  created_at: string;
}

interface QuestionItem {
  id: string;
  bank_id: string;
  question_type: string;
  stem: string;
  difficulty: number;
  cognitive_node_ids: string[];
  status: string;
  is_favorite: boolean;
  is_slashed: boolean;
  created_at: string;
}

// ── 题型标签 ──

const TYPE_LABELS: Record<string, string> = {
  single: "单选",
  multiple: "多选",
  judge: "判断",
  fill: "填空",
  essay: "简答",
  choice: "选择题",
};

const TYPE_COLORS: Record<string, string> = {
  single: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  multiple: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  judge: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  fill: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  essay: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
  choice: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300",
};

export default function BankDetailPage() {
  const params = useParams();
  const router = useRouter();
  const bankId = params.id as string;

  const [bank, setBank] = useState<BankDetail | null>(null);
  const [questions, setQuestions] = useState<QuestionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [filterType, setFilterType] = useState("");
  const [searchText, setSearchText] = useState("");
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const pageSize = 30;

  // ── 加载题库详情 ──
  const loadBank = async () => {
    try {
      const [bankRes, qRes] = await Promise.all([
        fetch(`/api/v7/practice/banks/${bankId}`),
        fetch(`/api/v7/practice/banks/${bankId}/questions?page=${page}&page_size=${pageSize}${filterType ? `&question_type=${filterType}` : ""}`),
      ]);
      if (!bankRes.ok) { router.push("/practice"); return; }
      const b = await bankRes.json();
      setBank(b);
      setEditName(b.name);
      setEditDesc(b.description || "");

      const q = await qRes.json();
      setQuestions(q.items || []);
      setTotal(q.total || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadBank(); }, [bankId, page, filterType]);

  // ── 编辑题库 ──
  const handleUpdate = async () => {
    await fetch(`/api/v7/practice/banks/${bankId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: editName, description: editDesc }),
    });
    setEditing(false);
    loadBank();
  };

  // ── 删除题目 ──
  const handleDelete = async (qId: string) => {
    if (!confirm("确认删除这道题？")) return;
    await fetch(`/api/v7/practice/questions/${qId}`, { method: "DELETE" });
    loadBank();
  };

  // ── 切换收藏 ──
  const handleToggleFav = async (qId: string) => {
    await fetch(`/api/v7/practice/questions/${qId}/favorite`, { method: "POST" });
    loadBank();
  };

  // ── 切换斩题 ──
  const handleToggleSlash = async (qId: string) => {
    await fetch(`/api/v7/practice/questions/${qId}/slash`, { method: "POST" });
    loadBank();
  };

  const totalPages = Math.ceil(total / pageSize);

  if (loading) {
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
          {editing ? (
            <div className="space-y-2">
              <input
                value={editName} onChange={(e) => setEditName(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-lg font-semibold"
              />
              <input
                value={editDesc} onChange={(e) => setEditDesc(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-500"
                placeholder="题库描述"
              />
              <div className="flex gap-2">
                <button onClick={handleUpdate} className="px-3 py-1 text-sm bg-indigo-500 text-white rounded-lg hover:bg-indigo-600">保存</button>
                <button onClick={() => setEditing(false)} className="px-3 py-1 text-sm rounded-lg border border-gray-300 dark:border-gray-600">取消</button>
              </div>
            </div>
          ) : (
            <div>
              <h1 className="text-xl font-semibold">{bank.name}</h1>
              {bank.description && <p className="text-sm text-gray-500 mt-1">{bank.description}</p>}
              <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                <span>共 {bank.real_count} 题</span>
                {bank.ref_node_id && <span>关联知识点: {bank.ref_node_id}</span>}
                <button onClick={() => setEditing(true)} className="text-indigo-500 hover:underline"><Edit3 className="w-3 h-3 inline mr-1" />编辑</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 操作栏 ── */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={searchText} onChange={(e) => setSearchText(e.target.value)}
            placeholder="搜索题目..."
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
          />
        </div>
        <select
          value={filterType} onChange={(e) => { setFilterType(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
        >
          <option value="">全部题型</option>
          <option value="single">单选</option>
          <option value="multiple">多选</option>
          <option value="judge">判断</option>
          <option value="fill">填空</option>
        </select>
        <button
          onClick={() => router.push(`/practice?skill=${bank.ref_node_id || ""}`)}
          className="px-3 py-2 rounded-lg bg-indigo-500 text-white text-sm hover:bg-indigo-600 flex items-center gap-1.5"
        >
          <Sparkles className="w-4 h-4" />开始练习
        </button>
      </div>

      {/* ── 题目列表 ── */}
      <div className="space-y-2">
        {questions.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <BookOpen className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>这个题库还没有题目</p>
            <p className="text-sm mt-1">去对话中说「帮我出题」或在练习中生成</p>
          </div>
        ) : (
          questions.filter(q => !searchText || q.stem.toLowerCase().includes(searchText.toLowerCase())).map((q) => (
            <div
              key={q.id}
              className="flex items-start gap-3 p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 hover:border-indigo-300 dark:hover:border-indigo-700 transition-colors group"
            >
              {/* 题型标签 */}
              <span className={`shrink-0 px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[q.question_type] || TYPE_COLORS.choice}`}>
                {TYPE_LABELS[q.question_type] || q.question_type}
              </span>

              {/* 题干 */}
              <div className="flex-1 min-w-0">
                <p className="text-sm line-clamp-2">{q.stem}</p>
                <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-400">
                  <span className={`inline-block w-2 h-2 rounded-full ${q.difficulty >= 4 ? "bg-red-400" : q.difficulty >= 3 ? "bg-amber-400" : "bg-green-400"}`} />
                  难度 {q.difficulty}/5
                  {q.is_slashed && <span className="text-gray-300 line-through">已斩</span>}
                </div>
              </div>

              {/* 操作按钮 */}
              <div className="shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={() => handleToggleFav(q.id)} className={`p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 ${q.is_favorite ? "text-amber-500" : "text-gray-400"}`}>
                  <Star className="w-4 h-4" fill={q.is_favorite ? "currentColor" : "none"} />
                </button>
                <button onClick={() => handleToggleSlash(q.id)} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400">
                  <Eye className="w-4 h-4" />
                </button>
                <button onClick={() => handleDelete(q.id)} className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-500">
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
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-sm disabled:opacity-30">上一页</button>
          <span className="text-sm text-gray-500">{page}/{totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-sm disabled:opacity-30">下一页</button>
        </div>
      )}
    </div>
  );
}
