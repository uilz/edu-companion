/**
 * Resource API Client — AppleGo Demo6.0
 *
 * Backend: /api/resources (reading_runtime.py)
 */

import { authedFetchJson } from "./api";

export interface ResourceItem {
  id: string;
  workspaceId: string;
  materialId: string;
  title: string;
  state: string;
  createdAt: string;
}

export interface ReadingState {
  resourceId: string;
  positionPage: number;
  positionScroll: number;
  lastReadAt: string;
}

export interface HighlightData {
  id: string;
  resourceId: string;
  text: string;
  note: string;
  positionPage: number;
  positionScroll: number;
  createdAt: string;
}

export interface LifecycleResp {
  resourceId: string;
  state: string;
  title: string;
}

export async function listResources(): Promise<ResourceItem[]> {
  const rows = await authedFetchJson<any[]>("/api/resources");
  return (
    rows?.map((r: any) => ({
      id: r.id,
      workspaceId: r.workspace_id,
      materialId: r.material_id,
      title: r.title || "",
      state: r.state || "closed",
      createdAt: r.created_at || "",
    })) || []
  );
}

export async function getReadingState(
  resourceId: string
): Promise<ReadingState> {
  const s: any = await authedFetchJson(`/api/resources/${resourceId}/state`);
  return {
    resourceId: s.resource_id || resourceId,
    positionPage: s.position_page || 0,
    positionScroll: s.position_scroll || 0,
    lastReadAt: s.last_read_at || "",
  };
}

export async function openResource(resourceId: string): Promise<LifecycleResp> {
  const r: any = await authedFetchJson(`/api/resources/${resourceId}/open`, {
    method: "POST",
  });
  return { resourceId: r.resource_id, state: r.state, title: r.title };
}

export async function updatePosition(
  resourceId: string,
  page: number,
  scroll: number
): Promise<void> {
  await authedFetchJson(`/api/resources/${resourceId}/progress`, {
    method: "POST",
    body: JSON.stringify({ page, scroll }),
  });
}

export async function createHighlight(
  resourceId: string,
  text: string,
  note: string = "",
  page: number = 0,
  scroll: number = 0
): Promise<HighlightData> {
  const h: any = await authedFetchJson(
    `/api/resources/${resourceId}/highlights`,
    {
      method: "POST",
      body: JSON.stringify({ text, note, page, scroll }),
    }
  );
  return {
    id: h.id,
    resourceId: h.resource_id,
    text: h.text,
    note: h.note,
    positionPage: h.position_page,
    positionScroll: h.position_scroll,
    createdAt: h.created_at,
  };
}

export async function closeResource(resourceId: string): Promise<LifecycleResp> {
  const r: any = await authedFetchJson(`/api/resources/${resourceId}/close`, {
    method: "POST",
  });
  return { resourceId: r.resource_id, state: r.state, title: r.title };
}

export async function completeResource(
  resourceId: string
): Promise<LifecycleResp> {
  const r: any = await authedFetchJson(
    `/api/resources/${resourceId}/complete`,
    { method: "POST" }
  );
  return { resourceId: r.resource_id, state: r.state, title: r.title };
}
