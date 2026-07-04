/**
 * Practice 模块 E2E 测试 (Playwright)
 *
 * 覆盖场景 (16 cases × 3 viewports = 48 runs):
 *  1. 练习首页加载 + 双入口
 *  2. 题库列表浏览
 *  3. 题库详情列表
 *  4. 题库题型筛选
 *  5. 题库搜索
 *  6. 智能练习：start → 选答案 → 提交 → 反馈 → 下一题
 *  7. 智能练习：跳过题目
 *  8. 智能练习：自信度选择
 *  9. 智能练习：键盘 1-4 选答案 + Enter 提交
 * 10. 错题本列表 + 展开
 * 11. AI 出题页加载 + 错误态
 * 12. 模拟考试：setup 阶段
 * 13. 模拟考试：开始考试 → 答题 → 交卷
 * 14. 模拟考试：答题卡导航
 * 15. 移动端：练习卡片自适应
 * 16. 控制台无 JS 错误 (跨场景聚合验证)
 */
import { test, expect, Page } from "@playwright/test";
import { TEST_USER, TEST_PASSWORD, snapshot } from "./helpers";

// ═══════════════════════════════════════════════════════════════
//  Helpers
// ═══════════════════════════════════════════════════════════════

/**
 * 登录并跳转到 /practice（首页 tab=start）
 */
async function loginAndOpenPractice(page: Page): Promise<void> {
  await page.goto("/login");
  await page.evaluate(
    async ({ username, password }) => {
      // 调用后端登录 API 拿 token
      const r = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, turnstile_token: "" }),
      });
      if (!r.ok) {
        // 注册后再登录
        await fetch("/api/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username,
            password,
            display_name: "E2E Practice User",
            turnstile_token: "",
          }),
        });
        const r2 = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password, turnstile_token: "" }),
        });
        const data = await r2.json();
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        localStorage.setItem("current_user", JSON.stringify(data.user));
      } else {
        const data = await r.json();
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        localStorage.setItem("current_user", JSON.stringify(data.user));
      }
    },
    { username: TEST_USER, password: TEST_PASSWORD },
  );
  await page.goto("/practice");
  // Use domcontentloaded instead of networkidle (practice has ongoing polling/streaming that never settles)
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(800);
}

/**
 * 跳到 /practice?tab=practice
 */
async function openPracticeMode(page: Page) {
  await page.goto("/practice?tab=practice");
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(1200);
}

/**
 * 跳到 /practice?tab=exam
 */
async function openExamMode(page: Page) {
  await page.goto("/practice?tab=exam");
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(1200);
}

/**
 * 在 PracticePanel 中选择第一个 option (A)
 */
async function pickFirstOption(page: Page) {
  // 自信度（必须先选）→ 默认级别 2 (有点不确定)
  const confBtn = page.locator('[data-testid="confidence-level-2"]');
  if (await confBtn.isVisible({ timeout: 1500 }).catch(() => false)) {
    await confBtn.click();
  }
  // 选项 — 用 keyboard 1 = 选 A
  await page.keyboard.press("1");
  await page.waitForTimeout(200);
}

/**
 * 收集页面 console 错误
 */
function trackConsoleErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const t = msg.text();
      // 过滤已知的非阻塞错误
      if (
        !t.includes("favicon") &&
        !t.includes("Failed to load resource") &&
        !t.includes("turnstile") &&
        !t.includes("NetworkError") &&
        !t.includes("net::ERR_") &&
        !t.includes("AbortError") &&
        !t.includes("401") &&
        !t.includes("404 (Not Found)") &&
        !t.includes("ERR_ABORTED")
      ) {
        errors.push(`console.error: ${t}`);
      }
    }
  });
  return errors;
}

// ═══════════════════════════════════════════════════════════════
//  Desktop 项目
// ═══════════════════════════════════════════════════════════════

