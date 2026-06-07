import { describe, it, expect, beforeEach, vi } from "vitest";
import type { SecretaryNotification, SecretaryUpdatePayload } from "../types";
import { useNotificationStore } from "../notification-store";

// ══════════════════════════════════════════════════════════════
//  NotificationService — WS 事件消费测试
// ══════════════════════════════════════════════════════════════

function createSampleNotification(
  overrides: Partial<SecretaryNotification> = {}
): SecretaryNotification {
  return {
    id: "notif_001",
    emoji: "🔔",
    title: "测试通知",
    description: "这是一条测试通知",
    priority: 3,
    target: { pages: ["learn"] },
    source: "secretary",
    read: false,
    status: "pending",
    created_at: Date.now(),
    ...overrides,
  };
}

describe("NotificationService — WS 消费", () => {
  beforeEach(() => {
    useNotificationStore.getState().clearAll();
    vi.restoreAllMocks();
  });

  describe("handleSecretaryInline", () => {
    it("收到 secretary_inline 事件后应将通知加入 store", async () => {
      const { handleSecretaryInline } = await import("../notification-service");

      const proposal = createSampleNotification({
        id: "inline_001",
        title: "内联通知",
        source: "context_switch",
        target: { pages: ["learn"], inlineConversationId: "conv_123" },
      });

      handleSecretaryInline(proposal);

      const notifications = useNotificationStore.getState().getNotifications();
      expect(notifications).toHaveLength(1);
      expect(notifications[0].id).toBe("inline_001");
      expect(notifications[0].source).toBe("context_switch");
    });

    it("多次 secretary_inline 应累积通知", async () => {
      const { handleSecretaryInline } = await import("../notification-service");

      handleSecretaryInline(createSampleNotification({ id: "a" }));
      handleSecretaryInline(createSampleNotification({ id: "b" }));
      handleSecretaryInline(createSampleNotification({ id: "c" }));

      expect(useNotificationStore.getState().getNotifications()).toHaveLength(3);
    });
  });

  describe("handleSecretaryUpdate", () => {
    it("收到 secretary_update 后应从 API 拉取提案并入 store", async () => {
      const mockProposals = [
        createSampleNotification({ id: "api_001", title: "提案 1" }),
        createSampleNotification({ id: "api_002", title: "提案 2" }),
      ];

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockProposals),
      });

      const { handleSecretaryUpdate } = await import("../notification-service");

      const payload: SecretaryUpdatePayload = {
        reason: ["新提案"],
        proposal_count: 2,
      };

      await handleSecretaryUpdate(payload);

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/secretary/proposals/pending"
      );

      const notifications = useNotificationStore.getState().getNotifications();
      expect(notifications).toHaveLength(2);
      expect(notifications[0].id).toBe("api_001");
      expect(notifications[1].id).toBe("api_002");
    });

    it("API 请求失败时应静默处理，不抛异常", async () => {
      globalThis.fetch = vi.fn().mockRejectedValue(new Error("Network error"));

      const { handleSecretaryUpdate } = await import("../notification-service");

      const payload: SecretaryUpdatePayload = {
        reason: [],
        proposal_count: 0,
      };

      // 不应抛出异常
      await expect(handleSecretaryUpdate(payload)).resolves.toBeUndefined();

      expect(useNotificationStore.getState().getNotifications()).toHaveLength(0);
    });

    it("API 返回非 200 时应静默处理", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
      });

      const { handleSecretaryUpdate } = await import("../notification-service");

      await handleSecretaryUpdate({ reason: [], proposal_count: 0 });

      expect(useNotificationStore.getState().getNotifications()).toHaveLength(0);
    });
  });

  describe("markNotificationRead / accept / dismiss", () => {
    it("markNotificationRead 应将本地通知标记已读并调用后端 API", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({ ok: true });

      const { markNotificationRead } = await import("../notification-service");
      const store = useNotificationStore.getState();

      store.addNotification(createSampleNotification({ id: "n1" }));
      expect(store.unreadCount()).toBe(1);

      await markNotificationRead("n1");

      expect(store.getNotifications()[0].read).toBe(true);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/secretary/proposals/n1/dismiss",
        expect.objectContaining({ method: "POST" })
      );
    });

    it("acceptNotification 应将通知标记为 accepted", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({ ok: true });

      const { acceptNotification } = await import("../notification-service");
      const store = useNotificationStore.getState();

      store.addNotification(createSampleNotification({ id: "n2" }));
      await acceptNotification("n2");

      expect(store.getNotifications()[0].status).toBe("accepted");
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/secretary/proposals/n2/accept",
        expect.objectContaining({ method: "POST" })
      );
    });

    it("dismissNotification 应将通知标记为 dismissed", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({ ok: true });

      const { dismissNotification } = await import("../notification-service");
      const store = useNotificationStore.getState();

      store.addNotification(createSampleNotification({ id: "n3" }));
      await dismissNotification("n3");

      expect(store.getNotifications()[0].status).toBe("dismissed");
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/secretary/proposals/n3/dismiss",
        expect.objectContaining({ method: "POST" })
      );
    });
  });
});