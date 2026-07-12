/**
 * Knowledge Trees API v1 — 四实体解耦架构
 *
 * 统一前缀: /api/trees
 * 与用户知识结构（knowledge_trees / tree_nodes / tree_edges）交互，
 * 并通过 tree_node_cognitive_links 关联认知数据视图。
 */

import { api } from "./api";

// ═══════════════════════════════════════════════════════════════
// 类型定义
// ═══════════════════════════════════════════════════════════════

export type TreeType = "project" | "domain" | "map";
export type TreeStatus = "active" | "archived" | "deleted";
export type TreeViewMode = "tree" | "graph" | "split";
export type TreeLayout = "layered" | "force" | "radial" | "manual";

export interface KnowledgeTree {
  id: string;
  user_id: string;
  title: string;
  description: string;
  tree_type: TreeType;
  root_node_id: string | null;
  default_view_mode: TreeViewMode;
  default_layout: TreeLayout;
  tags: string[];
  metadata: Record<string, unknown>;
  status: TreeStatus;
  created_at: number;
  updated_at: number;
  version: number;
}

export type TreeNodeType =
  | "topic"
  | "concept"
  | "skill"
  | "material"
  | "question"
  | "card"
  | "note"
  | "milestone";
export type TreeNodeStatus = "active" | "collapsed" | "archived" | "deleted";

export interface TreeNode {
  id: string;
  tree_id: string;
  user_id: string;
  label: string;
  node_type: TreeNodeType;
  parent_id: string | null;
  children_order: string[];
  children_ids: string[];
  order_index: number;
  color: string;
  emoji: string;
  icon_url: string;
  position: { x?: number; y?: number };
  source_refs: SourceRef[];
  tags: string[];
  brief: string;
  metadata: Record<string, unknown>;
  status: TreeNodeStatus;
  created_at: number;
  updated_at: number;
  version: number;
  // 认知视图（仅在 include_cognitive_view=true 时出现）
  linked_cognitive_node_ids?: string[];
  cognitive_view?: CognitiveNodeView | null;
}

export type EdgeType =
  | "parent_child"
  | "prerequisite"
  | "related"
  | "sequence"
  | "reference";

export interface TreeEdge {
  id: string;
  tree_id: string;
  user_id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: EdgeType;
  strength: number;
  is_user_confirmed: boolean;
  is_inferred: boolean;
  metadata: Record<string, unknown>;
  created_at: number;
}

export type LinkRole = "primary" | "reference" | "derived";

export interface CognitiveLink {
  id: string;
  tree_id: string;
  tree_node_id: string;
  cognitive_node_id: string;
  user_id: string;
  link_role: LinkRole;
  created_at: number;
}

export interface CognitiveNodeView {
  cognitive_node_id: string;
  label: string;
  level: string;
  proficiency: number;
  uncertainty: number;
  urgency: number;
  stagnation_days: number;
  next_review_at: number | null;
  next_action_type: string;
  display_color: string;
  display_size: number;
  display_glow: boolean;
}

export interface SourceRef {
  module: string;
  id: string;
  sub_id?: string;
}

export interface ViewportState {
  view_mode?: TreeViewMode;
  layout?: TreeLayout;
  zoom?: number;
  pan_x?: number;
  pan_y?: number;
  filters?: Record<string, unknown>;
  collapsed_node_ids?: string[];
  focused_node_id?: string;
  updated_at?: number;
}

export interface TreeStats {
  total: number;
  mastered: number;
  learning: number;
  untouched: number;
  avgMastery: number;
}

// ═══════════════════════════════════════════════════════════════
// 请求体类型
// ═══════════════════════════════════════════════════════════════

export interface CreateTreeBody {
  title: string;
  tree_type?: TreeType;
  description?: string;
}

export interface UpdateTreeBody {
  title?: string;
  description?: string;
  tree_type?: TreeType;
  root_node_id?: string | null;
  default_view_mode?: TreeViewMode;
  default_layout?: TreeLayout;
  tags?: string[];
  meta?: Record<string, unknown>;
}

export interface CreateNodeBody {
  label: string;
  parent_id?: string | null;
  node_type?: TreeNodeType;
  order_index?: number;
  color?: string;
  emoji?: string;
  position?: { x?: number; y?: number };
  brief?: string;
  tags?: string[];
  meta?: Record<string, unknown>;
}

