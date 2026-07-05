"use client";

/**
 * Reading 对比阅读 — 左右分屏对比
 * 依据 docs/modules/reading/overview.md §8 + ADR 0003
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { GitCompare, ArrowLeftRight, Loader2, AlertCircle, Highlighter, BookOpen } from "lucide-react";
import { readingService, ComparePayload, ReadingAnnotation, COLOR_HEX, COLOR_LABELS } from "@/lib/api/reading-api";

export default function ComparePage() {
  const router = useRouter();
  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");
  const [syncScroll, setSyncScroll] = useState(false);
  const [payload, setPayload] = useState<ComparePayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = async () => {
    if (!leftId || !rightId) {
      setError("请输入左右两侧材料 ID");
      return;
    }
    if (leftId === rightId) {
      setError("左右两侧材料不能相同");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await readingService.buildCompare({
        material_id_left: leftId,
        material_id_right: rightId,
        sync_scroll: syncScroll,
      });
      setPayload(data);
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {/* 头部 */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => router.push("/reading")}
            className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            ←
          </button>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <GitCompare size={22} /> 对比阅读
          </h1>
        </div>

        {/* 输入栏 */}
        <div className="border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-4 mb-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
            <div className="lg:col-span-2">
              <label className="text-xs text-[var(--color-text-muted)] block mb-1">左侧材料 ID</label>
              <input
                value={leftId}
                onChange={(e) => setLeftId(e.target.value)}
                placeholder="material_id_left"
                className="w-full px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
              />
            </div>
            <div className="hidden lg:flex justify-center pb-1.5">
              <ArrowLeftRight size={20} className="text-[var(--color-text-muted)]" />
            </div>
            <div className="lg:col-span-2">
              <label className="text-xs text-[var(--color-text-muted)] block mb-1">右侧材料 ID</label>
              <input
                value={rightId}
                onChange={(e) => setRightId(e.target.value)}
                placeholder="material_id_right"
                className="w-full px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
              />
            </div>
            <button
              onClick={handleLoad}
              disabled={loading}
              className="px-4 py-1.5 text-sm bg-[var(--color-accent)] text-white rounded disabled:opacity-50"
            >
              {loading ? <Loader2 size={14} className="inline animate-spin" /> : "加载对比"}
            </button>
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs">
            <label className="flex items-center gap-1.5 text-[var(--color-text-muted)]">
              <input
                type="checkbox"
                checked={syncScroll}
                onChange={(e) => setSyncScroll(e.target.checked)}
              />
              同步滚动
            </label>
          </div>
        </div>

        {error && (
          <div className="mb-4 px-4 py-3 border border-red-300 bg-red-50 text-sm text-red-700 rounded flex items-center gap-2">
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {/* 对比分屏 */}
        {payload && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <CompareColumn
              title="左侧材料"
              materialId={payload.material_id_left}
              annotations={payload.left.annotations}
              byColor={payload.left.by_color}
            />
            <CompareColumn
              title="右侧材料"
              materialId={payload.material_id_right}
              annotations={payload.right.annotations}
              byColor={payload.right.by_color}
            />
          </div>
        )}

        {!payload && !loading && (
          <div className="border border-dashed border-[var(--color-border)] rounded-lg p-12 text-center text-sm text-[var(--color-text-muted)]">
            <GitCompare size={36} className="mx-auto mb-3 opacity-30" />
            输入两个材料 ID 进行左右分屏对比
            <div className="mt-2 text-xs">
              标注自动带材料来源标记，可导出为对比表 / 转为对比 FlashCard
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function CompareColumn({ title, materialId, annotations, byColor }: {
  title: string;
  materialId: string;
  annotations: ReadingAnnotation[];
  byColor: Record<string, number>;
}) {
  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-[var(--color-border)] bg-[var(--color-surface-2)] flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <BookOpen size={14} /> {title}
          </h3>
          <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
            {materialId.slice(0, 20)} · 共 {annotations.length} 条标注
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          {(Object.keys(byColor) as (keyof typeof byColor)[]).map((c) =>
            byColor[c] ? (
              <span
                key={c}
                className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                style={{ backgroundColor: COLOR_HEX[c as keyof typeof COLOR_HEX] + "22", color: COLOR_HEX[c as keyof typeof COLOR_HEX] }}
              >
                {COLOR_LABELS[c as keyof typeof COLOR_HEX]} {byColor[c]}
              </span>
            ) : null,
          )}
        </div>
      </div>
      <div className="p-4 max-h-[600px] overflow-y-auto">
        {/* 占位文本 — 实际由 file-management 提供 */}
        <p className="text-xs text-[var(--color-text-muted)] mb-3 italic">
          实际内容由 file-management 提供（MaterialChunk）。此处仅展示标注汇总。
        </p>
        {annotations.length === 0 ? (
          <p className="text-xs text-[var(--color-text-muted)]">该材料暂无标注</p>
        ) : (
          <div className="space-y-2">
            {annotations.map((a) => (
              <div
                key={a.id}
                className="border border-[var(--color-border)] rounded p-2"
                style={{ borderLeftWidth: 3, borderLeftColor: COLOR_HEX[a.color] }}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <Highlighter size={10} style={{ color: COLOR_HEX[a.color] }} />
                  <span className="text-[10px]" style={{ color: COLOR_HEX[a.color] }}>
                    {COLOR_LABELS[a.color]}
                  </span>
                </div>
                {a.text && <p className="text-xs line-clamp-3">{a.text}</p>}
                {a.note && <p className="text-[10px] text-[var(--color-text-muted)] mt-1">{a.note}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
