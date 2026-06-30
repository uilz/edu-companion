"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { MessageCircle, X, ChevronDown } from "lucide-react";
import { getAgentStore, useAgentStore, type ToolCallEvent } from "@/store/agent/agent-store";
import { useChatStream } from "@/components/chat-shared/useChatStream";
import ChatMessages from "@/components/chat-shared/ChatMessages";
import ChatInputBar from "@/components/chat-shared/ChatInputBar";
import ToolCallConfirmation from "@/components/chat-shared/ToolCallConfirmation";
import { apiFetch } from "@/store/conversation/tree-helpers";

// ══════════════════════════════════════════════════════════════
//  Helpers — 秘书树操作
// ══════════════════════════════════════════════════════════════

const SECRETARY_DIR_NAME = "🤖 秘书对话";

/** 确保「秘书对话」目录存在，返回其 ID */
async function ensureSecretaryDir(): Promise<string | null> {
  try {
    const data = await apiFetch<{ directory_nodes: any[] }>("/tree/directory");
    const nodes = data.directory_nodes || [];
    const existing = nodes.find((n) => n.kind === "secretary");
    if (existing) return existing.id;

    // 创建新的秘书目录
    const created = await apiFetch<{ directory_node: { id: string } }>("/tree/directory", {
      method: "POST",
      body: JSON.stringify({ node_type: "dir", kind: "secretary", name: SECRETARY_DIR_NAME, emoji: "🤖" }),
    });
    return created.directory_node?.id || null;
  } catch {
    return null;
  }
}

/** 获取秘书目录下的所有对话 */
async function loadSecretaryConvs(dirId: string) {
  try {
    const data = await apiFetch<{ directory_nodes: any[] }>(`/tree/directory?parent_id=${dirId}`);
    const convs = (data.directory_nodes || [])
      .filter((n) => n.node_type === "conv")
      .map((n) => ({
        id: n.id,
        name: n.name || "秘书对话",
        messageCount: (n as any).message_count || 0,
        createdAt: (n as any).created_at || 0,
      }));
    return convs;
  } catch {
    return [];
  }
}

/** 在秘书目录下创建一个新对话（按日期命名） */
async function createSecretaryConv(dirId: string): Promise<string | null> {
  const today = new Date();
  const dateStr = `${today.getMonth() + 1}/${today.getDate()} ${today.getHours().toString().padStart(2, "0")}:${today.getMinutes().toString().padStart(2, "0")}`;
  try {
    const data = await apiFetch<{ directory_node: { id: string } }>("/tree/directory", {
      method: "POST",
      body: JSON.stringify({
        node_type: "conv",
        kind: "secretary",
        parent_id: dirId,
        name: dateStr,
      }),
    });
    return data.directory_node?.id || null;
  } catch {
    return null;
  }
}

/** 加载秘书对话的消息列表 */
async function loadSecretaryMessages(convId: string): Promise<{ role: "user" | "assistant"; content: string }[]> {
  try {
    const data = await apiFetch<{ messages: any[] }>(`/tree/conversation/${convId}/messages?limit=100&offset=0`);
    return (data.messages || [])
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.text_summary || m.content || "",
      }));
  } catch {
    return [];
  }
}

/** 保存一条消息到树对话 */
async function saveMessageToTreeConv(convId: string, role: "user" | "assistant", content: string): Promise<void> {
  try {
    await apiFetch(`/tree/conversation/${convId}/message`, {
      method: "POST",
      body: JSON.stringify({
        role,
        content_blocks: [{ type: "text", text: content }],
        text_summary: content,
      }),
    });
  } catch (e) {
    console.error(`[Secretary] 保存 ${role} 消息失败:`, e);
  }
}

// ══════════════════════════════════════════════════════════════
//  Component
// ══════════════════════════════════════════════════════════════

