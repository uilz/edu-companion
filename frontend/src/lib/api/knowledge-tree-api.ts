/**
 * Knowledge Tree API v5 — 四实体解耦架构
 *
 * 统一前缀: /api/knowledge-tree
 */

import { api } from "./api";

// ═══════════════════════════════════════════
// Type Definitions
// ═══════════════════════════════════════════

export interface KnowledgeNode {
  id: string;
  user_id: string;
  parent_id: string | null;
  label: string;
  level: string; // domain | topic | concept | atom
  brief: string;
  tags: string[];
  created_by: string;
  children_order: string[];
  prerequisites: Array<{ id: string; type: string }>;
  unlocks: Array<{ id: string; gate?: { ref: string; value: number } }>;
  associates: Array<{ id: string; strength: number; type: string; label: string }>;
  emoji: string;
  color: string;
  sort_order: number;
  is_visible: boolean;
  node_type: string;
  mastery: number;
  mastery_level: string;
  path_id: string;
  created_at: number;
  updated_at: number;
  is_active: boolean;
}

export interface Conversation {
  id: string;
  user_id: string;
  message_ids: string[];
  knowledge_node_ids: string[];
  summary_short: string;
  summary_dirty: boolean;
  parent_conv_id: string;
  sub_branch_ids: string[];
  depth: number;
  created_at: number;
  updated_at: number;
  metadata: Record<string, unknown>;
}

export interface Message {
  id: string;
  conv_id: string;
  role: string;
  content: string;
  content_blocks: Array<Record<string, unknown>>;
  text_summary: string;
  knowledge_node_ids: string[];
  parent_id: string | null;
  children_ids: string[];
  has_sub_branches: boolean;
  sub_branch_ids: string[];
  sub_branch_summaries: Array<Record<string, unknown>>;
  version: number;
  is_deleted: boolean;
  timestamp: number;
  token_count: number;
  agent_label: string;
}

export interface NavigationNode {
  id: string;
  user_id: string;
  parent_id: string | null;
  node_type: "dir" | "conv";
  kind: string;
  name: string;
  user_name: string | null;
  ai_name: string;
  children_order: string[];
  conv_id: string | null;
  knowledge_area_id: string | null;
  path: string[];
  created_at: number;
  updated_at: number;
  display_name: string;
}

export interface NavigationTree {
  id: string;
  name: string;
  node_type: string;
  kind: string;
  parent_id: string | null;
  conv_id: string | null;
  knowledge_area_id: string | null;
  children?: NavigationTree[];
}

export interface ListResponse<T> {
  nodes?: T[];
  conversations?: T[];
  children?: T[];
  messages?: T[];
  total: number;
}

// ═══════════════════════════════════════════
// KnowledgeNode API
// ═══════════════════════════════════════════

