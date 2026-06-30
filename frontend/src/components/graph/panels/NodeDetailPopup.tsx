"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import type { GraphNode } from "@/lib/types/graph-types";
import { getMasteryColor } from "@/lib/types/graph-types";

interface NodeDetailPopupProps {
  node: GraphNode;
  /** 节点在画布中的位置 (SVG 坐标，对应卡片左上角) */
  nodePosition: { x: number; y: number };
  onClose: () => void;
}

// ── 等级标签 ──
const LEVEL_LABELS: Record<string, string> = {
  domain: "领域",
  topic: "专题",
  concept: "概念",
  atom: "原子",
};

const LEVEL_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  domain: { bg: "rgba(99,102,241,0.12)", text: "rgba(165,180,252,0.9)", border: "rgba(99,102,241,0.3)" },
  topic: { bg: "rgba(34,197,94,0.1)", text: "rgba(134,239,172,0.9)", border: "rgba(34,197,94,0.25)" },
  concept: { bg: "rgba(234,179,8,0.1)", text: "rgba(253,224,71,0.9)", border: "rgba(234,179,8,0.25)" },
  atom: { bg: "rgba(239,68,68,0.08)", text: "rgba(252,165,165,0.9)", border: "rgba(239,68,68,0.2)" },
};

const CARD_W = 175;
const CARD_H = 118;
const POPUP_W = 180;
const GAP = 8;

// 持久化收起状态
const COLLAPSED_KEY = "kt-popup-collapsed";

function loadCollapsed(): Set<string> {
  try {
    const raw = localStorage.getItem(COLLAPSED_KEY);
    if (raw) return new Set(JSON.parse(raw));
  } catch {}
  return new Set();
}

function saveCollapsed(set: Set<string>) {
  try {
    localStorage.setItem(COLLAPSED_KEY, JSON.stringify(Array.from(set)));
  } catch {}
}

