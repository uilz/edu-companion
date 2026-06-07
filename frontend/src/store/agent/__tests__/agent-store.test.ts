import { describe, it, expect, beforeEach } from "vitest";
import { createAgentStore, type ToolCallEvent } from "../agent-store";

const sampleToolCall: ToolCallEvent = {
  name: "start_practice",
  arguments: { subject: "微积分", count: 10 },
  confidence: 0.92,
  require_confirmation: true,
  route: { target: "/practice", params: { bank_id: "abc" } },
  confirmation_text: "即将跳转到练习页，开始微积分练习",
};

describe("AgentStore", () => {
  let store: ReturnType<typeof createAgentStore>;

  beforeEach(() => {
    store = createAgentStore();
  });

  describe("对话管理", () => {
    it("setConversationId 设置对话 ID", () => {
      store.setConversationId("conv_abc");
      expect(store.conversationId).toBe("conv_abc");
    });

    it("addUserMessage 添加用户消息", () => {
      store.addUserMessage("帮我复习微积分");
      expect(store.messages).toHaveLength(1);
      expect(store.messages[0].role).toBe("user");
      expect(store.messages[0].content).toBe("帮我复习微积分");
    });

    it("appendAssistantChunk 追加流式回复", () => {
      store.appendAssistantChunk("你好");
      store.appendAssistantChunk("，世界");
      expect(store.messages).toHaveLength(1);
      expect(store.messages[0].role).toBe("assistant");
      expect(store.messages[0].content).toBe("你好，世界");
    });

    it("appendAssistantChunk 在用户消息后创建新 assistant 消息", () => {
      store.addUserMessage("复习微积分");
      store.appendAssistantChunk("好的");
      expect(store.messages).toHaveLength(2);
      expect(store.messages[1].role).toBe("assistant");
    });
  });

  describe("流式状态", () => {
    it("setStreaming 控制流式状态", () => {
      expect(store.isStreaming).toBe(false);
      store.setStreaming(true);
      expect(store.isStreaming).toBe(true);
      store.setStreaming(false);
      expect(store.isStreaming).toBe(false);
    });
  });

  describe("Tool Call", () => {
    it("setToolCall 设置当前 tool call", () => {
      store.setToolCall(sampleToolCall);
      expect(store.currentToolCall?.name).toBe("start_practice");
      expect(store.currentToolCall?.confidence).toBe(0.92);
    });

    it("acceptToolCall 清除 tool call", () => {
      store.setToolCall(sampleToolCall);
      store.acceptToolCall();
      expect(store.currentToolCall).toBeNull();
    });

    it("rejectToolCall 清除 tool call", () => {
      store.setToolCall(sampleToolCall);
      store.rejectToolCall();
      expect(store.currentToolCall).toBeNull();
    });
  });

  describe("确认模式", () => {
    it("默认确认模式为 smart", () => {
      expect(store.confirmMode).toBe("smart");
    });

    it("setConfirmMode 切换确认模式", () => {
      store.setConfirmMode("always");
      expect(store.confirmMode).toBe("always");
      store.setConfirmMode("never");
      expect(store.confirmMode).toBe("never");
    });

    it("setAutoJumpThreshold 设置自动跳转阈值", () => {
      store.setAutoJumpThreshold(0.7);
      expect(store.autoJumpThreshold).toBe(0.7);
    });
  });

  describe("重置", () => {
    it("reset 清空所有状态", () => {
      store.setConversationId("conv_001");
      store.addUserMessage("hi");
      store.appendAssistantChunk("hello");
      store.setToolCall(sampleToolCall);
      store.setStreaming(true);

      store.reset();

      expect(store.conversationId).toBeNull();
      expect(store.messages).toHaveLength(0);
      expect(store.isStreaming).toBe(false);
      expect(store.currentToolCall).toBeNull();
    });
  });
});