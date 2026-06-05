"use client";

import React, { useState } from "react";
import { Target, X, Calendar, TrendingUp, Star } from "lucide-react";
import { createGoal, listGoals, updateGoal } from "@/lib/api/learning-api";
import type { Goal } from "@/lib/api/learning-api";

interface GoalSettingModalProps {
  open: boolean;
  nodeId: string;
  nodeLabel: string;
  currentMastery: number;
  existingGoal?: Goal | null;
  onClose: () => void;
  onSaved: () => void;
}

/**
 * 知识作用与目标设定（10.6）
 * 对关键知识节点手动设定掌握度目标和预计达成时间。
 */
export default function GoalSettingModal({
  open,
  nodeId,
  nodeLabel,
  currentMastery,
  existingGoal,
  onClose,
  onSaved,
}: GoalSettingModalProps) {
  const [targetMastery, setTargetMastery] = useState(
    existingGoal?.target_mastery ?? 0.9
  );
  const [targetDate, setTargetDate] = useState(
    existingGoal?.target_date ?? ""
  );
  const [priority, setPriority] = useState(existingGoal?.priority ?? 2);
  const [notes, setNotes] = useState(existingGoal?.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  if (!open) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      if (existingGoal) {
        await updateGoal(existingGoal.id, {
          target_mastery: targetMastery,
          target_date: targetDate || undefined,
          priority,
          notes,
        });
      } else {
        await createGoal({
          node_id: nodeId,
          node_label: nodeLabel,
          target_mastery: targetMastery,
          target_date: targetDate || undefined,
          priority,
          notes,
        });
      }
      setSaved(true);
      setTimeout(() => {
        onSaved();
        onClose();
      }, 1200);
    } catch (e) {
      console.error("Failed to save goal:", e);
    } finally {
      setSaving(false);
    }
  };

  const daysRemaining = targetDate
    ? Math.ceil(
        (new Date(targetDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
      )
    : null;

  const gap = targetMastery - currentMastery;
  const dailyProgress = daysRemaining
    ? ((gap / daysRemaining) * 100).toFixed(1)
    : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="w-full max-w-md mx-4 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl shadow-xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[var(--color-accent)]/10 flex items-center justify-center text-[var(--color-accent)]">
              <Target size={16} />
            </div>
            <div>
              <span className="text-sm font-semibold">
                {existingGoal ? "更新目标" : "设定学习目标"}
              </span>
              <p className="text-[10px] text-[var(--color-text-muted)]">{nodeLabel}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">
            <X size={14} />
          </button>
        </div>

        {saved ? (
          <div className="flex flex-col items-center py-10 px-5">
            <div className="w-14 h-14 rounded-full bg-[var(--color-success)]/10 flex items-center justify-center mb-4">
              <Star size={28} className="text-[var(--color-success)]" />
            </div>
            <p className="text-base font-semibold text-[var(--color-text)]">
              目标已{existingGoal ? "更新" : "设定"}！
            </p>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">
              {targetMastery * 100}% 掌握 · {targetDate || "灵活期限"}
            </p>
          </div>
        ) : (
          <>
            {/* Current vs Target */}
            <div className="px-5 py-4 border-b border-[var(--color-border)]/50">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] text-[var(--color-text-muted)]">当前掌握度</span>
                <span className="text-[11px] font-medium text-[var(--color-accent)]">目标</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 rounded-full bg-[var(--color-surface-hover)] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-[var(--color-accent)]"
                    style={{ width: `${currentMastery * 100}%` }}
                  />
                </div>
                <span className="text-xs font-mono">{Math.round(currentMastery * 100)}%</span>
                <TrendingUp size={14} className="text-[var(--color-accent)]" />
                <div className="flex-1 h-2 rounded-full bg-[var(--color-surface-hover)] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-[var(--color-success)]"
                    style={{ width: `${targetMastery * 100}%` }}
                  />
                </div>
                <span className="text-xs font-mono">{Math.round(targetMastery * 100)}%</span>
              </div>
              {dailyProgress && (
                <p className="text-[10px] text-[var(--color-text-muted)] mt-2">
                  每日需提升 {dailyProgress}% 可达成目标
                </p>
              )}
            </div>

            {/* Form */}
            <div className="px-5 py-4 space-y-4">
              {/* Target mastery slider */}
              <div>
                <label className="flex items-center justify-between text-[11px] text-[var(--color-text-muted)] mb-1.5">
                  <span>目标掌握度</span>
                  <span className="font-mono font-medium text-[var(--color-text)]">
                    {Math.round(targetMastery * 100)}%
                  </span>
                </label>
                <input
                  type="range"
                  min={0.5}
                  max={1.0}
                  step={0.05}
                  value={targetMastery}
                  onChange={(e) => setTargetMastery(parseFloat(e.target.value))}
                  className="w-full h-1.5 rounded-full appearance-none bg-[var(--color-surface-hover)] accent-[var(--color-success)] cursor-pointer"
                />
                <div className="flex justify-between text-[9px] text-[var(--color-text-muted)] mt-0.5">
                  <span>50%</span>
                  <span>75%</span>
                  <span>100%</span>
                </div>
              </div>

              {/* Target date */}
              <div>
                <label className="flex items-center gap-1.5 text-[11px] text-[var(--color-text-muted)] mb-1.5">
                  <Calendar size={11} />
                  预计达成日期
                </label>
                <input
                  type="date"
                  value={targetDate}
                  onChange={(e) => setTargetDate(e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)]"
                />
                {daysRemaining && (
                  <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
                    距目标还有 {daysRemaining} 天
                  </p>
                )}
              </div>

              {/* Priority */}
              <div>
                <label className="text-[11px] text-[var(--color-text-muted)] mb-1.5 block">优先级</label>
                <div className="flex gap-1.5">
                  {[
                    { value: 1, label: "🔥 紧急" },
                    { value: 2, label: "⚡ 重要" },
                    { value: 3, label: "📌 一般" },
                    { value: 4, label: "📖 后续" },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setPriority(opt.value)}
                      className={`flex-1 px-2 py-1.5 rounded-lg text-[10px] font-medium border transition-all ${
                        priority === opt.value
                          ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                          : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-accent)]/30"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className="text-[11px] text-[var(--color-text-muted)] mb-1.5 block">备注</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="设定这个目标的原因..."
                  className="w-full h-16 px-2.5 py-1.5 text-xs rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] resize-none focus:outline-none focus:border-[var(--color-accent)]"
                />
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-[var(--color-border)]">
              <button
                onClick={onClose}
                className="px-3 py-1.5 rounded-lg text-xs text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-40 transition-opacity"
              >
                {saving ? "保存中..." : existingGoal ? "更新目标" : "设定目标"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
