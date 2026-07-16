// ============================================================
// EXP-04 · Mechanism Event Logger
//
// 收集 Session 机制事件用于验证 Safety → Search → Self-resolution 链路。
// 不是产品数据、不是运营指标、不是 KPI。
//
// 原则：
//   - 不收集用户输入内容（隐私）
//   - 不计算相似度 / 正确率（不考核）
//   - 不阻塞 UI（fire-and-forget）
//   - 不重试失败（安静丢弃，不打扰用户）
// ============================================================

import { API_BASE } from "@/lib/api/api";

// ── 事件类型 ───────────────────────────────────────────────

export type MechanismEventName =
  | "session.entered"
  | "session.started"
  | "chat.drawer_opened"
  | "chat.message_sent"
  | "chat.drawer_closed"
  | "cognitive_search.entered"
  | "cognitive_search.resumed"
  | "self_validation.started"
  | "self_validation.submitted"
  | "self_validation.compared"
  | "self_validation.went_back"
  | "self_validation.continued"
  | "reflection.started"
  | "reflection.submitted"
  | "reflection.skipped"
  | "session.ended";

export interface MechanismEvent {
  event: MechanismEventName;
  timestamp: string; // ISO 8601
  seq: number;
  payload: Record<string, unknown>;
}

// ── Logger 内部状态 ───────────────────────────────────────

let seq = 0;
let sessionId: string | null = null;
let buffer: MechanismEvent[] = [];
let flushed = false;

// ── 公共 API ──────────────────────────────────────────────

/** 初始化 — Session 进入时调用一次 */
export function initMechanismLogger(sid: string): void {
  sessionId = sid;
  seq = 0;
  buffer = [];
  flushed = false;
}

/** 记录一个机制事件（fire-and-forget，永不抛异常） */
export function logMechanismEvent(
  event: MechanismEventName,
  payload: Record<string, unknown> = {},
): void {
  if (!sessionId) return;

  seq += 1;
  const entry: MechanismEvent = {
    event,
    timestamp: new Date().toISOString(),
    seq,
    payload,
  };
  buffer.push(entry);

  // 高危事件（session.ended）立即 flush。其他事件批量发送。
  if (event === "session.ended") {
    // 不 await — fire-and-forget
    flushEvents();
  }
}

/** 批量发送事件到后端 */
export function flushEvents(): void {
  if (!sessionId || buffer.length === 0 || flushed) return;

  const toSend = [...buffer];
  buffer = [];

  // fire-and-forget — 不阻塞页面
  sendEvents(sessionId, toSend).catch(() => {
    // 静默失败。事件采集失败不应影响用户学习体验。
  });
}

// ── 内部 ──────────────────────────────────────────────────

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("access_token");
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function sendEvents(
  sid: string,
  events: MechanismEvent[],
): Promise<void> {
  const authHeaders = getAuthHeaders();

  const res = await fetch(`${API_BASE}/api/session/${sid}/events`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ events }),
  });

  if (!res.ok) {
    // 静默失败
    console.debug(
      `[mechanism-logger] Failed to send ${events.length} events: ${res.status}`,
    );
  }
}

// ── 辅助：从 localStorage 批量发送（页面关闭前） ──────────

if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    if (buffer.length > 0 && sessionId && !flushed) {
      // 使用 sendBeacon 确保页面关闭前发送
      const payload = JSON.stringify({ events: buffer });
      const blob = new Blob([payload], { type: "application/json" });
      navigator.sendBeacon(
        `${API_BASE}/api/session/${sessionId}/events`,
        blob,
      );
    }
  });
}
