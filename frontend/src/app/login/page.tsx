"use client";

/**
 * 登录 / 注册页（v3 — 集成 Cloudflare Turnstile）
 *
 * 设计要点:
 * 1. 主区一个表单，根据当前 LocalProvider 动态渲染字段
 * 2. 登录按钮下方一行 chip「使用 用户名 / 邮箱 登录」→ 不抢主视觉、可扩展
 * 3. OAuth（未来）独立一排按钮，与本地登录互不干扰
 * 4. 切换方式时，只切换字段，不刷新页面
 * 5. 注册/登录集成 Turnstile 人机验证
 */

import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

interface TurnstileObject {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string;
  reset: (id: string) => void;
  remove: (id: string) => void;
}

interface TurnstileWindow extends Window {
  turnstile?: TurnstileObject;
}
import { BookOpen, Loader2 } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import {
  LOCAL_PROVIDERS,
  ENABLED_OAUTH_PROVIDERS,
  type LocalLoginProvider,
} from "@/lib/auth/providers";

// Turnstile 站点密钥（在 .env.local 中配置）
const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
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

  // Turnstile 状态
  const [turnstileToken, setTurnstileToken] = useState("");
  const turnstileRef = useRef<HTMLDivElement>(null);
  const turnstileWidgetId = useRef<string | null>(null);

  const switchMode = (m: Mode) => {
    setMode(m);
    setError("");
    setTurnstileToken("");
  };

  const switchLocalProvider = (idx: number) => {
    setProviderIdx(idx);
    setError("");
  };

  // ── 加载 Turnstile 脚本并渲染 widget ──
  useEffect(() => {
    if (!TURNSTILE_SITE_KEY || !turnstileRef.current) return;

    // 如果 widget 已渲染，重置
    const win = window as unknown as TurnstileWindow;
    if (turnstileWidgetId.current && win.turnstile) {
      win.turnstile.reset(turnstileWidgetId.current);
      return;
    }

    // 加载 Turnstile 脚本
    if (!document.getElementById("turnstile-script")) {
      const script = document.createElement("script");
      script.id = "turnstile-script";
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
      script.async = true;
      script.defer = true;
      script.onload = () => {
        renderTurnstile();
      };
      document.body.appendChild(script);
    } else if ((window as unknown as TurnstileWindow).turnstile) {
      renderTurnstile();
    }

    function renderTurnstile() {
      const ts = (window as unknown as TurnstileWindow).turnstile;
      if (!turnstileRef.current || !ts) return;
      // 清除已有内容
      turnstileRef.current.innerHTML = "";
      turnstileWidgetId.current = ts.render(
        turnstileRef.current,
        {
          sitekey: TURNSTILE_SITE_KEY,
          callback: (token: string) => {
            setTurnstileToken(token);
          },
          "expired-callback": () => {
            setTurnstileToken("");
          },
          "error-callback": () => {
            setTurnstileToken("");
          },
          theme: "auto",
        }
      );
    }

    return () => {
      // 清理 widget
      const ts = (window as unknown as TurnstileWindow).turnstile;
      if (turnstileWidgetId.current && ts) {
        try {
          ts.remove(turnstileWidgetId.current);
        } catch {}
        turnstileWidgetId.current = null;
      }
    };
  }, [mode, providerIdx]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // Turnstile 验证检查（如果配置了 site key）
    if (TURNSTILE_SITE_KEY && !turnstileToken) {
      setError("请完成人机验证");
      return;
    }

    setLoading(true);

    try {
      if (mode === "login") {
        if (provider.id === "email") {
          await loginByEmail(email, password, turnstileToken);
        } else {
          await login(username, password, turnstileToken);
        }
      } else {
        // 注册始终使用用户名作为主键（邮箱为可选）
        await register(username, password, displayName || username, email, turnstileToken);
      }
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "操作失败");
      // Turnstile 令牌已使用，重置
      resetTurnstile();
    } finally {
      setLoading(false);
    }
  };

  const resetTurnstile = () => {
    setTurnstileToken("");
    const win = window as unknown as TurnstileWindow;
    if (turnstileWidgetId.current && win.turnstile) {
      win.turnstile.reset(turnstileWidgetId.current);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-page px-4">
      <div className="w-full max-w-sm">
        {/* Logo + 文案 */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-accent text-white mb-3 shadow-glow">
            <BookOpen size={26} strokeWidth={2.4} />
          </div>
          <h1 className="text-xl font-semibold text-ink-primary tracking-tight">
            苹果果学习助手
          </h1>
          <p className="text-sm text-ink-secondary mt-1">
            {mode === "login" ? "登录以继续你的学习" : "创建账号开始学习"}
          </p>
        </div>

        {/* 卡片 */}
        <form
          onSubmit={handleSubmit}
          className="bg-surface backdrop-blur rounded-2xl shadow-md p-6 space-y-4"
        >
          {error && (
            <div className="bg-danger/10 text-danger text-sm rounded-lg px-3 py-2">
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

          {/* ── Turnstile 验证控件 ── */}
          {TURNSTILE_SITE_KEY && (
            <div
              className="flex justify-center"
              style={{ overflow: "visible", position: "relative", zIndex: 9999 }}
            >
              <div ref={turnstileRef} />
            </div>
          )}

          {/* 主登录按钮 */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 rounded-lg bg-accent hover:bg-accent-hover disabled:opacity-60 text-white font-medium transition-all shadow-md flex items-center justify-center gap-2"
          >
            {loading && <Loader2 size={16} className="animate-spin" />}
            {mode === "login" ? "登 录" : "注 册"}
          </button>

          {/* ── 登录方式切换（按钮下方一行 chip） ── */}
          {mode === "login" && LOCAL_PROVIDERS.length > 1 && (
            <div className="flex items-center justify-center gap-1.5 text-sm pt-1">
              <span className="text-ink-muted">使用</span>
              {LOCAL_PROVIDERS.map((p, i) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => switchLocalProvider(i)}
                  className={`px-2 py-0.5 rounded-md transition-colors ${
                    i === providerIdx
                      ? "text-accent font-medium"
                      : "text-ink-muted hover:text-ink-primary"
                  }`}
                >
                  {p.shortLabel}
                </button>
              )).reduce<React.ReactNode[]>(
                (acc, el, i) => (i === 0 ? [el] : [...acc, <span key={`d${i}`} className="text-divider">/</span>, el]),
                [],
              )}
              <span className="text-ink-muted">登录</span>
            </div>
          )}

          {/* ── OAuth 登录（未来启用） ── */}
          {mode === "login" && ENABLED_OAUTH_PROVIDERS.length > 0 && (
            <div className="pt-2 border-t border-divider">
              <div className="flex items-center justify-center gap-3 mt-3">
                {ENABLED_OAUTH_PROVIDERS.map((p) => {
                  const Icon = p.icon;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => {
                        setError(`「${p.label}」登录尚未对接`);
                      }}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-divider hover:bg-surface-hover text-sm text-ink-secondary transition-colors"
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
        <div className="text-center text-sm text-ink-secondary mt-5">
          {mode === "login" ? (
            <>
              还没有账号？{" "}
              <button
                type="button"
                onClick={() => switchMode("register")}
                className="text-accent hover:text-accent-hover font-medium"
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
                className="text-accent hover:text-accent-hover font-medium"
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
      <label className="block text-xs font-medium text-ink-secondary mb-1">
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
        className="w-full px-3 py-2 rounded-lg border border-divider bg-input text-sm text-ink-primary focus:ring-2 focus:ring-accent/40 focus:border-accent outline-none transition"
      />
    </div>
  );
}
