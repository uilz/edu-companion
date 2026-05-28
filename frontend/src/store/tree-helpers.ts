// ══════════════════════════════════════════════════════════════
//  API helpers + tree navigation helpers
// ══════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════
//  API helpers (duplicated from api.ts — cannot import "use client" file)
// ══════════════════════════════════════════════════════════════

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api/conversations${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
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
  const res = await fetch(`/api/v2${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
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

// ══════════════════════════════════════════════════════════════
//  Helper: ensure conversation exists at a given tree level
// ══════════════════════════════════════════════════════════════

export async function ensureConversationAtLevel(
  level: string,
  parentId: string,
  pId: string,
): Promise<{ partitionId: string; conversationId: string } | null> {
  try {
    if (level === "partition") {
      // Find or create domain under partition
      const dData = await apiFetch<{ domains: { id: string }[] }>(
        `/tree/domain?parent_id=${parentId}`,
      );
      const domainId =
        dData.domains?.[0]?.id ||
        (
          await apiFetch<{ domain: { id: string } }>("/tree/domain", {
            method: "POST",
            body: JSON.stringify({ parent_id: parentId, name: "新领域", emoji: "📚" }),
          })
        ).domain.id;

      // Find or create topic under domain
      const tData = await apiFetch<{ topics: { id: string }[] }>(
        `/tree/topic?parent_id=${domainId}`,
      );
      const topicId =
        tData.topics?.[0]?.id ||
        (
          await apiFetch<{ topic: { id: string } }>("/tree/topic", {
            method: "POST",
            body: JSON.stringify({ parent_id: domainId, name: "新专题", emoji: "📝" }),
          })
        ).topic.id;

      // Find or create conversation under topic
      const cData = await apiFetch<{
        conversations: { id: string; message_count?: number }[];
      }>(`/tree/conversation?parent_id=${topicId}`);
      const empty = (cData.conversations || []).find(
        (c) => !c.message_count || c.message_count === 0,
      );
      const convId =
        empty?.id ||
        (
          await apiFetch<{ conversation: { id: string } }>("/tree/conversation", {
            method: "POST",
            body: JSON.stringify({ parent_id: topicId, name: "" }),
          })
        ).conversation.id;

      return { partitionId: pId, conversationId: convId };
    }

    if (level === "domain") {
      // Find or create topic under domain
      const tData = await apiFetch<{ topics: { id: string }[] }>(
        `/tree/topic?parent_id=${parentId}`,
      );
      const topicId =
        tData.topics?.[0]?.id ||
        (
          await apiFetch<{ topic: { id: string } }>("/tree/topic", {
            method: "POST",
            body: JSON.stringify({ parent_id: parentId, name: "新专题", emoji: "📝" }),
          })
        ).topic.id;

      // Find or create conversation under topic
      const cData = await apiFetch<{
        conversations: { id: string; message_count?: number }[];
      }>(`/tree/conversation?parent_id=${topicId}`);
      const empty = (cData.conversations || []).find(
        (c) => !c.message_count || c.message_count === 0,
      );
      const convId =
        empty?.id ||
        (
          await apiFetch<{ conversation: { id: string } }>("/tree/conversation", {
            method: "POST",
            body: JSON.stringify({ parent_id: topicId, name: "" }),
          })
        ).conversation.id;

      return { partitionId: pId, conversationId: convId };
    }

    if (level === "topic") {
      // Find or create conversation under topic
      const cData = await apiFetch<{
        conversations: { id: string; message_count?: number }[];
      }>(`/tree/conversation?parent_id=${parentId}`);
      const empty = (cData.conversations || []).find(
        (c) => !c.message_count || c.message_count === 0,
      );
      const convId =
        empty?.id ||
        (
          await apiFetch<{ conversation: { id: string } }>("/tree/conversation", {
            method: "POST",
            body: JSON.stringify({ parent_id: parentId, name: "" }),
          })
        ).conversation.id;

      return { partitionId: pId, conversationId: convId };
    }

    return null;
  } catch (e) {
    console.warn(`${level} 级别创建对话失败:`, e);
    return null;
  }
}
