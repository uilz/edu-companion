"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { getAttemptFeedback, type AttemptFeedback } from "@/lib/api/practice-api";

interface UseAttemptFeedbackReturn {
  feedback: AttemptFeedback | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<AttemptFeedback | null>;
}

const POLL_INTERVAL_MS = 1200;
const MAX_POLL_COUNT = 10;

/**
 * 按 attempt_id 轮询拉取答题后的信息增益反馈。
 * - 首次立即请求
 * - 若返回 is_final=false，则轮询直至 is_final=true 或达到最大次数
 */
export function useAttemptFeedback(attemptId: string | undefined): UseAttemptFeedbackReturn {
  const [feedback, setFeedback] = useState<AttemptFeedback | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollCountRef = useRef(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const load = useCallback(async (): Promise<AttemptFeedback | null> => {
    if (!attemptId) return null;
    setLoading(true);
    setError(null);
    try {
      const data = await getAttemptFeedback(attemptId);
      setFeedback(data);
      return data;
    } catch (e) {
      setError(String((e as Error).message || e));
      return null;
    } finally {
      setLoading(false);
    }
  }, [attemptId]);

  useEffect(() => {
    if (!attemptId) {
      setFeedback(null);
      setError(null);
      setLoading(false);
      pollCountRef.current = 0;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    pollCountRef.current = 0;
    setFeedback(null);
    setError(null);

    const tick = async () => {
      const data = await load();
      pollCountRef.current += 1;
      if (data && !data.is_final && pollCountRef.current < MAX_POLL_COUNT) {
        timerRef.current = setTimeout(tick, POLL_INTERVAL_MS);
      }
    };

    void tick();

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [attemptId, load]);

  return { feedback, loading, error, reload: load };
}
