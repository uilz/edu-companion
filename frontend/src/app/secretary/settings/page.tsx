"use client";

import {
  Settings, Moon, Bell, RefreshCw, Check, BookOpen, Download, Trash2, Bot,
} from "lucide-react";
import { useState, useEffect } from "react";
import { useNotificationPreferenceStore } from "@/store/notification/notification-preferences";
import type { NotificationSource } from "@/store/notification/types";

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

const SOURCE_LABELS: Record<NotificationSource, string> = {
  secretary: "秘书引擎",
  context_switch: "上下文切换推荐",
  tree_recommendation: "知识树推荐",
  temp_recommendation: "会话推荐",
  job_update: "后台任务更新",
};

const SOURCE_EMOJIS: Record<NotificationSource, string> = {
  secretary: "🤖",
  context_switch: "🔀",
  tree_recommendation: "🌳",
  temp_recommendation: "📚",
  job_update: "⚙️",
};

const ALL_SOURCES: NotificationSource[] = [
  "secretary",
  "context_switch",
  "tree_recommendation",
  "temp_recommendation",
  "job_update",
];

export default function SecretarySettingsPage() {
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null);
  const [agentPrefs, setAgentPrefs] = useState({ confirm_mode: "smart", auto_jump_threshold: 0.85 });

  // ── 通知偏好 store ──
  const prefs = useNotificationPreferenceStore((s) => s.prefs);
  const updatePrefs = useNotificationPreferenceStore((s) => s.updatePrefs);
  const setSourceEnabled = useNotificationPreferenceStore((s) => s.setSourceEnabled);
  const resetPrefs = useNotificationPreferenceStore((s) => s.resetPrefs);

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [modRes, onbRes, prefRes, agentRes] = await Promise.all([
        fetch("/api/secretary/modules?user_id=default_user"),
        fetch("/api/secretary/onboarding?user_id=default_user"),
        fetch("/api/secretary/preferences?user_id=default_user"),
        fetch("/api/secretary/agent/preferences?user_id=default_user"),
      ]);
      if (modRes.ok) setModules(await modRes.json());
      if (onbRes.ok) setOnboarding(await onbRes.json());
      if (prefRes.ok) {
        const p = await prefRes.json();
        // 合并后端偏好到本地 store
        if (p.quiet_hours_start || p.quiet_hours_end || p.max_proactive_per_day !== undefined) {
          updatePrefs({
            quietHoursStart: p.quiet_hours_start || prefs.quietHoursStart,
            quietHoursEnd: p.quiet_hours_end || prefs.quietHoursEnd,
            dailyPushLimit: p.max_proactive_per_day ?? prefs.dailyPushLimit,
          });
        }
      }
      if (agentRes.ok) {
        const a = await agentRes.json();
        setAgentPrefs({ confirm_mode: a.confirm_mode, auto_jump_threshold: a.auto_jump_threshold });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleModuleToggle = async (name: string, enabled: boolean) => {
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

  // 保存偏好到后端
  const savePreferences = async () => {
    try {
      await fetch("/api/secretary/preferences?user_id=default_user", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          quiet_hours_start: prefs.quietHoursStart,
          quiet_hours_end: prefs.quietHoursEnd,
          max_proactive_per_day: prefs.dailyPushLimit,
        }),
      });
    } catch {
      // silently fail - localStorage already saved
    }
  };

  // 保存 Agent 偏好
  const saveAgentPrefs = async () => {
    try {
      await fetch("/api/secretary/agent/preferences?user_id=default_user", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(agentPrefs),
      });
    } catch {
      // silently fail
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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings size={16} className="text-[var(--color-text-muted)]" />
          <h1 className="text-lg font-semibold text-[var(--color-text)]">秘书设置</h1>
        </div>
        <button
          onClick={() => { resetPrefs(); savePreferences(); }}
          className="text-xs px-2 py-1 rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
        >
          重置偏好
        </button>
      </div>

      {/* ── 冷启动引导 ── */}
      {isColdStart && onboarding && (
        <div className="p-4 rounded-lg border border-[var(--color-accent)]/20 bg-[var(--color-accent)]/5 transition-transform">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen size={16} className="text-[var(--color-info)]" />
            <span className="text-sm font-semibold text-[var(--color-text)]">{onboarding.message}</span>
          </div>
          <div className="space-y-2">
            {onboarding.guide_steps.map((step) => (
              <div
                key={step.step}
                className={`flex items-center gap-2 text-xs p-2 rounded ${
                  step.done
                    ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
                    : step.step === onboarding.current_step
                    ? "bg-[var(--color-accent)]/10 text-[var(--color-text)]"
                    : "text-[var(--color-text-muted)]"
                }`}
              >
                <div className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold border border-current flex-shrink-0">
                  {step.done ? <Check size={10} /> : step.step}
                </div>
                <div className="flex-1">{step.title}</div>
                <span className="text-[9px] opacity-70">{step.done ? "✅" : "进行中"}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 模块管理（已有） ── */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-1.5">
          <Bell size={14} />
          模块管理
          <span className="text-[10px] text-[var(--color-text-muted)] font-normal ml-1">— 自定义秘书的功能模块</span>
        </h2>
        <div className="space-y-2">
          {modules.map((mod) => (
            <div
              key={mod.name}
              className={`p-3 rounded-lg border transition-colors ${
                mod.enabled ? "border-[var(--color-border)]" : "border-dashed border-[var(--color-border)] opacity-60"
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
                  onClick={() => handleModuleToggle(mod.name, !mod.enabled)}
                  disabled={saving === mod.name}
                  className={`relative w-10 h-5 rounded-full transition-colors flex-shrink-0 ${
                    saving === mod.name ? "opacity-50" : mod.enabled ? "bg-[var(--color-accent)]" : "bg-[var(--color-text-muted)]/30"
                  }`}
                >
                  <div
                    className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow-sm ${
                      mod.enabled ? "translate-x-5" : "translate-x-0.5"
                    }`}
                  />
                </button>
              </div>
              {mod.enabled && mod.stats && (
                <div className="mt-2 ml-8 flex gap-3 text-[10px] text-[var(--color-text-muted)]">
                  <span>运行 {mod.stats.total_runs} 次</span>
                  <span>提案 {mod.stats.total_proposals} 条</span>
                  {mod.stats.errors > 0 && <span className="text-[var(--color-error)]">错误 {mod.stats.errors} 次</span>}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Agent 助手 ── */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-1.5">
          <Bot size={14} />
          AI 秘书
          <span className="text-[10px] text-[var(--color-text-muted)] font-normal ml-1">— 控制悬浮球助手的行为</span>
        </h2>
        <div className="space-y-3">
          {/* 确认模式 */}
          <div className="p-3 rounded-lg border border-[var(--color-border)]">
            <div className="text-xs font-medium text-[var(--color-text)] mb-2">跳转确认模式</div>
            <div className="flex gap-2">
              {([
                ["smart", "智能判断", "高置信度自动跳转，低置信度询问"],
                ["always", "始终确认", "每次跳转前都需要确认"],
                ["never", "无需确认", "直接跳转，不询问"],
              ] as const).map(([mode, label, desc]) => (
                <button
                  key={mode}
                  onClick={() => {
                    setAgentPrefs((p) => ({ ...p, confirm_mode: mode }));
                    saveAgentPrefs();
                  }}
                  className={`flex-1 p-2 rounded-lg text-xs border text-left transition-colors ${
                    agentPrefs.confirm_mode === mode
                      ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-text)]"
                      : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-text-muted)]"
                  }`}
                >
                  <div className="font-medium">{label}</div>
                  <div className="text-[10px] opacity-70 mt-0.5">{desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* 自动跳转阈值 */}
          <div className="p-3 rounded-lg border border-[var(--color-border)]">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-medium text-[var(--color-text)]">自动跳转置信度阈值</div>
              <span className="text-xs font-semibold text-[var(--color-accent)]">{agentPrefs.auto_jump_threshold}</span>
            </div>
            <input
              type="range"
              min={0.5}
              max={1.0}
              step={0.05}
              value={agentPrefs.auto_jump_threshold}
              onChange={(e) => {
                setAgentPrefs((p) => ({ ...p, auto_jump_threshold: Number(e.target.value) }));
              }}
              onMouseUp={saveAgentPrefs}
              onTouchEnd={saveAgentPrefs}
              className="w-full accent-[var(--color-accent)]"
            />
            <div className="flex justify-between text-[10px] text-[var(--color-text-muted)] mt-1">
              <span>0.5 宽松</span>
              <span>1.0 严格</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── 通知偏好：通知源开关 ── */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-1.5">
          <Bell size={14} />
          通知偏好
          <span className="text-[10px] text-[var(--color-text-muted)] font-normal ml-1">— 控制哪些通知显示</span>
        </h2>
        <div className="space-y-1.5">
          {ALL_SOURCES.map((source) => (
            <div key={source} className="flex items-center justify-between p-2.5 rounded-lg border border-[var(--color-border)]">
              <div className="flex items-center gap-2">
                <span className="text-base">{SOURCE_EMOJIS[source]}</span>
                <span className="text-xs font-medium text-[var(--color-text)]">{SOURCE_LABELS[source]}</span>
              </div>
              <button
                onClick={() => setSourceEnabled(source, !prefs.sourceEnabled[source])}
                className={`relative w-9 h-4.5 rounded-full transition-colors flex-shrink-0 ${
                  prefs.sourceEnabled[source] ? "bg-[var(--color-accent)]" : "bg-[var(--color-text-muted)]/30"
                }`}
              >
                <div
                  className={`absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white transition-transform shadow-sm ${
                    prefs.sourceEnabled[source] ? "translate-x-[18px]" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* ── 优先级阈值 ── */}
      <div className="p-3 rounded-lg border border-[var(--color-border)]">
        <h2 className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-1.5 mb-3">
          <Bell size={14} />
          最低优先级
          <span className="text-[10px] text-[var(--color-text-muted)] font-normal ml-1">— 仅显示 ≥ 此优先级的通知</span>
        </h2>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min={1}
            max={5}
            value={prefs.priorityThreshold}
            onChange={(e) => updatePrefs({ priorityThreshold: Number(e.target.value) })}
            className="flex-1 accent-[var(--color-accent)]"
          />
          <span className="text-xs text-[var(--color-text-muted)] w-4 text-center">{prefs.priorityThreshold}</span>
          <div className="flex gap-1 text-[10px] text-[var(--color-text-muted)]">
            {[1, 2, 3, 4, 5].map((v) => (
              <button
                key={v}
                onClick={() => updatePrefs({ priorityThreshold: v })}
                className={`px-1.5 py-0.5 rounded ${
                  prefs.priorityThreshold === v
                    ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                    : "hover:text-[var(--color-text)]"
                }`}
              >
                {v === 1 ? "全部" : v === 5 ? "仅紧急" : v}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── 安静时段 ── */}
      <div className="p-3 rounded-lg border border-[var(--color-border)]">
        <h2 className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-1.5 mb-3">
          <Moon size={14} />
          安静时段
          <span className="text-[10px] text-[var(--color-text-muted)] font-normal ml-1">— 在此期间不推送通知</span>
        </h2>
        <div className="flex items-center gap-3">
          <input
            type="time"
            value={prefs.quietHoursStart}
            onChange={(e) => updatePrefs({ quietHoursStart: e.target.value })}
            className="px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
          />
          <span className="text-xs text-[var(--color-text-muted)]">至</span>
          <input
            type="time"
            value={prefs.quietHoursEnd}
            onChange={(e) => updatePrefs({ quietHoursEnd: e.target.value })}
            className="px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
          />
        </div>
      </div>

      {/* ── 每日推送上限 ── */}
      <div className="p-3 rounded-lg border border-[var(--color-border)]">
        <h2 className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-1.5 mb-3">
          <Bell size={14} />
          每日推送上限
          <span className="text-[10px] text-[var(--color-text-muted)] font-normal ml-1">— 0 = 无限</span>
        </h2>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min={0}
            max={20}
            value={prefs.dailyPushLimit}
            onChange={(e) => updatePrefs({ dailyPushLimit: Number(e.target.value) })}
            className="flex-1 accent-[var(--color-accent)]"
          />
          <span className="text-sm font-semibold text-[var(--color-accent)] w-6 text-center">{prefs.dailyPushLimit}</span>
          <span className="text-[10px] text-[var(--color-text-muted)]">条/天</span>
        </div>
      </div>

      {/* ── 保存按钮 ── */}
      <div className="flex items-center gap-2">
        <button
          onClick={savePreferences}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--color-accent)] text-white rounded-md hover:opacity-90 transition-opacity"
        >
          <RefreshCw size={12} />保存到服务器
        </button>
        <span className="text-[10px] text-[var(--color-text-muted)]">本地偏好已自动保存</span>
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
                const res = await fetch("/api/secretary/data/export?user_id=default_user");
                if (!res.ok) return;
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `secretary-data-${new Date().toISOString().split("T")[0]}.json`;
                a.click();
                URL.revokeObjectURL(url);
              } catch { /* silently fail */ }
            }}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
          >
            <Download size={14} />导出数据
          </button>
          <button
            onClick={() => {
              if (!window.confirm("确定要删除所有秘书数据吗？此操作不可撤销！")) return;
              fetch("/api/secretary/data/delete?user_id=default_user", { method: "DELETE" }).then((res) => {
                if (res.ok) alert("数据已删除");
              });
            }}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-[var(--color-error)]/30 text-[var(--color-error)] hover:bg-[var(--color-error)]/10 transition-colors"
          >
            <Trash2 size={14} />删除数据
          </button>
        </div>
      </div>
    </div>
  );
}