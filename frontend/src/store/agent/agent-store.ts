import { create } from "zustand";

export interface AgentMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ToolCallEvent {
  name: string;
  arguments: Record<string, unknown>;
  confidence: number;
  require_confirmation: boolean;
  route?: { target: string; params?: Record<string, string> };
  confirmation_text: string;
}

/** 秘书对话的快照信息 */
export interface SecretaryConvInfo {
  id: string;
  name: string;
  messageCount: number;
  createdAt: number;
}

export interface AgentState {
  // ── 秘书对话状态 ──
  conversationId: string | null;
  messages: AgentMessage[];
  isStreaming: boolean;
  currentToolCall: ToolCallEvent | null;
  confirmMode: "smart" | "always" | "never";
  autoJumpThreshold: number;

  // ── 树持久化 ──
  secretaryDirId: string | null;
  secretaryConvs: SecretaryConvInfo[];
  activeConvId: string | null;
  loadingSecretary: boolean;
  loadingMessages: boolean;
}

export interface AgentActions {
  setConversationId: (id: string) => void;
  addUserMessage: (content: string) => void;
  appendAssistantChunk: (delta: string) => void;
  setStreaming: (v: boolean) => void;
  setToolCall: (tc: ToolCallEvent | null) => void;
  acceptToolCall: () => void;
  rejectToolCall: () => void;
  setConfirmMode: (mode: "smart" | "always" | "never") => void;
  setAutoJumpThreshold: (t: number) => void;

  // ── 树持久化 ──
  setSecretaryDirId: (id: string | null) => void;
  setSecretaryConvs: (convs: SecretaryConvInfo[]) => void;
  setActiveConvId: (id: string | null) => void;
  setLoadingSecretary: (v: boolean) => void;
  setLoadingMessages: (v: boolean) => void;
  /** 从 tree API 加载的消息替换本地 messages */
  setMessagesFromTree: (msgs: AgentMessage[]) => void;
  switchConv: (convId: string) => void;
  reset: () => void;
}

const defaultState: AgentState = {
  conversationId: null,
  messages: [],
  isStreaming: false,
  currentToolCall: null,
  confirmMode: "smart",
  autoJumpThreshold: 0.85,

  secretaryDirId: null,
  secretaryConvs: [],
  activeConvId: null,
  loadingSecretary: false,
  loadingMessages: false,
};

export const useAgentStore = create<AgentState & AgentActions>()((set) => ({
  ...defaultState,

  setConversationId: (id) => set({ conversationId: id }),
  addUserMessage: (content) =>
    set((s) => ({ messages: [...s.messages, { role: "user", content }] })),
  appendAssistantChunk: (delta) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, content: last.content + delta };
      } else {
        msgs.push({ role: "assistant", content: delta });
      }
      return { messages: msgs };
    }),
  setStreaming: (v) => set({ isStreaming: v }),
  setToolCall: (tc) => set({ currentToolCall: tc }),
  acceptToolCall: () => set({ currentToolCall: null }),
  rejectToolCall: () => set({ currentToolCall: null }),
  setConfirmMode: (mode) => set({ confirmMode: mode }),
  setAutoJumpThreshold: (t) => set({ autoJumpThreshold: t }),
  reset: () =>
    set({
      conversationId: null,
      messages: [],
      isStreaming: false,
      currentToolCall: null,
    }),

  setSecretaryDirId: (id) => set({ secretaryDirId: id }),
  setSecretaryConvs: (convs) => set({ secretaryConvs: convs }),
  setActiveConvId: (id) => set({ activeConvId: id }),
  setLoadingSecretary: (v) => set({ loadingSecretary: v }),
  setLoadingMessages: (v) => set({ loadingMessages: v }),
  setMessagesFromTree: (msgs) => set({ messages: msgs }),
  switchConv: (convId: string) =>
    set({
      activeConvId: convId,
      conversationId: convId,
      messages: [],
      currentToolCall: null,
    }),
}));

/** 向后兼容：回调中获取最新状态/执行动作 */
export function getAgentStore(): AgentState & AgentActions {
  return useAgentStore.getState();
}

/** 测试用：创建独立 store 实例 */
export function createAgentStoreForTest(): AgentState & AgentActions {
  return create<AgentState & AgentActions>()((set) => ({
    ...defaultState,
    setConversationId: (id) => set({ conversationId: id }),
    addUserMessage: (content) =>
      set((s) => ({ messages: [...s.messages, { role: "user", content }] })),
    appendAssistantChunk: (delta) =>
      set((s) => {
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (last && last.role === "assistant") {
          msgs[msgs.length - 1] = { ...last, content: last.content + delta };
        } else {
          msgs.push({ role: "assistant", content: delta });
        }
        return { messages: msgs };
      }),
    setStreaming: (v) => set({ isStreaming: v }),
    setToolCall: (tc) => set({ currentToolCall: tc }),
    acceptToolCall: () => set({ currentToolCall: null }),
    rejectToolCall: () => set({ currentToolCall: null }),
    setConfirmMode: (mode) => set({ confirmMode: mode }),
    setAutoJumpThreshold: (t) => set({ autoJumpThreshold: t }),
    setSecretaryDirId: (id) => set({ secretaryDirId: id }),
    setSecretaryConvs: (convs) => set({ secretaryConvs: convs }),
    setActiveConvId: (id) => set({ activeConvId: id }),
    setLoadingSecretary: (v) => set({ loadingSecretary: v }),
    setLoadingMessages: (v) => set({ loadingMessages: v }),
    setMessagesFromTree: (msgs) => set({ messages: msgs }),
    switchConv: (convId: string) =>
      set({ activeConvId: convId, conversationId: convId, messages: [], currentToolCall: null }),
    reset: () => set({
      conversationId: null, messages: [], isStreaming: false, currentToolCall: null,
    }),
  })).getState();
}
