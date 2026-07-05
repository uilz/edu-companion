"use client";

/**
 * Reading 主页 — 阅读列表/入口
 * 依据 docs/modules/reading/overview.md + ADR 0003
 *
 * 设计：复用 file-management 的材料，本页是阅读入口和元数据看板
 */
import { useRouter } from "next/navigation";
import { BookOpen, GitCompare, StickyNote, Settings, ArrowRight, Library, Loader2, AlertCircle } from "lucide-react";
import { readingService, ReadingMode, MODE_LABELS, ReadingSession } from "@/lib/api/reading-api";
import { useUserData } from "@/hooks/useUserData";

export default function ReadingPage() {
  const router = useRouter();
  // 任务 #49：统一使用 useUserData 自动等待 AuthContext，
  // 避免「useCurrentUserId 隐藏 authLoading 导致 useEffect 死锁」问题。
  const { data, loading, error, refetch } = useUserData<{
    sessions: ReadingSession[];
    remindersCount: number;
    prefs: any;
  }>(async () => {
    const [sessRes, remRes, prefsRes] = await Promise.all([
      readingService.listSessions({ limit: 20 }),
      readingService.listReviewReminders().catch(() => ({ total: 0, items: [] })),
      readingService.getPrefs().catch(() => null),
    ]);
    return {
      sessions: sessRes.items,
      remindersCount: remRes.total,
      prefs: prefsRes,
    };
  });
  const sessions = data?.sessions ?? [];
  const remindersCount = data?.remindersCount ?? 0;
  const prefs = data?.prefs ?? null;

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* 头部 */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-[var(--color-text)] tracking-tight flex items-center gap-2">
              <BookOpen size={22} /> 知识加工车间
            </h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              阅读体验 + 加工工具 — 5 色标注 · 反思笔记 · 回顾提醒
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => router.push("/files")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-[var(--color-border)] rounded-md hover:bg-[var(--color-card)]"
            >
              <Library size={14} /> 材料库
            </button>
            <button
              onClick={() => router.push("/reading/notes")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-[var(--color-border)] rounded-md hover:bg-[var(--color-card)]"
            >
              <StickyNote size={14} /> 笔记
            </button>
          </div>
        </div>

        {/* 加载/错误 */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
          </div>
        )}
        {error && (
          <div className="mb-6 px-4 py-3 border border-red-300 bg-red-50 text-sm text-red-700 flex items-center gap-2 rounded">
            <AlertCircle size={15} /> {error.message}
          </div>
        )}

        {/* 概览卡片 */}
        {!loading && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <StatCard
              label="总会话"
              value={String(sessions.length)}
              hint="包括已结束和进行中"
            />
            <StatCard
              label="进行中"
              value={String(sessions.filter((s) => !s.ended_at).length)}
              hint="未结束的会话"
              color="text-emerald-600"
            />
            <StatCard
              label="笔记数"
              value={String(
                sessions.reduce((acc, s) => acc + (s.notes_created || 0), 0),
              )}
              hint="通过 FlashCard 反思型"
            />
            <StatCard
              label="待回顾"
              value={String(remindersCount)}
              hint="由 PlanItem 调度"
              color="text-amber-600"
            />
          </div>
        )}

        {/* 入口卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <EntryCard
            icon={<BookOpen size={20} />}
            title="阅读材料"
            description="从材料库选择材料进入阅读会话（精读/略读/回顾三种模式）"
            onClick={() => router.push("/files")}
            cta="打开材料库"
          />
          <EntryCard
            icon={<GitCompare size={20} />}
            title="对比阅读"
            description="左右分屏对比两个独立材料，同步滚动，标注跨材料标记"
            onClick={() => router.push("/reading/compare")}
            cta="进入对比"
          />
          <EntryCard
            icon={<StickyNote size={20} />}
            title="笔记管理"
            description="所有阅读笔记 = FlashCard 反思型列表，统一进入 FSRS 调度"
            onClick={() => router.push("/reading/notes")}
            cta="查看笔记"
          />
        </div>

        {/* 最近会话 */}
        {!loading && sessions.length > 0 && (
          <div className="border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-5">
            <h2 className="text-sm font-semibold text-[var(--color-text-muted)] mb-3">最近会话</h2>
            <div className="space-y-2">
              {sessions.slice(0, 10).map((s) => (
                <button
                  key={s.id}
                  onClick={() => router.push(`/reading/materials/${s.material_id}?session=${s.id}`)}
                  className="w-full flex items-center justify-between px-3 py-2 border border-[var(--color-border)] rounded-md hover:bg-[var(--color-surface-2)] text-left"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="text-xs font-mono text-[var(--color-text-muted)] w-24 truncate">
                      {s.material_id.slice(0, 12)}
                    </div>
                    <div className="text-sm font-medium">
                      {MODE_LABELS[s.mode as ReadingMode] || s.mode}
                    </div>
                    <div className="text-xs text-[var(--color-text-muted)]">
                      {s.ended_at ? "已结束" : "进行中"}
                    </div>
                    <div className="text-xs text-[var(--color-text-muted)]">
                      标注 {s.annotations_created} · 笔记 {s.notes_created}
                    </div>
                  </div>
                  <div className="text-xs text-[var(--color-text-muted)]">
                    {new Date(s.started_at).toLocaleString("zh-CN", { hour12: false })}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 偏好提示 */}
        {prefs && (
          <div className="mt-6 border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-4 flex items-center gap-3 text-sm text-[var(--color-text-muted)]">
            <Settings size={14} />
            <span>
              默认模式：<b>{MODE_LABELS[prefs.default_mode as ReadingMode] || prefs.default_mode}</b> ·
              回顾提醒：<b>{prefs.review_reminder_days?.join("/") || "7/30/90"}</b> 天
            </span>
            <button
              onClick={() => router.push("/files")}
              className="ml-auto text-[var(--color-accent)] hover:underline inline-flex items-center gap-1"
            >
              开始阅读 <ArrowRight size={12} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, hint, color }: { label: string; value: string; hint?: string; color?: string }) {
  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-3">
      <div className="text-xs text-[var(--color-text-muted)]">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color || ""}`}>{value}</div>
      {hint && <div className="text-[10px] text-[var(--color-text-muted)] mt-1">{hint}</div>}
    </div>
  );
}

function EntryCard({ icon, title, description, onClick, cta }: {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
  cta: string;
}) {
  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-4">
      <div className="flex items-center gap-2 mb-2 text-[var(--color-text)]">
        {icon}
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <p className="text-xs text-[var(--color-text-muted)] mb-3">{description}</p>
      <button
        onClick={onClick}
        className="text-xs text-[var(--color-accent)] hover:underline inline-flex items-center gap-1"
      >
        {cta} <ArrowRight size={12} />
      </button>
    </div>
  );
}
