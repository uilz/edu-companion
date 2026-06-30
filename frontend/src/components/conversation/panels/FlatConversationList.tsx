"use client";

import React, { useEffect, useState, useCallback } from "react";
import { MessageSquare, Hash, MoreVertical, Pencil, Trash2 } from "lucide-react";
import { tree } from "@/lib/api/api";
import { useConversationStore } from "@/store/conversation/conversation-store";
import { useTreeStore } from "@/store/conversation/tree-store";
import type { GraphNode } from "@/components/conversation/tree/SidebarTreeNode";

// ══════════════════════════════════════════════════════════════
//  类型定义
// ══════════════════════════════════════════════════════════════

interface AncestorInfo {
  id: string;
  name: string;
  node_type: string;
}

interface RecentConversation {
  id: string;
  display_name: string;
  name: string;
  parent_id: string | null;
  path: string[];
  node_type: string;
  kind: string;
  updated_at: number;
  created_at: number;
  ancestors: AncestorInfo[];
}

interface RecentConversationsResponse {
  conversations: RecentConversation[];
}

// ══════════════════════════════════════════════════════════════
//  辅助：判断是否最近活跃（24 小时内）
// ══════════════════════════════════════════════════════════════

function isRecentlyActive(updatedAt: number): boolean {
  const ONE_DAY_MS = 24 * 60 * 60 * 1000;
  return Date.now() - updatedAt * 1000 < ONE_DAY_MS;
}

// ══════════════════════════════════════════════════════════════
//  FlatConversationList
// ══════════════════════════════════════════════════════════════

interface FlatConversationListProps {
  onRenameConv?: (convId: string, name: string, parentId: string) => void;
  onDeleteConv?: (target: { id: string; label: string; parentId?: string; isConv?: boolean; parent?: string | null }) => void;
}

