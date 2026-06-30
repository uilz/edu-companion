/**
 * tree-helpers — 树操作辅助函数
 * ensureConversationAtLevel, createConversationWithSmartName,
 * refreshDirectoryData
 *
 * apiFetch / cognitiveApiFetch 委托给 @/lib/api/api 统一路径 (带 401 刷新)。
 */

// ══════════════════════════════════════════════════════════════
//  API helpers
// ══════════════════════════════════════════════════════════════
import { tree as _tree, cognitiveApi as _cognitiveApi } from "@/lib/api/api";
import { useTreeStore } from "@/store/conversation/tree-store";
import type { ConversationState } from "@/store/conversation/conversation-store";

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  return _tree<T>(path, options);
}

export async function cognitiveApiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  return _cognitiveApi<T>(path, options);
}

export function fireClassify(convId: string, text: string) {
  cognitiveApiFetch("/classify", {
    method: "POST",
    body: JSON.stringify({ conv_id: convId, message: text }),
  }).catch(() => {}); // fire-and-forget
}

// ══════════════════════════════════════════════════════════════
//  统一目录数据刷新（去重）
// ══════════════════════════════════════════════════════════════

const ROOT_KEY = "__graph_root__";

/**
 * refreshDirectoryData — 一次 API 调用同时更新 treeStore 和 conversationStore。
 * 合并了 loadRootNodes() + loadDirList() 的重复 /tree/directory 请求。
 *
 * @param setDirList - 传入 conversationStore 的 set 函数以更新 dirList；不传则只刷 treeStore
 */
export async function refreshDirectoryData(
  setDirList?: (partial: Partial<ConversationState>) => void,
): Promise<void> {
  try {
    const dirData = await apiFetch<{ directory_nodes?: any[] }>("/tree/directory");
    const allNodes = dirData?.directory_nodes || [];

    const sysRoot = allNodes.find((n: any) => n.node_type === "dir" && !n.parent_id);

    // ── 1. 更新 treeStore（原 loadRootNodes 逻辑） ──
    let topLevelNodes: any[];
    if (sysRoot) {
      topLevelNodes = allNodes
        .filter((n: any) => n.node_type === "dir" && n.parent_id === sysRoot.id)
        .map((n: any, i: number) => ({
          id: n.id, label: n.name, level: "dir" as const,
          parent: null, emoji: n.emoji || "", nodeIndex: i,
          path_id: n.name, is_visible: true, node_type: "dir",
          kind: n.kind, suggested_count: 0, created_at: 0,
          brief: "", path: n.path || [],
        }));
    } else {
      topLevelNodes = allNodes
        .filter((n: any) => !n.parent_id)
        .map((n: any, i: number) => ({
          id: n.id, label: n.name,
          level: (n.node_type === "dir" ? "dir" : "conv") as "dir" | "conv",
          parent: null, emoji: n.emoji || "", nodeIndex: i,
          path_id: n.name, is_visible: true, node_type: n.node_type,
          kind: n.kind, suggested_count: 0, created_at: 0,
          brief: "", path: n.path || [],
        }));
    }

    useTreeStore.setState(s => {
      const next = new Map(s.childMap);
      next.set(ROOT_KEY, topLevelNodes);
      const validExpanded = new Set<string>();
      s.expandedSet.forEach((eid) => {
        if (eid === ROOT_KEY || next.has(eid)) validExpanded.add(eid);
      });
      return {
        childMap: next,
        rootLoaded: true,
        rootId: sysRoot?.id || "",
        expandedSet: validExpanded,
      };
    });

    // ── 2. 更新 conversationStore dirList（原 loadDirListImpl 逻辑） ──
    if (setDirList) {
      let topLevel: { id: string; name: string; emoji: string; kind: string }[];
      if (sysRoot) {
        topLevel = allNodes
          .filter((n: any) => n.node_type === "dir" && n.parent_id === sysRoot.id)
          .map((n: any) => ({ id: n.id, name: n.name, emoji: n.emoji || "", kind: n.kind }));
      } else {
        topLevel = allNodes
          .filter((n: any) => n.node_type === "dir" && !n.parent_id)
          .map((n: any) => ({ id: n.id, name: n.name, emoji: n.emoji || "", kind: n.kind }));
      }
      setDirList({ dirList: topLevel, loadingDirList: false });
    }
  } catch {
    if (setDirList) setDirList({ dirList: [], loadingDirList: false });
  }
}

// ══════════════════════════════════════════════════════════════
//  智能命名 + 创建会话
// ══════════════════════════════════════════════════════════════

/**
 * 确保在指定目录节点下创建对话。
 *
 * @param kind 子节点 kind，默认 "general"，父为 temp 时应传 "temp"
 */
export async function ensureConversationAtLevel(
  level: string,
  parentId: string,
  pId: string,
  kind: string = "general",
): Promise<{ dirId: string; convId: string } | null> {
  try {
    const actualParentId = parentId;

    // ── 一次 GET 获取所有子节点，同时用于智能命名和空会话复用 ──
    const listResp = await apiFetch<{ directory_nodes: any[] }>(
      `/tree/directory?parent_id=${actualParentId}`
    );
    const children = listResp.directory_nodes || [];
    const convs = children.filter((n: any) => n.node_type === "conv");

    // 检查是否已有空的「新会话」
    const emptyConv = convs.find(
      (c: any) => (!c.message_count || c.message_count === 0) && c.name.startsWith("新会话"),
    );
    if (emptyConv) {
      return { dirId: pId, convId: emptyConv.id };
    }

    // 生成下一个可用名称
    const name = _nextConvName(convs);

    // ── 创建新会话 ──
    const createData = await apiFetch<{ directory_node: { id: string }; conv_id?: string }>(
      "/tree/directory",
      {
        method: "POST",
        body: JSON.stringify({ node_type: "conv", kind, parent_id: actualParentId, name }),
      },
    );
    const convId = createData.directory_node.id;
    return { dirId: pId, convId: convId };
  } catch (e) {
    console.error("ensureConversationAtLevel failed: parentId=%s kind=%s", parentId, kind, e);
    return null;
  }
}

/** 生成下一个可用的"新会话N"名称 */
function _nextConvName(convs: any[]): string {
  let maxN = 0;
  const baseName = "新会话";
  for (const c of convs) {
    if (c.name === baseName) { maxN = Math.max(maxN, 1); continue; }
    const m = c.name.match(/^新会话(\d+)$/);
    if (m) maxN = Math.max(maxN, parseInt(m[1], 10));
  }
  if (maxN === 0) return baseName;
  return `${baseName}${maxN + 1}`;
}
