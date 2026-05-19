"use client";

import { useState, useEffect, useCallback } from "react";
import {
  FileText,
  Search,
  Upload,
  Trash2,
  Loader2,
  BookOpen,
  X,
  ChevronRight,
  File,
  CheckCircle2,
} from "lucide-react";
import type { MaterialMeta } from "@/types";

interface MaterialPanelProps {
  partitionId: string;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function fileIcon(fileType: string) {
  if (fileType === "pdf") return <FileText size={14} className="text-red-400" />;
  if (fileType === "docx") return <FileText size={14} className="text-blue-400" />;
  if (fileType === "pptx") return <FileText size={14} className="text-orange-400" />;
  return <File size={14} />;
}

export default function MaterialPanel({ partitionId }: MaterialPanelProps) {
  const [materials, setMaterials] = useState<MaterialMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [error, setError] = useState("");

  // ── Load ──
  const loadMaterials = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const url = new URL("/api/materials", window.location.origin);
      if (partitionId) url.searchParams.set("partition_id", partitionId);
      if (searchQuery) url.searchParams.set("search", searchQuery);

      const res = await fetch(url.toString());
      if (!res.ok) throw new Error("加载失败");
      const data = await res.json();
      setMaterials(data.materials || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [partitionId, searchQuery]);

  useEffect(() => {
    loadMaterials();
  }, [loadMaterials]);

  // ── Upload ──
  const handleUpload = useCallback(
    async (file: File) => {
      setUploading(true);
      setError("");
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("partition_id", partitionId);
        const res = await fetch("/api/materials/upload", {
          method: "POST",
          body: formData,
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "上传失败");
        }
        await loadMaterials();
      } catch (e) {
        setError(e instanceof Error ? e.message : "上传失败");
      } finally {
        setUploading(false);
      }
    },
    [partitionId, loadMaterials]
  );

  // ── Delete ──
  const handleDelete = useCallback(
    async (materialId: string) => {
      try {
        const res = await fetch(`/api/materials/${materialId}`, {
          method: "DELETE",
        });
        if (!res.ok) throw new Error("删除失败");
        setMaterials((prev) => prev.filter((m) => m.material_id !== materialId));
      } catch (e) {
        setError(e instanceof Error ? e.message : "删除失败");
      }
    },
    []
  );

  // ── Promote ──
  const handlePromote = useCallback(
    async (materialId: string) => {
      try {
        const res = await fetch(`/api/materials/${materialId}/promote`, {
          method: "POST",
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "转为知识库失败");
        }
        await loadMaterials();
      } catch (e) {
        setError(e instanceof Error ? e.message : "转为知识库失败");
      }
    },
    [loadMaterials]
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2">
          <BookOpen size={16} className="text-[var(--color-accent)]" />
          <span className="text-sm font-semibold text-[var(--color-text)]">
            资料
          </span>
          {materials.length > 0 && (
            <span className="text-xs text-[var(--color-text-muted)]">
              ({materials.length})
            </span>
          )}
        </div>
        <label className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] cursor-pointer transition-colors">
          {uploading ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Upload size={16} />
          )}
          <input
            type="file"
            accept=".pdf,.docx,.pptx,.md,.txt,.mp3,.wav,.m4a,.jpg,.jpeg,.png,.webp"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleUpload(f);
              e.target.value = "";
            }}
            className="hidden"
          />
        </label>
      </div>

      {/* Search */}
      <div className="px-3 py-2">
        <div className="flex items-center gap-1.5 px-2 py-1.5 text-xs bg-[var(--color-surface)] border border-[var(--color-border)]">
          <Search size={13} className="text-[var(--color-text-muted)]" />
          <input
            type="text"
            placeholder="搜索资料..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent border-none outline-none flex-1 text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]"
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery("")}>
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="px-3 py-1.5 text-xs text-red-400">{error}</div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="px-4 py-8 text-center">
            <Loader2 size={16} className="animate-spin mx-auto mb-2 text-[var(--color-text-muted)]" />
            <div className="text-xs text-[var(--color-text-muted)]">加载中...</div>
          </div>
        ) : materials.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <BookOpen size={20} className="text-[var(--color-text-muted)] mx-auto mb-2" />
            <div className="text-xs text-[var(--color-text-muted)]">暂无资料</div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1 opacity-60">
              上传讲义或学习材料
            </div>
          </div>
        ) : (
          <div className="space-y-0.5 px-2 pb-4">
            {materials.map((mat) => {
              const isExpanded = expandedId === mat.material_id;
              return (
                <div key={mat.material_id} className="border border-[var(--color-border)]">
                  {/* Row */}
                  <button
                    onClick={() =>
                      setExpandedId(isExpanded ? null : mat.material_id)
                    }
                    className="w-full flex items-center gap-1.5 px-2 py-1.5 text-xs hover:bg-[var(--color-surface)] transition-colors text-left"
                  >
                    <ChevronRight
                      size={11}
                      className={`text-[var(--color-text-muted)] transition-transform flex-shrink-0 ${
                        isExpanded ? "rotate-90" : ""
                      }`}
                    />
                    {fileIcon(mat.file_type)}
                    <span className="truncate flex-1 text-[var(--color-text-secondary)]">
                      {mat.file_name}
                    </span>
                    <span className="text-[10px] text-[var(--color-text-muted)] flex-shrink-0">
                      {formatSize(mat.file_size)}
                    </span>
                    {mat.status === "ready" && (
                      <CheckCircle2 size={11} className="text-green-400 flex-shrink-0" />
                    )}
                  </button>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div className="px-3 py-2 border-t border-[var(--color-border)] bg-[var(--color-surface)]">
                      <div className="space-y-1.5 text-[11px] text-[var(--color-text-muted)]">
                        <div className="flex gap-2">
                          <span className="text-[var(--color-text-secondary)]">类型:</span>
                          <span>{mat.file_type}</span>
                        </div>
                        <div className="flex gap-2">
                          <span className="text-[var(--color-text-secondary)]">状态:</span>
                          <span
                            className={
                              mat.status === "ready"
                                ? "text-green-400"
                                : "text-yellow-400"
                            }
                          >
                            {mat.status === "ready" ? "已索引" : mat.status === "stored" ? "已存储" : mat.status}
                          </span>
                        </div>
                        {mat.skills_covered && mat.skills_covered.length > 0 && (
                          <div className="flex gap-2 flex-wrap">
                            <span className="text-[var(--color-text-secondary)]">知识点:</span>
                            {mat.skills_covered.map((s, i) => (
                              <span
                                key={i}
                                className="px-1 text-[10px] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                              >
                                {s}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Actions */}
                        <div className="flex gap-2 pt-1">
                          {mat.status === "stored" && (
                            <button
                              onClick={() => handlePromote(mat.material_id)}
                              className="px-2 py-0.5 text-[10px] text-[var(--color-accent)] hover:bg-[var(--color-accent)]/10 transition-colors"
                            >
                              转为知识库
                            </button>
                          )}
                          <button
                            onClick={() => handleDelete(mat.material_id)}
                            className="px-2 py-0.5 text-[10px] text-red-400 hover:bg-red-400/10 transition-colors"
                          >
                            删除
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
