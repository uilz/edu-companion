"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Brain, Clock, ChevronRight, Trash2, Filter,
  Loader2, ArrowUp, List, Grid3X3,
  RefreshCw,
} from "lucide-react";
import { api } from "@/lib/api/api";

type ViewMode = "detailed" | "compact";

export default function PracticeHistoryPage() {
  const router = useRouter();

  // 数据
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  // 筛选
  const [status, setStatus] = useState("completed");
  const [mode, setMode] = useState("");
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 30);
    return d.toISOString().slice(0, 10);
  });
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().slice(0, 10));
  const [scoreMin, setScoreMin] = useState("");
  const [scoreMax, setScoreMax] = useState("");

  // 排序
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState("desc");

  // 分页
  const [page, setPage] = useState(1);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [paginationMode, setPaginationMode] = useState<"page" | "cursor">("page");
  const [hasMore, setHasMore] = useState(false);
  const pageSize = 20;

  // UI
  const [viewMode, setViewMode] = useState<ViewMode>("detailed");
  const [showFilters, setShowFilters] = useState(false);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  // 题单列表（筛选用）
  const [banks, setBanks] = useState<any[]>([]);
  const [selectedBankId, setSelectedBankId] = useState("");

  // 加载题单
  useEffect(() => {
    api<any[]>("/api/practice/banks").then(data => {
      setBanks(Array.isArray(data) ? data : []);
    }).catch(() => {});
  }, []);

  // 用 ref 保存最新请求参数，避免闭包过期
  const paramsRef = useRef({
    status, mode, selectedBankId, dateFrom, dateTo,
    scoreMin, scoreMax, sortBy, sortOrder, page, paginationMode, nextCursor,
  });
  paramsRef.current = {
    status, mode, selectedBankId, dateFrom, dateTo,
    scoreMin, scoreMax, sortBy, sortOrder, page, paginationMode, nextCursor,
  };
  const loadingMoreRef = useRef(false);

  // 加载数据
  const loadData = async (isLoadMore = false) => {
    const p = paramsRef.current;
    if (isLoadMore) {
      if (loadingMoreRef.current) return;
      loadingMoreRef.current = true;
      setLoadingMore(true);
    } else {
      setLoading(true);
    }

    const qp = new URLSearchParams();
    if (p.status) qp.set("status", p.status);
    if (p.mode) qp.set("mode", p.mode);
    if (p.selectedBankId) qp.set("bank_id", p.selectedBankId);
    if (p.dateFrom) qp.set("date_from", p.dateFrom);
    if (p.dateTo) qp.set("date_to", p.dateTo + "T23:59:59Z");
    if (p.scoreMin) qp.set("score_min", p.scoreMin);
    if (p.scoreMax) qp.set("score_max", p.scoreMax);
    qp.set("sort_by", p.sortBy);
    qp.set("sort_order", p.sortOrder);

    if (p.paginationMode === "page") {
      qp.set("offset", String((p.page - 1) * pageSize));
      qp.set("limit", String(pageSize));
    } else {
      if (isLoadMore && p.nextCursor) qp.set("cursor", p.nextCursor);
      qp.set("limit", String(pageSize));
    }

    try {
      const data = await api<any>(`/api/practice/sessions?${qp}`);

      if (isLoadMore) {
        setItems(prev => [...prev, ...(data.items || [])]);
      } else {
        setItems(data.items || []);
      }
      if (data.total !== undefined) setTotal(data.total);
      setNextCursor(data.next_cursor || null);
      setHasMore(data.has_more || false);
    } catch (e) {
      console.error("加载历史记录失败", e);
    } finally {
      setLoading(false);
      loadingMoreRef.current = false;
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [status, mode, selectedBankId, dateFrom, dateTo, scoreMin, scoreMax, sortBy, sortOrder, page, paginationMode]);

  // 删除记录
  const handleDelete = async (sessionId: string) => {
    if (!confirm("确认删除此练习记录？删除后不可恢复。")) return;
    await api(`/api/practice/sessions/${sessionId}`, { method: "DELETE" });
    setItems(prev => prev.filter(s => s.session_id !== sessionId));
    if (total !== null) setTotal(total - 1);
  };

  // 滚动加载更多（通过 ref 避免闭包过期）
  const loadMoreRef = useRef<() => void>(() => {});
  loadMoreRef.current = () => {
    const p = paramsRef.current;
    if (p.paginationMode === "cursor" && hasMore && !loadingMoreRef.current) {
      loadData(true);
    }
  };

  useEffect(() => {
    const handleScroll = () => {
      setShowScrollTop(window.scrollY > 400);
      if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 600) {
        loadMoreRef.current();
      }
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // 格式化时长
  const fmtDuration = (sec: number | null) => {
    if (!sec) return "";
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return m > 0 ? `${m}分${s}秒` : `${s}秒`;
  };

  // 格式化日期
  const fmtDate = (iso: string | null) => {
    if (!iso) return "";
    const d = new Date(iso);
    return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  };

  // 模式中文名
  const modeName = (m: string) => {
    const map: Record<string, string> = {
      adaptive: "自适应练习", review: "复习模式", challenge: "挑战模式",
      targeted: "专项练习", exam: "模拟考试",
    };
    return map[m] || m;
  };

  // 分数颜色
  const scoreColor = (s: number | null) => {
    if (s === null) return "text-[var(--color-text-muted)]";
    if (s >= 80) return "text-green-500";
    if (s >= 60) return "text-yellow-500";
    return "text-red-500";
  };

  // 重置筛选
  const resetFilters = () => {
    setStatus("completed");
    setMode("");
    setSelectedBankId("");
    setDateFrom(new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10));
    setDateTo(new Date().toISOString().slice(0, 10));
    setScoreMin("");
    setScoreMax("");
    setPage(1);
    setNextCursor(null);
  };

  const hasActiveFilters = mode || selectedBankId || scoreMin || scoreMax;

  // 重置日期范围
  const resetDateRange = () => {
    setDateFrom("");
    setDateTo("");
    setPage(1);
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)]" ref={listRef}>
      {/* Top bar */}
      <div className="sticky top-0 z-30 bg-[var(--color-bg)]/90 backdrop-blur-sm border-b border-[var(--color-border)]/50">
        <div className="max-w-3xl mx-auto px-4 flex items-center h-12 gap-3">
          <button onClick={() => router.back()}
            className="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
            ← 返回
          </button>
          <span className="text-[11px] text-[var(--color-text-muted)]">|</span>
          <span className="text-[12px] font-medium text-[var(--color-text)]">练习历史</span>
          {total !== null && (
            <span className="text-[10px] text-[var(--color-text-muted)] ml-auto">共 {total} 条</span>
          )}
        </div>

        {/* 筛选栏 */}
        <div className="max-w-3xl mx-auto px-4 pb-2">
          <div className="flex items-center gap-2">
            <button onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-medium transition-colors ${
                showFilters || hasActiveFilters
                  ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                  : "bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              }`}>
              <Filter size={12} />
              筛选
              {hasActiveFilters && <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent)]" />}
            </button>

            {/* 模式切换 */}
            <div className="flex bg-[var(--color-surface)] rounded-lg overflow-hidden border border-[var(--color-border)]/50">
              <button onClick={() => { setPaginationMode("page"); setPage(1); }}
                className={`px-2.5 py-1.5 text-[10px] transition-colors ${
                  paginationMode === "page" ? "bg-[var(--color-accent)] text-white" : "text-[var(--color-text-muted)]"
                }`}>页码</button>
              <button onClick={() => { setPaginationMode("cursor"); setPage(1); }}
                className={`px-2.5 py-1.5 text-[10px] transition-colors ${
                  paginationMode === "cursor" ? "bg-[var(--color-accent)] text-white" : "text-[var(--color-text-muted)]"
                }`}>滚动</button>
            </div>

            {/* 视图切换 */}
            <div className="flex bg-[var(--color-surface)] rounded-lg overflow-hidden border border-[var(--color-border)]/50">
              <button onClick={() => setViewMode("detailed")}
                className={`p-1.5 transition-colors ${
                  viewMode === "detailed" ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "text-[var(--color-text-muted)]"
                }`} title="详细模式">
                <List size={14} />
              </button>
              <button onClick={() => setViewMode("compact")}
                className={`p-1.5 transition-colors ${
                  viewMode === "compact" ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "text-[var(--color-text-muted)]"
                }`} title="简明模式">
                <Grid3X3 size={14} />
              </button>
            </div>

            <div className="ml-auto" />

            {/* 排序 */}
            <select value={`${sortBy}|${sortOrder}`} onChange={e => {
              const [b, o] = e.target.value.split("|");
              setSortBy(b); setSortOrder(o);
            }}
              className="text-[10px] bg-[var(--color-surface)] border border-[var(--color-border)]/50 rounded-lg px-2 py-1.5 text-[var(--color-text)]">
              <option value="created_at|desc">最新</option>
              <option value="created_at|asc">最早</option>
              <option value="score|desc">高分↓</option>
              <option value="score|asc">低分↑</option>
              <option value="duration_seconds|desc">最长↓</option>
              <option value="total_count|desc">题量↓</option>
            </select>

            <button onClick={resetFilters}
              className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
              title="重置筛选">
              <RefreshCw size={12} />
            </button>
          </div>

          {/* 筛选面板 */}
          {showFilters && (
            <div className="mt-2 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 space-y-2">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div>
                  <label className="text-[9px] text-[var(--color-text-muted)] block mb-1">状态</label>
                  <select value={status} onChange={e => setStatus(e.target.value)}
                    className="w-full text-[10px] bg-[var(--color-bg)] border border-[var(--color-border)]/50 rounded-lg px-2 py-1.5 text-[var(--color-text)]">
                    <option value="">全部</option>
                    <option value="completed">已完成</option>
                    <option value="cancelled">已取消</option>
                    <option value="timeout">超时</option>
                  </select>
                </div>
                <div>
                  <label className="text-[9px] text-[var(--color-text-muted)] block mb-1">模式</label>
                  <select value={mode} onChange={e => setMode(e.target.value)}
                    className="w-full text-[10px] bg-[var(--color-bg)] border border-[var(--color-border)]/50 rounded-lg px-2 py-1.5 text-[var(--color-text)]">
                    <option value="">全部</option>
                    <option value="adaptive">自适应</option>
                    <option value="review">复习</option>
                    <option value="challenge">挑战</option>
                    <option value="targeted">专项</option>
                    <option value="exam">考试</option>
                  </select>
                </div>
                <div>
                  <label className="text-[9px] text-[var(--color-text-muted)] block mb-1">题单</label>
                  <select value={selectedBankId} onChange={e => setSelectedBankId(e.target.value)}
                    className="w-full text-[10px] bg-[var(--color-bg)] border border-[var(--color-border)]/50 rounded-lg px-2 py-1.5 text-[var(--color-text)]">
                    <option value="">全部</option>
                    {banks.map((b: any) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-[9px] text-[var(--color-text-muted)] block mb-1">正确率</label>
                  <div className="flex items-center gap-1">
                    <input type="number" placeholder="最低" value={scoreMin} onChange={e => setScoreMin(e.target.value)}
                      className="w-full text-[10px] bg-[var(--color-bg)] border border-[var(--color-border)]/50 rounded-lg px-2 py-1.5 text-[var(--color-text)]" />
                    <span className="text-[10px] text-[var(--color-text-muted)]">~</span>
                    <input type="number" placeholder="最高" value={scoreMax} onChange={e => setScoreMax(e.target.value)}
                      className="w-full text-[10px] bg-[var(--color-bg)] border border-[var(--color-border)]/50 rounded-lg px-2 py-1.5 text-[var(--color-text)]" />
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[9px] text-[var(--color-text-muted)] block mb-1">开始日期</label>
                    <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                      className="w-full text-[10px] bg-[var(--color-bg)] border border-[var(--color-border)]/50 rounded-lg px-2 py-1.5 text-[var(--color-text)]" />
                  </div>
                  <div>
                    <label className="text-[9px] text-[var(--color-text-muted)] block mb-1">结束日期</label>
                    <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
                      className="w-full text-[10px] bg-[var(--color-bg)] border border-[var(--color-border)]/50 rounded-lg px-2 py-1.5 text-[var(--color-text)]" />
                  </div>
                </div>
                {/* 日期快捷选择 */}
                <div className="flex items-center gap-1.5">
                  <span className="text-[9px] text-[var(--color-text-muted)]">快捷：</span>
                  <button onClick={() => { setDateFrom(new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10)); setDateTo(new Date().toISOString().slice(0, 10)); }}
                    className="px-2 py-1 rounded text-[9px] bg-[var(--color-bg)] border border-[var(--color-border)]/50 text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-accent)]/30 transition-colors">
                    最近 7 天
                  </button>
                  <button onClick={() => { setDateFrom(new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10)); setDateTo(new Date().toISOString().slice(0, 10)); }}
                    className="px-2 py-1 rounded text-[9px] bg-[var(--color-bg)] border border-[var(--color-border)]/50 text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-accent)]/30 transition-colors">
                    最近 30 天
                  </button>
                  <button onClick={() => { setDateFrom(new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10)); setDateTo(new Date().toISOString().slice(0, 10)); }}
                    className="px-2 py-1 rounded text-[9px] bg-[var(--color-bg)] border border-[var(--color-border)]/50 text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-accent)]/30 transition-colors">
                    最近 90 天
                  </button>
                  <button onClick={() => { const d = new Date(); d.setDate(1); setDateFrom(d.toISOString().slice(0, 10)); setDateTo(new Date().toISOString().slice(0, 10)); }}
                    className="px-2 py-1 rounded text-[9px] bg-[var(--color-bg)] border border-[var(--color-border)]/50 text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-accent)]/30 transition-colors">
                    本月
                  </button>
                  <button onClick={() => { resetDateRange(); }}
                    className="px-2 py-1 rounded text-[9px] bg-[var(--color-bg)] border border-[var(--color-border)]/50 text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-accent)]/30 transition-colors">
                    不限
                  </button>
                </div>
            </div>
          )}
        </div>
      </div>

      {/* 列表 */}
      <div className="max-w-3xl mx-auto px-4 py-4">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-20">
            <Brain size={24} className="mx-auto text-[var(--color-text-muted)] mb-3" />
            <p className="text-[13px] text-[var(--color-text-muted)]">暂无练习记录</p>
            <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
              {hasActiveFilters ? "试试调整筛选条件" : "快去开始练习吧"}
            </p>
          </div>
        ) : (
          <>
            <div className="space-y-2">
              {items.map((s: any) => (
                viewMode === "detailed" ? (
                  // ── 详细模式 ──
                  <div key={s.session_id}
                    onClick={() => router.push(`/practice/history/${s.session_id}`)}
                    className="flex items-center gap-3 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30 cursor-pointer transition-all group">
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      (s.score || 0) >= 80 ? "bg-green-500/10" :
                      (s.score || 0) >= 60 ? "bg-yellow-500/10" : "bg-red-500/10"
                    }`}>
                      <Brain size={15} className={
                        (s.score || 0) >= 80 ? "text-green-500" :
                        (s.score || 0) >= 60 ? "text-yellow-500" : "text-red-500"
                      } />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[12px] font-medium text-[var(--color-text)]">
                          {s.bank_name || modeName(s.mode)}
                        </span>
                        <span className="text-[9px] text-[var(--color-text-muted)] bg-[var(--color-bg)] px-1.5 py-0.5 rounded">
                          {modeName(s.mode)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 mt-0.5 text-[10px] text-[var(--color-text-muted)]">
                        <span>{fmtDate(s.started_at || s.created_at)}</span>
                        <span>·</span>
                        <span>{s.total_count} 题 · {s.correct_count}/{s.wrong_count}</span>
                        {s.duration_seconds && <>
                          <span>·</span>
                          <Clock size={10} className="inline" />
                          <span>{fmtDuration(s.duration_seconds)}</span>
                        </>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={`text-[14px] font-bold ${scoreColor(s.score)}`}>
                        {s.score ?? "—"}
                      </span>
                      <button onClick={(e) => { e.stopPropagation(); handleDelete(s.session_id); }}
                        className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-500/10 text-[var(--color-text-muted)] hover:text-red-500 transition-all"
                        title="删除">
                        <Trash2 size={12} />
                      </button>
                      <ChevronRight size={14} className="text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </div>
                ) : (
                  // ── 简明模式 ──
                  <div key={s.session_id}
                    onClick={() => router.push(`/practice/history/${s.session_id}`)}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30 cursor-pointer transition-all group text-[11px]">
                    <span className={`font-bold w-8 text-right ${scoreColor(s.score)}`}>{s.score ?? "—"}</span>
                    <span className="text-[var(--color-text)] truncate flex-1">
                      {s.bank_name || modeName(s.mode)}
                    </span>
                    <span className="text-[var(--color-text-muted)]">{s.total_count}题</span>
                    <span className="text-[var(--color-text-muted)]">{fmtDate(s.created_at)}</span>
                    <button onClick={(e) => { e.stopPropagation(); handleDelete(s.session_id); }}
                      className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/10 text-[var(--color-text-muted)] hover:text-red-500 transition-all">
                      <Trash2 size={10} />
                    </button>
                  </div>
                )
              ))}
            </div>

            {/* 页码分页 */}
            {paginationMode === "page" && total !== null && total > pageSize && (
              <div className="flex items-center justify-center gap-2 mt-6">
                {Array.from({ length: Math.ceil(total / pageSize) }, (_, i) => i + 1).map(p => (
                  <button key={p} onClick={() => setPage(p)}
                    className={`w-7 h-7 rounded-lg text-[11px] font-medium transition-colors ${
                      p === page
                        ? "bg-[var(--color-accent)] text-white"
                        : "bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                    }`}>
                    {p}
                  </button>
                ))}
              </div>
            )}

            {/* 加载更多指示 */}
            {loadingMore && (
              <div className="flex items-center justify-center py-6">
                <Loader2 size={16} className="animate-spin text-[var(--color-text-muted)]" />
              </div>
            )}
          </>
        )}
      </div>

      {/* 回到顶部 */}
      {showScrollTop && (
        <button onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="fixed bottom-20 right-4 w-9 h-9 rounded-full bg-[var(--color-accent)] text-white shadow-lg flex items-center justify-center hover:opacity-90 transition-opacity z-40">
          <ArrowUp size={16} />
        </button>
      )}
    </div>
  );
}
