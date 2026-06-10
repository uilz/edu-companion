"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Sun, Moon, Key, Cpu, MessageSquare, Brain,
  User, Shield, LogOut, Eye, EyeOff, Check, Loader2,
  Monitor, Smartphone, MapPin, X, Database, Download,
  AlertTriangle, RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { useTheme, STYLE_LIST } from "@/contexts/ThemeContext";
import { useRouter } from "next/navigation";
import { authedFetch, AuthUser } from "@/lib/api/auth";

const SETTINGS_TABS = [
  { key: "account", label: "账户", icon: User },
  { key: "security", label: "安全", icon: Shield },
  { key: "llm", label: "LLM 配置", icon: Cpu },
  { key: "preferences", label: "学习偏好", icon: Brain },
  { key: "appearance", label: "外观", icon: Sun },
  { key: "data", label: "数据管理", icon: Database },
  { key: "about", label: "关于", icon: "info" },
] as const;

type TabKey = (typeof SETTINGS_TABS)[number]["key"];

export default function SettingsPage() {
  const { theme, setTheme, style, setStyle } = useTheme();

  const [activeTab, setActiveTab] = useState<TabKey>("account");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authedFetch<AuthUser>("/api/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <div className="flex items-center gap-3 mb-6">
        <Link
          href="/learn"
          className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
        </Link>
        <h1 className="text-xl font-bold text-[var(--color-text)]">设置</h1>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 p-1 mb-6 bg-[var(--color-surface)] rounded-xl overflow-x-auto border border-[var(--color-border)]">
        {SETTINGS_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg whitespace-nowrap transition-colors ${
              activeTab === tab.key
                ? "bg-[var(--color-accent)] text-white shadow-sm"
                : "text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-hover)]"
            }`}
          >
            {tab.key === "about" ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
              </svg>
            ) : (
              <tab.icon size={14} />
            )}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5">
        {activeTab === "account" && <AccountTab user={user} />}
        {activeTab === "security" && <SecurityTab user={user} />}
        {activeTab === "llm" && <LlmTab user={user} />}
        {activeTab === "preferences" && <PreferencesTab />}
        {activeTab === "appearance" && (
          <AppearanceTab
            theme={theme}
            setTheme={(t: unknown) => setTheme(t as "dark" | "light")}
            style={style}
            setStyle={(s: unknown) => setStyle(s as "professional" | "playful" | "knowledge" | "soft-data" | "gamified")}
          />
        )}
        {activeTab === "data" && <DataTab />}
        {activeTab === "about" && <AboutTab />}
      </div>
    </div>
  );
}

// ══════════════════ 账户 Tab ══════════════════
function AccountTab({ user }: { user: AuthUser | null }) {
  const [editing, setEditing] = useState(false);
  const [profileName, setProfileName] = useState(user?.display_name || "");
  const [profileEmail, setProfileEmail] = useState(user?.email || "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (user) {
      setProfileName(user.display_name || user.username);
      setProfileEmail(user.email || "");
    }
  }, [user]);

  const saveProfile = useCallback(async () => {
    setSaving(true);
    setMsg("");
    try {
      await authedFetch("/api/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ display_name: profileName, email: profileEmail }),
      });
      setEditing(false);
      setMsg("已保存");
    } catch (e: any) {
      setMsg(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  }, [profileName, profileEmail]);

  if (!user) return null;

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-[var(--color-text)] flex items-center gap-2">
        <User size={18} />
        账户信息
      </h2>

      {/* Avatar + basic info */}
      <div className="flex items-center gap-4 p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">
        <div className="relative">
          <div className={`w-16 h-16 rounded-full flex items-center justify-center text-xl font-bold text-white ${user.avatar_url ? "" : "bg-[var(--color-accent)]"}`}
            style={user.avatar_url ? { backgroundImage: `url(${user.avatar_url})`, backgroundSize: "cover" } : undefined}
          >
            {user.avatar_url ? "" : (user.display_name || user.username).charAt(0).toUpperCase()}
          </div>
        </div>
        <div>
          <div className="font-semibold text-[var(--color-text)]">{user.display_name || user.username}</div>
          <div className="text-sm text-[var(--color-text-muted)]">@{user.username}</div>
          {user.email && <div className="text-xs text-[var(--color-text-muted)] mt-0.5">{user.email}</div>}
          <div className="mt-1">
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${user.role === "super_admin" ? "bg-purple-500/10 text-purple-500" : user.role === "admin" ? "bg-blue-500/10 text-blue-500" : "bg-gray-500/10 text-gray-500"}`}>
              {user.role === "super_admin" ? "超级管理员" : user.role === "admin" ? "管理员" : "用户"}
            </span>
          </div>
        </div>
      </div>

      {/* Edit mode */}
      {editing ? (
        <div className="space-y-3 p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">
          <div>
            <label className="text-xs text-[var(--color-text-muted)] mb-1 block">显示名称</label>
            <input
              value={profileName}
              onChange={(e) => setProfileName(e.target.value)}
              maxLength={64}
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-[var(--color-border-hover)]"
            />
          </div>
          <div>
            <label className="text-xs text-[var(--color-text-muted)] mb-1 block">邮箱</label>
            <input
              type="email"
              value={profileEmail}
              onChange={(e) => setProfileEmail(e.target.value)}
              maxLength={128}
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-[var(--color-border-hover)]"
              placeholder="可选"
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={saveProfile}
              disabled={saving}
              className="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50"
            >
              {saving ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
              保存
            </button>
            <button
              onClick={() => { setEditing(false); setMsg(""); }}
              className="flex items-center gap-1 px-3 py-1.5 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)]"
            >
              <X size={12} />
              取消
            </button>
            {msg && (
              <span className={`text-xs ml-auto ${msg.includes("失败") ? "text-red-500" : "text-green-500"}`}>
                {msg}
              </span>
            )}
          </div>
        </div>
      ) : (
        <button
          onClick={() => setEditing(true)}
          className="flex items-center gap-2 text-xs text-[var(--color-accent)] hover:underline"
        >
          <User size={12} />
          编辑资料
        </button>
      )}
    </div>
  );
}

// ══════════════════ 安全 Tab ══════════════════
function SecurityTab({ user }: { user: AuthUser | null }) {
  const router = useRouter();
  const [pwdOpen, setPwdOpen] = useState(false);
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [newPwd2, setNewPwd2] = useState("");
  const [pwdShow, setPwdShow] = useState(false);
  const [pwdSaving, setPwdSaving] = useState(false);
  const [pwdMsg, setPwdMsg] = useState("");

  // Device session data
  const [sessions, setSessions] = useState<any[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [kickingDevice, setKickingDevice] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setSessionsLoading(true);
    authedFetch<{ sessions: any[] }>("/api/auth/me/active-sessions")
      .then((d: { sessions: any[] }) => setSessions(d.sessions || []))
      .catch(() => setSessions([]))
      .finally(() => setSessionsLoading(false));
  }, [user]);

  const handleLogoutOthers = async () => {
    setKickingDevice("all");
    try {
      await authedFetch("/api/auth/me/logout-other-devices", { method: "POST" });
      setSessions((prev) =>
        prev.filter((s) => s.is_current)
      );
    } catch { /* silent */ }
    finally { setKickingDevice(null); }
  };

  const handleChangePwd = async () => {
    if (!oldPwd || !newPwd) { setPwdMsg("请填写所有字段"); return; }
    if (newPwd !== newPwd2) { setPwdMsg("两次新密码不一致"); return; }
    if (newPwd.length < 6) { setPwdMsg("新密码至少6位"); return; }
    setPwdSaving(true);
    setPwdMsg("");
    try {
      await authedFetch("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ old_password: oldPwd, new_password: newPwd }),
      });
      setPwdMsg("密码修改成功");
      setPwdOpen(false);
      setOldPwd(""); setNewPwd(""); setNewPwd2("");
    } catch (e: any) {
      setPwdMsg(e.message || "修改失败");
    } finally {
      setPwdSaving(false);
    }
  };

  const logout = useCallback(async () => {
    try {
      localStorage.removeItem("token");
      localStorage.removeItem("learn-page-state");
      sessionStorage.clear();
      router.push("/login");
    } catch { router.push("/login"); }
  }, [router]);

  if (!user) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-base font-semibold text-[var(--color-text)] flex items-center gap-2">
        <Shield size={18} />
        安全设置
      </h2>

      {/* 修改密码 */}
      <div className="p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-[var(--color-text)]">修改密码</div>
            <p className="text-xs text-[var(--color-text-muted)] mt-0.5">定期修改密码可以提高账户安全性</p>
          </div>
          <button
            onClick={() => { setPwdOpen(!pwdOpen); setPwdMsg(""); }}
            className="px-3 py-1.5 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)]"
          >
            {pwdOpen ? "收起" : "修改"}
          </button>
        </div>

        {pwdOpen && (
          <div className="space-y-3 pt-3 border-t border-[var(--color-border)]">
            <div>
              <label className="text-xs text-[var(--color-text-muted)] mb-1 block">当前密码</label>
              <div className="relative">
                <input
                  type={pwdShow ? "text" : "password"}
                  value={oldPwd}
                  onChange={(e) => setOldPwd(e.target.value)}
                  className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 pr-10 rounded focus:outline-none focus:border-[var(--color-border-hover)]"
                  placeholder="输入当前密码"
                />
                <button
                  type="button"
                  onClick={() => setPwdShow(!pwdShow)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                >
                  {pwdShow ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <div>
              <label className="text-xs text-[var(--color-text-muted)] mb-1 block">新密码</label>
              <input
                type="password"
                value={newPwd}
                onChange={(e) => setNewPwd(e.target.value)}
                className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-[var(--color-border-hover)]"
                placeholder="至少6位"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--color-text-muted)] mb-1 block">确认新密码</label>
              <input
                type="password"
                value={newPwd2}
                onChange={(e) => setNewPwd2(e.target.value)}
                className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-[var(--color-border-hover)]"
                placeholder="再次输入新密码"
              />
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleChangePwd}
                disabled={pwdSaving}
                className="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50"
              >
                {pwdSaving ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                确认修改
              </button>
              {pwdMsg && (
                <span className={`text-xs ${pwdMsg.includes("成功") ? "text-green-500" : "text-red-500"}`}>
                  {pwdMsg}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 设备管理 */}
      <div className="p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-1.5">
              <Monitor size={14} />
              登录设备
            </div>
            <p className="text-xs text-[var(--color-text-muted)] mt-0.5">最近24小时内登录的设备</p>
          </div>
          {sessions.length > 1 && (
            <button
              onClick={handleLogoutOthers}
              disabled={kickingDevice === "all"}
              className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-red-500/30 text-red-500 hover:bg-red-500/10 disabled:opacity-50 transition-colors"
            >
              {kickingDevice === "all" ? <Loader2 size={12} className="animate-spin" /> : <LogOut size={12} />}
              踢出其他设备
            </button>
          )}
        </div>

        {sessionsLoading ? (
          <div className="flex justify-center py-4">
            <Loader2 size={16} className="animate-spin text-[var(--color-text-muted)]" />
          </div>
        ) : sessions.length === 0 ? (
          <p className="text-xs text-[var(--color-text-muted)] text-center py-4">暂无设备记录</p>
        ) : (
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {sessions.map((session, i) => (
              <div key={i} className={`flex items-center gap-3 py-2 px-3 rounded-lg text-xs border ${
                session.is_current
                  ? "border-[var(--color-accent)]/20 bg-[var(--color-accent)]/5"
                  : "border-[var(--color-border)]/30"
              }`}>
                <span className="text-base">
                  {session.device_type === "mobile" ? <Smartphone size={16} /> : <Monitor size={16} />}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-[var(--color-text)] font-medium">
                    {session.browser} · {session.os}
                    {session.is_current && (
                      <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--color-accent)]/15 text-[var(--color-accent)] font-medium">当前</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-[var(--color-text-muted)] mt-0.5">
                    <MapPin size={10} />
                    <span>{session.ip_address || "未知IP"}</span>
                    {[session.city, session.region, session.country].filter(Boolean).join(" · ") && (
                      <span>· {[session.city, session.region, session.country].filter(Boolean).join(" · ")}</span>
                    )}
                  </div>
                </div>
                <span className="text-[10px] text-[var(--color-text-muted)] whitespace-nowrap">
                  {session.created_at?.slice(0, 16)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 退出登录 + 注销 */}
      <div className="p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] space-y-3">
        <button
          onClick={logout}
          className="flex items-center gap-2 text-sm text-red-500 hover:text-red-600"
        >
          <LogOut size={16} />
          退出登录
        </button>
        <DeactivateAccount onDeactivated={logout} />
      </div>
    </div>
  );
}

const MODEL_PRESETS = [
  { label: "GPT-4o", model: "gpt-4o", endpoint: "https://api.openai.com/v1" },
  { label: "GPT-4o-mini", model: "gpt-4o-mini", endpoint: "https://api.openai.com/v1" },
  { label: "DeepSeek V3", model: "deepseek-chat", endpoint: "https://api.deepseek.com/v1" },
  { label: "DeepSeek R1", model: "deepseek-reasoner", endpoint: "https://api.deepseek.com/v1" },
  { label: "Claude 3.5 Sonnet", model: "claude-3-5-sonnet-20241022", endpoint: "https://api.anthropic.com/v1" },
  { label: "自定义", model: "", endpoint: "" },
] as const;

// ══════════════════ LLM Tab ══════════════════
function LlmTab({ user }: { user: AuthUser | null }) {
  const [settings, setSettings] = useState({
    apiEndpoint: "", apiKey: "", modelName: "", systemPrompt: "",
    temperature: 0.7, maxTokens: 2048,
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [hasCustom, setHasCustom] = useState(false);

  // 预设模型选择
  const applyPreset = (preset: typeof MODEL_PRESETS[number]) => {
    if (preset.label === "自定义") return;
    setSettings(s => ({
      ...s,
      modelName: preset.model,
      apiEndpoint: preset.endpoint,
    }));
  };

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    authedFetch<any>("/api/settings/llm")
      .then((data: any) => {
        if (data?.has_custom_config) {
          setSettings({
            apiEndpoint: data.api_base || "",
            apiKey: data.api_key || "",
            modelName: data.model_name || "",
            systemPrompt: settings.systemPrompt,
            temperature: settings.temperature,
            maxTokens: settings.maxTokens,
          });
          setHasCustom(true);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user]);

  useEffect(() => {
    const saved = localStorage.getItem("edu-companion-settings-llm-system-prompt");
    if (saved) {
      try {
        const p = JSON.parse(saved);
        setSettings((s) => ({
          ...s,
          systemPrompt: p.systemPrompt || "",
          temperature: p.temperature ?? 0.7,
          maxTokens: p.maxTokens ?? 2048,
        }));
      } catch { /* */ }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("edu-companion-settings-llm-system-prompt", JSON.stringify({
      systemPrompt: settings.systemPrompt,
      temperature: settings.temperature,
      maxTokens: settings.maxTokens,
    }));
  }, [settings.systemPrompt, settings.temperature, settings.maxTokens]);

  const saveConfig = async () => {
    if (!user) return;
    setSaving(true);
    setMsg("");
    try {
      await authedFetch("/api/settings/llm", {
        method: "PUT",
        body: JSON.stringify({
          api_base: settings.apiEndpoint,
          api_key: settings.apiKey,
          model_name: settings.modelName,
        }),
      });
      // 同时持久化温度/最大长度到本地
      localStorage.setItem("edu-companion-settings-llm-ext", JSON.stringify({
        temperature: settings.temperature,
        maxTokens: settings.maxTokens,
      }));
      setMsg("配置已保存");
      setHasCustom(true);
    } catch (e: any) {
      setMsg(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const resetConfig = async () => {
    if (!user) return;
    setSaving(true);
    setMsg("");
    try {
      await authedFetch("/api/settings/llm", { method: "DELETE" });
      setSettings((s) => ({ ...s, apiEndpoint: "", apiKey: "", modelName: "" }));
      setHasCustom(false);
      setMsg("已恢复为系统默认");
    } catch (e: any) {
      setMsg(e.message || "重置失败");
    } finally {
      setSaving(false);
    }
  };

  if (!user) return null;

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-[var(--color-text)] flex items-center gap-2">
        <Cpu size={18} />
        LLM 配置
      </h2>

      {loading ? (
        <div className="flex justify-center py-4">
          <Loader2 size={16} className="animate-spin text-[var(--color-text-muted)]" />
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1.5">
              <Key size={12} />
              API 端点
            </label>
            <input
              value={settings.apiEndpoint}
              onChange={(e) => setSettings((s) => ({ ...s, apiEndpoint: e.target.value }))}
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-[var(--color-border-hover)] font-mono"
              placeholder="https://api.openai.com/v1"
            />
          </div>
          <div>
            <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1.5">
              <Shield size={12} />
              API Key
            </label>
            <input
              value={settings.apiKey}
              onChange={(e) => setSettings((s) => ({ ...s, apiKey: e.target.value }))}
              type="password"
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-[var(--color-border-hover)] font-mono"
              placeholder="sk-..."
            />
          </div>
          <div>
            <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1.5">
              <Cpu size={12} />
              模型名称
            </label>
            <input
              value={settings.modelName}
              onChange={(e) => setSettings((s) => ({ ...s, modelName: e.target.value }))}
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-[var(--color-border-hover)]"
              placeholder="gpt-4o / deepseek-chat / 等"
            />
          </div>

          {/* 预设模型快速选择 */}
          <div>
            <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1.5">
              <Cpu size={12} />
              预设模型
            </label>
            <div className="flex flex-wrap gap-1.5">
              {MODEL_PRESETS.filter(p => p.label !== "自定义").map(p => (
                <button key={p.label} onClick={() => applyPreset(p)}
                  className={`px-2.5 py-1 text-[10px] rounded-lg border transition-all ${
                    settings.modelName === p.model
                      ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                      : "border-[var(--color-border)]/50 text-[var(--color-text-secondary)] hover:border-[var(--color-accent)]/30"
                  }`}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* 温度 */}
          <div>
            <label className="flex items-center justify-between text-xs text-[var(--color-text-muted)] mb-1.5">
              <span className="flex items-center gap-1.5"><Cpu size={12} /> 温度</span>
              <span className="font-mono text-[10px]">{settings.temperature.toFixed(1)}</span>
            </label>
            <input type="range" min="0" max="2" step="0.1"
              value={settings.temperature}
              onChange={(e) => setSettings(s => ({ ...s, temperature: parseFloat(e.target.value) }))}
              className="w-full h-1.5 rounded-full appearance-none cursor-pointer bg-[var(--color-border)] accent-[var(--color-accent)]"
            />
            <div className="flex justify-between text-[9px] text-[var(--color-text-muted)] mt-0.5">
              <span>精确 (0)</span>
              <span>平衡 (1)</span>
              <span>创意 (2)</span>
            </div>
          </div>

          {/* 最大 Token 数 */}
          <div>
            <label className="flex items-center justify-between text-xs text-[var(--color-text-muted)] mb-1.5">
              <span className="flex items-center gap-1.5"><MessageSquare size={12} /> 最大回复长度</span>
              <span className="font-mono text-[10px]">{settings.maxTokens}</span>
            </label>
            <input type="range" min="256" max="4096" step="256"
              value={settings.maxTokens}
              onChange={(e) => setSettings(s => ({ ...s, maxTokens: parseInt(e.target.value) }))}
              className="w-full h-1.5 rounded-full appearance-none cursor-pointer bg-[var(--color-border)] accent-[var(--color-accent)]"
            />
            <div className="flex justify-between text-[9px] text-[var(--color-text-muted)] mt-0.5">
              <span>256</span>
              <span>2048</span>
              <span>4096</span>
            </div>
          </div>

          <div>
            <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1.5">
              <MessageSquare size={12} />
              系统提示词（本地存储）
            </label>
            <textarea
              value={settings.systemPrompt}
              onChange={(e) => setSettings((s) => ({ ...s, systemPrompt: e.target.value }))}
              rows={4}
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-[var(--color-border-hover)] resize-none"
            />
          </div>
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={saveConfig}
              disabled={saving || !user}
              className="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50"
            >
              {saving ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
              保存配置
            </button>
            {hasCustom && (
              <button
                onClick={resetConfig}
                disabled={saving}
                className="flex items-center gap-1 px-3 py-1.5 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-red-400 hover:text-red-500"
              >
                <X size={12} />
                恢复默认
              </button>
            )}
            {msg && (
              <span className={`text-xs ml-auto ${msg.includes("失败") ? "text-red-500" : "text-green-500"}`}>
                {msg}
              </span>
            )}
          </div>
          <p className="text-[10px] text-[var(--color-text-muted)] leading-relaxed">
            API Key 将加密存储于服务器，对话时使用你的配置调用模型。
            如只填模型名称而不填 API 端点和 Key，则使用系统默认配置。
          </p>
        </div>
      )}
    </div>
  );
}

// ══════════════════ 学习偏好 Tab ══════════════════
function PreferencesTab() {
  const [socratic, setSocratic] = useState(false);
  const [socraticFollowUp, setSocraticFollowUp] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState("");

  useEffect(() => {
    const saved = localStorage.getItem("edu-companion-settings-prefs");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setSocratic(parsed.socraticMode || false);
        setSocraticFollowUp(parsed.socraticFollowUpMode || false);
        setSystemPrompt(parsed.systemPrompt || "");
      } catch { /* */ }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("edu-companion-settings-prefs", JSON.stringify({
      socraticMode: socratic,
      socraticFollowUpMode: socraticFollowUp,
      systemPrompt,
    }));
  }, [socratic, socraticFollowUp, systemPrompt]);

  return (
    <div className="space-y-5">
      <h2 className="text-base font-semibold text-[var(--color-text)] flex items-center gap-2">
        <Brain size={18} />
        学习偏好
      </h2>

      {/* 启发式追问 */}
      <div className="p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-[var(--color-text)]">启发式追问（苏格拉底教学法）</div>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">
              遇到概念问题时，AI 会先反问引导思考，而不是直接给答案
            </p>
          </div>
          <button
            onClick={() => setSocratic(!socratic)}
            className={`relative w-11 h-6 rounded-full transition-colors ${socratic ? "bg-[var(--color-accent)]" : "bg-[var(--color-surface)] border border-[var(--color-border)]"}`}
          >
            <div className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform ${socratic ? "translate-x-[22px]" : "translate-x-[2px]"}`} />
          </button>
        </div>
      </div>

      {/* 追问模式 */}
      <div className="p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-[var(--color-text)]">追问模式</div>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">
              开启后，AI 回答完概念问题后会继续追问，深化理解
            </p>
          </div>
          <button
            onClick={() => setSocraticFollowUp(!socraticFollowUp)}
            className={`relative w-11 h-6 rounded-full transition-colors ${socraticFollowUp ? "bg-[var(--color-accent)]" : "bg-[var(--color-surface)] border border-[var(--color-border)]"}`}
          >
            <div className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform ${socraticFollowUp ? "translate-x-[22px]" : "translate-x-[2px]"}`} />
          </button>
        </div>
      </div>

      {/* 系统提示词 */}
      <div className="p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">
        <label className="text-sm font-semibold text-[var(--color-text)] mb-2 block">
          自定义系统提示词
        </label>
        <textarea
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          rows={4}
          className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-[var(--color-border-hover)] resize-none"
          placeholder="自定义 AI 的角色和行为指令..."
        />
      </div>
    </div>
  );
}

// ══════════════════ 外观 Tab ══════════════════
function AppearanceTab({ theme, setTheme, style, setStyle }: {
  theme: string;
  setTheme: (t: string) => void;
  style: string;
  setStyle: (s: string) => void;
}) {
  return (
    <div className="space-y-6">
      <h2 className="text-base font-semibold text-[var(--color-text)] flex items-center gap-2">
        <Sun size={18} />
        外观设置
      </h2>

      {/* 主题 */}
      <div>
        <div className="text-sm font-semibold text-[var(--color-text)] mb-3">主题模式</div>
        <div className="flex gap-3">
          <button
            onClick={() => setTheme("dark")}
            className={`flex items-center gap-2 px-4 py-3 rounded-lg border text-sm transition-colors ${
              theme === "dark"
                ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)]"
            }`}
          >
            <Moon size={16} />
            深色
          </button>
          <button
            onClick={() => setTheme("light")}
            className={`flex items-center gap-2 px-4 py-3 rounded-lg border text-sm transition-colors ${
              theme === "light"
                ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)]"
            }`}
          >
            <Sun size={16} />
            浅色
          </button>
        </div>
      </div>

      {/* 设计风格 */}
      <div>
        <div className="text-sm font-semibold text-[var(--color-text)] mb-3">设计风格</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {STYLE_LIST.map((s) => (
            <button
              key={s.id}
              onClick={() => setStyle(s.id)}
              className={`flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm transition-all ${
                style === s.id
                  ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)] ring-1 ring-[var(--color-accent)]/30"
                  : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)]"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ══════════════════ 关于 Tab ══════════════════
function AboutTab() {
  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-[var(--color-text)]">关于智学伴</h2>
      <div className="space-y-3 text-sm">
        <div className="flex justify-between py-2 border-b border-[var(--color-border)]/30">
          <span className="text-[var(--color-text-secondary)]">应用名称</span>
          <span className="text-[var(--color-text)] font-medium">智学伴</span>
        </div>
        <div className="flex justify-between py-2 border-b border-[var(--color-border)]/30">
          <span className="text-[var(--color-text-secondary)]">版本</span>
          <span className="text-[var(--color-text)] font-medium">v1.0.0</span>
        </div>
        <div className="flex justify-between py-2 border-b border-[var(--color-border)]/30">
          <span className="text-[var(--color-text-secondary)]">框架</span>
          <span className="text-[var(--color-text)] font-medium">Next.js 14 + Tailwind</span>
        </div>
        <div className="pt-3">
          <p className="text-xs text-[var(--color-text-muted)] leading-relaxed">
            智学伴是一个 AI 驱动的个性化学习助手，支持智能对话、练习题生成、
            知识图谱和学情分析。
          </p>
        </div>
      </div>
    </div>
  );
}

// ══════════════════ 注销账号组件 ══════════════════
function DeactivateAccount({ onDeactivated }: { onDeactivated: () => void }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const handleDeactivate = async () => {
    if (!password) { setMsg("请输入密码确认"); return; }
    setLoading(true);
    setMsg("");
    try {
      await authedFetch("/api/auth/deactivate", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      setMsg("账号已注销，即将跳转…");
      setTimeout(() => onDeactivated(), 1500);
    } catch (e: any) {
      setMsg(e.message || "注销失败");
    } finally {
      setLoading(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 text-sm text-red-400 hover:text-red-500"
      >
        <X size={16} />
        注销账号
      </button>
    );
  }

  return (
    <div className="space-y-3 p-3 rounded-lg bg-red-500/5 border border-red-500/20">
      <p className="text-sm font-medium text-red-500">确认注销账号</p>
      <p className="text-xs text-[var(--color-text-muted)]">
        注销后账号将被永久停用，数据无法恢复。请输入密码确认。
      </p>
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-red-500"
        placeholder="输入当前密码"
      />
      <div className="flex items-center gap-2">
        <button
          onClick={handleDeactivate}
          disabled={loading}
          className="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-red-500 text-white hover:bg-red-600 disabled:opacity-50"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <X size={12} />}
          确认注销
        </button>
        <button
          onClick={() => { setOpen(false); setPassword(""); setMsg(""); }}
          className="px-3 py-1.5 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-secondary)]"
        >
          取消
        </button>
        {msg && (
          <span className={`text-xs ml-auto ${msg.includes("失败") || msg.includes("密码") ? "text-red-500" : "text-green-500"}`}>
            {msg}
          </span>
        )}
      </div>
    </div>
  );
}

// ══════════════════ 数据管理 Tab ══════════════════
function DataTab() {
  const [exporting, setExporting] = useState(false);
  const [overview, setOverview] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchOverview = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authedFetch<any>("/api/v7/data/overview");
      setOverview(res?.overview || null);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchOverview(); }, [fetchOverview]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch("/api/v7/data/export", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `edu-companion-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {} finally { setExporting(false); }
  };

  const handleReset = async () => {
    if (!confirm("确定清除所有学习数据？此操作不可撤销！\n\n将删除所有对话、练习记录、知识图谱等数据。")) return;
    if (!confirm("再次确认：所有数据将被永久删除。")) return;
    try {
      const token = localStorage.getItem("access_token");
      await fetch("/api/v7/data/reset", {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}`, "Content-Type": "application/json" } : {},
      });
      alert("数据已清除");
      fetchOverview();
    } catch { alert("清除失败，请重试"); }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-[var(--color-text)] flex items-center gap-2">
        <Database size={18} />
        数据管理
      </h2>

      {loading ? (
        <div className="flex justify-center py-4">
          <Loader2 size={16} className="animate-spin text-[var(--color-text-muted)]" />
        </div>
      ) : (
        <>
          {/* 数据概览 */}
          {overview && (
            <div className="p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-[var(--color-text-muted)]">数据概览</span>
                <button onClick={fetchOverview} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                  <RefreshCw size={12} />
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div className="text-center p-2 rounded bg-[var(--color-bg)]">
                  <div className="text-lg font-bold text-[var(--color-text)]">{overview.partitions ?? 0}</div>
                  <div className="text-[9px] text-[var(--color-text-muted)]">分区</div>
                </div>
                <div className="text-center p-2 rounded bg-[var(--color-bg)]">
                  <div className="text-lg font-bold text-[var(--color-text)]">{overview.domains ?? 0}</div>
                  <div className="text-[9px] text-[var(--color-text-muted)]">领域</div>
                </div>
                <div className="text-center p-2 rounded bg-[var(--color-bg)]">
                  <div className="text-lg font-bold text-[var(--color-text)]">{overview.conversations ?? 0}</div>
                  <div className="text-[9px] text-[var(--color-text-muted)]">对话</div>
                </div>
                <div className="text-center p-2 rounded bg-[var(--color-bg)]">
                  <div className="text-lg font-bold text-[var(--color-text)]">{overview.questions ?? overview.graph_nodes ?? 0}</div>
                  <div className="text-[9px] text-[var(--color-text-muted)]">题目/节点</div>
                </div>
              </div>
            </div>
          )}

          {/* 操作区 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">
              <div>
                <div className="text-sm font-semibold text-[var(--color-text)]">导出全部数据</div>
                <p className="text-xs text-[var(--color-text-muted)] mt-0.5">下载 JSON 格式的完整学习数据备份</p>
              </div>
              <button onClick={handleExport} disabled={exporting}
                className="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50">
                {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
                {exporting ? "导出中..." : "导出"}
              </button>
            </div>

            <div className="flex items-center justify-between p-4 rounded-lg bg-[var(--color-surface)] border border-red-500/20">
              <div>
                <div className="text-sm font-semibold text-red-500">清除所有学习数据</div>
                <p className="text-xs text-[var(--color-text-muted)] mt-0.5">删除所有对话、练习记录、知识图谱，不可恢复</p>
              </div>
              <button onClick={handleReset}
                className="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-red-500 text-white hover:bg-red-600">
                <AlertTriangle size={12} />
                清除
              </button>
            </div>
          </div>
        </>
      )}

      <Link href="/settings/data"
        className="block text-center text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] underline">
        查看详细数据管理 →
      </Link>
    </div>
  );
}