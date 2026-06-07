// 知识图谱 API 工具
import type { GraphData } from "@/lib/types/graph-types";
import type { KGTreeResponse } from "@/lib/types/graph-types";
import { kgTreeToGraphData } from "@/lib/types/graph-types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * 获取统一知识图谱数据
 * 调用 /api/knowledge/graph/{partition_id} 并转换为前端 GraphData
 */
export async function fetchGraphData(partitionId = "default"): Promise<GraphData> {
  const res = await fetch(`${API_BASE}/api/knowledge/graph/${partitionId}`);
  if (!res.ok) throw new Error(`加载知识图谱失败: ${res.statusText}`);
  const json: KGTreeResponse = await res.json();
  return kgTreeToGraphData(json);
}

/**
 * 获取分区列表
 */
export async function fetchPartitions(): Promise<
  { id: string; name: string; subject?: string; emoji?: string; has_graph: boolean; node_count: number; edge_count: number }[]
> {
  const res = await fetch(`${API_BASE}/api/knowledge/graph/partitions`);
  if (!res.ok) return [];
  const json = await res.json();
  return json.partitions || [];
}
