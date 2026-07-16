// ============================================================
// EXP-04 V2 · SELF VALIDATION Screen
//
// "试着讲给苹果果听"
//   - 大字输入框
//   - 顶部温柔引导
//   - 提交后触发 LI-02 Understanding Analysis（后端）
//   - 无参考对比（对比移到了 OBSERVATION 屏）
// ============================================================

"use client";

import { useState, useCallback } from "react";
import { Loader2, AlertCircle } from "lucide-react";
import { authedFetch } from "@/lib/api/api";
import type { Exp04State } from "@/lib/exp04/types";

interface SelfValidationScreenProps {
  engine: any;
  currentState: Exp04State;
  mission: { title: string; steps: { order: number; description: string; type: string }[] } | null;
  referenceText: string | null;
  onBackToLearn: () => Promise<void>;
  onContinue: () => Promise<void>;
  transitioning: boolean;
  sessionId?: string;
  missionTitle?: string;
}

export default function Exp04SelfValidationScreen({
  mission,
  referenceText,
  onBackToLearn,
  onContinue,
  transitioning,
  sessionId,
  missionTitle,
}: SelfValidationScreenProps) {
  const [text, setText] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async () => {
    if (!text.trim() || analyzing || transitioning) return;

    setAnalyzing(true);
    setError(null);

    try {
      // 触发 LI-02 Understanding Analysis（后端分析，结果存 backend）
      if (sessionId) {
        await authedFetch(`/api/session/${sessionId}/analyze-understanding`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text.trim() }),
        });
      }
    } catch (e) {
      console.warn("[SELF_VALIDATION] LI-02 analysis failed, continuing anyway:", e);
    }

    setAnalyzing(false);
    onContinue();
  }, [text, analyzing, transitioning, sessionId, onContinue]);

  return (
    <div className="min-h-screen bg-page flex flex-col">
      <div className="flex-1 overflow-auto">
        <div className="max-w-lg mx-auto px-5 pt-12">
          {/* 引导文案 */}
          <p className="text-xs text-ink-muted tracking-[2px] uppercase mb-4 font-medium">
            Self Validation
          </p>

          <h1 className="text-[28px] font-bold text-ink-primary leading-[1.2] mb-3 tracking-tight">
            试着讲给苹果果听
          </h1>

          <p className="text-base text-ink-muted leading-relaxed mb-8">
            不用照着书说。用自己的话解释{missionTitle || "今天学的内容"}，让苹果果听听你的理解。
          </p>

          {/* 大输入框 */}
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={`把你对${missionTitle || "今天的内容"}的理解写下来……`}
            disabled={analyzing || transitioning}
            className="w-full min-h-[240px] p-5 rounded-2xl bg-white border border-border/60 text-base leading-relaxed text-ink-primary resize-none outline-none focus:border-[#F4B400] transition-colors placeholder:text-ink-muted/50"
          />

          {error && (
            <div className="mt-3 flex items-center gap-2 text-red-500 text-sm">
              <AlertCircle size={14} />
              {error}
            </div>
          )}
        </div>
      </div>

      {/* 底部 */}
      <div className="border-t border-border/50 px-5 py-4">
        <div className="max-w-lg mx-auto flex gap-3">
          <button
            onClick={onBackToLearn}
            disabled={analyzing || transitioning}
            className="flex-1 h-14 rounded-xl bg-white border border-border/60 text-ink-primary text-base font-medium hover:bg-surface transition-colors disabled:opacity-40"
          >
            再看看
          </button>
          <button
            onClick={handleSubmit}
            disabled={!text.trim() || analyzing || transitioning}
            className="flex-1 h-14 rounded-xl bg-[#F4B400] text-white text-base font-semibold hover:bg-[#e5a800] transition-colors disabled:opacity-40"
          >
            {analyzing ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 size={18} className="animate-spin" />
                苹果果正在看…
              </span>
            ) : (
              "写好了"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
