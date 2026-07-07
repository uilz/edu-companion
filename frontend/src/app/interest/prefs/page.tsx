"use client";

/**
 * 推送偏好 — 频率/时间/比例/跨学科/保留期
 * 依据 docs/modules/interest-explorer/data-model.md §2 + ADR 0007 决策 4/8
 */
import { useEffect, useState, useCallback } from "react";
import {
  Save, Loader2, AlertCircle, ChevronLeft, Settings as SettingsIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  interestService, InterestPushPrefs, PushFrequency, FREQUENCY_LABELS,
} from "@/lib/api/interest-api";

export default function PrefsPage() {
  const router = useRouter();
  const [prefs, setPrefs] = useState<InterestPushPrefs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await interestService.getPrefs();
      setPrefs(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onSave = async () => {
    if (!prefs) return;
    setBusy(true);
    setError(null);
    setSuccess(false);
    try {
      const r = await interestService.updatePrefs(prefs);
      setPrefs(r);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-2xl text-center py-12 text-muted">
        <Loader2 className="w-8 h-8 mx-auto animate-spin" />
      </div>
    );
  }

  if (!prefs) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-2xl">
        <div className="p-3 bg-danger/10 border border-danger/20 rounded text-sm text-danger">
          加载失败: {error}
        </div>
      </div>
    );
  }

  const sum =
    prefs.research_object_pct +
    prefs.research_method_pct +
    prefs.hot_news_pct;
  const sumValid = sum === 100;

  return (
    <div className="container mx-auto px-4 py-8 max-w-2xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <SettingsIcon className="w-6 h-6 text-info" />
            推送偏好
          </h1>
          <p className="text-sm text-muted mt-1">
            严格遵循 ADR 0007: 时区感知 · 推送比例可配置 · 跨学科默认关闭
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => router.push("/interest")}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-surface"
          >
            返回
          </button>
          <button
            onClick={onSave}
            disabled={busy || !sumValid}
            className="px-3 py-1.5 text-sm bg-info text-white rounded-lg hover:bg-info flex items-center gap-1 disabled:opacity-50"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            保存
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-danger/10 border border-danger/20 rounded-lg flex items-start gap-2 text-sm text-danger">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 bg-success/10 border border-success/20 rounded-lg text-sm text-success">
          保存成功
        </div>
      )}

      <div className="space-y-6">
        {/* 频率 + 时间 */}
        <div className="border rounded-lg p-4 bg-white">
          <h2 className="font-medium text-sm mb-3">推送频率</h2>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted block mb-1">频率</label>
              <select
                value={prefs.frequency}
                onChange={(e) => setPrefs({ ...prefs, frequency: e.target.value as PushFrequency })}
                className="w-full px-3 py-2 border rounded text-sm"
              >
                {Object.entries(FREQUENCY_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-muted block mb-1">推送时间</label>
              <input
                type="time"
                value={prefs.push_time?.slice(0, 5) || "08:00"}
                onChange={(e) => setPrefs({ ...prefs, push_time: e.target.value + ":00" })}
                className="w-full px-3 py-2 border rounded text-sm"
              />
            </div>
          </div>
          <div className="mt-3">
            <label className="text-xs text-muted block mb-1">时区</label>
            <input
              value={prefs.timezone}
              onChange={(e) => setPrefs({ ...prefs, timezone: e.target.value })}
              placeholder="Asia/Shanghai"
              className="w-full px-3 py-2 border rounded text-sm font-mono"
            />
          </div>
        </div>

        {/* 每日上限 */}
        <div className="border rounded-lg p-4 bg-white">
          <h2 className="font-medium text-sm mb-3">每日推送上限</h2>
          <input
            type="number"
            value={prefs.daily_limit}
            onChange={(e) => setPrefs({ ...prefs, daily_limit: Number(e.target.value) })}
            min={1}
            max={50}
            className="w-32 px-3 py-2 border rounded text-sm"
          />
          <p className="text-xs text-muted mt-1">1 - 50 条</p>
        </div>

        {/* 推送比例 */}
        <div className="border rounded-lg p-4 bg-white">
          <h2 className="font-medium text-sm mb-3">
            推送比例{" "}
            <span className={`text-xs ${sumValid ? "text-success" : "text-danger"}`}>
              (合计: {sum}%)
            </span>
          </h2>
          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <label>研究对象 (research_object)</label>
                <span className="text-muted">{prefs.research_object_pct}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={prefs.research_object_pct}
                onChange={(e) => setPrefs({
                  ...prefs,
                  research_object_pct: Number(e.target.value),
                })}
                className="w-full"
              />
            </div>
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <label>研究方法 (research_method)</label>
                <span className="text-muted">{prefs.research_method_pct}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={prefs.research_method_pct}
                onChange={(e) => setPrefs({
                  ...prefs,
                  research_method_pct: Number(e.target.value),
                })}
                className="w-full"
              />
            </div>
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <label>热点日报 (hot_news)</label>
                <span className="text-muted">{prefs.hot_news_pct}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={prefs.hot_news_pct}
                onChange={(e) => setPrefs({
                  ...prefs,
                  hot_news_pct: Number(e.target.value),
                })}
                className="w-full"
              />
            </div>
            {!sumValid && (
              <p className="text-xs text-danger">
                推送比例之和必须 = 100%
              </p>
            )}
          </div>
        </div>

        {/* 跨学科推送 */}
        <div className="border rounded-lg p-4 bg-white">
          <h2 className="font-medium text-sm mb-3">跨学科推送</h2>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={prefs.cross_disciplinary}
              onChange={(e) => setPrefs({
                ...prefs,
                cross_disciplinary: e.target.checked,
              })}
              className="rounded"
            />
            <span>启用跨学科推送（范围扩展到用户兴趣领域之外）</span>
          </label>
          <p className="text-xs text-muted mt-1">
            默认关闭。开启后从所有标签的全局采样（决策 4）
          </p>
        </div>

        {/* 历史保留期 */}
        <div className="border rounded-lg p-4 bg-white">
          <h2 className="font-medium text-sm mb-3">历史保留期</h2>
          <select
            value={prefs.retention_days}
            onChange={(e) => setPrefs({ ...prefs, retention_days: Number(e.target.value) })}
            className="px-3 py-2 border rounded text-sm"
          >
            <option value={30}>30 天</option>
            <option value={90}>90 天 (默认)</option>
            <option value={180}>180 天</option>
            <option value={365}>365 天</option>
          </select>
        </div>

        {/* 启用 */}
        <div className="border rounded-lg p-4 bg-white">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={prefs.is_enabled}
              onChange={(e) => setPrefs({ ...prefs, is_enabled: e.target.checked })}
              className="rounded"
            />
            <span>启用推送</span>
          </label>
        </div>
      </div>
    </div>
  );
}
