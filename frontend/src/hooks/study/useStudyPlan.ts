"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api/api";
import { useCurrentUserId } from "@/hooks/useCurrentUserId";

/** 学习计划中的单个任务项 */
export interface PlanItem {
  task_id: string; skill_id: string; title: string; description: string;
  subject: string; estimated_minutes: number; difficulty: number;
  priority: number; daily_questions: number; completed: boolean; level: string;
}

/** 学习计划整体数据 */
export interface PlanData {
  items: PlanItem[]; total_items: number; estimated_total_minutes: number;
  daily_questions: number; habit_level: string; difficulty_bias: number;
  recent_accuracy: number; week_number: number;
}

/** AI 学习建议项 */
export interface Suggestion {
  skill_id: string; label: string; level: string; p_known: number; subject: string;
}

/** 进度数据 */
export interface ProgressData {
  completed_tasks: number; total_tasks: number; completion_rate: number;
}

/** 建议数据 */
export interface SuggestionData {
  urgent: Suggestion[]; building: Suggestion[]; new_topic: Suggestion[];
  suggestion: string;
}

/**
 * useStudyPlan — 学习规划页面的数据逻辑
 * 加载计划、进度、建议，支持生成/刷新和完成标记
 */
export function useStudyPlan() {
  const userId = useCurrentUserId();
  const [planItems, setPlanItems] = useState<PlanItem[]>([]);
  const [planMeta, setPlanMeta] = useState<PlanData | null>(null);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    if (!userId) return;
    setLoading(true); setError("");
    try {
      const [planData, progData, suggData] = await Promise.all([
        api<any>(`/api/study/plan/${userId}`).catch(() => null),
        api<any>(`/api/study/plan/${userId}/progress`).catch(() => null),
        api<any>("/api/study/suggestions").catch(() => null),
      ]);
      if (planData) {
        setPlanItems(planData.plan?.items || []); setPlanMeta(planData.plan || null);
      }
      if (progData) setProgress(progData);
      if (suggData) setSuggestions(suggData);
    } catch { setError("加载失败，请检查后端服务"); }
    finally { setLoading(false); }
  }, [userId]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await api(`/api/study/plan/generate?user_id=${userId}&reason=manual`, { method: "POST" });
      await loadData();
    } catch { /* ignore */ }
    finally { setGenerating(false); }
  };

  const handleComplete = async (taskId: string) => {
    try {
      await api(`/api/study/plan/${userId}/${taskId}/complete`, { method: "PUT" });
      const progData = await api<any>(`/api/study/plan/${userId}/progress`);
      setProgress(progData);
    } catch { /* ignore */ }
  };

  const completionRate = progress?.completion_rate ?? 0;

  const habitLabel: Record<string, string> = {
    beginner: "🌱 初学", regular: "📚 日常", intensive: "💪 强化",
  };

  return {
    planItems, planMeta, progress, suggestions, loading, generating, error,
    handleGenerate, handleComplete, loadData, completionRate, habitLabel,
  };
}
