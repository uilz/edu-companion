/**
 * graph-layout — 知识图谱类型定义与布局算法
 */

// ── 类型 ──
export interface KGNode { id: string; label: string; description?: string; mastery?: number; mastery_level?: string; priority?: number; tags?: string[]; created_by?: string; }
export interface KGEdge { id: string; from_id: string; to_id: string; relation?: string; label?: string; }
export interface GraphNode {
  id: string; label: string; description: string; subject: string;
  mastery: number; mastery_level: string; confidence: number;
  blocked: boolean; blocked_by: string[]; attempt_count: number;
  error_clusters: string[]; trend: string; review_urgency: number;
  anomaly_type: string | null; anomaly_detail: string | null;
  x?: number; y?: number;
}
export interface GraphEdge { from: string; to: string; label: string; satisfied: boolean; edgeId?: string; }
export interface Coverage { total: number; mastered: number; learning: number; weak: number; untouched: number; }

// ── 配色 ──
export const subjectColors: Record<string, string> = {
  "高等数学": "#0066FF", "大学物理": "var(--color-warning)",
  "计算机": "#22c55e", "线性代数": "#a855f7", "概率论": "#ec4899",
};
export const fallbackColor = "#737373";

export function masteryColor(m: number): string {
  if (m >= 95) return "#22c55e";
  if (m >= 70) return "#84cc16";
  if (m >= 40) return "var(--color-warning)";
  if (m > 0) return "#f97316";
  return "#525252";
}

// ── 拓扑布局 ──
export function computeLayout(nodes: GraphNode[], edges: GraphEdge[]): GraphNode[] {
  if (nodes.length === 0) return nodes;
  const inDegree = new Map<string, number>();
  const outEdges = new Map<string, string[]>();
  nodes.forEach((n) => { inDegree.set(n.id, 0); outEdges.set(n.id, []); });
  edges.forEach((e) => {
    inDegree.set(e.to, (inDegree.get(e.to) || 0) + 1);
    outEdges.get(e.from)?.push(e.to);
  });
  const layers: string[][] = [];
  const visited = new Set<string>();
  let queue = nodes.filter((n) => (inDegree.get(n.id) || 0) === 0).map((n) => n.id);
  while (queue.length > 0) {
    layers.push([...queue]);
    const next: string[] = [];
    for (const id of queue) {
      visited.add(id);
      for (const child of outEdges.get(id) || []) {
        const deg = (inDegree.get(child) || 1) - 1;
        inDegree.set(child, deg);
        if (deg === 0 && !visited.has(child)) next.push(child);
      }
    }
    queue = next;
  }
  const remaining = nodes.filter((n) => !visited.has(n.id));
  if (remaining.length > 0) layers.push(remaining.map((n) => n.id));

  const layerHeight = Math.max(140, 700 / Math.max(layers.length, 1));
  const nodeSpacing = Math.max(180, 900 / Math.max(Math.max(...layers.map(l => l.length)), 1));
  const marginX = 100, marginY = 80;
  const result = nodes.map((n) => ({ ...n }));
  layers.forEach((layer, li) => {
    const totalWidth = (layer.length - 1) * nodeSpacing;
    const startX = marginX + Math.max(0, (600 - totalWidth) / 2);
    layer.forEach((id, ni) => {
      const node = result.find((n) => n.id === id);
      if (node) { node.x = startX + ni * nodeSpacing; node.y = marginY + li * layerHeight; }
    });
  });
  return result;
}
