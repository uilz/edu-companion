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

// ── 将后端 KGNodeItem + tree 结构转为前端 GraphData ──
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
  const allIds = new Set(tree.nodes.map(n => n.id));
  const rootIds = tree.nodes
    .filter(n => !prerequisiteTargets.has(n.id))
    .map(n => n.id);

  // 分配 level
  const levelMap = new Map<string, string>();
  function assignLevel(id: string, depth: number) {
    const lv = depth === 0 ? "topic" : depth === 1 ? "concept" : "atom";
    levelMap.set(id, lv);
    for (const child of childrenOf.get(id) || []) {
      assignLevel(child, depth + 1);
    }
  }
  for (const rootId of rootIds) {
    assignLevel(rootId, 0);
  }

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
    parent: parentMap.get(n.id),
    is_visible: true,
    node_type: n.created_by === "user" ? "explicit" : "auto_generated",
    path_id: `${tree.partition_id}.${n.id.slice(0, 8)}`,
    emoji: "",
    brief: n.description || `${n.label}`,
    conversation_ids: tree.linked_conversations?.[n.id] || [],
  }));

  const edges: GraphEdge[] = [
    // prerequisite 边
    ...tree.edges.map(e => ({
      id: e.id,
      source: e.from_id,
      target: e.to_id,
      label: e.label || e.relation,
      relation: e.relation as GraphEdge["relation"],
    })),
    // parent-child 边（没有 prerequisite 但有父子推断的）
    ...nodes.filter(n => n.parent && !tree.edges.some(e => e.from_id === n.parent && e.to_id === n.id))
      .map(n => ({
        id: `parent_${n.parent}_${n.id}`,
        source: n.parent!,
        target: n.id,
        label: "包含",
        relation: "parent" as const,
      })),
  ];

  return { nodes, edges };
}

// ── 工具函数 ──

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
