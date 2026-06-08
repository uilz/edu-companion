"use client";

/**
 * 登录 / 注册页（v2）
 *
 * 设计要点:
 * 1. 主区一个表单，根据当前 LocalProvider 动态渲染字段
 * 2. 登录按钮下方一行 chip「使用 用户名 / 邮箱 登录」→ 不抢主视觉、可扩展
 * 3. OAuth（未来）独立一排按钮，与本地登录互不干扰
 * 4. 切换方式时，只切换字段，不刷新页面
 */

import React, { useState } from "react";
import { BookOpen, Loader2 } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import {
  LOCAL_PROVIDERS,
  ENABLED_OAUTH_PROVIDERS,
  type LocalLoginProvider,
} from "@/lib/auth/providers";

type Mode = "login" | "register";

export default function LoginPage() {
  const { login, loginByEmail, register } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  // 当前登录方式（仅在 login 模式下有意义）
  const [providerIdx, setProviderIdx] = useState(0);
  const provider: LocalLoginProvider = LOCAL_PROVIDERS[providerIdx];

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const switchMode = (m: Mode) => {
    setMode(m);
    setError("");
  };

  const switchLocalProvider = (idx: number) => {
    setProviderIdx(idx);
    setError("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "login") {
        if (provider.id === "email") {
          await loginByEmail(email, password);
        } else {
          await login(username, password);
        }
      } else {
        // 注册始终使用用户名作为主键（邮箱为可选）
        await register(username, password, displayName || username, email);
      }
      window.location.href = "/";
    } catch (err: any) {
      setError(err.message || "操作失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-900 dark:to-indigo-950 px-4">
      <div className="w-full max-w-sm">
        {/* Logo + 文案 */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white mb-3 shadow-lg shadow-indigo-500/30">
            <BookOpen size={26} strokeWidth={2.4} />
          </div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white tracking-tight">
            智能学习伴侣
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {mode === "login" ? "登录以继续你的学习" : "创建账号开始学习"}
          </p>
        </div>

        {/* 卡片 */}
        <form
          onSubmit={handleSubmit}
          className="bg-white/80 dark:bg-gray-800/80 backdrop-blur rounded-2xl shadow-xl shadow-gray-200/50 dark:shadow-black/30 p-6 space-y-4"
        >
          {error && (
            <div className="bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          {/* 主字段区（根据 mode + provider 动态渲染） */}
          {mode === "register" ? (
            <>
              <Field
                label="用户名"
                placeholder="字母 / 数字 / 中文 / 下划线"
                value={username}
                onChange={setUsername}
                type="text"
                pattern="[a-zA-Z0-9_\\u4e00-\\u9fff]+"
                title="只能包含字母、数字、下划线和中文"
                minLength={3}
                maxLength={32}
              />
              <Field
                label="邮箱（可选）"
                placeholder="用于找回密码"
                value={email}
                onChange={setEmail}
                type="email"
                maxLength={128}
                required={false}
              />
              <Field
                label="显示名称（可选）"
                placeholder="其他用户看到的名称"
                value={displayName}
                onChange={setDisplayName}
                type="text"
                maxLength={64}
                required={false}
              />
            </>
          ) : (
            <Field
              label={provider.fieldLabel}
              placeholder={provider.fieldPlaceholder}
              value={provider.fieldKey === "email" ? email : username}
              onChange={provider.fieldKey === "email" ? setEmail : setUsername}
              type={provider.fieldType}
              minLength={provider.fieldKey === "username" ? 3 : undefined}
              maxLength={provider.fieldKey === "username" ? 32 : 128}
              pattern={provider.fieldValidation?.pattern}
              title={provider.fieldValidation?.title}
            />
          )}

          <Field
            label="密码"
            placeholder="至少 6 个字符"
            value={password}
            onChange={setPassword}
            type="password"
            minLength={6}
            maxLength={64}
          />

          {/* 主登录按钮 */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 disabled:opacity-60 text-white font-medium transition-all shadow-md shadow-indigo-500/30 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 size={16} className="animate-spin" />}
            {mode === "login" ? "登 录" : "注 册"}
          </button>

          {/* ── 登录方式切换（按钮下方一行 chip） ── */}
          {mode === "login" && LOCAL_PROVIDERS.length > 1 && (
            <div className="flex items-center justify-center gap-1.5 text-sm pt-1">
              <span className="text-gray-400 dark:text-gray-500">使用</span>
              {LOCAL_PROVIDERS.map((p, i) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => switchLocalProvider(i)}
                  className={`px-2 py-0.5 rounded-md transition-colors ${
                    i === providerIdx
                      ? "text-indigo-600 dark:text-indigo-400 font-medium"
                      : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                  }`}
                >
                  {p.shortLabel}
                </button>
              )).reduce<React.ReactNode[]>(
                (acc, el, i) => (i === 0 ? [el] : [...acc, <span key={`d${i}`} className="text-gray-300 dark:text-gray-600">/</span>, el]),
                [],
              )}
              <span className="text-gray-400 dark:text-gray-500">登录</span>
            </div>
          )}

          {/* ── OAuth 登录（未来启用） ── */}
          {mode === "login" && ENABLED_OAUTH_PROVIDERS.length > 0 && (
            <div className="pt-2 border-t border-gray-100 dark:border-gray-700">
              <div className="flex items-center justify-center gap-3 mt-3">
                {ENABLED_OAUTH_PROVIDERS.map((p) => {
                  const Icon = p.icon;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => {
                        // TODO: 调用 oauth flow
                        setError(`「${p.label}」登录尚未对接`);
                      }}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 text-sm text-gray-700 dark:text-gray-300 transition-colors"
                    >
                      <Icon size={16} />
                      {p.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </form>

        {/* 底部：登录/注册切换 */}
        <div className="text-center text-sm text-gray-500 dark:text-gray-400 mt-5">
          {mode === "login" ? (
            <>
              还没有账号？{" "}
              <button
                type="button"
                onClick={() => switchMode("register")}
                className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 font-medium"
              >
                立即注册
              </button>
            </>
          ) : (
            <>
              已有账号？{" "}
              <button
                type="button"
                onClick={() => switchMode("login")}
                className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 font-medium"
              >
                返回登录
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── 内部小组件：统一的输入框 ──
function Field(props: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  type: "text" | "email" | "password";
  required?: boolean;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  title?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
        {props.label}
      </label>
      <input
        type={props.type}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        required={props.required ?? true}
        minLength={props.minLength}
        maxLength={props.maxLength}
        pattern={props.pattern}
        title={props.title}
        placeholder={props.placeholder}
        className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900/50 text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500 outline-none transition"
      />
    </div>
  );
}
