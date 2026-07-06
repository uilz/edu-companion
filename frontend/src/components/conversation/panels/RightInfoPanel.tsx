"use client";

import React, { useEffect, useMemo, useState, useRef } from "react";
import {
  Network, ListChecks, Sparkles, ChevronRight, Edit3, Trash2,
  Plus, Library, BookOpen, Pen, Share2, MessageSquare, LayoutDashboard,
} from "lucide-react";
import { useNotificationStore } from "@/store/notification/notification-store";
import { apiFetch } from "@/store/conversation/tree-helpers";
import type { MessageNode } from "@/types";
import type { SelectedNode } from "@/components/conversation/tree/SidebarTreeNode";
import type { UseConversationReturn } from "@/hooks/conversation/useConversation";

interface RightInfoPanelProps {
  selectedNode: SelectedNode | null;
  activeDir: UseConversationReturn["activeDir"];
  activeConversationId: string | null;
  messages: MessageNode[];
  onRenameDir?: (id: string, name: string) => void;
  onDeleteDir?: (id: string) => void;
  onCreateSubdir?: () => void;
  onCreateConv?: () => void;
  onOpenKnowledgeTree?: (nodeId: string) => void;
}

// ── 卡片包装 ──
function InfoCard({ icon, title, children, action }: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--color-divider-soft)]">
        <span className="text-[var(--color-text-muted)]">{icon}</span>
        <span className="text-[11px] font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">{title}</span>
        {action && <div className="ml-auto">{action}</div>}
      </div>
      <div className="px-3 py-2.5">{children}</div>
    </div>
  );
}

// ── 当前节点 ──
function CurrentNodeCard({ selectedNode, activeDir }: { selectedNode: any; activeDir: any }) {
  if (!selectedNode) {
    return (
      <InfoCard icon={<Network size={12} />} title="当前节点">
        <p className="text-[12px] text-[var(--color-text-muted)]">未选择任何节点</p>
      </InfoCard>
    );
  }

  const isDir = selectedNode.level === "dir";
  const name = isDir ? activeDir?.name : (selectedNode.name || "未命名会话");
  const emoji = isDir ? activeDir?.emoji || "📁" : "💬";
  const kind = isDir ? activeDir?.kind || "目录" : "会话";
  const parent = selectedNode.parent;

  return (
    <InfoCard
      icon={<Network size={12} />}
      title="当前节点"
      action={
        <span className="text-[10px] text-[var(--color-text-muted)]">{selectedNode.level === "dir" ? "目录" : "会话"}</span>
      }
    >
      <div className="flex items-start gap-2">
        <span className="text-lg leading-none shrink-0">{emoji}</span>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-medium text-[var(--color-text)] truncate">{name}</div>
          <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
            {kind} · ID: {selectedNode.id?.slice(-8) || "—"}
          </div>
          {parent && (
            <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5 truncate">
              父节点: {parent}
            </div>
          )}
        </div>
      </div>
    </InfoCard>
  );
}

// ── 知识点标签缓存（模块级，组件挂载期有效）──
const labelCache = new Map<string, string>();

/** 拉取单个知识点标题，缓存结果 */
async function fetchNodeLabel(id: string): Promise<string> {
  if (labelCache.has(id)) return labelCache.get(id)!;
  try {
    const resp = await apiFetch<{ node: { label: string } }>(`/knowledge-tree/nodes/${id}`);
    const label = resp.node?.label || id.slice(-6);
    labelCache.set(id, label);
    return label;
  } catch {
    labelCache.set(id, id.slice(-6));
    return id.slice(-6);
  }
}

