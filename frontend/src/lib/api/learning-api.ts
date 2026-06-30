// Phase 10: 笔记/目标/探索项目 API 客户端
// 对接后端 /api/learning/*

import { api } from "@/lib/api/api";

// ── 带认证的 fetch 封装 ──
async function learningFetch<T>(path: string, options?: RequestInit): Promise<T> {
  return api<T>(path, options);
}

// ════════════════════════════════════════
// Types
// ════════════════════════════════════════

export interface Note {
  id: string;
  user_id: string;
  content: string;
  type: "highlight" | "explain" | "reflect" | "note";
  source_text: string;
  node_ids: string[];
  message_id: string | null;
  conv_id: string | null;
  metadata: Record<string, any>;
  created_at: string;
}

export interface Goal {
  id: string;
  user_id: string;
  node_id: string;
  node_label: string;
  target_mastery: number;
  target_date: string | null;
  current_mastery: number;
  priority: number;
  status: "active" | "achieved" | "paused" | "abandoned";
  notes: string;
  created_at: string;
}

export interface Project {
  id: string;
  title: string;
  description: string;
  goal: string;
  node_ids: string[];
  prerequisites: string[];
  deliverables: string[];
  status: string;
  difficulty: number;
  estimated_hours: number;
  source: string;
  created_at: string;
}

// ════════════════════════════════════════
// Notes API
// ════════════════════════════════════════

export async function createNote(data: {
  content: string;
  type: Note["type"];
  source_text?: string;
  node_ids?: string[];
  message_id?: string;
  conv_id?: string;
  metadata?: Record<string, any>;
}): Promise<{ id: string; status: string }> {
  return learningFetch("/api/learning/notes", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listNotes(params?: {
  node_id?: string;
  type?: Note["type"];
  limit?: number;
  offset?: number;
}): Promise<Note[]> {
  const searchParams = new URLSearchParams();
  if (params?.node_id) searchParams.set("node_id", params.node_id);
  if (params?.type) searchParams.set("type", params.type);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const path = `/api/learning/notes${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
  return learningFetch(path);
}

export async function getNote(noteId: string): Promise<Note> {
  return learningFetch(`/api/learning/notes/${noteId}`);
}

export async function deleteNote(noteId: string): Promise<void> {
  await learningFetch(`/api/learning/notes/${noteId}`, { method: "DELETE" });
}

export async function aggregateNotes(params?: {
  node_ids?: string[];
  time_range?: "week" | "month" | "all";
}): Promise<{ total: number; notes: Note[]; message: string }> {
  const searchParams = new URLSearchParams();
  if (params?.node_ids) {
    params.node_ids.forEach((id) => searchParams.append("node_ids", id));
  }
  if (params?.time_range) searchParams.set("time_range", params.time_range);

  const path = `/api/learning/notes/aggregate${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
  return learningFetch(path, { method: "POST" });
}

// ════════════════════════════════════════
// Goals API
// ════════════════════════════════════════

export async function createGoal(data: {
  node_id: string;
  node_label?: string;
  target_mastery?: number;
  target_date?: string;
  priority?: number;
  notes?: string;
}): Promise<{ id: string; status: string }> {
  return learningFetch("/api/learning/goals", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listGoals(params?: {
  node_id?: string;
  status?: Goal["status"];
}): Promise<Goal[]> {
  const searchParams = new URLSearchParams();
  if (params?.node_id) searchParams.set("node_id", params.node_id);
  if (params?.status) searchParams.set("status", params.status);

  const path = `/api/learning/goals${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
  return learningFetch(path);
}

export async function updateGoal(
  goalId: string,
  data: Partial<{
    target_mastery: number;
    target_date: string;
    priority: number;
    status: Goal["status"];
    current_mastery: number;
    notes: string;
  }>
): Promise<void> {
  await learningFetch(`/api/learning/goals/${goalId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ════════════════════════════════════════
// Projects API
// ════════════════════════════════════════

export async function generateProject(data: {
  node_ids: string[];
  title_hint?: string;
}): Promise<{ projects: Project[] }> {
  return learningFetch("/api/learning/projects/generate", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listProjects(params?: {
  status?: string;
}): Promise<Project[]> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);

  const path = `/api/learning/projects${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
  return learningFetch(path);
}
