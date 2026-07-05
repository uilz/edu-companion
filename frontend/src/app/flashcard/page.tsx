"use client";

/**
 * FlashCard 列表页 — 创建、筛选、批量操作
 * 依据 docs/modules/flashcard/overview.md §3 + ADR 0002
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { flashcardService, FlashCard, CardType, CardSource, CardStatus, CARD_TYPE_LABELS, CARD_SOURCE_LABELS, STATUS_LABELS } from "@/lib/api/flashcard-api";
import { FlashCardItem } from "./components/FlashCardItem";

export default function FlashCardListPage() {
  const router = useRouter();
  const [cards, setCards] = useState<FlashCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [total, setTotal] = useState(0);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [stats, setStats] = useState<any>(null);

  const loadCards = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = { limit: 100 };
      if (statusFilter !== "all") params.status = statusFilter;
      if (typeFilter !== "all") params.type = Number(typeFilter);
      if (sourceFilter !== "all") params.source = sourceFilter;
      const data = await flashcardService.list(params);
      let filtered = data.cards;
      if (search) {
        const q = search.toLowerCase();
        filtered = filtered.filter(
          (c) => c.front_text.toLowerCase().includes(q) || c.back_text.toLowerCase().includes(q),
        );
      }
      setCards(filtered);
      setTotal(data.total);
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await flashcardService.getStats();
      setStats(data);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    loadCards();
    loadStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, typeFilter, sourceFilter]);

  const handleDelete = async (cardId: string) => {
    if (!confirm("确认删除这张卡片？")) return;
    try {
      await flashcardService.delete(cardId);
      loadCards();
      loadStats();
    } catch (e: any) {
      alert(`删除失败: ${e.message}`);
    }
  };

  const handleSuspend = async (cardId: string) => {
    try { await flashcardService.suspend(cardId); loadCards(); }
    catch (e: any) { alert(`暂停失败: ${e.message}`); }
  };

  const handleResume = async (cardId: string) => {
    try { await flashcardService.resume(cardId); loadCards(); }
    catch (e: any) { alert(`恢复失败: ${e.message}`); }
  };

  const handleArchive = async (cardId: string) => {
    try { await flashcardService.archive(cardId); loadCards(); loadStats(); }
    catch (e: any) { alert(`归档失败: ${e.message}`); }
  };

  const handleReset = async (cardId: string) => {
    if (!confirm("确认重置调度历史？此操作不可撤销")) return;
    try { await flashcardService.reset(cardId); loadCards(); }
    catch (e: any) { alert(`重置失败: ${e.message}`); }
  };

  return (
    <div className="container mx-auto p-6 max-w-7xl">
      {/* 标题栏 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">📚 FlashCard 间隔重复记忆卡</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            基于知识点的可追溯复习材料 · FSRS 调度 · 多源提取
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => router.push("/flashcard/stats")}
            className="px-3 py-1.5 text-sm rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
          >
            统计
          </button>
          <button
            onClick={() => router.push("/flashcard/review")}
            className="px-3 py-1.5 text-sm rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
          >
            ▶ 开始复习
          </button>
          <button
            onClick={() => setShowCreateDialog(true)}
            className="px-3 py-1.5 text-sm rounded bg-emerald-600 text-white hover:bg-emerald-700"
          >
            + 新建卡片
          </button>
        </div>
      </div>

      {/* 统计卡片 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <StatCard label="卡片总量" value={String(stats.total)} />
          <StatCard label="今日到期" value={String(stats.due_today)} color="text-orange-500" />
          <StatCard label="7天内到期" value={String(stats.due_7d)} />
          <StatCard label="平均稳定性" value={stats.average_stability?.toFixed(2) ?? "—"} sub="天" />
        </div>
      )}

      {/* 筛选栏 */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <input
          type="text"
          placeholder="搜索卡片内容..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
        >
          <option value="all">全部状态</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
        >
          <option value="all">全部类型</option>
          {Object.entries(CARD_TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
        >
          <option value="all">全部来源</option>
          {Object.entries(CARD_SOURCE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <button
          onClick={() => { loadCards(); loadStats(); }}
          className="px-3 py-1.5 text-sm border border-[var(--color-border)] rounded hover:bg-[var(--color-surface-2)]"
        >
          ↻
        </button>
      </div>

      {/* 列表 */}
      {loading ? (
        <div className="text-center py-20 text-[var(--color-text-muted)]">加载中...</div>
      ) : error ? (
        <div className="text-red-500 py-8 text-center">⚠ {error}</div>
      ) : cards.length === 0 ? (
        <div className="border border-[var(--color-border)] bg-[var(--color-surface)] rounded-lg p-12 text-center">
          <div className="text-6xl mb-4">📝</div>
          <div className="text-lg font-medium mb-2">还没有卡片</div>
          <div className="text-sm text-[var(--color-text-muted)] mb-4">
            点击"新建卡片"创建第一张，或从错题本/对话文本导入
          </div>
          <button
            onClick={() => setShowCreateDialog(true)}
            className="px-4 py-2 text-sm rounded bg-emerald-600 text-white hover:bg-emerald-700"
          >
            + 新建卡片
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cards.map((c) => (
            <FlashCardItem
              key={c.id}
              card={c}
              onDelete={() => handleDelete(c.id)}
              onSuspend={() => handleSuspend(c.id)}
              onResume={() => handleResume(c.id)}
              onArchive={() => handleArchive(c.id)}
              onReset={() => handleReset(c.id)}
            />
          ))}
        </div>
      )}

      <div className="mt-4 text-xs text-[var(--color-text-muted)] text-right">
        共 {total} 张
      </div>

      {/* 创建对话框 */}
      {showCreateDialog && (
        <CreateCardDialog
          onClose={() => setShowCreateDialog(false)}
          onCreated={() => {
            setShowCreateDialog(false);
            loadCards();
            loadStats();
          }}
        />
      )}
    </div>
  );
}

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] rounded-lg p-3">
      <div className="text-[10px] text-[var(--color-text-muted)]">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color || ""}`}>
        {value}
        {sub && <span className="text-xs font-normal text-[var(--color-text-muted)] ml-1">{sub}</span>}
      </div>
    </div>
  );
}

// ── 创建对话框 ──

function CreateCardDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [type, setType] = useState<CardType>(1);
  const [source, setSource] = useState<CardSource>("manual");
  const [frontText, setFrontText] = useState("");
  const [backText, setBackText] = useState("");
  const [tags, setTags] = useState("");
  const [nodeIdsRaw, setNodeIdsRaw] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!frontText.trim()) {
      setError("正面内容不能为空");
      return;
    }
    const nodeIds = nodeIdsRaw.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
    if (nodeIds.length === 0) {
      setError("至少关联一个知识点 (linked_node_ids)");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const nodeLinkRoles: Record<string, "primary" | "secondary"> = {};
      nodeIds.forEach((n, i) => {
        nodeLinkRoles[n] = i === 0 ? "primary" : "secondary";
      });
      await flashcardService.create({
        type,
        source,
        front_text: frontText,
        back_text: backText,
        tags: tags.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean),
        linked_node_ids: nodeIds,
        node_link_roles: nodeLinkRoles,
        target_retention: 0.85,
      });
      onCreated();
    } catch (e: any) {
      setError(e.message || "创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[90vh] overflow-auto bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">新建 FlashCard</h2>
          <button onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            ✕
          </button>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium block mb-1">类型</label>
              <select
                value={type}
                onChange={(e) => setType(Number(e.target.value) as CardType)}
                className="w-full px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
              >
                {Object.entries(CARD_TYPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium block mb-1">来源</label>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value as CardSource)}
                className="w-full px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
              >
                {Object.entries(CARD_SOURCE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium block mb-1">正面 (问题)</label>
            <textarea
              value={frontText}
              onChange={(e) => setFrontText(e.target.value)}
              placeholder="问题或概念名..."
              rows={3}
              className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
            />
          </div>

          <div>
            <label className="text-sm font-medium block mb-1">反面 (答案)</label>
            <textarea
              value={backText}
              onChange={(e) => setBackText(e.target.value)}
              placeholder="答案或解释..."
              rows={4}
              className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
            />
          </div>

          <div>
            <label className="text-sm font-medium block mb-1">标签 (逗号分隔)</label>
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="例如: 高数, 极限, 重要"
              className="w-full px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
            />
          </div>

          <div>
            <label className="text-sm font-medium block mb-1">
              关联知识点 ID (必填, 逗号或空格分隔, 第一个为主)
            </label>
            <input
              value={nodeIdsRaw}
              onChange={(e) => setNodeIdsRaw(e.target.value)}
              placeholder="例如: node_abc, node_def"
              className="w-full px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
            />
          </div>

          {error && <div className="text-sm text-red-500">{error}</div>}

          <div className="flex justify-end gap-2">
            <button
              onClick={onClose}
              className="px-4 py-1.5 text-sm rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
            >
              取消
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="px-4 py-1.5 text-sm rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {submitting ? "创建中..." : "创建"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
