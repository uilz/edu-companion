"use client";

/**
 * MoodStress 手动记录卡片
 *
 * 入口：点击"现在记录"按钮 → 弹出此卡片
 * 行为：选择情绪标签 + 压力自评 + 能量自评 + 备注 → 提交到后端
 * 设计：手动优先（仪表盘顶部展示）
 */

import { useEffect, useState } from"react";
import { X, Save, Loader2 } from"lucide-react";
import { authedFetch } from"@/lib/api/api";

interface Constants {
  emotion_tags: Array<{ value: string; label: string; emoji: string; severity: string }>;
  intervention_types: Array<{ value: string; label: string; emoji: string; side: string }>;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

const SEVERITY_COLOR: Record<string, string> = {
  negative: "border-danger/30 dark:border-danger/20 bg-danger/10 dark:bg-danger/10",
  positive: "border-success/30 dark:border-success/70 bg-success/10 dark:bg-success/10",
  neutral: "border-divider dark:dark:border-divider bg-surface dark:dark:bg-surface-hover",
};

export function ManualRecordCard({ open, onClose, onSaved }: Props) {
  const [tags, setTags] = useState<string[]>([]);
  const [pressure, setPressure] = useState<number | null>(null);
  const [energy, setEnergy] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [constants, setConstants] = useState<Constants | null>(null);

  useEffect(() => {
    if (open && !constants) {
      authedFetch("/api/secretary/mood-stress/constants")
        .then((r) => r.json())
        .then(setConstants)
        .catch(() => setError("加载情绪标签失败"));
    }
  }, [open, constants]);

  if (!open) return null;

  const toggleTag = (v: string) => {
    setTags((prev) => (prev.includes(v) ? prev.filter((t) => t !== v) : [...prev, v]));
  };

  const submit = async () => {
    if (tags.length === 0 && pressure === null && energy === null && !note.trim()) {
      setError("请至少填写一项");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await authedFetch("/api/secretary/mood-stress/record", {
        method: "POST",
        body: JSON.stringify({
          emotion_tags: tags,
          pressure_score: pressure,
          energy_score: energy,
          text_note: note.trim() || null,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text.slice(0, 200));
      }
      setTags([]);
      setPressure(null);
      setEnergy(null);
      setNote("");
      onSaved();
      onClose();
    } catch (e: unknown) {
      const err = e as Error;
      setError(err.message || "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-2xl bg-white dark:bg-surface shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border  dark:border">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🌊</span>
            <h2 className="text-lg font-semibold">现在记录一下</h2>
          </div>
          <button onClick={onClose} className="text-muted hover:text-muted">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-5 max-h-[70vh] overflow-y-auto">
          {/* 情绪标签 */}
          <div>
            <label className="text-sm font-medium text dark:text block mb-2">
              当前心情（可多选）
            </label>
            <div className="flex flex-wrap gap-2">
              {constants?.emotion_tags.map((t) => {
                const selected = tags.includes(t.value);
                return (
                  <button
                    key={t.value}
                    onClick={() => toggleTag(t.value)}
                    className={`px-3 py-1.5 rounded-full border text-sm transition ${
                      selected
                        ? "border-accent bg-accent/20 dark:bg-accent/10 text-accent dark:text-accent"
                        : SEVERITY_COLOR[t.severity] +
                          " hover:border-accent/30"
                    }`}
                  >
                    <span className="mr-1">{t.emoji}</span>
                    {t.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 压力自评 */}
          <div>
            <label className="text-sm font-medium text dark:text block mb-2">
              压力自评：<span className="font-bold text-danger">{pressure ?? "—"}</span> / 10
            </label>
            <div className="flex gap-1">
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                <button
                  key={n}
                  onClick={() => setPressure(pressure === n ? null : n)}
                  className={`flex-1 h-9 rounded text-sm font-medium transition ${
                    pressure !== null && n <= pressure
                      ? "bg-danger/80 text-white"
                      : "bg-surface dark:bg-surface-hover text-muted hover:bg-danger/10"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          {/* 能量自评 */}
          <div>
            <label className="text-sm font-medium text dark:text block mb-2">
              能量自评：<span className="font-bold text-success">{energy ?? "—"}</span> / 10
            </label>
            <div className="flex gap-1">
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                <button
                  key={n}
                  onClick={() => setEnergy(energy === n ? null : n)}
                  className={`flex-1 h-9 rounded text-sm font-medium transition ${
                    energy !== null && n <= energy
                      ? "bg-success/80 text-white"
                      : "bg-surface dark:bg-surface-hover text-muted hover:bg-success/20"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          {/* 备注 */}
          <div>
            <label className="text-sm font-medium text dark:text block mb-2">
              备注（可选）
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={500}
              rows={2}
              placeholder="今天状态有点疲惫，可能需要早点睡…"
              className="w-full px-3 py-2 rounded-lg border border dark:border  bg-white dark:bg-surface text-sm resize-none focus:outline-none focus:border-accent"
            />
          </div>

          {error && (
            <div className="text-sm text-danger bg-danger/10 dark:bg-danger/10 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
        </div>

        <div className="px-5 py-3 border-t border  dark:border flex items-center justify-end gap-2 bg-surface dark:bg-surface/40">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm text-muted dark:text-muted hover:bg-surface dark:hover:bg-surface-hover"
          >
            取消
          </button>
          <button
            onClick={submit}
            disabled={submitting}
            className="px-4 py-2 rounded-lg text-sm bg-accent hover:bg-accent-hover text-white flex items-center gap-1.5 disabled:opacity-50"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
