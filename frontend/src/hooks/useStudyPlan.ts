"use client";

import { useState, useEffect, useCallback } from "react";
import { API_BASE } from "@/lib/api";

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
  const [planItems, setPlanItems] = useState<PlanItem[]>([]);
  const [planMeta, setPlanMeta] = useState<PlanData | null>(null);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [planRes, progRes, suggRes] = await Promise.all([
        fetch(`${API_BASE}/api/study/plan/default_user`),
        fetch(`${API_BASE}/api/study/plan/default_user/progress`),
        fetch(`${API_BASE}/api/study/suggestions`),
      ]);
      if (planRes.ok) {
        const d = await planRes.json();
        setPlanItems(d.plan?.items || []); setPlanMeta(d.plan || null);
      }
      if (progRes.ok) setProgress(await progRes.json());
      if (suggRes.ok) setSuggestions(await suggRes.json());
    } catch { setError("加载失败，请检查后端服务"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`${API_BASE}/api/study/plan/generate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "default_user", reason: "manual" }),
      });
      if (res.ok) await loadData();
    } catch { /* ignore */ }
    finally { setGenerating(false); }
  };

  const handleComplete = async (taskId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/study/plan/default_user/${taskId}/complete`, { method: "PUT" });
      if (res.ok) {
        const progRes = await fetch(`${API_BASE}/api/study/plan/default_user/progress`);
        if (progRes.ok) setProgress(await progRes.json());
      }
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
