"use client";

/**
 * LanguageRoom 会话回顾页
 * 依据 docs/modules/language-room/overview.md + ADR 0004
 * 按参与者各自维度展示
 */
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { History, ArrowLeft, Loader2, AlertCircle, Clock, MessageSquare, AlertCircle as AlertIcon, BookOpen, StickyNote, Sparkles } from "lucide-react";
import { liveroomService, SessionReview, ErrorType, HELPER_TYPE_LABELS } from "@/lib/api/liveroom-api";

export default function ReviewPage() {
  const router = useRouter();
  const params = useParams();
  const roomId = params.roomId as string;

  const [review, setReview] = useState<SessionReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [speakerFilter, setSpeakerFilter] = useState<string>("");

  useEffect(() => {
    setLoading(true);
    liveroomService.getSessionReview(roomId)
      .then(setReview)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [roomId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin" />
      </div>
    );
  }

  // 后端可能返回 {} (无 session 时 routes.py:507) — 友好空态而非 "undefined" 满屏
  if (error || !review || !review.session_id) {
    return (
      <div className="min-h-screen bg-[var(--color-bg)]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
          <div className="flex items-center gap-3 mb-6">
            <button
              onClick={() => router.push(`/liveroom/rooms/${roomId}`)}
              className="p-1.5 hover:bg-[var(--color-card)] rounded"
            >
              <ArrowLeft size={18} />
            </button>
            <h1 className="text-xl font-semibold flex items-center gap-2">
              <History size={20} /> 会话回顾
            </h1>
          </div>
          <div className="border border-dashed border-[var(--color-border)] rounded-lg p-10 text-center text-sm text-[var(--color-text-muted)]">
            {error || "暂无会话记录 (需要先加入房间并参与一次对话)"}
          </div>
          <div className="mt-4 text-center">
            <button
              onClick={() => router.push("/liveroom")}
              className="text-xs text-emerald-600 hover:underline"
            >
              返回房间列表
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 后端可能返回 {} (无 session 时 routes.py:507) — 加可选链 + 默认值防崩
  const transcripts = review?.transcripts ?? [];
  const messages = review?.messages ?? [];
  const vocabularies = review?.vocabularies ?? [];
  const errors = review?.errors ?? [];

  const filteredTranscripts = transcripts.filter((t) => {
    if (searchQuery && !t.text.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => router.push(`/liveroom/rooms/${roomId}`)}
            className="p-1.5 hover:bg-[var(--color-card)] rounded"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <h1 className="text-xl font-semibold flex items-center gap-2">
              <History size={20} /> 会话回顾
            </h1>
            <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
              决策 1 + 11: 数据归属 = 参与者各自, 转写数据各自分开
            </p>
          </div>
        </div>

        {/* 概览 */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-6">
          <StatCard icon={<Clock size={14} />} label="时长" value={formatDuration(review.duration_seconds)} />
          <StatCard icon={<MessageSquare size={14} />} label="转写段" value={String(review.transcript_count)} />
          <StatCard icon={<AlertIcon size={14} />} label="错误标记" value={String(review.errors_marked)} color="text-red-600" />
          <StatCard icon={<BookOpen size={14} />} label="生成卡片" value={String(review.cards_generated)} />
          <StatCard icon={<Sparkles size={14} />} label="AI 召唤" value={String(review.ai_help_requests)} />
          <StatCard icon={<StickyNote size={14} />} label="词汇便签" value={String(review.vocabulary_captured)} />
        </div>

        {/* 场景信息 */}
        {review.scenario && (
          <div className="mb-6 border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-4">
            <div className="text-sm font-medium mb-1.5">场景: {review.scenario.name}</div>
            {review.scenario.prompt_text && (
              <div className="text-xs px-2.5 py-1.5 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded inline-block">
                {review.scenario.prompt_text}
              </div>
            )}
            {review.scenario.target_goals?.length > 0 && (
              <ul className="mt-2 space-y-0.5 text-xs">
                {review.scenario.target_goals.map((g, i) => (
                  <li key={i}>• {g}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* 转写搜索 */}
        {transcripts.length > 0 && (
          <div className="mb-3 flex items-center gap-2">
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索转写..."
              className="flex-1 text-sm px-3 py-1.5 border border-[var(--color-border)] rounded bg-[var(--color-card)]"
            />
            <div className="text-xs text-[var(--color-text-muted)]">
              {filteredTranscripts.length} / {transcripts.length}
            </div>
          </div>
        )}

        {/* 转写列表 */}
        {filteredTranscripts.length > 0 ? (
          <div className="border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg overflow-hidden">
            <div className="px-4 py-2 border-b border-[var(--color-border)]">
              <div className="text-sm font-medium">我的转写记录</div>
              <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                决策 11: 仅自己可见的转写 (按参与者各自存)
              </div>
            </div>
            <div className="max-h-[600px] overflow-y-auto p-3 space-y-1.5">
              {filteredTranscripts.map((t) => (
                <div
                  key={t.id}
                  className={`text-sm px-3 py-2 rounded border ${
                    t.is_error
                      ? "border-red-200 bg-red-50"
                      : "border-[var(--color-border)] bg-[var(--color-bg)]"
                  }`}
                >
                  <div className="flex items-center justify-between mb-0.5 text-[10px] text-[var(--color-text-muted)]">
                    <span>{t.speaker_name || t.speaker_id?.slice(0, 8)}</span>
                    <span>
                      {t.started_at ? new Date(t.started_at).toLocaleTimeString("zh-CN", { hour12: false }) : ""}
                      {t.is_error && <span className="ml-2 text-red-600">⚠ 错误</span>}
                    </span>
                  </div>
                  <div>{t.text}</div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="border border-dashed border-[var(--color-border)] rounded-lg p-10 text-center text-sm text-[var(--color-text-muted)]">
            暂无转写记录
          </div>
        )}

        {/* 词汇便签 */}
        {vocabularies.length > 0 && (
          <div className="mt-6 border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-4">
            <div className="text-sm font-medium mb-2 flex items-center gap-1.5">
              <StickyNote size={14} /> 词汇便签 (复用 FlashCard 数据卡)
            </div>
            <div className="space-y-1.5">
              {vocabularies.map((v) => (
                <div key={v.id} className="text-xs px-2 py-1.5 border border-[var(--color-border)] rounded">
                  <strong>{v.word}</strong>
                  {v.translation && <span className="text-[var(--color-text-muted)]"> — {v.translation}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 文字辅助区 */}
        {messages.length > 0 && (
          <div className="mt-6 border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-4">
            <div className="text-sm font-medium mb-2">文字辅助区 (复用 ExplainCard)</div>
            <div className="space-y-1.5">
              {messages.slice(0, 10).map((m: any) => (
                <div key={m.id} className="text-xs px-2 py-1.5 bg-blue-50 border border-blue-200 rounded">
                  <div className="text-[10px] text-blue-600 mb-0.5">[{m.message_type || "text"}]</div>
                  {m.content || m.text}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon, label, value, color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-3">
      <div className="text-[10px] text-[var(--color-text-muted)] flex items-center gap-1">
        {icon} {label}
      </div>
      <div className={`text-xl font-semibold mt-1 ${color || "text-[var(--color-text)]"}`}>
        {value}
      </div>
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (!seconds) return "0s";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s}s`;
}
