"use client";

import React, { useState } from "react";
import { X, Brain, Trash2, BookOpen, StickyNote, Layers, Calendar, Link as LinkIcon } from "lucide-react";
import type { TreeNode, CognitiveNodeView, SourceRef } from "@/lib/api/knowledge-trees-api";

interface TreeNodeDetailPanelProps {
  node: TreeNode;
  onClose: () => void;
  onDelete: () => void;
  onLinkCognitive: () => void;
}

function CognitiveViewCard({ cv }: { cv: CognitiveNodeView }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-muted text-xs">掌握度</span>
        <span className="text-xs font-medium" style={{ color: cv.display_color }}>
          {Math.round(cv.proficiency * 100)}%
        </span>
      </div>
      <div className="h-1.5 bg-page rounded-full overflow-hidden border border">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${cv.proficiency * 100}%`, background: cv.display_color }}
        />
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-page p-2 rounded-lg border border">
          <div className="text-muted text-[10px]">紧迫度</div>
          <div className="font-medium">{Math.round(cv.urgency * 100)}%</div>
        </div>
        <div className="bg-page p-2 rounded-lg border border">
          <div className="text-muted text-[10px]">不确定性</div>
          <div className="font-medium">{Math.round(cv.uncertainty * 100)}%</div>
        </div>
        <div className="bg-page p-2 rounded-lg border border">
          <div className="text-muted text-[10px]">停滞天数</div>
          <div className="font-medium">{cv.stagnation_days} 天</div>
        </div>
        <div className="bg-page p-2 rounded-lg border border">
          <div className="text-muted text-[10px]">下次行动</div>
          <div className="font-medium">{cv.next_action_type}</div>
        </div>
      </div>
      {cv.display_glow && (
        <div className="text-[10px] text-amber-400 bg-amber-400/10 px-2 py-1.5 rounded-lg border border-amber-400/20">
          ⚠️ 不确定性较高，建议复习
        </div>
      )}
    </div>
  );
}

function SourceRefItem({ ref }: { ref: SourceRef }) {
  return (
    <div className="flex items-center gap-2 text-xs px-2 py-1.5 rounded-lg bg-page border border hover:border-accent/30">
      <LinkIcon size={10} className="text-muted" />
      <span className="capitalize text-muted">{ref.module}</span>
      <span className="truncate font-mono">{ref.id.slice(-8)}</span>
    </div>
  );
}

export default function TreeNodeDetailPanel({
  node, onClose, onDelete, onLinkCognitive,
}: TreeNodeDetailPanelProps) {
  const cv = node.cognitive_view;
  const [activeTab, setActiveTab] = useState<"cognitive" | "materials">("cognitive");

  return (
    <div className="h-full flex flex-col bg-surface border-l border">
      <div className="flex items-center justify-between px-4 py-3 border-b border">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-lg">{node.emoji || "📄"}</span>
          <div className="min-w-0">
            <div className="text-sm font-semibold text truncate">{node.label}</div>
            <div className="text-[10px] text-muted uppercase tracking-wide">{node.node_type}</div>
          </div>
        </div>
        <button onClick={onClose} className="p-1 rounded-md hover:bg-surface-hover">
          <X size={14} className="text-muted" />
        </button>
      </div>

      <div className="flex border-b border">
        {[
          { id: "cognitive" as const, label: "认知视图", icon: Brain },
          { id: "materials" as const, label: "材料聚合", icon: Layers },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[11px] font-medium transition-colors ${
              activeTab === tab.id ? "text-accent bg-accent/5 border-b-2 border-accent" : "text-muted hover:text"
            }`}
          >
            <tab.icon size={12} /> {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {node.brief && (
          <div className="text-xs text-muted leading-relaxed bg-page p-3 rounded-lg border border">
            {node.brief}
          </div>
        )}

        {activeTab === "cognitive" && (
          <div className="space-y-3">
            <div className="text-[10px] font-medium text-muted uppercase tracking-wide">关联认知节点</div>
            {cv ? (
              <CognitiveViewCard cv={cv} />
            ) : (
              <div className="text-xs text-muted bg-page p-4 rounded-lg border border text-center">
                未关联认知节点
              </div>
            )}
            <button
              onClick={onLinkCognitive}
              className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs bg-accent text-white rounded-lg hover:opacity-90"
            >
              <Brain size={12} /> {cv ? "切换认知节点" : "关联认知节点"}
            </button>
          </div>
        )}

        {activeTab === "materials" && (
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="text-[10px] font-medium text-muted uppercase tracking-wide">来源引用</div>
              {node.source_refs && node.source_refs.length > 0 ? (
                <div className="space-y-1.5">
                  {node.source_refs.map((ref, idx) => (
                    <SourceRefItem key={`${ref.module}-${ref.id}-${idx}`} ref={ref} />
                  ))}
                </div>
              ) : (
                <div className="text-xs text-muted">暂无来源引用</div>
              )}
            </div>

            <div className="space-y-2">
              <div className="text-[10px] font-medium text-muted uppercase tracking-wide">跨壳材料（预留）</div>
              <div className="grid grid-cols-2 gap-2">
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-page border border opacity-50">
                  <BookOpen size={12} className="text-muted" />
                  <span className="text-xs text-muted">闪卡</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-page border border opacity-50">
                  <StickyNote size={12} className="text-muted" />
                  <span className="text-xs text-muted">笔记</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-page border border opacity-50">
                  <Layers size={12} className="text-muted" />
                  <span className="text-xs text-muted">错题</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-page border border opacity-50">
                  <Calendar size={12} className="text-muted" />
                  <span className="text-xs text-muted">计划</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="p-3 border-t border">
        <button
          onClick={onDelete}
          className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs border border-danger text-danger rounded-lg hover:bg-danger/10"
        >
          <Trash2 size={12} /> 删除节点
        </button>
      </div>
    </div>
  );
}
