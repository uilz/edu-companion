// 知识图谱 API 工具 — 四实体解耦架构
// 新 API 前缀: /api/knowledge-tree

import type { GraphData, GraphNode, GraphEdge } from "@/lib/types/graph-types";
import { knowledgeNodesApi, navigationApi, type KnowledgeNode, type NavigationNode } from "@/lib/api/knowledge-tree-api";
import { api } from "@/lib/api/api";

// ══════════════════════════════════════════════════════════════
// 将 KnowledgeNode[] 转换为 GraphData (替代旧 kgTreeToGraphData)
// ══════════════════════════════════════════════════════════════

export function kgNodesToGraphData(nodes: KnowledgeNode[]): GraphData {
  const nodeById = new Map<string, KnowledgeNode>();
  nodes.forEach(n => nodeById.set(n.id, n));

  // 构建 GraphNode[]
  const graphNodes: GraphNode[] = nodes.map(n => ({
    id: n.id,
    label: n.label,
    description: n.brief || "",
    level: n.level,
    mastery: n.mastery,
    trend: "stable",
    priority: n.sort_order || 0,
    tags: n.tags || [],
    created_by: n.created_by,
    children: n.children_order || [],
    parent: n.parent_id || undefined,
    is_visible: n.is_visible,
    node_type: n.node_type,
    path_id: n.path_id,
    emoji: n.emoji,
    color: n.color,
    brief: n.brief || n.label,
    conv_ids: [],
  }));

  // 构建 GraphEdge[]
  const edges: GraphEdge[] = [];

  for (const n of nodes) {
    // parent → child 边
    if (n.parent_id) {
      edges.push({
        id: `parent_${n.parent_id}_${n.id}`,
        source: n.parent_id,
        target: n.id,
        label: "包含",
        relation: "parent",
      });
    }
    // prerequisite 边
    for (const p of n.prerequisites || []) {
      edges.push({
        id: `prereq_${p.id}_${n.id}`,
        source: p.id,
        target: n.id,
        label: p.type === "strict" ? "前置" : "建议前置",
        relation: "prerequisite",
      });
    }
    // associate 边
    for (const a of n.associates || []) {
      edges.push({
        id: `assoc_${n.id}_${a.id}`,
        source: n.id,
        target: a.id,
        label: a.label || a.type || "相关",
        relation: "related",
        strength: a.strength,
      });
    }
  }

  return { nodes: graphNodes, edges };
}

// ══════════════════════════════════════════════════════════════
// 获取知识图谱数据 (从 /api/knowledge-tree/nodes)
// ══════════════════════════════════════════════════════════════

export async function fetchGraphData(partitionId?: string): Promise<GraphData> {
  // 如果指定了 partitionId，只请求该 domain 及其子节点
  const json = partitionId
    ? await knowledgeNodesApi.list({ parent_id: partitionId })
    : await knowledgeNodesApi.list();
  const nodes: KnowledgeNode[] = json.nodes || [];
  // 确保 partitionId 对应的 domain 节点也包含在内
  if (partitionId && !nodes.some(n => n.id === partitionId)) {
    try {
      const domainJson = await knowledgeNodesApi.get(partitionId);
      if (domainJson.node) nodes.unshift(domainJson.node);
    } catch { /* ignore */ }
  }
  return kgNodesToGraphData(nodes);
}

// ══════════════════════════════════════════════════════════════
// 获取分区列表 (从导航树获取，暂无 partition 概念，用导航根节点替代)
// ══════════════════════════════════════════════════════════════

export async function fetchPartitions(): Promise<
  { id: string; name: string; subject?: string; emoji?: string; has_graph: boolean; node_count: number; edge_count: number }[]
> {
  // 用知识节点的 domain 级别节点作为"分区"，与画布上显示的根节点一致
  try {
    const json = await knowledgeNodesApi.list({ level: "domain" });
    const nodes = json.nodes || [];
    if (nodes.length > 0) {
      return nodes.map((n: KnowledgeNode) => ({
        id: n.id,
        name: n.label,
        subject: n.brief,
        emoji: n.emoji,
        has_graph: true,
        node_count: 0,
        edge_count: 0,
      }));
    }
  } catch { /* fall through */ }

  // 回退：用导航树根节点
  try {
    const json = await navigationApi.getTree();
    const tree = json.tree || [];
    return tree.map((t: { id: string; name: string; kind?: string }) => ({
      id: t.id,
      name: t.name,
      subject: t.kind,
      emoji: "",
      has_graph: true,
      node_count: 0,
      edge_count: 0,
    }));
  } catch {
    return [];
  }
}
