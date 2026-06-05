"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Sun, Moon, Globe, Key, Cpu, MessageSquare, Info, Brain, Database,
  User, Shield, LogOut, Eye, EyeOff, Check, X, Loader2,
} from "lucide-react";
import Link from "next/link";
import { useTheme } from "@/contexts/ThemeContext";
import { useAuth } from "@/contexts/AuthContext";
import { authedFetch } from "@/lib/api/auth";
import Card from "@/components/ui/Card";

// ===== 设置项类型定义 =====
interface Settings {
  apiEndpoint: string;
  apiKey: string;
  modelName: string;
  systemPrompt: string;
  socraticMode: boolean;
  socraticFollowUpMode: "ask" | "answer";
}

// ===== 默认设置值 =====
const defaultSettings: Settings = {
  apiEndpoint: "",
  apiKey: "",
  modelName: "gpt-4o",
  systemPrompt: "你是一个专业的学习助手，擅长解答各学科问题。",
  socraticMode: true,
  socraticFollowUpMode: "ask",
};

// ===== 设置页面组件 =====
export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { user, logout, refresh } = useAuth();
  const [settings, setSettings] = useState<Settings>(defaultSettings);

  // 用户资料编辑
  const [profileEditing, setProfileEditing] = useState(false);
  const [profileName, setProfileName] = useState("");
  const [profileEmail, setProfileEmail] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState("");

  // 修改密码
  const [pwdOpen, setPwdOpen] = useState(false);
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [newPwd2, setNewPwd2] = useState("");
  const [pwdShow, setPwdShow] = useState(false);
  const [pwdSaving, setPwdSaving] = useState(false);
  const [pwdMsg, setPwdMsg] = useState("");

  // 加载设置
  useEffect(() => {
    const saved = localStorage.getItem("edu-companion-settings");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setSettings((s) => ({ ...s, ...parsed }));
      } catch { ; }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("edu-companion-settings", JSON.stringify(settings));
  }, [settings]);

  // 同步用户资料到编辑表单
  useEffect(() => {
    if (user) {
      setProfileName(user.display_name || user.username);
      setProfileEmail(user.email || "");
    }
  }, [user]);

  // 保存用户资料
  const saveProfile = useCallback(async () => {
    setProfileSaving(true);
    setProfileMsg("");
    try {
      await authedFetch("/api/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ display_name: profileName, email: profileEmail }),
      });
      setProfileMsg("已保存");
      setProfileEditing(false);
      await refresh();
    } catch (e: any) {
      setProfileMsg(e.message || "保存失败");
    } finally {
      setProfileSaving(false);
    }
  }, [profileName, profileEmail, refresh]);

  // 修改密码
  const changePassword = useCallback(async () => {
    setPwdMsg("");
    if (!oldPwd || !newPwd || !newPwd2) {
      setPwdMsg("请填写所有字段");
      return;
    }
    if (newPwd !== newPwd2) {
      setPwdMsg("两次输入的新密码不一致");
      return;
    }
    if (newPwd.length < 6) {
      setPwdMsg("新密码至少需要6个字符");
      return;
    }
    setPwdSaving(true);
    try {
      await authedFetch("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ old_password: oldPwd, new_password: newPwd }),
      });
      setPwdMsg("密码修改成功");
      setOldPwd("");
      setNewPwd("");
      setNewPwd2("");
      setTimeout(() => setPwdOpen(false), 1500);
    } catch (e: any) {
      setPwdMsg(e.message || "修改失败");
    } finally {
      setPwdSaving(false);
    }
  }, [oldPwd, newPwd, newPwd2]);

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="text-4xl font-semibold tracking-tight text-[var(--color-text)] mb-12">
          设置
        </h1>

        <div className="space-y-8">
          {/* ===== 账户信息 ===== */}
          <Card title="账户">
            <div className="space-y-4">
              {/* 用户头像 + 基本信息 */}
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xl font-bold flex-shrink-0">
                  {user ? (user.display_name || user.username).charAt(0).toUpperCase() : "?"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-lg font-semibold text-[var(--color-text)] truncate">
                    {user?.display_name || user?.username || "未登录"}
                  </div>
                  <div className="text-sm text-[var(--color-text-muted)] truncate">
                    @{user?.username || "—"}
                    {user?.email ? ` · ${user.email}` : ""}
                  </div>
                </div>
              </div>

              {/* 资料编辑 */}
              {profileEditing ? (
                <div className="space-y-3 pt-2 border-t border-[var(--color-border)]">
                  <div>
                    <label className="text-xs text-[var(--color-text-muted)] mb-1 block">显示名称</label>
                    <input
                      value={profileName}
                      onChange={(e) => setProfileName(e.target.value)}
                      maxLength={64}
                      className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-[var(--color-border-hover)]"
                      placeholder="你的显示名称"
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
                      disabled={profileSaving}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50"
                    >
                      {profileSaving ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                      保存
                    </button>
                    <button
                      onClick={() => { setProfileEditing(false); setProfileMsg(""); }}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)]"
                    >
                      <X size={12} />
                      取消
                    </button>
                    {profileMsg && (
                      <span className={`text-xs ml-auto ${profileMsg.includes("失败") ? "text-red-500" : "text-green-500"}`}>
                        {profileMsg}
                      </span>
                    )}
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setProfileEditing(true)}
                  className="flex items-center gap-2 text-xs text-[var(--color-accent)] hover:underline"
                >
                  <User size={12} />
                  编辑资料
                </button>
              )}
            </div>
          </Card>

          {/* ===== 账户安全 ===== */}
          <Card title="安全">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text)]">
                    <Shield size={16} />
                    修改密码
                  </div>
                  <p className="text-xs text-[var(--color-text-muted)] mt-1">
                    定期修改密码可以提高账户安全性
                  </p>
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
                      type={pwdShow ? "text" : "password"}
                      value={newPwd}
                      onChange={(e) => setNewPwd(e.target.value)}
                      minLength={6}
                      className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-[var(--color-border-hover)]"
                      placeholder="至少6个字符"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-[var(--color-text-muted)] mb-1 block">确认新密码</label>
                    <input
                      type={pwdShow ? "text" : "password"}
                      value={newPwd2}
                      onChange={(e) => setNewPwd2(e.target.value)}
                      minLength={6}
                      className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded focus:outline-none focus:border-[var(--color-border-hover)]"
                      placeholder="再次输入新密码"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={changePassword}
                      disabled={pwdSaving}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50"
                    >
                      {pwdSaving ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                      确认修改
                    </button>
                    {pwdMsg && (
                      <span className={`text-xs ${pwdMsg.includes("失败") || pwdMsg.includes("不一致") || pwdMsg.includes("至少") ? "text-red-500" : "text-green-500"}`}>
                        {pwdMsg}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* 退出登录 */}
              <div className="pt-3 border-t border-[var(--color-border)]">
                <button
                  onClick={logout}
                  className="flex items-center gap-2 text-sm text-red-500 hover:text-red-600"
                >
                  <LogOut size={16} />
                  退出登录
                </button>
              </div>
            </div>
          </Card>

          {/* ===== 外观设置 ===== */}
          <Card title="外观">
            <div className="space-y-4">
              <div>
                <div className="text-sm font-semibold text-[var(--color-text)] mb-3">主题</div>
                <div className="flex gap-3">
                  <button
                    onClick={() => setTheme("dark")}
                    className={`flex items-center gap-2 px-4 py-3 border text-sm transition-colors ${
                      theme === "dark"
                        ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                        : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)]"
                    }`}
                  >
                    <Moon size={16} />
                    深色模式
                  </button>
                  <button
                    onClick={() => setTheme("light")}
                    className={`flex items-center gap-2 px-4 py-3 border text-sm transition-colors ${
                      theme === "light"
                        ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                        : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)]"
                    }`}
                  >
                    <Sun size={16} />
                    浅色模式
                  </button>
                </div>
              </div>
            </div>
          </Card>

          {/* ===== API 设置 ===== */}
          <Card title="API 设置">
            <div className="space-y-4">
              <div>
                <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] block mb-1.5">
                  <Globe size={12} />
                  API 端点
                </label>
                <input
                  value={settings.apiEndpoint}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, apiEndpoint: e.target.value }))
                  }
                  className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]"
                  placeholder="留空使用默认"
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] block mb-1.5">
                  <Key size={12} />
                  API Key
                </label>
                <input
                  type="password"
                  value={settings.apiKey}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, apiKey: e.target.value }))
                  }
                  className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]"
                  placeholder="sk-..."
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] block mb-1.5">
                  <Cpu size={12} />
                  模型名称
                </label>
                <input
                  value={settings.modelName}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, modelName: e.target.value }))
                  }
                  className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]"
                  placeholder="gpt-4o"
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] block mb-1.5">
                  <MessageSquare size={12} />
                  系统提示词
                </label>
                <textarea
                  value={settings.systemPrompt}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, systemPrompt: e.target.value }))
                  }
                  rows={4}
                  className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)] resize-none"
                />
              </div>
            </div>
          </Card>

          {/* ===== 学习偏好设置 ===== */}
          <Card title="学习偏好">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text)]">
                    <Brain size={16} />
                    启发式追问（苏格拉底教学法）
                  </div>
                  <p className="text-xs text-[var(--color-text-muted)] mt-1">
                    概念问题时 AI 会先反问引导思考，而不是直接给答案
                  </p>
                </div>
                <button
                  onClick={() =>
                    setSettings((s) => ({ ...s, socraticMode: !s.socraticMode }))
                  }
                  className={`relative w-11 h-6 transition-colors ${
                    settings.socraticMode ? "bg-[var(--color-accent)]" : "bg-[var(--color-surface)] border border-[var(--color-border)]"
                  }`}
                  style={{ borderRadius: "12px" }}
                >
                  <div
                    className={`absolute top-0.5 w-5 h-5 bg-white transition-transform ${
                      settings.socraticMode ? "translate-x-[22px]" : "translate-x-[2px]"
                    }`}
                    style={{ borderRadius: "50%" }}
                  />
                </button>
              </div>
              {settings.socraticMode && (
                <div className="flex items-center gap-2 pt-1">
                  <span className="text-xs text-[var(--color-text-muted)]">追问模式：</span>
                  <button onClick={() => setSettings((s) => ({ ...s, socraticFollowUpMode: "ask" }))}
                    className={`px-2.5 py-1 text-[10px] rounded-full transition-all ${
                      settings.socraticFollowUpMode === "ask"
                        ? "bg-[var(--color-accent)] text-white font-medium"
                        : "text-[var(--color-text-muted)] border border-[var(--color-border)] hover:border-[var(--color-accent)]"
                    }`}>追问AI</button>
                  <button onClick={() => setSettings((s) => ({ ...s, socraticFollowUpMode: "answer" }))}
                    className={`px-2.5 py-1 text-[10px] rounded-full transition-all ${
                      settings.socraticFollowUpMode === "answer"
                        ? "bg-amber-500 text-white font-medium"
                        : "text-[var(--color-text-muted)] border border-[var(--color-border)] hover:border-amber-400"
                    }`}>回答追问</button>
                  <span className="text-[9px] text-[var(--color-text-muted)] ml-auto">
                    {settings.socraticFollowUpMode === "ask" ? "AI回答后自动出追问选项" : "AI反问时自动切换为回答模式"}
                  </span>
                </div>
              )}
            </div>
          </Card>

          {/* ===== 学习数据管理 ===== */}
          <Card title="学习数据管理">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text)]">
                  <Database size={16} />
                  查看与导出学习数据
                </div>
                <p className="text-xs text-[var(--color-text-muted)] mt-1">
                  查看所有知识图谱、对话记录、练习数据，支持导出全部数据
                </p>
              </div>
              <Link
                href="/settings/data"
                className="px-3 py-1.5 text-xs rounded-md bg-[var(--color-accent)] text-white hover:opacity-90 transition-all"
              >
                进入管理
              </Link>
            </div>
          </Card>

          {/* ===== 关于页面 ===== */}
          <Card title="关于">
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-[var(--color-text-secondary)]">应用名称</span>
                <span className="text-[var(--color-text)] font-medium">智学伴</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--color-text-secondary)]">版本</span>
                <span className="text-[var(--color-text)] font-medium">v1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--color-text-secondary)]">框架</span>
                <span className="text-[var(--color-text)] font-medium">Next.js 14 + Tailwind</span>
              </div>
              <div className="pt-3 border-t border-[var(--color-surface)]">
                <div className="flex items-start gap-2 text-xs text-[var(--color-text-muted)]">
                  <Info size={14} className="mt-0.5 flex-shrink-0" />
                  <span>
                    智学伴是一个 AI 驱动的个性化学习助手，支持智能对话、练习题生成、
                    知识图谱和学情分析。
                  </span>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </main>
  );
}
