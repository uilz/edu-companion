"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api/api";
import { useAuth } from "@/contexts/AuthContext";

// ── Types ──

export type SourceModule =
  | "flashcard"
  | "practice"
  | "project"
  | "reading"
  | "language_room"
  | "manual";

export type PlanItemStatus =
  | "pending"
  | "scheduled"
  | "in_progress"
  | "completed"
  | "skipped"
  | "extended";

export interface PlanItem {
  id: string;
  user_id: string;
  source_module: SourceModule | string;
  target_type: string;
  target_ref_id: string;
  title: string;
  description?: string;
  estimated_minutes: number;
  actual_minutes?: number | null;
  linked_node_ids: string[];
  priority: number;
  is_mood_rule_affected: boolean;
  status: PlanItemStatus | string;
  scheduled_for?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  skipped_at?: string | null;
  plan_date?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface StatusBar {
  fatigue_risk: "low" | "medium" | "high" | string;
  pressure_score: number | null;
  energy_score: number | null;
  habit_level: "beginner" | "regular" | "intensive" | string;
  pomodoro_work_minutes: number;
  pomodoro_break_minutes: number;
  pomodoro_message: string;
}

export interface DailyView {
  date: string;
  status_bar: StatusBar;
  timeline_items: PlanItem[];
  pending_pool: Array<{
    id: string;
    source_module: string;
    target_type: string;
    target_ref_id: string;
    title: string;
    estimated_minutes: number;
    status: string;
  }>;
  adaptive_recommendations: Array<{
    task_id?: string;
    skill_id?: string;
    title?: string;
    description?: string;
    estimated_minutes?: number;
    difficulty?: number;
    priority?: number;
    level?: string;
  }>;
  brief_summary: { summary: string; payload: Record<string, unknown> };
}

export interface WeeklyDay {
  date: string;
  item_count: number;
  total_minutes: number;
  completed_count: number;
}

export interface WeeklyView {
  week_start: string;
  week_end: string;
  days: WeeklyDay[];
  totals: { total_minutes: number; total_completed: number; total_items: number };
  summary: StatusBar;
}

export interface KnowledgeNode {
  id: string;
  label: string;
  level: string;
  parent: string;
  todo_count: number;
}

export interface KnowledgeView {
  nodes: KnowledgeNode[];
  selected_node_id: string | null;
  selected_node_todos: PlanItem[];
}

export interface PlanGoal {
  id: string;
  user_id: string;
  title: string;
  description?: string;
  target_module: string;
  target_metric: string;
  target_value: number;
  current_value: number;
  deadline?: string | null;
  status: "active" | "completed" | "abandoned" | string;
  progress_pct: number;
  created_at?: string | null;
  completed_at?: string | null;
}

export interface PeriodicReview {
  id: string;
  user_id: string;
  period_type: "weekly" | "monthly" | string;
  period_start: string;
  period_end: string;
  summary_data: {
    items_total?: number;
    items_completed?: number;
    estimated_minutes?: number;
    actual_minutes?: number;
    by_module?: Array<{ source_module: string; count: number; minutes: number }>;
  };
  user_note: string;
  created_at?: string | null;
}

export interface ViewLayout {
  id: string;
  user_id: string;
  name: string;
  view_type: "day" | "week" | "knowledge" | "custom" | string;
  filters: Record<string, unknown>;
  layout: Record<string, unknown>;
  is_default: boolean;
  created_at?: string | null;
}

// ── Hooks ──

export function useDailyView(initialDate?: string) {
  const { user, loading: authLoading } = useAuth();
  const [data, setData] = useState<DailyView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(
    async (date?: string) => {
      if (authLoading || !user) return;
      setLoading(true);
      setError("");
      try {
        const params = new URLSearchParams();
        if (date) params.set("date", date);
        const qs = params.toString();
        const r = await api<DailyView>(`/api/planning/daily${qs ? `?${qs}` : ""}`);
        setData(r);
      } catch (e) {
        setError(String((e as Error).message || e));
      } finally {
        setLoading(false);
      }
    },
    [authLoading, user],
  );

  useEffect(() => {
    if (initialDate) load(initialDate);
    else load();
  }, [load, initialDate]);

  return { data, loading, error, reload: load };
}

export function useWeeklyView(weekStart?: string) {
  const { user, loading: authLoading } = useAuth();
  const [data, setData] = useState<WeeklyView | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(
    async (ws?: string) => {
      if (authLoading || !user) return;
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (ws) params.set("week_start", ws);
        const qs = params.toString();
        const r = await api<WeeklyView>(`/api/planning/weekly${qs ? `?${qs}` : ""}`);
        setData(r);
      } catch {
        setData(null);
      } finally {
        setLoading(false);
      }
    },
    [authLoading, user],
  );

  useEffect(() => {
    if (weekStart) load(weekStart);
    else load();
  }, [load, weekStart]);

  return { data, loading, reload: load };
}

export function useKnowledgeView(selectedNodeId?: string) {
  const { user, loading: authLoading } = useAuth();
  const [data, setData] = useState<KnowledgeView | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(
    async (nid?: string) => {
      if (authLoading || !user) return;
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (nid) params.set("selected_node_id", nid);
        const qs = params.toString();
        const r = await api<KnowledgeView>(`/api/planning/knowledge${qs ? `?${qs}` : ""}`);
        setData(r);
      } catch {
        setData(null);
      } finally {
        setLoading(false);
      }
    },
    [authLoading, user],
  );

  useEffect(() => {
    if (selectedNodeId !== undefined) load(selectedNodeId);
    else load();
  }, [load, selectedNodeId]);

  return { data, loading, reload: load };
}

