// ============================================================
// RightPanel — 右栏 (任务 #76)
//
// 设计目标：
//   - 宽度 320px (默认)，可被 Workbench 拖动调整 (200-500)
//   - 4 个 tab：AI 助手 / 上下文 / 详情 / 状态
//   - 用户可自由切换；tab 选择也持久化到 localStorage
//
// 风格遵循 design-language.md professional 风格
// ============================================================

"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  Sparkles,
  ListTree,
  FileText,
  Activity,
  Send,
  Loader2,
  Bot,
  User as UserIcon,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { usePathname } from "next/navigation";
import { authedFetch, api } from "@/lib/api/api";

// authedFetch 在 AI tab 使用（POST 请求），api 在其他 tab 使用（GET JSON）

// ── Tab 类型 ──
type RightTab = "ai" | "context" | "details" | "status";
const TAB_KEY = "workbench-right-tab";
const TABS: { key: RightTab; label: string; icon: typeof Sparkles }[] = [
  { key: "ai", label: "AI 助手", icon: Sparkles },
  { key: "context", label: "上下文", icon: ListTree },
  { key: "details", label: "详情", icon: FileText },
  { key: "status", label: "状态", icon: Activity },
];

// ── AI 对话消息 ──
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  ts: number;
}

export default function RightPanel() {
  const { user } = useAuth();
  const pathname = usePathname() || "/";

  // 当前 tab，持久化
  const [activeTab, setActiveTab] = useState<RightTab>("ai");
  useEffect(() => {
    try {
      const saved = localStorage.getItem(TAB_KEY) as RightTab | null;
      if (saved && TABS.find((t) => t.key === saved)) setActiveTab(saved);
    } catch {}
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(TAB_KEY, activeTab);
    } catch {}
  }, [activeTab]);

  // 监听 AI 唤起事件
  useEffect(() => {
    const handler = () => setActiveTab("ai");
    window.addEventListener("workbench-ai-invoke", handler);
    return () => window.removeEventListener("workbench-ai-invoke", handler);
  }, []);

  return (
    <div className="h-full w-full flex flex-col">
      {/* Tab 栏 */}
      <div className="flex border-b border-divider bg-page-secondary/40">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = activeTab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[12px] font-medium transition-colors ${
                active
                  ? "text-accent border-b-2 border-accent bg-accent/5"
                  : "text-ink-muted hover:text-ink-primary border-b-2 border-transparent"
              }`}
            >
              <Icon size={13} />
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab 内容 */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {activeTab === "ai" && <AITab user={user} />}
        {activeTab === "context" && <ContextTab pathname={pathname} />}
        {activeTab === "details" && <DetailsTab pathname={pathname} />}
        {activeTab === "status" && <StatusTab />}
      </div>
    </div>
  );
}

// ════════════════ AI 助手 Tab ════════════════
function AITab({ user }: { user: ReturnType<typeof useAuth>["user"] }) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "你好，我是你的学习助手。可以问学习问题、生成练习、推荐资源。",
      ts: Date.now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  const send = useCallback(async () => {
    const q = input.trim();
    if (!q || sending) return;
    const userMsg: ChatMessage = { role: "user", content: q, ts: Date.now() };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setSending(true);
    try {
      // 简化：使用 secretary agent chat 端点（SSE 流，但非流场景下取首条）
      const res = await authedFetch(
        `/api/secretary/agent/chat?user_id=${user?.id || "guest"}`,
        {
          method: "POST",
          body: JSON.stringify({ message: q, stream: false }),
        },
      );
      // 尝试解析 JSON
      let reply = "（无回复）";
      try {
        const data = await res.json();
        reply = data?.reply || data?.content || data?.text || reply;
      } catch {
        reply = "（回复非 JSON 格式）";
      }
      setMessages((m) => [...m, { role: "assistant", content: reply, ts: Date.now() }]);
    } catch (e: any) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "（AI 接口暂不可用）" + (e?.message ? `：${e.message}` : ""),
          ts: Date.now(),
        },
      ]);
    } finally {
      setSending(false);
    }
  }, [input, sending, user]);

  return (
    <div className="h-full flex flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex gap-2 ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {m.role === "assistant" && (
              <div className="w-6 h-6 rounded-full bg-accent/15 text-accent flex items-center justify-center shrink-0">
                <Bot size={12} />
              </div>
            )}
            <div
              className={`max-w-[80%] px-2.5 py-1.5 rounded-md text-[12px] leading-relaxed ${
                m.role === "user"
                  ? "bg-accent text-white"
                  : "bg-surface text-ink-primary"
              }`}
            >
              {m.content}
            </div>
            {m.role === "user" && (
              <div className="w-6 h-6 rounded-full bg-surface text-ink-secondary flex items-center justify-center shrink-0">
                <UserIcon size={12} />
              </div>
            )}
          </div>
        ))}
        {sending && (
          <div className="flex items-center gap-2 text-ink-muted text-[11px]">
            <Loader2 size={12} className="animate-spin" />
            思考中…
          </div>
        )}
      </div>
      <div className="border-t border-divider p-2 flex gap-1.5">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="向 AI 提问…"
          className="flex-1 h-8 px-2 text-[12px] bg-surface text-ink-primary rounded border border-divider focus:outline-none focus:border-accent"
          disabled={sending}
        />
        <button
          onClick={send}
          disabled={sending || !input.trim()}
          className="px-2 h-8 rounded bg-accent text-white disabled:opacity-50 hover:opacity-90 transition-opacity"
        >
          {sending ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
        </button>
      </div>
    </div>
  );
}

// ════════════════ 上下文 Tab ════════════════
function ContextTab({ pathname }: { pathname: string }) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    // 当前路径作为上下文：尝试加载对话树 / 相关笔记
    api<any>(`/api/conversations/tree/conversations/recent?limit=20`)
      .then((d) => {
        if (!active) return;
        setItems(d?.conversations || d?.items || []);
      })
      .catch(() => {})
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [pathname]);

  return (
    <div className="h-full overflow-y-auto px-3 py-3">
      <div className="text-[11px] uppercase tracking-wider text-ink-muted mb-2">当前路径</div>
      <div className="text-[12px] text-ink-primary px-2 py-1.5 rounded bg-surface mb-3 truncate">
        {pathname}
      </div>

      <div className="text-[11px] uppercase tracking-wider text-ink-muted mb-2">最近对话</div>
      {loading ? (
        <div className="flex justify-center py-4">
          <Loader2 size={14} className="animate-spin text-ink-muted" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-[12px] text-ink-muted text-center py-4">暂无对话</div>
      ) : (
        <div className="space-y-1">
          {items.slice(0, 10).map((it, i) => (
            <div
              key={i}
              className="px-2 py-1.5 text-[12px] text-ink-secondary rounded hover:bg-surface-hover truncate"
              title={it.title || it.name || it.id}
            >
              {it.title || it.name || `对话 ${i + 1}`}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ════════════════ 详情 Tab ════════════════
function DetailsTab({ pathname }: { pathname: string }) {
  return (
    <div className="h-full overflow-y-auto px-3 py-3 text-[12px] text-ink-secondary space-y-3">
      <div>
        <div className="text-[11px] uppercase tracking-wider text-ink-muted mb-1.5">路径</div>
        <div className="px-2 py-1.5 rounded bg-surface text-ink-primary font-mono text-[11px] break-all">
          {pathname}
        </div>
      </div>
      <div>
        <div className="text-[11px] uppercase tracking-wider text-ink-muted mb-1.5">说明</div>
        <p className="leading-relaxed">
          这里是当前页面的详情面板。不同路由可在此处展示：
        </p>
        <ul className="list-disc pl-4 mt-1.5 space-y-0.5 text-[11px] text-ink-muted">
          <li>知识节点信息（学习页面）</li>
          <li>任务元数据（规划页面）</li>
          <li>数据统计（仪表盘）</li>
        </ul>
      </div>
    </div>
  );
}

// ════════════════ 状态 Tab ════════════════
function StatusTab() {
  const [health, setHealth] = useState<{ ok: boolean; latency: number } | null>(null);
  const [userInfo, setUserInfo] = useState<any>(null);

  useEffect(() => {
    const t0 = Date.now();
    api<any>("/api/auth/me")
      .then((u) => {
        setUserInfo(u);
        setHealth({ ok: true, latency: Date.now() - t0 });
      })
      .catch(() => setHealth({ ok: false, latency: -1 }));
  }, []);

  return (
    <div className="h-full overflow-y-auto px-3 py-3 text-[12px] text-ink-secondary space-y-3">
      <div>
        <div className="text-[11px] uppercase tracking-wider text-ink-muted mb-1.5">系统</div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${health?.ok ? "bg-success" : "bg-error"}`} />
          <span className="text-ink-primary">
            {health?.ok ? "在线" : health ? "离线" : "检测中…"}
          </span>
          {health && health.latency >= 0 && (
            <span className="text-ink-muted text-[11px]">{health.latency}ms</span>
          )}
        </div>
      </div>

      {userInfo && (
        <div>
          <div className="text-[11px] uppercase tracking-wider text-ink-muted mb-1.5">账户</div>
          <div className="space-y-1 text-[12px]">
            <div className="flex justify-between">
              <span className="text-ink-muted">用户</span>
              <span className="text-ink-primary">{userInfo.username}</span>
            </div>
            {userInfo.role && (
              <div className="flex justify-between">
                <span className="text-ink-muted">角色</span>
                <span className="text-ink-primary">{userInfo.role}</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div>
        <div className="text-[11px] uppercase tracking-wider text-ink-muted mb-1.5">快捷键</div>
        <div className="space-y-1 text-[11px]">
          <div className="flex justify-between">
            <span>命令面板</span>
            <kbd className="text-[10px] px-1.5 py-0.5 rounded border border-divider text-ink-muted">⌘K</kbd>
          </div>
          <div className="flex justify-between">
            <span>AI 助手</span>
            <kbd className="text-[10px] px-1.5 py-0.5 rounded border border-divider text-ink-muted">⌘J</kbd>
          </div>
        </div>
      </div>
    </div>
  );
}
