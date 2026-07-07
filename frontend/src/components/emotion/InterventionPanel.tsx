"use client";

/**
 * MoodStress 干预工具面板
 *
 * 4 种工具：呼吸引导 / 知识呼吸 / 认知重评 / 环境切换
 * 设计原则：用户手动触发；不修改学习数据；仅本地记录 + 事件流
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Wind, Brain, Palette, Sparkles, Loader2 } from "lucide-react";
import { authedFetch } from "@/lib/api/api";

interface InterventionType {
  value: string;
  label: string;
  emoji: string;
  side: string;
}

interface Props {
  types: InterventionType[];
  onUsed: () => void;
}

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  breathing: Wind,
  knowledge_breathing: Sparkles,
  cognitive_reappraisal: Brain,
  environment: Palette,
};

const BREATH_STEPS = [
  { phase: "吸气", duration: 4, color: "from-info/30 to-info/40" },
  { phase: "屏息", duration: 4, color: "from-accent/30 to-accent/40" },
  { phase: "呼气", duration: 6, color: "from-success/30 to-success/40" },
  { phase: "屏息", duration: 2, color: "from-accent/30 to-accent/40" },
];

const COG_REAPPRAISAL_PROMPTS = [
  "发生了什么？(客观事实，不评判)",
  "我的想法是什么？",
  "有没有其他解释？",
  "我能做什么？(微小、可执行的步骤)",
];

const ENV_THEMES: Array<{ value: string; label: string; gradient: string }> = [
  { value: "default", label: "默认", gradient: "from-surface to-divider" },
  { value: "warm", label: "暖阳", gradient: "from-warning/20 to-warning/30" },
  { value: "cool", label: "冷月", gradient: "from-info/20 to-accent/30" },
  { value: "forest", label: "森林", gradient: "from-success/20 to-success/30" },
  { value: "sunset", label: "日落", gradient: "from-danger/20 to-danger/30" },
];

export function InterventionPanel({ types, onUsed }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [breathing, setBreathing] = useState(false);
  const [breathStep, setBreathStep] = useState(0);
  const [cogReappraisal, setCogReappraisal] = useState(false);
  const [cogAnswers, setCogAnswers] = useState<string[]>(["", "", "", ""]);
  const [envOpen, setEnvOpen] = useState(false);
  const [currentTheme, setCurrentTheme] = useState("default");

  // 记录到后端
  const log = async (t: string, duration = 0) => {
    setBusy(t);
    try {
      const res = await authedFetch("/api/secretary/mood-stress/intervention", {
        method: "POST",
        body: JSON.stringify({
          intervention_type: t,
          duration_seconds: duration,
        }),
      });
      if (res.ok) onUsed();
    } catch {
      // 静默失败
    } finally {
      setBusy(null);
    }
  };

  // 呼吸引导
  const startBreathing = () => {
    setBreathing(true);
    setBreathStep(0);
    let total = 0;
    const run = () => {
      if (total >= 4) {
        // 约 1 分钟，简化处理
        setBreathing(false);
        log("breathing", 60);
        return;
      }
      setBreathStep(total % BREATH_STEPS.length);
      total += 1;
      setTimeout(run, 1000);
    };
    setTimeout(run, 1000);
  };

  // 知识呼吸
  const startKnowledgeBreathing = () => {
    log("knowledge_breathing", 30);
    // 跳转 FlashCard 复习（复用入口）
    router.push("/practice/review?source=mood_stress");
  };

  // 认知重评
  const startCogReappraisal = () => {
    setCogReappraisal(true);
    setCogAnswers(["", "", "", ""]);
  };

  const submitCogReappraisal = () => {
    log("cognitive_reappraisal", 120);
    setCogReappraisal(false);
    setCogAnswers(["", "", "", ""]);
  };

  // 环境切换
  const applyEnvTheme = (theme: string) => {
    setCurrentTheme(theme);
    if (typeof document !== "undefined") {
      document.documentElement.dataset.theme = theme;
    }
    log("environment", 0);
    setEnvOpen(false);
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {types.map((t) => {
          const Icon = ICON_MAP[t.value] || Wind;
          const disabled = busy !== null;
          return (
            <button
              key={t.value}
              onClick={() => {
                if (t.value === "breathing") startBreathing();
                else if (t.value === "knowledge_breathing") startKnowledgeBreathing();
                else if (t.value === "cognitive_reappraisal") startCogReappraisal();
                else if (t.value === "environment") setEnvOpen(true);
              }}
              disabled={disabled}
              className="p-3 rounded-xl border border dark:border bg-white dark:bg-surface/60 hover:border-accent/30 hover:shadow-sm transition text-left disabled:opacity-50"
            >
              <div className="text-2xl mb-1">{t.emoji}</div>
              <div className="text-sm font-medium text dark:text">{t.label}</div>
              {busy === t.value && (
                <Loader2 className="w-3 h-3 animate-spin inline mt-1 text-accent" />
              )}
            </button>
          );
        })}
      </div>

      {/* 呼吸动画 */}
      {breathing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="text-center text-white">
            <div
              className={`w-48 h-48 rounded-full bg-gradient-to-br ${
                BREATH_STEPS[breathStep].color
              } mx-auto flex items-center justify-center text-3xl font-bold animate-pulse`}
            >
              {BREATH_STEPS[breathStep].phase}
            </div>
            <p className="mt-6 text-sm opacity-80">跟随圆圈呼吸 5 分钟</p>
            <button
              onClick={() => {
                setBreathing(false);
                log("breathing", 30);
              }}
              className="mt-4 text-xs underline opacity-60"
            >
              结束
            </button>
          </div>
        </div>
      )}

      {/* 认知重评 */}
      {cogReappraisal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setCogReappraisal(false)}>
          <div
            className="w-full max-w-md rounded-2xl bg-white dark:bg-surface p-5 space-y-3"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="font-semibold flex items-center gap-2"><Brain className="w-4 h-4" /> 认知重评引导</h3>
            <p className="text-xs text-muted">仅提供框架，请填写你自己的想法</p>
            {COG_REAPPRAISAL_PROMPTS.map((p, i) => (
              <div key={i}>
                <label className="text-xs text-muted dark:text-muted">{i + 1}. {p}</label>
                <textarea
                  value={cogAnswers[i]}
                  onChange={(e) => {
                    const next = [...cogAnswers];
                    next[i] = e.target.value;
                    setCogAnswers(next);
                  }}
                  rows={2}
                  className="w-full mt-1 px-3 py-2 rounded border border dark:border  bg-white dark:bg-surface text-sm resize-none"
                />
              </div>
            ))}
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setCogReappraisal(false)} className="px-3 py-1.5 text-sm rounded text-muted">取消</button>
              <button onClick={submitCogReappraisal} className="px-3 py-1.5 text-sm rounded bg-accent text-white">完成</button>
            </div>
          </div>
        </div>
      )}

      {/* 环境切换 */}
      {envOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setEnvOpen(false)}>
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-surface p-5 space-y-3" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold flex items-center gap-2"><Palette className="w-4 h-4" /> 选择主题色调</h3>
            <div className="grid grid-cols-3 gap-2">
              {ENV_THEMES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => applyEnvTheme(t.value)}
                  className={`p-3 rounded-xl border ${
                    currentTheme === t.value ? "border-accent" : "border "
                  }`}
                >
                  <div className={`h-12 rounded bg-gradient-to-br ${t.gradient}`} />
                  <div className="text-xs mt-1 text-center">{t.label}</div>
                </button>
              ))}
            </div>
            <p className="text-xs text-muted">仅前端 UI 变化，不修改学习数据</p>
          </div>
        </div>
      )}
    </div>
  );
}
