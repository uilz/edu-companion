"use client";

import React, { useRef, useEffect, useState, useMemo, useCallback } from "react";
import { ChevronLeft, ChevronRight, Network } from "lucide-react";
import type { GraphData, GraphNode } from "@/lib/types/graph-types";
import FocusGraph from "@/components/graph/graphs/FocusGraph";
import ForceGraph from "@/components/graph/graphs/ForceGraph";
import { fetchGraphData } from "@/lib/api/graph-api";

/**
 * GraphPanel — 专注模式右侧知识图谱面板
 * 支持思维导图/力导向双模式、可拖拽宽度、自动聚焦
 */
export default function GraphPanel({
  activeTopicId,
}: {
  activeTopicId?: string | null;
}) {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(true);
  const [graphMode, setGraphMode] = useState<"tree" | "force">("tree");
  const [selectedGraphNode, setSelectedGraphNode] = useState<GraphNode | null>(null);
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const [graphWidth, setGraphWidth] = useState(400);

  // 图谱 active path
  const activePath = useMemo(() => {
    if (!selectedGraphNode || !graphData) return [];
    const path: string[] = [];
    let current: GraphNode | undefined = selectedGraphNode;
    while (current) {
      path.unshift(current.id);
      current = current.parent ? graphData.nodes.find((n) => n.id === current!.parent) : undefined;
    }
    return path;
  }, [selectedGraphNode, graphData]);

  // 加载图谱
  useEffect(() => {
    let retries = 0;
    const doFetch = () => {
      setGraphLoading(true);
      fetchGraphData()
        .then(setGraphData)
        .catch(() => { if (retries++ < 3) setTimeout(doFetch, 1500 * retries); })
        .finally(() => setGraphLoading(false));
    };
    doFetch();
  }, []);

  // 会话切换 → 图谱自动聚焦
  useEffect(() => {
    if (!activeTopicId || !graphData) return;
    const topicNode = graphData.nodes.find((n) => n.id === activeTopicId);
    if (topicNode) setSelectedGraphNode(topicNode);
  }, [activeTopicId, graphData]);

  // 面板宽度监听
  useEffect(() => {
    if (!graphContainerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) setGraphWidth(entry.contentRect.width);
    });
    ro.observe(graphContainerRef.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={graphContainerRef} className="flex flex-col h-full">
      <div className="flex-shrink-0 border-b border-[var(--color-border)] px-4 py-3 flex items-center gap-2">
        <Network size={16} className="text-[var(--color-accent)]" />
        <span className="text-sm font-semibold text-[var(--color-text)]">知识图谱</span>
        {graphLoading && <span className="text-xs text-[var(--color-text-muted)]">加载中…</span>}
        <div className="flex-1" />
        <div className="flex items-center bg-[var(--color-surface)] rounded-lg p-0.5 gap-0.5">
          <button onClick={() => setGraphMode("tree")}
            className={`px-2 py-1 text-[11px] rounded-md transition-colors ${graphMode === "tree" ? "bg-[var(--color-accent)] text-white font-medium" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"}`}>思维导图</button>
          <button onClick={() => setGraphMode("force")}
            className={`px-2 py-1 text-[11px] rounded-md transition-colors ${graphMode === "force" ? "bg-[var(--color-accent)] text-white font-medium" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"}`}>力导向</button>
        </div>
      </div>
      <div className="flex-1 overflow-hidden p-2">
        {graphLoading ? (
          <div className="flex items-center justify-center h-full text-sm text-[var(--color-text-muted)]">加载知识图谱…</div>
        ) : graphData ? (
          graphMode === "tree" ? (
            <FocusGraph data={graphData} selectedNodeId={selectedGraphNode?.id} onNodeSelect={setSelectedGraphNode} activePath={activePath} width={graphWidth} height={1000} />
          ) : (
            <ForceGraph data={(() => {
              const validLevels = new Set(["partition", "domain", "topic"]);
              const nodes = graphData.nodes.filter((n) => validLevels.has(n.level));
              const validIds = new Set(nodes.map((n) => n.id));
              return { nodes, edges: graphData.edges.filter((e) => validIds.has(e.source) && validIds.has(e.target)) };
            })()} selectedNodeId={selectedGraphNode?.id} onNodeSelect={setSelectedGraphNode} width={graphWidth} height={1000} />
          )
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-[var(--color-text-muted)]">暂无图谱数据</div>
        )}
      </div>
    </div>
  );
}
