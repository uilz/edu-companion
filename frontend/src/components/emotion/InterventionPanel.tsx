"use client";

/**
 * InterventionPanel — 4 种干预工具面板
 *
 * Task #87 重建（原源文件丢失）
 *
 * 设计原则：
 *   - 干预不修改学习数据（Belief/FSRS/Scheduling）
 *   - 仅本地记录 + 事件流
 *   - 4 种类型：breathing / knowledge_breathing / cognitive_reappraisal / environment
 *   - "side" 字段标识是纯客户端还是有服务端联动
 */

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { authedFetch } from "@/lib/api/api";

interface InterventionType {
  value: string;
  label: string;
  emoji: string;
  side: "client" | "client+read_cards";
}

interface InterventionPanelProps {
  types: InterventionType[];
  onUsed: () => void;
}

const SIDE_LABELS: Record<string, string> = {
  client: "本地工具",
  "client+read_cards": "联动复习",
};

export function InterventionPanel({ types, onUsed }: InterventionPanelProps) {
  const [using, setUsing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeType, setActiveType] = useState<string | null>(null);
  const [duration, setDuration] = useState(180); // 默认 3 分钟
  const [notes, setNotes] = useState("");

  // 客户端干预引导
  const runClientGuidance = (type: InterventionType) => {
    if (type.value === "breathing") {
      // 4-7-8 呼吸法引导
      return {
        title: "4-7-8 呼吸法",
        steps: [
          "1. 用鼻子缓慢吸气，数 4 秒",
          "2. 屏住呼吸，数 7 秒",
          "3. 用嘴缓慢呼气，数 8 秒",
          "4. 重复 4-5 个循环",
        ],
        duration: 180,
      };
    } else if (type.value === "cognitive_reappraisal") {
      return {
        title: "认知重评 — 3 步法",
        steps: [
          "1. 识别当下的负面想法",
          "2. 问自己：这是事实还是解读？",
          "3. 换一个角度：如果朋友遇到同样情况，我会怎么建议？",
        ],
        duration: 120,
      };
    } else if (type.value === "environment") {
      return {
        title: "环境切换建议",
        steps: [
          "1. 离开当前座位 5 分钟",
          "2. 打开窗户或换到另一个房间",
          "3. 改变一下灯光（暖光 → 冷光，或反之）",
          "4. 播放白噪音/雨声/咖啡馆背景音",
        ],
        duration: 300,
      };
    } else if (type.value === "knowledge_breathing") {
      return {
        title: "知识呼吸 — 闪卡轻复习",
        steps: [
          "1. 选 5 张今天学过的卡片",
          "2. 快速浏览，不评分",
          "3. 把不熟悉的标记为「待复习」",
        ],
        duration: 240,
      };
    }
    return null;
  };

  const handleUse = async (type: InterventionType) => {
    setError(null);
    const guidance = runClientGuidance(type);

    if (guidance) {
      // 显示引导面板
      setActiveType(type.value);
      setDuration(guidance.duration);
      setNotes("");
      return;
    }

    // 无引导，直接记录
    await submitUsage(type.value, duration, "");
  };

  const submitUsage = async (type: string, dur: number, note: string) => {
    setUsing(type);
    try {
      const res = await authedFetch("/api/secretary/mood-stress/intervention", {
        method: "POST",
        body: JSON.stringify({
          intervention_type: type,
          duration_seconds: dur,
          notes: note,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail?.detail || `记录失败 (${res.status})`);
      }
      onUsed();
      setActiveType(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUsing(null);
    }
  };

  const activeGuidance = activeType
    ? runClientGuidance(types.find((t) => t.value === activeType) || types[0])
    : null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {types.map((type) => {
          const isLoading = using === type.value;
          return (
            <button
              key={type.value}
              onClick={() => handleUse(type)}
              disabled={!!using}
              className="text-left p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60 hover:border-indigo-300 hover:shadow-sm transition disabled:opacity-50"
            >
              <div className="flex items-start gap-3">
                <div className="text-3xl shrink-0">{type.emoji}</div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm text-gray-800 dark:text-gray-100">
                    {type.label}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {SIDE_LABELS[type.side] || type.side}
                  </div>
                </div>
                {isLoading && (
                  <Loader2 className="w-4 h-4 animate-spin text-indigo-500 shrink-0" />
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* 引导面板 */}
      {activeGuidance && activeType && (
        <div className="rounded-xl border border-indigo-200 dark:border-indigo-800 bg-indigo-50/50 dark:bg-indigo-950/30 p-4 space-y-3">
          <div className="font-medium text-indigo-700 dark:text-indigo-200 flex items-center gap-2">
            <span>📋</span>
            {activeGuidance.title}
          </div>
          <ol className="text-sm text-gray-700 dark:text-gray-200 space-y-1.5 pl-4 list-decimal">
            {activeGuidance.steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
          <div className="text-xs text-gray-500 pt-1 border-t border-indigo-100 dark:border-indigo-900/50">
            完成后请记录到干预日志（系统不会自动记录时长）。
          </div>
          <div className="flex items-end gap-2 pt-1">
            <div className="flex-1">
              <label className="text-xs text-gray-500 block mb-1">实际时长（秒）</label>
              <input
                type="number"
                min={0}
                max={3600}
                value={duration}
                onChange={(e) => setDuration(Math.max(0, Math.min(3600, Number(e.target.value))))}
                className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
            <button
              onClick={() => setActiveType(null)}
              disabled={!!using}
              className="px-3 py-1.5 rounded-lg text-sm text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              取消
            </button>
            <button
              onClick={() => submitUsage(activeType, duration, notes)}
              disabled={!!using}
              className="px-3 py-1.5 rounded-lg text-sm bg-indigo-500 hover:bg-indigo-600 text-white disabled:opacity-50 flex items-center gap-1"
            >
              {using && <Loader2 className="w-3 h-3 animate-spin" />}
              记录
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="text-sm text-rose-500 bg-rose-50 dark:bg-rose-950/30 rounded-lg px-3 py-2">
          {error}
        </div>
      )}
    </div>
  );
}

export default InterventionPanel;
