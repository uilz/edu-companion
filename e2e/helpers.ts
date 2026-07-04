/**
 * 共享 E2E 工具：登录 + 跳转对话页
 */
import { Page, expect, request as playwrightRequest } from "@playwright/test";

export const TEST_USER = "e2euser01";
export const TEST_PASSWORD = "e2eTest1234";

/**
 * 登录并跳转到 /conversation
 *
 * 策略：直接调用后端登录 API → 拿到 token → 注入 localStorage → 跳转。
 * 比走 UI 登录表单更稳定（避免 Turnstile / 表单渲染时序问题）。
 */
export async function loginAndOpenConversation(page: Page): Promise<void> {
  // 用 API 上下文登录（不受页面 state 干扰）
  const ctx = await playwrightRequest.newContext({ baseURL: "http://127.0.0.1:8080" });
  let result: any;
  // 先尝试登录；失败则注册
  let resp = await ctx.post("/api/auth/login", {
    data: { username: TEST_USER, password: TEST_PASSWORD, turnstile_token: "" },
  });
  if (!resp.ok()) {
    resp = await ctx.post("/api/auth/register", {
      data: {
        username: TEST_USER,
        password: TEST_PASSWORD,
        display_name: "E2E Test User",
        turnstile_token: "",
      },
    });
    if (!resp.ok()) {
      throw new Error(`Register failed: ${resp.status()} ${await resp.text()}`);
    }
  }
  result = await resp.json();

  // 打开 /login 以便 localStorage 可用，然后注入 token
  await page.goto("/login");
  await page.evaluate(
    ({ access, refresh, user }) => {
      localStorage.setItem("access_token", access);
      localStorage.setItem("refresh_token", refresh);
      localStorage.setItem("current_user", JSON.stringify(user));
    },
    {
      access: result.access_token,
      refresh: result.refresh_token,
      user: result.user,
    },
  );

  // 跳转到对话页
  await page.goto("/conversation");
  await page.waitForLoadState("networkidle");

  // 等对话页核心元素出现
  await expect(page.locator('[data-testid="chat-input-container"]').first())
    .toBeVisible({ timeout: 20_000 });
  await ctx.dispose();
}

/**
 * 等待消息气泡出现
 */
export async function waitForMessage(page: Page, text: string, timeout = 10_000) {
  await page.locator(`text="${text}"`).first().waitFor({ state: "visible", timeout });
}

/**
 * 截图并保存到指定目录（用于交付物归档）
 */
export async function snapshot(page: Page, name: string) {
  await page.screenshot({ path: `playwright-report/screenshots/${name}.png`, fullPage: true });
}
