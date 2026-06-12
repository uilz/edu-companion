/**
 * tree-helpers — 树操作辅助函数
 * ensureConversationAtLevel, createConversationWithSmartName
 */

// ══════════════════════════════════════════════════════════════
//  API helpers
// ══════════════════════════════════════════════════════════════
export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`/api/conversations${path}`, {
    headers: { ...headers, ...(options?.headers as Record<string, string> | undefined) },
    cache: "no-store",
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function v2Fetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`/api/v2${path}`, {
    headers: { ...headers, ...(options?.headers as Record<string, string> | undefined) },
    cache: "no-store",
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`v2 API error ${res.status}: ${text}`);
  }
  return res.json();
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
    const data = await apiFetch<{
      conversations: { name: string; message_count?: number }[];
    }>(`/tree/conversation?parent_id=${parentId}`);
    const convs = data.conversations || [];

    // 检查是否已有空的新会话
    const emptyConv = convs.find(
      (c) => (!c.message_count || c.message_count === 0) && c.name.startsWith("新会话"),
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
 * 确保在指定层级下创建对话。
 *
 * 层级含义：
 *   partition → 直接在分区下创建会话
 *   domain    → 直接在领域下创建会话
 *   topic     → 在专题下创建会话
 *
 * 不再忽略中间层自动补全——对话可以挂在 partition/domain/topic 任意层级。
 */
export async function ensureConversationAtLevel(
  level: string,
  parentId: string,
  pId: string,
): Promise<{ partitionId: string; conversationId: string } | null> {
  try {
    let actualParentId = parentId;

    // ── 1. 确定实际父节点 ID ──
    if (level === "partition") {
      // 对话直接挂在 partition 下
      actualParentId = parentId; // parentId 就是 partitionId
    } else if (level === "domain") {
      // 对话直接挂在 domain 下
      actualParentId = parentId;
    } else if (level === "topic") {
      // 对话直接挂在 topic 下
      actualParentId = parentId;
    } else {
      return null;
    }

    // ── 2. 智能命名：先检查是否已存在空的「新会话」 ──
    const name = await getNextConversationName(actualParentId);

    // 如果已有空的「新会话」，直接使用它
    if (name === "__use_existing__") {
      const cData = await apiFetch<{
        conversations: { id: string; name: string; message_count?: number }[];
      }>(`/tree/conversation?parent_id=${actualParentId}`);
      const empty = (cData.conversations || []).find(
        (c) => (!c.message_count || c.message_count === 0) && c.name.startsWith("新会话"),
      );
      if (empty) {
        return { partitionId: pId, conversationId: empty.id };
      }
      // 没找到空会话，回退到默认名称
    }

    // ── 3. 创建新会话 ──
    const convName = name === "__use_existing__" ? "新会话" : name;
    const createData = await apiFetch<{ conversation: { id: string } }>(
      "/tree/conversation",
      {
        method: "POST",
        body: JSON.stringify({ parent_id: actualParentId, name: convName }),
      },
    );
    const convId = createData.conversation.id;
    return { partitionId: pId, conversationId: convId };
  } catch (e) {
    console.error("ensureConversationAtLevel failed:", e);
    return null;
  }
}