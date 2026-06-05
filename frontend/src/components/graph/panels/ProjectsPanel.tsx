"use client";

import React, { useState, useEffect } from "react";
import {
  Rocket,
  Loader2,
  Sparkles,
  CheckCircle,
  Clock,
  BarChart3,
  Target,
  X,
} from "lucide-react";
import { listProjects, generateProject } from "@/lib/api/learning-api";
import type { Project } from "@/lib/api/learning-api";

interface ProjectsPanelProps {
  open: boolean;
  selectedNodeId?: string;
  selectedNodeLabel?: string;
  onClose: () => void;
}

/**
 * 探索项目面板（10.6）
 * 查看和生成基于知识点的项目式学习任务。
 */
export default function ProjectsPanel({
  open,
  selectedNodeId,
  selectedNodeLabel,
  onClose,
}: ProjectsPanelProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    listProjects()
      .then(setProjects)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  const handleGenerate = async () => {
    if (!selectedNodeId) return;
    setGenerating(true);
    setMessage("");
    try {
      const result = await generateProject({
        node_ids: [selectedNodeId],
        title_hint: selectedNodeLabel ? `${selectedNodeLabel} 实践项目` : undefined,
      });
      if (result.projects.length > 0) {
        setProjects((prev) => [...result.projects.map((p: any) => ({
          ...p,
          node_ids: [p.node_id || selectedNodeId],
          prerequisites: [],
          deliverables: [],
          difficulty: 0.5,
          estimated_hours: 2,
          source: "system",
          created_at: new Date().toISOString(),
          goal: "",
          user_id: "",
          status: "suggested",
          description: p.description || "",
        })), ...prev]);
        setMessage(`✅ 已生成项目：「${result.projects[0].title}」`);
      }
    } catch (e: any) {
      setMessage(`❌ 生成失败: ${e.message}`);
    } finally {
      setGenerating(false);
    }
  };

  const statusLabels: Record<string, { label: string; color: string }> = {
    suggested: { label: "待开始", color: "var(--color-accent)" },
    active: { label: "进行中", color: "var(--color-info)" },
    in_progress: { label: "进行中", color: "var(--color-info)" },
    completed: { label: "已完成", color: "var(--color-success)" },
    archived: { label: "已归档", color: "var(--color-text-muted)" },
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="w-full max-w-lg mx-4 max-h-[80vh] flex flex-col bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl shadow-xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[var(--color-accent)]/10 flex items-center justify-center text-[var(--color-accent)]">
              <Rocket size={16} />
            </div>
            <div>
              <span className="text-sm font-semibold">探索项目</span>
              <p className="text-[10px] text-[var(--color-text-muted)]">
                基于知识点生成动手实践任务
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]"
          >
            <X size={14} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {/* Message */}
          {message && (
            <div className="p-2.5 rounded-lg text-xs bg-[var(--color-accent)]/5 border border-[var(--color-accent])/20">
              {message}
            </div>
          )}

          {/* Generate button */}
          {selectedNodeId && (
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-xs font-medium bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-40 transition-opacity"
            >
              {generating ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Sparkles size={14} />
              )}
              {generating
                ? "生成中..."
                : selectedNodeLabel
                  ? `基于「${selectedNodeLabel}」生成项目`
                  : "生成探索项目"}
            </button>
          )}

          {/* Project list */}
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={18} className="animate-spin text-[var(--color-text-muted)]" />
            </div>
          ) : projects.length === 0 ? (
            <div className="flex flex-col items-center py-8 text-center">
              <div className="w-12 h-12 rounded-full bg-[var(--color-surface-hover)] flex items-center justify-center mb-3">
                <Rocket size={20} className="text-[var(--color-text-muted)]" />
              </div>
              <p className="text-xs text-[var(--color-text-muted)]">
                还没有探索项目
              </p>
              <p className="text-[10px] text-[var(--color-text-muted)] mt-1 opacity-60">
                选择一个知识点，点击上方按钮生成
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {projects.map((project) => {
                const st = statusLabels[project.status] || statusLabels.suggested;
                return (
                  <div
                    key={project.id}
                    className="p-3 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] hover:border-[var(--color-accent)]/30 transition-all"
                  >
                    {/* Title + status */}
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-sm font-medium text-[var(--color-text)]">
                        {project.title}
                      </span>
                      <span
                        className="text-[9px] px-1.5 py-0.5 rounded-full flex-shrink-0"
                        style={{
                          backgroundColor: `${st.color}15`,
                          color: st.color,
                        }}
                      >
                        {st.label}
                      </span>
                    </div>

                    {/* Description */}
                    {project.description && (
                      <p className="text-[11px] text-[var(--color-text-muted)] mt-1 line-clamp-2">
                        {project.description}
                      </p>
                    )}

                    {/* Goal */}
                    {project.goal && (
                      <p className="text-[10px] text-[var(--color-text)] italic mt-1 line-clamp-1">
                        🎯 {project.goal}
                      </p>
                    )}

                    {/* Metadata */}
                    <div className="flex items-center gap-3 mt-2 text-[10px] text-[var(--color-text-muted)]">
                      {project.difficulty > 0 && (
                        <span className="flex items-center gap-0.5">
                          <BarChart3 size={10} />
                          {project.difficulty <= 0.3
                            ? "简单"
                            : project.difficulty <= 0.6
                              ? "中等"
                              : "困难"}
                        </span>
                      )}
                      {project.estimated_hours > 0 && (
                        <span className="flex items-center gap-0.5">
                          <Clock size={10} />
                          ~{project.estimated_hours}小时
                        </span>
                      )}
                      {project.node_ids.length > 0 && (
                        <span className="flex items-center gap-0.5">
                          <Target size={10} />
                          {project.node_ids.length}个知识点
                        </span>
                      )}
                    </div>

                    {/* Deliverables */}
                    {project.deliverables && project.deliverables.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {project.deliverables.map((d, i) => (
                          <span
                            key={i}
                            className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]"
                          >
                            {d}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Count */}
              <p className="text-[10px] text-[var(--color-text-muted)] text-center pt-1">
                共 {projects.length} 个项目
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
