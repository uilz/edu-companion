"use client";

/**
 * InterestExplorer 探索面板 — 今日推送 + 历史
 * 依据 docs/modules/interest-explorer/overview.md + ADR 0007
 */
import { useEffect, useState, useCallback } from "react";
import {
  Search, Filter, RefreshCw, Loader2, AlertCircle,
  Calendar, ExternalLink, BookOpen, GitBranch, FileText,
  CheckCircle2, XCircle, Bookmark, Heart, Sparkles,
  Eye, History as HistoryIcon, Settings as SettingsIcon, Tag as TagIcon,
  Rss, Scale, ChevronRight,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  interestService,
  PUSH_TYPE_LABELS, PUSH_TYPE_COLORS,
  FEEDBACK_LABELS, FEEDBACK_COLORS,
  IMPORT_TARGET_LABELS, IMPORT_TARGET_ICONS,
  InterestPush, ImportTarget, PushFeedback, PushType,
} from "@/lib/api/interest-api";

const ALL_TARGETS: ImportTarget[] = [
  "reading", "project", "flashcard", "cognitive_node", "language_room",
];

export default function InterestExplorerPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"today" | "history">("today");
  const [today, setToday] = useState<{ items: InterestPush[]; date: string; total: number } | null>(null);
  const [history, setHistory] = useState<{
    items: InterestPush[]; total: number; limit: number; offset: number;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState<"" | PushType>("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const loadToday = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await interestService.getTodayPushes();
      setToday(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await interestService.getHistory({
        push_type: typeFilter || undefined,
        limit: 50,
      });
      setHistory(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [typeFilter]);

  useEffect(() => {
    if (activeTab === "today") {
      loadToday();
    } else {
      loadHistory();
    }
  }, [activeTab, loadToday, loadHistory]);

  const onFeedback = async (
    push: InterestPush,
    feedback: PushFeedback,
  ) => {
    setBusyId(push.id);
    try {
      await interestService.recordFeedback(push.id, { feedback });
      if (activeTab === "today") {
        await loadToday();
      } else {
        await loadHistory();
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  };

  const onImport = async (push: InterestPush, target: ImportTarget) => {
    setBusyId(push.id);
    try {
      await interestService.importPush(push.id, target);
      if (activeTab === "today") {
        await loadToday();
      } else {
        await loadHistory();
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "导入失败");
    } finally {
      setBusyId(null);
    }
  };

  const onTriggerPush = async () => {
    setBusyId("trigger");
    try {
      const r = await interestService.triggerPush();
      setError(null);
      await loadToday();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "触发推送失败");
    } finally {
      setBusyId(null);
    }
  };

  const items = activeTab === "today" ? (today?.items ?? []) : (history?.items ?? []);
  const filtered = searchTerm
    ? items.filter(
        (i) =>
          i.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
          (i.summary || "").toLowerCase().includes(searchTerm.toLowerCase()),
      )
    : items;

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-info" />
            学术信息探索
          </h1>
          <div className="flex gap-2">
            <button
              onClick={() => router.push("/interest/tags")}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-surface flex items-center gap-1"
            >
              <TagIcon className="w-4 h-4" />
              标签
            </button>
            <button
              onClick={() => router.push("/interest/sources")}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-surface flex items-center gap-1"
            >
              <Rss className="w-4 h-4" />
              信息源
            </button>
            <button
              onClick={() => router.push("/interest/prefs")}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-surface flex items-center gap-1"
            >
              <SettingsIcon className="w-4 h-4" />
              偏好
            </button>
            <button
              onClick={() => router.push("/interest/weight")}
              className="px-3 py-1.5 text-sm border rounded-lg hover:bg-surface flex items-center gap-1"
            >
              <Scale className="w-4 h-4" />
              本地权重
            </button>
          </div>
        </div>
        <p className="text-sm text-muted">
          严格遵循 ADR 0007: 不调用 LLM · 链接级别去重 · 本地权重
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b mb-4">
        <button
          onClick={() => setActiveTab("today")}
          className={`px-4 py-2 text-sm font-medium border-b-2 ${
            activeTab === "today"
              ? "border-info text-info"
              : "border-transparent text-muted hover:text"
          }`}
        >
          <Eye className="w-4 h-4 inline mr-1" />
          今日推送
          {today && <span className="ml-2 text-xs">({today.total})</span>}
        </button>
        <button
          onClick={() => setActiveTab("history")}
          className={`px-4 py-2 text-sm font-medium border-b-2 ${
            activeTab === "history"
              ? "border-info text-info"
              : "border-transparent text-muted hover:text"
          }`}
        >
          <HistoryIcon className="w-4 h-4 inline mr-1" />
          历史
          {history && <span className="ml-2 text-xs">({history.total})</span>}
        </button>
      </div>

      {/* Search + Actions */}
      <div className="flex items-center gap-2 mb-4">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="text"
            placeholder="搜索标题或摘要..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-3 py-2 border rounded-lg text-sm"
          />
        </div>
        {activeTab === "history" && (
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as "" | PushType)}
            className="px-3 py-2 border rounded-lg text-sm"
          >
            <option value="">全部类型</option>
            {(Object.keys(PUSH_TYPE_LABELS) as PushType[]).map((k) => (
              <option key={k} value={k}>{PUSH_TYPE_LABELS[k]}</option>
            ))}
          </select>
        )}
        <button
          onClick={activeTab === "today" ? loadToday : loadHistory}
          disabled={loading}
          className="px-3 py-2 border rounded-lg text-sm hover:bg-surface flex items-center gap-1"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
        {activeTab === "today" && (
          <button
            onClick={onTriggerPush}
            disabled={busyId === "trigger"}
            className="px-3 py-2 bg-info text-white rounded-lg text-sm hover:bg-info flex items-center gap-1"
          >
            {busyId === "trigger" ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            立即推送
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-danger/10 border border-danger/20 rounded-lg flex items-start gap-2 text-sm text-danger">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-muted">
          <Loader2 className="w-8 h-8 mx-auto animate-spin mb-2" />
          加载中...
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-muted">
          <Sparkles className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>暂无推送内容</p>
          <p className="text-xs mt-1">配置兴趣标签和信息源后会显示推送</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((push) => (
            <PushItem
              key={push.id}
              push={push}
              expanded={expandedId === push.id}
              busy={busyId === push.id}
              onToggle={() => setExpandedId(expandedId === push.id ? null : push.id)}
              onFeedback={(fb) => onFeedback(push, fb)}
              onImport={(target) => onImport(push, target)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function PushItem({
  push,
  expanded,
  busy,
  onToggle,
  onFeedback,
  onImport,
}: {
  push: InterestPush;
  expanded: boolean;
  busy: boolean;
  onToggle: () => void;
  onFeedback: (fb: PushFeedback) => void;
  onImport: (target: ImportTarget) => void;
}) {
  return (
    <div className="border rounded-lg overflow-hidden bg-white">
      <button
        onClick={onToggle}
        className="w-full p-4 text-left hover:bg-surface"
      >
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span
                className={`text-xs px-2 py-0.5 rounded ${PUSH_TYPE_COLORS[push.push_type]}`}
              >
                {PUSH_TYPE_LABELS[push.push_type]}
              </span>
              {push.feedback && (
                <span
                  className={`text-xs px-2 py-0.5 rounded ${FEEDBACK_COLORS[push.feedback]}`}
                >
                  {FEEDBACK_LABELS[push.feedback]}
                </span>
              )}
              {push.matched_tags.length > 0 && (
                <span className="text-xs text-muted">
                  匹配 {push.matched_tags.length} 个标签
                </span>
              )}
            </div>
            <h3 className="font-medium text-sm line-clamp-2">{push.title}</h3>
            {push.summary && !expanded && (
              <p className="text-xs text-muted mt-1 line-clamp-2">
                {push.summary}
              </p>
            )}
            <div className="text-xs text-muted mt-1 flex items-center gap-3 flex-wrap">
              {push.author && <span>👤 {push.author}</span>}
              {push.published_at && (
                <span>
                  <Calendar className="w-3 h-3 inline mr-0.5" />
                  {new Date(push.published_at).toLocaleDateString("zh-CN")}
                </span>
              )}
              {push.url && (
                <span className="truncate max-w-xs">🔗 {new URL(push.url).hostname}</span>
              )}
            </div>
          </div>
          <ChevronRight
            className={`w-4 h-4 text-muted shrink-0 transition-transform ${
              expanded ? "rotate-90" : ""
            }`}
          />
        </div>
      </button>

      {expanded && (
        <div className="border-t p-4 bg-surface space-y-3">
          {push.summary && (
            <div>
              <p className="text-xs text-muted mb-1">原文摘要</p>
              <p className="text-sm text whitespace-pre-wrap">
                {push.summary}
              </p>
            </div>
          )}

          {push.url && (
            <a
              href={push.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-info hover:underline"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              打开原文
            </a>
          )}

          {/* 反馈按钮 */}
          <div>
            <p className="text-xs text-muted mb-1.5">反馈</p>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => onFeedback("read")}
                disabled={busy}
                className="px-3 py-1.5 text-xs border rounded hover:bg-white flex items-center gap-1"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                已读
              </button>
              <button
                onClick={() => onFeedback("later")}
                disabled={busy}
                className="px-3 py-1.5 text-xs border rounded hover:bg-white flex items-center gap-1"
              >
                <Bookmark className="w-3.5 h-3.5" />
                稍后读 (FlashCard 临时状态)
              </button>
              <button
                onClick={() => onFeedback("dislike")}
                disabled={busy}
                className="px-3 py-1.5 text-xs border rounded hover:bg-white flex items-center gap-1"
              >
                <XCircle className="w-3.5 h-3.5" />
                不感兴趣 (本地权重)
              </button>
            </div>
          </div>

          {/* 跨模块导入 */}
          <div>
            <p className="text-xs text-muted mb-1.5">
              导入到 5 个目标模块（CrossModuleTarget）
            </p>
            <div className="flex gap-2 flex-wrap">
              {ALL_TARGETS.map((target) => (
                <button
                  key={target}
                  onClick={() => onImport(target)}
                  disabled={busy}
                  className="px-3 py-1.5 text-xs border rounded hover:bg-white flex items-center gap-1"
                  title={IMPORT_TARGET_LABELS[target]}
                >
                  <span>{IMPORT_TARGET_ICONS[target]}</span>
                  {IMPORT_TARGET_LABELS[target]}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