export interface UpdateNodeBody {
  label?: string;
  node_type?: TreeNodeType;
  color?: string;
  emoji?: string;
  position?: { x?: number; y?: number };
  brief?: string;
  tags?: string[];
  meta?: Record<string, unknown>;
  status?: TreeNodeStatus;
}

export interface MoveNodeBody {
  new_parent_id?: string | null;
  new_position?: { x?: number; y?: number };
  new_order_index?: number;
}

export interface ReorderChildrenBody {
  children_order: string[];
}

export interface CreateEdgeBody {
  source_node_id: string;
  target_node_id: string;
  edge_type?: EdgeType;
  strength?: number;
  is_user_confirmed?: boolean;
  is_inferred?: boolean;
  meta?: Record<string, unknown>;
}

export interface LinkCognitiveBody {
  cognitive_node_id: string;
  link_role?: LinkRole;
}

export interface ImportContentBody {
  source_module: string;
  source_ref_id: string;
  target_node_id?: string;
  auto_create_node?: boolean;
  label?: string;
}

// ═══════════════════════════════════════════════════════════════
// 通用响应包装
// ═══════════════════════════════════════════════════════════════

interface ListResp<T> {
  trees?: T[];
  nodes?: T[];
  edges?: T[];
  total: number;
}

// ═══════════════════════════════════════════════════════════════
// Knowledge Tree API
// ═══════════════════════════════════════════════════════════════

