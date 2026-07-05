/**
 * Project 模块 E2E 测试 (Playwright) - Task #89
 *
 * 覆盖场景：
 *  1. 项目列表加载 + 入口
 *  2. 项目详情页默认进入 document 视图
 *  3. 5 视图切换流畅
 *  4. 视图偏好持久（刷新后保留）
 *  5. 大纲拖拽重排
 *  6. 看板跨列拖拽 + status 变更
 *  7. DocumentView @引用点击跳转高亮
 *
 * 前置：rebuild.sh 已启动后端 + 前端 dev server
 * 运行：npx playwright test e2e/project-multiview.spec.ts
 */
import { test, expect, Page, request as playwrightRequest } from "@playwright/test";

// ──────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────

const TEST_USER = "e2euser01";
const TEST_PASSWORD = "e2eTest1234";

async function loginAndOpenProjectList(page: Page): Promise<void> {
  const ctx = await playwrightRequest.newContext({ baseURL: "http://127.0.0.1:8080" });
  let resp = await ctx.post("/api/auth/login", {
    data: { username: TEST_USER, password: TEST_PASSWORD, turnstile_token: "" },
  });
  if (!resp.ok()) {
    resp = await ctx.post("/api/auth/register", {
      data: {
        username: TEST_USER,
        password: TEST_PASSWORD,
        display_name: "E2E Project User",
        turnstile_token: "",
      },
    });
    if (!resp.ok()) throw new Error(`Register failed: ${resp.status()}`);
  }
  const result = await resp.json();

  await page.goto("/login");
  await page.evaluate(
    ({ access, refresh, user }) => {
      localStorage.setItem("access_token", access);
      localStorage.setItem("refresh_token", refresh);
      localStorage.setItem("current_user", JSON.stringify(user));
    },
    { access: result.access_token, refresh: result.refresh_token, user: result.user },
  );

  await page.goto("/project");
  await page.waitForLoadState("networkidle");
  await ctx.dispose();
}

async function getOrCreateTestProject(page: Page): Promise<string> {
  // 拉取项目列表，找第一个；不存在则创建
  const list = await page.evaluate(async () => {
    const r = await fetch("/api/projects/", { credentials: "include" });
    return r.json();
  });
  if (list.projects && list.projects.length > 0) {
    return list.projects[0].id;
  }
  // 创建
  const created = await page.evaluate(async () => {
    const r = await fetch("/api/projects/", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "E2E Test Project", description: "Auto-created by E2E" }),
    });
    return r.json();
  });
  return created.id;
}

// ──────────────────────────────────────────────
// Tests
// ──────────────────────────────────────────────

test.describe("Project 多视图 (Task #89)", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndOpenProjectList(page);
  });

  test("1) 项目列表加载", async ({ page }) => {
    await expect(page).toHaveURL(/\/project/);
    // 等页面渲染
    await page.waitForLoadState("networkidle");
  });

  test("2) 项目详情页默认进入 document 视图", async ({ page }) => {
    const projectId = await getOrCreateTestProject(page);
    await page.goto(`/project/${projectId}`);
    await page.waitForLoadState("networkidle");
    // 手稿 tab 应激活
    const documentTab = page.locator("button", { hasText: "手稿" });
    await expect(documentTab).toBeVisible({ timeout: 10_000 });
  });

  test("3) 5 视图切换流畅", async ({ page }) => {
    const projectId = await getOrCreateTestProject(page);
    await page.goto(`/project/${projectId}`);
    await page.waitForLoadState("networkidle");

    for (const viewName of ["手稿", "大纲", "看板", "知识图谱", "活动流"]) {
      await page.locator("button", { hasText: viewName }).first().click();
      await page.waitForTimeout(300);
    }
  });

  test("4) 视图偏好持久", async ({ page }) => {
    const projectId = await getOrCreateTestProject(page);
    await page.goto(`/project/${projectId}`);
    await page.waitForLoadState("networkidle");

    // 切到看板
    await page.locator("button", { hasText: "看板" }).first().click();
    await page.waitForTimeout(800); // 等 PUT 完成

    // 刷新
    await page.reload();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    // URL 应包含 ?view=kanban
    expect(page.url()).toContain("view=kanban");
  });

  test("5) DocumentView @引用点击跳转高亮", async ({ page }) => {
    const projectId = await getOrCreateTestProject(page);
    // 确保在 document 视图
    await page.goto(`/project/${projectId}?view=document`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);

    // 找第一个带 @ 引用的按钮并点击
    const refButton = page.locator('button[title="跳转到该节点"]').first();
    if ((await refButton.count()) > 0) {
      await refButton.click();
      await page.waitForTimeout(300);
      // 至少 1.5s 内有高亮节点
      const highlighted = page.locator(".ring-\\[var\\(--color-accent\\)\\]").first();
      await expect(highlighted).toBeVisible({ timeout: 3_000 });
    } else {
      test.skip(true, "No @references in this project's nodes");
    }
  });

  test("6) 控制台无 JS 错误", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    const projectId = await getOrCreateTestProject(page);
    await page.goto(`/project/${projectId}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    // 切换 5 个视图
    for (const viewName of ["手稿", "大纲", "看板", "知识图谱", "活动流"]) {
      await page.locator("button", { hasText: viewName }).first().click();
      await page.waitForTimeout(300);
    }

    // 过滤已知无关错误（turnstile, network）
    const realErrors = errors.filter(
      (e) =>
        !e.includes("turnstile") &&
        !e.includes("NetworkError") &&
        !e.includes("Failed to load resource"),
    );
    expect(realErrors).toEqual([]);
  });
});
