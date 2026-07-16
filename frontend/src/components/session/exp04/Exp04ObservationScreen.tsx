// ============================================================
// EXP-04 V2 · APPLEGO OBSERVATION Screen
//
// "苹果果注意到……"
//   - AI 用自然语言说出观察到什么
//   - 不说"你错了"，不打分（P1: Observe before Judge）
//   - 指出已经理解了的部分
//   - 指出值得进一步思考的地方
//   - 最后给一个开放问题
//   - 用户继续 → REFLECTION
// ============================================================

"use client";

import { useState, useEffect, useCallback } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { authedFetch } from "@/lib/api/api";

interface ObservationScreenProps {
  mission: { title: string; steps: { order: number; description: string; type: string }[] } | null;
  referenceText: string | null;
  onContinue: () => void;
  transitioning: boolean;
  sessionId?: string;
  missionTitle?: string;
}

interface ObservationData {
  coverage: string;
  gaps: string;
  guidance_question: string;
}

export default function Exp04ObservationScreen({
  mission,
  onContinue,
  transitioning,
  sessionId,
  missionTitle,
}: ObservationScreenProps) {
  const [observation, setObservation] = useState<ObservationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [fallback, setFallback] = useState(false);

  // ── 加载 LI-02 分析结果 ──
  useEffect(() => {
    if (!sessionId) {
      setLoading(false);
      setFallback(true);
      return;
    }

    let cancelled = false;

    const fetchAnalysis = async () => {
      try {
        const res = await authedFetch(`/api/session/${sessionId}`);
        if (!res.ok) throw new Error("Failed to fetch session");

        const data = await res.json();
        if (cancelled) return;

        // 从 session 数据中读取 understanding_analysis
        const analysis = data.session?.understanding_analysis || data.understanding_analysis;

        if (analysis?.observation && analysis?.gaps) {
          setObservation({
            coverage: analysis.observation,
            gaps: analysis.gaps,
            guidance_question: analysis.guidance_question || "",
          });
        } else {
          // 没有分析结果 → fallback
          setFallback(true);
        }
      } catch (e) {
        console.warn("[OBSERVATION] Failed to load analysis:", e);
        if (!cancelled) setFallback(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    // 给 LI-02 一点时间完成分析
    const timer = setTimeout(fetchAnalysis, 800);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [sessionId]);

  // ── 默认观察内容（fallback） ──
  const defaultObservation: ObservationData = {
    coverage: "你已经提到了建立连接需要三次交互。",
    gaps: "不过，\u201C确认\u201D具体是通过什么机制实现的，还可以再深入想想。",
    guidance_question: "你说的\u201C确认\u201D\u2014\u2014具体是指什么？",
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-page flex flex-col items-center justify-center">
        <div className="text-center">
          <Sparkles size={32} className="text-[#F4B400] animate-pulse mx-auto mb-4" />
          <p className="text-base text-ink-muted">苹果果正在看你的理解……</p>
        </div>
      </div>
    );
  }

  const obs = fallback ? defaultObservation : observation!;

  return (
    <div className="min-h-screen bg-page flex flex-col">
      <div className="flex-1 overflow-auto">
        <div className="max-w-lg mx-auto px-5 pt-12">
          {/* 标题 */}
          <p className="text-xs text-ink-muted tracking-[2px] uppercase mb-4 font-medium">
            AppleGo Observation
          </p>

          <h1 className="text-[28px] font-bold text-ink-primary leading-[1.2] mb-3 tracking-tight">
            苹果果注意到
          </h1>

          <p className="text-base text-ink-muted leading-relaxed mb-10">
            这是苹果果对你刚才那段理解的一些观察——
          </p>

          {/* 已理解 */}
          <div className="mb-6">
            <div className="bg-surface rounded-2xl border border-border/50 p-5 sm:p-6 mb-4">
              <h3 className="text-sm font-semibold text-ink-primary mb-2 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
                你已经理解了
              </h3>
              <p className="text-base text-ink-secondary leading-relaxed">
                {obs.coverage}
              </p>
            </div>
          </div>

          {/* 还可以想想 */}
          <div className="mb-6">
            <div className="bg-surface rounded-2xl border border-border/50 p-5 sm:p-6 mb-4">
              <h3 className="text-sm font-semibold text-ink-primary mb-2 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#ffb84d]" />
                还有一个值得思考的地方
              </h3>
              <p className="text-base text-ink-secondary leading-relaxed">
                {obs.gaps}
              </p>
            </div>
          </div>

          {/* 开放问题 */}
          <div className="mb-6">
            <div className="bg-[#FFF6E8] rounded-2xl border border-[#FFF6E8] p-5 sm:p-6">
              <h3 className="text-sm font-semibold text-[#A96F00] mb-2">想一想</h3>
              <p className="text-base text-[#A96F00] leading-relaxed">
                {obs.guidance_question || "你觉得自己刚才的解释还有哪里可以补充？"}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 底部 */}
      <div className="border-t border-border/50 px-5 py-4">
        <div className="max-w-lg mx-auto">
          <button
            onClick={onContinue}
            disabled={transitioning}
            className="w-full h-14 rounded-xl bg-[#F4B400] text-white text-base font-semibold hover:bg-[#e5a800] transition-colors disabled:opacity-50"
          >
            继续
          </button>
        </div>
      </div>
    </div>
  );
}
