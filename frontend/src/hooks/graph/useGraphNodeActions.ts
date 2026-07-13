// ══════════════════════════════════════════════════════════════
//  useGraphNodeActions — 共享图谱节点操作 hook
//
//  封装 KnowledgeTreePage / NodeDetailPanel / TreeChatPanel
//  之间重复的节点 CRUD 和 AI 操作逻辑。
//  使用 knowledge-graph-api.ts (四实体解耦架构)
//
//  用法：
//     const actions = useGraphNodeActions({ onNodeUpdated: loadGraph });
//     await actions.deleteNode(nodeId);
//     await actions.aiExpand(nodeId);
// ══════════════════════════════════════════════════════════════

import { useCallback } from "react";
import { knowledgeNodesApi } from "@/lib/api/knowledge-graph-api";
import { authedFetch } from "@/lib/api/api";

export interface GraphNodeActionsCallbacks {
  onNodeUpdated?: () => void;
  onError?: (msg: string) => void;
  onDeleted?: () => void;
}

export function useGraphNodeActions(
  callbacks?: GraphNodeActionsCallbacks,
) {
  const { onNodeUpdated, onError, onDeleted } = callbacks || {};

  // ── 删除节点 ──
  const deleteNode = useCallback(async (nodeId: string, nodeLabel: string): Promise<boolean> => {
    try {
      const json = await knowledgeNodesApi.delete(nodeId);
      if (!json.ok) throw new Error("删除失败");
      onDeleted?.();
      onNodeUpdated?.();
      return true;
    } catch (e: any) {
      onError?.(e.message || "删除失败");
      return false;
    }
  }, [onNodeUpdated, onError, onDeleted]);

  // ── 编辑节点 ──
  const editNode = useCallback(async (
    nodeId: string,
    data: { label?: string; description?: string; tags?: string[] },
  ): Promise<boolean> => {
    try {
      const payload: Record<string, unknown> = {};
      if (data.label !== undefined) payload.label = data.label;
      if (data.description !== undefined) payload.brief = data.description;
      if (data.tags !== undefined) payload.tags = data.tags;
      const json = await knowledgeNodesApi.update(nodeId, payload);
      if (!json.node) throw new Error("保存失败");
      onNodeUpdated?.();
      return true;
    } catch (e: any) {
      onError?.(e.message || "保存失败");
      return false;
    }
  }, [onNodeUpdated, onError]);

  // ── 创建节点 ──
  const createNode = useCallback(async (data: {
    label: string; parent_id?: string; description?: string;
  }): Promise<boolean> => {
    try {
      const json = await knowledgeNodesApi.create({
        label: data.label,
        parent_id: data.parent_id,
        brief: data.description,
      });
      if (!json.node) throw new Error("创建失败");
      onNodeUpdated?.();
      return true;
    } catch (e: any) {
      onError?.(e.message || "创建失败");
      return false;
    }
  }, [onNodeUpdated, onError]);

  // ── AI 扩展 ──
  const aiExpand = useCallback(async (
    nodeId: string,
    options?: { depth?: number; direction?: "children" | "siblings" },
  ): Promise<boolean> => {
    try {
      const res = await authedFetch(`/api/knowledge-graph/ai/expand/${nodeId}`, {
        method: "POST",
        body: JSON.stringify({ depth: options?.depth ?? 2, direction: options?.direction ?? "children" }),
      });
      if (!res.ok) throw new Error("AI 扩充失败");
      onNodeUpdated?.();
      return true;
    } catch (e: any) {
      onError?.(e.message || "AI 扩充失败");
      return false;
    }
  }, [onNodeUpdated, onError]);

  // ── AI 编辑/优化 ──
  const aiEdit = useCallback(async (nodeId: string): Promise<boolean> => {
    try {
      const res = await authedFetch(`/api/knowledge-graph/ai/edit/${nodeId}`, {
        method: "POST",
        body: JSON.stringify({ instruction: "优化该节点的名称、描述和标签" }),
      });
      if (!res.ok) throw new Error("AI 编辑失败");
      onNodeUpdated?.();
      return true;
    } catch (e: any) {
      onError?.(e.message || "AI 编辑失败");
      return false;
    }
  }, [onNodeUpdated, onError]);

  // ── AI 对话 ──
  const aiChat = useCallback(async (
    nodeId: string,
    message: string,
    convId?: string,
  ): Promise<{ response: string; conversationId?: string } | null> => {
    try {
      const res = await authedFetch(`/api/knowledge-graph/ai/chat/${nodeId}`, {
        method: "POST",
        body: JSON.stringify({
          message,
          conv_id: convId || undefined,
        }),
      });
      const data = await res.json();
      if (data.error === "scope_mismatch") {
        const errMsg = `⚠️ ${data.message}\n\n👉 请点击「${data.bound_node_label}」节点，在它的详情面板中启动探索会话。`;
        onError?.(errMsg);
        return { response: errMsg };
      }
      return { response: data.response || "", conversationId: data.conv_id };
    } catch (e: any) {
      onError?.(e.message || "对话失败");
      return null;
    }
  }, [onError]);

  // ── 生成知识树 ──
  const generateGraph = useCallback(async (): Promise<boolean> => {
    try {
      const res = await authedFetch(`/api/knowledge-graph/ai/generate`, { method: "POST" });
      if (!res.ok) throw new Error(`服务返回 ${res.status}`);
      onNodeUpdated?.();
      return true;
    } catch (e: any) {
      onError?.(e.message || "生成失败");
      return false;
    }
  }, [onNodeUpdated, onError]);

  return { deleteNode, editNode, createNode, aiExpand, aiEdit, aiChat, generateGraph };
}
