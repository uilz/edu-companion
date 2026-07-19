/**
 * Conversation API Client — AppleGo Demo6.0
 *
 * Backend: /api/conversations (conversation_runtime.py)
 */

import { authedFetchJson } from "./api";

export interface ConversationData {
  id: string;
  sessionId: string;
  state: string;
  title: string;
  createdAt: string;
}

export interface TurnData {
  id: string;
  seq: number;
  userMessage: string;
  aiResponse: string;
  orchestration: string;
  createdAt: string;
}

export interface LifecycleResp {
  conversationId: string;
  state: string;
  title: string;
}

export async function startConversation(
  sessionId: string,
  title: string = ""
): Promise<LifecycleResp> {
  const c: any = await authedFetchJson(`/api/conversations/${sessionId}`, {
    method: "POST",
    body: JSON.stringify({ title }),
  });
  return {
    conversationId: c.conversation_id,
    state: c.state,
    title: c.title,
  };
}

export async function createTurn(
  convId: string,
  userMessage: string,
  aiResponse: string,
  readingPage: number = 0,
  readingScroll: number = 0,
  memoryTier: string = "",
  knowledgeConcepts: string = ""
): Promise<TurnData> {
  const t: any = await authedFetchJson(`/api/conversations/${convId}/turns`, {
    method: "POST",
    body: JSON.stringify({
      user_message: userMessage,
      ai_response: aiResponse,
      reading_page: readingPage,
      reading_scroll: readingScroll,
      memory_tier: memoryTier,
      knowledge_concepts: knowledgeConcepts,
    }),
  });
  return {
    id: t.id,
    seq: t.seq,
    userMessage: t.user_message,
    aiResponse: t.ai_response,
    orchestration: t.orchestration,
    createdAt: t.created_at,
  };
}

export async function recordOrchestration(
  convId: string,
  turnId: string,
  decision: string,
  artifactType: string = "",
  artifactId: string = ""
): Promise<void> {
  await authedFetchJson(`/api/conversations/${convId}/orchestration`, {
    method: "POST",
    body: JSON.stringify({
      turn_id: turnId,
      decision,
      artifact_type: artifactType,
      artifact_id: artifactId,
    }),
  });
}

export async function pauseConversation(
  convId: string
): Promise<LifecycleResp> {
  const c: any = await authedFetchJson(
    `/api/conversations/${convId}/pause`,
    { method: "POST" }
  );
  return {
    conversationId: c.conversation_id,
    state: c.state,
    title: c.title,
  };
}

export async function closeConversation(
  convId: string
): Promise<LifecycleResp> {
  const c: any = await authedFetchJson(
    `/api/conversations/${convId}/close`,
    { method: "POST" }
  );
  return {
    conversationId: c.conversation_id,
    state: c.state,
    title: c.title,
  };
}

export async function getTurns(convId: string): Promise<TurnData[]> {
  const rows = await authedFetchJson<any[]>(
    `/api/conversations/${convId}/turns`
  );
  return (
    rows?.map((t: any) => ({
      id: t.id,
      seq: t.seq,
      userMessage: t.user_message,
      aiResponse: t.ai_response,
      orchestration: t.orchestration,
      createdAt: t.created_at,
    })) || []
  );
}
