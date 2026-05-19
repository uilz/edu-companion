"use client";

import { useState, useEffect, useCallback } from "react";
import { Search, X, Loader2, BookOpen, CheckSquare, Square } from "lucide-react";
import type { MaterialMeta } from "@/types";

interface MaterialPickerProps {
  partitionId: string;
  selectedIds: string[];
  onConfirm: (ids: string[]) => void;
  onClose: () => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

export default function MaterialPicker({
  partitionId,
  selectedIds,
  onConfirm,
  onClose,
}: MaterialPickerProps) {
  const [materials, setMaterials] = useState<MaterialMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [checked, setChecked] = useState<Set<string>>(new Set(selectedIds));
  const [error, setError] = useState("");

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

  const toggleMaterial = (materialId: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(materialId)) {
        next.delete(materialId);
      } else {
        next.add(materialId);
      }
      return next;
    });
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50">
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] shadow-xl w-[420px] max-h-[70vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <div className="flex items-center gap-2">
            <BookOpen size={16} className="text-[var(--color-accent)]" />
            <span className="text-sm font-semibold text-[var(--color-text)]">
              引用资料
            </span>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-[var(--color-surface)]">
            <X size={16} />
          </button>
        </div>

        {/* Search */}
        <div className="px-4 py-2">
          <div className="flex items-center gap-1.5 px-2 py-1.5 text-xs bg-[var(--color-surface)] border border-[var(--color-border)]">
            <Search size={13} className="text-[var(--color-text-muted)]" />
            <input
              type="text"
              placeholder="搜索本分区资料..."
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
          <div className="px-4 py-1.5 text-xs text-red-400">{error}</div>
        )}

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="px-4 py-8 text-center">
              <Loader2 size={16} className="animate-spin mx-auto mb-2" />
              <div className="text-xs text-[var(--color-text-muted)]">加载中...</div>
            </div>
          ) : materials.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <BookOpen size={20} className="text-[var(--color-text-muted)] mx-auto mb-2" />
              <div className="text-xs text-[var(--color-text-muted)]">本分区暂无资料</div>
            </div>
          ) : (
            <div className="space-y-0.5 p-2">
              {materials.map((mat) => {
                const isChecked = checked.has(mat.material_id);
                return (
                  <button
                    key={mat.material_id}
                    onClick={() => toggleMaterial(mat.material_id)}
                    className={`w-full flex items-center gap-2 px-2 py-1.5 text-xs text-left hover:bg-[var(--color-surface)] transition-colors ${
                      isChecked ? "bg-[var(--color-accent)]/5" : ""
                    }`}
                  >
                    {isChecked ? (
                      <CheckSquare size={15} className="text-[var(--color-accent)] flex-shrink-0" />
                    ) : (
                      <Square size={15} className="text-[var(--color-text-muted)] flex-shrink-0" />
                    )}
                    <span className="truncate flex-1 text-[var(--color-text-secondary)]">
                      {mat.file_name}
                    </span>
                    <span className="text-[10px] text-[var(--color-text-muted)] flex-shrink-0">
                      {formatSize(mat.file_size)}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--color-border)]">
          <span className="text-xs text-[var(--color-text-muted)]">
            已选: {checked.size}
          </span>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
            >
              取消
            </button>
            <button
              onClick={() => onConfirm(Array.from(checked))}
              className="px-4 py-1.5 text-xs font-medium bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity"
            >
              确认引用
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
