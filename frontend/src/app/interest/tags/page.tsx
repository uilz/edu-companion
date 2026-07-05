"use client";

/**
 * 兴趣标签管理 — 3 层树形结构
 * 依据 docs/modules/interest-explorer/data-model.md + ADR 0007 决策 9
 */
import { useEffect, useState, useCallback } from "react";
import {
  Plus, Trash2, Edit3, Save, X, Tag as TagIcon, Loader2,
  ChevronRight, ChevronDown, AlertCircle, Sparkles, GitBranch,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  interestService, InterestTag, TagLevel, TagWeight,
} from "@/lib/api/interest-api";

const LEVEL_LABELS: Record<TagLevel, string> = {
  0: "一级领域",
  1: "二级方向",
  2: "三级主题",
};

const LEVEL_COLORS: Record<TagLevel, string> = {
  0: "bg-blue-100 text-blue-700 border-blue-200",
  1: "bg-purple-100 text-purple-700 border-purple-200",
  2: "bg-green-100 text-green-700 border-green-200",
};

export default function TagsPage() {
  const router = useRouter();
  const [tags, setTags] = useState<InterestTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<{ name: string; weight: TagWeight; color: string }>({
    name: "", weight: 1, color: "",
  });
  const [showCreate, setShowCreate] = useState(false);
  const [newForm, setNewForm] = useState<{
    name: string;
    level: TagLevel;
    parent_id: string | null;
    weight: TagWeight;
    color: string;
  }>({ name: "", level: 0, parent_id: null, weight: 1, color: "" });
  const [busy, setBusy] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await interestService.listTags();
      setTags(r.items);
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onCreate = async () => {
    if (!newForm.name.trim()) {
      setError("名称必填");
      return;
    }
    setBusy(true);
    try {
      await interestService.createTag(newForm);
      setNewForm({ name: "", level: 0, parent_id: null, weight: 1, color: "" });
      setShowCreate(false);
      await load();
    } catch (e: any) {
      setError(e.message || "创建失败");
    } finally {
      setBusy(false);
    }
  };

  const onDelete = async (id: string) => {
    if (!confirm("确定删除该标签？子标签也会被删除")) return;
    setBusy(true);
    try {
      await interestService.deleteTag(id);
      await load();
    } catch (e: any) {
      setError(e.message || "删除失败");
    } finally {
      setBusy(false);
    }
  };

  const onEdit = (tag: InterestTag) => {
    setEditingId(tag.id);
    setEditForm({
      name: tag.name,
      weight: (tag.weight as TagWeight) || 1,
      color: tag.color || "",
    });
  };

  const onSaveEdit = async () => {
    if (!editingId) return;
    setBusy(true);
    try {
      await interestService.updateTag(editingId, editForm);
      setEditingId(null);
      await load();
    } catch (e: any) {
      setError(e.message || "更新失败");
    } finally {
      setBusy(false);
    }
  };

  const toggleExpand = (id: string) => {
    const next = new Set(expandedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setExpandedIds(next);
  };

  // 收集所有可作为父标签的标签
  const flatAll = useFlatTags(tags);

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <TagIcon className="w-6 h-6 text-blue-500" />
            兴趣标签
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            3 层结构 · 主/次权重 · 独立于知识图谱存储
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => router.push("/interest")}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50"
          >
            返回
          </button>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="px-3 py-1.5 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 flex items-center gap-1"
          >
            <Plus className="w-4 h-4" />
            新建标签
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-sm text-red-700">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {showCreate && (
        <div className="mb-4 p-4 border-2 border-blue-200 rounded-lg bg-blue-50/50">
          <h3 className="font-medium mb-3 text-sm">新建兴趣标签</h3>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-600 block mb-1">名称</label>
              <input
                value={newForm.name}
                onChange={(e) => setNewForm({ ...newForm, name: e.target.value })}
                placeholder="如: 机器学习"
                className="w-full px-3 py-2 border rounded text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-600 block mb-1">层级</label>
                <select
                  value={newForm.level}
                  onChange={(e) => setNewForm({
                    ...newForm,
                    level: Number(e.target.value) as TagLevel,
                  })}
                  className="w-full px-3 py-2 border rounded text-sm"
                >
                  <option value={0}>0 - 一级领域</option>
                  <option value={1}>1 - 二级方向</option>
                  <option value={2}>2 - 三级主题 (叶子)</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-600 block mb-1">权重</label>
                <select
                  value={newForm.weight}
                  onChange={(e) => setNewForm({
                    ...newForm,
                    weight: Number(e.target.value) as TagWeight,
                  })}
                  className="w-full px-3 py-2 border rounded text-sm"
                >
                  <option value={1}>主要 (采样权重 1.0)</option>
                  <option value={2}>次要 (采样权重 0.5)</option>
                </select>
              </div>
            </div>
            {newForm.level > 0 && (
              <div>
                <label className="text-xs text-gray-600 block mb-1">父标签</label>
                <select
                  value={newForm.parent_id || ""}
                  onChange={(e) => setNewForm({
                    ...newForm,
                    parent_id: e.target.value || null,
                  })}
                  className="w-full px-3 py-2 border rounded text-sm"
                >
                  <option value="">-- 无父标签 --</option>
                  {flatAll
                    .filter((t) => t.level === newForm.level - 1)
                    .map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                </select>
              </div>
            )}
            <div>
              <label className="text-xs text-gray-600 block mb-1">颜色 (可选)</label>
              <input
                type="color"
                value={newForm.color || "#3b82f6"}
                onChange={(e) => setNewForm({ ...newForm, color: e.target.value })}
                className="w-20 h-8 border rounded"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={onCreate}
                disabled={busy}
                className="px-3 py-1.5 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 flex items-center gap-1"
              >
                {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                保存
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-400">
          <Loader2 className="w-8 h-8 mx-auto animate-spin" />
        </div>
      ) : tags.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <TagIcon className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>暂无兴趣标签</p>
          <p className="text-xs mt-1">点击"新建标签"开始</p>
        </div>
      ) : (
        <div className="space-y-1">
          {tags.map((tag) => (
            <TagNode
              key={tag.id}
              tag={tag}
              expanded={expandedIds.has(tag.id)}
              editing={editingId === tag.id}
              editForm={editForm}
              setEditForm={setEditForm}
              onToggle={() => toggleExpand(tag.id)}
              onEdit={() => onEdit(tag)}
              onSave={onSaveEdit}
              onCancel={() => setEditingId(null)}
              onDelete={() => onDelete(tag.id)}
              busy={busy}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function useFlatTags(tree: InterestTag[]): InterestTag[] {
  const out: InterestTag[] = [];
  const walk = (node: InterestTag) => {
    out.push(node);
    for (const c of node.children || []) walk(c);
  };
  for (const t of tree) walk(t);
  return out;
}

function TagNode({
  tag,
  expanded,
  editing,
  editForm,
  setEditForm,
  onToggle,
  onEdit,
  onSave,
  onCancel,
  onDelete,
  busy,
}: {
  tag: InterestTag;
  expanded: boolean;
  editing: boolean;
  editForm: { name: string; weight: TagWeight; color: string };
  setEditForm: (f: any) => void;
  onToggle: () => void;
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  onDelete: () => void;
  busy: boolean;
}) {
  const hasChildren = (tag.children || []).length > 0;
  return (
    <div className={`border-l-2 ${tag.level === 0 ? "border-blue-300" : tag.level === 1 ? "border-purple-300" : "border-green-300"} pl-3`}>
      <div className="flex items-center gap-2 py-2 px-2 hover:bg-gray-50 rounded">
        {hasChildren ? (
          <button onClick={onToggle} className="p-0.5">
            {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          </button>
        ) : (
          <span className="w-4" />
        )}
        <span className={`text-xs px-1.5 py-0.5 rounded border ${LEVEL_COLORS[tag.level as TagLevel]}`}>
          L{tag.level}
        </span>
        {editing ? (
          <input
            value={editForm.name}
            onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
            className="px-2 py-0.5 border rounded text-sm flex-1"
          />
        ) : (
          <span className="font-medium text-sm flex-1">{tag.name}</span>
        )}
        {tag.weight === 1 ? (
          <span className="text-xs px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded">主要</span>
        ) : (
          <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">次要</span>
        )}
        {tag.dislike_score > 0 && (
          <span className="text-xs px-1.5 py-0.5 bg-red-50 text-red-700 rounded" title="本地 dislike 权重">
            衰减 {(tag.dislike_score * 100).toFixed(0)}%
          </span>
        )}
        {editing ? (
          <>
            <select
              value={editForm.weight}
              onChange={(e) => setEditForm({ ...editForm, weight: Number(e.target.value) as TagWeight })}
              className="px-2 py-0.5 border rounded text-xs"
            >
              <option value={1}>主要</option>
              <option value={2}>次要</option>
            </select>
            <button onClick={onSave} disabled={busy} className="p-1 hover:bg-blue-50 rounded">
              <Save className="w-3.5 h-3.5 text-blue-600" />
            </button>
            <button onClick={onCancel} className="p-1 hover:bg-gray-100 rounded">
              <X className="w-3.5 h-3.5" />
            </button>
          </>
        ) : (
          <>
            <button onClick={onEdit} className="p-1 hover:bg-gray-100 rounded" title="编辑">
              <Edit3 className="w-3.5 h-3.5 text-gray-500" />
            </button>
            <button onClick={onDelete} className="p-1 hover:bg-red-50 rounded" title="删除">
              <Trash2 className="w-3.5 h-3.5 text-red-500" />
            </button>
          </>
        )}
      </div>
      {expanded && hasChildren && (
        <div className="ml-4 mt-1 space-y-1">
          {tag.children.map((c) => (
            <TagNode
              key={c.id}
              tag={c}
              expanded={false}
              editing={false}
              editForm={editForm}
              setEditForm={setEditForm}
              onToggle={() => {}}
              onEdit={() => {}}
              onSave={() => {}}
              onCancel={() => {}}
              onDelete={() => {}}
              busy={busy}
            />
          ))}
        </div>
      )}
    </div>
  );
}
