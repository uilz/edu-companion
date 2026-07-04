"use client";

import { useEffect, useMemo } from "react";
import { FolderOpen } from "lucide-react";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { NewNodeDialog } from "@/components/ui/NewNodeDialog";
import EmptyState from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { SidebarTreeNode } from "@/components/conversation/tree/SidebarTreeNode";
import { FlatConversationList } from "@/components/conversation/panels/FlatConversationList";
import { useTreeNavigation } from "@/hooks/graph/useTreeNavigation";
import { useConversationStore } from "@/store/conversation/conversation-store";
import { useTreeStore } from "@/store/conversation/tree-store";
import { apiFetch } from "@/store/conversation/tree-helpers";
import type { GraphNode } from "@/components/conversation/tree/SidebarTreeNode";

interface Props {
  selectedDirId: string | null;
  activeConversationId: string | null;
  initialConversationId?: string;
  onSelectConversation: (pid: string, cid: string) => void;
  onCreateDir: () => void;
  onRenameDir?: (id: string, name: string) => void;
  loading?: boolean;
  compact?: boolean;
  onNewConversation?: (level: string, parentId: string, dirId?: string) => void;
  onConversationReady?: (dirId: string, conversationId: string) => void;
  onTreeChanged?: () => void;
  onSelectConv?: (dirId: string, conversationId: string) => void;
}

export default function StudySidebar({
  selectedDirId: _selectedNodeId,
  activeConversationId,
  initialConversationId,
  onCreateDir,
  loading = false, compact = false,
  onConversationReady,
  onTreeChanged,
}: Props) {
  // ── 挂载时展开祖先链 ──
  useEffect(() => {
    const init = async () => {
      const treeState = useTreeStore.getState();
      if (!treeState.rootLoaded) {
        await treeState.loadRootNodes();
      }
      const s = useConversationStore.getState();
      const pid = s.selectedNode?.id;
      if (!pid) return;

      try {
        // 从后端获取节点详情（含 path 祖先链）
        const resp = await apiFetch<{ directory_node: any }>(`/tree/directory/${pid}`);
        const d = resp.directory_node;
        const path = d.path || [];
        // 展开所有祖先节点，让树视图定位到当前选中节点
        if (path.length > 0) {
          useTreeStore.getState().expandAncestors(path);
        }
      } catch {
        // 节点不存在（如 URL 中的 node_id 已被删除），清除 URL 回到默认
        try {
          window.history.replaceState(null, "", window.location.pathname);
          localStorage.removeItem("conversation-page-state");
        } catch { /* ignore */ }
      }
    };
    init();
  }, []);

  const nav = useTreeNavigation(onConversationReady, onTreeChanged);
  const selectGraphNode = useConversationStore(s => s.selectGraphNode);
  const selectedNode = useConversationStore(s => s.selectedNode);
  const sidebarMode = useConversationStore(s => s.sidebarMode);

  // ── 祖先链：selectedNode.path 中的祖先 ID 集合 ──
  const ancestorIds = useMemo(() => {
    if (!selectedNode?.path || selectedNode.path.length === 0) return new Set<string>();
    return new Set(selectedNode.path);
  }, [selectedNode]);

  // ── 选中+展开（交由 store 自包含处理）──
  const handleSelectGraphNode = async (node: GraphNode, partitionId: string) => {
    await selectGraphNode(node, partitionId);
  };

  return (
    <div className="flex flex-col h-full bg-[var(--color-page-secondary)] border-r border-[var(--color-border)] select-none">
      {!compact && (
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-[var(--color-border)]">
          <div className="flex items-center gap-1.5">
            <FolderOpen size={15} className="text-[var(--color-accent)]" />
            <span className="text-xs font-semibold text-[var(--color-text)]">学习空间</span>
          </div>
          <div className="flex items-center gap-1">
          </div>
        </div>
      )}
      <div className="flex-1 overflow-hidden py-1" data-testid="sidebar-tree">
        {sidebarMode === "flat" ? (
          <FlatConversationList
            onRenameConv={nav.handleRenameConv}
            onDeleteConv={nav.setDeleteTarget}
          />
        ) : loading ? (
          <div className="p-3 space-y-2" aria-busy="true" aria-label="加载中">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="flex items-center gap-2">
                <Skeleton variant="circle" className="h-3 w-3" />
                <Skeleton variant="text" className="h-3 flex-1" />
              </div>
            ))}
          </div>
        ) : nav.rootNodes.length === 0 ? (
          <EmptyState
            icon="📂"
            title="暂无分区"
            description="发送消息将自动创建"
          />
        ) : (
          nav.rootNodes.map(node => (
            <SidebarTreeNode
              key={node.id} node={node} depth={0}
              partitionId={node.id}
              expandedSet={nav.expandedSet} loadingSet={nav.loadingSet}
              childMap={nav.childMap}
              selectedNode={selectedNode}
              ancestorIds={ancestorIds}
              editingId={nav.editingId} editValue={nav.editValue}
              toggleExpand={nav.toggleExpand} handleCreateChild={nav.handleCreateChild}
              handleNewConvClick={nav.handleNewConvClick}
              setEditingId={nav.setEditingId} setEditValue={nav.setEditValue}
              setDeleteTarget={nav.setDeleteTarget}
              handleRename={nav.handleRename} handleRenameConv={nav.handleRenameConv}
              onSelectGraphNode={handleSelectGraphNode}
            />
          ))
        )}
      </div>
      {nav.deleteTarget && (
        <ConfirmDialog onConfirm={nav.confirmDelete} onCancel={() => nav.setDeleteTarget(null)}>
          确认删除「{nav.deleteTarget.label}」及其所有子节点？此项操作不可恢复。
        </ConfirmDialog>
      )}
      <NewNodeDialog
        open={!!nav.newChildTarget}
        onClose={() => nav.setNewChildTarget(null)}
        onCreate={nav.confirmCreateChild}
        title="新建"
        namePlaceholder="输入名称"
        defaultEmoji={nav.newChildTarget?.defaultEmoji || "📚"}
        nameLabel="名称"
      />
    </div>
  );
}
