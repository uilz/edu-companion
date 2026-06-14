"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { fetchGraphData } from "@/lib/api/graph-api";
import type { GraphData } from "@/lib/types/graph-types";

export interface UseGraphDataOptions {
  /** 分区 ID（可选，不传则获取全部图谱） */
  partitionId?: string;
  /** 失败重试次数（默认 0，不重试） */
  maxRetries?: number;
  /** 是否自动加载（默认 true） */
  autoLoad?: boolean;
}

export interface UseGraphDataReturn {
  graphData: GraphData | null;
  loading: boolean;
  error: string | null;
  /** 绑定到图谱容器的 ref（自动关联 ResizeObserver） */
  graphContainerRef: React.RefObject<HTMLDivElement | null>;
  /** 容器尺寸（px） */
  graphSize: { width: number; height: number };
  /** 重新加载图谱数据 */
  reload: () => void;
  /** 手工设置 graphData（例如外部更新后同步） */
  setGraphData: React.Dispatch<React.SetStateAction<GraphData | null>>;
}

/**
 * useGraphData — 图谱数据加载 + ResizeObserver 监听
 *
 * 被 useGraphCanvas 和 FocusPage 共享使用，消除数据层重复。
 */
export function useGraphData(options: UseGraphDataOptions = {}): UseGraphDataReturn {
  const { partitionId, maxRetries = 0, autoLoad = true } = options;

  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(autoLoad);
  const [error, setError] = useState<string | null>(null);
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const [graphSize, setGraphSize] = useState({ width: 600, height: 500 });

  const reload = useCallback(() => {
    let retries = 0;
    const doFetch = () => {
      setLoading(true);
      setError(null);
      fetchGraphData(partitionId)
        .then((data) => {
          setGraphData(data);
          setError(null);
        })
        .catch((e) => {
          if (retries < maxRetries) {
            retries++;
            setTimeout(doFetch, 1500 * retries);
          } else {
            setError((e as Error).message);
          }
        })
        .finally(() => setLoading(false));
    };
    doFetch();
  }, [partitionId, maxRetries]);

  // Auto-load
  useEffect(() => {
    if (autoLoad) reload();
  }, [reload, autoLoad]);

  // ResizeObserver
  useEffect(() => {
    const el = graphContainerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        setGraphSize({
          width: Math.max(300, e.contentRect.width),
          height: Math.max(300, e.contentRect.height),
        });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return { graphData, loading, error, graphContainerRef, graphSize, reload, setGraphData };
}