export const treesApi = {
  create: (body: CreateTreeBody) =>
    api<{ tree: KnowledgeTree }>("/api/trees", { method: "POST", body: JSON.stringify(body) }),

  list: (status?: TreeStatus) => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return api<ListResp<KnowledgeTree>>(`/api/trees${qs}`);
  },

  get: (treeId: string) => api<{ tree: KnowledgeTree }>(`/api/trees/${treeId}`),

  update: (treeId: string, body: UpdateTreeBody) =>
    api<{ tree: KnowledgeTree }>(`/api/trees/${treeId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  delete: (treeId: string) =>
    api<{ ok: boolean }>(`/api/trees/${treeId}`, { method: "DELETE" }),
};

// ═══════════════════════════════════════════════════════════════
// Tree Node API
// ═══════════════════════════════════════════════════════════════

export const treeNodesApi = {
  create: (treeId: string, body: CreateNodeBody) =>
    api<{ node: TreeNode }>(`/api/trees/${treeId}/nodes`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  list: (treeId: string, includeCognitiveView = false) =>
    api<{ nodes: TreeNode[]; total: number }>(
      `/api/trees/${treeId}/nodes?include_cognitive_view=${includeCognitiveView}`
    ),

  get: (treeId: string, nodeId: string, includeCognitiveView = false) =>
    api<{ node: TreeNode }>(
      `/api/trees/${treeId}/nodes/${nodeId}?include_cognitive_view=${includeCognitiveView}`
    ),

  update: (treeId: string, nodeId: string, body: UpdateNodeBody) =>
    api<{ node: TreeNode }>(`/api/trees/${treeId}/nodes/${nodeId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  move: (treeId: string, nodeId: string, body: MoveNodeBody) =>
    api<{ node: TreeNode }>(`/api/trees/${treeId}/nodes/${nodeId}/move`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  reorderChildren: (treeId: string, nodeId: string, childrenOrder: string[]) =>
    api<{ ok: boolean }>(`/api/trees/${treeId}/nodes/${nodeId}/reorder`, {
      method: "POST",
      body: JSON.stringify({ children_order: childrenOrder }),
    }),

  delete: (treeId: string, nodeId: string) =>
    api<{ ok: boolean }>(`/api/trees/${treeId}/nodes/${nodeId}`, { method: "DELETE" }),

  addSourceRef: (treeId: string, nodeId: string, ref: SourceRef) =>
    api<{ node: TreeNode }>(`/api/trees/${treeId}/nodes/${nodeId}/source-refs`, {
      method: "POST",
      body: JSON.stringify(ref),
    }),
};

// ═══════════════════════════════════════════════════════════════
// Cognitive Link API
// ═══════════════════════════════════════════════════════════════

export const cognitiveLinksApi = {
  create: (treeId: string, nodeId: string, body: LinkCognitiveBody) =>
    api<{ link: CognitiveLink }>(`/api/trees/${treeId}/nodes/${nodeId}/link-cognitive`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  delete: (treeId: string, nodeId: string, cognitiveNodeId: string) =>
    api<{ ok: boolean }>(`/api/trees/${treeId}/nodes/${nodeId}/link-cognitive/${cognitiveNodeId}`, {
      method: "DELETE",
    }),
};

// ═══════════════════════════════════════════════════════════════
// Tree Edge API
// ═══════════════════════════════════════════════════════════════

export const treeEdgesApi = {
  create: (treeId: string, body: CreateEdgeBody) =>
    api<{ edge: TreeEdge }>(`/api/trees/${treeId}/edges`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  list: (treeId: string) =>
    api<{ edges: TreeEdge[]; total: number }>(`/api/trees/${treeId}/edges`),

  delete: (treeId: string, edgeId: string) =>
    api<{ ok: boolean }>(`/api/trees/${treeId}/edges/${edgeId}`, { method: "DELETE" }),
};

// ═══════════════════════════════════════════════════════════════
// Content Import API
// ═══════════════════════════════════════════════════════════════

export const treeImportsApi = {
  import: (treeId: string, body: ImportContentBody) =>
    api<{ ok: boolean; target_node_id?: string }>(`/api/trees/${treeId}/import`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

// ═══════════════════════════════════════════════════════════════
// Viewport API
// ═══════════════════════════════════════════════════════════════

export const treeViewportApi = {
  get: (treeId: string) => api<{ viewport: ViewportState }>(`/api/trees/${treeId}/viewport`),

  save: (treeId: string, body: ViewportState) =>
    api<{ viewport: ViewportState }>(`/api/trees/${treeId}/viewport`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};

// ═══════════════════════════════════════════════════════════════
// Node Materials & Cognitive Projection
// ═══════════════════════════════════════════════════════════════

export interface FlashcardMaterial {
  id: string;
  front_text: string;
  back_text?: string;
  status: string;
  source?: string;
  linked_node_ids?: string[];
  created_at?: number | string;
  updated_at?: number | string;
}

export interface ReadingAnnotationMaterial {
  id: string;
  material_id: string;
  color: string;
  intent: string;
  text?: string;
  note?: string;
  linked_node_id?: string;
  created_at?: number | string;
  updated_at?: number | string;
}

export interface PracticeSessionMaterial {
  session_id: string;
  bank_id: string;
  bank_name?: string;
  session_type: string;
  mode: string;
  status: string;
  question_count: number;
  cognitive_node_ids?: string[];
  created_at?: string;
}

export interface PracticeErrorMaterial {
  question_id: string;
  bank_id: string;
  stem: string;
  question_type: string;
  difficulty: number;
  cognitive_node_ids?: string[];
  wrong_count: number;
  wrong_rate: number;
  mastered: boolean;
  last_wrong?: string;
}

export interface PlanningMaterial {
  id: string;
  title: string;
  description?: string;
  status: string;
  priority?: number;
  estimated_minutes?: number;
  source_module?: string;
  linked_node_ids?: string[];
  scheduled_for?: string;
  plan_date?: string;
  created_at?: string;
}

export interface NodeMaterialsResponse {
  materials: {
    cognitive_nodes: CognitiveNodeView[];
    source_refs: SourceRef[];
    flashcards: FlashcardMaterial[];
    reading: {
      annotations: ReadingAnnotationMaterial[];
      notes: FlashcardMaterial[];
    };
    practice: {
      sessions: PracticeSessionMaterial[];
      errors: PracticeErrorMaterial[];
    };
    planning: PlanningMaterial[];
  };
}

export interface CognitiveSearchResult {
  cognitive_node_id: string;
  label: string;
  level: string;
}

export const treeMaterialsApi = {
  get: (treeId: string, nodeId: string) =>
    api<NodeMaterialsResponse>(`/api/trees/${treeId}/nodes/${nodeId}/materials`),
};

export const cognitiveSearchApi = {
  search: (q: string, limit = 20) =>
    api<{ nodes: CognitiveSearchResult[]; total: number }>(
      `/api/trees/cognitive-nodes/search?q=${encodeURIComponent(q)}&limit=${limit}`
    ),

  projection: (cognitiveNodeId: string) =>
    api<{ cognitive_view: CognitiveNodeView }>(`/api/trees/cognitive-nodes/${cognitiveNodeId}/projection`),
};

// ═══════════════════════════════════════════════════════════════
// Unified service export
// ═══════════════════════════════════════════════════════════════

export const knowledgeTreesApi = {
  trees: treesApi,
  nodes: treeNodesApi,
  edges: treeEdgesApi,
  links: cognitiveLinksApi,
  imports: treeImportsApi,
  viewport: treeViewportApi,
  materials: treeMaterialsApi,
  cognitive: cognitiveSearchApi,
};
