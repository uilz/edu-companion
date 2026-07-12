// navConfig 角色 / 订阅过滤 — 单元测试（任务 #34 / 任务 #45 / 任务 #75）
//
// 任务 #45：admin 已从主前端移除（admin 走独立 3001 项目），
// 本测试只覆盖 student / guest 两档角色。
//
// 任务 #75：撤销 liveroom 的 Pro 档位过滤
//   • liveroom 不再有 requiredTiers / badgePro
//   • 所有已登录用户都看到 liveroom
//   • 未登录（userRole=guest）受 requiresAuth 拦截，函数层面就看不到
import { describe, it, expect } from "vitest";
import {
  primaryNavItems,
  getNavItemsFor,
  getQuickActions,
  matchesRole,
  matchesTier,
  isItemVisible,
  type NavContext,
} from "@/lib/navConfig";

const studentFree: NavContext = { userRole: "student", subscriptionTier: "free" };
const studentPro: NavContext = { userRole: "student", subscriptionTier: "pro" };
const guestFree: NavContext = { userRole: "guest", subscriptionTier: "free" };

describe("navConfig — 角色/订阅过滤（任务 #34 / #45 / #75）", () => {
  describe("matchesRole", () => {
    it("空 requiredRoles = 不限制（任何角色都通过）", () => {
      const item = primaryNavItems.find((i) => i.path === "/conversation")!;
      expect(matchesRole(item, "guest")).toBe(true);
      expect(matchesRole(item, "student")).toBe(true);
    });
  });

  describe("matchesTier", () => {
    it("空 requiredTiers = 不限制", () => {
      const item = primaryNavItems.find((i) => i.path === "/conversation")!;
      expect(matchesTier(item, "free")).toBe(true);
      expect(matchesTier(item, "pro")).toBe(true);
    });

    it("任务 #75：liveroom 不再有 requiredTiers 限制（任何档位都通过）", () => {
      const item = primaryNavItems.find((i) => i.path === "/liveroom")!;
      // 撤销 Task #34 的 Pro 档位过滤 + 角标
      expect(item.requiredTiers).toBeUndefined();
      expect(item.badgePro).toBeUndefined();
      expect(matchesTier(item, "free")).toBe(true);
      expect(matchesTier(item, "pro")).toBe(true);
      expect(matchesTier(item, "enterprise")).toBe(true);
    });
  });

  describe("isItemVisible — slot + role + tier + requiresAuth 完整判断", () => {
    it("任务 #75：liveroom 对所有档位的 student 都可见", () => {
      const liveroom = primaryNavItems.find((i) => i.path === "/liveroom")!;
      expect(isItemVisible(liveroom, "sidebar", studentFree)).toBe(true);
      expect(isItemVisible(liveroom, "sidebar", studentPro)).toBe(true);
    });

    it("任务 #75：liveroom 对未登录（userRole=guest）用户隐藏（requiresAuth 拦截）", () => {
      const liveroom = primaryNavItems.find((i) => i.path === "/liveroom")!;
      expect(liveroom.requiresAuth).toBe(true);
      // isItemVisible 在 guest 上下文下不返回 liveroom
      expect(isItemVisible(liveroom, "sidebar", guestFree)).toBe(false);
    });
  });

  describe("getNavItemsFor — sidebar 槽位", () => {
    it("任务 #75：student+free 看到 liveroom（撤销 Pro 档位限制）", () => {
      const items = getNavItemsFor("sidebar", studentFree).map((i) => i.path);
      expect(items).toContain("/liveroom");
      // 撤销 Pro 限制后 sidebar 12 项对 student+free 全部可见
      expect(items.length).toBe(12);
      expect(items).toContain("/conversation");
      expect(items).toContain("/practice");
      expect(items).toContain("/project");
      expect(items).toContain("/knowledge-tree");
      expect(items).toContain("/");
      expect(items).toContain("/resources");
      expect(items).toContain("/flashcard");
      expect(items).toContain("/reading");
    });

    it("student+pro 看到 liveroom", () => {
      const items = getNavItemsFor("sidebar", studentPro).map((i) => i.path);
      expect(items).toContain("/liveroom");
    });

    it("student+pro 看到所有 sidebar 项（除 analytics/settings 仅 quickAction 露出）", () => {
      const items = getNavItemsFor("sidebar", studentPro);
      // sidebar 槽位共 12 项（analytics 和 settings 仅 quickAction 露出）
      expect(items.length).toBe(12);
      expect(items.map((i) => i.path)).toContain("/liveroom");
    });

    it("任务 #75：guest 看不到任何 requiresAuth 项（全部 nav items 都被拦截）", () => {
      const items = getNavItemsFor("sidebar", guestFree);
      const paths = items.map((i) => i.path);
      // 所有 primaryNavItems 都 requiresAuth=true，所以 guest 在函数层面看不到任何 sidebar 项
      expect(paths).not.toContain("/liveroom");
      expect(paths).not.toContain("/conversation");
      expect(paths).not.toContain("/practice");
      expect(items.length).toBe(0);
    });
  });

  describe("getQuickActions — 四宫格快捷入口", () => {
    it("student+free 看到 liveroom (但 liveroom 不在 quickAction 里，所以不参与此测试)", () => {
      const items = getQuickActions(studentFree).map((i) => i.path);
      // 验证 8 大模块都在 quickAction 露出
      expect(items).toContain("/conversation");
      expect(items).toContain("/practice");
      expect(items).toContain("/knowledge-tree");
      expect(items).toContain("/analytics");
      expect(items).toContain("/settings");
    });

    it("任务 #75：guest 在 quickAction 中也看不到任何 requiresAuth 项", () => {
      const items = getQuickActions(guestFree);
      // 所有 quickAction 项都 requiresAuth=true，guest 全部被拦截
      expect(items.length).toBe(0);
    });
  });

  describe("向后兼容：context 不传时不过滤", () => {
    it("不传 context = 不过滤 role/tier/requiresAuth（返回所有 sidebar 槽位项 = 12）", () => {
      const items = getNavItemsFor("sidebar");
      // analytics 和 settings 是 quickAction only，不进 sidebar
      expect(items.length).toBe(12);
    });
  });

  describe("priority 排序保持", () => {
    it("sidebar 返回结果按 priority 升序", () => {
      const items = getNavItemsFor("sidebar", studentPro);
      for (let i = 1; i < items.length; i++) {
        expect(items[i].priority).toBeGreaterThanOrEqual(items[i - 1].priority);
      }
    });
  });

  describe("任务 #45：admin 入口已从主前端移除", () => {
    it("primaryNavItems 不再包含 /admin 路径", () => {
      const adminItem = primaryNavItems.find((i) => i.path === "/admin");
      expect(adminItem).toBeUndefined();
    });

    it("primaryNavItems 不再含 badgeAdmin 字段（类型层面）", () => {
      // 静态断言：没有任何 item 出现 badgeAdmin 键
      for (const item of primaryNavItems) {
        expect((item as { badgeAdmin?: unknown }).badgeAdmin).toBeUndefined();
      }
    });
  });
});