export function usePlanItems() {
  const { user, loading: authLoading } = useAuth();
  const [items, setItems] = useState<PlanItem[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(
    async (filters?: { date?: string; status?: string; source_module?: string }) => {
      if (authLoading || !user) return;
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (filters?.date) params.set("date", filters.date);
        if (filters?.status) params.set("status", filters.status);
        if (filters?.source_module) params.set("source_module", filters.source_module);
        const qs = params.toString();
        const r = await api<{ items: PlanItem[]; total: number }>(
          `/api/planning/items${qs ? `?${qs}` : ""}`,
        );
        setItems(r.items || []);
      } catch {
        setItems([]);
      } finally {
        setLoading(false);
      }
    },
    [authLoading, user],
  );

  return { items, loading, reload: load };
}

export function useGoals() {
  const { user, loading: authLoading } = useAuth();
  const [goals, setGoals] = useState<PlanGoal[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (authLoading || !user) return;
    setLoading(true);
    try {
      const r = await api<{ goals: PlanGoal[]; total: number }>("/api/planning/goals");
      setGoals(r.goals || []);
    } catch {
      setGoals([]);
    } finally {
      setLoading(false);
    }
  }, [authLoading, user]);

  useEffect(() => {
    load();
  }, [load]);

  const create = useCallback(
    async (body: Omit<PlanGoal, "id" | "user_id" | "current_value" | "progress_pct" | "status" | "created_at" | "completed_at">) => {
      const r = await api<PlanGoal>("/api/planning/goals", {
        method: "POST",
        body: JSON.stringify(body),
      });
      await load();
      return r;
    },
    [load],
  );

  const update = useCallback(
    async (id: string, body: Partial<PlanGoal>) => {
      await api(`/api/planning/goals/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      await load();
    },
    [load],
  );

  return { goals, loading, reload: load, create, update };
}

export function useReviews() {
  const { user, loading: authLoading } = useAuth();
  const [reviews, setReviews] = useState<PeriodicReview[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (authLoading || !user) return;
    setLoading(true);
    try {
      const r = await api<{ reviews: PeriodicReview[] }>("/api/planning/reviews");
      setReviews(r.reviews || []);
    } catch {
      setReviews([]);
    } finally {
      setLoading(false);
    }
  }, [authLoading, user]);

  useEffect(() => {
    load();
  }, [load]);

  const generate = useCallback(
    async (body: {
      period_type: "weekly" | "monthly";
      period_start: string;
      period_end: string;
      user_note?: string;
    }) => {
      const r = await api<PeriodicReview>("/api/planning/reviews/generate", {
        method: "POST",
        body: JSON.stringify(body),
      });
      await load();
      return r;
    },
    [load],
  );

  return { reviews, loading, reload: load, generate };
}

export function useViewLayouts() {
  const { user, loading: authLoading } = useAuth();
  const [layouts, setLayouts] = useState<ViewLayout[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (authLoading || !user) return;
    setLoading(true);
    try {
      const r = await api<{ layouts: ViewLayout[] }>("/api/planning/view-layouts");
      setLayouts(r.layouts || []);
    } catch {
      setLayouts([]);
    } finally {
      setLoading(false);
    }
  }, [authLoading, user]);

  useEffect(() => {
    load();
  }, [load]);

  const create = useCallback(
    async (body: Omit<ViewLayout, "id" | "user_id" | "created_at">) => {
      const r = await api<ViewLayout>("/api/planning/view-layouts", {
        method: "POST",
        body: JSON.stringify(body),
      });
      await load();
      return r;
    },
    [load],
  );

  return { layouts, loading, reload: load, create };
}

// ── Mutations ──

export async function createPlanItem(body: {
  source_module: SourceModule;
  target_type: string;
  target_ref_id: string;
  title: string;
  description?: string;
  estimated_minutes?: number;
  linked_node_ids?: string[];
  priority?: number;
  scheduled_for?: string;
  plan_date?: string;
  is_mood_rule_affected?: boolean;
}): Promise<PlanItem> {
  return api<PlanItem>("/api/planning/items", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updatePlanItem(
  id: string,
  body: Partial<PlanItem>,
): Promise<PlanItem> {
  return api<PlanItem>(`/api/planning/items/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deletePlanItem(id: string): Promise<void> {
  await api(`/api/planning/items/${id}`, { method: "DELETE" });
}

export async function completePlanItem(
  id: string,
  actual_minutes: number,
): Promise<PlanItem> {
  return api<PlanItem>(`/api/planning/items/${id}/complete`, {
    method: "POST",
    body: JSON.stringify({ actual_minutes }),
  });
}

export async function startPlanItem(id: string): Promise<PlanItem> {
  return api<PlanItem>(`/api/planning/items/${id}/start`, { method: "POST" });
}

export async function skipPlanItem(id: string): Promise<PlanItem> {
  return api<PlanItem>(`/api/planning/items/${id}/skip`, { method: "POST" });
}

export async function extendPlanItem(
  id: string,
  minutes: number,
): Promise<PlanItem> {
  return api<PlanItem>(
    `/api/planning/items/${id}/extend?minutes=${minutes}`,
    { method: "POST" },
  );
}
