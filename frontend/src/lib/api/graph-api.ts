// 知识图谱 API 工具
import type { GraphData } from "@/lib/types/graph-types";
import type { KGTreeResponse } from "@/lib/types/graph-types";
import { kgTreeToGraphData } from "@/lib/types/graph-types";
import { api } from "@/lib/api/api";

/**
 * 获取统一知识图谱数据
 * 调用 /api/knowledge/graph/{partition_id} 并转换为前端 GraphData
 */
export async function fetchGraphData(partitionId = "default"): Promise<GraphData> {
  const json: KGTreeResponse = await api<KGTreeResponse>(
    `/api/knowledge/graph/${partitionId}`,
  );
  return kgTreeToGraphData(json);
}

/**
 * 获取分区列表
 */
export async function fetchPartitions(): Promise<
  { id: string; name: string; subject?: string; emoji?: string; has_graph: boolean; node_count: number; edge_count: number }[]
> {
  try {
    const json = await api<{ partitions?: { id: string; name: string; subject?: string; emoji?: string; has_graph: boolean; node_count: number; edge_count: number }[] }>(
      `/api/knowledge/graph/partitions`,
    );
    return json.partitions || [];
  } catch {
    return [];
  }
}
