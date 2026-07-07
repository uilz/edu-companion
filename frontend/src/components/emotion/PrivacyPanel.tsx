"use client";

import { useState, useEffect } from "react";
import { ShieldCheck, Settings, Loader2 } from "lucide-react";
import { authedFetch } from "@/lib/api/api";

function Switch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
        checked ? "bg-accent" : "bg-surface-hover dark:bg-surface-hover"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
          checked ? "translate-x-6" : "translate-x-1"
        }`}
      />
    </button>
  );
}

export default function PrivacyPanel({
  prefs,
  onUpdated,
}: {
  prefs: Record<string, unknown>;
  onUpdated: () => void;
}) {
  const [local, setLocal] = useState<Record<string, unknown>>(prefs);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLocal(prefs);
  }, [prefs]);

  const save = async () => {
    setSaving(true);
    try {
      const res = await authedFetch("/api/secretary/mood-stress/prefs", {
        method: "PUT",
        body: JSON.stringify(local),
      });
      if (res.ok) onUpdated();
    } finally {
      setSaving(false);
    }
  };

  const setFlag = (key: string, value: boolean) => {
    setLocal((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border dark:border bg-white dark:bg-surface/60 p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-success" />
          隐私与控制
        </h2>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">手动记录提醒</div>
              <div className="text-xs text-muted">默认关闭，需用户主动开启</div>
            </div>
            <Switch
              checked={Boolean(local.reminder_enabled)}
              onChange={(v) => setFlag("reminder_enabled", v)}
            />
          </div>

          <div className="border-t border  dark:border pt-3">
            <div className="text-xs text-muted mb-2">行为信号采集（可逐项关闭）</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {[
                ["auto_collect_task_switch", "频繁切换任务"],
                ["auto_collect_stay_duration", "同一知识点停留异常"],
                ["auto_collect_error_rate", "练习错误率突增"],
                ["auto_collect_undo", "连续撤销/修改"],
                ["auto_collect_session_anomaly", "会话时长异常"],
                ["auto_collect_flashcard_failure", "卡片困难比例上升"],
                ["auto_collect_voice_features", "语音特征（默认关闭）"],
              ].map(([key, label]) => (
                <div key={key} className="flex items-center justify-between text-sm">
                  <span>{label}</span>
                  <Switch
                    checked={Boolean(local[key])}
                    onChange={(v) => setFlag(key as string, v)}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="border-t border  dark:border pt-3">
            <div className="text-xs text-muted mb-2">输出控制</div>
            <div className="space-y-2">
              {[
                ["output_to_planning", "向规划模块输出压力/能量"],
                ["output_to_conversation", "向对话模块输出情绪状态"],
                ["output_to_language_room", "向语言房间输出"],
              ].map(([key, label]) => (
                <div key={key} className="flex items-center justify-between text-sm">
                  <span>{label}</span>
                  <Switch
                    checked={Boolean(local[key])}
                    onChange={(v) => setFlag(key as string, v)}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="border-t border  dark:border pt-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">数据保留期</div>
              <div className="text-xs text-muted">默认 90 天，到期自动清理</div>
            </div>
            <select
              value={Number(local.data_retention_days) || 90}
              onChange={(e) =>
                setLocal((prev) => ({ ...prev, data_retention_days: Number(e.target.value) }))
              }
              className="px-2 py-1 rounded border border dark:border  bg-white dark:bg-surface text-sm"
            >
              <option value={30}>30 天</option>
              <option value={90}>90 天</option>
              <option value={180}>180 天</option>
              <option value={365}>1 年</option>
            </select>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border  dark:border flex justify-end">
          <button
            onClick={save}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-accent hover:bg-accent-hover text-white text-sm disabled:opacity-50 flex items-center gap-1"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Settings className="w-4 h-4" />}
            保存设置
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border dark:border bg-white dark:bg-surface/60 p-5 text-sm space-y-2 text-muted dark:text-muted">
        <p className="font-medium text dark:text">🛡️ 系统边界（不做什么）</p>
        <ul className="list-disc pl-5 space-y-1 text-xs">
          <li>不诊断情绪障碍 / 不替代专业心理咨询</li>
          <li>不自动评判/打分/评价用户状态</li>
          <li>干预工具不修改学习数据（Belief/FSRS/Scheduling）</li>
          <li>行为信号仅提示，不自动触发任何学习数据修改</li>
          <li>语音特征默认关闭，需用户主动开启</li>
          <li>情绪记录不会进入全局事件流污染其他模块</li>
        </ul>
      </div>
    </div>
  );
}