"use client";

import { useState, useEffect, useCallback } from "react";
import { Search, Check, X, FileText, Image, File, Loader2, Library } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface FileItem {
  material_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  status: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSelect: (files: { name: string; type: "image" | "file"; materialId: string }[]) => void;
  selectedIds?: Set<string>;
}

function getIcon(ext: string) {
  if (["jpg", "jpeg", "png", "gif", "webp", "bmp"].includes(ext)) return <Image size={16} className="text-blue-500" />;
  if (ext === "pdf") return <FileText size={16} className="text-red-500" />;
  if (["docx", "pptx", "xlsx", "csv"].includes(ext)) return <FileText size={16} className="text-[var(--color-accent)]" />;
  return <File size={16} className="text-[var(--color-text-muted)]" />;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

export default function ResourcePicker({ open, onClose, onSelect, selectedIds: initialSelectedIds }: Props) {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(initialSelectedIds ?? new Set());

  // 同步外部选中状态
  useEffect(() => {
    if (initialSelectedIds) setSelectedIds(initialSelectedIds);
  }, [initialSelectedIds]);

  // 加载文件列表
  const fetchFiles = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: "1", page_size: "50" });
      if (search) params.set("search", search);
      const res = await fetch(`${API_BASE}/api/files?${params}`);
      const data = await res.json();
      setFiles((data.items || []).filter((f: FileItem) => f.status === "indexed"));
    } catch (e) {
      console.error("加载文件失败:", e);
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    if (open) fetchFiles();
  }, [open, fetchFiles]);

  const toggleFile = (materialId: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(materialId)) next.delete(materialId);
      else next.add(materialId);
      return next;
    });
  };

  const handleConfirm = () => {
    const selected = files
      .filter(f => selectedIds.has(f.material_id))
      .map(f => ({
        name: f.file_name,
        type: (["jpg", "jpeg", "png", "gif", "webp", "bmp"].includes(f.file_type?.toLowerCase() || "")
          ? "image" : "file") as "image" | "file",
        materialId: f.material_id,
      }));
    onSelect(selected);
    onClose();
  };

  if (!open) return null;

  const ext = (f: FileItem) => f.file_type?.toLowerCase() || "";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-2xl shadow-2xl w-[480px] max-h-[70vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]/50">
          <div className="flex items-center gap-2">
            <Library size={18} className="text-violet-500" />
            <span className="text-sm font-semibold text-[var(--color-text)]">引用我的资源</span>
          </div>
          <button onClick={onClose} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)] rounded">
            <X size={18} />
          </button>
        </div>

        {/* Search */}
        <div className="px-5 py-3">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索已索引的资料..."
              className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-input)] focus:outline-none focus:border-[var(--color-accent)]"
            />
          </div>
        </div>

        {/* File list */}
        <div className="flex-1 overflow-y-auto px-1">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={18} className="animate-spin text-[var(--color-text-muted)]" />
            </div>
          ) : files.length === 0 ? (
            <div className="text-center py-12">
              <Library size={28} className="text-[var(--color-text-muted)] mx-auto mb-2 opacity-30" />
              <p className="text-xs text-[var(--color-text-muted)]">
                {search ? "没有匹配的文件" : "暂无可引用的资源"}
              </p>
              <p className="text-[10px] text-[var(--color-text-muted)] mt-1 opacity-60">
                去「我的资源」页上传文件，索引完成后即可引用
              </p>
            </div>
          ) : (
            <div className="space-y-0.5 py-1">
              {files.map(f => {
                const sel = selectedIds.has(f.material_id);
                return (
                  <button
                    key={f.material_id}
                    onClick={() => toggleFile(f.material_id)}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-left transition-colors ${
                      sel
                        ? "bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/30"
                        : "hover:bg-[var(--color-surface)] border border-transparent"
                    }`}
                  >
                    {/* Checkbox */}
                    <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                      sel
                        ? "bg-[var(--color-accent)] border-[var(--color-accent)]"
                        : "border-[var(--color-border)]"
                    }`}>
                      {sel && <Check size={12} className="text-white" />}
                    </div>

                    {/* Icon */}
                    <div className="flex-shrink-0">{getIcon(ext(f))}</div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-[var(--color-text)] truncate">{f.file_name}</div>
                      <div className="text-[10px] text-[var(--color-text-muted)]">
                        {f.file_type?.toUpperCase()} · {formatSize(f.file_size)} · {f.status === "indexed" ? "✅ 已索引" : f.status}
                      </div>
                    </div>

                    {/* Select indicator */}
                    {sel && (
                      <div className="w-2 h-2 rounded-full bg-[var(--color-accent)] flex-shrink-0" />
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-[var(--color-border)]/50">
          <span className="text-[11px] text-[var(--color-text-muted)]">
            已选 {selectedIds.size} 个文件
          </span>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-1.5 text-xs rounded-lg border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleConfirm}
              disabled={selectedIds.size === 0}
              className="px-4 py-1.5 text-xs rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-30 transition-colors font-medium"
            >
              引用 ({selectedIds.size})
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
