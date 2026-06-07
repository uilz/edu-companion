import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { useNotificationStore } from "@/store/notification/notification-store";
import type { SecretaryNotification } from "@/store/notification/types";
import SecretaryInlineBanner from "../SecretaryInlineBanner";

function createInlineNotif(
  overrides: Partial<SecretaryNotification> = {}
): SecretaryNotification {
  return {
    id: "inline_001",
    emoji: "🤖",
    title: "秘书建议",
    description: "你最近在微积分上花了大量时间，建议去看看线性代数。",
    priority: 3,
    target: {
      pages: ["learn"],
      inlineConversationId: "conv_123",
    },
    source: "secretary",
    read: false,
    status: "pending",
    created_at: Date.now(),
    ...overrides,
  };
}

describe("SecretaryInlineBanner", () => {
  afterEach(() => {
    cleanup();
    useNotificationStore.getState().clearAll();
  });

  it("匹配 conversationId 的内联通知应渲染", () => {
    useNotificationStore.getState().addNotification(
      createInlineNotif({ target: { pages: ["learn"], inlineConversationId: "conv_123" } })
    );

    render(<SecretaryInlineBanner conversationId="conv_123" />);

    expect(screen.getByText("🤖")).toBeTruthy();
    expect(screen.getByText("秘书建议")).toBeTruthy();
    expect(screen.getByText(/你最近在微积分上/)).toBeTruthy();
  });

  it("不匹配 conversationId 的通知不渲染", () => {
    useNotificationStore.getState().addNotification(
      createInlineNotif({ target: { pages: ["learn"], inlineConversationId: "conv_456" } })
    );

    const { container } = render(<SecretaryInlineBanner conversationId="conv_123" />);
    expect(container.innerHTML).toBe("");
  });

  it("没有 inlineConversationId 的通知不渲染", () => {
    useNotificationStore.getState().addNotification(
      createInlineNotif({ target: { pages: ["learn"] } })
    );

    const { container } = render(<SecretaryInlineBanner conversationId="conv_123" />);
    expect(container.innerHTML).toBe("");
  });

  it("已读的通知不渲染", () => {
    useNotificationStore.getState().addNotification(
      createInlineNotif({
        id: "read_notif",
        read: true,
        target: { pages: ["learn"], inlineConversationId: "conv_123" },
      })
    );

    const { container } = render(<SecretaryInlineBanner conversationId="conv_123" />);
    expect(container.innerHTML).toBe("");
  });

  it("点击采纳按钮应标记为 accepted", async () => {
    useNotificationStore.getState().addNotification(
      createInlineNotif({ id: "n1", target: { pages: ["learn"], inlineConversationId: "conv_123" } })
    );

    render(<SecretaryInlineBanner conversationId="conv_123" />);

    const acceptBtn = screen.getByRole("button", { name: /采纳/i });
    fireEvent.click(acceptBtn);

    await waitFor(() => {
      expect(useNotificationStore.getState().getNotifications()[0].status).toBe("accepted");
    });
  });

  it("点击忽略按钮应标记为 dismissed", async () => {
    useNotificationStore.getState().addNotification(
      createInlineNotif({ id: "n2", target: { pages: ["learn"], inlineConversationId: "conv_123" } })
    );

    render(<SecretaryInlineBanner conversationId="conv_123" />);

    const dismissBtn = screen.getByRole("button", { name: /忽略/i });
    fireEvent.click(dismissBtn);

    await waitFor(() => {
      expect(useNotificationStore.getState().getNotifications()[0].status).toBe("dismissed");
    });
  });

  it("采纳后通知块从 DOM 消失", async () => {
    useNotificationStore.getState().addNotification(
      createInlineNotif({ id: "n3", title: "会消失的通知", target: { pages: ["learn"], inlineConversationId: "conv_123" } })
    );

    render(<SecretaryInlineBanner conversationId="conv_123" />);

    expect(screen.getByText("会消失的通知")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /采纳/i }));

    await waitFor(() => {
      expect(screen.queryByText("会消失的通知")).toBeNull();
    });
  });
});