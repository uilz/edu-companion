"use client";

import { Settings, Moon, Volume2, Bell, RefreshCw, ChevronRight, Check, BookOpen, Download, Trash2 } from "lucide-react";
import { useState, useEffect } from "react";

interface ModuleInfo {
  name: string;
  display_name: string;
  emoji: string;
  description: string;
  enabled: boolean;
  default_enabled: boolean;
  stats: { total_runs: number; total_proposals: number; errors: number };
}

interface OnboardingStatus {
  is_cold_start: boolean;
  total_nodes: number;
  guide_steps: { step: number; title: string; description: string; link: string; done: boolean }[];
  current_step: number;
  message: string;
}

export default function SecretarySettingsPage() {
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  // 配置
  const [quietHoursStart, setQuietHoursStart] = useState("22:00");
  const [quietHoursEnd, setQuietHoursEnd] = useState("08:00");
  const [maxProactive, setMaxProactive] = useState(5);

  // 冷启动引导
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null);

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [modRes, onbRes, prefRes] = await Promise.all([
        fetch("/api/secretary/modules?user_id=default_user"),
        fetch("/api/secretary/onboarding?user_id=default_user"),
        fetch("/api/secretary/preferences?user_id=default_user"),
      ]);
      if (modRes.ok) {
        const data = await modRes.json();
        setModules(data);
      }
      if (onbRes.ok) {
        setOnboarding(await onbRes.json());
      }
      if (prefRes.ok) {
        const prefs = await prefRes.json();
        setQuietHoursStart(prefs.quiet_hours_start || "22:00");
        setQuietHoursEnd(prefs.quiet_hours_end || "08:00");
        setMaxProactive(prefs.max_proactive_per_day || 5);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (name: string, enabled: boolean) => {
    setSaving(name);
    try {
      const res = await fetch(`/api/secretary/modules/toggle?name=${name}&enabled=${enabled}&user_id=default_user`, {
        method: "POST",
      });
      if (res.ok) {
        setModules((prev) => prev.map((m) => (m.name === name ? { ...m, enabled } : m)));
      }
    } finally {
      setSaving(null);
    }
  };

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-6 text-center text-sm text-[var(--color-text-muted)]">
        加载中…
      </div>
    );
  }

  const isColdStart = onboarding?.is_cold_start;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* ── 页面标题 ── */}
      <div className="flex items-center gap-2">
        <Settings size={16} className="text-[var(--color-text-muted)]" />
        <h1 className="text-lg font-bold text-[var(--color-text)]">秘书设置</h1>
      </div>

      {/* ── 冷启动引导 ── */}
      {isColdStart && onboarding && (
        <div className="p-4 rounded-lg border border-blue-500/20 bg-blue-500/5">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen size={16} className="text-blue-400" />
            <span className="text-sm font-semibold text-[var(--color-text)]">{onboarding.message}</span>
          </div>
          <div className="space-y-2">
            {onboarding.guide_steps.map((step) => (
              <div
                key={step.step}
                className={`flex items-center gap-2 text-xs p-2 rounded ${
                  step.done
                    ? "bg-green-500/10 text-green-400"
                    : step.step === onboarding.current_step
                    ? "bg-blue-500/10 text-[var(--color-text)]"
                    : "text-[var(--color-text-muted)]"
                }`}
              >
                <div className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border border-current flex-shrink-0">
                  {step.done ? <Check size={10} /> : step.step}
                </div>
                <div className="flex-1">{step.title}</div>
                <span className="text-[9px] opacity-70">{step.done ? "✅" : "进行中"}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 模块开关 ── */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-1.5">
          <Bell size={14} />
          模块管理
          <span className="text-[10px] text-[var(--color-text-muted)] font-normal ml-1">
            — 自定义秘书的功能模块
          </span>
        </h2>

        <div className="space-y-2">
          {modules.map((mod) => (
            <div
              key={mod.name}
              className={`p-3 rounded-lg border transition-colors ${
                mod.enabled
                  ? "border-[var(--color-border)]"
                  : "border-dashed border-[var(--color-border)] opacity-60"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{mod.emoji}</span>
                  <div>
                    <div className="text-sm font-medium text-[var(--color-text)]">{mod.display_name}</div>
                    <div className="text-[11px] text-[var(--color-text-muted)]">{mod.description}</div>
                  </div>
                </div>
                <button
                  onClick={() => handleToggle(mod.name, !mod.enabled)}
                  disabled={saving === mod.name}
                  className={`relative w-10 h-5 rounded-full transition-colors ${
                    saving === mod.name ? "opacity-50" : mod.enabled ? "bg-[var(--color-accent)]" : "bg-gray-500/30"
                  }`}
                >
                  <div
                    className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow-sm ${
                      mod.enabled ? "translate-x-5" : "translate-x-0.5"
                    }`}
                  />
                </button>
              </div>

              {/* 模块统计 */}
              {mod.enabled && mod.stats && (
                <div className="mt-2 ml-8 flex gap-3 text-[10px] text-[var(--color-text-muted)]">
                  <span>运行 {mod.stats.total_runs} 次</span>
                  <span>提案 {mod.stats.total_proposals} 条</span>
                  {mod.stats.errors > 0 && <span className="text-red-400">错误 {mod.stats.errors} 次</span>}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── 安静时段 ── */}
      <div className="p-3 rounded-lg border border-[var(--color-border)]">
        <h2 className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-1.5 mb-3">
          <Moon size={14} />
          安静时段
        </h2>
        <div className="flex items-center gap-3">
          <input
            type="time"
            value={quietHoursStart}
            onChange={(e) => setQuietHoursStart(e.target.value)}
            className="px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
          />
          <span className="text-xs text-[var(--color-text-muted)]">至</span>
          <input
            type="time"
            value={quietHoursEnd}
            onChange={(e) => setQuietHoursEnd(e.target.value)}
            className="px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
          />
          <span className="text-[10px] text-[var(--color-text-muted)] ml-1">
            在此期间不推送建议
          </span>
        </div>
      </div>

      {/* ── 每日上限 ── */}
      <div className="p-3 rounded-lg border border-[var(--color-border)]">
        <h2 className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-1.5 mb-3">
          <Bell size={14} />
          每日主动推送上限
        </h2>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min={1}
            max={10}
            value={maxProactive}
            onChange={(e) => setMaxProactive(Number(e.target.value))}
            className="flex-1 accent-[var(--color-accent)]"
          />
          <span className="text-sm font-bold text-[var(--color-accent)] w-8 text-center">{maxProactive}</span>
          <span className="text-[10px] text-[var(--color-text-muted)]">条/天</span>
        </div>
      </div>

      {/* ── 说明 ── */}
      <div className="text-[10px] text-[var(--color-text-muted)] p-3 rounded-lg border border-dashed border-[var(--color-border)]">
        <p className="flex items-center gap-1">
          <RefreshCw size={10} />
          设置自动保存。模块开启后，秘书系统将在 10 分钟周期内自动检查并推送建议。
        </p>
      </div>

      {/* ── 数据管理 ── */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-1.5">
          <Download size={14} />
          数据管理
        </h2>
        <div className="flex gap-2">
          <button
            onClick={async () => {
              try {
                const res = await fetch(
                  "/api/secretary/data/export?user_id=default_user"
                );
                if (!res.ok) return;
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `secretary-data-${new Date().toISOString().split("T")[0]}.json`;
                a.click();
                URL.revokeObjectURL(url);
              } catch {
                // silently fail
              }
            }}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
          >
            <Download size={14} />
            导出数据
          </button>
          <button
            onClick={() => {
              if (
                !window.confirm(
                  "确定要删除所有秘书数据吗？此操作不可撤销！"
                )
              ) return;
              fetch(
                "/api/secretary/data/delete?user_id=default_user",
                { method: "DELETE" }
              ).then((res) => {
                if (res.ok) {
                  alert("数据已删除");
                }
              });
            }}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <Trash2 size={14} />
            删除数据
          </button>
        </div>
      </div>
    </div>
  );
}
