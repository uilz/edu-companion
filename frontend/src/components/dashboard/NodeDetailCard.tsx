"use client";

import React from "react";
import Card from "@/components/ui/Card";
import { Info } from "lucide-react";
import type { DashboardNode, DashboardEdge } from "./graph-layout";
import { masteryColor, subjectColors, fallbackColor } from "./graph-layout";

interface NodeDetailCardProps {
  selectedNode: DashboardNode;
  edges: DashboardEdge[];
  nodes: DashboardNode[];
  onSelectNode: (node: DashboardNode | null) => void;
}

export default function NodeDetailCard({ selectedNode, edges, nodes, onSelectNode }: NodeDetailCardProps) {
  return (
    <Card title="知识点详情">
      <div className="space-y-3">
        <div>
          <div className="text-lg font-semibold text">{selectedNode.label}</div>
          {selectedNode.description && <div className="text-xs text-muted mt-0.5">{selectedNode.description}</div>}
        </div>
        <div>
          <div className="text-xs text-muted mb-1">
            掌握度 · {selectedNode.mastery_level}
            <span className="ml-2">{selectedNode.trend === "improving" ? "📈" : selectedNode.trend === "declining" ? "📉" : selectedNode.trend === "plateau" ? "→" : ""}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 bg-surface h-2">
              <div className="h-full transition-all duration-500" style={{ width: `${selectedNode.mastery}%`, backgroundColor: masteryColor(selectedNode.mastery) }} />
            </div>
            <span className="text-sm text font-medium">{selectedNode.mastery}%</span>
          </div>
          {selectedNode.confidence > 0 && <div className="text-[10px] text-muted mt-1">信度 {Math.round(selectedNode.confidence * 100)}%</div>}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-muted">状态:</span>
          {selectedNode.blocked
            ? <span className="text-xs px-2 py-0.5 border border-[#f97316] text-[#f97316]">前置未满足</span>
            : selectedNode.mastery >= 80
              ? <span className="text-xs px-2 py-0.5 border border-[#22c55e] text-[#22c55e]">已掌握</span>
              : selectedNode.mastery > 0
                ? <span className="text-xs px-2 py-0.5 border border-[#84cc16] text-[#84cc16]">学习中</span>
                : <span className="text-xs px-2 py-0.5 border border text-muted">未接触</span>
          }
          {selectedNode.attempt_count > 0 && <span className="text-[10px] text-muted">练 {selectedNode.attempt_count} 次</span>}
        </div>
        {selectedNode.anomaly_type && (
          <div className="p-2 border border-[#f59e0b] bg-[#f59e0b]/10 text-xs">
            <span className="text-[#f59e0b] font-medium">⚠️ {selectedNode.anomaly_type}</span>
            {selectedNode.anomaly_detail && <div className="text-muted mt-0.5">{selectedNode.anomaly_detail}</div>}
          </div>
        )}
        <div>
          <div className="text-xs text-muted mb-1">前置知识</div>
          <div className="flex flex-wrap gap-1.5">
            {edges.filter(e => e.to === selectedNode.id).map(e => {
              const fromNode = nodes.find(n => n.id === e.from);
              return (
                <button key={e.from} onClick={() => { const n = nodes.find(nn => nn.id === e.from); if (n) onSelectNode(n); }}
                  className={`text-xs px-2 py-1 border transition-colors cursor-pointer ${e.satisfied ? "border text-secondary" : "border-[#f97316]/30 text-[#f97316]"}`}>
                  {fromNode?.label || e.from}
                </button>
              );
            })}
            {edges.filter(e => e.to === selectedNode.id).length === 0 && <span className="text-xs text-muted">无（入口知识点）</span>}
          </div>
        </div>
        {selectedNode.error_clusters.length > 0 && (
          <div>
            <div className="text-xs text-muted mb-1">常见错误</div>
            <div className="flex flex-wrap gap-1">
              {selectedNode.error_clusters.map((e, i) => <span key={i} className="text-[10px] px-1.5 py-0.5 bg-surface text-muted">{e}</span>)}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
