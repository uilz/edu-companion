"use client";

import React, { useState, useMemo } from "react";
import { Search, X, ChevronRight, ChevronDown, ChevronsUpDown, ChevronsDownUp } from "lucide-react";
import type { GraphData, GraphNode } from "@/lib/types/graph-types";
import { getMasteryColor, LEVEL_LABELS } from "@/lib/types/graph-types";

interface LayerPanelProps {
  graphData: GraphData;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  matchedNodeIds: string[];
  selectedNodeId?: string;
  onNodeSelect: (node: GraphNode) => void;
  maxDisplayLevel?: string;
  onMaxLevelChange: (level: string | undefined) => void;
  onClose: () => void;
  masteryFilter?: Set<string>;
  onMasteryFilterChange?: (f: Set<string>) => void;
}

export default function LayerPanel({
  graphData, searchQuery, onSearchChange, matchedNodeIds,
  selectedNodeId, onNodeSelect, maxDisplayLevel, onMaxLevelChange, onClose,
  masteryFilter, onMasteryFilterChange,
}: LayerPanelProps) {
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());

  // 全部展开/折叠
  const hasAnyCollapsed = useMemo(() => {
    return collapsedIds.size > 0;
  }, [collapsedIds]);

  const toggleExpandAll = () => {
    if (hasAnyCollapsed) {
      setCollapsedIds(new Set());
    } else {
      const allIds = new Set(graphData.nodes.map(n => n.id));
      setCollapsedIds(allIds);
    }
  };

  // 掌握度过滤
  const masteryFilterSet = masteryFilter || new Set(["mastered", "learning", "untouched"]);

  // ── 构建层级树 ──
  const treeItems = useMemo(() => {
    if (!graphData?.nodes) return [];
    const rootNodes = graphData.nodes.filter(n => !n.parent);
    const childrenOf = new Map<string, GraphNode[]>();
    for (const n of graphData.nodes) {
      if (n.parent) {
        const sib = childrenOf.get(n.parent) || [];
        sib.push(n);
        childrenOf.set(n.parent, sib);
      }
    }

    const renderNode = (node: GraphNode, depth: number): React.ReactNode => {
      const children = childrenOf.get(node.id) || [];
      const isCollapsed = collapsedIds.has(node.id);
      const isSelected = node.id === selectedNodeId;
      const isMatched = matchedNodeIds.length > 0 && matchedNodeIds.includes(node.id);

      return (
        <div key={node.id}>
          <div
            className={`lp-item flex items-center gap-1 px-3 py-1.5 cursor-pointer text-[11px] transition-colors hover:bg-surface-hover ${
              isSelected ? "bg-accent/10 text-accent font-medium" : ""
            }`}
            style={{ paddingLeft: `${12 + depth * 14}px` }}
            onClick={() => onNodeSelect(node)}>
            {/* 折叠/展开 */}
            {children.length > 0 ? (
              <span className="w-4 flex-shrink-0 flex items-center justify-center text-muted cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  const newSet = new Set(collapsedIds);
                  if (isCollapsed) newSet.delete(node.id); else newSet.add(node.id);
                  setCollapsedIds(newSet);
                }}>
                {isCollapsed ? <ChevronRight size={11} /> : <ChevronDown size={11} />}
              </span>
            ) : <span className="w-4" />}

            {/* 名称 */}
            <span className={`flex-1 truncate ${isMatched ? "text-accent font-medium" : ""}`}>
              {isMatched ? highlightMatch(node.label, searchQuery) : node.label}
            </span>

            {/* 掌握度 */}
            <span className="text-[9px] px-1.5 py-0.5 rounded-full" style={{
              background: `${getMasteryColor(node.mastery)}15`,
              color: getMasteryColor(node.mastery),
            }}>
              {node.mastery >= 0.8 ? "✅" : node.mastery >= 0.05 ? `${Math.round(node.mastery * 100)}%` : "—"}
            </span>
          </div>
          {/* 子节点 */}
          {!isCollapsed && children.map(c => renderNode(c, depth + 1))}
        </div>
      );
    };

    return rootNodes.map(n => renderNode(n, 0));
  }, [graphData, collapsedIds, selectedNodeId, matchedNodeIds, searchQuery, onNodeSelect]);

  return (
    <div className="absolute top-3 left-3 w-[220px] bg-surface-elevated border border rounded-xl shadow-md z-30 overflow-hidden">
      {/* 标题 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border">
        <span className="text-[11px] font-semibold text">📂 层级导航</span>
        <div className="flex items-center gap-1">
          <button
            onClick={toggleExpandAll}
            className="text-muted hover:text p-0.5 rounded transition-colors"
            title={hasAnyCollapsed ? "全部展开" : "全部折叠"}
          >
            {hasAnyCollapsed ? <ChevronsDownUp size={12} /> : <ChevronsUpDown size={12} />}
          </button>
          <button onClick={onClose} className="text-muted hover:text p-0.5 rounded transition-colors">
            <X size={12} />
          </button>
        </div>
      </div>

      {/* 搜索 */}
      <div className="px-3 py-2 border-b border">
        <div className="relative">
          <input value={searchQuery} onChange={e => onSearchChange(e.target.value)}
            placeholder="搜索节点…"
            className="w-full pl-6 pr-2 py-1 text-[11px] border border rounded-lg bg-page-secondary focus:outline-none focus:border-accent" />
          <Search size={11} className="absolute left-1.5 top-1/2 -translate-y-1/2 text-muted" />
        </div>
      </div>

      {/* 层级树 */}
      <div className="max-h-[240px] overflow-y-auto">
        {treeItems}
      </div>

      {/* 掌握度筛选 — 匹配 demo */}
      <div className="px-3 py-2 border-t border space-y-1.5">
        <span className="text-[9px] text-muted font-medium">掌握度</span>
        <div className="flex flex-wrap gap-1">
          {([
            { key: "mastered", label: "已掌握", icon: "✅", color: "text-success" },
            { key: "learning", label: "学习中", icon: "📖", color: "text-warning" },
            { key: "untouched", label: "未开始", icon: "📐", color: "text-muted" },
          ] as const).map(({ key, label, icon, color }) => (
            <label key={key} className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] cursor-pointer hover:bg-surface-hover text-muted">
              <input
                type="checkbox"
                checked={masteryFilterSet.has(key)}
                onChange={(e) => {
                  if (!onMasteryFilterChange) return;
                  const next = new Set(masteryFilterSet);
                  if (e.target.checked) next.add(key);
                  else next.delete(key);
                  onMasteryFilterChange(next);
                }}
                className="w-2.5 h-2.5 accent-accent"
              />
              <span className={color}>{icon} {label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* 层级筛选 */}
      <div className="px-3 py-2 border-t border space-y-1.5">
        <span className="text-[9px] text-muted font-medium">层级筛选</span>
        <div className="flex flex-wrap gap-1">
          {Object.entries(LEVEL_LABELS).map(([level, label]) => (
            <button key={level} onClick={() => onMaxLevelChange(maxDisplayLevel === level ? undefined : level)}
              className={`px-2 py-0.5 rounded text-[9px] transition-all ${
                maxDisplayLevel === level
                  ? "bg-accent/10 text-accent border border-accent/30"
                  : "text-muted hover:text border border-transparent"
              }`}>
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── 高亮匹配文字 ──
function highlightMatch(text: string, query: string) {
  if (!query.trim()) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx < 0) return text;
  return (
    <>
      {text.slice(0, idx)}
      <span className="bg-accent/20 text-accent rounded px-0.5">{text.slice(idx, idx + query.length)}</span>
      {text.slice(idx + query.length)}
    </>
  );
}
