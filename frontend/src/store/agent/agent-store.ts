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

export interface AgentState {
  conversationId: string | null;
  messages: AgentMessage[];
  isStreaming: boolean;
  currentToolCall: ToolCallEvent | null;
  confirmMode: "smart" | "always" | "never";
  autoJumpThreshold: number;
}

export function createAgentStore() {
  const state: AgentState = {
    conversationId: null,
    messages: [],
    isStreaming: false,
    currentToolCall: null,
    confirmMode: "smart",
    autoJumpThreshold: 0.85,
  };

  return {
    setConversationId(id: string) { state.conversationId = id; },
    addUserMessage(content: string) {
      state.messages.push({ role: "user", content });
    },
    appendAssistantChunk(delta: string) {
      const last = state.messages[state.messages.length - 1];
      if (last && last.role === "assistant") {
        last.content += delta;
      } else {
        state.messages.push({ role: "assistant", content: delta });
      }
    },
    setStreaming(v: boolean) { state.isStreaming = v; },
    setToolCall(tc: ToolCallEvent | null) { state.currentToolCall = tc; },
    acceptToolCall() { state.currentToolCall = null; },
    rejectToolCall() { state.currentToolCall = null; },
    setConfirmMode(mode: "smart" | "always" | "never") { state.confirmMode = mode; },
    setAutoJumpThreshold(t: number) { state.autoJumpThreshold = t; },
    reset() {
      state.conversationId = null;
      state.messages = [];
      state.isStreaming = false;
      state.currentToolCall = null;
    },

    get conversationId() { return state.conversationId; },
    get messages() { return state.messages; },
    get isStreaming() { return state.isStreaming; },
    get currentToolCall() { return state.currentToolCall; },
    get confirmMode() { return state.confirmMode; },
    get autoJumpThreshold() { return state.autoJumpThreshold; },
  };
}

export type AgentStore = ReturnType<typeof createAgentStore>;

// 全局单例
let _instance: AgentStore | null = null;

export function getAgentStore(): AgentStore {
  if (!_instance) {
    _instance = createAgentStore();
  }
  return _instance;
}