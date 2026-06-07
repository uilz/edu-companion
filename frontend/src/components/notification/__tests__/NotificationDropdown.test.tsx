import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { useNotificationStore } from "@/store/notification/notification-store";
import type { SecretaryNotification } from "@/store/notification/types";
import NotificationDropdown from "../NotificationDropdown";

function createNotif(
  overrides: Partial<SecretaryNotification> = {}
): SecretaryNotification {
  return {
    id: "n1",
    emoji: "🔔",
    title: "通知标题",
    description: "通知描述内容",
    priority: 3,
    target: { pages: ["learn"] },
    source: "secretary",
    read: false,
    status: "pending",
    created_at: Date.now(),
    ...overrides,
  };
}

describe("NotificationDropdown", () => {
  afterEach(() => {
    cleanup();
    useNotificationStore.getState().clearAll();
  });

  it("显示当前页面的未读通知列表", () => {
    const store = useNotificationStore.getState();
    store.addNotification(createNotif({ id: "a", title: "通知 A" }));
    store.addNotification(createNotif({ id: "b", title: "通知 B" }));
    store.addNotification(createNotif({
      id: "c",
      title: "通知 C",
      target: { pages: ["dashboard"] },
    }));

    render(<NotificationDropdown page="learn" />);

    expect(screen.getByText("通知 A")).toBeTruthy();
    expect(screen.getByText("通知 B")).toBeTruthy();
    expect(screen.queryByText("通知 C")).toBeNull();
  });

  it("无通知时显示空状态提示", () => {
    render(<NotificationDropdown page="learn" />);
    expect(screen.getByText(/暂无新通知/i)).toBeTruthy();
  });

  it("每条通知显示 emoji、标题、描述和来源", () => {
    const store = useNotificationStore.getState();
    store.addNotification(createNotif({
      title: "疲劳提醒",
      description: "已学习 2 小时，建议休息",
      emoji: "😴",
      source: "secretary",
    }));

    render(<NotificationDropdown page="learn" />);

    expect(screen.getByText("😴")).toBeTruthy();
    expect(screen.getByText("疲劳提醒")).toBeTruthy();
    expect(screen.getByText(/已学习 2 小时/)).toBeTruthy();
  });

  it("点击采纳按钮应将通知标记为 accepted", async () => {
    const store = useNotificationStore.getState();
    store.addNotification(createNotif({ id: "a" }));

    render(<NotificationDropdown page="learn" />);

    fireEvent.click(screen.getByRole("button", { name: /采纳/i }));

    await waitFor(() => {
      expect(store.getNotifications()[0].status).toBe("accepted");
    });
  });

  it("点击忽略按钮应将通知标记为 dismissed", async () => {
    const store = useNotificationStore.getState();
    store.addNotification(createNotif({ id: "a" }));

    render(<NotificationDropdown page="learn" />);

    fireEvent.click(screen.getByRole("button", { name: /忽略/i }));

    await waitFor(() => {
      expect(store.getNotifications()[0].status).toBe("dismissed");
    });
  });

  it("采纳或忽略后通知从下拉列表消失", async () => {
    const store = useNotificationStore.getState();
    store.addNotification(createNotif({ id: "a", title: "唯一通知" }));

    render(<NotificationDropdown page="learn" />);

    expect(screen.getByText("唯一通知")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /采纳/i }));

    await waitFor(() => {
      expect(screen.queryByText("唯一通知")).toBeNull();
    });
    expect(screen.getByText(/暂无新通知/i)).toBeTruthy();
  });
});