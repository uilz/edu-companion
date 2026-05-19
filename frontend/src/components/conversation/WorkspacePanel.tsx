"use client";

import { useState, useEffect, useCallback } from "react";
import {
  FolderOpen,
  Upload,
  Trash2,
  Image,
  FileText,
  Music,
  Video,
  Loader2,
  ChevronRight,
  ChevronDown,
  Link,
  X,
} from "lucide-react";
import MaterialPicker from "@/components/materials/MaterialPicker";
import type { MaterialRef } from "@/types";

// ── Types ──
export interface WorkspaceFile {
  id: string;
  original_name: string;
  file_type: string;
  mime_type: string;
  file_size: number;
  processing_status: string;
  created_at: number;
}

interface WorkspacePanelProps {
  branchId: string | null;
  partitionId?: string | null;
  onFileClick?: (file: WorkspaceFile) => void;
}

// ── Helpers ──
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function fileIcon(fileType: string) {
  switch (fileType) {
    case "image": return <Image size={14} />;
    case "audio": return <Music size={14} />;
    case "video": return <Video size={14} />;
    default: return <FileText size={14} />;
  }
}

// ── Component ──
export default function WorkspacePanel({
  branchId,
  partitionId,
  onFileClick,
}: WorkspacePanelProps) {
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [materialRefs, setMaterialRefs] = useState<MaterialRef[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const [showPicker, setShowPicker] = useState(false);

  // ── Load files + refs ──
  const loadData = useCallback(async () => {
    if (!branchId) {
      setFiles([]);
      setMaterialRefs([]);
      return;
    }
    setLoading(true);
    setError("");
    try {
      // Load workspace files
      const fileRes = await fetch(
        `/api/conversations/workspace/files?branch_id=${encodeURIComponent(branchId)}`
      );
      if (fileRes.ok) {
        const data = await fileRes.json();
        setFiles(data.files || []);
      }

      // Load material refs
      const refRes = await fetch(
        `/api/conversations/branches/${encodeURIComponent(branchId)}/materials`
      );
      if (refRes.ok) {
        const data = await refRes.json();
        setMaterialRefs(data.refs || []);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [branchId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ── Upload ──
  const handleUpload = useCallback(
    async (file: File) => {
      if (!branchId) return;
      setUploading(true);
      setError("");
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("branch_id", branchId);
        const res = await fetch("/api/conversations/workspace/upload", {
          method: "POST",
          body: formData,
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "上传失败");
        }
        await loadData();
      } catch (e) {
        setError(e instanceof Error ? e.message : "上传失败");
      } finally {
        setUploading(false);
      }
    },
    [branchId, loadData]
  );

  // ── Delete ──
  const handleDelete = useCallback(
    async (fileId: string) => {
      if (!branchId) return;
      try {
        const res = await fetch(
          `/api/conversations/workspace/files/${fileId}?branch_id=${encodeURIComponent(branchId)}`,
          { method: "DELETE" }
        );
        if (!res.ok) throw new Error("删除失败");
        setFiles((prev) => prev.filter((f) => f.id !== fileId));
      } catch (e) {
        setError(e instanceof Error ? e.message : "删除失败");
      }
    },
    [branchId]
  );

  // ── Remove ref ──
  const handleRemoveRef = useCallback(
    async (materialId: string) => {
      if (!branchId) return;
      try {
        const res = await fetch(
          `/api/conversations/branches/${encodeURIComponent(branchId)}/materials/${encodeURIComponent(materialId)}`,
          { method: "DELETE" }
        );
        if (!res.ok) throw new Error("取消引用失败");
        setMaterialRefs((prev) => prev.filter((r) => r.material_id !== materialId));
      } catch (e) {
        setError(e instanceof Error ? e.message : "取消引用失败");
      }
    },
    [branchId]
  );

  // ── Confirm refs from picker ──
  const handleConfirmRefs = useCallback(
    async (ids: string[]) => {
      if (!branchId) return;
      setShowPicker(false);
      try {
        const res = await fetch(
          `/api/conversations/branches/${encodeURIComponent(branchId)}/materials/batch`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(ids.map((material_id) => ({ material_id }))),
          }
        );
        if (!res.ok) throw new Error("设置引用失败");
        await loadData();
      } catch (e) {
        setError(e instanceof Error ? e.message : "设置引用失败");
      }
    },
    [branchId, loadData]
  );

  // ── Empty state ──
  if (!branchId) {
    return (
      <div className="px-3 py-4 text-xs text-[var(--color-text-muted)]">
        选择分支查看工作空间
      </div>
    );
  }

  const currentPartitionId = partitionId || "";

  return (
    <>
      <div className="border-t border-[var(--color-border)]">
        {/* Header */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] transition-colors"
        >
          {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
          <FolderOpen size={13} />
          <span>工作空间</span>
          {(files.length > 0 || materialRefs.length > 0) && (
            <span className="text-[10px] text-[var(--color-text-muted)] ml-auto">
              {files.length + materialRefs.length}
            </span>
          )}
        </button>

        {!collapsed && (
          <div className="px-2 pb-2">
            {/* Action buttons */}
            <div className="flex items-center gap-1 mb-1">
              <label className="flex items-center gap-1 px-2 py-1 text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] cursor-pointer transition-colors">
                {uploading ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <Upload size={12} />
                )}
                <span>{uploading ? "上传中" : "上传"}</span>
                <input
                  type="file"
                  accept="image/*,audio/*,video/*,.pdf,.docx,.pptx,.md,.txt"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleUpload(f);
                    e.target.value = "";
                  }}
                  className="hidden"
                />
              </label>

              {/* P5: 引用资料 */}
              <button
                onClick={() => setShowPicker(true)}
                className="flex items-center gap-1 px-2 py-1 text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors"
                title="引用本分区资料"
              >
                <Link size={12} />
                <span>引用</span>
              </button>
            </div>

            {/* Error */}
            {error && (
              <div className="px-2 py-1 text-[10px] text-red-400">{error}</div>
            )}

            {/* Loading */}
            {loading && (
              <div className="flex items-center gap-1.5 px-2 py-2 text-[11px] text-[var(--color-text-muted)]">
                <Loader2 size={12} className="animate-spin" />
                加载中...
              </div>
            )}

            {/* Empty */}
            {!loading && files.length === 0 && materialRefs.length === 0 && (
              <div className="px-2 py-3 text-[11px] text-[var(--color-text-muted)] text-center">
                暂无文件
                <br />
                <span className="text-[10px]">上传或引用资料</span>
              </div>
            )}

            {/* Workspace files */}
            {files.length > 0 && (
              <>
                <div className="px-2 py-0.5 text-[10px] font-medium text-[var(--color-text-muted)]">
                  📁 本分支文件
                </div>
                {files.map((file) => (
                  <div
                    key={file.id}
                    className="group flex items-center gap-1.5 px-2 py-1.5 text-[11px] hover:bg-[var(--color-surface)] transition-colors"
                  >
                    <button
                      onClick={() => onFileClick?.(file)}
                      className="flex items-center gap-1.5 flex-1 min-w-0 text-left"
                      title={file.original_name}
                    >
                      <span className="text-[var(--color-text-muted)] flex-shrink-0">
                        {fileIcon(file.file_type)}
                      </span>
                      <span className="truncate text-[var(--color-text-secondary)]">
                        {file.original_name}
                      </span>
                    </button>
                    <span className="text-[10px] text-[var(--color-text-muted)] flex-shrink-0">
                      {formatSize(file.file_size)}
                    </span>
                    <button
                      onClick={() => handleDelete(file.id)}
                      className="opacity-0 group-hover:opacity-100 p-0.5 text-[var(--color-text-muted)] hover:text-red-400 transition-all flex-shrink-0"
                      title="删除"
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                ))}
              </>
            )}

            {/* Material refs */}
            {materialRefs.length > 0 && (
              <>
                <div className="px-2 py-0.5 mt-1 text-[10px] font-medium text-[var(--color-text-muted)]">
                  📎 已引用资料
                </div>
                {materialRefs.map((ref) => (
                  <div
                    key={ref.material_id}
                    className="group flex items-center gap-1.5 px-2 py-1 text-[11px] hover:bg-[var(--color-surface)] transition-colors"
                  >
                    <span className="text-[var(--color-text-muted)] flex-shrink-0">
                      <FileText size={12} />
                    </span>
                    <span className="truncate flex-1 text-[var(--color-text-secondary)]">
                      {ref.file_name}
                    </span>
                    <button
                      onClick={() => handleRemoveRef(ref.material_id)}
                      className="opacity-0 group-hover:opacity-100 p-0.5 text-[var(--color-text-muted)] hover:text-red-400 transition-all flex-shrink-0"
                      title="取消引用"
                    >
                      <X size={11} />
                    </button>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {/* MaterialPicker modal */}
      {showPicker && (
        <MaterialPicker
          partitionId={currentPartitionId}
          selectedIds={materialRefs.map((r) => r.material_id)}
          onConfirm={handleConfirmRefs}
          onClose={() => setShowPicker(false)}
        />
      )}
    </>
  );
}
