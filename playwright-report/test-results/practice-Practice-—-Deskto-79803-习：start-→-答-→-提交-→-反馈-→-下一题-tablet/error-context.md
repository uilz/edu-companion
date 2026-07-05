# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: practice.spec.ts >> Practice — Desktop @desktop >> 6. 智能练习：start → 答 → 提交 → 反馈 → 下一题
- Location: e2e/practice.spec.ts:240:7

# Error details

```
TimeoutError: locator.click: Timeout 5000ms exceeded.
Call log:
  - waiting for locator('[data-testid="next-question-btn"]')

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - alert [ref=e2]
  - generic [ref=e3]:
    - banner [ref=e4]:
      - button "打开菜单" [ref=e5] [cursor=pointer]:
        - img [ref=e6]
      - generic [ref=e7]: 苹果果
    - complementary "导航菜单" [ref=e8]:
      - generic [ref=e9]:
        - link "果 苹果果" [ref=e10] [cursor=pointer]:
          - /url: /
          - generic [ref=e12]: 果
          - generic [ref=e13]: 苹果果
        - button "关闭菜单" [ref=e14] [cursor=pointer]:
          - img [ref=e15]
      - navigation [ref=e18]:
        - generic [ref=e19]:
          - link "驾驶舱" [ref=e20] [cursor=pointer]:
            - /url: /dashboard
            - img [ref=e22]
            - generic [ref=e32]: 驾驶舱
          - link "练习" [ref=e33] [cursor=pointer]:
            - /url: /practice
            - img [ref=e35]
            - generic [ref=e41]: 练习
          - link "闪卡" [ref=e43] [cursor=pointer]:
            - /url: /flashcard
            - img [ref=e45]
            - generic [ref=e49]: 闪卡
          - link "阅读" [ref=e50] [cursor=pointer]:
            - /url: /reading
            - img [ref=e52]
            - generic [ref=e54]: 阅读
          - link "知识树" [ref=e55] [cursor=pointer]:
            - /url: /knowledge-tree
            - img [ref=e57]
            - generic [ref=e62]: 知识树
          - link "对话" [ref=e63] [cursor=pointer]:
            - /url: /conversation
            - img [ref=e65]
            - generic [ref=e67]: 对话
          - link "秘书" [ref=e68] [cursor=pointer]:
            - /url: /secretary
            - img [ref=e70]
            - generic [ref=e73]: 秘书
          - link "语音房" [ref=e74] [cursor=pointer]:
            - /url: /liveroom
            - img [ref=e76]
            - generic [ref=e79]: 语音房
          - link "分析" [ref=e80] [cursor=pointer]:
            - /url: /analytics
            - img [ref=e82]
            - generic [ref=e84]: 分析
          - link "文件" [ref=e85] [cursor=pointer]:
            - /url: /files
            - img [ref=e87]
            - generic [ref=e90]: 文件
          - link "设置" [ref=e91] [cursor=pointer]:
            - /url: /settings
            - img [ref=e93]
            - generic [ref=e96]: 设置
          - link "心情" [ref=e97] [cursor=pointer]:
            - /url: /emotion
            - img [ref=e99]
            - generic [ref=e101]: 心情
      - generic [ref=e102]:
        - generic [ref=e103]:
          - generic [ref=e104]: E
          - generic [ref=e105]:
            - generic [ref=e106]: E2E Test User
            - generic [ref=e107]: "@e2euser01"
          - button "退出登录" [ref=e108] [cursor=pointer]:
            - img [ref=e109]
        - link "设置" [ref=e112] [cursor=pointer]:
          - /url: /settings
          - img [ref=e113]
          - generic [ref=e116]: 设置
        - button "深色模式" [ref=e117] [cursor=pointer]:
          - img [ref=e118]
          - generic [ref=e124]: 深色模式
        - generic [ref=e125]: 苹果果 v1.0
    - main [ref=e126]:
      - generic [ref=e128]:
        - generic [ref=e130]:
          - button "← 返回" [ref=e131] [cursor=pointer]
          - generic [ref=e132]: "|"
          - generic [ref=e133]: 智能练习
        - generic [ref=e135]:
          - generic [ref=e136]:
            - img [ref=e138]
            - heading "智能练习" [level=3] [ref=e148]
          - button "基于资料出题" [ref=e150] [cursor=pointer]:
            - img [ref=e151]
            - text: 基于资料出题
          - generic [ref=e153]:
            - paragraph [ref=e154]: 练习模式
            - generic [ref=e155]:
              - button "自适应" [ref=e156] [cursor=pointer]:
                - img [ref=e158]
                - generic [ref=e168]: 自适应
              - button "复习" [ref=e169] [cursor=pointer]:
                - img [ref=e171]
                - generic [ref=e174]: 复习
              - button "挑战" [ref=e175] [cursor=pointer]:
                - img [ref=e177]
                - generic [ref=e179]: 挑战
          - generic [ref=e180]:
            - paragraph [ref=e181]: 题数
            - generic [ref=e182]:
              - button "3 题" [ref=e183] [cursor=pointer]
              - button "5 题" [ref=e184] [cursor=pointer]
              - button "10 题" [ref=e185] [cursor=pointer]
          - generic [ref=e186]:
            - paragraph [ref=e187]: 难度
            - generic [ref=e188]:
              - button "自适应" [ref=e189] [cursor=pointer]
              - button "简单" [ref=e190] [cursor=pointer]
              - button "中等" [ref=e191] [cursor=pointer]
              - button "困难" [ref=e192] [cursor=pointer]
          - button "开始练习" [ref=e193] [cursor=pointer]:
            - img [ref=e194]
            - text: 开始练习
          - paragraph [ref=e196]: "键盘: 1-4 选答案 · Enter 提交/下一题"
    - generic "AI 秘书" [ref=e197]:
      - img [ref=e199]
```

