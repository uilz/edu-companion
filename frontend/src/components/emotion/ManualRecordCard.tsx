"use client";

/**
 * ManualRecordCard — 手动记录心情/压力/能量弹窗
 *
 * Task #87 重建（原源文件丢失）
 *
 * 功能：
 *   - 11 种情绪标签多选
 *   - 压力/能量 1-10 滑块（可空）
 *   - 文本笔记（可空）
 *   - 关联事件 ID（高级字段，默认隐藏）
 *
 * 约束：
 *   - 不诊断情绪障碍
 *   - 弹窗内确认前不污染状态
 *   - 保存后通过 onSaved 回调刷新父组件
 */

import { useState, useEffect } from "react";
import { X, Loader2 } from "lucide-react";
import { authedFetch } from "@/lib/api/api";

interface EmotionTag {
  value: string;
  label: string;
  emoji: string;
  severity: "negative" | "neutral" | "positive";
}

interface ManualRecordCardProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

const DEFAULT_TAGS: EmotionTag[] = [
  { value: "frustration", label: "挫败", emoji: "😤", severity: "negative" },
  { value: "anxiety", label: "焦虑", emoji: "😰", severity: "negative" },
  { value: "confusion", label: "困惑", emoji: "🤔", severity: "neutral" },
  { value: "boredom", label: "无聊", emoji: "😴", severity: "negative" },
  { value: "overwhelm", label: "压力大", emoji: "😵", severity: "negative" },
  { value: "procrastination", label: "拖延", emoji: "🥱", severity: "negative" },
  { value: "motivated", label: "有动力", emoji: "💪", severity: "positive" },
  { value: "achievement", label: "成就感", emoji: "🎉", severity: "positive" },
  { value: "curious", label: "好奇", emoji: "🔍", severity: "positive" },
  { value: "calm", label: "平静", emoji: "😌", severity: "positive" },
  { value: "neutral", label: "中性", emoji: "📝", severity: "neutral" },
];

const SEVERITY_STYLES: Record<string, { selected: string; hover: string }> = {
  negative: {
    selected: "bg-rose-100 dark:bg-rose-900/40 border-rose-400 text-rose-700 dark:text-rose-200",
    hover: "hover:border-rose-300",
  },
  neutral: {
    selected: "bg-amber-100 dark:bg-amber-900/40 border-amber-400 text-amber-700 dark:text-amber-200",
    hover: "hover:border-amber-300",
  },
  positive: {
    selected: "bg-emerald-100 dark:bg-emerald-900/40 border-emerald-400 text-emerald-700 dark:text-emerald-200",
    hover: "hover:border-emerald-300",
  },
};

