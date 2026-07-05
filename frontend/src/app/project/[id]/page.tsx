"use client";

// ============================================================
//  Project Detail — 详情 + 视图切换 (Task #89 拆分后主壳)
// ============================================================

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ChevronLeft, Flag, Loader2, FileText } from "lucide-react";
import { useProjectData } from "./hooks/useProjectData";
import { useViewPreference } from "./hooks/useViewPreference";
import { ViewSwitcher } from "./views/ViewSwitcher";
import { DocumentView } from "./views/DocumentView";
import { OutlineView } from "./views/OutlineView";
import { KanbanView } from "./views/KanbanView";
import { KnowledgeView } from "./views/KnowledgeView";
import { ActivityView } from "./views/ActivityView";
import { NodeEditor } from "./components/NodeEditor";
import { VersionHistory } from "./components/VersionHistory";
import { Version, ProjectNode } from "./types";

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = (params?.id as string) || "";

  const {
    project,
    loading,
    saveNode,
    deleteNode,
    completeNode,
    setNodeStatus,
    reorderNodes,
    loadVersions,
    rollbackNode,
    diffVersions,
    createMilestone,
    linkCopyNode,
  } = useProjectData(projectId);

  const { view, setView } = useViewPreference(projectId);

  // 本地 UI state
  const [editing, setEditing] = useState<ProjectNode | null>(null);
  const [historyNode, setHistoryNode] = useState<ProjectNode | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [showAddChild, setShowAddChild] = useState<{ parent_id: string | null } | null>(null);
  const [addingNode, setAddingNode] = useState(false);
  const [newNode, setNewNode] = useState({ title: "", type: 1, description: "" });
  const [showMilestone, setShowMilestone] = useState(false);
  const [milestoneName, setMilestoneName] = useState("");

  const handleAddNode = async () => {
    if (!newNode.title.trim() || !showAddChild) return;
    setAddingNode(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE || ""}/api/projects/${projectId}/nodes`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            type: newNode.type,
            title: newNode.title,
            parent_id: showAddChild.parent_id,
            description: newNode.description || null,
          }),
        },
      );
      if (res.ok) {
        setShowAddChild(null);
        setNewNode({ title: "", type: 1, description: "" });
        // 触发 useProjectData refetch 通过 reload
        window.location.reload();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setAddingNode(false);
    }
  };

  const handleOpenHistory = async (node: ProjectNode) => {
    setHistoryNode(node);
    const v = await loadVersions(node.id);
    setVersions(v);
  };

  const handleRollback = async (targetVersion: number) => {
    if (!historyNode) return;
    try {
      await rollbackNode(historyNode.id, targetVersion);
      setHistoryNode(null);
      setEditing(null);
    } catch (e) {
      console.error(e);
      alert(`回滚失败: ${e}`);
    }
  };

  const handleDiff = async (a: number, b: number) => {
    if (!historyNode) return;
    try {
      const fields = await diffVersions(historyNode.id, a, b);
      alert(
        `字段级 diff (v${a} ↔ v${b}):\n\n` +
          (fields.length === 0
            ? "无字段差异"
            : fields.map((f) => `• ${f}`).join("\n")),
      );
    } catch (e) {
      console.error(e);
    }
  };

  const handleCreateMilestone = async () => {
    if (!milestoneName.trim()) return;
    try {
      await createMilestone(milestoneName);
      setShowMilestone(false);
      setMilestoneName("");
    } catch (e) {
      console.error(e);
    }
  };

  const handleDropOnBlank = () => {
    if (showAddChild === null) setShowAddChild({ parent_id: null });
  };

  if (loading || !project) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] text-ink-secondary">
        <Loader2 className="animate-spin" size={24} />
      </div>
    );
  }

  const nodes = project.nodes || [];
  const viewProps = {
    projectId,
    nodes,
    onOpenNode: (n: ProjectNode) => setEditing(n),
    onAddNode: (parentId: string | null, type: number) => {
      setNewNode({ title: "", type, description: "" });
      setShowAddChild({ parent_id: parentId });
    },
    onCompleteNode: (n: ProjectNode) => completeNode(n.id, !n.completed_at),
    onReorder: (parentId: string | null, newOrder: ProjectNode[]) =>
      reorderNodes(parentId, newOrder.map((n) => n.id)),
  };

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
      <ViewSwitcher current={view} onChange={setView} />

      {/* Views */}
      <div onDragOver={(e) => e.preventDefault()} onDrop={handleDropOnBlank}>
        {view === "document" && <DocumentView {...viewProps} />}
        {view === "outline" && <OutlineView {...viewProps} />}
        {view === "kanban" && (
          <KanbanView
            {...viewProps}
            onSetStatus={(nodeId, status) => setNodeStatus(nodeId, status)}
          />
        )}
        {view === "knowledge" && <KnowledgeView {...viewProps} />}
        {view === "activity" && <ActivityView {...viewProps} />}
      </div>

      {/* Add Node Modal */}
      {showAddChild && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="bg-page rounded-xl border border-divider w-full max-w-md p-4">
            <h3 className="text-lg font-semibold text-ink-primary mb-3 flex items-center gap-2">
              <FileText size={16} />
              {showAddChild.parent_id ? "添加子节点" : "添加根节点"}
            </h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-ink-secondary block mb-1">类型</label>
                <select
                  value={newNode.type}
                  onChange={(e) => setNewNode({ ...newNode, type: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                >
                  <option value={1}>大纲</option>
                  <option value={2}>文本</option>
                  <option value={3}>数据表</option>
                  <option value={4}>对比</option>
                  <option value={5}>代码</option>
                  <option value={6}>附件</option>
                  <option value={7}>成果板</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">标题</label>
                <input
                  value={newNode.title}
                  onChange={(e) => setNewNode({ ...newNode, title: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                  autoFocus
                />
              </div>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">描述（可选）</label>
                <textarea
                  value={newNode.description}
                  onChange={(e) => setNewNode({ ...newNode, description: e.target.value })}
                  rows={2}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-4">
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
                {addingNode ? "添加中..." : "添加"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Milestone Modal */}
      {showMilestone && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="bg-page rounded-xl border border-divider w-full max-w-md p-4">
            <h3 className="text-lg font-semibold text-ink-primary mb-3 flex items-center gap-2">
              <Flag size={16} className="text-amber-500" />
              标记里程碑
            </h3>
            <input
              value={milestoneName}
              onChange={(e) => setMilestoneName(e.target.value)}
              placeholder="例如：完成第一版大纲"
              className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
              autoFocus
            />
            <div className="flex items-center justify-end gap-2 mt-3">
              <button
                onClick={() => setShowMilestone(false)}
                className="px-4 py-2 rounded-lg text-ink-secondary"
              >
                取消
              </button>
              <button
                onClick={handleCreateMilestone}
                disabled={!milestoneName.trim()}
                className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50"
              >
                标记
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Node Editor Modal */}
      {editing && (
        <NodeEditor
          node={editing}
          onClose={() => setEditing(null)}
          onSave={async (payload) => {
            await saveNode(editing.id, payload);
          }}
          onVersions={() => handleOpenHistory(editing)}
          onDelete={async () => {
            if (confirm(`确定要删除节点 "${editing.title}" 吗？`)) {
              await deleteNode(editing.id);
              setEditing(null);
            }
          }}
        />
      )}

      {/* Version History Modal */}
      {historyNode && (
        <VersionHistory
          node={historyNode}
          versions={versions}
          onClose={() => setHistoryNode(null)}
          onRollback={async (v) => {
            await handleRollback(v);
          }}
          onDiff={async (a, b) => {
            await handleDiff(a, b);
          }}
        />
      )}
    </div>
  );
}
