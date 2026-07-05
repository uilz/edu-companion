"use client";

// ============================================================
//  useProjectData — 项目数据 + 操作 (Task #89)
// ============================================================

import { useCallback } from "react";
import { useUserData } from "@/hooks/useUserData";
import { authedFetch, API_BASE } from "@/lib/api/api";
import { Project, ProjectNode, Version, Milestone } from "../types";

export interface NewNodeInput {
  type: number;
  title: string;
  parent_id: string | null;
  description?: string | null;
}

export function useProjectData(projectId: string | undefined) {
  const { data, loading, refetch } = useUserData<Project>(
    async () => {
      if (!projectId) throw new Error("missing projectId");
      const res = await authedFetch(`${API_BASE}/api/projects/${projectId}`);
      return res.json();
    },
    [projectId],
  );

  const addNode = useCallback(
    async (input: NewNodeInput): Promise<ProjectNode | null> => {
      if (!projectId) return null;
      const res = await authedFetch(`${API_BASE}/api/projects/${projectId}/nodes`, {
        method: "POST",
        body: JSON.stringify({
          type: input.type,
          title: input.title,
          parent_id: input.parent_id,
          description: input.description || null,
        }),
      });
      await refetch();
      return res.json();
    },
    [projectId, refetch],
  );

  const saveNode = useCallback(
    async (nodeId: string, payload: Record<string, unknown>): Promise<void> => {
      if (!projectId) return;
      await authedFetch(`${API_BASE}/api/projects/${projectId}/nodes/${nodeId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await refetch();
    },
    [projectId, refetch],
  );

  const deleteNode = useCallback(
    async (nodeId: string): Promise<void> => {
      if (!projectId) return;
      await authedFetch(`${API_BASE}/api/projects/${projectId}/nodes/${nodeId}`, {
        method: "DELETE",
      });
      await refetch();
    },
    [projectId, refetch],
  );

  const completeNode = useCallback(
    async (nodeId: string, completed: boolean): Promise<void> => {
      if (!projectId) return;
      await authedFetch(
        `${API_BASE}/api/projects/${projectId}/nodes/${nodeId}/complete?completed=${completed}`,
        { method: "POST" },
      );
      await refetch();
    },
    [projectId, refetch],
  );

  const setNodeStatus = useCallback(
    async (nodeId: string, status: string): Promise<void> => {
      if (!projectId) return;
      await authedFetch(
        `${API_BASE}/api/projects/${projectId}/nodes/${nodeId}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({ status }),
        },
      );
      await refetch();
    },
    [projectId, refetch],
  );

  const reorderNodes = useCallback(
    async (parentId: string | null, nodeIds: string[]): Promise<void> => {
      if (!projectId) return;
      await authedFetch(`${API_BASE}/api/projects/${projectId}/nodes/reorder`, {
        method: "POST",
        body: JSON.stringify({
          parent_id: parentId,
          node_ids_in_order: nodeIds,
        }),
      });
      await refetch();
    },
    [projectId, refetch],
  );

  const loadVersions = useCallback(
    async (nodeId: string): Promise<Version[]> => {
      if (!projectId) return [];
      const res = await authedFetch(
        `${API_BASE}/api/projects/${projectId}/nodes/${nodeId}/versions`,
      );
      const json = await res.json();
      return json.versions || [];
    },
    [projectId],
  );

  const rollbackNode = useCallback(
    async (nodeId: string, targetVersion: number, fields?: string[]): Promise<void> => {
      if (!projectId) return;
      await authedFetch(
        `${API_BASE}/api/projects/${projectId}/nodes/${nodeId}/rollback`,
        {
          method: "POST",
          body: JSON.stringify({ target_version: targetVersion, fields: fields || null }),
        },
      );
      await refetch();
    },
    [projectId, refetch],
  );

  const diffVersions = useCallback(
    async (nodeId: string, a: number, b: number): Promise<string[]> => {
      if (!projectId) return [];
      const res = await authedFetch(
        `${API_BASE}/api/projects/${projectId}/nodes/${nodeId}/diff`,
        {
          method: "POST",
          body: JSON.stringify({ version_a: a, version_b: b }),
        },
      );
      const json = await res.json();
      return json.changed_fields || [];
    },
    [projectId],
  );

  const createMilestone = useCallback(
    async (milestoneName: string): Promise<Milestone | null> => {
      if (!projectId) return null;
      const res = await authedFetch(
        `${API_BASE}/api/projects/${projectId}/milestones`,
        {
          method: "POST",
          body: JSON.stringify({ milestone_name: milestoneName }),
        },
      );
      await refetch();
      return res.json();
    },
    [projectId, refetch],
  );

  const exportNode = useCallback(
    async (nodeId: string, targetModule: string): Promise<void> => {
      if (!projectId) return;
      await authedFetch(
        `${API_BASE}/api/projects/${projectId}/nodes/${nodeId}/export`,
        {
          method: "POST",
          body: JSON.stringify({
            target_module: targetModule,
            target_ref_id: "",
          }),
        },
      );
    },
    [projectId],
  );

  const linkCopyNode = useCallback(
    async (nodeId: string): Promise<void> => {
      if (!projectId) return;
      await authedFetch(`${API_BASE}/api/projects/${projectId}/copy-nodes`, {
        method: "POST",
        body: JSON.stringify({
          source_project_id: projectId,
          node_ids: [nodeId],
          mode: "link_copy",
        }),
      });
      await refetch();
    },
    [projectId, refetch],
  );

  return {
    project: data,
    loading,
    refetch,
    addNode,
    saveNode,
    deleteNode,
    completeNode,
    setNodeStatus,
    reorderNodes,
    loadVersions,
    rollbackNode,
    diffVersions,
    createMilestone,
    exportNode,
    linkCopyNode,
  };
}
