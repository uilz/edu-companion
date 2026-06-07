"use client";

import React, { useState, useCallback } from "react";
import {
  X, Pencil, Trash2, Loader2, Sparkles, Check, Send,
  AlertCircle, MessageSquare, Brain, ChevronRight, Save,
} from "lucide-react";
import type { GraphNode } from "@/lib/types/graph-types";
import { getMasteryColor, getTrendIcon } from "@/lib/types/graph-types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface NodeDetailPanelProps {
  node: GraphNode;
  partitionId: string;
  onClose: () => void;
  onNodeUpdated: () => void;
  onStartPractice?: (nodeId: string) => void;
  onRequestExplain?: (nodeId: string) => void;
  parentNode?: GraphNode | null;
  onNavigateToParent?: (node: GraphNode) => void;
}

export default function NodeDetailPanel({
  node, partitionId, onClose, onNodeUpdated,
  onStartPractice, onRequestExplain,
  parentNode, onNavigateToParent,
}: NodeDetailPanelProps) {
  const [editing, setEditing] = useState(false);
  const [editLabel, setEditLabel] = useState(node.label);
  const [editDesc, setEditDesc] = useState(node.description || "");
  const [editTags, setEditTags] = useState(node.tags?.join(", ") || "");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // AI 扩充
  const [expanding, setExpanding] = useState(false);
  const [expandDepth, setExpandDepth] = useState(2);

  // AI 对话
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMsg, setChatMsg] = useState("");
  const [chatResp, setChatResp] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatConvId, setChatConvId] = useState("");

  const [error, setError] = useState("");

  // ── 保存编辑 ──
  const handleSave = useCallback(async () => {
    if (!editLabel.trim()) return;
    setSaving(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/graph/${partitionId}/node/${node.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: editLabel.trim(),
          description: editDesc.trim(),
          tags: editTags ? editTags.split(",").map(s => s.trim()).filter(Boolean) : [],
        }),
      });
      if (!res.ok) throw new Error("保存失败");
      setEditing(false);
      onNodeUpdated();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }, [editLabel, editDesc, editTags, partitionId, node.id, onNodeUpdated]);

  // ── 删除节点 ──
  const handleDelete = useCallback(async () => {
    if (!confirm(`确定删除「${node.label}」及其关联边？`)) return;
    setDeleting(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/graph/${partitionId}/node/${node.id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("删除失败");
      onClose();
      onNodeUpdated();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setDeleting(false);
    }
  }, [node, partitionId, onClose, onNodeUpdated]);

  // ── AI 扩充 ──
  const handleAiExpand = useCallback(async () => {
    setExpanding(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/graph/${partitionId}/ai-expand`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node_id: node.id, depth: expandDepth, direction: "children" }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "AI扩充失败");
      onNodeUpdated();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setExpanding(false);
    }
  }, [node.id, partitionId, expandDepth, onNodeUpdated]);

  // ── AI 对话编辑 ──
  const handleAiChat = useCallback(async () => {
    if (!chatMsg.trim()) return;
    setChatLoading(true);
    setError("");
    setChatResp("");
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/graph/${partitionId}/ai-chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          node_id: node.id,
          message: chatMsg,
          conversation_id: chatConvId || undefined,
        }),
      });
      const data = await res.json();
      // scope_mismatch: 提示切换到对应节点的探索会话
      if (data.error === "scope_mismatch") {
        setChatResp(
          `⚠️ ${data.message}\n\n👉 请点击「${data.bound_node_label}」节点，在它的详情面板中启动探索会话。`
        );
        setChatMsg("");
        setChatLoading(false);
        return;
      }
      setChatResp(data.response || "");
      if (data.conversation_id) setChatConvId(data.conversation_id);
      setChatMsg("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setChatLoading(false);
    }
  }, [chatMsg, node.id, partitionId, chatConvId]);

  const mColor = getMasteryColor(node.mastery);

  return (
    <div className="flex flex-col h-full overflow-hidden border-l border-[var(--color-border)] bg-[var(--color-surface)]">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2">
          {parentNode && onNavigateToParent && (
            <button
              onClick={() => onNavigateToParent(parentNode)}
              className="flex items-center gap-0.5 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors"
              title={`返回父节点: ${parentNode.label}`}
            >
              <ChevronRight size={12} className="rotate-180" />
              <span className="max-w-[80px] truncate">{parentNode.label}</span>
            </button>
          )}
          {!parentNode && <span className="text-xs font-medium text-[var(--color-text-muted)]">节点详情</span>}
        </div>
        <button onClick={onClose}
          className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]">
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="p-4 space-y-4">
          {/* Error */}
          {error && (
            <div className="flex items-center gap-1.5 p-2 rounded bg-red-500/10 text-red-500 text-[11px]">
              <AlertCircle size={12} />{error}
            </div>
          )}

          {editing ? (
            /* ═══ 编辑模式 ═══ */
            <div className="space-y-3">
              <input value={editLabel} onChange={e => setEditLabel(e.target.value)}
                placeholder="节点名称" autoFocus
                className="w-full px-3 py-2 text-xs rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] focus:outline-none focus:border-[var(--color-accent)]" />
              <textarea value={editDesc} onChange={e => setEditDesc(e.target.value)}
                placeholder="描述（可选）" rows={3}
                className="w-full px-3 py-2 text-xs rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] focus:outline-none focus:border-[var(--color-accent)] resize-none" />
              <input value={editTags} onChange={e => setEditTags(e.target.value)}
                placeholder="标签（逗号分隔）"
                className="w-full px-3 py-2 text-xs rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] focus:outline-none focus:border-[var(--color-accent)]" />
              <div className="flex items-center gap-2">
                <button onClick={handleSave} disabled={saving}
                  className="flex items-center gap-1 px-3 py-1.5 text-[11px] rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50">
                  {saving ? <Loader2 size={11} className="animate-spin" /> : <Save size={11} />}
                  保存
                </button>
                <button onClick={() => setEditing(false)}
                  className="px-3 py-1.5 text-[11px] rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-border-hover)]">
                  取消
                </button>
              </div>
            </div>
          ) : (
            /* ═══ 查看模式 ═══ */
            <>
              {/* 节点信息 */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: mColor }} />
                  <h3 className="text-sm font-semibold text-[var(--color-text)]">{node.label}</h3>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] ml-auto">{node.level}</span>
                </div>
                {node.description && (
                  <p className="text-[11px] text-[var(--color-text-secondary)] leading-relaxed">{node.description}</p>
                )}
                <div className="flex items-center gap-3 mt-2 text-[10px] text-[var(--color-text-muted)]">
                  <span>优先级: {"★".repeat(Math.min(node.priority, 5))}{"☆".repeat(Math.max(5 - node.priority, 0))}</span>
                  <span>来源: {node.created_by === "user" ? "手动" : "AI"}</span>
                </div>
                {node.tags && node.tags.length > 0 && (
                  <div className="flex items-center gap-1 mt-2 flex-wrap">
                    {node.tags.map(tag => (
                      <span key={tag} className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--color-accent)]/10 text-[var(--color-accent)]">{tag}</span>
                    ))}
                  </div>
                )}
              </div>

              {/* 掌握度 */}
              {node.mastery > 0 && (
                <div>
                  <div className="flex items-center justify-between text-[10px] text-[var(--color-text-muted)] mb-1">
                    <span>掌握度</span>
                    <span style={{ color: mColor }}>{Math.round(node.mastery * 100)}% {getTrendIcon(node.trend)}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-[var(--color-surface-hover)] overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{ width: `${node.mastery * 100}%`, backgroundColor: mColor }} />
                  </div>
                </div>
              )}

              {/* 关联会话 */}
              {node.conversation_ids && node.conversation_ids.length > 0 && (
                <div>
                  <span className="text-[10px] text-[var(--color-text-muted)]">关联 {node.conversation_ids.length} 个会话</span>
                  <div className="flex items-center gap-1 mt-1 flex-wrap">
                    {node.conversation_ids.slice(0, 5).map(cid => (
                      <span key={cid} className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] truncate max-w-[100px]">{cid.slice(0, 12)}…</span>
                    ))}
                  </div>
                </div>
              )}

              {/* 操作按钮 */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <button onClick={() => setEditing(true)}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-[10px] rounded-lg border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-colors">
                    <Pencil size={10} />编辑
                  </button>
                  <button onClick={handleDelete} disabled={deleting}
                    className="flex items-center gap-1 px-2.5 py-1.5 text-[10px] rounded-lg border border-[var(--color-border)] text-red-500 hover:border-red-500 transition-colors">
                    {deleting ? <Loader2 size={10} className="animate-spin" /> : <Trash2 size={10} />}
                    删除
                  </button>
                  {onRequestExplain && (
                    <button onClick={() => onRequestExplain(node.id)}
                      className="flex items-center gap-1 px-2.5 py-1.5 text-[10px] rounded-lg bg-[var(--color-accent)]/10 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 transition-colors">
                      <Brain size={10} />请求讲解
                    </button>
                  )}
                  {onStartPractice && (
                    <button onClick={() => onStartPractice(node.id)}
                      className="flex items-center gap-1 px-2.5 py-1.5 text-[10px] rounded-lg bg-[var(--color-accent)]/10 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 transition-colors">
                      <MessageSquare size={10} />开始练习
                    </button>
                  )}
                </div>
              </div>
            </>
          )}

          {/* ═══ AI 扩充 ═══ */}
          <div className="pt-3 border-t border-[var(--color-border)]">
            <span className="text-[10px] font-medium text-[var(--color-text-muted)]">AI 扩充</span>
            <div className="flex items-center gap-2 mt-2">
              <input type="number" value={expandDepth} onChange={e => setExpandDepth(Math.max(1, Math.min(5, Number(e.target.value))))}
                min={1} max={5} className="w-14 px-2 py-1 text-[11px] rounded border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)]" />
              <span className="text-[10px] text-[var(--color-text-muted)]">层深度</span>
              <button onClick={handleAiExpand} disabled={expanding}
                className="flex items-center gap-1 px-3 py-1.5 text-[11px] rounded-lg bg-[var(--color-accent)]/10 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 disabled:opacity-50 transition-colors">
                {expanding ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />}
                AI 扩充子节点
              </button>
            </div>
          </div>

          {/* ═══ AI 对话编辑 ═══ */}
          <div className="pt-3 border-t border-[var(--color-border)]">
            <button onClick={() => setChatOpen(!chatOpen)}
              className="flex items-center gap-1 text-[10px] font-medium text-[var(--color-accent)] hover:underline">
              <MessageSquare size={11} />
              与 AI 对话编辑知识树
              <ChevronRight size={11} className={`transition-transform ${chatOpen ? "rotate-90" : ""}`} />
            </button>

            {chatOpen && (
              <div className="mt-2 space-y-2">
                <div className="max-h-[200px] overflow-y-auto space-y-2">
                  {chatResp && (
                    <div className="p-2.5 rounded-lg bg-[var(--color-accent)]/5 border border-[var(--color-accent)]/10 text-[11px] text-[var(--color-text)] leading-relaxed">
                      {chatResp}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <input value={chatMsg} onChange={e => setChatMsg(e.target.value)}
                    placeholder="告诉AI你想怎样编辑这个节点..."
                    className="flex-1 px-3 py-1.5 text-[11px] rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] focus:outline-none focus:border-[var(--color-accent)]"
                    onKeyDown={e => e.key === "Enter" && handleAiChat()} />
                  <button onClick={handleAiChat} disabled={chatLoading || !chatMsg.trim()}
                    className="p-1.5 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50">
                    {chatLoading ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* 子节点提示 */}
          {node.children && node.children.length > 0 && (
            <div className="pt-3 border-t border-[var(--color-border)]">
              <span className="text-[10px] font-medium text-[var(--color-text-muted)]">子节点 ({node.children.length})</span>
              <div className="mt-1 space-y-1">
                {node.children.map(cid => (
                  <div key={cid} className="flex items-center gap-1.5 px-2 py-1 rounded text-[10px] text-[var(--color-text-secondary)] bg-[var(--color-surface-hover)]">
                    <ChevronRight size={8} />{cid.slice(0, 24)}…
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
