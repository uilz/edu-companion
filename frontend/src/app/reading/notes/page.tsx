"use client";

/**
 * Reading 笔记管理 — 跳转到 FlashCard 反思型列表
 * 依据 docs/modules/reading/overview.md §5 + ADR 0003
 * 笔记 = FlashCard 反思型 (source='reading_note')
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { StickyNote, ArrowRight, Loader2, AlertCircle, ExternalLink } from "lucide-react";
import { readingService, COLOR_HEX, COLOR_LABELS } from "@/lib/api/reading-api";

export default function ReadingNotesPage() {
  const router = useRouter();
  const [notes, setNotes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterMaterial, setFilterMaterial] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await readingService.listNotes({ limit: 100 });
        setNotes(res.items);
      } catch (e: any) {
        setError(e.message || "加载失败");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const filteredNotes = filterMaterial
    ? notes.filter((n) => n.source_ref?.id === filterMaterial)
    : notes;

  // 统计
  const materials = Array.from(
    new Set(notes.map((n) => n.source_ref?.id).filter(Boolean)),
  );

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        {/* 头部 */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => router.push("/reading")}
            className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            ←
          </button>
          <div className="flex-1">
            <h1 className="text-2xl font-semibold flex items-center gap-2">
              <StickyNote size={22} /> 笔记管理
            </h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              笔记 = FlashCard 反思型 · 自动进入 FSRS 调度 · 统一复习入口
            </p>
          </div>
          <button
            onClick={() => router.push("/flashcard?source=reading_note")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-[var(--color-border)] rounded-md hover:bg-[var(--color-card)]"
          >
            <ExternalLink size={14} /> 在 FlashCard 中查看
          </button>
        </div>

        {error && (
          <div className="mb-4 px-4 py-3 border border-red-300 bg-red-50 text-sm text-red-700 rounded flex items-center gap-2">
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {/* 统计 */}
        {!loading && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <StatCard label="笔记总数" value={String(notes.length)} />
            <StatCard label="涉及材料" value={String(materials.length)} />
            <StatCard
              label="待复习"
              value={String(
                notes.filter((n) => {
                  if (!n.next_review_at) return true;
                  return new Date(n.next_review_at) <= new Date();
                }).length,
              )}
              color="text-amber-600"
            />
            <StatCard
              label="已稳定"
              value={String(notes.filter((n) => (n.stability || 0) > 30).length)}
              color="text-emerald-600"
            />
          </div>
        )}

        {/* 筛选 */}
        {!loading && materials.length > 0 && (
          <div className="mb-4 flex items-center gap-2 flex-wrap text-sm">
            <span className="text-[var(--color-text-muted)]">按材料筛选:</span>
            <button
              onClick={() => setFilterMaterial("")}
              className={`px-2.5 py-1 text-xs rounded border ${
                !filterMaterial
                  ? "bg-[var(--color-accent)] text-white"
                  : "border-[var(--color-border)] hover:bg-[var(--color-card)]"
              }`}
            >
              全部
            </button>
            {materials.map((m: any) => (
              <button
                key={m}
                onClick={() => setFilterMaterial(m)}
                className={`px-2.5 py-1 text-xs rounded border ${
                  filterMaterial === m
                    ? "bg-[var(--color-accent)] text-white"
                    : "border-[var(--color-border)] hover:bg-[var(--color-card)]"
                }`}
              >
                {m.slice(0, 12)}
              </button>
            ))}
          </div>
        )}

        {/* 列表 */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
          </div>
        ) : filteredNotes.length === 0 ? (
          <div className="border border-dashed border-[var(--color-border)] rounded-lg p-12 text-center">
            <StickyNote size={36} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm text-[var(--color-text-muted)] mb-3">
              {filterMaterial ? "该材料暂无笔记" : "还没有阅读笔记"}
            </p>
            <button
              onClick={() => router.push("/files")}
              className="text-sm text-[var(--color-accent)] hover:underline inline-flex items-center gap-1"
            >
              去阅读并写笔记 <ArrowRight size={12} />
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredNotes.map((n) => (
              <div
                key={n.id}
                className="border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-4"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1">
                      <span>来源: {n.source_ref?.id?.slice(0, 12) || "—"}</span>
                      {n.source_ref?.sub_id && (
                        <span>· 段落: {n.source_ref.sub_id}</span>
                      )}
                      <span>· {n.source}</span>
                    </div>
                    <p className="text-sm font-medium">{n.front_text}</p>
                  </div>
                  <div className="text-right text-xs text-[var(--color-text-muted)] ml-3">
                    <div>
                      复习 {n.review_count || 0} 次
                    </div>
                    {n.next_review_at && (
                      <div>
                        下次: {new Date(n.next_review_at).toLocaleDateString("zh-CN")}
                      </div>
                    )}
                  </div>
                </div>
                {n.back_context && (
                  <p className="text-xs text-[var(--color-text-muted)] mt-1 pl-3 border-l-2 border-[var(--color-border)]">
                    {n.back_context}
                  </p>
                )}
                {n.back_text && (
                  <p className="text-xs text-[var(--color-text)] mt-2 pl-3 border-l-2 border-emerald-300">
                    💭 {n.back_text}
                  </p>
                )}
                {n.linked_node_ids && n.linked_node_ids.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {n.linked_node_ids.slice(0, 3).map((id: string) => (
                      <span
                        key={id}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                      >
                        {id.slice(0, 12)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-3">
      <div className="text-xs text-[var(--color-text-muted)]">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color || ""}`}>{value}</div>
    </div>
  );
}
