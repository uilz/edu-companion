// 知识图谱 API 工具
import type { GraphData, GraphNode, GraphEdge } from "@/lib/types/graph-types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export async function fetchGraphData(userId = "default_user"): Promise<GraphData> {
  const res = await fetch(`${API_BASE}/api/v2/graph/nodes?user_id=${userId}`);
  const rawNodes = await res.json();

  // Transform API nodes to GraphNode format
  const nodes: GraphNode[] = rawNodes.map((n: any) => ({
    id: n.id,
    label: n.label || n.id,
    level: n.level || "atom",
    mastery: n.mastery ?? 0,
    trend: (n.trend?.direction as "ascending" | "descending" | "stable") ?? "stable",
    children: n.children || [],
    parent: n.parent || undefined,
    is_visible: n.is_visible ?? true,
    node_type: n.node_type || "explicit",
    path_id: n.path_id || "",
    emoji: n.emoji || "",
    color: n.color || "",
    brief: n.brief || "",
  }));

  // Generate edges from parent-child relationships
  const edges: GraphEdge[] = [];
  const edgeSet = new Set<string>();
  for (const node of nodes) {
    if (node.parent) {
      const key = `${node.parent}->${node.id}`;
      if (!edgeSet.has(key)) {
        edgeSet.add(key);
        edges.push({
          id: `edge_${key}`,
          source: node.parent,
          target: node.id,
          relation: "parent",
        });
      }
    }
  }

  return { nodes, edges };
}
