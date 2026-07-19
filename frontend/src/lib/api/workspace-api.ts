/**
 * Workspace API Client — AppleGo Demo6.0
 *
 * Backend: /api/workspaces (workspace_runtime.py)
 */

import { authedFetchJson, authedFetch } from "./api";

export interface WorkspaceItem {
  id: string;
  name: string;
  icon: string;
  color: string;
  state: string;
  dayCount: number;
  activeCount: number;
  completedCount: number;
  createdAt: string;
}

export interface WorkspaceDetail {
  id: string;
  name: string;
  icon: string;
  color: string;
  state: string;
  dayCount: number;
  totalSessions: number;
  activeSessions: number;
  overallProgress: number;
}

export interface SessionItem {
  id: string;
  title: string;
  description: string;
  stage: string;
  progress: number;
  estimatedMinutes: number;
  createdAt: string;
  status: string;
  state: string;
  missionSource: string;
  missionText: string;
  endedAt: string | null;
}

export interface SessionLifecycle {
  sessionId: string;
  workspaceId: string;
  state: string;
  title: string;
}

export interface TimelineEntry {
  dateLabel: string;
  items: { type: string; title: string; meta: string; sessionId: string | null }[];
}

export interface RoadmapStage {
  name: string;
  status: string;
  desc: string;
  stats: string;
  badge: string;
}

export interface Roadmap {
  title: string;
  overallProgress: number;
  stages: RoadmapStage[];
}

export interface SearchResult {
  type: string;
  title: string;
  snippet: string;
  meta: string;
  badge: string;
}

export interface LandingMemory {
  workspaceName: string;
  topic: string;
  workspaceId: string;
  sessionId: string | null;
}

// ── API Calls ──

export async function listWorkspaces(): Promise<WorkspaceItem[]> {
  const rows = await authedFetchJson<any[]>(
    "/api/workspaces"
  );
  return (
    rows?.map((w: any) => ({
      id: w.id,
      name: w.name,
      icon: w.icon || "book",
      color: w.color || "#5a8f6b",
      state: w.state || "created",
      dayCount: w.day_count || 0,
      activeCount: w.active_sessions_count || 0,
      completedCount: w.completed_sessions_count || 0,
      createdAt: w.created_at || "",
    })) || []
  );
}

export async function createWorkspace(name: string): Promise<WorkspaceItem> {
  const w: any = await authedFetchJson("/api/workspaces", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  return {
    id: w.id,
    name: w.name,
    icon: w.icon || "book",
    color: w.color || "#5a8f6b",
    state: w.state || "created",
    dayCount: w.day_count || 0,
    activeCount: w.active_sessions_count || 0,
    completedCount: w.completed_sessions_count || 0,
    createdAt: w.created_at || "",
  };
}

export async function getWorkspaceDetail(wsId: string): Promise<WorkspaceDetail> {
  const w: any = await authedFetchJson(`/api/workspaces/${wsId}`);
  return {
    id: w.id,
    name: w.name,
    icon: w.icon || "book",
    color: w.color || "#5a8f6b",
    state: w.state || "created",
    dayCount: w.day_count || 0,
    totalSessions: w.total_sessions || 0,
    activeSessions: w.active_sessions || 0,
    overallProgress: w.overall_progress || 0,
  };
}

export async function listSessions(wsId: string): Promise<SessionItem[]> {
  const rows = await authedFetchJson<any[]>(
    `/api/workspaces/${wsId}/sessions`
  );
  return (
    rows?.map((s: any) => ({
      id: s.id,
      title: s.title || "",
      description: s.description || "",
      stage: s.stage || "intro",
      progress: s.progress || 0,
      estimatedMinutes: s.estimated_minutes || 25,
      createdAt: s.created_at || "",
      status: s.status || "pending",
      state: s.state || "created",
      missionSource: s.mission_source || "",
      missionText: s.mission_text || "",
      endedAt: s.ended_at || null,
    })) || []
  );
}

export async function enterWorkspace(wsId: string): Promise<SessionLifecycle> {
  const s: any = await authedFetchJson(`/api/workspaces/${wsId}/enter`, {
    method: "POST",
  });
  return {
    sessionId: s.session_id,
    workspaceId: s.workspace_id,
    state: s.state,
    title: s.title,
  };
}

export async function pauseSession(wsId: string): Promise<SessionLifecycle> {
  const s: any = await authedFetchJson(`/api/workspaces/${wsId}/pause`, {
    method: "POST",
  });
  return {
    sessionId: s.session_id,
    workspaceId: s.workspace_id,
    state: s.state,
    title: s.title,
  };
}

export async function endSession(wsId: string): Promise<SessionLifecycle> {
  const s: any = await authedFetchJson(`/api/workspaces/${wsId}/end`, {
    method: "POST",
  });
  return {
    sessionId: s.session_id,
    workspaceId: s.workspace_id,
    state: s.state,
    title: s.title,
  };
}

export async function getTimeline(wsId: string): Promise<TimelineEntry[]> {
  const entries = await authedFetchJson<any[]>(
    `/api/workspaces/${wsId}/timeline`
  );
  return (
    entries?.map((e: any) => ({
      dateLabel: e.date_label,
      items: (e.items || []).map((it: any) => ({
        type: it.type,
        title: it.title,
        meta: it.meta,
        sessionId: it.session_id || null,
      })),
    })) || []
  );
}

export async function getRoadmap(wsId: string): Promise<Roadmap> {
  const r: any = await authedFetchJson(`/api/workspaces/${wsId}/roadmap`);
  return {
    title: r.title || "学习路线",
    overallProgress: r.overall_progress || 0,
    stages:
      r.stages?.map((s: any) => ({
        name: s.name,
        status: s.status,
        desc: s.desc || "",
        stats: s.stats || "",
        badge: s.badge || "",
      })) || [],
  };
}

export async function searchWorkspace(
  wsId: string,
  query: string
): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q: query });
  const rows = await authedFetchJson<any[]>(
    `/api/workspaces/${wsId}/search?${params}`
  );
  return (
    rows?.map((r: any) => ({
      type: r.type,
      title: r.title,
      snippet: r.snippet,
      meta: r.meta,
      badge: r.badge,
    })) || []
  );
}

export async function getLandingMemory(): Promise<LandingMemory | null> {
  try {
    const workspaces = await listWorkspaces();
    if (!workspaces.length) return null;

    // Find the workspace with most recent activity
    const active = workspaces.find((w) => w.activeCount > 0);
    if (!active) {
      return {
        workspaceName: workspaces[0].name,
        topic: "开始学习",
        workspaceId: workspaces[0].id,
        sessionId: null,
      };
    }

    // Get sessions for this workspace
    const sessions = await listSessions(active.id);
    const lastSession = sessions.find(
      (s) => s.state === "paused" || s.state === "active"
    );
    const topic = lastSession?.title || lastSession?.missionText || "上次的内容";

    return {
      workspaceName: active.name,
      topic,
      workspaceId: active.id,
      sessionId: lastSession?.id || null,
    };
  } catch {
    return null;
  }
}