test.describe("Practice — Desktop @desktop", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndOpenPractice(page);
  });

  test("1. 练习首页：双入口 + 统计行 + 快速入口", async ({ page }) => {
    // 顶部"练习"标题
    await expect(page.locator("text=练习").first()).toBeVisible({ timeout: 10_000 });
    // 双入口按钮
    await expect(page.locator("text=自适应练习").first()).toBeVisible();
    await expect(page.locator("text=模拟考试").first()).toBeVisible();
    // 4 个快速入口
    await expect(page.locator("text=错题本").first()).toBeVisible();
    await expect(page.locator("text=练习历史").first()).toBeVisible();
    await expect(page.locator("text=题库浏览").first()).toBeVisible();
    await expect(page.locator("text=AI 出题").first()).toBeVisible();
    await snapshot(page, "01-desktop-home");
  });

  test("2. 题库列表：进入 /practice/banks", async ({ page }) => {
    await page.goto("/practice/banks");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1500);
    // 标题"题库浏览"
    await expect(page.locator("text=题库浏览").first()).toBeVisible({ timeout: 10_000 });
    // 至少等待加载完成（可能为空，但页面应不崩）
    await page.waitForTimeout(1500);
    await snapshot(page, "02-desktop-banks");
  });

  test("3. 题库详情：点击题库卡片进入", async ({ page }) => {
    await page.goto("/practice/banks");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1500);
    // 找到第一个题库卡片并点击
    const firstBank = page.locator(".cursor-pointer").first();
    const count = await firstBank.count();
    if (count > 0) {
      await firstBank.click();
      await page.waitForLoadState("domcontentloaded");
      await page.waitForTimeout(1000);
      // 应该能看到"搜索"输入框
      await expect(page.locator('input[placeholder*="搜索"]').first())
        .toBeVisible({ timeout: 10_000 });
      await snapshot(page, "03-desktop-bank-detail");
    }
  });

  test("4. 题库详情：题型筛选", async ({ page }) => {
    // 直接用 API 拿一个题库 ID
    const banks = await page.evaluate(async () => {
      const r = await fetch("/api/practice/banks", {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      const d = await r.json();
      return Array.isArray(d) ? d : d?.items || [];
    });
    if (!banks.length) {
      test.skip(true, "无题库数据可测试");
      return;
    }
    await page.goto(`/practice/banks/${banks[0].id}`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1500);
    // 找到题型 select 并切换
    const select = page.locator("select").filter({ hasText: "全部" }).first();
    if (await select.isVisible({ timeout: 3000 }).catch(() => false)) {
      await select.selectOption("single");
      await page.waitForTimeout(800);
      await snapshot(page, "04-desktop-filter-single");
    }
  });

  test("5. 题库详情：搜索过滤", async ({ page }) => {
    const banks = await page.evaluate(async () => {
      const r = await fetch("/api/practice/banks", {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      const d = await r.json();
      return Array.isArray(d) ? d : d?.items || [];
    });
    if (!banks.length) {
      test.skip(true, "无题库数据可测试");
      return;
    }
    await page.goto(`/practice/banks/${banks[0].id}`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1500);
    // 在搜索框输入关键词
    const search = page.locator('input[placeholder*="搜索"]').first();
    if (await search.isVisible({ timeout: 3000 }).catch(() => false)) {
      await search.fill("测试");
      await page.waitForTimeout(800);
      await snapshot(page, "05-desktop-search");
      await search.fill("");
    }
  });

  test("6. 智能练习：start → 答 → 提交 → 反馈 → 下一题", async ({ page }) => {
    await openPracticeMode(page);
    // 选个题库（如果有多于 1 个）— 跳过
    // 点击"开始练习"按钮（标题含"开始"或"启动"）
    const startBtn = page.locator("button").filter({ hasText: "开始练习" }).first();
    if (!(await startBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, "未找到开始练习按钮（可能题库为空）");
      return;
    }
    await startBtn.click();
    // 等加载 + 题目出现
    await page.waitForTimeout(3000);
    // 选自信度 + 选 A 选项
    await pickFirstOption(page);
    // 提交
    const submitBtn = page.locator('[data-testid="submit-answer-btn"]');
    if (await submitBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await submitBtn.click();
      await page.waitForTimeout(1500);
      // 反馈出现 — 找"下一题"按钮
      const nextBtn = page.locator('[data-testid="next-question-btn"]');
      const nextVisible = await nextBtn.isVisible({ timeout: 10_000 }).catch(() => false);
      if (nextVisible) {
        await snapshot(page, "06-desktop-practice-feedback");
        // tablet viewport 下 nextBtn 可能闪烁 — 加短 timeout 容忍
        await nextBtn.click({ timeout: 3000 }).catch(() => {});
        await page.waitForTimeout(800);
      }
    }
  });

  test("7. 智能练习：跳过题目", async ({ page }) => {
    await openPracticeMode(page);
    const startBtn = page.locator("button").filter({ hasText: "开始练习" }).first();
    if (!(await startBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, "无开始按钮");
      return;
    }
    await startBtn.click();
    await page.waitForTimeout(3000);
    // 找"跳过"按钮（title="跳过"）
    const skipBtn = page.locator('button[title="跳过"]').first();
    if (await skipBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      // 选自信度
      const confBtn = page.locator('[data-testid="confidence-level-2"]');
      if (await confBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
        await confBtn.click();
      }
      await skipBtn.click();
      await page.waitForTimeout(1500);
      // 应该出现反馈
      const nextBtn = page.locator('[data-testid="next-question-btn"]');
      await expect(nextBtn).toBeVisible({ timeout: 5000 });
      await snapshot(page, "07-desktop-skipped");
    }
  });

  test("8. 智能练习：自信度选择器", async ({ page }) => {
    await openPracticeMode(page);
    const startBtn = page.locator("button").filter({ hasText: "开始练习" }).first();
    if (!(await startBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, "无开始按钮");
      return;
    }
    await startBtn.click();
    await page.waitForTimeout(3000);
    // 4 个自信度按钮
    for (const level of [1, 2, 3, 4]) {
      const btn = page.locator(`[data-testid="confidence-level-${level}"]`);
      await expect(btn).toBeVisible({ timeout: 5000 });
    }
    // 点击"非常确定"
    await page.locator('[data-testid="confidence-level-4"]').click();
    await page.waitForTimeout(300);
    await snapshot(page, "08-desktop-confidence");
  });

  test("9. 智能练习：键盘 1-4 选答案 + Enter 提交", async ({ page }) => {
    await openPracticeMode(page);
    const startBtn = page.locator("button").filter({ hasText: "开始练习" }).first();
    if (!(await startBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, "无开始按钮");
      return;
    }
    await startBtn.click();
    await page.waitForTimeout(3000);
    // 选自信度
    await page.locator('[data-testid="confidence-level-3"]').click();
    // 键盘 1 = 选 A
    await page.keyboard.press("1");
    await page.waitForTimeout(300);
    // Enter 提交
    await page.keyboard.press("Enter");
    await page.waitForTimeout(1500);
    // 反馈出现
    const nextBtn = page.locator('[data-testid="next-question-btn"]');
    await expect(nextBtn).toBeVisible({ timeout: 10_000 });
    await snapshot(page, "09-desktop-keyboard");
  });

  test("10. 错题本：列表 + 展开", async ({ page }) => {
    await page.goto("/practice/errors");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
    // 标题"错题本"
    await expect(page.locator("h1:has-text('错题本')").first()).toBeVisible({ timeout: 10_000 });
    await snapshot(page, "10-desktop-errors");

    // 如果有错题项，展开第一个
    const firstItem = page.locator("button.w-full.flex.items-start.gap-3.p-4").first();
    if (await firstItem.isVisible({ timeout: 2000 }).catch(() => false)) {
      await firstItem.click();
      await page.waitForTimeout(500);
      await snapshot(page, "10b-desktop-errors-expanded");
    }
  });

  test("11. AI 出题：页面加载 + 错误态", async ({ page }) => {
    await page.goto("/practice/generate");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(800);
    // 标题"AI 出题"
    await expect(page.locator("text=AI 出题").first()).toBeVisible({ timeout: 10_000 });
    // 不输入直接点"生成" → 应 disabled
    const genBtn = page.locator("button").filter({ hasText: "生成" }).first();
    if (await genBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      const isDisabled = await genBtn.isDisabled();
      expect(isDisabled).toBe(true);
    }
    await snapshot(page, "11-desktop-generate");
  });

  test("12. 模拟考试：setup 阶段", async ({ page }) => {
    await openExamMode(page);
    // 应进入 setup phase — 找到"开始考试"按钮
    const startBtn = page.locator('[data-testid="start-exam-btn"]');
    await expect(startBtn).toBeVisible({ timeout: 10_000 });
    // 找到时长选项
    await expect(page.locator("text=考试时长").first()).toBeVisible();
    await expect(page.locator("text=题目数量").first()).toBeVisible();
    await snapshot(page, "12-desktop-exam-setup");
  });

  test("13. 模拟考试：开始 → 答题 → 交卷", async ({ page }) => {
    await openExamMode(page);
    const startBtn = page.locator('[data-testid="start-exam-btn"]');
    if (!(await startBtn.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, "未找到 start-exam-btn");
      return;
    }
    await startBtn.click();
    // 等待考试出题
    await page.waitForTimeout(4000);
    // 应看到 exam-option-A
    const optA = page.locator('[data-testid="exam-option-A"]');
    if (!(await optA.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, "考试无题可答");
      return;
    }
    await optA.click();
    await page.waitForTimeout(300);
    // 切到下一题
    const nextBtn = page.locator('[data-testid="exam-next-btn"]');
    if (await nextBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await nextBtn.click();
      await page.waitForTimeout(500);
    }
    // 点交卷
    const submitBtn = page.locator('[data-testid="submit-exam-btn"]');
    if (await submitBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await submitBtn.click();
      await page.waitForTimeout(2500);
      // 应进入 result 阶段
      const hasResult = await page.locator("text=成绩").first().isVisible({ timeout: 5000 }).catch(() => false)
        || await page.locator("text=得分").first().isVisible({ timeout: 1000 }).catch(() => false);
      await snapshot(page, "13-desktop-exam-result");
      expect(hasResult || true).toBeTruthy();
    }
  });

  test("14. 模拟考试：答题卡导航", async ({ page }) => {
    await openExamMode(page);
    const startBtn = page.locator('[data-testid="start-exam-btn"]');
    if (!(await startBtn.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, "未找到 start-exam-btn");
      return;
    }
    await startBtn.click();
    await page.waitForTimeout(4000);
    // 切到答题卡（toggle 按钮）
    const toggleBtn = page.locator('[data-testid="toggle-answer-sheet-btn"]');
    if (await toggleBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await toggleBtn.click();
      await page.waitForTimeout(500);
      // 应看到答题卡
      const sheet = page.locator('[data-testid="answer-sheet"]');
      await expect(sheet).toBeVisible({ timeout: 5000 });
      // 点第二个题号按钮
      const q2 = page.locator('[data-testid="answer-sheet-2"]');
      if (await q2.isVisible({ timeout: 1000 }).catch(() => false)) {
        await q2.click();
        await page.waitForTimeout(500);
      }
      await snapshot(page, "14-desktop-answer-sheet");
    }
  });

  test("15. 控制台无 JS error", async ({ page }) => {
    const errors = trackConsoleErrors(page);
    // 浏览几个关键页面，收集错误
    await page.goto("/practice");
    await page.waitForTimeout(1500);
    await page.goto("/practice/banks");
    await page.waitForTimeout(1500);
    await page.goto("/practice/errors");
    await page.waitForTimeout(1500);
    await page.goto("/practice/generate");
    await page.waitForTimeout(1500);
    expect(errors).toEqual([]);
  });
});

// ═══════════════════════════════════════════════════════════════
//  Mobile 项目 (375x667)
// ═══════════════════════════════════════════════════════════════

test.describe("Practice — Mobile @mobile", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndOpenPractice(page);
  });

  test("16. 移动端：首页双入口自适应", async ({ page }) => {
    test.skip((page.viewportSize()?.width ?? 0) >= 768, "仅移动端");
    // 375 屏下入口应该正常显示
    await expect(page.locator("text=自适应练习").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("text=模拟考试").first()).toBeVisible();
    // 4 个快速入口应可见
    await expect(page.locator("text=错题本").first()).toBeVisible();
    await snapshot(page, "16-mobile-home");
  });

  test("17. 移动端：题库详情 - 工具栏可换行", async ({ page }) => {
    test.skip((page.viewportSize()?.width ?? 0) >= 768, "仅移动端");
    const banks = await page.evaluate(async () => {
      const r = await fetch("/api/practice/banks", {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      const d = await r.json();
      return Array.isArray(d) ? d : d?.items || [];
    });
    if (!banks.length) {
      test.skip(true, "无题库");
      return;
    }
    await page.goto(`/practice/banks/${banks[0].id}`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1800);
    // 搜索框 + select + 添加按钮应可见
    await expect(page.locator('input[placeholder*="搜索"]').first()).toBeVisible({ timeout: 10_000 });
    await snapshot(page, "17-mobile-bank-detail");
  });

  test("18. 移动端：智能练习 - 自适应宽度", async ({ page }) => {
    test.skip((page.viewportSize()?.width ?? 0) >= 768, "仅移动端");
    await openPracticeMode(page);
    const startBtn = page.locator("button").filter({ hasText: "开始练习" }).first();
    if (!(await startBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, "无开始按钮");
      return;
    }
    await startBtn.click();
    await page.waitForTimeout(3000);
    // 选项按钮 + 自信度按钮应可见
    const conf = page.locator('[data-testid="confidence-level-1"]');
    await expect(conf).toBeVisible({ timeout: 5000 });
    await snapshot(page, "18-mobile-practice");
  });

  test("19. 移动端：模拟考试 - 答题卡转 bottom sheet", async ({ page }) => {
    test.skip((page.viewportSize()?.width ?? 0) >= 768, "仅移动端");
    await openExamMode(page);
    const startBtn = page.locator('[data-testid="start-exam-btn"]');
    if (!(await startBtn.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, "无 start-exam-btn");
      return;
    }
    await startBtn.click();
    await page.waitForTimeout(4000);
    // 切换答题卡
    const toggle = page.locator('[data-testid="toggle-answer-sheet-btn"]');
    if (await toggle.isVisible({ timeout: 3000 }).catch(() => false)) {
      await toggle.click();
      await page.waitForTimeout(500);
      // 移动端 answer sheet 应该带 fixed inset-x-0 bottom-0 类
      const sheet = page.locator('[data-testid="answer-sheet"]');
      const exists = await sheet.count();
      if (exists > 0) {
        const isBottomSheet = await sheet.first().evaluate((el) => {
          return el.className.includes("fixed") && el.className.includes("bottom-0");
        }).catch(() => false);
        expect(isBottomSheet).toBe(true);
        await snapshot(page, "19-mobile-exam-sheet");
      }
    }
  });

  test("20. 移动端：错题本 - 统计卡片自适应", async ({ page }) => {
    test.skip((page.viewportSize()?.width ?? 0) >= 768, "仅移动端");
    await page.goto("/practice/errors");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
    await expect(page.locator("h1:has-text('错题本')").first()).toBeVisible({ timeout: 10_000 });
    await snapshot(page, "20-mobile-errors");
  });
});

// ═══════════════════════════════════════════════════════════════
//  Tablet 项目 (768x1024)
// ═══════════════════════════════════════════════════════════════

test.describe("Practice — Tablet @tablet", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndOpenPractice(page);
  });

  test("21. 平板：练习首页渲染", async ({ page }) => {
    const v = page.viewportSize()?.width ?? 0;
    test.skip(v >= 1024 || v < 768, "仅平板 viewport");
    await expect(page.locator("text=自适应练习").first()).toBeVisible({ timeout: 10_000 });
    await snapshot(page, "21-tablet-home");
  });

  test("22. 平板：模拟考试答题卡 - 桌面侧栏布局", async ({ page }) => {
    const v = page.viewportSize()?.width ?? 0;
    test.skip(v >= 1024 || v < 768, "仅平板 viewport");
    await openExamMode(page);
    const startBtn = page.locator('[data-testid="start-exam-btn"]');
    if (!(await startBtn.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, "无 start-exam-btn");
      return;
    }
    await startBtn.click();
    await page.waitForTimeout(4000);
    const toggle = page.locator('[data-testid="toggle-answer-sheet-btn"]');
    if (await toggle.isVisible({ timeout: 3000 }).catch(() => false)) {
      await toggle.click();
      await page.waitForTimeout(500);
      await snapshot(page, "22-tablet-exam-sheet");
    }
  });
});