// ── 关联知识点：从消息 cognitive_node_ids 聚合 ──
function RelatedKnowledgeCard({ messages, onOpenKnowledgeTree, selectedNodeId }: {
  messages: MessageNode[];
  onOpenKnowledgeTree?: (nodeId: string) => void;
  selectedNodeId: string | null;
}) {
  // 提取所有 cognitive_node_ids
  const knowledgeIds = useMemo(() => {
    const set = new Set<string>();
    for (const m of messages) {
      for (const id of m.cognitive_node_ids || []) set.add(id);
    }
    return Array.from(set);
  }, [messages]);

  // 异步拉取节点标题
  const [labels, setLabels] = useState<Map<string, string>>(new Map());
  const fetchingRef = useRef(false);

  useEffect(() => {
    if (knowledgeIds.length === 0) return;

    // 检查缓存是否已覆盖所有 ID
    const uncached = knowledgeIds.filter(id => !labelCache.has(id));
    if (uncached.length === 0) {
      // 全部命中缓存，直接更新
      const m = new Map<string, string>();
      for (const id of knowledgeIds) {
        m.set(id, labelCache.get(id)!);
      }
      setLabels(m);
      return;
    }

    // 有未缓存的 — 分批拉取
    fetchingRef.current = true;
    let cancelled = false;

    (async () => {
      const m = new Map<string, string>(labels);
      for (const id of knowledgeIds) {
        if (cancelled) return;
        if (!m.has(id)) {
          const label = await fetchNodeLabel(id);
          if (!cancelled) {
            m.set(id, label);
            setLabels(new Map(m));
          }
        }
      }
      fetchingRef.current = false;
    })();

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [knowledgeIds]);

  if (knowledgeIds.length === 0) {
    return (
      <InfoCard
        icon={<Library size={12} />}
        title="关联知识点"
        action={
          onOpenKnowledgeTree ? (
            <button
              onClick={() => selectedNodeId && onOpenKnowledgeTree(selectedNodeId)}
              className="text-[10px] text-[var(--color-accent)] hover:underline"
            >
              打开图谱
            </button>
          ) : undefined
        }
      >
        <p className="text-[12px] text-[var(--color-text-muted)]">对话尚未关联知识点</p>
      </InfoCard>
    );
  }

  return (
    <InfoCard
      icon={<Library size={12} />}
      title="关联知识点"
      action={
        <span className="text-[10px] text-[var(--color-text-muted)]">{knowledgeIds.length}</span>
      }
    >
      <div className="flex flex-wrap gap-1.5">
        {knowledgeIds.slice(0, 6).map((id, idx) => (
          <div key={id} className="w-full flex items-center gap-1.5">
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] rounded-md bg-[var(--color-accent-soft)] text-[var(--color-accent)] border border-[var(--color-accent)]/20 cursor-default"
              title={id}
            >
              <span className="w-1 h-1 rounded-full bg-[var(--color-accent)]" />
              {labels.get(id) || id.slice(-6)}
            </span>
            <span className="ml-auto text-[9px] text-[var(--color-text-muted)] font-mono">
              {0.8 - idx * 0.1}
            </span>
          </div>
        ))}
        {knowledgeIds.length > 6 && (
          <span className="text-[10px] text-[var(--color-text-muted)]">+{knowledgeIds.length - 6}</span>
        )}
      </div>
    </InfoCard>
  );
}

