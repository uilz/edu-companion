// ============================================================
//  Project 共享类型 (Task #89 — 详情页拆分)
// ============================================================

import {
  ListTree,
  Type,
  Table2,
  Columns,
  Code,
  Paperclip,
  Layers,
} from "lucide-react";
import { ReactNode } from "react";

export type ProjectViewName = "document" | "outline" | "kanban" | "knowledge" | "activity";

export const PROJECT_VIEW_NAMES: ProjectViewName[] = [
  "document",
  "outline",
  "kanban",
  "knowledge",
  "activity",
];

// ── 实体 ──

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  tags: string[];
  node_count: number;
  completed_node_count: number;
  template_id: string | null;
  created_at: string;
  updated_at: string;
  nodes: ProjectNode[];
  milestones: Milestone[];
}

export interface ProjectNode {
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
  status: string; // pending | active | completed | archived (Task #89 看板)
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  tags: string[];
  order_in_parent: number;
  linked_node_ids: string[];
  linked_material_ids: string[];
  linked_card_ids: string[];
}

export interface Milestone {
  id: string;
  milestone_name: string;
  snapshot_data: Record<string, unknown>;
  is_user_marked: boolean;
  marked_at: string;
}

export interface Version {
  version_id: string;
  version_number: number;
  changed_fields: string[];
  diff_summary: string;
  is_rollback: boolean;
  rolled_back_from_version: number | null;
  change_source: string;
  created_at: string;
}

// ── 视图 Props ──

export interface ProjectViewProps {
  projectId: string;
  nodes: ProjectNode[];
  onOpenNode: (n: ProjectNode) => void;
  onAddNode: (parentId: string | null, type: number) => void;
  onCompleteNode: (n: ProjectNode) => void;
  onReorder: (parentId: string | null, newOrder: ProjectNode[]) => void | Promise<void>;
}

// ── 工具类型 ──

export interface NodeTypeInfo {
  label: string;
  icon: ReactNode;
  key: string;
}

export const NODE_TYPE_LABELS: Record<number, NodeTypeInfo> = {
  1: { label: "大纲", icon: <ListTree size={14} />, key: "outline" },
  2: { label: "文本", icon: <Type size={14} />, key: "text" },
  3: { label: "数据表", icon: <Table2 size={14} />, key: "table" },
  4: { label: "对比", icon: <Columns size={14} />, key: "compare" },
  5: { label: "代码", icon: <Code size={14} />, key: "code" },
  6: { label: "附件", icon: <Paperclip size={14} />, key: "attachment" },
  7: { label: "成果板", icon: <Layers size={14} />, key: "gallery" },
};

// ── 状态枚举 (看板列) ──

export const NODE_STATUS_COLUMNS = [
  { value: "pending", label: "草稿", color: "border-l-zinc-400" },
  { value: "active", label: "进行中", color: "border-l-[var(--color-accent)]" },
  { value: "completed", label: "已完成", color: "border-l-emerald-500" },
  { value: "archived", label: "已归档", color: "border-l-amber-500" },
] as const;

export type NodeStatusValue = (typeof NODE_STATUS_COLUMNS)[number]["value"];

// ── 工具函数 ──

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  return iso.slice(0, 16).replace("T", " ");
}

export function getChildren(nodes: ProjectNode[], parentId: string | null): ProjectNode[] {
  return nodes
    .filter((n) => n.parent_id === parentId)
    .sort((a, b) => a.order_in_parent - b.order_in_parent);
}

/**
 * 把树扁平化为带 depth 字段的数组（手稿/活动流用）
 * 拓扑排序：父在前，子在后；同层按 order_in_parent
 */
export interface FlatNode extends ProjectNode {
  depth: number;
  hasChildren: boolean;
}

export function flattenTree(nodes: ProjectNode[]): FlatNode[] {
  const result: FlatNode[] = [];
  const byParent = new Map<string | null, ProjectNode[]>();
  for (const n of nodes) {
    const list = byParent.get(n.parent_id) || [];
    list.push(n);
    byParent.set(n.parent_id, list);
  }
  for (const list of Array.from(byParent.values())) {
    list.sort((a: ProjectNode, b: ProjectNode) => a.order_in_parent - b.order_in_parent);
  }
  const childCount = new Map<string, number>();
  for (const n of nodes) {
    if (n.parent_id) {
      childCount.set(n.parent_id, (childCount.get(n.parent_id) || 0) + 1);
    }
  }
  const walk = (parentId: string | null, depth: number) => {
    const children = byParent.get(parentId) || [];
    for (const c of children) {
      result.push({
        ...c,
        depth,
        hasChildren: (childCount.get(c.id) || 0) > 0,
      });
      walk(c.id, depth + 1);
    }
  };
  walk(null, 0);
  return result;
}
