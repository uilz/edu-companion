"use client";

/**
 * FlashCard 复习会话页
 * 依据 docs/modules/flashcard/overview.md §4
 */
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { flashcardService, FlashCard, ReviewResult, SelfAssessment, ASSESSMENT_LABELS, CARD_TYPE_LABELS } from "@/lib/api/flashcard-api";

export default function FlashCardReviewPage() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [queue, setQueue] = useState<FlashCard[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showBack, setShowBack] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<ReviewResult | null>(null);
  const [stats, setStats] = useState({ difficult: 0, good: 0, easy: 0 });
  const [sessionStartedAt, setSessionStartedAt] = useState<number>(Date.now());

  const startSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await flashcardService.startSession("manual", 50);
      setSessionId(data.session_id);
      setQueue(data.cards);
      setCurrentIndex(0);
      setShowBack(false);
      setLastResult(null);
      setStats({ difficult: 0, good: 0, easy: 0 });
      setSessionStartedAt(Date.now());
    } catch (e: any) {
      setError(e.message || "启动复习失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const submitAssessment = useCallback(async (assessment: SelfAssessment) => {
    if (!queue[currentIndex] || !sessionId) return;
    setLoading(true);
    try {
      const result = await flashcardService.submitReview(queue[currentIndex].id, assessment, sessionId);
      setLastResult(result);
      setStats((s) => ({ ...s, [assessment]: s[assessment] + 1 }));
      setTimeout(() => {
        if (currentIndex + 1 < queue.length) {
          setCurrentIndex((i) => i + 1);
          setShowBack(false);
          setLastResult(null);
        }
      }, 1500);
    } catch (e: any) {
      setError(e.message || "提交失败");
    } finally {
      setLoading(false);
    }
  }, [currentIndex, queue, sessionId]);

  const endSession = useCallback(async () => {
    if (!sessionId) return;
    const duration = Math.round((Date.now() - sessionStartedAt) / 1000);
    try {
      await flashcardService.endSession(sessionId, {
        ...stats,
        duration_seconds: duration,
      });
    } catch (e: any) {
      console.warn("结束会话失败:", e);
    }
    setSessionId(null);
    setQueue([]);
    setCurrentIndex(0);
  }, [sessionId, stats, sessionStartedAt]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!sessionId || queue.length === 0) return;
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        setShowBack((v) => !v);
      } else if (showBack && !lastResult) {
        if (e.key === "1") submitAssessment("difficult");
        else if (e.key === "2") submitAssessment("good");
        else if (e.key === "3") submitAssessment("easy");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [sessionId, queue, showBack, lastResult, submitAssessment]);

  // ── 启动前 ──
  if (!sessionId) {
    return (
      <div className="container mx-auto p-6 max-w-2xl">
        <div className="flex items-center gap-2 mb-6">
          <button
            onClick={() => router.push("/flashcard")}
            className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            ← 返回
          </button>
        </div>
        <div className="border border-[var(--color-border)] bg-[var(--color-surface)] rounded-lg p-6">
          <h1 className="text-xl font-semibold mb-4">📖 开始复习会话</h1>
          <p className="text-[var(--color-text-muted)] mb-4">
            FSRS 调度器将根据每张卡片的稳定性、难度、遗忘速率计算最优复习时间。
          </p>
          <ul className="text-sm space-y-1 text-[var(--color-text-muted)] list-disc pl-5 mb-4">
            <li>按"空格"或"回车"显示答案</li>
            <li>显示答案后, 按 <kbd className="px-1.5 py-0.5 rounded border border-[var(--color-border)] text-xs">1</kbd> 困难 / <kbd className="px-1.5 py-0.5 rounded border border-[var(--color-border)] text-xs">2</kbd> 良好 / <kbd className="px-1.5 py-0.5 rounded border border-[var(--color-border)] text-xs">3</kbd> 简单</li>
            <li>每次复习后会展示 FSRS 状态变化与下次复习时间</li>
            <li>复习事件会小权重回写到 CognitiveNode.Belief (主 1.0 / 次 0.3)</li>
          </ul>
          {error && <div className="text-sm text-red-500 mb-2">{error}</div>}
          <button
            onClick={startSession}
            disabled={loading}
            className="w-full px-4 py-2 text-sm rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {loading ? "加载中..." : "▶ 开始复习"}
          </button>
        </div>
      </div>
    );
  }

  // ── 无到期卡 ──
  if (queue.length === 0) {
    return (
      <div className="container mx-auto p-6 max-w-2xl">
        <div className="border border-[var(--color-border)] bg-[var(--color-surface)] rounded-lg p-12 text-center">
          <div className="text-6xl mb-4">🎉</div>
          <div className="text-lg font-medium mb-2">没有需要复习的卡片</div>
          <div className="text-sm text-[var(--color-text-muted)] mb-4">
            所有卡片都已掌握, 7 天后再来吧!
          </div>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => router.push("/flashcard")}
              className="px-4 py-2 text-sm rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
            >
              返回列表
            </button>
            <button
              onClick={endSession}
              className="px-4 py-2 text-sm rounded bg-emerald-600 text-white hover:bg-emerald-700"
            >
              完成
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── 复习中 ──
  const card = queue[currentIndex];

  return (
    <div className="container mx-auto p-6 max-w-3xl">
      {/* 顶部进度栏 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => router.push("/flashcard")}
            className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            ←
          </button>
          <span className="text-sm text-[var(--color-text-muted)]">
            {currentIndex + 1} / {queue.length}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2 py-0.5 rounded bg-red-500/10 text-red-500">
            困难 {stats.difficult}
          </span>
          <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-600">
            良好 {stats.good}
          </span>
          <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-500">
            简单 {stats.easy}
          </span>
        </div>
        <button
          onClick={endSession}
          className="px-3 py-1 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
        >
          结束会话
        </button>
      </div>

      {/* 进度条 */}
      <div className="w-full bg-[var(--color-surface-2)] rounded-full h-1.5 mb-6">
        <div
          className="bg-emerald-500 h-1.5 rounded-full transition-all"
          style={{ width: `${((currentIndex + (lastResult ? 1 : 0)) / queue.length) * 100}%` }}
        />
      </div>

      {/* 卡片内容 */}
      <div className="border border-[var(--color-border)] bg-[var(--color-surface)] rounded-lg p-8 min-h-[300px] mb-4">
        <div className="flex items-center gap-1.5 mb-4 flex-wrap">
          <span className="text-[10px] px-2 py-0.5 rounded border border-[var(--color-border)] text-[var(--color-text-muted)]">
            {CARD_TYPE_LABELS[card.type] || `类型${card.type}`}
          </span>
          {card.tags?.slice(0, 3).map((t) => (
            <span
              key={t}
              className="text-[10px] px-2 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
            >
              #{t}
            </span>
          ))}
        </div>

        {/* 正面 */}
        <div className="text-xl font-medium leading-relaxed whitespace-pre-wrap mb-4">
          {card.front_text}
        </div>

        {/* 分隔线 */}
        {showBack && <hr className="my-4 border-dashed border-[var(--color-border)]" />}

        {/* 反面 */}
        {showBack && (
          <div className="text-base leading-relaxed whitespace-pre-wrap text-foreground/90">
            {card.back_text || <span className="text-[var(--color-text-muted)]">(无答案)</span>}
          </div>
        )}

        {/* 上次复习结果 (FSRS 可观测) */}
        {lastResult && (
          <div className="mt-6 p-4 bg-emerald-500/5 border border-emerald-500/20 rounded space-y-2 text-sm">
            <div className="font-medium flex items-center gap-1 text-emerald-600">
              ✓ 已记录: {ASSESSMENT_LABELS[lastResult.self_assessment]}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div>
                <div className="text-[var(--color-text-muted)]">稳定性</div>
                <div>{lastResult.stability_before.toFixed(2)} → <b>{lastResult.stability_after.toFixed(2)}</b></div>
              </div>
              <div>
                <div className="text-[var(--color-text-muted)]">难度</div>
                <div>{lastResult.difficulty_before.toFixed(2)} → <b>{lastResult.difficulty_after.toFixed(2)}</b></div>
              </div>
              <div>
                <div className="text-[var(--color-text-muted)]">遗忘速率</div>
                <div>{(lastResult.forgetting_rate_after * 100).toFixed(0)}%</div>
              </div>
              <div>
                <div className="text-[var(--color-text-muted)]">下次复习</div>
                <div>{new Date(lastResult.next_review_at).toLocaleDateString()}</div>
              </div>
            </div>
            {lastResult.belief_deltas && lastResult.belief_deltas.length > 0 && (
              <div className="text-xs text-[var(--color-text-muted)] pt-2 border-t border-emerald-500/20">
                📊 Belief 已更新: {lastResult.belief_deltas.length} 个知识点
              </div>
            )}
          </div>
        )}

        {/* FSRS 当前状态 (复习前) */}
        {!lastResult && showBack && card.stability != null && (
          <div className="mt-6 p-3 bg-[var(--color-surface-2)] rounded grid grid-cols-3 gap-3 text-xs">
            <div>稳定性 S: <b>{card.stability?.toFixed(2)}</b></div>
            <div>难度 D: <b>{card.difficulty?.toFixed(2)}</b></div>
            <div>遗忘 F: <b>{((card.forgetting_rate ?? 0) * 100).toFixed(0)}%</b></div>
          </div>
        )}
      </div>

      {/* 操作 */}
      {error && <div className="text-sm text-red-500 mb-2">{error}</div>}

      {!showBack ? (
        <button
          onClick={() => setShowBack(true)}
          className="w-full px-4 py-3 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          disabled={loading}
        >
          👁 显示答案 (空格)
        </button>
      ) : lastResult ? (
        <div className="text-center text-sm text-[var(--color-text-muted)]">
          正在进入下一张...
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={() => submitAssessment("difficult")}
            disabled={loading}
            className="px-4 py-3 text-sm rounded bg-red-500 text-white hover:bg-red-600 disabled:opacity-50"
          >
            ✕ 困难 (1)
          </button>
          <button
            onClick={() => submitAssessment("good")}
            disabled={loading}
            className="px-4 py-3 text-sm rounded bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50"
          >
            ✓ 良好 (2)
          </button>
          <button
            onClick={() => submitAssessment("easy")}
            disabled={loading}
            className="px-4 py-3 text-sm rounded bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
          >
            → 简单 (3)
          </button>
        </div>
      )}
    </div>
  );
}
