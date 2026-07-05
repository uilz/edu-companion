"use client";

// ============================================================
//  Project Detail — 详情 + 视图切换（大纲/时间线/知识图谱）
// ============================================================

import { useState, useCallback, useEffect } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft,
  Plus,
  Loader2,
  ListTree,
  Clock,
  GitBranch,
  Flag,
  Archive,
  Edit3,
  Trash2,
  CheckCircle2,
  Circle,
  X,
  Type,
  Table2,
  Columns,
  Code,
  Paperclip,
  Layers,
  FileText,
  MoreVertical,
} from "lucide-react";
import { authedFetch, API_BASE } from "@/lib/api/api";
import { useUserData } from "@/hooks/useUserData";

// ── 类型 ──

interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  tags: string[];
  node_count: number;
  completed_node_count: number;
  created_at: string;
  updated_at: string;
  nodes: ProjectNode[];
  milestones: Milestone[];
}

interface ProjectNode {
  id: string;
  project_id: string;
  parent_id: string | null;
  type: number;
  title: string;
  description: string | null;
  content: unknown;
  rows: unknown;
  columns: unknown;
  language: string | null;
  code: string | null;
  explanation: string | null;
  material_id: string | null;
  fragments: unknown;
  version: number;
  is_archived: boolean;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  tags: string[];
  order_in_parent: number;
  linked_node_ids: string[];
  linked_material_ids: string[];
  linked_card_ids: string[];
}

interface Milestone {
  id: string;
  milestone_name: string;
  snapshot_data: Record<string, unknown>;
  is_user_marked: boolean;
  marked_at: string;
}

interface Version {
  version_id: string;
  version_number: number;
  changed_fields: string[];
  diff_summary: string;
  is_rollback: boolean;
  rolled_back_from_version: number | null;
  change_source: string;
  created_at: string;
}

// ── 工具 ──

const NODE_TYPE_LABELS: Record<number, { label: string; icon: React.ReactNode }> = {
  1: { label: "大纲", icon: <ListTree size={14} /> },
  2: { label: "文本", icon: <Type size={14} /> },
  3: { label: "数据表", icon: <Table2 size={14} /> },
  4: { label: "对比", icon: <Columns size={14} /> },
  5: { label: "代码", icon: <Code size={14} /> },
  6: { label: "附件", icon: <Paperclip size={14} /> },
  7: { label: "成果板", icon: <Layers size={14} /> },
};

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  return iso.slice(0, 16).replace("T", " ");
}

function buildTree(nodes: ProjectNode[]): ProjectNode[] {
  // Sort by order
  const sorted = [...nodes].sort((a, b) => a.order_in_parent - b.order_in_parent);
  return sorted;
}

function getChildren(nodes: ProjectNode[], parentId: string | null): ProjectNode[] {
  return nodes.filter((n) => n.parent_id === parentId);
}

// ── 节点编辑器 ──

