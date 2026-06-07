import { describe, it, expect, beforeEach } from "vitest";
import type { SecretaryNotification } from "../types";

// ══════════════════════════════════════════════════════════════
//  NotificationStore — 行为测试
//
//  测试通过 public interface 验证行为，不关注实现细节。
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

describe("NotificationStore", () => {
  let store: ReturnType<typeof import("../notification-store").createNotificationStore>;

  beforeEach(async () => {
    const mod = await import("../notification-store");
    store = mod.createNotificationStore();
    store.clearAll(); // 重置单例状态，避免测试间泄露
  });

  describe("添加通知", () => {
    it("addNotification 添加通知后 getNotifications 应返回该通知", () => {
      const n = createSampleNotification();
      store.addNotification(n);
      expect(store.getNotifications()).toHaveLength(1);
      expect(store.getNotifications()[0].id).toBe("notif_001");
    });
  });

  describe("按页面类型筛选", () => {
    it("getNotificationsByPage 只返回目标页面包含指定 pageType 的通知", () => {
      const learnNotif = createSampleNotification({
        id: "notif_learn",
        target: { pages: ["learn"] },
      });
      const dashNotif = createSampleNotification({
        id: "notif_dash",
        target: { pages: ["dashboard"] },
      });
      const multiNotif = createSampleNotification({
        id: "notif_multi",
        target: { pages: ["learn", "dashboard"] },
      });

      store.addNotification(learnNotif);
      store.addNotification(dashNotif);
      store.addNotification(multiNotif);

      const learnNotifications = store.getNotificationsByPage("learn");
      expect(learnNotifications).toHaveLength(2);
      expect(learnNotifications.map((n) => n.id).sort()).toEqual([
        "notif_learn",
        "notif_multi",
      ]);
    });

    it("getNotificationsByPage 不存在的 pageType 应返回空数组", () => {
      const n = createSampleNotification({
        target: { pages: ["practice"] },
      });
      store.addNotification(n);
      expect(store.getNotificationsByPage("learn")).toHaveLength(0);
    });
  });

  describe("标记已读", () => {
    it("markRead 将指定通知的 read 设为 true", () => {
      const n = createSampleNotification();
      store.addNotification(n);
      store.markRead("notif_001");
      const updated = store.getNotifications()[0];
      expect(updated.read).toBe(true);
    });
  });

  describe("未读计数", () => {
    it("unreadCount 返回 read=false 的通知数量", () => {
      store.addNotification(createSampleNotification({ id: "n1", read: false }));
      store.addNotification(createSampleNotification({ id: "n2", read: false }));
      store.addNotification(createSampleNotification({ id: "n3", read: true }));

      expect(store.unreadCount()).toBe(2);
    });

    it("标记已读后 unreadCount 应减少", () => {
      store.addNotification(createSampleNotification({ id: "n1", read: false }));
      store.addNotification(createSampleNotification({ id: "n2", read: false }));
      expect(store.unreadCount()).toBe(2);

      store.markRead("n1");
      expect(store.unreadCount()).toBe(1);
    });
  });

  describe("接受/忽略通知", () => {
    it("acceptNotification 将通知 status 设为 accepted", () => {
      const n = createSampleNotification();
      store.addNotification(n);
      store.acceptNotification("notif_001");
      expect(store.getNotifications()[0].status).toBe("accepted");
    });

    it("dismissNotification 将通知 status 设为 dismissed", () => {
      const n = createSampleNotification();
      store.addNotification(n);
      store.dismissNotification("notif_001");
      expect(store.getNotifications()[0].status).toBe("dismissed");
    });
  });

  describe("内联通知", () => {
    it("getInlineNotifications 返回匹配 conversationId 的通知", () => {
      const inlineNotif = createSampleNotification({
        id: "n1",
        target: { pages: ["learn"], inlineConversationId: "conv_123" },
      });
      const otherNotif = createSampleNotification({
        id: "n2",
        target: { pages: ["learn"], inlineConversationId: "conv_456" },
      });
      const noInlineNotif = createSampleNotification({
        id: "n3",
        target: { pages: ["learn"] },
      });

      store.addNotification(inlineNotif);
      store.addNotification(otherNotif);
      store.addNotification(noInlineNotif);

      const inline = store.getInlineNotifications("conv_123");
      expect(inline).toHaveLength(1);
      expect(inline[0].id).toBe("n1");
    });
  });
});