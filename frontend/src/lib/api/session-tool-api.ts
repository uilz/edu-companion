// EXP-04 Session 工具托盘 / 闪卡关联 API
import { authedFetch } from "@/lib/api/api";
import type { FlashCard } from "@/lib/api/flashcard-api";

export interface ToolStatePayload {
  [key: string]: unknown;
}

export interface SessionFlashcardPayload {
  front_text: string;
  back_text?: string;
  type?: number;
  tags?: string[];
  linked_node_ids?: string[];
  back_context?: string;
}

export async function getToolState(sessionId: string): Promise<ToolStatePayload> {
  const res = await authedFetch(`/api/session/${sessionId}/tool-state`);
  if (!res.ok) throw new Error("获取工具状态失败");
  const data = await res.json();
  return data.tool_state || {};
}

export async function updateToolState(
  sessionId: string,
  patch: ToolStatePayload
): Promise<ToolStatePayload> {
  const res = await authedFetch(`/api/session/${sessionId}/tool-state`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool_state: patch }),
  });
  if (!res.ok) throw new Error("更新工具状态失败");
  const data = await res.json();
  return data.tool_state || {};
}

export async function createSessionFlashcard(
  sessionId: string,
  payload: SessionFlashcardPayload
): Promise<{ card: FlashCard; session_id: string }> {
  const res = await authedFetch(`/api/session/${sessionId}/flashcards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("创建闪卡失败");
  return res.json();
}
