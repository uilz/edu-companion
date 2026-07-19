/**
 * Demo6.0 Growth Runtime Hook
 *
 * Integrates with backend GrowthEngine (/api/growth)
 * for milestone tracking + evolution snapshots + trajectory.
 */

"use client";

import { useState, useCallback } from "react";
import {
  getMilestones,
  getUserMilestones,
  getSnapshots,
  computeSnapshot,
  getTrajectory,
  type MilestoneData,
  type SnapshotData,
  type TrajectoryData,
} from "@/lib/api/growth-runtime-api";

export function useGrowthRuntime() {
  const [milestones, setMilestones] = useState<MilestoneData[]>([]);
  const [userMilestones, setUserMilestones] = useState<MilestoneData[]>([]);
  const [snapshots, setSnapshots] = useState<SnapshotData[]>([]);
  const [trajectory, setTrajectory] = useState<TrajectoryData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadMilestones = useCallback(async (workspaceId: string) => {
    if (!workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      const list = await getMilestones(workspaceId);
      setMilestones(list);
    } catch (e: any) {
      setError(e?.message || "Failed to load milestones");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadUserMilestones = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await getUserMilestones();
      setUserMilestones(list);
    } catch (e: any) {
      setError(e?.message || "Failed to load user milestones");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSnapshots = useCallback(async (workspaceId: string) => {
    if (!workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      const list = await getSnapshots(workspaceId);
      setSnapshots(list);
    } catch (e: any) {
      setError(e?.message || "Failed to load snapshots");
    } finally {
      setLoading(false);
    }
  }, []);

  const triggerSnapshot = useCallback(async (workspaceId: string) => {
    if (!workspaceId) return null;
    setError(null);
    try {
      const snap = await computeSnapshot(workspaceId);
      setSnapshots((prev) => [...prev, snap]);
      return snap;
    } catch (e: any) {
      setError(e?.message || "Failed to compute snapshot");
      return null;
    }
  }, []);

  const loadTrajectory = useCallback(
    async (workspaceId: string, fromDay: number, toDay: number) => {
      if (!workspaceId) return;
      setLoading(true);
      setError(null);
      try {
        const t = await getTrajectory(workspaceId, fromDay, toDay);
        setTrajectory(t);
      } catch (e: any) {
        setError(e?.message || "Failed to load trajectory");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return {
    milestones,
    userMilestones,
    snapshots,
    trajectory,
    loading,
    error,
    loadMilestones,
    loadUserMilestones,
    loadSnapshots,
    triggerSnapshot,
    loadTrajectory,
  };
}
