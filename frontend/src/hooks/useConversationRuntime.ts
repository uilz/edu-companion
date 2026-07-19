/**
 * Demo6.0 Conversation Runtime Hook
 *
 * Integrates with backend ConversationRuntime (/api/conversations)
 * for AI dialogue + orchestration within a session.
 */

"use client";

import { useState, useCallback } from "react";
import {
  startConversation,
  createTurn,
  recordOrchestration,
  pauseConversation,
  closeConversation,
  getTurns,
  type ConversationData,
  type TurnData,
} from "@/lib/api/conversation-runtime-api";

interface UseConversationRuntimeOptions {
  sessionId: string;
  onStateChange?: (state: string) => void;
}

export function useConversationRuntime({
  sessionId,
  onStateChange,
}: UseConversationRuntimeOptions) {
  const [conversation, setConversation] = useState<ConversationData | null>(null);
  const [turns, setTurns] = useState<TurnData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(
    async (title?: string) => {
      if (!sessionId) return;
      setLoading(true);
      setError(null);
      try {
        const resp = await startConversation(sessionId, title);
        setConversation({
          id: resp.conversationId,
          sessionId,
          state: resp.state,
          title: resp.title,
          createdAt: new Date().toISOString(),
        });
        onStateChange?.(resp.state);
      } catch (e: any) {
        setError(e?.message || "Failed to start conversation");
      } finally {
        setLoading(false);
      }
    },
    [sessionId, onStateChange],
  );

  const sendTurn = useCallback(
    async (
      userMessage: string,
      aiResponse: string,
      context?: {
        readingPage?: number;
        readingScroll?: number;
        memoryTier?: string;
        knowledgeConcepts?: string;
      },
    ) => {
      if (!conversation?.id) return null;
      setLoading(true);
      setError(null);
      try {
        const turn = await createTurn(
          conversation.id,
          userMessage,
          aiResponse,
          context?.readingPage,
          context?.readingScroll,
          context?.memoryTier,
          context?.knowledgeConcepts,
        );
        setTurns((prev) => [...prev, turn]);
        return turn;
      } catch (e: any) {
        setError(e?.message || "Failed to create turn");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [conversation],
  );

  const orchestrate = useCallback(
    async (turnId: string, decision: string, artifactType?: string, artifactId?: string) => {
      if (!conversation?.id) return;
      try {
        await recordOrchestration(conversation.id, turnId, decision, artifactType, artifactId);
      } catch (e: any) {
        setError(e?.message || "Failed to record orchestration");
      }
    },
    [conversation],
  );

  const pause = useCallback(async () => {
    if (!conversation?.id) return;
    try {
      const resp = await pauseConversation(conversation.id);
      setConversation((prev) => prev ? { ...prev, state: resp.state } : null);
      onStateChange?.(resp.state);
    } catch (e: any) {
      setError(e?.message || "Failed to pause conversation");
    }
  }, [conversation, onStateChange]);

  const close = useCallback(async () => {
    if (!conversation?.id) return;
    try {
      const resp = await closeConversation(conversation.id);
      setConversation((prev) => prev ? { ...prev, state: resp.state } : null);
      onStateChange?.(resp.state);
    } catch (e: any) {
      setError(e?.message || "Failed to close conversation");
    }
  }, [conversation, onStateChange]);

  const loadTurns = useCallback(async () => {
    if (!conversation?.id) return;
    setLoading(true);
    try {
      const loaded = await getTurns(conversation.id);
      setTurns(loaded);
    } catch (e: any) {
      setError(e?.message || "Failed to load turns");
    } finally {
      setLoading(false);
    }
  }, [conversation]);

  return {
    conversation,
    turns,
    loading,
    error,
    start,
    sendTurn,
    orchestrate,
    pause,
    close,
    loadTurns,
  };
}