export function FlatConversationList({ onRenameConv, onDeleteConv }: FlatConversationListProps) {
  const [conversations, setConversations] = useState<RecentConversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── 三点菜单状态 ──
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const menuLeaveTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  function clearMenuTimer() {
    if (menuLeaveTimerRef.current) { clearTimeout(menuLeaveTimerRef.current); menuLeaveTimerRef.current = null; }
  }
  function startMenuTimer() {
    clearMenuTimer();
    menuLeaveTimerRef.current = setTimeout(() => setOpenMenuId(null), 350);
  }
  React.useEffect(() => {
    if (!openMenuId) return;
    const handler = () => setOpenMenuId(null);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [openMenuId]);

  const selectGraphNode = useConversationStore(s => s.selectGraphNode);
  const selectedNodeId = useConversationStore(s => s.selectedNode?.id);

  // ── 获取最近的会话 ──
  const fetchRecent = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await tree<RecentConversationsResponse>(
        "/tree/conversations/recent?limit=50",
      );
      setConversations(data.conversations || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
      setConversations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRecent();
  }, [fetchRecent]);

  // ── 点击行 → 导航到该会话 ──
  const handleRowClick = useCallback(async (conv: RecentConversation) => {
    const node: GraphNode = {
      id: conv.id,
      label: conv.display_name || conv.name,
      level: "conv",
      parent: conv.parent_id,
      nodeIndex: 0,
      path_id: conv.name,
      is_visible: true,
      node_type: "conv",
      kind: conv.kind || "general",
      suggested_count: 0,
      created_at: conv.created_at,
      brief: "",
      path: conv.path || [],
      emoji: "",
    };
    // 确定 partitionId（取路径中第一个 dir 节点 ID，或父节点）
    const partitionId = conv.parent_id || conv.id;
    // 确保父节点已展开并加载
    const treeState = useTreeStore.getState();
    if (conv.parent_id && !treeState.childMap.has(conv.parent_id)) {
      await treeState.loadChildren(conv.parent_id, "dir").catch(() => {});
    }
    await selectGraphNode(node, partitionId);
  }, [selectGraphNode]);

  // ── 构建面包屑路径文字 ──
  const buildBreadcrumb = (conv: RecentConversation): string => {
    if (conv.ancestors && conv.ancestors.length > 0) {
      return conv.ancestors.map(a => a.name).join(" / ");
    }
    return "";
  };

  // ── 加载状态 ──
  if (loading) {
    return (
      <div className="px-4 py-8 text-center text-xs text-[var(--color-text-muted)]">
        加载中...
      </div>
    );
  }

  // ── 错误状态 ──
  if (error) {
    return (
      <div className="px-4 py-8 text-center">
        <div className="text-xs text-[var(--color-error)]">{error}</div>
        <button
          onClick={fetchRecent}
          className="mt-2 text-xs text-[var(--color-accent)] hover:underline"
        >
          重试
        </button>
      </div>
    );
  }

  // ── 空状态 ──
  if (conversations.length === 0) {
    return (
      <div className="px-4 py-8 text-center">
        <Hash size={18} className="text-[var(--color-text-muted)] mx-auto mb-2" />
        <div className="text-xs text-[var(--color-text-muted)]">暂无会话</div>
        <div className="text-[10px] text-[var(--color-text-muted)] mt-1 opacity-60">
          发送消息将自动创建
        </div>
      </div>
    );
  }

  // ── 列表 ──
  return (
    <div className="py-1">
      {conversations.map(conv => {
        const isSelected = selectedNodeId === conv.id;
        const breadcrumb = buildBreadcrumb(conv);
        const recent = isRecentlyActive(conv.updated_at);

        return (
          <div
            key={conv.id}
            role="button"
            tabIndex={0}
            className={`group flex cursor-pointer items-start px-3 py-3 transition-colors ${
              isSelected
                ? "bg-[var(--color-surface)] font-semibold text-[var(--color-text)]"
                : "bg-transparent text-[var(--color-text-secondary)] hover:bg-[rgb(245_245_247)] dark:hover:bg-[rgb(30_30_32)]"
            }`}
            onClick={() => handleRowClick(conv)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleRowClick(conv);
              }
            }}
          >
            {/* 图标 */}
            <span className="mr-2 mt-0.5 flex-shrink-0 text-[var(--color-text-muted)]">
              <MessageSquare size={13} />
            </span>

            {/* 文字区 */}
            <div className="flex-1 min-w-0">
              {/* 名称行 */}
              <div className="flex items-center gap-1.5">
                <span className={`truncate text-xs ${
                  isSelected
                    ? "text-[var(--color-text)] font-semibold"
                    : "text-[var(--color-text-secondary)] font-normal"
                }`}>
                  {conv.display_name || conv.name}
                </span>
                {recent && (
                  <span className="flex-shrink-0 rounded bg-[var(--color-accent)]/10 px-1.5 py-0.5 text-[10px] text-[var(--color-accent)]">
                    活跃
                  </span>
                )}
              </div>

              {/* 面包屑路径 */}
              {breadcrumb && (
                <div className="mt-0.5 truncate text-[10px] text-[var(--color-text-muted)] opacity-60">
                  {breadcrumb}
                </div>
              )}
            </div>

            {/* 三点菜单 */}
            <div
              className="ml-1 flex-shrink-0 opacity-0 transition-opacity group-hover:opacity-100 max-lg:opacity-100"
              onClick={(e) => e.stopPropagation()}
              onMouseEnter={clearMenuTimer}
              onMouseLeave={startMenuTimer}
            >
              <div className="relative">
                <button
                  onClick={(e) => { e.stopPropagation(); setOpenMenuId(prev => prev === conv.id ? null : conv.id); }}
                  className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)] rounded"
                  style={{ minWidth: 44, minHeight: 44 }}
                  title="更多操作"
                >
                  <MoreVertical size={11} />
                </button>
                {openMenuId === conv.id && (
                  <div
                    className="absolute right-0 top-full mt-1 z-50 min-w-[120px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] py-1 shadow-lg"
                    onClick={(e) => e.stopPropagation()}
                    onMouseEnter={clearMenuTimer}
                    onMouseLeave={startMenuTimer}
                  >
                    <button
                      onClick={() => {
                        const newName = window.prompt("输入新名称", conv.display_name || conv.name);
                        if (newName && newName.trim()) {
                          onRenameConv?.(conv.id, newName.trim(), conv.parent_id || "");
                        }
                        setOpenMenuId(null);
                      }}
                      className="flex w-full items-center gap-2 px-4 py-2.5 text-xs text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)]"
                      style={{ minHeight: 44 }}
                    >
                      <Pencil size={12} /> 重命名
                    </button>
                    <button
                      onClick={() => {
                        onDeleteConv?.({ id: conv.id, label: conv.display_name || conv.name, parentId: conv.parent_id || undefined, isConv: true, parent: conv.parent_id });
                        setOpenMenuId(null);
                      }}
                      className="flex w-full items-center gap-2 px-4 py-2.5 text-xs text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)]"
                      style={{ minHeight: 44 }}
                    >
                      <Trash2 size={12} /> 删除
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