export function ManualRecordCard({ open, onClose, onSaved }: ManualRecordCardProps) {
  const [selected, setSelected] = useState<string[]>([]);
  const [pressure, setPressure] = useState<number | null>(null);
  const [energy, setEnergy] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [relatedEventIds, setRelatedEventIds] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // 重置表单（弹窗打开时）
  useEffect(() => {
    if (open) {
      setSelected([]);
      setPressure(null);
      setEnergy(null);
      setNote("");
      setRelatedEventIds("");
      setError(null);
      setShowAdvanced(false);
    }
  }, [open]);

  // ESC 关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !saving) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, saving, onClose]);

  if (!open) return null;

  const toggleTag = (value: string) => {
    setSelected((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    );
  };

  const canSave = selected.length > 0 || pressure !== null || energy !== null || note.trim() !== "";

  const save = async () => {
    if (!canSave || saving) return;
    setSaving(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        emotion_tags: selected,
      };
      if (pressure !== null) body.pressure_score = pressure;
      if (energy !== null) body.energy_score = energy;
      if (note.trim()) body.text_note = note.trim();
      if (relatedEventIds.trim()) {
        body.related_event_ids = relatedEventIds
          .split(/[,\s]+/)
          .filter((s) => s.length > 0);
      }
      const res = await authedFetch("/api/secretary/mood-stress/record", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail?.detail || `保存失败 (${res.status})`);
      }
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !saving) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-2xl bg-white dark:bg-gray-900 shadow-2xl border border-gray-200 dark:border-gray-700 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-800">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <span>💗</span>
            <span>现在感受如何？</span>
          </h2>
          <button
            onClick={onClose}
            disabled={saving}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 disabled:opacity-50"
            aria-label="关闭"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-5">
          {/* 情绪标签 */}
          <div>
            <label className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2 block">
              情绪标签 <span className="text-xs text-gray-400">（可多选）</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {DEFAULT_TAGS.map((tag) => {
                const isSel = selected.includes(tag.value);
                const style = SEVERITY_STYLES[tag.severity] || SEVERITY_STYLES.neutral;
                return (
                  <button
                    key={tag.value}
                    type="button"
                    onClick={() => toggleTag(tag.value)}
                    disabled={saving}
                    className={`px-2.5 py-1 rounded-full text-sm border transition ${
                      isSel
                        ? style.selected
                        : `bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 ${style.hover}`
                    }`}
                  >
                    <span className="mr-1">{tag.emoji}</span>
                    {tag.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 压力滑块 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-200">
                😓 压力
              </label>
              <span className="text-sm font-semibold text-rose-500 tabular-nums w-10 text-right">
                {pressure ?? "—"}
                {pressure !== null && <span className="text-xs text-gray-400">/10</span>}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={1}
                max={10}
                value={pressure ?? 5}
                onChange={(e) => setPressure(Number(e.target.value))}
                disabled={saving}
                className="flex-1 accent-rose-500"
              />
              <button
                type="button"
                onClick={() => setPressure(null)}
                disabled={saving || pressure === null}
                className="text-xs text-gray-400 hover:text-gray-600 disabled:opacity-30"
              >
                清除
              </button>
            </div>
          </div>

          {/* 能量滑块 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-200">
                ⚡ 能量
              </label>
              <span className="text-sm font-semibold text-emerald-500 tabular-nums w-10 text-right">
                {energy ?? "—"}
                {energy !== null && <span className="text-xs text-gray-400">/10</span>}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={1}
                max={10}
                value={energy ?? 5}
                onChange={(e) => setEnergy(Number(e.target.value))}
                disabled={saving}
                className="flex-1 accent-emerald-500"
              />
              <button
                type="button"
                onClick={() => setEnergy(null)}
                disabled={saving || energy === null}
                className="text-xs text-gray-400 hover:text-gray-600 disabled:opacity-30"
              >
                清除
              </button>
            </div>
          </div>

          {/* 文本笔记 */}
          <div>
            <label className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2 block">
              想说点什么 <span className="text-xs text-gray-400">（可选）</span>
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              disabled={saving}
              maxLength={500}
              rows={3}
              placeholder="今天被某个题目卡住了，有点挫败..."
              className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
            <div className="text-xs text-gray-400 text-right mt-1">{note.length}/500</div>
          </div>

          {/* 高级字段 (默认隐藏) */}
          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              disabled={saving}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              {showAdvanced ? "▾" : "▸"} 高级设置（关联事件 ID）
            </button>
            {showAdvanced && (
              <input
                type="text"
                value={relatedEventIds}
                onChange={(e) => setRelatedEventIds(e.target.value)}
                disabled={saving}
                placeholder="多个用空格或逗号分隔"
                className="mt-2 w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-1.5 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            )}
          </div>

          {error && (
            <div className="text-sm text-rose-500 bg-rose-50 dark:bg-rose-950/30 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-100 dark:border-gray-800">
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 rounded-lg text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={save}
            disabled={!canSave || saving}
            className="px-4 py-2 rounded-lg text-sm bg-indigo-500 hover:bg-indigo-600 text-white disabled:opacity-50 flex items-center gap-1"
          >
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

export default ManualRecordCard;
