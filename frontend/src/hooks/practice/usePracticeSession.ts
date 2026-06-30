"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api/api";

/** 题目选项 */
export interface QuestionOption { letter: string; text: string; is_correct: boolean; }

/** 题目 */
export interface Question {
  question_id: string; skill_id: string; subject: string; bloom_level: string;
  text: string; options: QuestionOption[] | null; correct_answer: string;
  explanation: string; hints: string[]; difficulty: number;
}

/** 练习会话 */
export interface Session {
  session_id: string; question_ids: string[]; planned_skills: string[];
  mode: string; status: string;
}

/** 提交答案结果 */
export interface SubmitResult {
  is_correct: boolean; correct_answer: string; explanation: string;
  knowledge_update?: { skill_id: string; p_known_before: number; p_known_after: number; mastery_level: string; };
  error_analysis?: { type: string; suggestion: string; };
  emotional_feedback?: string;
}

/** 提示结果 */
export interface HintResult { level: number; text: string; type: string; }

/**
 * usePracticeSession — 练习检测页面的状态管理
 * 管理会话创建、题目加载、答题提交、提示获取
 */
export function usePracticeSession(initialSkill: string | null) {
  const [session, setSession] = useState<Session | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitResult, setSubmitResult] = useState<SubmitResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [hint, setHint] = useState<HintResult | null>(null);
  const [hintLevel, setHintLevel] = useState(0);
  const [startTime, setStartTime] = useState<number>(0);

  const q = questions[currentIndex];
  const isCorrect = submitResult?.is_correct;

  const resetForNewQuestion = () => {
    setSelected(null); setSubmitted(false); setSubmitResult(null);
    setHint(null); setHintLevel(0); setStartTime(Date.now());
  };

  const createSession = useCallback(async (skillIds?: string[]) => {
    setLoading(true);
    try {
      const data = await api<Session & { questions?: Question[] }>(
        `/api/practice/sessions`,
        {
          method: "POST",
          body: JSON.stringify({
            bank_id: "default",
            session_type: "practice",
            mode: "adaptive",
            count: 10,
            cognitive_node_ids: skillIds || [],
          }),
        },
      );
      setSession(data);
      setQuestions(data.questions || []);
      setCurrentIndex(0); resetForNewQuestion();
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (!session) createSession(initialSkill ? [initialSkill] : []);
  }, [session, createSession, initialSkill]);

  const handleSubmit = async () => {
    if (!selected || !session || !q) return;
    setLoading(true);
    try {
      const timeSpent = (Date.now() - startTime) / 1000;
      const data = await api<SubmitResult>(
        `/api/practice/sessions/${session.session_id}/submit`,
        {
          method: "POST",
          body: JSON.stringify({
            question_id: q.question_id,
            answer: selected,
            time_spent: timeSpent,
            hints_used: hintLevel,
          }),
        },
      );
      setSubmitResult(data);
      setSubmitted(true);
    } catch { /* ignore */ }
    setLoading(false);
  };

  const handleHint = async () => {
    if (!q) return;
    try {
      const data = await api<{ hint: HintResult }>(
        `/api/practice/hint`,
        {
          method: "POST",
          body: JSON.stringify({ question_id: q.question_id, current_level: hintLevel }),
        },
      );
      setHint(data.hint); setHintLevel(data.hint.level);
    } catch { /* ignore */ }
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((i) => i + 1); resetForNewQuestion();
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex((i) => i - 1); resetForNewQuestion();
    }
  };

  const handleRestart = () => createSession();

  return {
    q, session, questions, currentIndex, selected, submitted, submitResult,
    loading, hint, hintLevel, isCorrect, setSelected, handleSubmit, handleHint,
    handleNext, handlePrev, handleRestart, createSession, setLoading,
  };
}