function NodeEditor({
  node,
  onClose,
  onSave,
  onVersions,
  onDelete,
}: {
  node: ProjectNode;
  onClose: () => void;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
  onVersions: () => void;
  onDelete: () => void;
}) {
  const [title, setTitle] = useState(node.title);
  const [description, setDescription] = useState(node.description || "");
  const [content, setContent] = useState<unknown>(node.content);
  const [code, setCode] = useState(node.code || "");
  const [language, setLanguage] = useState(node.language || "");
  const [explanation, setExplanation] = useState(node.explanation || "");
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<"edit" | "preview">("edit");

  const typeInfo = NODE_TYPE_LABELS[node.type] || NODE_TYPE_LABELS[1];

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        title,
        description: description || null,
      };
      if (node.type === 2) payload.content = content;
      if (node.type === 5) {
        payload.code = code;
        payload.language = language || null;
        payload.explanation = explanation || null;
      }
      await onSave(payload);
      onClose();
    } catch (e) {
      console.error(e);
      alert(`保存失败: ${e}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
      <div className="bg-page rounded-xl border border-divider w-full max-w-3xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-divider">
          <div className="flex items-center gap-2">
            <span className="text-ink-secondary">{typeInfo.icon}</span>
            <span className="text-sm text-ink-secondary">{typeInfo.label}</span>
            <span className="text-sm text-ink-secondary">v{node.version}</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={onVersions}
              className="px-3 py-1.5 rounded text-sm text-ink-secondary hover:text-ink-primary hover:bg-surface-hover"
            >
              版本历史
            </button>
            <button
              onClick={onDelete}
              className="px-3 py-1.5 rounded text-sm text-ink-secondary hover:text-red-500 hover:bg-surface-hover"
            >
              删除
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded text-ink-secondary hover:text-ink-primary hover:bg-surface-hover"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-divider px-4">
          <button
            onClick={() => setActiveTab("edit")}
            className={`px-3 py-2 text-sm ${activeTab === "edit" ? "border-b-2 border-[var(--color-accent)] text-[var(--color-accent)]" : "text-ink-secondary"}`}
          >
            编辑
          </button>
          <button
            onClick={() => setActiveTab("preview")}
            className={`px-3 py-2 text-sm ${activeTab === "preview" ? "border-b-2 border-[var(--color-accent)] text-[var(--color-accent)]" : "text-ink-secondary"}`}
          >
            预览
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {activeTab === "edit" ? (
            <>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">标题</label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                />
              </div>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">
                  描述（支持 <code className="text-xs">@节点名</code> 引用）
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary font-mono text-sm"
                />
              </div>
              {node.type === 2 && (
                <div>
                  <label className="text-sm text-ink-secondary block mb-1">富文本内容（JSON）</label>
                  <textarea
                    value={JSON.stringify(content, null, 2) || "{}"}
                    onChange={(e) => {
                      try {
                        setContent(JSON.parse(e.target.value));
                      } catch {
                        /* ignore */
                      }
                    }}
                    rows={6}
                    className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary font-mono text-sm"
                  />
                </div>
              )}
              {node.type === 5 && (
                <>
                  <div>
                    <label className="text-sm text-ink-secondary block mb-1">语言</label>
                    <input
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                      placeholder="python / javascript / ..."
                    />
                  </div>
                  <div>
                    <label className="text-sm text-ink-secondary block mb-1">代码</label>
                    <textarea
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      rows={10}
                      className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary font-mono text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-ink-secondary block mb-1">说明</label>
                    <textarea
                      value={explanation}
                      onChange={(e) => setExplanation(e.target.value)}
                      rows={3}
                      className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                    />
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="prose max-w-none">
              <h1 className="text-2xl font-bold text-ink-primary">{title}</h1>
              {description && (
                <div className="text-ink-secondary whitespace-pre-wrap mb-4">{description}</div>
              )}
              {node.type === 5 && code && (
                <pre className="bg-surface-hover p-3 rounded-lg overflow-x-auto text-sm">
                  <code>{code}</code>
                </pre>
              )}
              {node.type === 5 && explanation && (
                <p className="text-ink-secondary mt-2 whitespace-pre-wrap">{explanation}</p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 p-4 border-t border-divider">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-ink-secondary hover:text-ink-primary"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
          >
            {saving && <Loader2 className="animate-spin" size={14} />}
            保存（自动入栈版本）
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 版本历史 ──

function VersionHistory({
  versions,
  node,
  onClose,
  onRollback,
  onDiff,
}: {
  versions: Version[];
  node: ProjectNode;
  onClose: () => void;
  onRollback: (version: number, fields?: string[]) => Promise<void>;
  onDiff: (a: number, b: number) => Promise<void>;
}) {
  const [a, setA] = useState<number | null>(null);
  const [b, setB] = useState<number | null>(null);

  return (
    <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
      <div className="bg-page rounded-xl border border-divider w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-divider">
          <h2 className="text-lg font-semibold text-ink-primary">版本历史 — {node.title}</h2>
          <button onClick={onClose} className="p-1.5 rounded text-ink-secondary hover:text-ink-primary">
            <X size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {versions.length === 0 ? (
            <p className="text-ink-secondary text-center py-8">暂无历史版本</p>
          ) : (
            <div className="space-y-2">
              {versions.map((v) => (
                <div
                  key={v.version_id}
                  className="p-3 rounded-lg border border-divider bg-surface"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-ink-primary">
                        v{v.version_number}
                        {v.is_rollback && (
                          <span className="ml-2 text-xs text-amber-500">
                            回滚自 v{v.rolled_back_from_version}
                          </span>
                        )}
                        <span className="ml-2 text-xs text-ink-secondary">
                          [{v.change_source}]
                        </span>
                      </div>
                      <div className="text-xs text-ink-secondary mt-1">
                        {formatDate(v.created_at)} · {v.changed_fields.join(", ")}
                      </div>
                      {v.diff_summary && (
                        <div className="text-xs text-ink-secondary mt-1">{v.diff_summary}</div>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => {
                          if (a === null) setA(v.version_number);
                          else if (b === null) setB(v.version_number);
                          else { setA(v.version_number); setB(null); }
                        }}
                        className={`px-2 py-1 text-xs rounded ${
                          a === v.version_number || b === v.version_number
                            ? "bg-[var(--color-accent)] text-white"
                            : "bg-surface-hover text-ink-secondary hover:text-ink-primary"
                        }`}
                      >
                        {a === v.version_number ? "A" : b === v.version_number ? "B" : "选择"}
                      </button>
                      <button
                        onClick={() => onRollback(v.version_number)}
                        className="px-2 py-1 text-xs rounded text-ink-secondary hover:text-ink-primary hover:bg-surface-hover"
                      >
                        回滚到此版
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        {a !== null && b !== null && (
          <div className="p-3 border-t border-divider flex justify-end">
            <button
              onClick={() => onDiff(a, b)}
              className="px-3 py-1.5 rounded-lg bg-[var(--color-accent)] text-white text-sm hover:opacity-90"
            >
              对比 v{a} ↔ v{b}
            </button>
          </div>
        )}
        {a !== null && b === null && (
          <div className="p-3 border-t border-divider text-xs text-ink-secondary text-center">
            请再选一个版本作为 B 进行对比
          </div>
        )}
      </div>
    </div>
  );
}

// ── 大纲视图 ──

function OutlineView({
  nodes,
  onAddNode,
  onOpenNode,
  onCompleteNode,
  onDragStart,
  onDragEnd,
}: {
  nodes: ProjectNode[];
  onAddNode: (parentId: string | null, type: number) => void;
  onOpenNode: (node: ProjectNode) => void;
  onCompleteNode: (node: ProjectNode) => void;
  onDragStart: (e: React.DragEvent, node: ProjectNode) => void;
  onDragEnd: () => void;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const renderNode = (node: ProjectNode, depth: number) => {
    const children = getChildren(nodes, node.id);
    const hasChildren = children.length > 0;
    const isExpanded = expanded.has(node.id);
    const typeInfo = NODE_TYPE_LABELS[node.type] || NODE_TYPE_LABELS[1];

    return (
      <div key={node.id}>
        <div
          draggable
          onDragStart={(e) => onDragStart(e, node)}
          onDragEnd={onDragEnd}
          className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-surface-hover group cursor-grab"
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
        >
          {hasChildren ? (
            <button
              onClick={() => toggle(node.id)}
              className="w-4 h-4 flex items-center justify-center text-ink-secondary"
            >
              {isExpanded ? "▼" : "▶"}
            </button>
          ) : (
            <span className="w-4" />
          )}
          <span className="text-ink-secondary">{typeInfo.icon}</span>
          <button
            onClick={() => onOpenNode(node)}
            className="flex-1 text-left text-ink-primary hover:text-[var(--color-accent)] truncate"
          >
            {node.title || "(无标题)"}
          </button>
          <span className="text-xs text-ink-secondary">v{node.version}</span>
          <button
            onClick={() => onCompleteNode(node)}
            className="p-1 rounded text-ink-secondary hover:text-green-500"
            title={node.completed_at ? "已完成" : "标记完成"}
          >
            {node.completed_at ? <CheckCircle2 size={14} className="text-green-500" /> : <Circle size={14} />}
          </button>
          <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1">
            <button
              onClick={() => onAddNode(node.id, 2)}
              className="p-1 rounded text-ink-secondary hover:text-ink-primary"
              title="添加子节点"
            >
              <Plus size={12} />
            </button>
          </div>
        </div>
        {isExpanded && children.map((c) => renderNode(c, depth + 1))}
      </div>
    );
  };

  const rootNodes = getChildren(nodes, null);
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider">
          大纲视图
        </h3>
        <button
          onClick={() => onAddNode(null, 1)}
          className="text-sm text-[var(--color-accent)] hover:opacity-80 flex items-center gap-1 whitespace-nowrap flex-shrink-0"
        >
          <Plus size={14} /> 根节点
        </button>
      </div>
      <div className="border border-divider rounded-lg bg-surface p-2 min-h-[400px]">
        {rootNodes.length === 0 ? (
          <div className="text-center text-ink-secondary py-12">
            暂无节点。点击"根节点"开始构建大纲。
          </div>
        ) : (
          rootNodes.map((n) => renderNode(n, 0))
        )}
      </div>
    </div>
  );
}

// ── 时间线视图 ──

function TimelineView({
  nodes,
  onOpenNode,
}: {
  nodes: ProjectNode[];
  onOpenNode: (n: ProjectNode) => void;
}) {
  const sorted = [...nodes].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  );

  return (
    <div>
      <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider mb-3">
        时间线视图（按更新时间）
      </h3>
      <div className="relative pl-6 border-l-2 border-divider space-y-3">
        {sorted.length === 0 ? (
          <p className="text-ink-secondary">暂无节点</p>
        ) : (
          sorted.map((n) => {
            const typeInfo = NODE_TYPE_LABELS[n.type] || NODE_TYPE_LABELS[1];
            return (
              <button
                key={n.id}
                onClick={() => onOpenNode(n)}
                className="w-full text-left p-3 rounded-lg bg-surface border border-divider hover:border-[var(--color-accent)] transition"
              >
                <div className="flex items-center gap-2 text-xs text-ink-secondary mb-1">
                  <span>{typeInfo.icon}</span>
                  <span>{typeInfo.label}</span>
                  <span>·</span>
                  <span>{formatDate(n.updated_at)}</span>
                  {n.completed_at && (
                    <>
                      <span>·</span>
                      <span className="text-green-500 flex items-center gap-1">
                        <CheckCircle2 size={10} /> 已完成
                      </span>
                    </>
                  )}
                </div>
                <div className="text-ink-primary font-medium">{n.title}</div>
                {n.description && (
                  <div className="text-sm text-ink-secondary mt-1 line-clamp-2">
                    {n.description}
                  </div>
                )}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}

// ── 知识图谱视图 ──

function KnowledgeView({
  nodes,
  onOpenNode,
}: {
  nodes: ProjectNode[];
  onOpenNode: (n: ProjectNode) => void;
}) {
  const linkedNodes = nodes.filter(
    (n) =>
      (n.linked_node_ids && n.linked_node_ids.length > 0) ||
      (n.linked_material_ids && n.linked_material_ids.length > 0) ||
      (n.linked_card_ids && n.linked_card_ids.length > 0),
  );

  return (
    <div>
      <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider mb-3">
        知识关联视图
      </h3>
      {linkedNodes.length === 0 ? (
        <div className="text-center text-ink-secondary py-12 border border-dashed border-divider rounded-lg">
          暂无知识关联。在节点编辑面板中关联 CognitiveNode / Material / FlashCard 后将显示在此。
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {linkedNodes.map((n) => {
            const typeInfo = NODE_TYPE_LABELS[n.type] || NODE_TYPE_LABELS[1];
            return (
              <button
                key={n.id}
                onClick={() => onOpenNode(n)}
                className="text-left p-3 rounded-lg bg-surface border border-divider hover:border-[var(--color-accent)] transition"
              >
                <div className="flex items-center gap-2 text-xs text-ink-secondary mb-2">
                  <span>{typeInfo.icon}</span>
                  <span>{typeInfo.label}</span>
                </div>
                <div className="text-ink-primary font-medium mb-2">{n.title}</div>
                <div className="flex flex-wrap gap-1 text-xs">
                  {n.linked_node_ids && n.linked_node_ids.length > 0 && (
                    <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-500">
                      {n.linked_node_ids.length} 知识点
                    </span>
                  )}
                  {n.linked_material_ids && n.linked_material_ids.length > 0 && (
                    <span className="px-2 py-0.5 rounded bg-green-500/10 text-green-500">
                      {n.linked_material_ids.length} 材料
                    </span>
                  )}
                  {n.linked_card_ids && n.linked_card_ids.length > 0 && (
                    <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-500">
                      {n.linked_card_ids.length} 卡片
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── 主页面 ──

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = params?.id as string;
  // 任务 #32：从 URL ?view= 读取初始视图，让 /project/[id]/view/{knowledge,timeline} 重定向生效
  const initialView = (() => {
    const v = searchParams?.get("view");
    return v === "timeline" || v === "knowledge" ? v : "outline";
  })();
  const [view, setView] = useState<"outline" | "timeline" | "knowledge">(initialView);
  // 任务 #49：统一使用 useUserData 自动等待 AuthContext，
  // 避免「useCurrentUserId 隐藏 authLoading 导致 useEffect 死锁」问题。
  // 这里用 projectId 作为 dep，项目切换时自动重新加载。
  const {
    data: project,
    loading,
    refetch: loadProject,
  } = useUserData<Project>(
    async () => {
      if (!projectId) throw new Error("missing projectId");
      const res = await authedFetch(`${API_BASE}/api/projects/${projectId}`);
      return res.json();
    },
    [projectId],
  );
  const [editing, setEditing] = useState<ProjectNode | null>(null);
  const [historyNode, setHistoryNode] = useState<ProjectNode | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [showAddChild, setShowAddChild] = useState<{ parent_id: string | null } | null>(null);
  const [addingNode, setAddingNode] = useState(false);
  const [newNode, setNewNode] = useState({ title: "", type: 1, description: "" });
  const [showMilestone, setShowMilestone] = useState(false);
  const [milestoneName, setMilestoneName] = useState("");
  const [draggedNode, setDraggedNode] = useState<ProjectNode | null>(null);
  const [showExport, setShowExport] = useState<ProjectNode | null>(null);
  const [exportTarget, setExportTarget] = useState("flashcard");

  const loadVersions = useCallback(
    async (nodeId: string) => {
      try {
        const res = await authedFetch(
          `${API_BASE}/api/projects/${projectId}/nodes/${nodeId}/versions`,
        );
        const json = await res.json();
        setVersions(json.versions || []);
      } catch (e) {
        console.error(e);
      }
    },
    [projectId],
  );

  const handleAddNode = async () => {
    if (!newNode.title.trim() || !showAddChild) return;
    setAddingNode(true);
    try {
      await authedFetch(`${API_BASE}/api/projects/${projectId}/nodes`, {
        method: "POST",
        body: JSON.stringify({
          type: newNode.type,
          title: newNode.title,
          parent_id: showAddChild.parent_id,
          description: newNode.description || null,
        }),
      });
      setShowAddChild(null);
      setNewNode({ title: "", type: 1, description: "" });
      loadProject();
    } catch (e) {
      console.error(e);
    } finally {
      setAddingNode(false);
    }
  };

  const handleSaveNode = async (payload: Record<string, unknown>) => {
    if (!editing) return;
    await authedFetch(`${API_BASE}/api/projects/${projectId}/nodes/${editing.id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    loadProject();
  };

  const handleDeleteNode = async (node: ProjectNode) => {
    if (!confirm(`确定要删除节点 "${node.title}" 吗？`)) return;
    try {
      await authedFetch(`${API_BASE}/api/projects/${projectId}/nodes/${node.id}`, {
        method: "DELETE",
      });
      setEditing(null);
      loadProject();
    } catch (e) {
      console.error(e);
    }
  };

  const handleCompleteNode = async (node: ProjectNode) => {
    const completed = !node.completed_at;
    try {
      await authedFetch(
        `${API_BASE}/api/projects/${projectId}/nodes/${node.id}/complete?completed=${completed}`,
        { method: "POST" },
      );
      loadProject();
    } catch (e) {
      console.error(e);
    }
  };

  const handleOpenHistory = async (node: ProjectNode) => {
    setHistoryNode(node);
    await loadVersions(node.id);
  };

  const handleRollback = async (targetVersion: number, fields?: string[]) => {
    if (!historyNode) return;
    try {
      await authedFetch(
        `${API_BASE}/api/projects/${projectId}/nodes/${historyNode.id}/rollback`,
        {
          method: "POST",
          body: JSON.stringify({ target_version: targetVersion, fields: fields || null }),
        },
      );
      setHistoryNode(null);
      setEditing(null);
      loadProject();
    } catch (e) {
      console.error(e);
      alert(`回滚失败: ${e}`);
    }
  };

  const handleDiff = async (a: number, b: number) => {
    if (!historyNode) return;
    try {
      const res = await authedFetch(
        `${API_BASE}/api/projects/${projectId}/nodes/${historyNode.id}/diff`,
        {
          method: "POST",
          body: JSON.stringify({ version_a: a, version_b: b }),
        },
      );
      const json = await res.json();
      alert(
        `字段级 diff (v${a} ↔ v${b}):\n\n` +
          (json.changed_fields.length === 0
            ? "无字段差异"
            : json.changed_fields.map((f) => `• ${f}`).join("\n")),
      );
    } catch (e) {
      console.error(e);
    }
  };

  const handleCreateMilestone = async () => {
    if (!milestoneName.trim()) return;
    try {
      await authedFetch(`${API_BASE}/api/projects/${projectId}/milestones`, {
        method: "POST",
        body: JSON.stringify({ milestone_name: milestoneName }),
      });
      setShowMilestone(false);
      setMilestoneName("");
      loadProject();
    } catch (e) {
      console.error(e);
    }
  };

  const handleExport = async () => {
    if (!showExport) return;
    try {
      await authedFetch(
        `${API_BASE}/api/projects/${projectId}/nodes/${showExport.id}/export`,
        {
          method: "POST",
          body: JSON.stringify({ target_module: exportTarget, target_ref_id: "" }),
        },
      );
      setShowExport(null);
      alert(`已导出到 ${exportTarget}`);
    } catch (e) {
      console.error(e);
    }
  };

  // ── 拖拽支持 ──
  const onDragStart = (e: React.DragEvent, node: ProjectNode) => {
    setDraggedNode(node);
    e.dataTransfer.setData("text/plain", node.id);
    e.dataTransfer.effectAllowed = "move";
  };

  const onDragEnd = () => setDraggedNode(null);

  const handleDropOnNode = async (target: ProjectNode) => {
    if (!draggedNode || draggedNode.id === target.id) return;
    // 拖拽到关联节点：建立 link_copy
    try {
      await authedFetch(`${API_BASE}/api/projects/${projectId}/copy-nodes`, {
        method: "POST",
        body: JSON.stringify({
          source_project_id: projectId,
          node_ids: [draggedNode.id],
          mode: "link_copy",
        }),
      });
      loadProject();
    } catch (e) {
      console.error(e);
    }
  };

  if (loading || !project) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] text-ink-secondary">
        <Loader2 className="animate-spin" size={24} />
      </div>
    );
  }

  const nodes = project.nodes || [];

  return (
    <div className="min-h-full p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <button
            onClick={() => router.push("/project")}
            className="text-sm text-ink-secondary hover:text-ink-primary flex items-center gap-1 mb-2"
          >
            <ChevronLeft size={14} /> 返回项目列表
          </button>
          <h1 className="text-2xl font-bold text-ink-primary tracking-tight flex items-center gap-2">
            {project.name}
            {project.status === "archived" && (
              <span className="text-xs px-2 py-0.5 rounded bg-amber-500/10 text-amber-500">
                已归档
              </span>
            )}
          </h1>
          {project.description && (
            <p className="text-sm text-ink-secondary mt-1">{project.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => setShowMilestone(true)}
            className="px-3 py-2 rounded-lg border border-divider text-ink-primary hover:bg-surface-hover flex items-center gap-1 whitespace-nowrap"
          >
            <Flag size={14} /> 里程碑
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="p-3 rounded-lg border border-divider bg-surface">
          <div className="text-xs text-ink-secondary">节点总数</div>
          <div className="text-2xl font-bold text-ink-primary">{project.node_count}</div>
        </div>
        <div className="p-3 rounded-lg border border-divider bg-surface">
          <div className="text-xs text-ink-secondary">已完成</div>
          <div className="text-2xl font-bold text-green-500">{project.completed_node_count}</div>
        </div>
        <div className="p-3 rounded-lg border border-divider bg-surface">
          <div className="text-xs text-ink-secondary">里程碑</div>
          <div className="text-2xl font-bold text-ink-primary">{project.milestones?.length || 0}</div>
        </div>
        <div className="p-3 rounded-lg border border-divider bg-surface">
          <div className="text-xs text-ink-secondary">完成率</div>
          <div className="text-2xl font-bold text-ink-primary">
            {project.node_count > 0
              ? Math.round((project.completed_node_count / project.node_count) * 100)
              : 0}
            %
          </div>
        </div>
      </div>

      {/* View Switcher */}
      <div className="flex items-center gap-1 mb-4 border-b border-divider">
        <button
          onClick={() => setView("outline")}
          className={`px-4 py-2 text-sm flex items-center gap-1 ${
            view === "outline"
              ? "border-b-2 border-[var(--color-accent)] text-[var(--color-accent)]"
              : "text-ink-secondary hover:text-ink-primary"
          }`}
        >
          <ListTree size={14} /> 大纲
        </button>
        <button
          onClick={() => setView("timeline")}
          className={`px-4 py-2 text-sm flex items-center gap-1 ${
            view === "timeline"
              ? "border-b-2 border-[var(--color-accent)] text-[var(--color-accent)]"
              : "text-ink-secondary hover:text-ink-primary"
          }`}
        >
          <Clock size={14} /> 时间线
        </button>
        <button
          onClick={() => setView("knowledge")}
          className={`px-4 py-2 text-sm flex items-center gap-1 ${
            view === "knowledge"
              ? "border-b-2 border-[var(--color-accent)] text-[var(--color-accent)]"
              : "text-ink-secondary hover:text-ink-primary"
          }`}
        >
          <GitBranch size={14} /> 知识关联
        </button>
      </div>
      {/* Views */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
        }}
        onDrop={(e) => {
          e.preventDefault();
          // 拖拽到空白区视为添加到根
          if (draggedNode) {
            setShowAddChild({ parent_id: null });
          }
        }}
      >
        {view === "outline" && (
          <OutlineView
            nodes={nodes}
            onAddNode={(parentId, type) => {
              setNewNode({ title: "", type, description: "" });
              setShowAddChild({ parent_id: parentId });
            }}
            onOpenNode={(n) => setEditing(n)}
            onCompleteNode={handleCompleteNode}
            onDragStart={onDragStart}
            onDragEnd={onDragEnd}
          />
        )}
        {view === "timeline" && (
          <TimelineView nodes={nodes} onOpenNode={(n) => setEditing(n)} />
        )}
        {view === "knowledge" && (
          <div>
            <KnowledgeView nodes={nodes} onOpenNode={(n) => setEditing(n)} />
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider mb-3">
                节点关联（拖拽节点到此处建立 link_copy）
              </h3>
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (draggedNode) {
                    setShowExport(draggedNode);
                  }
                }}
                className="border-2 border-dashed border-divider rounded-lg p-6 text-center text-ink-secondary"
              >
                拖拽节点到此处可选择导出到其他模块（FlashCard / Material / Plan / CognitiveNode）
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Milestones */}
      {project.milestones && project.milestones.length > 0 && (
        <div className="mt-8">
          <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider mb-3">
            里程碑
          </h3>
          <div className="space-y-2">
            {project.milestones.map((m) => (
              <div
                key={m.id}
                className="p-3 rounded-lg border border-divider bg-surface"
              >
                <div className="flex items-center gap-2 text-ink-primary">
                  <Flag size={14} className="text-amber-500" />
                  <span className="font-medium">{m.milestone_name}</span>
                  <span className="text-xs text-ink-secondary">
                    · {formatDate(m.marked_at)}
                  </span>
                </div>
                {m.snapshot_data && (
                  <div className="text-xs text-ink-secondary mt-1">
                    节点 {String(m.snapshot_data.node_count ?? 0)} · 完成{" "}
                    {String(m.snapshot_data.completed_count ?? 0)} · 关联{" "}
                    {String(m.snapshot_data.link_count ?? 0)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Add Node Modal */}
      {showAddChild && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="bg-page rounded-xl border border-divider w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-ink-primary mb-4">
              {showAddChild.parent_id ? "添加子节点" : "添加根节点"}
            </h2>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-ink-secondary block mb-1">类型</label>
                <select
                  value={newNode.type}
                  onChange={(e) => setNewNode({ ...newNode, type: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                >
                  {Object.entries(NODE_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">
                  标题 <span className="text-red-500">*</span>
                </label>
                <input
                  value={newNode.title}
                  onChange={(e) => setNewNode({ ...newNode, title: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                />
              </div>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">描述</label>
                <textarea
                  value={newNode.description}
                  onChange={(e) => setNewNode({ ...newNode, description: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-6">
              <button
                onClick={() => setShowAddChild(null)}
                className="px-4 py-2 rounded-lg text-ink-secondary"
              >
                取消
              </button>
              <button
                onClick={handleAddNode}
                disabled={addingNode || !newNode.title.trim()}
                className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50"
              >
                {addingNode && <Loader2 className="animate-spin" size={14} />} 创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Milestone Modal */}
      {showMilestone && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="bg-page rounded-xl border border-divider w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-ink-primary mb-4">创建里程碑</h2>
            <p className="text-sm text-ink-secondary mb-3">
              里程碑是项目级整体快照（节点数、关联数、完成率）。
            </p>
            <input
              value={milestoneName}
              onChange={(e) => setMilestoneName(e.target.value)}
              placeholder="例如：完成初稿、完成第 1 阶段"
              className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary mb-4"
            />
            <div className="flex items-center justify-end gap-2">
              <button onClick={() => setShowMilestone(false)} className="px-4 py-2 rounded-lg text-ink-secondary">
                取消
              </button>
              <button
                onClick={handleCreateMilestone}
                disabled={!milestoneName.trim()}
                className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Export Modal */}
      {showExport && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="bg-page rounded-xl border border-divider w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-ink-primary mb-4">导出节点</h2>
            <p className="text-sm text-ink-secondary mb-3">将节点内容导出到其他模块：</p>
            <select
              value={exportTarget}
              onChange={(e) => setExportTarget(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary mb-4"
            >
              <option value="flashcard">FlashCard（复习卡）</option>
              <option value="material">Material（阅读材料）</option>
              <option value="cognitive_node">CognitiveNode（知识点）</option>
              <option value="plan">Plan（计划项）</option>
              <option value="language_room">LanguageRoom（语言房间）</option>
            </select>
            <div className="flex items-center justify-end gap-2">
              <button onClick={() => setShowExport(null)} className="px-4 py-2 rounded-lg text-ink-secondary">
                取消
              </button>
              <button
                onClick={handleExport}
                className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90"
              >
                导出
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editing && (
        <NodeEditor
          node={editing}
          onClose={() => setEditing(null)}
          onSave={handleSaveNode}
          onVersions={() => handleOpenHistory(editing)}
          onDelete={() => handleDeleteNode(editing)}
        />
      )}

      {/* Version History Modal */}
      {historyNode && (
        <VersionHistory
          versions={versions}
          node={historyNode}
          onClose={() => setHistoryNode(null)}
          onRollback={handleRollback}
          onDiff={handleDiff}
        />
      )}
    </div>
  );
}
