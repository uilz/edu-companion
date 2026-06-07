import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useNotificationStore } from "@/store/notification/notification-store";
import type { SecretaryNotification } from "@/store/notification/types";
import NavBellBadge from "../NavBellBadge";

// ══════════════════════════════════════════════════════════════
//  NavBellBadge — 组件行为测试
// ══════════════════════════════════════════════════════════════

function createNotif(
  overrides: Partial<SecretaryNotification> = {}
): SecretaryNotification {
  return {
    id: "n1",
    emoji: "🔔",
    title: "通知",
    description: "描述",
    priority: 3,
    target: { pages: ["learn"] },
    source: "secretary",
    read: false,
    status: "pending",
    created_at: Date.now(),
    ...overrides,
  };
}

describe("NavBellBadge", () => {
  beforeEach(() => {
    useNotificationStore.getState().clearAll();
  });

  it("当前页面有未读通知时显示铃铛和计数的红点", () => {
    const store = useNotificationStore.getState();
    store.addNotification(createNotif({ target: { pages: ["learn"] } }));
    store.addNotification(createNotif({ target: { pages: ["learn"] } }));

    render(<NavBellBadge page="learn" />);

    // 应该有铃铛图标
    const bell = screen.getByTestId("nav-bell");
    expect(bell).toBeTruthy();

    // 应该有 badge 显示 2
    const badge = screen.getByTestId("nav-bell-badge");
    expect(badge.textContent).toBe("2");
  });

  it("无未读通知时只显示铃铛，不显示红点", () => {
    render(<NavBellBadge page="learn" />);

    const bell = screen.getByTestId("nav-bell");
    expect(bell).toBeTruthy();

    const badge = screen.queryByTestId("nav-bell-badge");
    expect(badge).toBeNull();
  });

  it("只统计当前 page 的通知，忽略其他页面", () => {
    const store = useNotificationStore.getState();
    store.addNotification(createNotif({ id: "a", target: { pages: ["learn"] } }));
    store.addNotification(createNotif({ id: "b", target: { pages: ["dashboard"] } }));

    render(<NavBellBadge page="learn" />);

    const badge = screen.getByTestId("nav-bell-badge");
    expect(badge.textContent).toBe("1");
  });

  it("点击铃铛应触发 onToggle 回调", async () => {
    const store = useNotificationStore.getState();
    store.addNotification(createNotif());
    store.addNotification(createNotif());

    let toggled = false;
    render(<NavBellBadge page="learn" onToggle={() => { toggled = true; }} />);

    const bell = screen.getByTestId("nav-bell");
    await userEvent.click(bell);

    expect(toggled).toBe(true);
  });

  it("阅读通知后 badge 数字应自动更新", () => {
    const store = useNotificationStore.getState();
    store.addNotification(createNotif({ id: "x", target: { pages: ["learn"] } }));
    store.addNotification(createNotif({ id: "y", target: { pages: ["learn"] } }));

    render(<NavBellBadge page="learn" />);

    expect(screen.getByTestId("nav-bell-badge").textContent).toBe("2");

    // 标记一条已读 → badge 应变为 1
    act(() => {
      store.markRead("x");
    });

    expect(screen.getByTestId("nav-bell-badge").textContent).toBe("1");
  });
});