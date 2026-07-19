/**
 * Demo6.0 Resource Runtime Hook
 *
 * Integrates with backend ReadingRuntime (/api/resources)
 * for resource reading position tracking + highlight management.
 */

"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import {
  listResources,
  getReadingState,
  openResource,
  updatePosition,
  createHighlight,
  closeResource,
  completeResource,
  type ResourceItem,
  type ReadingState,
  type HighlightData,
} from "@/lib/api/resource-runtime-api";

interface UseResourceRuntimeOptions {
  /** Only track position changes after a debounce delay (ms) */
  debounceMs?: number;
}

export function useResourceRuntime(opts: UseResourceRuntimeOptions = {}) {
  const { debounceMs = 3000 } = opts;

  const [resources, setResources] = useState<ResourceItem[]>([]);
  const [currentResource, setCurrentResource] = useState<ResourceItem | null>(null);
  const [readingState, setReadingState] = useState<ReadingState | null>(null);
  const [highlights, setHighlights] = useState<HighlightData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounced position sync
  const pendingPositionRef = useRef<{ page: number; scroll: number } | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const loadResources = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listResources();
      setResources(list);
    } catch (e: any) {
      setError(e?.message || "Failed to load resources");
    } finally {
      setLoading(false);
    }
  }, []);

  const open = useCallback(async (resourceId: string) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await openResource(resourceId);
      const state = await getReadingState(resourceId);
      setReadingState(state);
      setCurrentResource(resources.find((r) => r.id === resourceId) || null);
    } catch (e: any) {
      setError(e?.message || "Failed to open resource");
    } finally {
      setLoading(false);
    }
  }, [resources]);

  const trackPosition = useCallback(
    (page: number, scroll: number) => {
      pendingPositionRef.current = { page, scroll };
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(async () => {
        if (!currentResource?.id || !pendingPositionRef.current) return;
        try {
          await updatePosition(currentResource.id, pendingPositionRef.current.page, pendingPositionRef.current.scroll);
          setReadingState((prev) =>
            prev
              ? { ...prev, positionPage: page, positionScroll: scroll }
              : null,
          );
        } catch (e: any) {
          // silently fail — position tracking is best-effort
        }
        pendingPositionRef.current = null;
      }, debounceMs);
    },
    [currentResource, debounceMs],
  );

  const addHighlight = useCallback(
    async (text: string, note?: string, page?: number, scroll?: number) => {
      if (!currentResource?.id) return null;
      setError(null);
      try {
        const h = await createHighlight(currentResource.id, text, note || "", page, scroll);
        setHighlights((prev) => [...prev, h]);
        return h;
      } catch (e: any) {
        setError(e?.message || "Failed to create highlight");
        return null;
      }
    },
    [currentResource],
  );

  const close = useCallback(async () => {
    if (!currentResource?.id) return;
    try {
      await closeResource(currentResource.id);
      setCurrentResource(null);
      setReadingState(null);
    } catch (e: any) {
      setError(e?.message || "Failed to close resource");
    }
  }, [currentResource]);

  const complete = useCallback(async () => {
    if (!currentResource?.id) return;
    try {
      await completeResource(currentResource.id);
      setCurrentResource(null);
      setReadingState(null);
    } catch (e: any) {
      setError(e?.message || "Failed to complete resource");
    }
  }, [currentResource]);

  return {
    resources,
    currentResource,
    readingState,
    highlights,
    loading,
    error,
    loadResources,
    open,
    trackPosition,
    addHighlight,
    close,
    complete,
  };
}
