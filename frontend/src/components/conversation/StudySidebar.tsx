"use client";

import { useEffect } from "react";
import { Plus, Hash, FolderOpen } from "lucide-react";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { NewNodeDialog } from "@/components/ui/NewNodeDialog";
import { SidebarTreeNode } from "@/components/conversation/SidebarTreeNode";
import { useTreeNavigation } from "@/hooks/useTreeNavigation";
import { useConversationStore } from "@/store/conversation-store";
import type { GraphNode } from "@/components/conversation/SidebarTreeNode";

interface Props {
  partitions?: unknown[];
  selectedPartitionId: string | null;
  activeConversationId: string | null;
  activeDomainId?: string | null;
  activeTopicId?: string | null;
  initialConversationId?: string;
  onSelectConversation: (pid: string, cid: string) => void;
  onCreatePartition: () => void;
  onRenamePartition?: (id: string, name: string) => void;
  loading?: boolean;
  compact?: boolean;
  onNewConversation?: (level: string, parentId: string, partitionId?: string) => void;
  onConversationReady?: (partitionId: string, conversationId: string) => void;
  onTreeChanged?: () => void;
  onSelectConv?: (partitionId: string, conversationId: string) => void;
}

export default function StudySidebar({
  selectedPartitionId: selectedNodeId,
  activeConversationId,
  activeDomainId,
  activeTopicId,
  initialConversationId,
  onCreatePartition,
  loading = false, compact = false,
  onConversationReady,
  onTreeChanged,
  onSelectConv,
}: Props) {
  // 挂载时加载根节点
  useEffect(() => {
    const store = useConversationStore.getState();
    if (!store.rootLoaded) store.loadRootNodes();
  }, []);

  const nav = useTreeNavigation(onConversationReady, onTreeChanged);
  const selectGraphNode = useConversationStore(s => s.selectGraphNode);
  const selectedNode = useConversationStore(s => s.selectedNode);

  // ── 选中+展开（交由 store 自包含处理）──
  const handleSelectGraphNode = async (node: GraphNode, partitionId: string) => {
    await selectGraphNode(node, partitionId);
  };

  // ── 回退父级（已选中的节点点击后选中其父节点）──
  const handleGoUp = (node: GraphNode, partitionId: string) => {
    const parentId = node.parent;
    if (!parentId) return;
    // 根据当前级别确定父级级别
    const parentLevel = node.level === "topic" ? "domain" : "partition";
    // 创建最小父节点对象用于选中
    const parentNode: GraphNode = {
      id: parentId,
      label: "",
      level: parentLevel as any,
      parent: parentLevel === "domain" ? partitionId : null,
      nodeIndex: 0,
      path_id: parentId,
      is_visible: true,
      node_type: "explicit",
      suggested_count: 0,
      created_at: 0,
    };
    selectGraphNode(parentNode, partitionId);
  };

  return (
    <div className="flex flex-col h-full bg-[var(--color-page-secondary)] border-r border-[var(--color-border)] select-none">
      {!compact && (
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-[var(--color-border)]">
          <div className="flex items-center gap-1.5">
            <FolderOpen size={15} className="text-[var(--color-accent)]" />
            <span className="text-xs font-semibold text-[var(--color-text)]">学习空间</span>
          </div>
          <button onClick={onCreatePartition}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] active:scale-[0.97] transition-all rounded" title="新建分区">
            <Plus size={15} />
          </button>
        </div>
      )}
      <div className="flex-1 overflow-y-auto py-1">
        {loading ? (
          <div className="px-4 py-8 text-center text-xs text-[var(--color-text-muted)]">加载中...</div>
        ) : nav.rootNodes.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <Hash size={18} className="text-[var(--color-text-muted)] mx-auto mb-2" />
            <div className="text-xs text-[var(--color-text-muted)]">暂无分区</div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1 opacity-60">发送消息将自动创建</div>
          </div>
        ) : (
          nav.rootNodes.map(node => (
            <SidebarTreeNode
              key={node.id} node={node} depth={0}
              partitionId={node.level === "partition" ? node.id : undefined}
              expandedSet={nav.expandedSet} loadingSet={nav.loadingSet}
              childMap={nav.childMap}
              selectedNode={selectedNode}
              convCache={nav.convCache} activeConversationId={activeConversationId}
              editingId={nav.editingId} editValue={nav.editValue}
              toggleExpand={nav.toggleExpand} handleCreateChild={nav.handleCreateChild}
              handleNewConvClick={nav.handleNewConvClick}
              setEditingId={nav.setEditingId} setEditValue={nav.setEditValue}
              setDeleteTarget={nav.setDeleteTarget}
              handleRename={nav.handleRename} handleRenameConv={nav.handleRenameConv}
              onSelectConv={onSelectConv}
              onSelectGraphNode={handleSelectGraphNode}
              onGoUp={handleGoUp}
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
        title={nav.newChildTarget?.level === "domain" ? "新建领域" : nav.newChildTarget?.level === "topic" ? "新建专题" : "新建"}
        namePlaceholder={nav.newChildTarget?.level === "domain" ? "例如: 分析" : nav.newChildTarget?.level === "topic" ? "例如: 微积分" : "输入名称"}
        defaultEmoji={nav.newChildTarget?.defaultEmoji || "📚"}
        nameLabel={nav.newChildTarget?.level === "domain" ? "领域名称" : nav.newChildTarget?.level === "topic" ? "专题名称" : "名称"}
      />
    </div>
  );
}
