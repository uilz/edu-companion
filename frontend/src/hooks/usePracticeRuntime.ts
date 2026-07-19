/**
 * Demo6.0 Practice Runtime Hook
 *
 * Integrates with backend PracticeRuntime (/api/practices)
 * for practice creation + question answering + review.
 */

"use client";

import { useState, useCallback } from "react";
import {
  createPractice,
  startPractice,
  getQuestions,
  submitAttempt,
  reviewAttempt,
  completePractice,
  type DemoPracticeData,
  type DemoQuestionData,
  type DemoAttemptData,
  type CreateDemoPracticeInput,
} from "@/lib/api/practice-runtime-api";

export function usePracticeRuntime() {
  const [practice, setPractice] = useState<DemoPracticeData | null>(null);
  const [questions, setQuestions] = useState<DemoQuestionData[]>([]);
  const [attempts, setAttempts] = useState<Record<string, DemoAttemptData>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = useCallback(async (input: CreateDemoPracticeInput) => {
    setLoading(true);
    setError(null);
    try {
      const p = await createPractice(input);
      setPractice(p);
      return p;
    } catch (e: any) {
      setError(e?.message || "Failed to create practice");
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const start = useCallback(async (practiceId: string) => {
    setLoading(true);
    setError(null);
    try {
      const p = await startPractice(practiceId);
      setPractice(p);
      const qs = await getQuestions(practiceId);
      setQuestions(qs);
      return p;
    } catch (e: any) {
      setError(e?.message || "Failed to start practice");
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const answer = useCallback(
    async (questionId: string, answer: string, isCorrect: boolean, confidence?: number, timeS?: number) => {
      if (!practice?.id) return null;
      setError(null);
      try {
        const a = await submitAttempt(practice.id, questionId, answer, isCorrect, confidence, timeS);
        setAttempts((prev) => ({ ...prev, [questionId]: a }));
        return a;
      } catch (e: any) {
        setError(e?.message || "Failed to submit attempt");
        return null;
      }
    },
    [practice],
  );

  const review = useCallback(
    async (attemptId: string, comment: string) => {
      if (!practice?.id) return;
      setError(null);
      try {
        await reviewAttempt(practice.id, attemptId, comment);
      } catch (e: any) {
        setError(e?.message || "Failed to review attempt");
      }
    },
    [practice],
  );

  const complete = useCallback(async () => {
    if (!practice?.id) return null;
    setError(null);
    try {
      const p = await completePractice(practice.id);
      setPractice(p);
      return p;
    } catch (e: any) {
      setError(e?.message || "Failed to complete practice");
      return null;
    }
  }, [practice]);

  return {
    practice,
    questions,
    attempts,
    loading,
    error,
    create,
    start,
    answer,
    review,
    complete,
  };
}
