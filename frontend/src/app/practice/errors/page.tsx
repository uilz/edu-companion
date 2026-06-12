"use client";

import { useState, useEffect, useCallback } from "react";
import {
  RotateCcw, CheckCircle, XCircle, Loader2, BookOpen,
  ChevronDown, ChevronUp, Brain, Trash2, ChevronLeft, ChevronRight,
  BarChart3, AlertTriangle, Filter,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import {
  getErrorBook, getErrorBookStats, clearMasteredErrors,
  createPracticeSession, resolveBankForNode,
  type ErrorBookItem, type ErrorBookStats as EBStats,
} from "@/lib/api/practice-api";
import QuestionStem from "@/components/practice/components/QuestionStem";

export default function ErrorBookPage() {
  const [items, setItems] = useState<ErrorBookItem[]>([]);
  const [stats, setStats] = useState<EBStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("wrongs_desc");
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const [coldStart, setColdStart] = useState(false);

  const loadData = useCallback(async (p: number) => {
    setLoading(true);
    try {
      const [book, bookStats] = await Promise.all([
        getErrorBook({ page: p, page_size: 20, sort_by: sortBy }),
        getErrorBookStats(),
      ]);
      setItems(book.items);
      setTotal(book.total);
      setTotalPages(book.total_pages);
      setColdStart(!!book.cold_start);
      setStats(bookStats);
    } catch { /* ignore */ }
    setLoading(false);
  }, [sortBy]);

  useEffect(() => { loadData(page); }, [page, sortBy, loadData]);

  const handleClearMastered = useCallback(async () => {
    setClearing(true);
    try {
      await clearMasteredErrors();
      loadData(page);
    } catch { /* ignore */ }
    setClearing(false);
  }, [page, loadData]);

  const handleCreateReviewSession = useCallback(async (item: ErrorBookItem) => {
    try {
      // 找到对应的 bank
      const nodeId = item.cognitive_node_ids?.[0];
      let bankId = item.bank_id;
      if (nodeId) {
        const resolved = await resolveBankForNode(nodeId);
        bankId = resolved.bank_id;
      }
      const sess = await createPracticeSession(bankId, {
        mode: "review", count: 5,
        cognitive_node_ids: nodeId ? [nodeId] : undefined,
      });
      window.location.href = `/practice/sessions/${sess.session_id}`;
    } catch { /* ignore */ }
  }, []);

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <h1 className="text-2xl font-semibold text-[var(--color-text)] mb-6 tracking-tight">
          错题本
        </h1>

        {/* 统计卡片 */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            {[
              { icon: <XCircle size={18} />, label: "错题", value: stats.unique_wrong_questions, color: "text-red-500" },
              { icon: <RotateCcw size={18} />, label: "总错误次数", value: stats.total_wrong_attempts, color: "text-amber-500" },
              { icon: <CheckCircle size={18} />, label: "已掌握", value: stats.mastered_from_errors, color: "text-green-500" },
              { icon: <AlertTriangle size={18} />, label: "仍需巩固", value: stats.still_weak, color: "text-orange-500" },
            ].map((c, i) => (
              <div key={i} className="p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/60">
                <div className={c.color}>{c.icon}</div>
                <div className="text-xl font-bold text-[var(--color-text)] mt-1">{c.value}</div>
                <div className="text-[10px] text-[var(--color-text-muted)]">{c.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* 工具栏 */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <select
              value={sortBy}
              onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
              className="text-[11px] px-2 py-1.5 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-[var(--color-text)]"
            >
              <option value="wrongs_desc">错误最多</option>
              <option value="wrongs_asc">错误最少</option>
              <option value="last_wrong_desc">最近错误</option>
              <option value="difficulty_desc">难度最高</option>
            </select>
            <span className="text-[11px] text-[var(--color-text-muted)]">共 {total} 道</span>
          </div>
          <button
            onClick={handleClearMastered}
            disabled={clearing}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-[11px] text-[var(--color-text-muted)] hover:text-red-500 transition-colors"
          >
            <Trash2 size={12} />{clearing ? "清理中..." : "清除已掌握"}
          </button>
        </div>

        {/* 错题列表 */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-16 rounded-2xl border border-[var(--color-border)]/40 bg-[var(--color-surface)]/50">
            {coldStart ? (
              <>
                <BookOpen size={32} className="text-blue-500 mx-auto mb-3" />
                <p className="text-sm text-[var(--color-text)] font-medium">还没有错题记录</p>
                <p className="text-xs text-[var(--color-text-muted)] mt-1">
                  刚开始练习时不会产生错题，开始你的第一次练习吧
                </p>
                <a
                  href="/practice"
                  className="inline-flex items-center gap-1.5 mt-4 px-4 py-2 rounded-lg bg-blue-500 text-white text-sm font-medium hover:bg-blue-600 transition-colors"
                >
                  <Brain size={14} />开始练习
                </a>
              </>
            ) : (
              <>
                <CheckCircle size={32} className="text-green-500 mx-auto mb-3" />
                <p className="text-sm text-[var(--color-text)] font-medium">没有错题！</p>
                <p className="text-xs text-[var(--color-text-muted)] mt-1">继续保持</p>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => {
              const isExpanded = expandedId === item.question_id;
              return (
                <div key={item.question_id}
                  className={`rounded-xl border transition-all ${
                    item.mastered
                      ? "border-green-500/20 bg-green-500/5"
                      : "border-[var(--color-border)]/60 bg-[var(--color-surface)]"
                  }`}>
                  {/* 折叠头 */}
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : item.question_id)}
                    className="w-full flex items-start gap-3 p-4 text-left"
                  >
                    <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${
                      item.mastered
                        ? "bg-green-500/10 text-green-500"
                        : "bg-red-500/10 text-red-500"
                    }`}>
                      {item.wrong_count}
                    </div>
                    <div className="flex-1 min-w-0">
                      <QuestionStem stem={item.stem} className="text-sm leading-relaxed" />
                      <div className="flex items-center gap-3 mt-1.5 text-[10px] text-[var(--color-text-muted)]">
                        <span>难度: {"★".repeat(item.difficulty).padEnd(5, "☆")}</span>
                        <span>错 {item.wrong_count}/{item.total_attempts} 次</span>
                        {item.mastered && <span className="text-green-500">✓ 已掌握</span>}
                        {!item.mastered && <span className="text-red-500">⚡ 需巩固</span>}
                      </div>
                    </div>
                    <div className="flex-shrink-0 flex items-center gap-2">
                      <div
                        onClick={(e) => { e.stopPropagation(); handleCreateReviewSession(item); }}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[var(--color-accent)] text-white text-[10px] font-medium hover:opacity-90 transition-opacity"
                      >
                        <RotateCcw size={10} />复习
                      </div>
                      {isExpanded ? <ChevronUp size={14} className="text-[var(--color-text-muted)]" /> : <ChevronDown size={14} className="text-[var(--color-text-muted)]" />}
                    </div>
                  </button>

                  {/* 展开详情 */}
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-0 border-t border-[var(--color-border)]/30 mt-0">
                      {/* 选项回顾 */}
                      {item.options?.length > 0 && (
                        <div className="mt-3 space-y-1.5">
                          {item.options.map((opt) => (
                            <div key={opt.letter}
                              className={`flex items-start gap-2 p-2 rounded-lg text-xs ${
                                opt.is_correct
                                  ? "bg-green-500/10 text-green-600"
                                  : "bg-[var(--color-bg)] text-[var(--color-text-muted)]"
                              }`}>
                              <span className="flex-shrink-0 font-medium">{opt.letter}.</span>
                              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} components={{ p: ({ children }) => <>{children}</> }}>
                                {opt.text}
                              </ReactMarkdown>
                              {opt.is_correct && <CheckCircle size={10} className="flex-shrink-0 mt-0.5" />}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* 解析 */}
                      {item.analysis && (
                        <div className="mt-3 p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]/30">
                          <p className="text-[10px] font-medium text-[var(--color-text-muted)] mb-1">解析</p>
                          <div className="text-xs text-[var(--color-text)] leading-relaxed [&_p]:m-0 [&_.katex]:text-xs">
                            <QuestionStem stem={item.analysis} />
                          </div>
                        </div>
                      )}

                      {/* 统计信息 */}
                      <div className="flex items-center gap-4 mt-3 text-[10px] text-[var(--color-text-muted)]">
                        <span>难度: {item.difficulty}/5</span>
                        <span>总尝试: {item.total_attempts}次</span>
                        <span>错误率: {item.wrong_rate}%</span>
                        {item.last_wrong && <span>最近错误: {item.last_wrong.slice(0, 10)}</span>}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* 分页 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="p-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 disabled:opacity-30"
            >
              <ChevronLeft size={14} />
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <button
                key={p}
                onClick={() => setPage(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  p === page
                    ? "bg-[var(--color-accent)] text-white"
                    : "bg-[var(--color-surface)] border border-[var(--color-border)]/60 text-[var(--color-text-muted)]"
                }`}
              >
                {p}
              </button>
            ))}
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="p-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/60 disabled:opacity-30"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
