// navConfig V1 导航收敛 — 单元测试
//
// V1 仅保留 3 项主导航：Today / Growth / Profile
// 所有项目 requiresAuth=true，未登录用户全部拦截。

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
const guestFree: NavContext = { userRole: "guest", subscriptionTier: "free" };

describe("navConfig — V1 导航收敛", () => {
  it("primaryNavItems 只有 3 项：Today / Growth / Profile", () => {
    expect(primaryNavItems.length).toBe(3);
    const paths = primaryNavItems.map((i) => i.path);
    expect(paths).toEqual(["/", "/growth", "/profile"]);
  });

  describe("matchesRole", () => {
    it("空 requiredRoles = 不限制", () => {
      const item = primaryNavItems[0]; // Today
      expect(matchesRole(item, "guest")).toBe(true);
      expect(matchesRole(item, "student")).toBe(true);
    });
  });

  describe("matchesTier", () => {
    it("空 requiredTiers = 不限制", () => {
      const item = primaryNavItems[0]; // Today
      expect(matchesTier(item, "free")).toBe(true);
      expect(matchesTier(item, "pro")).toBe(true);
    });
  });

  describe("isItemVisible", () => {
    it("student 可以看到所有 3 项", () => {
      for (const item of primaryNavItems) {
        expect(isItemVisible(item, "sidebar", studentFree)).toBe(true);
        expect(isItemVisible(item, "bottomNav", studentFree)).toBe(true);
      }
    });

    it("guest 看不到任何 requiresAuth 项", () => {
      for (const item of primaryNavItems) {
        expect(item.requiresAuth).toBe(true);
        expect(isItemVisible(item, "sidebar", guestFree)).toBe(false);
      }
    });
  });

  describe("getNavItemsFor — sidebar 槽位", () => {
    it("student 看到全部 3 项", () => {
      const items = getNavItemsFor("sidebar", studentFree);
      expect(items.length).toBe(3);
      expect(items.map((i) => i.path)).toEqual(["/", "/growth", "/profile"]);
    });

    it("guest 看不到任何项", () => {
      const items = getNavItemsFor("sidebar", guestFree);
      expect(items.length).toBe(0);
    });
  });

  describe("getQuickActions — 四宫格", () => {
    it("student 看到全部 3 项快捷入口", () => {
      const items = getQuickActions(studentFree);
      expect(items.length).toBe(3);
    });

    it("guest 看不到任何快捷入口", () => {
      const items = getQuickActions(guestFree);
      expect(items.length).toBe(0);
    });
  });

  describe("向后兼容：context 不传时不过滤", () => {
    it("不传 context 返回所有 sidebar 项 = 3", () => {
      const items = getNavItemsFor("sidebar");
      expect(items.length).toBe(3);
    });
  });

  describe("priority 排序保持", () => {
    it("sidebar 返回结果按 priority 升序", () => {
      const items = getNavItemsFor("sidebar", studentFree);
      for (let i = 1; i < items.length; i++) {
        expect(items[i].priority).toBeGreaterThanOrEqual(items[i - 1].priority);
      }
    });
  });
});
