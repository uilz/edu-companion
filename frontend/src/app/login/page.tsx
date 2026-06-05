"use client";

import React, { useState } from "react";
import { useAuth } from "../../contexts/AuthContext";

export default function LoginPage() {
  const { login, loginByEmail, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loginType, setLoginType] = useState<"username" | "email">("username");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "login") {
        if (loginType === "email") {
          await loginByEmail(email, password);
        } else {
          await login(username, password);
        }
      } else {
        await register(username, password, displayName || username, email);
      }
      // 登录/注册成功后跳转
      window.location.href = "/";
    } catch (err: any) {
      setError(err.message || "操作失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-600 text-white text-2xl font-bold mb-4 shadow-lg">
            AI
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            智能学习伴侣
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            {mode === "login" ? "登录你的账号" : "创建新账号"}
          </p>
        </div>

        {/* 表单 */}
        <form
          onSubmit={handleSubmit}
          className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 space-y-5"
        >
          {error && (
            <div className="bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          {/* 登录方式切换 */}
          {mode === "login" && (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setLoginType("username")}
                className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${
                  loginType === "username"
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                }`}
              >
                用户名登录
              </button>
              <button
                type="button"
                onClick={() => setLoginType("email")}
                className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${
                  loginType === "email"
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                }`}
              >
                邮箱登录
              </button>
            </div>
          )}

          {mode === "register" || loginType === "username" ? (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                用户名
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={3}
                maxLength={32}
                pattern="[a-zA-Z0-9_\u4e00-\u9fff]+"
                title="只能包含字母、数字、下划线和中文"
                placeholder="请输入用户名（字母/数字/中文/下划线）"
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition"
              />
              {username && !/^[a-zA-Z0-9_\u4e00-\u9fff]+$/.test(username) && (
                <p className="text-xs text-red-500 mt-1">用户名只能包含字母、数字、下划线和中文</p>
              )}
            </div>
          ) : null}

          {loginType === "email" && mode === "login" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                邮箱
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="请输入邮箱"
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition"
              />
            </div>
          )}

          {mode === "register" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                邮箱（可选）
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                maxLength={128}
                placeholder="用于找回密码（可选）"
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition"
              />
            </div>
          )}

          {mode === "register" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                显示名称
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                maxLength={64}
                placeholder="可选，其他用户看到的名称"
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
              密码
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              maxLength={64}
              placeholder="请输入密码（至少6个字符）"
              className="w-full px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition"
            />
            {mode === "register" && password && password.length < 6 && (
              <p className="text-xs text-red-500 mt-1">密码至少需要6个字符</p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-medium transition-colors"
          >
            {loading ? "处理中..." : mode === "login" ? "登 录" : "注 册"}
          </button>

          <div className="text-center text-sm text-gray-500 dark:text-gray-400">
            {mode === "login" ? (
              <>
                还没有账号？{" "}
                <button
                  type="button"
                  onClick={() => { setMode("register"); setError(""); }}
                  className="text-indigo-600 hover:text-indigo-700 font-medium"
                >
                  立即注册
                </button>
              </>
            ) : (
              <>
                已有账号？{" "}
                <button
                  type="button"
                  onClick={() => { setMode("login"); setError(""); }}
                  className="text-indigo-600 hover:text-indigo-700 font-medium"
                >
                  返回登录
                </button>
              </>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
