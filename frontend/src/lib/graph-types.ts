// 知识图谱数据模型
export interface GraphNode {
  id: string;
  label: string;
  level: string; // partition | domain | topic | concept | atom
  mastery: number; // 0-1
  trend: string; // ascending | descending | stable
  children: string[];
  parent?: string;
  is_visible: boolean;
  node_type: string;
  path_id: string;
  emoji?: string;
  color?: string;
  brief?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  strength?: number;
  relation?: string;
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

// 获取节点颜色（按掌握度）
// 对话卡片信息
export interface DialogueCardInfo {
  id: string;
  question: string;
  summary: string;
  knowledgeNodes: string[];
  timestamp: string;
}

export function getMasteryColor(mastery: number): string {
  if (mastery >= 0.8) return "#22c55e";     // green - mastered
  if (mastery >= 0.6) return "#3b82f6";     // blue - learning
  if (mastery >= 0.3) return "#f59e0b";     // amber - struggling
  if (mastery > 0)    return "#ef4444";     // red - weak
  return "#9ca3af";                          // gray - untouched
}

// 获取节点大小（按层级）
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

// 获取趋势图标
export function getTrendIcon(trend: string): string {
  switch (trend) {
    case "ascending":  return "↑";
    case "descending": return "↓";
    case "plateau":    return "→";
    case "volatile":   return "↕";
    default:           return "—";
  }
}