export const knowledgeNodesApi = {
  list: (params?: { parent_id?: string; level?: string; search?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.parent_id) searchParams.set("parent_id", params.parent_id);
    if (params?.level) searchParams.set("level", params.level);
    if (params?.search) searchParams.set("search", params.search);
    const qs = searchParams.toString();
    return api<ListResponse<KnowledgeNode>>(
      `/api/knowledge-tree/nodes${qs ? `?${qs}` : ""}`
    );
  },

  get: (nodeId: string) =>
    api<{ node: KnowledgeNode }>(`/api/knowledge-tree/nodes/${nodeId}`),

  getSubtree: (nodeId: string) =>
    api<{ nodes: Record<string, KnowledgeNode> }>(
      `/api/knowledge-tree/nodes/${nodeId}/subtree`
    ),

  getConversations: (nodeId: string) =>
    api<{ conversations: Conversation[]; total: number }>(
      `/api/knowledge-tree/nodes/${nodeId}/conversations`
    ),

  create: (data: {
    label: string;
    level?: string;
    parent_id?: string;
    brief?: string;
    tags?: string[];
    emoji?: string;
    color?: string;
  }) =>
    api<{ node: KnowledgeNode }>("/api/knowledge-tree/nodes", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (nodeId: string, data: Record<string, unknown>) =>
    api<{ node: KnowledgeNode }>(`/api/knowledge-tree/nodes/${nodeId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: (nodeId: string) =>
    api<{ ok: boolean }>(`/api/knowledge-tree/nodes/${nodeId}`, {
      method: "DELETE",
    }),

  addPrerequisite: (nodeId: string, prereqId: string, prereqType = "strict") =>
    api<{ ok: boolean }>(
      `/api/knowledge-tree/nodes/${nodeId}/prerequisites`,
      {
        method: "POST",
        body: JSON.stringify({ prereq_id: prereqId, prereq_type: prereqType }),
      }
    ),

  removePrerequisite: (nodeId: string, prereqId: string) =>
    api<{ ok: boolean }>(
      `/api/knowledge-tree/nodes/${nodeId}/prerequisites/${prereqId}`,
      { method: "DELETE" }
    ),

  addAssociate: (
    nodeId: string,
    targetId: string,
    strength = 0.5,
    relType = "analogy"
  ) =>
    api<{ ok: boolean }>(
      `/api/knowledge-tree/nodes/${nodeId}/associates`,
      {
        method: "POST",
        body: JSON.stringify({
          target_id: targetId,
          strength,
          rel_type: relType,
        }),
      }
    ),

  reorderChildren: (nodeId: string, childrenOrder: string[]) =>
    api<{ ok: boolean }>(
      `/api/knowledge-tree/nodes/${nodeId}/reorder`,
      {
        method: "PUT",
        body: JSON.stringify({ children_order: childrenOrder }),
      }
    ),
};

// ═══════════════════════════════════════════
// Conversation API
// ═══════════════════════════════════════════

export const conversationsApi = {
  list: (knowledgeNodeId?: string) => {
    const params = knowledgeNodeId
      ? `?knowledge_node_id=${knowledgeNodeId}`
      : "";
    return api<ListResponse<Conversation>>(
      `/api/knowledge-tree/conversations${params}`
    );
  },

  get: (convId: string) =>
    api<{ conversation: Conversation }>(
      `/api/knowledge-tree/conversations/${convId}`
    ),

  create: (data?: {
    knowledge_node_ids?: string[];
    summary_short?: string;
  }) =>
    api<{ conversation: Conversation }>(
      "/api/knowledge-tree/conversations",
      {
        method: "POST",
        body: JSON.stringify(data || {}),
      }
    ),

  update: (convId: string, data: Record<string, unknown>) =>
    api<{ conversation: Conversation }>(
      `/api/knowledge-tree/conversations/${convId}`,
      { method: "PUT", body: JSON.stringify(data) }
    ),

  delete: (convId: string) =>
    api<{ ok: boolean }>(
      `/api/knowledge-tree/conversations/${convId}`,
      { method: "DELETE" }
    ),

  addKnowledgeNode: (convId: string, nodeId: string) =>
    api<{ ok: boolean }>(
      `/api/knowledge-tree/conversations/${convId}/knowledge-nodes/${nodeId}`,
      { method: "POST" }
    ),

  removeKnowledgeNode: (convId: string, nodeId: string) =>
    api<{ ok: boolean }>(
      `/api/knowledge-tree/conversations/${convId}/knowledge-nodes/${nodeId}`,
      { method: "DELETE" }
    ),
};

// ═══════════════════════════════════════════
// Navigation API
// ═══════════════════════════════════════════

export const navigationApi = {
  getTree: (rootId?: string) => {
    const params = rootId ? `?root_id=${rootId}` : "";
    return api<{ tree: NavigationTree[] }>(
      `/api/knowledge-tree/navigation${params}`
    );
  },

  getNode: (nodeId: string) =>
    api<{ node: NavigationNode }>(
      `/api/knowledge-tree/navigation/${nodeId}`
    ),

  getChildren: (nodeId: string) =>
    api<ListResponse<NavigationNode>>(
      `/api/knowledge-tree/navigation/${nodeId}/children`
    ),

  create: (data: {
    parent_id: string;
    name: string;
    node_type?: "dir" | "conv";
    kind?: string;
    conv_id?: string;
    knowledge_area_id?: string;
  }) =>
    api<{ node: NavigationNode }>("/api/knowledge-tree/navigation", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (nodeId: string, data: Record<string, unknown>) =>
    api<{ node: NavigationNode }>(
      `/api/knowledge-tree/navigation/${nodeId}`,
      { method: "PUT", body: JSON.stringify(data) }
    ),

  delete: (nodeId: string) =>
    api<{ ok: boolean }>(
      `/api/knowledge-tree/navigation/${nodeId}`,
      { method: "DELETE" }
    ),

  migrate: (nodeId: string, targetDirId: string) =>
    api<{ node: NavigationNode }>(
      `/api/knowledge-tree/navigation/${nodeId}/migrate`,
      {
        method: "POST",
        body: JSON.stringify({ target_dir_id: targetDirId }),
      }
    ),
};

// ═══════════════════════════════════════════
// Message API
// ═══════════════════════════════════════════

export const messagesApi = {
  list: (convId: string, options?: { limit?: number; offset?: number; tree?: boolean }) => {
    const params = new URLSearchParams();
    if (options?.limit) params.set("limit", String(options.limit));
    if (options?.offset) params.set("offset", String(options.offset));
    if (options?.tree) params.set("tree", "true");
    const qs = params.toString();
    return api<ListResponse<Message>>(
      `/api/knowledge-tree/conversations/${convId}/messages${qs ? `?${qs}` : ""}`
    );
  },

  get: (msgId: string) =>
    api<{ message: Message }>(`/api/knowledge-tree/messages/${msgId}`),

  create: (data: {
    conv_id: string;
    role?: string;
    content?: string;
    content_blocks?: Array<Record<string, unknown>>;
    text_summary?: string;
    parent_id?: string;
    knowledge_node_ids?: string[];
  }) =>
    api<{ message: Message }>("/api/knowledge-tree/messages", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (msgId: string, data: Record<string, unknown>) =>
    api<{ message: Message }>(`/api/knowledge-tree/messages/${msgId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: (msgId: string) =>
    api<{ ok: boolean }>(`/api/knowledge-tree/messages/${msgId}`, {
      method: "DELETE",
    }),

  addKnowledgeNode: (msgId: string, nodeId: string) =>
    api<{ ok: boolean }>(
      `/api/knowledge-tree/messages/${msgId}/knowledge-nodes/${nodeId}`,
      { method: "POST" }
    ),
};