# Test source

```ts
  163 |     await page.waitForLoadState("domcontentloaded");
  164 |     await page.waitForTimeout(1500);
  165 |     // 标题"题库浏览"
  166 |     await expect(page.locator("text=题库浏览").first()).toBeVisible({ timeout: 10_000 });
  167 |     // 至少等待加载完成（可能为空，但页面应不崩）
  168 |     await page.waitForTimeout(1500);
  169 |     await snapshot(page, "02-desktop-banks");
  170 |   });
  171 | 
  172 |   test("3. 题库详情：点击题库卡片进入", async ({ page }) => {
  173 |     await page.goto("/practice/banks");
  174 |     await page.waitForLoadState("domcontentloaded");
  175 |     await page.waitForTimeout(1500);
  176 |     // 找到第一个题库卡片并点击
  177 |     const firstBank = page.locator(".cursor-pointer").first();
  178 |     const count = await firstBank.count();
  179 |     if (count > 0) {
  180 |       await firstBank.click();
  181 |       await page.waitForLoadState("domcontentloaded");
  182 |       await page.waitForTimeout(1000);
  183 |       // 应该能看到"搜索"输入框
  184 |       await expect(page.locator('input[placeholder*="搜索"]').first())
  185 |         .toBeVisible({ timeout: 10_000 });
  186 |       await snapshot(page, "03-desktop-bank-detail");
  187 |     }
  188 |   });
  189 | 
  190 |   test("4. 题库详情：题型筛选", async ({ page }) => {
  191 |     // 直接用 API 拿一个题库 ID
  192 |     const banks = await page.evaluate(async () => {
  193 |       const r = await fetch("/api/practice/banks", {
  194 |         headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
  195 |       });
  196 |       const d = await r.json();
  197 |       return Array.isArray(d) ? d : d?.items || [];
  198 |     });
  199 |     if (!banks.length) {
  200 |       test.skip(true, "无题库数据可测试");
  201 |       return;
  202 |     }
  203 |     await page.goto(`/practice/banks/${banks[0].id}`);
  204 |     await page.waitForLoadState("domcontentloaded");
  205 |     await page.waitForTimeout(1500);
  206 |     // 找到题型 select 并切换
  207 |     const select = page.locator("select").filter({ hasText: "全部" }).first();
  208 |     if (await select.isVisible({ timeout: 3000 }).catch(() => false)) {
  209 |       await select.selectOption("single");
  210 |       await page.waitForTimeout(800);
  211 |       await snapshot(page, "04-desktop-filter-single");
  212 |     }
  213 |   });
  214 | 
  215 |   test("5. 题库详情：搜索过滤", async ({ page }) => {
  216 |     const banks = await page.evaluate(async () => {
  217 |       const r = await fetch("/api/practice/banks", {
  218 |         headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
  219 |       });
  220 |       const d = await r.json();
  221 |       return Array.isArray(d) ? d : d?.items || [];
  222 |     });
  223 |     if (!banks.length) {
  224 |       test.skip(true, "无题库数据可测试");
  225 |       return;
  226 |     }
  227 |     await page.goto(`/practice/banks/${banks[0].id}`);
  228 |     await page.waitForLoadState("domcontentloaded");
  229 |     await page.waitForTimeout(1500);
  230 |     // 在搜索框输入关键词
  231 |     const search = page.locator('input[placeholder*="搜索"]').first();
  232 |     if (await search.isVisible({ timeout: 3000 }).catch(() => false)) {
  233 |       await search.fill("测试");
  234 |       await page.waitForTimeout(800);
  235 |       await snapshot(page, "05-desktop-search");
  236 |       await search.fill("");
  237 |     }
  238 |   });
  239 | 
  240 |   test("6. 智能练习：start → 答 → 提交 → 反馈 → 下一题", async ({ page }) => {
  241 |     await openPracticeMode(page);
  242 |     // 选个题库（如果有多于 1 个）— 跳过
  243 |     // 点击"开始练习"按钮（标题含"开始"或"启动"）
  244 |     const startBtn = page.locator("button").filter({ hasText: "开始练习" }).first();
  245 |     if (!(await startBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
  246 |       test.skip(true, "未找到开始练习按钮（可能题库为空）");
  247 |       return;
  248 |     }
  249 |     await startBtn.click();
  250 |     // 等加载 + 题目出现
  251 |     await page.waitForTimeout(3000);
  252 |     // 选自信度 + 选 A 选项
  253 |     await pickFirstOption(page);
  254 |     // 提交
  255 |     const submitBtn = page.locator('[data-testid="submit-answer-btn"]');
  256 |     if (await submitBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
  257 |       await submitBtn.click();
  258 |       await page.waitForTimeout(1500);
  259 |       // 反馈出现 — 找"下一题"按钮
  260 |       const nextBtn = page.locator('[data-testid="next-question-btn"]');
  261 |       await expect(nextBtn).toBeVisible({ timeout: 10_000 });
  262 |       await snapshot(page, "06-desktop-practice-feedback");
> 263 |       await nextBtn.click();
      |                     ^ TimeoutError: locator.click: Timeout 5000ms exceeded.
  264 |       await page.waitForTimeout(800);
  265 |     }
  266 |   });
  267 | 
  268 |   test("7. 智能练习：跳过题目", async ({ page }) => {
  269 |     await openPracticeMode(page);
  270 |     const startBtn = page.locator("button").filter({ hasText: "开始练习" }).first();
  271 |     if (!(await startBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
  272 |       test.skip(true, "无开始按钮");
  273 |       return;
  274 |     }
  275 |     await startBtn.click();
  276 |     await page.waitForTimeout(3000);
  277 |     // 找"跳过"按钮（title="跳过"）
  278 |     const skipBtn = page.locator('button[title="跳过"]').first();
  279 |     if (await skipBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
  280 |       // 选自信度
  281 |       const confBtn = page.locator('[data-testid="confidence-level-2"]');
  282 |       if (await confBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
  283 |         await confBtn.click();
  284 |       }
  285 |       await skipBtn.click();
  286 |       await page.waitForTimeout(1500);
  287 |       // 应该出现反馈
  288 |       const nextBtn = page.locator('[data-testid="next-question-btn"]');
  289 |       await expect(nextBtn).toBeVisible({ timeout: 5000 });
  290 |       await snapshot(page, "07-desktop-skipped");
  291 |     }
  292 |   });
  293 | 
  294 |   test("8. 智能练习：自信度选择器", async ({ page }) => {
  295 |     await openPracticeMode(page);
  296 |     const startBtn = page.locator("button").filter({ hasText: "开始练习" }).first();
  297 |     if (!(await startBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
  298 |       test.skip(true, "无开始按钮");
  299 |       return;
  300 |     }
  301 |     await startBtn.click();
  302 |     await page.waitForTimeout(3000);
  303 |     // 4 个自信度按钮
  304 |     for (const level of [1, 2, 3, 4]) {
  305 |       const btn = page.locator(`[data-testid="confidence-level-${level}"]`);
  306 |       await expect(btn).toBeVisible({ timeout: 5000 });
  307 |     }
  308 |     // 点击"非常确定"
  309 |     await page.locator('[data-testid="confidence-level-4"]').click();
  310 |     await page.waitForTimeout(300);
  311 |     await snapshot(page, "08-desktop-confidence");
  312 |   });
  313 | 
  314 |   test("9. 智能练习：键盘 1-4 选答案 + Enter 提交", async ({ page }) => {
  315 |     await openPracticeMode(page);
  316 |     const startBtn = page.locator("button").filter({ hasText: "开始练习" }).first();
  317 |     if (!(await startBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
  318 |       test.skip(true, "无开始按钮");
  319 |       return;
  320 |     }
  321 |     await startBtn.click();
  322 |     await page.waitForTimeout(3000);
  323 |     // 选自信度
  324 |     await page.locator('[data-testid="confidence-level-3"]').click();
  325 |     // 键盘 1 = 选 A
  326 |     await page.keyboard.press("1");
  327 |     await page.waitForTimeout(300);
  328 |     // Enter 提交
  329 |     await page.keyboard.press("Enter");
  330 |     await page.waitForTimeout(1500);
  331 |     // 反馈出现
  332 |     const nextBtn = page.locator('[data-testid="next-question-btn"]');
  333 |     await expect(nextBtn).toBeVisible({ timeout: 10_000 });
  334 |     await snapshot(page, "09-desktop-keyboard");
  335 |   });
  336 | 
  337 |   test("10. 错题本：列表 + 展开", async ({ page }) => {
  338 |     await page.goto("/practice/errors");
  339 |     await page.waitForLoadState("domcontentloaded");
  340 |     await page.waitForTimeout(2000);
  341 |     // 标题"错题本"
  342 |     await expect(page.locator("h1:has-text('错题本')").first()).toBeVisible({ timeout: 10_000 });
  343 |     await snapshot(page, "10-desktop-errors");
  344 | 
  345 |     // 如果有错题项，展开第一个
  346 |     const firstItem = page.locator("button.w-full.flex.items-start.gap-3.p-4").first();
  347 |     if (await firstItem.isVisible({ timeout: 2000 }).catch(() => false)) {
  348 |       await firstItem.click();
  349 |       await page.waitForTimeout(500);
  350 |       await snapshot(page, "10b-desktop-errors-expanded");
  351 |     }
  352 |   });
  353 | 
  354 |   test("11. AI 出题：页面加载 + 错误态", async ({ page }) => {
  355 |     await page.goto("/practice/generate");
  356 |     await page.waitForLoadState("domcontentloaded");
  357 |     await page.waitForTimeout(800);
  358 |     // 标题"AI 出题"
  359 |     await expect(page.locator("text=AI 出题").first()).toBeVisible({ timeout: 10_000 });
  360 |     // 不输入直接点"生成" → 应 disabled
  361 |     const genBtn = page.locator("button").filter({ hasText: "生成" }).first();
  362 |     if (await genBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
  363 |       const isDisabled = await genBtn.isDisabled();
```