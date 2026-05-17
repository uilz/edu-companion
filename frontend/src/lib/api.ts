import { Settings, StreamEvent } from "@/types";

let ws: WebSocket | null = null;
let tokenBuffer = "";

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return window.location.origin;
  }
  return "";
}

export function getSettings(): Settings {
  if (typeof window === "undefined") {
    return { apiEndpoint: "", apiKey: "", modelName: "", systemPrompt: "你是一个智能学习助手，善于用简单易懂的方式解释复杂的概念。回答时使用中文，必要时使用数学公式。" };
  }
  const saved = localStorage.getItem("edu-companion-settings");
  if (saved) {
    return JSON.parse(saved);
  }
  return {
    apiEndpoint: "",
    apiKey: "",
    modelName: "",
    systemPrompt: "你是一个智能学习助手，善于用简单易懂的方式解释复杂的概念。回答时使用中文，必要时使用数学公式。",
  };
}

export function saveSettings(settings: Settings): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("edu-companion-settings", JSON.stringify(settings));
  }
}

export function connectWebSocket(
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (error: string) => void
): void {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.close();
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("[WS] 连接成功:", wsUrl);
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        const msgType = data.type;
        const payload = data.payload || {};

        switch (msgType) {
          case "token":
            // 兼容旧格式
            if (data.content) {
              tokenBuffer += data.content;
              onToken(data.content);
            }
            break;
          case "stream":
            // 后端实际发送的格式: { type: "stream", payload: { content: "..." } }
            if (payload.content) {
              tokenBuffer += payload.content;
              onToken(payload.content);
            }
            break;
          case "status":
            // 状态消息，可以显示给用户
            console.log("[WS] 状态:", payload.message);
            break;
          case "done":
            onDone();
            break;
          case "error":
            onError(payload.message || data.content || "未知错误");
            break;
          case "pong":
            break;
          default:
            console.log("[WS] 未知消息类型:", msgType, data);
        }
      } catch (e) {
        console.error("[WS] 解析失败:", e, event.data);
        onError("解析消息失败");
      }
    };

    ws.onerror = (e) => {
      console.error("[WS] 连接错误:", e);
      onError("WebSocket 连接错误");
    };

    ws.onclose = (e) => {
      console.log("[WS] 连接关闭:", e.code, e.reason);
      ws = null;
    };
  } catch (e) {
    console.error("[WS] 无法建立连接:", e);
    onError("无法建立 WebSocket 连接");
  }
}

export function sendMessage(
  conversationId: string,
  message: string,
  settings: Settings
): void {
  tokenBuffer = "";
  if (ws && ws.readyState === WebSocket.OPEN) {
    const payload = JSON.stringify({
      conversationId,
      message,
      settings,
    });
    console.log("[WS] 发送:", payload.slice(0, 100));
    ws.send(payload);
  } else {
    console.warn("[WS] 未连接，无法发送");
  }
}

export function disconnectWebSocket(): void {
  if (ws) {
    ws.close();
    ws = null;
  }
}

export function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
}

// Fallback REST streaming via fetch
export async function sendViaFetch(
  conversationId: string,
  message: string,
  settings: Settings,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (error: string) => void
): Promise<void> {
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversationId, message, settings }),
    });

    if (!res.ok) {
      onError(`请求失败: ${res.status}`);
      return;
    }

    // HTTP 接口返回的是完整 JSON，不是流式
    const data = await res.json();
    if (data.reply) {
      onToken(data.reply);
    }
    onDone();
  } catch (err) {
    onError(err instanceof Error ? err.message : "请求失败");
  }
}