export default function AgentFloat() {
  const pathname = usePathname();
  const router = useRouter();
  const messages = useAgentStore((s) => s.messages);
  const currentToolCall = useAgentStore((s) => s.currentToolCall);
  const secretaryConvs = useAgentStore((s) => s.secretaryConvs);
  const activeConvId = useAgentStore((s) => s.activeConvId);
  const loadingSecretary = useAgentStore((s) => s.loadingSecretary);
  const loadingMessages = useAgentStore((s) => s.loadingMessages);
  const store = getAgentStore();
  const { streaming, send } = useChatStream();

  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const [showConvList, setShowConvList] = useState(false);

  // ── 浮现动画状态（防止刷新瞬移）──
  const [visible, setVisible] = useState(false);

  // ── 拖动状态 ──
  const floatRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const dragState = useRef({
    dragging: false,
    isPanelDrag: false,        // true=面板拖拽, false=球拖拽
    moved: false,
    startX: 0,
    startY: 0,
    startLeft: 0,
    startTop: 0,
    // 面板拖拽时记录面板初始位置（用于 delta 计算）
    panelStartRight: 0,        // 面板 css right 初始值 (px)
    panelStartTop: 0,          // 面板相对于视口顶部的初始 Y (px)
    panelStartWidth: 0,        // 面板实际宽度 (px)，用于 X 边界夹紧
    panelStartHeight: 0,       // 面板实际高度 (px)，用于 Y 边界夹紧
  });

  type SnapSide = "none" | "left" | "right" | "top" | "bottom";
  // 用 ref 存储实时位置，避免拖动时频繁 setState 导致卡顿
  const posRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const snappedRef = useRef<SnapSide>("right");
  // 仅在拖动结束时 setState 触发重渲染
  const [renderPos, setRenderPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [snapped, setSnapped] = useState<SnapSide>("right");
  const [dragging, setDragging] = useState(false);
  const openRef = useRef(false);
  useEffect(() => { openRef.current = open; }, [open]);

  // 面板展开时球在视口的方位 → 收起时球应出现在面板的对面侧
  const openDirRef = useRef<{ h: "left" | "right"; v: "top" | "bottom" }>({ h: "right", v: "bottom" });

  // 夹紧球到当前视口并重新吸附
  const clampAndSnap = useCallback((pos: { x: number; y: number }) => {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let { x, y } = pos;
    x = Math.max(0, Math.min(vw - 48, x));
    y = Math.max(0, Math.min(vh - 48, y));
    posRef.current = { x, y };

    const result = snap(x, y);
    if (result) {
      snappedRef.current = result.side;
      posRef.current = { x: result.x, y: result.y };
      setSnapped(result.side);
    } else {
      snappedRef.current = "none";
      setSnapped("none");
    }
    setRenderPos({ ...posRef.current });
    try { localStorage.setItem(POS_KEY, JSON.stringify(posRef.current)); } catch {}
  }, []);

  // 窗口尺寸变化时：清除面板位置记忆，重新夹紧球位置并吸附
  useEffect(() => {
    const onResize = () => {
      setPanelPos(null);
      clampAndSnap(posRef.current);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [clampAndSnap]);

  // 面板被用户拖拽后的精确位置（非 null 时直接以此渲染，不从球反算）
  const [panelPos, setPanelPos] = useState<{ right: number; top: number } | null>(null);

  // 位置持久化
  const POS_KEY = "agent-float-pos";

  const loadPos = (): { x: number; y: number } | null => {
    try {
      const saved = localStorage.getItem(POS_KEY);
      if (saved) return JSON.parse(saved);
    } catch {}
    return null;
  };

  // 初始化位置，延迟 0.5s 浮现（防止刷新瞬移）
  useEffect(() => {
    const saved = loadPos();
    const initial = saved || { x: window.innerWidth - 64, y: window.innerHeight - 200 };
    // 夹紧到当前视口并吸附（桌面保存的位置在手机上可能溢出）
    clampAndSnap(initial);

    // 延迟 0.5s 后浮现
    const timer = setTimeout(() => setVisible(true), 500);
    return () => clearTimeout(timer);
  }, [clampAndSnap]);

  // 吸附到最近的边缘（水平优先）
  const EDGE_ZONE = 60;
  const snap = (x: number, y: number): { x: number; y: number; side: SnapSide } | null => {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    if (x < EDGE_ZONE) return { x: -24, y, side: "left" };
    if (x > vw - 48 - EDGE_ZONE) return { x: vw - 24, y, side: "right" };
    if (y < EDGE_ZONE) return { x, y: -24, side: "top" };
    if (y > vh - 48 - EDGE_ZONE) return { x, y: vh - 24, side: "bottom" };
    return null;
  };

  // 根据面板当前位置（离哪边近球放哪边）反算球位置并吸附
  const syncBallFromPanel = useCallback(() => {
    if (!panelRef.current) return;
    const rect = panelRef.current.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    // 根据面板与视口各边的距离决定球在哪侧
    // X：面板离左边近 → 球放面板左侧；离右边近 → 球放面板右侧
    const distLeft = rect.left;
    const distRight = vw - rect.right;
    let ballX: number;
    if (distLeft <= distRight) {
      ballX = rect.left - 56;   // 球在面板左侧（球右边缘距面板左边缘 8px）
    } else {
      ballX = rect.right + 8;   // 球在面板右侧（球左边缘距面板右边缘 8px）
    }

    // Y：面板离上边近 → 球放面板上方；离下边近 → 球放面板下方
    const distTop = rect.top;
    const distBottom = vh - rect.bottom;
    let ballY: number;
    if (distTop <= distBottom) {
      ballY = rect.top - 56;    // 球在面板上方（球底边距面板顶边 8px）
    } else {
      ballY = rect.bottom + 8;  // 球在面板下方（球顶边距面板底边 8px）
    }

    // 夹紧到视口内
    ballX = Math.max(0, Math.min(vw - 48, ballX));
    ballY = Math.max(0, Math.min(vh - 48, ballY));

    posRef.current = { x: ballX, y: ballY };

    // 应用吸附
    const result = snap(ballX, ballY);
    if (result) {
      snappedRef.current = result.side;
      posRef.current = { x: result.x, y: result.y };
      setSnapped(result.side);
    } else {
      snappedRef.current = "none";
      setSnapped("none");
    }

    setRenderPos({ ...posRef.current });
    try { localStorage.setItem(POS_KEY, JSON.stringify(posRef.current)); } catch {}
  }, []);

  // 登录页不显示悬浮球
  if (pathname === "/login") return null;

  // 加载用户偏好
  useEffect(() => {
    import("@/lib/api/api").then(({ api }) => {
      api<any>("/api/secretary/agent/preferences")
        .then((data) => {
          if (data.confirm_mode) store.setConfirmMode(data.confirm_mode);
          if (data.auto_jump_threshold !== undefined) {
            store.setAutoJumpThreshold(data.auto_jump_threshold);
          }
        })
        .catch(() => { /* 使用默认偏好 */ });
    });
  }, []);

  // ── 打开面板时初始化秘书对话 ──
  const initSecretary = useCallback(async () => {
    if (store.secretaryDirId && store.activeConvId) return;

    store.setLoadingSecretary(true);
    try {
      // 1. 确保秘书目录存在
      let dirId = store.secretaryDirId;
      if (!dirId) {
        dirId = await ensureSecretaryDir();
        if (!dirId) { store.setLoadingSecretary(false); return; }
        store.setSecretaryDirId(dirId);
      }

      // 2. 获取对话列表
      const convs = await loadSecretaryConvs(dirId);
      store.setSecretaryConvs(convs);

      // 3. 使用最新对话（或创建新对话）
      let convId = store.activeConvId;
      if (!convId) {
        // 取最近的对话（有消息的），否则新建
        const active = convs.sort((a, b) => b.createdAt - a.createdAt)[0];
        if (active) {
          convId = active.id;
        } else {
          convId = await createSecretaryConv(dirId);
          if (!convId) { store.setLoadingSecretary(false); return; }
          // 刷新列表
          const updatedConvs = await loadSecretaryConvs(dirId);
          store.setSecretaryConvs(updatedConvs);
        }
        store.setActiveConvId(convId!);
        store.setConversationId(convId!);
      }

      // 4. 加载消息
      if (convId && store.messages.length === 0) {
        store.setLoadingMessages(true);
        const msgs = await loadSecretaryMessages(convId!);
        if (msgs.length > 0) {
          store.setMessagesFromTree(msgs);
        }
        store.setLoadingMessages(false);
      }
    } finally {
      store.setLoadingSecretary(false);
    }
  }, []);

  // 打开面板时初始化
  useEffect(() => {
    if (open) {
      initSecretary();
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open, initSecretary]);

  // ── 对话切换 ──
  const handleSwitchConv = useCallback(async (convId: string) => {
    store.switchConv(convId);
    setShowConvList(false);

    // 加载该对话的消息
    store.setLoadingMessages(true);
    const msgs = await loadSecretaryMessages(convId);
    if (msgs.length > 0) {
      store.setMessagesFromTree(msgs);
    }
    store.setLoadingMessages(false);
  }, [secretaryConvs]);

  // ── 新建对话 ──
  const handleNewConv = useCallback(async () => {
    const dirId = store.secretaryDirId;
    if (!dirId) return;
    store.setLoadingSecretary(true);
    const convId = await createSecretaryConv(dirId);
    if (convId) {
      store.setActiveConvId(convId);
      store.setConversationId(convId);
      store.setMessagesFromTree([]);
      // 刷新列表
      const convs = await loadSecretaryConvs(dirId);
      store.setSecretaryConvs(convs);
    }
    store.setLoadingSecretary(false);
    setShowConvList(false);
  }, []);

  // ── 拖动事件 ──
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    _startDrag(e.clientX, e.clientY);
  }, []);

  const _startDrag = useCallback((clientX: number, clientY: number) => {
    const isCurrentlySnapped = snappedRef.current !== "none";
    let startX = posRef.current.x;
    let startY = posRef.current.y;
    if (snappedRef.current === "left") startX = 8;
    else if (snappedRef.current === "right") startX = window.innerWidth - 56;
    else if (snappedRef.current === "top") startY = 8;
    else if (snappedRef.current === "bottom") startY = window.innerHeight - 56;
    posRef.current = { x: startX, y: startY };
    // 同步 DOM 位置，防止从吸附态拖起时 22px 跳变（posRef 从 -24→8 但 DOM 还在 -14.4）
    if (floatRef.current) {
      floatRef.current.style.left = `${startX}px`;
      floatRef.current.style.top = `${startY}px`;
    }
    // 同步更新 ref 和 state，立即解除吸附恢复圆形
    if (isCurrentlySnapped) {
      snappedRef.current = "none";
      setSnapped("none");
    }
    setDragging(true);
    if (floatRef.current) floatRef.current.style.transition = "none";
    dragState.current = {
      dragging: true,
      isPanelDrag: false,
      moved: false,
      startX: clientX,
      startY: clientY,
      startLeft: startX,
      startTop: startY,
      panelStartRight: 0,
      panelStartTop: 0,
      panelStartWidth: 0,
      panelStartHeight: 0,
    };
  }, []);

  // 用原生 addEventListener 注册 float 按钮 touchstart（passive: false）
  useEffect(() => {
    const el = floatRef.current;
    if (!el) return;
    const onTouchStart = (e: TouchEvent) => {
      e.preventDefault();
      _startDrag(e.touches[0].clientX, e.touches[0].clientY);
    };
    el.addEventListener("touchstart", onTouchStart, { passive: false });
    return () => el.removeEventListener("touchstart", onTouchStart);
  }, [_startDrag]);

  // ── 面板拖拽 ──
  const handlePanelMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    _startPanelDrag(e.clientX, e.clientY);
  }, []);

  const _startPanelDrag = useCallback((clientX: number, clientY: number) => {
    setDragging(true);
    if (panelRef.current) panelRef.current.style.transition = "none";

    // 记录面板当前实际位置和尺寸，用于拖拽 delta 计算与边界夹紧
    const rect = panelRef.current!.getBoundingClientRect();
    dragState.current = {
      dragging: true,
      isPanelDrag: true,
      moved: false,
      startX: clientX,
      startY: clientY,
      startLeft: 0,
      startTop: 0,
      panelStartRight: window.innerWidth - rect.right,
      panelStartTop: rect.top,
      panelStartWidth: rect.width,
      panelStartHeight: rect.height,
    };
  }, []);

  // 用原生 addEventListener 注册面板头部 touchstart（passive: false）
  useEffect(() => {
    const el = panelRef.current;
    if (!el) return;
    const onTouchStart = (e: TouchEvent) => {
      e.preventDefault();
      e.stopPropagation();
      _startPanelDrag(e.touches[0].clientX, e.touches[0].clientY);
    };
    el.addEventListener("touchstart", onTouchStart, { passive: false });
    return () => el.removeEventListener("touchstart", onTouchStart);
  }, [_startPanelDrag]);

  useEffect(() => {
    const handleDragMove = (e: MouseEvent | TouchEvent) => {
      if (!dragState.current.dragging) return;
      e.preventDefault();
      const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
      const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;

      const dx = clientX - dragState.current.startX;
      const dy = clientY - dragState.current.startY;

      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
        dragState.current.moved = true;
      }

      if (dragState.current.isPanelDrag) {
        // ── 面板拖拽：只移动面板，球不动 ──
        if (panelRef.current) {
          const vw = window.innerWidth;
          const vh = window.innerHeight;
          const pw = dragState.current.panelStartWidth;
          const ph = dragState.current.panelStartHeight;

          // X 夹紧：面板从左边缘 8px 到右边缘 8px
          const maxRight = Math.max(8, vw - pw - 8);
          const newRight = Math.max(8, Math.min(maxRight, dragState.current.panelStartRight - dx));
          // Y 夹紧：面板从顶边 8px 到底边 8px
          const maxTop = Math.max(0, vh - ph - 8);
          const newTop = Math.max(0, Math.min(maxTop, dragState.current.panelStartTop + dy));

          panelRef.current.style.right = `${newRight}px`;
          panelRef.current.style.top = `${newTop}px`;
          panelRef.current.style.bottom = "auto";
        }
      } else {
        // ── 球拖拽：球移动，面板跟随（球打开时 pointer-events:none 故此路径仅在面板关闭时生效） ──
        const newX = Math.max(0, Math.min(window.innerWidth - 48, dragState.current.startLeft + dx));
        const newY = Math.max(0, Math.min(window.innerHeight - 48, dragState.current.startTop + dy));

        posRef.current = { x: newX, y: newY };
        if (floatRef.current) {
          floatRef.current.style.left = `${newX}px`;
          floatRef.current.style.top = `${newY}px`;
        }
      }
    };

    const handleDragEnd = () => {
      if (!dragState.current.dragging) return;
      const wasMoved = dragState.current.moved;
      const wasPanelDrag = dragState.current.isPanelDrag;
      dragState.current.dragging = false;

      if (floatRef.current) floatRef.current.style.transition = "";
      if (panelRef.current) panelRef.current.style.transition = "";

      if (!wasMoved) {
        // 点击（非拖动）：展开/收起面板
        if (openRef.current) {
          // 面板当前打开 → 收起：从面板反算球，清除面板位置记忆
          syncBallFromPanel();
          setPanelPos(null);
        } else {
          // 面板当前关闭 → 展开：根据球在视口的位置，决定面板展开方向
          const vw = window.innerWidth;
          const vh = window.innerHeight;
          const ballCX = posRef.current.x + 24;
          const ballCY = posRef.current.y + 24;
          openDirRef.current = {
            h: ballCX > vw / 2 ? "left" : "right",
            v: ballCY > vh / 2 ? "top" : "bottom",
          };
        }
        setOpen((prev) => !prev);
        setDragging(false);
        return;
      }

      // 面板拖拽结束：存面板精确位置，从面板反算球位置并吸附
      if (wasPanelDrag) {
        if (panelRef.current) {
          const rect = panelRef.current.getBoundingClientRect();
          const vw = window.innerWidth;
          setPanelPos({ right: vw - rect.right, top: rect.top });
        }
        syncBallFromPanel();
        setDragging(false);
        return;
      }

      // 球拖拽结束：清除 panelPos（面板下次打开从球位置计算），直接吸附球
      setPanelPos(null);
      const result = snap(posRef.current.x, posRef.current.y);
      if (result) {
        snappedRef.current = result.side;
        posRef.current = { x: result.x, y: result.y };
        setSnapped(result.side);
      } else {
        snappedRef.current = "none";
        setSnapped("none");
      }
      setDragging(false);
      setRenderPos({ ...posRef.current });
      try { localStorage.setItem(POS_KEY, JSON.stringify(posRef.current)); } catch {}
    };

    window.addEventListener("mousemove", handleDragMove);
    window.addEventListener("mouseup", handleDragEnd);
    window.addEventListener("touchmove", handleDragMove, { passive: false });
    window.addEventListener("touchend", handleDragEnd);

    return () => {
      window.removeEventListener("mousemove", handleDragMove);
      window.removeEventListener("mouseup", handleDragEnd);
      window.removeEventListener("touchmove", handleDragMove);
      window.removeEventListener("touchend", handleDragEnd);
    };
  }, []);

  // ── 工具调用处理 ──
  const handleToolCall = useCallback(
    (tc: ToolCallEvent) => {
      const { confirmMode, autoJumpThreshold } = store;

      if (confirmMode === "never") {
        store.appendAssistantChunk("\n\n✅ 已自动跳转。");
        if (tc.route) {
          const target = tc.route.target;
          const params = tc.route.params
            ? "?" + new URLSearchParams(tc.route.params).toString()
            : "";
          router.push(target + params);
        }
        store.setToolCall(null);
        return;
      }

      if (confirmMode === "always") {
        store.setToolCall(tc);
        return;
      }

      if (tc.confidence >= autoJumpThreshold && !tc.require_confirmation) {
        store.appendAssistantChunk("\n\n✅ 已自动跳转。");
        if (tc.route) {
          const target = tc.route.target;
          const params = tc.route.params
            ? "?" + new URLSearchParams(tc.route.params).toString()
            : "";
          router.push(target + params);
        }
        store.setToolCall(null);
        return;
      }

      store.setToolCall(tc);
    },
    [router],
  );

  // ── 发送消息 ──
  const handleSubmit = useCallback(async () => {
    const msg = input.trim();
    if (!msg || streaming) return;

    const convId = store.activeConvId;
    if (!convId) {
      store.appendAssistantChunk("⚠️ 暂未创建对话，请重新打开面板。");
      return;
    }

    setInput("");
    store.addUserMessage(msg);
    store.setStreaming(true);

    // 在发送 SSE 之前，先将用户消息持久化到树
    saveMessageToTreeConv(convId, "user", msg);

    let assistantText = "";

    await send(msg, {
      endpoint: "/api/secretary/agent/chat",
      bodyExtra: {
        current_page: pathname,
        conv_id: convId,
      },
      onToken: (delta) => {
        assistantText += delta;
        store.appendAssistantChunk(delta);
      },
      onToolCall: (tc) => handleToolCall(tc),
      onConversationId: (id) => store.setConversationId(id),
      onError: (err) => store.appendAssistantChunk(err),
      onDone: async () => {
        store.setStreaming(false);

        // 流完成后，将助手回复持久化到树
        if (assistantText) {
          await saveMessageToTreeConv(convId, "assistant", assistantText);
        }

        // 刷新对话列表（消息计数更新）
        const dirId = store.secretaryDirId;
        if (dirId) {
          const convs = await loadSecretaryConvs(dirId);
          store.setSecretaryConvs(convs);
        }
      },
    });
  }, [input, streaming, pathname, send, handleToolCall, store]);

  const handleAcceptToolCall = () => {
    const tc = store.currentToolCall;
    if (tc?.route) {
      const target = tc.route.target;
      const params = tc.route.params
        ? "?" + new URLSearchParams(tc.route.params).toString()
        : "";
      router.push(target + params);
    }
    store.acceptToolCall();
  };

  const handleRejectToolCall = () => {
    store.rejectToolCall();
  };

  const handleFloatClick = () => {
    if (dragState.current.moved) {
      dragState.current.moved = false;
      return;
    }
    // onClick 已不处理面板开关，由 handleDragEnd 负责
  };

  // 关闭面板：收起前从面板反算球位置，清除面板位置记忆
  const handleClosePanel = useCallback(() => {
    syncBallFromPanel();
    setPanelPos(null);
    setOpen(false);
  }, [syncBallFromPanel]);

  // 吸附时 hover 恢复完整显示
  const [hovering, setHovering] = useState(false);
  const isSnapped = snapped !== "none";
  const showFull = !isSnapped || hovering || open;

  // 拖动时禁用 transition，避免位置延迟
  const pos = dragging ? posRef.current : renderPos;

  /*
    视觉位置：吸附态时外层容器偏移后的实际位置，
    用于面板对齐（吸附态下 pos 是内部坐标，视觉球有偏移）
  */
  const BALL_SIZE = 48;
  const SNAP_SCALE = 0.6;
  const SNAP_OFFSET = BALL_SIZE * (1 - SNAP_SCALE) / 2; // 9.6
  const visualPos = {
    x: isSnapped
      ? (snapped === "left" ? pos.x + SNAP_OFFSET : snapped === "right" ? pos.x - SNAP_OFFSET : pos.x)
      : pos.x,
    y: isSnapped
      ? (snapped === "top" ? pos.y + SNAP_OFFSET : snapped === "bottom" ? pos.y - SNAP_OFFSET : pos.y)
      : pos.y,
  };

  // 当前对话名
  const currentConvName = secretaryConvs.find((c) => c.id === activeConvId)?.name || "秘书对话";

  return (
    <>
      {/* ── 悬浮球（外层容器：固定位置 + 全尺寸 hit area） ── */}
      <div
        ref={floatRef}
        onMouseDown={handleMouseDown}
        onClick={handleFloatClick}
        onMouseEnter={() => setHovering(true)}
        onMouseLeave={() => setHovering(false)}
        className={`
          fixed z-50
          w-12 h-12
          flex items-center justify-center
          select-none
          ${dragging ? "" : "transition-all duration-300"}
          ${visible ? "opacity-100" : "opacity-0"}
          ${open ? "pointer-events-none" : "cursor-grab active:cursor-grabbing"}
        `}
        style={{
          opacity: visible ? 1 : 0,
          transition: visible
            ? (dragging
              ? "opacity 0.5s ease-in-out"
              : "opacity 0.5s ease-in-out, left 0.3s, top 0.3s")
            : "none",
          /*
            吸附时外层始终停在固定位置（compact/hover 不跳变），
            使得 hit area 48×48 不收缩，hover 不抽搐。
            SNAP_OFFSET = 9.6，让内层 scaleX/Y(0.6) + 边缘 origin
            后 visible bump 仍为 14.4px。
          */
          left: isSnapped
            ? (snapped === "left" ? pos.x + SNAP_OFFSET : snapped === "right" ? pos.x - SNAP_OFFSET : pos.x)
            : pos.x,
          top: isSnapped
            ? `${snapped === "top" ? pos.y + SNAP_OFFSET : snapped === "bottom" ? pos.y - SNAP_OFFSET : pos.y}px`
            : `${pos.y}px`,
        }}
        aria-label="AI 秘书"
      >
        {/*
          ── 内层视觉球 ──
          scaleX / borderRadius 等形变只在此层生效，不影响外层 hit area。
          所以 hover 检测始终在展开后的全尺寸区域，不会抽搐。
        */}
        <div
          className={`
            w-full h-full rounded-full
            flex items-center justify-center
            shadow-lg overflow-hidden
            ${open
              ? "bg-[var(--color-text-muted)] text-white"
              : "bg-[var(--color-accent)] text-white"
            }
          `}
          style={{
            transform: open
              ? "scale(0)"
              : (isSnapped && !showFull
                ? (snapped === "left" || snapped === "right" ? "scaleX(0.6)" : "scaleY(0.6)")
                : undefined),
            borderRadius: isSnapped && !showFull
              ? (snapped === "left" ? "50% 4px 4px 50%"
                : snapped === "right" ? "4px 50% 50% 4px"
                // 顶吸附：可见 bump 在底部（下半部分露出），底边圆角
                : snapped === "top" ? "4px 4px 50% 50%"
                // 底吸附：可见 bump 在顶部（上半部分露出），顶边圆角
                : "50% 50% 4px 4px")
              : "50%",
            transformOrigin: isSnapped
              ? (snapped === "left" ? "left center"
                : snapped === "right" ? "right center"
                : snapped === "top" ? "center top"
                : "center bottom")
              : "center",
            transition: dragging ? "none" : "all 0.3s",
          }}
        >
          <MessageCircle size={20} />
        </div>
      </div>

      {/* ── 弹出面板 ── */}
      {open && (
        <div
          ref={panelRef}
          className="fixed z-50
            w-[calc(100vw-2rem)] max-w-[380px] max-h-[480px]
            bg-[var(--color-surface)] border border-[var(--color-border)]
            rounded-xl shadow-2xl flex flex-col overflow-hidden"
          style={(() => {
            // 用户拖拽后面板有精确位置 → 直接使用，不从球反算
            if (panelPos) {
              return { right: panelPos.right, top: panelPos.top };
            }
            // 根据展开方向从球位置计算面板位置
            const dir = openDirRef.current;
            const vw = window.innerWidth;
            const vh = window.innerHeight;
            const pw = Math.min(vw - 32, 380);
            const maxPanelRight = vw - pw - 8; // 面板最右：左边缘 8px

            // 水平：面板在球的对面侧（球在左 → 面板在右，球在右 → 面板在左）
            let panelRight: number;
            if (dir.h === "right") {
              // 面板在球右侧：面板左边缘 = ballX + 56
              panelRight = Math.max(8, Math.min(vw - pw - visualPos.x - 56, maxPanelRight));
            } else {
              // 面板在球左侧：面板右边缘 = ballX - 8
              panelRight = Math.max(8, Math.min(vw - visualPos.x + 8, maxPanelRight));
            }

            // 垂直：面板在球的对面侧（球在上 → 面板在下，球在下 → 面板在上）
            if (dir.v === "bottom") {
              // 面板在球下方：面板顶 = ballY + 56
              const panelTop = Math.max(8, Math.min(visualPos.y + 56, vh - 488));
              return { right: panelRight, top: panelTop };
            } else {
              // 面板在球上方：用 bottom 锚点，面板底边 = ballY - 8
              // CSS bottom = 视口高度 - 面板底边的视口 Y
              const panelBottom = Math.max(8, Math.min(vh - visualPos.y + 8, vh - 8));
              return { right: panelRight, bottom: panelBottom };
            }
          })()}
        >
          {/* ── 头部 — 可拖拽 + 对话切换 ── */}
          <div
            onMouseDown={handlePanelMouseDown}
            className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)] cursor-grab active:cursor-grabbing select-none"
          >
            <div className="flex items-center gap-2 min-w-0">
              {/* 对话选择器 */}
              <div className="relative">
                <button
                  onClick={(e) => { e.stopPropagation(); setShowConvList(!showConvList); }}
                  className="flex items-center gap-1 text-sm font-semibold text-[var(--color-text)] hover:text-[var(--color-accent)] truncate max-w-[180px]"
                >
                  <span className="truncate">{currentConvName}</span>
                  <ChevronDown size={14} className="shrink-0" />
                </button>

                {showConvList && (
                  <div
                    className="absolute top-full left-0 mt-1 w-56 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-xl z-[100] max-h-48 overflow-y-auto"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {loadingSecretary ? (
                      <div className="px-3 py-2 text-xs text-[var(--color-text-muted)]">加载中...</div>
                    ) : secretaryConvs.length === 0 ? (
                      <div className="px-3 py-2 text-xs text-[var(--color-text-muted)]">暂无对话</div>
                    ) : (
                      secretaryConvs.map((conv) => (
                        <button
                          key={conv.id}
                          onClick={() => handleSwitchConv(conv.id)}
                          className={`w-full text-left px-3 py-2 text-sm hover:bg-[var(--color-hover)] truncate ${conv.id === activeConvId ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "text-[var(--color-text)]"}`}
                        >
                          {conv.name}
                          {conv.messageCount > 0 && (
                            <span className="ml-2 text-xs text-[var(--color-text-muted)]">{conv.messageCount} 条</span>
                          )}
                        </button>
                      ))
                    )}
                    <div className="border-t border-[var(--color-border)]">
                      <button
                        onClick={handleNewConv}
                        className="w-full text-left px-3 py-2 text-sm text-[var(--color-accent)] hover:bg-[var(--color-hover)]"
                      >
                        + 新建对话
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
            <button
              onClick={handleClosePanel}
              className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              aria-label="关闭"
            >
              <X size={16} />
            </button>
          </div>

          {/* ── 消息区域 ── */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {loadingMessages ? (
              <div className="flex items-center justify-center py-8 text-sm text-[var(--color-text-muted)]">
                加载历史消息...
              </div>
            ) : (
              <ChatMessages
                messages={messages}
                showSpeak
                emptyText="输入学习需求，我来帮你导航"
              />
            )}

            {/* Tool Call 确认卡片 */}
            {currentToolCall && !loadingMessages && (
              <ToolCallConfirmation
                toolCall={currentToolCall}
                onAccept={handleAcceptToolCall}
                onReject={handleRejectToolCall}
              />
            )}
          </div>

          {/* ── 输入区域 ── */}
          <div className="px-4 py-3 border-t border-[var(--color-border)]">
            <ChatInputBar
              input={input}
              onInputChange={setInput}
              onSubmit={handleSubmit}
              loading={streaming || loadingMessages}
              showVoice
              placeholder="输入学习需求…"
            />
          </div>
        </div>
      )}
    </>
  );
}
