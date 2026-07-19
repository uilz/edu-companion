/**
 * Growth API Client — AppleGo Demo6.0
 *
 * Backend: /api/growth (growth_engine.py)
 */

import { authedFetchJson } from "./api";

export interface MilestoneData {
  id: string;
  workspaceId: string;
  type: string;
  title: string;
  description: string;
  conceptId: string;
  dayNumber: number;
  detectedAt: string;
}

export interface SnapshotData {
  id: string;
  workspaceId: string;
  dayNumber: number;
  sessionCount: number;
  conceptCount: number;
  connectionCount: number;
  topConcepts: string;
  createdAt: string;
}

export interface TrajectoryData {
  fromDay: number;
  toDay: number;
  deltaSessions: number;
  deltaConcepts: number;
}

export async function getMilestones(
  workspaceId: string
): Promise<MilestoneData[]> {
  const rows = await authedFetchJson<any[]>(
    `/api/growth/${workspaceId}/milestones`
  );
  return (
    rows?.map((m: any) => ({
      id: m.id,
      workspaceId: m.workspace_id,
      type: m.type,
      title: m.title,
      description: m.description,
      conceptId: m.concept_id,
      dayNumber: m.day_number,
      detectedAt: m.detected_at,
    })) || []
  );
}

export async function getUserMilestones(): Promise<MilestoneData[]> {
  const rows = await authedFetchJson<any[]>("/api/growth/milestones");
  return (
    rows?.map((m: any) => ({
      id: m.id,
      workspaceId: m.workspace_id,
      type: m.type,
      title: m.title,
      description: m.description,
      conceptId: m.concept_id,
      dayNumber: m.day_number,
      detectedAt: m.detected_at,
    })) || []
  );
}

export async function getSnapshots(
  workspaceId: string
): Promise<SnapshotData[]> {
  const rows = await authedFetchJson<any[]>(
    `/api/growth/${workspaceId}/snapshots`
  );
  return (
    rows?.map((s: any) => ({
      id: s.id,
      workspaceId: s.workspace_id,
      dayNumber: s.day_number,
      sessionCount: s.session_count,
      conceptCount: s.concept_count,
      connectionCount: s.connection_count,
      topConcepts: s.top_concepts,
      createdAt: s.created_at,
    })) || []
  );
}

export async function computeSnapshot(
  workspaceId: string
): Promise<SnapshotData> {
  const s: any = await authedFetchJson(
    `/api/growth/${workspaceId}/snapshots`,
    { method: "POST" }
  );
  return {
    id: s.id,
    workspaceId: s.workspace_id,
    dayNumber: s.day_number,
    sessionCount: s.session_count,
    conceptCount: s.concept_count,
    connectionCount: s.connection_count,
    topConcepts: s.top_concepts,
    createdAt: s.created_at,
  };
}

export async function getTrajectory(
  workspaceId: string,
  fromDay: number,
  toDay: number
): Promise<TrajectoryData> {
  const params = new URLSearchParams({
    from_day: String(fromDay),
    to_day: String(toDay),
  });
  const t: any = await authedFetchJson(
    `/api/growth/${workspaceId}/trajectory?${params}`
  );
  return {
    fromDay: t.from_day,
    toDay: t.to_day,
    deltaSessions: t.delta_sessions,
    deltaConcepts: t.delta_concepts,
  };
}