// ── 本节操作 ──
function SectionActionsCard({
  selectedNode,
  activeDir,
  onRenameDir,
  onDeleteDir,
  onCreateSubdir,
  onCreateConv,
}: Pick<RightInfoPanelProps, "onRenameDir" | "onDeleteDir" | "onCreateSubdir" | "onCreateConv" | "selectedNode"> & {
  activeDir: RightInfoPanelProps["activeDir"];
}) {
  const isDir = selectedNode?.level === "dir";
  const dirName = activeDir?.name || "";

  const actions = isDir
    ? [
        { icon: <Plus size={11} />, label: "新建子目录", onClick: onCreateSubdir },
        { icon: <Edit3 size={11} />, label: "重命名", onClick: selectedNode && onRenameDir ? () => onRenameDir(selectedNode.id, dirName) : undefined },
        { icon: <Trash2 size={11} />, label: "删除", danger: true, onClick: selectedNode && onDeleteDir ? () => onDeleteDir(selectedNode.id) : undefined },
      ]
    : [
        { icon: <Plus size={11} />, label: "新建会话", onClick: onCreateConv },
      ];

  return (
    <InfoCard icon={<ListChecks size={12} />} title="本节操作">
      <div className="flex flex-col gap-0.5">
        {actions.map((a, i) => (
          <button
            key={i}
            disabled={!a.onClick}
            onClick={a.onClick}
            className={`flex items-center gap-2 px-2 py-1.5 text-[12px] rounded-md text-left transition-colors ${
              a.danger
                ? "text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10"
                : "text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            <span className="text-[var(--color-text-muted)]">{a.icon}</span>
            <span className="flex-1">{a.label}</span>
            <ChevronRight size={11} className="text-[var(--color-text-muted)]" />
          </button>
        ))}
      </div>
    </InfoCard>
  );
}

// ── 秘书提示：复用 notification store ──
function SecretaryHintsCard() {
  const notifications = useNotificationStore((s) => s.notifications);
  const inlineHints = useMemo(
    () => notifications.filter(n => n.status === "pending" && !n.hidden && (!n.snoozedUntil || Date.now() >= n.snoozedUntil)).slice(0, 3),
    [notifications]
  );

  if (inlineHints.length === 0) {
    return (
      <InfoCard icon={<Sparkles size={12} />} title="秘书提示">
        <p className="text-[12px] text-[var(--color-text-muted)]">暂无秘书提示</p>
      </InfoCard>
    );
  }

  return (
    <InfoCard
      icon={<Sparkles size={12} />}
      title="秘书提示"
      action={<span className="text-[10px] text-[var(--color-text-muted)]">{inlineHints.length}</span>}
    >
      <div className="flex flex-col gap-1.5">
        {inlineHints.map((n) => (
          <div key={n.id} className="text-[11px] text-[var(--color-text-secondary)] leading-relaxed px-2 py-1.5 rounded-md bg-[var(--color-warning)]/5 border-l-2 border-[var(--color-warning)]/40">
            {n.title || n.description}
          </div>
        ))}
      </div>
    </InfoCard>
  );
}

// ── 快速操作网格 ──
function QuickActionsCard() {
  const actions = [
    { icon: <Pen size={14} />, label: "标注", onClick: undefined },
    { icon: <LayoutDashboard size={14} />, label: "制卡", onClick: undefined },
    { icon: <MessageSquare size={14} />, label: "费曼", onClick: undefined },
    { icon: <BookOpen size={14} />, label: "笔记", onClick: undefined },
    { icon: <Share2 size={14} />, label: "导图", onClick: undefined },
    { icon: <Library size={14} />, label: "引用", onClick: undefined },
  ];

  return (
    <InfoCard icon={<ListChecks size={12} />} title="快速操作">
      <div className="grid grid-cols-3 gap-1.5">
        {actions.map((a, i) => (
          <button
            key={i}
            onClick={a.onClick}
            disabled={!a.onClick}
            className="flex flex-col items-center gap-1 px-2 py-2 text-[10px] rounded-md text-[var(--color-text-secondary)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent)]/5 border border-transparent hover:border-[var(--color-accent)]/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <span className="text-[var(--color-text-muted)] group-hover:text-[var(--color-accent)]">{a.icon}</span>
            <span>{a.label}</span>
          </button>
        ))}
      </div>
    </InfoCard>
  );
}

// ── 顶层 RightInfoPanel ──
export default function RightInfoPanel({
  selectedNode,
  activeDir,
  messages,
  onRenameDir,
  onDeleteDir,
  onCreateSubdir,
  onCreateConv,
  onOpenKnowledgeTree,
}: RightInfoPanelProps) {
  const selectedNodeId = selectedNode?.id ?? null;
  return (
    <div className="flex flex-col gap-2 p-3 overflow-y-auto h-full">
      <CurrentNodeCard selectedNode={selectedNode} activeDir={activeDir} />
      <RelatedKnowledgeCard
        messages={messages}
        onOpenKnowledgeTree={onOpenKnowledgeTree}
        selectedNodeId={selectedNodeId}
      />
      <SectionActionsCard
        selectedNode={selectedNode}
        activeDir={activeDir}
        onRenameDir={onRenameDir}
        onDeleteDir={onDeleteDir}
        onCreateSubdir={onCreateSubdir}
        onCreateConv={onCreateConv}
      />
      <SecretaryHintsCard />
      <QuickActionsCard />
    </div>
  );
}
