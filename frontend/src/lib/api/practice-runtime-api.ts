/**
 * Practice Runtime API Client — AppleGo Demo6.0
 *
 * Backend: /api/practices (practice_runtime.py)
 * This is the Demo6.0 practice runtime — separate from the existing V7 practice-api.ts
 */

import { authedFetchJson } from "./api";

export interface DemoPracticeData {
  id: string;
  workspaceId: string;
  state: string;
  title: string;
  totalQuestions: number;
  correctCount: number;
  createdAt: string;
}

export interface DemoQuestionData {
  id: string;
  seq: number;
  text: string;
  conceptIds: string;
  contextSource: string;
  createdAt: string;
}

export interface DemoAttemptData {
  id: string;
  questionId: string;
  isCorrect: boolean;
  reviewed: boolean;
  reviewComment: string;
  createdAt: string;
}

export interface CreateDemoPracticeInput {
  workspaceId: string;
  title: string;
  questions: {
    text: string;
    concept_ids: string;
    context_source: string;
    correct_answer: string;
  }[];
}

export async function createPractice(
  input: CreateDemoPracticeInput
): Promise<DemoPracticeData> {
  const p: any = await authedFetchJson("/api/practices", {
    method: "POST",
    body: JSON.stringify({
      workspace_id: input.workspaceId,
      title: input.title,
      questions: input.questions,
    }),
  });
  return {
    id: p.id,
    workspaceId: p.workspace_id,
    state: p.state,
    title: p.title,
    totalQuestions: p.total_questions,
    correctCount: p.correct_count,
    createdAt: p.created_at,
  };
}

export async function startPractice(
  practiceId: string
): Promise<DemoPracticeData> {
  const p: any = await authedFetchJson(`/api/practices/${practiceId}/start`, {
    method: "POST",
  });
  return {
    id: p.id,
    workspaceId: p.workspace_id,
    state: p.state,
    title: p.title,
    totalQuestions: p.total_questions,
    correctCount: p.correct_count,
    createdAt: p.created_at,
  };
}

export async function getQuestions(
  practiceId: string
): Promise<DemoQuestionData[]> {
  const rows = await authedFetchJson<any[]>(
    `/api/practices/${practiceId}/questions`
  );
  return (
    rows?.map((q: any) => ({
      id: q.id,
      seq: q.seq,
      text: q.text,
      conceptIds: q.concept_ids,
      contextSource: q.context_source,
      createdAt: q.created_at,
    })) || []
  );
}

export async function submitAttempt(
  practiceId: string,
  questionId: string,
  answer: string,
  isCorrect: boolean,
  confidence: number = 0,
  responseTimeS: number = 0
): Promise<DemoAttemptData> {
  const a: any = await authedFetchJson(
    `/api/practices/${practiceId}/attempts`,
    {
      method: "POST",
      body: JSON.stringify({
        question_id: questionId,
        answer,
        is_correct: isCorrect,
        confidence,
        response_time_s: responseTimeS,
      }),
    }
  );
  return {
    id: a.id,
    questionId: a.question_id,
    isCorrect: a.is_correct,
    reviewed: a.reviewed,
    reviewComment: a.review_comment,
    createdAt: a.created_at,
  };
}

export async function reviewAttempt(
  practiceId: string,
  attemptId: string,
  comment: string
): Promise<void> {
  await authedFetchJson(`/api/practices/${practiceId}/review`, {
    method: "POST",
    body: JSON.stringify({ attempt_id: attemptId, comment }),
  });
}

export async function completePractice(
  practiceId: string
): Promise<DemoPracticeData> {
  const p: any = await authedFetchJson(
    `/api/practices/${practiceId}/complete`,
    { method: "POST" }
  );
  return {
    id: p.id,
    workspaceId: p.workspace_id,
    state: p.state,
    title: p.title,
    totalQuestions: p.total_questions,
    correctCount: p.correct_count,
    createdAt: p.created_at,
  };
}