export default function NodeDetailPopup({
  node, nodePosition, onClose,
}: NodeDetailPopupProps) {
  const [collapsed, setCollapsed] = useState(() => loadCollapsed().has(node.id));
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const mColor = getMasteryColor(node.mastery);
  const levelLabel = LEVEL_LABELS[node.level] || node.level;
  const levelStyle = LEVEL_STYLES[node.level] || LEVEL_STYLES.topic;

  // 节点切换时重置状态
  useEffect(() => {
    setCollapsed(loadCollapsed().has(node.id));
    setDismissed(false);
    const timer = requestAnimationFrame(() => {
      setVisible(true);
    });
    return () => cancelAnimationFrame(timer);
  }, [node.id]);

  const toggleCollapse = useCallback(() => {
    setCollapsed(prev => {
      const next = !prev;
      const set = loadCollapsed();
      if (next) set.add(node.id);
      else set.delete(node.id);
      saveCollapsed(set);
      return next;
    });
  }, [node.id]);

  // 弹出位置: 节点右侧
  const popupX = nodePosition.x + CARD_W + GAP;
  const popupY = nodePosition.y;

  // 收起状态 — 显示迷你指示器
  if (collapsed || dismissed) {
    return (
      <div
        className="absolute pointer-events-auto"
        style={{
          left: nodePosition.x + CARD_W + 4,
          top: nodePosition.y + CARD_H / 2 - 12,
          opacity: visible ? 1 : 0,
          transform: visible ? "scale(1)" : "scale(0.8)",
          transition: "opacity 0.2s ease-out, transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)",
          zIndex: 30,
        }}
      >
        <button
          onClick={dismissed ? onClose : toggleCollapse}
          className="flex items-center gap-1 px-2 py-1.5 rounded-full text-[10px] font-medium
            transition-all duration-200 hover:scale-110"
          style={{
            background: `linear-gradient(135deg, ${mColor}20, ${mColor}08)`,
            border: `1px solid ${mColor}30`,
            color: mColor,
            boxShadow: `0 0 12px ${mColor}15`,
          }}
          title={dismissed ? "重新打开" : "展开详情"}
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v8M8 12h8" />
          </svg>
          {node.label.slice(0, 6)}
        </button>
      </div>
    );
  }

  return (
    <div
      className="absolute pointer-events-auto"
      style={{
        left: popupX,
        top: popupY,
        width: POPUP_W,
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(-6px)",
        transition: "opacity 0.2s ease-out, transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)",
        zIndex: 30,
      }}
    >
      <div
        className="overflow-hidden rounded-xl"
        style={{
          background: "linear-gradient(135deg, rgba(15,15,22,0.92) 0%, rgba(22,22,32,0.88) 100%)",
          backdropFilter: "blur(24px) saturate(180%)",
          WebkitBackdropFilter: "blur(24px) saturate(180%)",
          border: `1px solid ${mColor}20`,
          boxShadow: `
            0 8px 32px rgba(0,0,0,0.4),
            0 0 40px ${mColor}12,
            inset 0 1px 0 rgba(255,255,255,0.04)
          `,
        }}
      >
        {/* ── 头部 ── */}
        <div className="flex items-center justify-between px-3 pt-3 pb-2">
          <div className="flex items-center gap-2 min-w-0">
            <div
              className="w-2 h-2 rounded-full shrink-0"
              style={{
                background: `radial-gradient(circle, ${mColor}, ${mColor}60)`,
                boxShadow: `0 0 6px ${mColor}60`,
              }}
            />
            <span className="text-[11px] font-semibold text-white/90 truncate">
              {node.label}
            </span>
          </div>
          <div className="flex items-center gap-1 shrink-0 ml-2">
            <button
              onClick={toggleCollapse}
              className="p-0.5 rounded hover:bg-white/5 transition-colors"
              title="收起"
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-white/30">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
            <button
              onClick={() => { setDismissed(true); }}
              className="p-0.5 rounded hover:bg-white/5 transition-colors"
              title="关闭"
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-white/30">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* ── 掌握度环形仪表 ── */}
        <div className="flex items-center gap-3 px-3 pb-2">
          <div className="relative shrink-0">
            <svg width="36" height="36" viewBox="0 0 36 36">
              <circle cx="18" cy="18" r="14" fill="none" stroke="white" strokeOpacity="0.06" strokeWidth="3" />
              <circle
                cx="18" cy="18" r="14"
                fill="none"
                stroke={mColor}
                strokeWidth="3"
                strokeLinecap="round"
                strokeDasharray={`${Math.round(node.mastery * 88)} 88`}
                transform="rotate(-90 18 18)"
                style={{ filter: `drop-shadow(0 0 4px ${mColor}60)` }}
              />
              <text x="18" y="20" textAnchor="middle" fontSize="8" fill="white" fontWeight="700" fontFamily="monospace">
                {Math.round(node.mastery * 100)}
              </text>
            </svg>
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-[8px] px-1.5 py-0.5 rounded font-medium"
                style={{
                  background: levelStyle.bg,
                  color: levelStyle.text,
                  border: `1px solid ${levelStyle.border}`,
                }}
              >
                {levelLabel}
              </span>
              {node.created_by === "ai" && (
                <span className="text-[7px] px-1 py-0.5 rounded bg-white/[0.04] text-white/25">
                  AI
                </span>
              )}
            </div>
            <span className="text-[9px] text-white/35" style={{ color: mColor }}>
              {node.mastery >= 0.8 ? "已掌握" : node.mastery >= 0.3 ? "学习中" : node.mastery > 0 ? "初学" : "未接触"}
            </span>
          </div>
        </div>

        {/* ── 简介 ── */}
        {(node.brief || node.description) && (
          <div className="px-3 pb-2">
            <p className="text-[9px] text-white/40 leading-relaxed line-clamp-3 pl-2 border-l border-white/[0.06]">
              {node.brief || node.description}
            </p>
          </div>
        )}

        {/* ── 标签 ── */}
        {node.tags && node.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 px-3 pb-2">
            {node.tags.slice(0, 4).map((tag) => (
              <span key={tag} className="text-[7px] px-1.5 py-[2px] rounded-full bg-white/[0.04] text-white/25 border border-white/[0.04]">
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* ── 底部信息栏 ── */}
        <div className="flex items-center justify-between px-3 py-1.5 border-t border-white/[0.04]">
          <span className="text-[8px] text-white/20">
            {node.created_by === "ai" ? "AI 生成" : "手动创建"}
          </span>
          {node.conv_ids && node.conv_ids.length > 0 && (
            <span className="text-[8px] text-white/25">
              {node.conv_ids.length} 会话
            </span>
          )}
        </div>

        {/* ── 全息扫描线装饰 ── */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden rounded-xl">
          <div
            className="absolute left-0 right-0 h-[1px] opacity-20"
            style={{
              background: `linear-gradient(90deg, transparent, ${mColor}, transparent)`,
              animation: "kt-scan 3s ease-in-out infinite",
            }}
          />
        </div>
      </div>
    </div>
  );
}