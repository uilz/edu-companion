/**
 * tree-helpers — 树操作辅助函数
 * ensureConversationAtLevel, createConversationWithSmartName
 *
 * apiFetch / v2Fetch 委托给 @/lib/api/api 统一路径 (带 401 刷新)。
 */

// ══════════════════════════════════════════════════════════════
//  API helpers
// ══════════════════════════════════════════════════════════════
import { tree as _tree, v2 as _v2 } from "@/lib/api/api";

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  return _tree<T>(path, options);
}

export async function v2Fetch<T>(path: string, options?: RequestInit): Promise<T> {
  return _v2<T>(path, options);
}

export function fireClassify(convId: string, text: string) {
  v2Fetch("/classify", {
    method: "POST",
    body: JSON.stringify({ conversation_id: convId, message: text }),
  }).catch(() => {}); // fire-and-forget
}

/** 智能命名：获取下一个可用的会话名称 */
async function getNextConversationName(parentId: string): Promise<string> {
  try {
    const data = await apiFetch<{ directory_nodes: any[] }>(`/tree/directory?parent_id=${parentId}`);
    const convs = (data.directory_nodes || []).filter((n: any) => n.node_type === "conv");

    // 检查是否已有空的新会话
    const emptyConv = convs.find(
      (c: any) => (!c.message_count || c.message_count === 0) && c.name.startsWith("新会话"),
    );
    if (emptyConv) return "__use_existing__";

    // 找出最大的编号
    let maxN = 0;
    const baseName = "新会话";
    for (const c of convs) {
      if (c.name === baseName) { maxN = Math.max(maxN, 1); continue; }
      const m = c.name.match(/^新会话(\d+)$/);
      if (m) maxN = Math.max(maxN, parseInt(m[1], 10));
    }

    if (maxN === 0) return baseName;
    return `${baseName}${maxN + 1}`;
  } catch {
    return "新会话";
  }
}

/**
 * 确保在指定目录节点下创建对话。
 *
 * 新架构统一使用 DirectoryNode（node_type: "dir" | "conv"）。
 * 对话（conv）只作为 dir 节点的子节点创建。
 */
export async function ensureConversationAtLevel(
  level: string,
  parentId: string,
  pId: string,
): Promise<{ partitionId: string; conversationId: string } | null> {
  try {
    // 新架构下所有非 conv 节点都是 dir，对话直接挂在 dir 下
    const actualParentId = parentId;

    // ── 智能命名：先检查是否已存在空的「新会话」 ──
    const name = await getNextConversationName(actualParentId);

    // 如果已有空的「新会话」，直接使用它
    if (name === "__use_existing__") {
      const cData = await apiFetch<{ directory_nodes: any[] }>(`/tree/directory?parent_id=${actualParentId}`);
      const empty = (cData.directory_nodes || []).find(
        (c: any) => c.node_type === "conv" && (!c.message_count || c.message_count === 0) && c.name.startsWith("新会话"),
      );
      if (empty) {
        return { partitionId: pId, conversationId: empty.id };
      }
      // 没找到空会话，回退到默认名称
    }

    // ── 创建新会话 ──
    const convName = name === "__use_existing__" ? "新会话" : name;
    const createData = await apiFetch<{ directory_node: { id: string }; conversation_id?: string }>(
      "/tree/directory",
      {
        method: "POST",
        body: JSON.stringify({ node_type: "conv", kind: "general", parent_id: actualParentId, name: convName }),
      },
    );
    const convId = createData.directory_node.id;
    return { partitionId: pId, conversationId: convId };
  } catch (e) {
    console.error("ensureConversationAtLevel failed:", e);
    return null;
  }
}
