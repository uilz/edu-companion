"use client";

import { useEffect, useMemo } from "react";
import { Plus, Hash, FolderOpen } from "lucide-react";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { NewNodeDialog } from "@/components/ui/NewNodeDialog";
import { SidebarTreeNode } from "@/components/conversation/tree/SidebarTreeNode";
import { useTreeNavigation } from "@/hooks/graph/useTreeNavigation";
import { useConversationStore } from "@/store/conversation/conversation-store";
import type { GraphNode } from "@/components/conversation/tree/SidebarTreeNode";
import { ROOT_KEY } from "@/components/conversation/tree/SidebarTreeNode";

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
  selectedPartitionId: _selectedNodeId,
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
  // ── 挂载时统一导航入口：覆盖 URL 恢复的三种场景 ──
  //  1) ?p=xxx&c=yyy (有会话、无 domain/topic) → 从后端解析路径 → 展开 + 选中
  //  2) ?p=xxx&d=yyy&t=zzz (有 domain/topic)       → 直接 expandPath
  //  3) ?p=xxx (仅分区)                              → 展开分区级
  useEffect(() => {
    const init = async () => {
      const store = useConversationStore.getState();
      if (!store.rootLoaded) {
        await store.loadRootNodes();
      }
      const s = useConversationStore.getState();
      const pid = s.selectedPartitionId;
      if (!pid) return;

      const cid = s.activeConversationId;
      const did = s.activeDomainId;
      const tid = s.activeTopicId;

      if (cid && (!did || !tid)) {
        // 场景1：有会话但缺少 domain/topic → 从后端解析完整路径
        const path = await s.resolveConversationPath(cid);
        if (path && path.partition_id) {
          useConversationStore.setState({
            selectedPartitionId: path.partition_id,
            activeDomainId: path.domain_id || null,
            activeTopicId: path.topic_id || null,
            selectedNode: path.topic_id
              ? { id: path.topic_id, level: "topic", parent: path.domain_id || path.partition_id }
              : path.domain_id
                ? { id: path.domain_id, level: "domain", parent: path.partition_id }
                : null,
          });
          await store.expandPath(path.partition_id, path.domain_id || null, path.topic_id || null);
          store.selectConversation(path.partition_id, cid);
        }
      } else if (did || tid) {
        // 场景2：已有 domain/topic → 直接展开 + 设置 selectedNode
        useConversationStore.setState({
          selectedNode: tid
            ? { id: tid, level: "topic", parent: did || pid }
            : did
              ? { id: did, level: "domain", parent: pid }
              : null,
        });
        await store.expandPath(pid, did, tid);
      } else {
        // 场景3：仅分区 → 展开分区级 + 设置 selectedNode
        useConversationStore.setState({
          selectedNode: { id: pid, level: "partition", parent: null },
        });
        await store.expandPath(pid);
      }
    };
    init();
  }, []);

  const nav = useTreeNavigation(onConversationReady, onTreeChanged);
  const selectGraphNode = useConversationStore(s => s.selectGraphNode);
  const selectedNode = useConversationStore(s => s.selectedNode);
  const childMap = useConversationStore(s => s.childMap);
  const convActiveConvId = useConversationStore(s => s.activeConversationId);
  const effectiveConvId = activeConversationId ?? convActiveConvId;

  // ── 构建 parentMap（子→父映射），用于计算祖先链 ──
  // 补全 parentMap：用 store 中的层级 ID 填充 childMap 未覆盖的映射
  const parentMap = useMemo(() => {
    const map = new Map<string, string>();
    childMap.forEach((children, parentId) => {
      for (const child of children) {
        map.set(child.id, parentId);
      }
    });
    // 补全：topic → domain、domain → partition（childMap 可能未加载这些层级）
    const s = useConversationStore.getState();
    if (s.activeTopicId && s.activeDomainId && !map.has(s.activeTopicId)) {
      map.set(s.activeTopicId, s.activeDomainId);
    }
    if (s.activeDomainId && s.selectedPartitionId && !map.has(s.activeDomainId)) {
      map.set(s.activeDomainId, s.selectedPartitionId);
    }
    return map;
  }, [childMap, activeDomainId, activeTopicId, _selectedNodeId]);

  // ── 计算祖先链 ──
  // 有活跃会话时，直接用 store 中的层级 ID 构建祖先集，不依赖 parentMap 回溯
  const ancestorIds = useMemo(() => {
    const ids = new Set<string>();

    if (effectiveConvId) {
      // 有活跃会话：把 selectedNode.id + activeTopicId + activeDomainId + selectedPartitionId 全部加入
      if (selectedNode?.id) ids.add(selectedNode.id);
      const s = useConversationStore.getState();
      if (s.activeTopicId) ids.add(s.activeTopicId);
      if (s.activeDomainId) ids.add(s.activeDomainId);
      if (s.selectedPartitionId) ids.add(s.selectedPartitionId);
      return ids;
    }

    // 无活跃会话时，用 parentMap 回溯选中节点的父链
    let startId = selectedNode?.parent ?? null;
    if (!startId) return ids;

    let cur: string | null = startId;
    while (cur) {
      if (cur === ROOT_KEY) break;
      ids.add(cur);
      cur = parentMap.get(cur) || null;
    }
    return ids;
  }, [selectedNode, parentMap, effectiveConvId, activeDomainId, activeTopicId, _selectedNodeId]);

  // ── 选中+展开（交由 store 自包含处理）──
  const handleSelectGraphNode = async (node: GraphNode, partitionId: string) => {
    await selectGraphNode(node, partitionId);
  };

  // 有活跃会话时，树节点不显示选中态（会话自身的强高亮由 activeConversationId 控制）
  const treeSelectedNode = effectiveConvId ? null : selectedNode;

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
              selectedNode={treeSelectedNode}
              ancestorIds={ancestorIds}
              convCache={nav.convCache} activeConversationId={activeConversationId}
              editingId={nav.editingId} editValue={nav.editValue}
              toggleExpand={nav.toggleExpand} handleCreateChild={nav.handleCreateChild}
              handleNewConvClick={nav.handleNewConvClick}
              setEditingId={nav.setEditingId} setEditValue={nav.setEditValue}
              setDeleteTarget={nav.setDeleteTarget}
              handleRename={nav.handleRename} handleRenameConv={nav.handleRenameConv}
              onSelectConv={onSelectConv}
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
        title={nav.newChildTarget?.level === "domain" ? "新建领域" : nav.newChildTarget?.level === "topic" ? "新建专题" : "新建"}
        namePlaceholder={nav.newChildTarget?.level === "domain" ? "例如: 分析" : nav.newChildTarget?.level === "topic" ? "例如: 微积分" : "输入名称"}
        defaultEmoji={nav.newChildTarget?.defaultEmoji || "📚"}
        nameLabel={nav.newChildTarget?.level === "domain" ? "领域名称" : nav.newChildTarget?.level === "topic" ? "专题名称" : "名称"}
      />
    </div>
  );
}
