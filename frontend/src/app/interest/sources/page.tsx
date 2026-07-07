"use client";

/**
 * 信息源管理 — 系统内置 + 用户自定义 RSS/Atom + OPML 导入
 * 依据 docs/modules/interest-explorer/overview.md §5 + ADR 0007 决策 5
 */
import { useEffect, useState, useCallback } from "react";
import {
  Plus, Trash2, Rss, Upload, Loader2, AlertCircle, CheckCircle2,
  XCircle, ChevronLeft, RefreshCw, Settings as SettingsIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  interestService, InterestSource, SourceType,
} from "@/lib/api/interest-api";

const SOURCE_TYPE_LABELS: Record<SourceType, string> = {
  arxiv: "arXiv",
  biorxiv: "bioRxiv",
  rss: "RSS",
  atom: "Atom",
  opml: "OPML",
  internal: "内部",
};

export default function SourcesPage() {
  const router = useRouter();
  const [sources, setSources] = useState<InterestSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showOPML, setShowOPML] = useState(false);
  const [opmlText, setOpmlText] = useState("");
  const [busy, setBusy] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);

  const [newForm, setNewForm] = useState<{
    name: string;
    type: SourceType;
    category: string;
    feed_url: string;
  }>({ name: "", type: "rss", category: "", feed_url: "" });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await interestService.listSources();
      setSources(r.items);
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onCreate = async () => {
    if (!newForm.name.trim() || !newForm.feed_url.trim()) {
      setError("名称和 feed_url 必填");
      return;
    }
    setBusy(true);
    try {
      await interestService.createSource({
        name: newForm.name,
        type: newForm.type,
        category: newForm.category || undefined,
        config: { feed_url: newForm.feed_url },
        enabled: true,
      });
      setNewForm({ name: "", type: "rss", category: "", feed_url: "" });
      setShowCreate(false);
      await load();
    } catch (e: any) {
      setError(e.message || "创建失败");
    } finally {
      setBusy(false);
    }
  };

  const onToggle = async (src: InterestSource) => {
    setBusy(true);
    try {
      await interestService.enableSource(src.id, !src.enabled);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  };

  const onDelete = async (src: InterestSource) => {
    if (!confirm(`确定删除信息源 "${src.name}"？`)) return;
    setBusy(true);
    try {
      await interestService.deleteSource(src.id);
      await load();
    } catch (e: any) {
      setError(e.message || "删除失败");
    } finally {
      setBusy(false);
    }
  };

  const onImportOPML = async () => {
    if (!opmlText.trim()) {
      setError("OPML 内容不能为空");
      return;
    }
    setBusy(true);
    setImportResult(null);
    try {
      const r = await interestService.importOPML(opmlText);
      setImportResult(`成功导入 ${r.imported} 个，跳过 ${r.skipped} 个`);
      setOpmlText("");
      setShowOPML(false);
      await load();
    } catch (e: any) {
      setError(e.message || "导入失败");
    } finally {
      setBusy(false);
    }
  };

  const onFetchNow = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await interestService.triggerFetch();
      setImportResult(`全量抓取完成: ${r.total_items} 条新增, ${r.source_results?.length || 0} 个源`);
      await load();
    } catch (e: any) {
      setError(e.message || "抓取失败");
    } finally {
      setBusy(false);
    }
  };

  const builtin = sources.filter((s) => s.is_system);
  const userSrc = sources.filter((s) => !s.is_system);

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Rss className="w-6 h-6 text-info" />
            信息源管理
          </h1>
          <p className="text-sm text-muted mt-1">
            仅支持 RSS/Atom 标准协议 · 不支持任意 URL 抓取
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => router.push("/interest")}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-surface"
          >
            返回
          </button>
          <button
            onClick={onFetchNow}
            disabled={busy}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-surface flex items-center gap-1"
          >
            <RefreshCw className="w-4 h-4" />
            全量抓取
          </button>
          <button
            onClick={() => setShowOPML(true)}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-surface flex items-center gap-1"
          >
            <Upload className="w-4 h-4" />
            OPML
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-1.5 text-sm bg-info text-white rounded-lg hover:bg-info flex items-center gap-1"
          >
            <Plus className="w-4 h-4" />
            新增
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-danger/10 border border-danger/20 rounded-lg flex items-start gap-2 text-sm text-danger">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {importResult && (
        <div className="mb-4 p-3 bg-success/10 border border-success/20 rounded-lg flex items-start gap-2 text-sm text-success">
          <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{importResult}</span>
        </div>
      )}

      {showCreate && (
        <div className="mb-4 p-4 border-2 border-info/20 rounded-lg bg-info/10">
          <h3 className="font-medium mb-3 text-sm">新增信息源</h3>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted block mb-1">名称</label>
                <input
                  value={newForm.name}
                  onChange={(e) => setNewForm({ ...newForm, name: e.target.value })}
                  className="w-full px-3 py-2 border rounded text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted block mb-1">类型</label>
                <select
                  value={newForm.type}
                  onChange={(e) => setNewForm({ ...newForm, type: e.target.value as SourceType })}
                  className="w-full px-3 py-2 border rounded text-sm"
                >
                  <option value="rss">RSS</option>
                  <option value="atom">Atom</option>
                  <option value="arxiv">arXiv</option>
                  <option value="biorxiv">bioRxiv</option>
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs text-muted block mb-1">分类 (可选)</label>
              <input
                value={newForm.category}
                onChange={(e) => setNewForm({ ...newForm, category: e.target.value })}
                placeholder="如: 预印本 / 学术新闻 / 技术博客"
                className="w-full px-3 py-2 border rounded text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-muted block mb-1">feed_url</label>
              <input
                value={newForm.feed_url}
                onChange={(e) => setNewForm({ ...newForm, feed_url: e.target.value })}
                placeholder="https://example.com/feed.xml"
                className="w-full px-3 py-2 border rounded text-sm font-mono"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={onCreate}
                disabled={busy}
                className="px-3 py-1.5 text-sm bg-info text-white rounded hover:bg-info"
              >
                保存
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="px-3 py-1.5 text-sm border rounded hover:bg-surface"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {showOPML && (
        <div className="mb-4 p-4 border-2 border-info/20 rounded-lg bg-info/10">
          <h3 className="font-medium mb-3 text-sm">OPML 导入</h3>
          <p className="text-xs text-muted mb-2">
            粘贴 OPML XML 内容（仅解析 RSS/Atom 项，跳过其他类型）
          </p>
          <textarea
            value={opmlText}
            onChange={(e) => setOpmlText(e.target.value)}
            rows={10}
            placeholder="<opml version=&quot;2.0&quot;>..."
            className="w-full px-3 py-2 border rounded text-xs font-mono"
          />
          <div className="flex gap-2 mt-2">
            <button
              onClick={onImportOPML}
              disabled={busy}
              className="px-3 py-1.5 text-sm bg-info text-white rounded hover:bg-info"
            >
              导入
            </button>
            <button
              onClick={() => { setShowOPML(false); setOpmlText(""); }}
              className="px-3 py-1.5 text-sm border rounded hover:bg-surface"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-muted">
          <Loader2 className="w-8 h-8 mx-auto animate-spin" />
        </div>
      ) : (
        <>
          <div className="mb-6">
            <h2 className="text-sm font-medium text-muted mb-2 flex items-center gap-1">
              <SettingsIcon className="w-4 h-4" />
              系统内置源 ({builtin.length})
            </h2>
            <div className="space-y-2">
              {builtin.map((s) => (
                <SourceItem
                  key={s.id}
                  source={s}
                  busy={busy}
                  onToggle={() => onToggle(s)}
                />
              ))}
            </div>
          </div>

          <div>
            <h2 className="text-sm font-medium text-muted mb-2">
              用户自定义源 ({userSrc.length})
            </h2>
            {userSrc.length === 0 ? (
              <p className="text-xs text-muted text-center py-4">
                暂无自定义源
              </p>
            ) : (
              <div className="space-y-2">
                {userSrc.map((s) => (
                  <SourceItem
                    key={s.id}
                    source={s}
                    busy={busy}
                    onToggle={() => onToggle(s)}
                    onDelete={() => onDelete(s)}
                  />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function SourceItem({
  source,
  busy,
  onToggle,
  onDelete,
}: {
  source: InterestSource;
  busy: boolean;
  onToggle: () => void;
  onDelete?: () => void;
}) {
  const status = source.last_fetch_status;
  return (
    <div className="border rounded-lg p-3 bg-white flex items-start gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className="text-xs px-1.5 py-0.5 rounded bg-surface text">
            {SOURCE_TYPE_LABELS[source.type as SourceType] || source.type}
          </span>
          {source.category && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-info/10 text-info">
              {source.category}
            </span>
          )}
          {status === "success" && (
            <CheckCircle2 className="w-3.5 h-3.5 text-success" />
          )}
          {status === "error" && (
            <XCircle className="w-3.5 h-3.5 text-danger" />
          )}
        </div>
        <p className="font-medium text-sm">{source.name}</p>
        <p className="text-xs text-muted mt-0.5 truncate font-mono">
          {source.config?.feed_url}
        </p>
        {source.last_fetched_at && (
          <p className="text-xs text-muted mt-0.5">
            上次抓取: {new Date(source.last_fetched_at).toLocaleString("zh-CN")}
          </p>
        )}
        {source.last_fetch_error && (
          <p className="text-xs text-danger mt-0.5 truncate">
            错误: {source.last_fetch_error}
          </p>
        )}
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="flex items-center gap-1.5 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={source.enabled}
            onChange={onToggle}
            disabled={busy}
            className="rounded"
          />
          启用
        </label>
        {onDelete && (
          <button
            onClick={onDelete}
            className="text-xs text-danger hover:bg-danger/10 px-1.5 py-0.5 rounded"
          >
            <Trash2 className="w-3 h-3 inline" /> 删除
          </button>
        )}
      </div>
    </div>
  );
}
