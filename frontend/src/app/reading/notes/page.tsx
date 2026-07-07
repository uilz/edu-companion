"use client";

/**
 * Reading 笔记管理 — 跳转到 FlashCard 反思型列表
 * 依据 docs/modules/reading/overview.md §5 + ADR 0003
 * 笔记 = FlashCard 反思型 (source='reading_note')
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { StickyNote, ArrowRight, AlertCircle, ExternalLink } from "lucide-react";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { readingService, COLOR_HEX, COLOR_LABELS } from "@/lib/api/reading-api";
import { StatCard } from "@/components/ui/StatCard";

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
    <div className="min-h-screen bg-page">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        {/* 头部 */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => router.push("/reading")}
            className="text-muted hover:text"
          >
            ←
          </button>
          <div className="flex-1">
            <h1 className="text-2xl font-semibold flex items-center gap-2">
              <StickyNote size={22} /> 笔记管理
            </h1>
            <p className="text-sm text-muted mt-1">
              笔记 = FlashCard 反思型 · 自动进入 FSRS 调度 · 统一复习入口
            </p>
          </div>
          <button
            onClick={() => router.push("/flashcard?source=reading_note")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border rounded-md hover:bg-surface"
          >
            <ExternalLink size={14} /> 在 FlashCard 中查看
          </button>
        </div>

        {error && (
          <div className="mb-4 px-4 py-3 border border-danger/30 bg-danger/10 text-sm text-danger rounded flex items-center gap-2">
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
              color="text-warning"
            />
            <StatCard
              label="已稳定"
              value={String(notes.filter((n) => (n.stability || 0) > 30).length)}
              color="text-success"
            />
          </div>
        )}

        {/* 筛选 */}
        {!loading && materials.length > 0 && (
          <div className="mb-4 flex items-center gap-2 flex-wrap text-sm">
            <span className="text-muted">按材料筛选:</span>
            <button
              onClick={() => setFilterMaterial("")}
              className={`px-2.5 py-1 text-xs rounded border ${
                !filterMaterial
                  ? "bg-accent text-white"
                  : "border hover:bg-surface"
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
                    ? "bg-accent text-white"
                    : "border hover:bg-surface"
                }`}
              >
                {m.slice(0, 12)}
              </button>
            ))}
          </div>
        )}

        {/* 列表 */}
        {loading ? (
          <PageSkeleton />
        ) : filteredNotes.length === 0 ? (
          <div className="border border-dashed border rounded-lg p-12 text-center">
            <StickyNote size={36} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm text-muted mb-3">
              {filterMaterial ? "该材料暂无笔记" : "还没有阅读笔记"}
            </p>
            <button
              onClick={() => router.push("/files")}
              className="text-sm text-accent hover:underline inline-flex items-center gap-1"
            >
              去阅读并写笔记 <ArrowRight size={12} />
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredNotes.map((n) => (
              <div
                key={n.id}
                className="border border bg-surface rounded-lg p-4"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-xs text-muted mb-1">
                      <span>来源: {n.source_ref?.id?.slice(0, 12) || "—"}</span>
                      {n.source_ref?.sub_id && (
                        <span>· 段落: {n.source_ref.sub_id}</span>
                      )}
                      <span>· {n.source}</span>
                    </div>
                    <p className="text-sm font-medium">{n.front_text}</p>
                  </div>
                  <div className="text-right text-xs text-muted ml-3">
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
                  <p className="text-xs text-muted mt-1 pl-3 border-l-2 border">
                    {n.back_context}
                  </p>
                )}
                {n.back_text && (
                  <p className="text-xs text mt-2 pl-3 border-l-2 border-success/30">
                    💭 {n.back_text}
                  </p>
                )}
                {n.linked_node_ids && n.linked_node_ids.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {n.linked_node_ids.slice(0, 3).map((id: string) => (
                      <span
                        key={id}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-surface-hover text-muted"
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


