// 知识图谱数据模型 — 统一前后端类型

// ── 后端 KGNode 对应字段（由 /api/knowledge/graph/{pid} 返回） ──
export interface KGNodeItem {
  id: string;
  label: string;
  description: string;
  priority: number;
  tags: string[];
  created_by: string;  // "ai" | "user"
  version: number;
}

// ── 后端 KGEdge 对应字段 ──
export interface KGEdgeItem {
  id: string;
  from_id: string;
  to_id: string;
  relation: string;    // "prerequisite" | "extends" | "applies" | "related"
  label: string;
}

// ── 后端完整树结构返回 ──
export interface KGTreeResponse {
  ok: boolean;
  nodes: KGNodeItem[];
  edges: KGEdgeItem[];
  partition_name: string;
  partition_id: string;
  version: number;
  linked_conversations: Record<string, string[]>;
}

// ── 前端渲染用 GraphNode（含布局信息） ──
export interface GraphNode {
  id: string;
  label: string;
  description: string;
  level: string;            // "partition" | "domain" | "topic" | "concept" | "atom"  — 布局用层级
  mastery: number;          // 0-1 掌握度
  trend: string;            // "ascending" | "descending" | "stable"
  priority: number;         // 学习优先级 1-10
  tags: string[];
  created_by: string;
  children: string[];       // 子节点 ID 列表
  parent?: string;          // 父节点 ID（从 prerequisite 推断）
  is_visible: boolean;
  node_type: string;
  path_id: string;
  emoji?: string;
  color?: string;
  brief?: string;           // 短描述（用于卡片展示）
  conversation_ids?: string[];  // 关联的对话会话 ID
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  relation?: string;        // "parent" | "prerequisite" | "extends" | "applies" | "related"
  strength?: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface LayoutNode extends GraphNode {
  x: number;
  y: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

// ── 对话卡片信息 ──
export interface DialogueCardInfo {
  id: string;
  question: string;
  summary: string;
  knowledgeNodes: string[];
  timestamp: string;
}

// ═══════════════════════════════════════════════════════
// 层级常量 — 从分区到原子的完整链路
// ═══════════════════════════════════════════════════════

export const LEVEL_ORDER: Record<string, number> = {
  partition: 0,
  domain: 1,
  topic: 2,
  concept: 3,
  atom: 4,
};

export const LEVEL_LABELS: Record<string, string> = {
  partition: "分区",
  domain: "领域",
  topic: "专题",
  concept: "概念",
  atom: "原子",
};

export const LEVEL_COLORS: Record<string, string> = {
  partition: "#6366f1",
  domain: "#3b82f6",
  topic: "#22c55e",
  concept: "#f59e0b",
  atom: "#a855f7",
};

// ═══════════════════════════════════════════════════════
// 将后端 KGNodeItem + tree 结构转为前端 GraphData
// ═══════════════════════════════════════════════════════
export function kgTreeToGraphData(tree: KGTreeResponse): GraphData {
  // 从 prerequisite 边推导父子关系
  const parentMap = new Map<string, string>();
  const prerequisiteTargets = new Set<string>();
  for (const edge of tree.edges) {
    if (edge.relation === "prerequisite") {
      parentMap.set(edge.to_id, edge.from_id);
      prerequisiteTargets.add(edge.to_id);
    }
  }

  // 构建子节点列表
  const childrenOf = new Map<string, string[]>();
  Array.from(parentMap.entries()).forEach(([childId, parentId]) => {
    const siblings = childrenOf.get(parentId) || [];
    siblings.push(childId);
    childrenOf.set(parentId, siblings);
  });
  // 根节点 = 没有任何 prerequisite 指向它的节点
  const rootIds = tree.nodes
    .filter(n => !prerequisiteTargets.has(n.id))
    .map(n => n.id);

  // ── 新层级分配：partition(虚拟) → domain → topic → concept → atom ──
  const levelMap = new Map<string, string>();
  function assignLevel(id: string, depth: number) {
    // depth 对应关系:
    //   0 → domain（原 root）
    //   1 → topic（原 concept）
    //   2 → concept（原 atom）
    //   3+ → atom（更深层）
    const lv = depth === 0
      ? "domain"
      : depth === 1
        ? "topic"
        : depth === 2
          ? "concept"
          : "atom";
    levelMap.set(id, lv);
    for (const child of childrenOf.get(id) || []) {
      assignLevel(child, depth + 1);
    }
  }
  for (const rootId of rootIds) {
    assignLevel(rootId, 0);
  }

  // ── 真实节点 ──
  const nodes: GraphNode[] = tree.nodes.map(n => ({
    id: n.id,
    label: n.label,
    description: n.description,
    level: levelMap.get(n.id) || "concept",
    mastery: 0,  // BKT 掌握度由认知引擎注入
    trend: "stable",
    priority: n.priority,
    tags: n.tags || [],
    created_by: n.created_by,
    children: childrenOf.get(n.id) || [],
    parent: parentMap.get(n.id) || undefined,
    is_visible: true,
    node_type: n.created_by === "user" ? "explicit" : "auto_generated",
    path_id: `${tree.partition_id}.${n.id.slice(0, 8)}`,
    emoji: "",
    brief: n.description || `${n.label}`,
    conversation_ids: tree.linked_conversations?.[n.id] || [],
  }));

  // ── 虚拟分区根节点 ──
  const partitionId = `partition:${tree.partition_id}`;
  const partitionNode: GraphNode = {
    id: partitionId,
    label: tree.partition_name || "知识图谱",
    description: "",
    level: "partition",
    mastery: 0,
    trend: "stable",
    priority: 0,
    tags: [],
    created_by: "system",
    children: rootIds,
    parent: undefined,
    is_visible: true,
    node_type: "explicit",
    path_id: tree.partition_id,
    emoji: "",
    brief: `分区: ${tree.partition_name || "知识图谱"}`,
  };

  // 将真实根节点的 parent 指向分区虚拟节点
  const nodeById = new Map<string, GraphNode>();
  nodes.forEach(n => nodeById.set(n.id, n));
  for (const rootId of rootIds) {
    const n = nodeById.get(rootId);
    if (n && !n.parent) {
      n.parent = partitionId;
    }
  }

  // ── 边 ──
  const edges: GraphEdge[] = [
    // 从分区指向领域级根节点
    ...rootIds.map((rid) => ({
      id: `edge_partition_${rid}`,
      source: partitionId,
      target: rid,
      label: "包含",
      relation: "parent" as const,
    })),
    // prerequisite 边
    ...tree.edges.map(e => ({
      id: e.id,
      source: e.from_id,
      target: e.to_id,
      label: e.label || e.relation,
      relation: e.relation as GraphEdge["relation"],
    })),
    // parent-child 边（没有 prerequisite 但有父子推断的）
    ...nodes.filter(n => n.parent && n.parent !== partitionId && !tree.edges.some(e => e.from_id === n.parent && e.to_id === n.id))
      .map(n => ({
        id: `parent_${n.parent}_${n.id}`,
        source: n.parent!,
        target: n.id,
        label: "包含",
        relation: "parent" as const,
      })),
  ];

  return { nodes: [partitionNode, ...nodes], edges };
}

// ═══════════════════════════════════════════════════════
// 通用层级过滤（含原子兼容层 — 选上一级自动包含下一级）
// ═══════════════════════════════════════════════════════
export function filterByLevel(data: GraphData, maxLevel: string | undefined): GraphData {
  if (!maxLevel || !data?.nodes?.length) return data;
  const max = LEVEL_ORDER[maxLevel] ?? 99;
  // 多包含一级子节点，保证选择 concept 时能看到 atom（depth 3+）
  const effectiveMax = Math.min(max + 1, 4);
  const filtered = data.nodes.filter(n => (LEVEL_ORDER[n.level] ?? 99) <= effectiveMax);
  const ids = new Set(filtered.map(n => n.id));
  const edges = data.edges.filter(e => ids.has(e.source) && ids.has(e.target));
  return { nodes: filtered, edges };
}

// ═══════════════════════════════════════════════════════
// 子树聚焦：以某节点为根，返回其下完整子树
// ═══════════════════════════════════════════════════════
export function subtreeFilter(data: GraphData, rootId: string | undefined): GraphData {
  if (!rootId || !data?.nodes?.length) return data;

  // 收集 rootId 的所有后代
  const childrenOf = new Map<string, string[]>();
  for (const n of data.nodes) {
    if (n.parent) {
      const sib = childrenOf.get(n.parent) || [];
      sib.push(n.id);
      childrenOf.set(n.parent, sib);
    }
  }

  const descendantIds = new Set<string>();
  const walk = (id: string) => {
    descendantIds.add(id);
    for (const c of childrenOf.get(id) || []) walk(c);
  };
  walk(rootId);

  const nodes = data.nodes.filter(n => descendantIds.has(n.id));
  const ids = new Set(nodes.map(n => n.id));
  const edges = data.edges.filter(e => ids.has(e.source) && ids.has(e.target));

  // 把 rootId 的父指针清空（使之成为新根）
  return {
    nodes: nodes.map(n => n.id === rootId ? { ...n, parent: undefined } : n),
    edges,
  };
}

// ═══════════════════════════════════════════════════════
// 获取节点祖先链（用于面包屑导航）
// ═══════════════════════════════════════════════════════
export function getNodeAncestors(data: GraphData, nodeId: string): GraphNode[] {
  const nodeMap = new Map(data.nodes.map(n => [n.id, n]));
  const ancestors: GraphNode[] = [];
  let current = nodeMap.get(nodeId);
  while (current?.parent) {
    const parent = nodeMap.get(current.parent);
    if (parent) {
      ancestors.unshift(parent);
      current = parent;
    } else break;
  }
  return ancestors;
}

// ═══════════════════════════════════════════════════════
// 根据节点 id 找节点
// ═══════════════════════════════════════════════════════
export function findNodeById(data: GraphData, nodeId: string): GraphNode | undefined {
  return data.nodes.find(n => n.id === nodeId);
}

// ═══════════════════════════════════════════════════════
// 工具函数
// ═══════════════════════════════════════════════════════

export function getMasteryColor(mastery: number): string {
  if (mastery >= 0.8) return "#22c55e";
  if (mastery >= 0.6) return "#3b82f6";
  if (mastery >= 0.3) return "#f59e0b";
  if (mastery > 0) return "#ef4444";
  return "#9ca3af";
}

export function getNodeRadius(level: string): number {
  switch (level) {
    case "partition": return 14;
    case "domain":    return 11;
    case "topic":     return 9;
    case "concept":   return 7;
    case "atom":      return 5;
    default:          return 6;
  }
}

export function getTrendIcon(trend: string): string {
  switch (trend) {
    case "ascending":  return "↑";
    case "descending": return "↓";
    case "plateau":    return "→";
    case "volatile":   return "↕";
    default:           return "—";
  }
}

// 边颜色（按类型）
export function getEdgeColor(relation: string): string {
  switch (relation) {
    case "prerequisite": return "#3b82f6";   // 蓝色实线
    case "extends":      return "#22c55e";   // 绿色虚线
    case "applies":      return "#f59e0b";   // 橙色
    case "related":      return "#a855f7";   // 紫色点线
    case "parent":       return "#94a3b8";   // 灰色
    default:             return "#94a3b8";
  }
}

export function getEdgeDash(relation: string): string {
  switch (relation) {
    case "prerequisite": return "";
    case "extends":      return "6,3";
    case "applies":      return "4,2";
    case "related":      return "2,4";
    case "parent":       return "3,3";
    default:             return "";
  }
}
