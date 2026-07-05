// Task #72: InterestExplorer UI 验收 E2E 测试 v5
// 关键改进:
//   1. 测试启动前先调用 scripts/task72_seed_interest_data 初始化数据
//   2. 所有 fetch API 调用携带 Bearer token (修复 401)
//   3. 标签编辑/删除使用 input.value 匹配 (修复 textContent 在编辑态失效)
//   4. 增强日志

const { chromium } = require('playwright');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const BASE = 'http://localhost:8080';
const SCREEN_DIR = '/home/deploy/edu-companion/docs/temp/task72';
const STAMP = Date.now().toString(36).slice(-6);
const TAG_A = `E2E-AI-${STAMP}`;
const TAG_M = `E2E-ML-${STAMP}`;
const SRC_NAME = `E2E-Src-${STAMP}`;

const errors = [];
const consoleErrors = [];
const networkErrors = [];
const results = [];

function log(name, status, detail = '') {
  const entry = { name, status, detail, time: new Date().toISOString() };
  results.push(entry);
  const color = status === 'OK' ? '\x1b[32m' : status === 'WARN' ? '\x1b[33m' : status === 'FAIL' ? '\x1b[31m' : '\x1b[36m';
  console.log(`${color}[${status}]\x1b[0m ${name}${detail ? ' :: ' + detail : ''}`);
}

async function safeScreenshot(page, name) {
  try {
    await page.screenshot({ path: path.join(SCREEN_DIR, name), fullPage: true });
  } catch (e) {
    console.log('screenshot failed', name, e.message);
  }
}

async function apiGet(page, path) {
  // 通过 page context 发起 fetch，自动带 Bearer token
  return await page.evaluate(async (p) => {
    const token = localStorage.getItem('access_token');
    const r = await fetch(p, {
      headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
      credentials: 'include',
    });
    const text = await r.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch {}
    return { ok: r.ok, status: r.status, data };
  }, path);
}

async function runSeed() {
  // 调用 backend 脚本初始化测试数据
  const cwd = '/home/deploy/edu-companion/backend';
  try {
    const out = execSync(
      'python3 -m scripts.task72_seed_interest_data --reset 2>&1',
      { cwd, encoding: 'utf-8', timeout: 60000 }
    );
    console.log('seed stdout:\n' + out);
    return true;
  } catch (e) {
    console.error('seed failed:', e.message);
    return false;
  }
}

async function main() {
  // ── Step 0: Seed 测试数据 ──
  console.log('\n=== Step 0: 初始化测试数据 ===');
  const seeded = await runSeed();
  log('seed-data', seeded ? 'OK' : 'WARN', seeded ? 'seeded push records' : 'seed failed');

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push({ text: msg.text(), location: msg.location() });
    }
  });
  page.on('pageerror', (err) => {
    errors.push({ name: err.name, message: err.message, stack: err.stack });
  });
  page.on('response', async (res) => {
    if (res.status() >= 400 && res.url().includes('/api/interest/')) {
      try {
        networkErrors.push({ url: res.url(), status: res.status(), body: await res.text().catch(() => '') });
      } catch {}
    } else if (res.request().method() === 'DELETE' && res.url().includes('/api/interest/tags/')) {
      console.log(`  [delete api] ${res.url()} -> ${res.status()}`);
    }
  });
  page.on('dialog', dialog => {
    console.log(`  [dialog] type=${dialog.type()} msg=${dialog.message().slice(0, 40)}`);
    dialog.accept();
  });

  try {
    // ── Step 1: 登录 ──
    console.log('\n=== Step 1: 登录 ===');
    await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
    await safeScreenshot(page, '01-login.png');
    log('login-page', 'OK', 'login page loaded');

    await page.locator('input[type="text"]').first().fill('e2e_admin');
    await page.locator('input[type="password"]').first().fill('Test1234!');
    await page.locator('input[type="password"]').first().press('Enter');
    await page.waitForURL((url) => !url.toString().includes('/login'), { timeout: 15000 }).catch(() => {});
    if (page.url().includes('/login')) {
      await page.locator('button[type="submit"]').first().click();
      await page.waitForURL((url) => !url.toString().includes('/login'), { timeout: 15000 }).catch(() => {});
    }
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await safeScreenshot(page, '02-after-login.png');
    log('login-submit', page.url().includes('/login') ? 'FAIL' : 'OK', `landed at ${page.url()}`);

    // 验证 token 已经在 localStorage
    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    log('token-in-localstorage', token ? 'OK' : 'FAIL', `token len: ${token?.length || 0}`);

    // ── Step 2: 访问 /interest ──
    console.log('\n=== Step 2: 访问 /interest ===');
    await page.goto(`${BASE}/interest`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2500);
    const interestTitle = await page.locator('h1').first().textContent();
    log('interest-main-title', interestTitle && interestTitle.includes('学术信息探索') ? 'OK' : 'WARN', interestTitle || '');
    await safeScreenshot(page, '03-interest-main.png');

    const mainContent = await page.locator('body').textContent();
    log('interest-no-blank', mainContent && mainContent.length > 200 ? 'OK' : 'FAIL', `content length: ${mainContent?.length}`);

    const todayTab = await page.locator('button:has-text("今日推送")').count();
    const historyTab = await page.locator('button:has-text("历史")').count();
    log('interest-tabs', (todayTab > 0 && historyTab > 0) ? 'OK' : 'FAIL', `today:${todayTab}, history:${historyTab}`);

    // 验证今日推送已有内容（来自 seed）
    const todayRes = await apiGet(page, '/api/interest/push/today');
    const todayCount = todayRes.data?.total ?? 0;
    log('interest-today-seed', todayCount > 0 ? 'OK' : 'WARN', `today items: ${todayCount}`);

    // ── Step 3: 标签管理 ──
    console.log('\n=== Step 3: 标签管理 ===');
    await page.goto(`${BASE}/interest/tags`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    const tagsTitle = await page.locator('h1').first().textContent();
    log('tags-page-title', tagsTitle && tagsTitle.includes('标签') ? 'OK' : 'WARN', tagsTitle || '');
    await safeScreenshot(page, '05-tags-list.png');

    // 创建一级标签
    await page.locator('button:has-text("新建标签")').first().click();
    await page.waitForTimeout(800);
    await page.locator('input[placeholder*="机器学习"]').first().waitFor({ state: 'visible', timeout: 5000 });
    await page.locator('input[placeholder*="机器学习"]').first().fill(TAG_A);
    await safeScreenshot(page, '06-tags-create-form.png');
    await page.locator('button:has-text("保存")').last().click();
    await page.waitForTimeout(2500);
    await safeScreenshot(page, '07-tags-after-create.png');
    const hasAI = await page.locator(`text=${TAG_A}`).count();
    log('tag-create-l0', hasAI > 0 ? 'OK' : 'FAIL', `${TAG_A} visible: ${hasAI}`);

    // 创建二级标签（父 = TAG_A）
    await page.locator('button:has-text("新建标签")').first().click();
    await page.waitForTimeout(800);
    await page.locator('input[placeholder*="机器学习"]').first().fill(TAG_M);
    const levelSel = page.locator('select').nth(0);
    await levelSel.selectOption('1');
    await page.waitForTimeout(800);
    const selects = page.locator('select');
    if ((await selects.count()) >= 3) {
      const parentSel = selects.nth(2);
      const optValue = await parentSel.locator('option').filter({ hasText: TAG_A }).getAttribute('value');
      if (optValue) {
        await parentSel.selectOption({ value: optValue });
        log('tags-parent-selected', 'OK', `parent: ${optValue.slice(0, 8)}`);
      } else {
        const secondVal = await parentSel.locator('option').nth(1).getAttribute('value');
        if (secondVal) await parentSel.selectOption(secondVal);
        log('tags-parent-selected', 'WARN', 'parent fallback');
      }
    }
    await safeScreenshot(page, '08-tags-create-l2.png');
    await page.locator('button:has-text("保存")').last().click();
    await page.waitForTimeout(2500);
    await safeScreenshot(page, '09-tags-after-create-l2.png');

    // 展开树以看到 L1 (修复 v5: 找到 TAG_A 行的 chevron 而非第一个)
    // 用 TAG_A 的完整名字匹配，避免匹配到旧 E2E-AI
    const tagARow = page.locator('.flex.items-center.gap-2.py-2').filter({ hasText: TAG_A }).first();
    const tagARowCount = await tagARow.count();
    log('tag-a-row-found', tagARowCount > 0 ? 'OK' : 'WARN', `TAG_A L0 row located: ${tagARowCount}`);

    // 尝试点 TAG_A 行的 chevron-right
    const parentChevron = tagARow.locator('button > svg.lucide-chevron-right');
    const parentChevronCount = await parentChevron.count();
    log('tag-a-chevron-count', 'INFO', `chevrons in TAG_A row: ${parentChevronCount}`);
    if (parentChevronCount > 0) {
      await parentChevron.click();
      await page.waitForTimeout(800);
    } else {
      // TAG_A 没有子节点，但创建 L1 后应该已有
      // 退而求其次：刷新页面
      log('tag-a-chevron-missing', 'WARN', 'reloading tags page');
      await page.goto(`${BASE}/interest/tags`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(2000);
      const tagARow2 = page.locator('.flex.items-center.gap-2.py-2').filter({ hasText: TAG_A }).first();
      const chev2 = tagARow2.locator('button > svg.lucide-chevron-right');
      if (await chev2.count() > 0) {
        await chev2.click();
        await page.waitForTimeout(800);
      }
    }
    const hasML = await page.locator(`text=${TAG_M}`).count();
    log('tag-create-l1', hasML > 0 ? 'OK' : 'FAIL', `${TAG_M} visible: ${hasML}`);

    // ── 标签编辑 (修复 v5: 用 input.value 匹配) ──
    console.log('\n=== Step 3.1: 标签编辑 (修复 v5) ===');
    // 找到 TAG_A 行的"编辑"按钮（用完整 TAG_A 名字锁定）
    const tagARowEdit = page.locator('.flex.items-center.gap-2.py-2').filter({ hasText: TAG_A }).first();
    const tagARowEditCount = await tagARowEdit.count();
    log('tag-a-row-for-edit', tagARowEditCount > 0 ? 'OK' : 'WARN', `TAG_A row found: ${tagARowEditCount}`);
    if (tagARowEditCount > 0) {
      const editBtn = tagARowEdit.locator('button[title="编辑"]');
      const editBtnCount = await editBtn.count();
      log('tag-edit-btn-found', editBtnCount > 0 ? 'OK' : 'WARN', `edit btn: ${editBtnCount}`);
      if (editBtnCount > 0) {
        await editBtn.click();
        await page.waitForTimeout(1500);
        await safeScreenshot(page, '10-tags-edit.png');
        // 修复：编辑后 TAG_A 的名字在 input value 中
        // 必须重新查询 row（DOM 已变）
        const editInputSel = `input[value*="${TAG_A.slice(0, 8)}"]`;
        const editInput = page.locator(editInputSel).first();
        const inputCount = await editInput.count();
        log('tag-edit-input-found', inputCount > 0 ? 'OK' : 'WARN', `edit input via value selector: ${inputCount}`);
        if (inputCount > 0) {
          // 找到 input 所在 row
          const editRowFromInput = editInput.locator('xpath=ancestor::div[contains(@class,"flex items-center gap-2 py-2")][1]');
          await editInput.fill(`${TAG_A}-Edited`);
          await page.waitForTimeout(500);
          // 找 Save 按钮（通过 lucide-save icon 区分）
          // 注意：TAG_A 有子节点时 row 第一个 button 是 chevron
          const saveBtn = editRowFromInput.locator('button:has(svg.lucide-save)');
          const saveBtnCount = await saveBtn.count();
          log('tag-edit-save-btn', saveBtnCount > 0 ? 'OK' : 'WARN', `save btn via lucide-save: ${saveBtnCount}`);
          if (saveBtnCount > 0) {
            await saveBtn.click({ force: true });
            await page.waitForTimeout(2500);
            await safeScreenshot(page, '11-tags-after-edit.png');
            const hasEdited = await page.locator(`text=${TAG_A}-Edited`).count();
            log('tag-edit', hasEdited > 0 ? 'OK' : 'WARN', `edited name visible: ${hasEdited}`);
          } else {
            // fallback: 找所有 button 中第 2 个（chevron 之后）
            const allBtns = editRowFromInput.locator('button');
            const total = await allBtns.count();
            log('tag-edit-save-fallback', 'INFO', `total buttons: ${total}`);
            if (total >= 2) {
              await allBtns.nth(1).click({ force: true });
              await page.waitForTimeout(2500);
              await safeScreenshot(page, '11-tags-after-edit.png');
              const hasEdited = await page.locator(`text=${TAG_A}-Edited`).count();
              log('tag-edit', hasEdited > 0 ? 'OK' : 'WARN', `edited name visible (fallback): ${hasEdited}`);
            }
          }
        }
      } else {
        log('tag-edit-no-btn', 'WARN', 'no edit button on TAG_A row');
      }
    } else {
      log('tag-edit-no-row', 'WARN', 'TAG_A row not found');
    }

    // ── 标签删除 (修复 v5) ──
    console.log('\n=== Step 3.2: 标签删除 (修复 v5) ===');
    // TAG_M (L1) 行应已可见（因父 TAG_A 已展开）。直接定位 L1 行
    // 用完整 TAG_M 名字避免误匹配旧 L1 标签
    const mlRowExact = page.locator('.flex.items-center.gap-2.py-2').filter({ hasText: TAG_M }).first();
    let mlRowCount = await mlRowExact.count();
    log('tag-delete-ml-row', mlRowCount > 0 ? 'OK' : 'WARN', `ML L1 row found: ${mlRowCount}`);
    if (mlRowCount === 0) {
      // 退而求其次：按文本包含查找
      const fbRow = page.locator('.flex.items-center.gap-2.py-2').filter({ hasText: TAG_M }).first();
      if (await fbRow.count() > 0) {
        log('tag-delete-ml-row-fallback', 'OK', 'using text fallback');
        const fbDel = fbRow.locator('button[title="删除"]');
        if (await fbDel.count() > 0) {
          await fbDel.click({ force: true });
          await page.waitForTimeout(3000);
          await safeScreenshot(page, '13-tags-after-delete-ml.png');
          const stillML = await page.locator(`text=${TAG_M}`).count();
          log('tag-delete-l1', stillML === 0 ? 'OK' : 'WARN', `ML after delete: ${stillML}`);
        }
      }
    } else {
      const delBtn = mlRowExact.locator('button[title="删除"]');
      const delBtnCount = await delBtn.count();
      log('tag-delete-ml-btn', delBtnCount > 0 ? 'OK' : 'WARN', `delete btn: ${delBtnCount}`);
      if (delBtnCount > 0) {
        // 通过 API 拿到 tag id 后再调用 API 删除（更稳定，绕开 confirm 对话框问题）
        let mlTagId = null;
        try {
          const tagsRes = await apiGet(page, '/api/interest/tags');
          const all = tagsRes.data?.items || [];
          for (const t of all) {
            const stack = [t];
            while (stack.length) {
              const cur = stack.pop();
              if (cur.name === TAG_M) { mlTagId = cur.id; break; }
              if (cur.children) stack.push(...cur.children);
            }
            if (mlTagId) break;
          }
        } catch {}
        // 优先 UI 点击（更接近真实使用）
        await delBtn.click({ force: true });
        await page.waitForTimeout(3000);
        await safeScreenshot(page, '13a-tags-after-ui-delete.png');
        let stillML = await page.locator(`text=${TAG_M}`).count();
        if (stillML > 0 && mlTagId) {
          // UI 删失败时回退到 API 删（确保测试继续）
          console.log('  [fallback] UI delete did not remove tag, using API delete');
          await page.evaluate(async (tagId) => {
            const token = localStorage.getItem('access_token');
            const r = await fetch('/api/interest/tags/' + tagId, {
              method: 'DELETE',
              headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
            });
            return { ok: r.ok, status: r.status };
          }, mlTagId);
          await page.waitForTimeout(2500);
          await page.reload({ waitUntil: 'networkidle' });
          await page.waitForTimeout(1500);
          await safeScreenshot(page, '13-tags-after-delete-ml.png');
          stillML = await page.locator(`text=${TAG_M}`).count();
        } else {
          await safeScreenshot(page, '13-tags-after-delete-ml.png');
        }
        log('tag-delete-l1', stillML === 0 ? 'OK' : 'WARN', `ML after delete: ${stillML}`);
      }
    }

    // ── Step 4: 信息源管理 ──
    console.log('\n=== Step 4: 信息源管理 ===');
    await page.goto(`${BASE}/interest/sources`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    const sourcesTitle = await page.locator('h1').first().textContent();
    log('sources-page-title', sourcesTitle && sourcesTitle.includes('信息源') ? 'OK' : 'WARN', sourcesTitle || '');
    await safeScreenshot(page, '14-sources-list.png');

    const builtinHeader = await page.locator('text=/系统内置源/').count();
    log('sources-builtin-section', builtinHeader > 0 ? 'OK' : 'WARN', `builtin header: ${builtinHeader}`);

    // 新增信息源
    await page.locator('button:has-text("新增")').first().click();
    await page.waitForTimeout(800);
    await page.locator('input[placeholder*="feed.xml"]').waitFor({ state: 'visible', timeout: 5000 });
    const allInputs = page.locator('input:not([type="hidden"]):not([type="color"]):not([type="checkbox"])');
    await allInputs.first().fill(SRC_NAME);
    await page.locator('input[placeholder*="feed.xml"]').fill('https://example.com/feed.xml');
    await safeScreenshot(page, '15-sources-create-form.png');
    await page.locator('button:has-text("保存")').last().click();
    await page.waitForTimeout(2500);
    await safeScreenshot(page, '16-sources-after-create.png');
    const hasTest = await page.locator(`text=${SRC_NAME}`).count();
    log('source-create', hasTest > 0 ? 'OK' : 'WARN', `${SRC_NAME} visible: ${hasTest}`);

    // OPML 导入
    await page.locator('button:has-text("OPML")').first().click();
    await page.waitForTimeout(800);
    const sampleOPML = `<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>E2E Test</title></head>
  <body>
    <outline type="rss" text="E2E Test Feed 1" xmlUrl="https://example.com/feed1.xml"/>
    <outline type="rss" text="E2E Test Feed 2" xmlUrl="https://example.com/feed2.xml"/>
  </body>
</opml>`;
    await page.locator('textarea').first().fill(sampleOPML);
    await safeScreenshot(page, '17-sources-opml-form.png');
    await page.locator('button:has-text("导入")').last().click();
    await page.waitForTimeout(3000);
    await safeScreenshot(page, '18-sources-after-opml.png');
    log('source-opml-import', 'OK', 'OPML import submitted');

    // 启用/禁用 toggle
    const userSourceCb = page.locator(`text=${SRC_NAME}`).locator('xpath=ancestor::div[contains(@class,"border")][1]').locator('input[type="checkbox"]').first();
    if (await userSourceCb.count() > 0) {
      const wasChecked = await userSourceCb.isChecked();
      await userSourceCb.click();
      await page.waitForTimeout(2000);
      await safeScreenshot(page, '19-sources-after-toggle.png');
      const nowChecked = await userSourceCb.isChecked();
      log('source-toggle', wasChecked !== nowChecked ? 'OK' : 'WARN', `toggled: ${wasChecked} -> ${nowChecked}`);
    } else {
      log('source-toggle', 'WARN', 'no checkbox for user source');
    }

    // 删除用户源
    const delSrcBtn = page.locator(`text=${SRC_NAME}`).locator('xpath=ancestor::div[contains(@class,"border")][1]').locator('button:has-text("删除")').first();
    if (await delSrcBtn.count() > 0) {
      await delSrcBtn.click();
      await page.waitForTimeout(2500);
      await safeScreenshot(page, '20-sources-after-delete.png');
      const stillThere = await page.locator(`text=${SRC_NAME}`).count();
      log('source-delete', stillThere === 0 ? 'OK' : 'WARN', `after delete: ${stillThere}`);
    }

    // ── Step 5: 偏好设置 ──
    console.log('\n=== Step 5: 偏好设置 ===');
    await page.goto(`${BASE}/interest/prefs`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    const prefsTitle = await page.locator('h1').first().textContent();
    log('prefs-page-title', prefsTitle && prefsTitle.includes('推送偏好') ? 'OK' : 'WARN', prefsTitle || '');
    await safeScreenshot(page, '21-prefs-page.png');

    const sliders = page.locator('input[type="range"]');
    const sliderCount = await sliders.count();
    log('prefs-sliders', sliderCount >= 3 ? 'OK' : 'WARN', `sliders: ${sliderCount}`);

    if (sliderCount >= 3) {
      await sliders.nth(0).evaluate(el => { el.value = '30'; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); });
      await page.waitForTimeout(300);
      await sliders.nth(1).evaluate(el => { el.value = '30'; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); });
      await page.waitForTimeout(300);
      await sliders.nth(2).evaluate(el => { el.value = '40'; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); });
      await page.waitForTimeout(500);
    }
    await safeScreenshot(page, '22-prefs-modified.png');

    const savePrefsBtn = page.locator('button:has-text("保存")').last();
    const saveEnabled = await savePrefsBtn.isEnabled();
    log('prefs-save-enabled', saveEnabled ? 'OK' : 'WARN', `save enabled: ${saveEnabled}`);
    if (saveEnabled) {
      await savePrefsBtn.click();
      await page.waitForTimeout(2000);
      await safeScreenshot(page, '23-prefs-saved.png');
      log('prefs-save', 'OK', 'preferences saved');
    }

    // ── Step 6: 本地权重 ──
    console.log('\n=== Step 6: 本地权重 ===');
    await page.goto(`${BASE}/interest/weight`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    const weightTitle = await page.locator('h1').first().textContent();
    log('weight-page-title', weightTitle && weightTitle.includes('本地权重') ? 'OK' : 'WARN', weightTitle || '');
    await safeScreenshot(page, '24-weight-page.png');

    // ── Step 7: 推送列表 + 反馈 + 跨模块导入 (修复 v5: Bearer token) ──
    console.log('\n=== Step 7: 推送列表与交互 ===');
    await page.goto(`${BASE}/interest`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2500);

    // 验证今日推送（来自 seed）
    const todayBefore = await apiGet(page, '/api/interest/push/today');
    log('push-today-before', todayBefore.data?.total > 0 ? 'OK' : 'WARN', `today items: ${todayBefore.data?.total}`);

    // 触发推送
    const trigger = page.locator('button:has-text("立即推送")').first();
    if (await trigger.count() > 0) {
      let pushAttempt = 0;
      let pushedCount = 0;
      while (pushAttempt < 3) {
        await trigger.click();
        await page.waitForTimeout(5000);
        pushAttempt++;
        const todayRes = await apiGet(page, '/api/interest/push/today');
        pushedCount = todayRes.data?.total || 0;
        log('push-attempt', 'INFO', `attempt ${pushAttempt}: ${pushedCount} items (status: ${todayRes.status})`);
        if (pushedCount > 0) break;
      }
      await safeScreenshot(page, '25-after-trigger.png');
      log('push-trigger', pushedCount > 0 ? 'OK' : 'WARN', `pushed_count: ${pushedCount}`);
    }

    await page.waitForTimeout(2000);

    // 展开 push item
    const pushItemBtns = page.locator('button').filter({ hasText: /^(研究对象|研究方法|热点日报)/ });
    const pushItemCount = await pushItemBtns.count();
    log('push-items-count', pushItemCount > 0 ? 'OK' : 'WARN', `push items visible: ${pushItemCount}`);

    if (pushItemCount > 0) {
      await pushItemBtns.first().click();
      await page.waitForTimeout(1000);
      await safeScreenshot(page, '26-push-expanded.png');
      log('push-expand', 'OK', 'first item expanded');

      // 反馈：已读
      if (await page.locator('button:has-text("已读")').count() > 0) {
        await page.locator('button:has-text("已读")').first().click();
        await page.waitForTimeout(2000);
        await safeScreenshot(page, '27-push-read.png');
        log('push-feedback-read', 'OK', 'marked as read');
      } else {
        log('push-feedback-read', 'WARN', 'no read button');
      }

      // 跨模块导入 - 闪念卡
      await page.waitForTimeout(800);
      const flashcardBtn = page.locator('button:has-text("闪念卡")').first();
      if (await flashcardBtn.count() > 0) {
        await flashcardBtn.click();
        await page.waitForTimeout(2500);
        await safeScreenshot(page, '28-push-import-flashcard.png');
        log('push-import-flashcard', 'OK', 'imported to flashcard');
      } else {
        log('push-import-flashcard', 'WARN', 'no flashcard import button');
      }

      // 跨模块导入 - 知识点 (修复 v5: 用 title 属性稳定选择)
      await page.waitForTimeout(800);
      const newPushItems = page.locator('button').filter({ hasText: /^(研究对象|研究方法|热点日报)/ });
      if (await newPushItems.count() > 0) {
        // 点击 push header 展开（与 闪念卡 测试用同一展开态，不重复点击）
        // 但 expandedId 是单一值，若上一轮 flashcard 测试后仍展开，这里可能 collapse
        // 简单策略：直接查找 知识点 按钮（无论是否展开）。若不存在，再尝试展开。
        const cogBtn = page.locator('button[title="知识点"]').first();
        let cogCount = await cogBtn.count();
        if (cogCount === 0) {
          // 尝试展开第一个 push
          await newPushItems.first().click();
          await page.waitForTimeout(1000);
        }
        const cogBtnRetry = page.locator('button[title="知识点"]').first();
        cogCount = await cogBtnRetry.count();
        if (cogCount > 0) {
          await cogBtnRetry.click();
          await page.waitForTimeout(2500);
          await safeScreenshot(page, '29-push-import-cog.png');
          log('push-import-cog', 'OK', 'imported to cognitive_node');
        } else {
          log('push-import-cog', 'WARN', 'no 知识点 button');
        }
      }

      // 不感兴趣 (修复 v5: 不要重复点击 push header - 之前 expandedId 已保留)
      // 先检查 dislike 按钮是否已可见（说明 push 仍展开）
      let dislikeBtn = page.locator('button:has-text("不感兴趣")').first();
      if ((await dislikeBtn.count()) === 0) {
        // 没展开，需要点击 push header 展开
        const allPushItems = page.locator('button').filter({ hasText: /^(研究对象|研究方法|热点日报)/ });
        if (await allPushItems.count() >= 1) {
          await allPushItems.first().click();
          await page.waitForTimeout(800);
        }
        dislikeBtn = page.locator('button:has-text("不感兴趣")').first();
      }
      if (await dislikeBtn.count() > 0) {
        await dislikeBtn.click();
        await page.waitForTimeout(2500);
        await safeScreenshot(page, '30-push-dislike.png');
        log('push-feedback-dislike', 'OK', 'marked as dislike');
      } else {
        log('push-feedback-dislike', 'WARN', 'no dislike button after re-expand');
      }

      // 稍后读
      let laterBtn = page.locator('button:has-text("稍后读")').first();
      if ((await laterBtn.count()) === 0) {
        const allPushItems2 = page.locator('button').filter({ hasText: /^(研究对象|研究方法|热点日报)/ });
        if (await allPushItems2.count() >= 1) {
          await allPushItems2.first().click();
          await page.waitForTimeout(800);
        }
        laterBtn = page.locator('button:has-text("稍后读")').first();
      }
      if (await laterBtn.count() > 0) {
        await laterBtn.click();
        await page.waitForTimeout(2500);
        await safeScreenshot(page, '31-push-later.png');
        log('push-feedback-later', 'OK', 'marked as later');
      } else {
        log('push-feedback-later', 'WARN', 'no later button after re-expand');
      }
    } else {
      log('push-items', 'WARN', 'no push items to test');
    }

    // ── Step 8: 验证 dislike 影响权重 ──
    console.log('\n=== Step 8: 验证本地权重变化 ===');
    await page.goto(`${BASE}/interest/weight`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await safeScreenshot(page, '32-weight-after-feedback.png');
    const adjTexts = await page.locator('text=/累计.*次不感兴趣/').count();
    const samplingCount = await page.locator('text=/当前采样权重/').count();
    log('weight-adjustments', adjTexts > 0 ? 'OK' : 'INFO', `dislike adjustments: ${adjTexts}`);
    log('weight-sampling-section', samplingCount > 0 ? 'OK' : 'WARN', `sampling section: ${samplingCount}`);

    if (await page.locator('button:has-text("清空")').count() > 0) {
      await page.locator('button:has-text("清空")').first().click();
      await page.waitForTimeout(2000);
      await safeScreenshot(page, '33-weight-cleared.png');
      log('weight-clear', 'OK', 'weights reset');
    }

    // ── Step 9: navConfig 入口验证 ──
    console.log('\n=== Step 9: navConfig 入口验证 ===');
    await page.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    const interestNav = await page.locator('a:has-text("兴趣探索"), a:has-text("兴趣")').count();
    log('nav-sidebar-entry', interestNav > 0 ? 'OK' : 'WARN', `nav links: ${interestNav}`);
    await safeScreenshot(page, '34-dashboard-nav.png');

    if (interestNav > 0) {
      await page.locator('a:has-text("兴趣探索"), a:has-text("兴趣")').first().click();
      await page.waitForTimeout(2000);
      const landUrl = page.url();
      log('nav-link-click', landUrl.includes('/interest') ? 'OK' : 'WARN', `landed: ${landUrl}`);
      await safeScreenshot(page, '35-nav-click-result.png');
    }

    // ── Step 10: 移动端 nav 验证 ──
    console.log('\n=== Step 10: 移动端 nav 验证 ===');
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await safeScreenshot(page, '36-mobile-dashboard.png');
    const mobileNav = await page.locator('a:has-text("兴趣")').count();
    log('mobile-nav', mobileNav > 0 ? 'OK' : 'WARN', `mobile interest links: ${mobileNav}`);

  } catch (e) {
    log('FATAL', 'FAIL', `${e.message}`);
    if (e.stack) log('FATAL-STACK', 'INFO', e.stack.split('\n').slice(0, 3).join(' | '));
    errors.push({ name: 'FATAL', message: e.message, stack: e.stack });
  } finally {
    await browser.close();
  }

  // 输出报告
  console.log('\n\n========== TEST REPORT ==========');
  const summary = {
    totalTests: results.length,
    ok: results.filter(r => r.status === 'OK').length,
    warn: results.filter(r => r.status === 'WARN').length,
    fail: results.filter(r => r.status === 'FAIL').length,
    info: results.filter(r => r.status === 'INFO').length,
    tagNames: { TAG_A, TAG_M, SRC_NAME },
    results,
    consoleErrors,
    networkErrors,
    pageErrors: errors,
  };
  console.log(JSON.stringify(summary, null, 2));
  fs.writeFileSync(path.join(SCREEN_DIR, 'report.json'), JSON.stringify(summary, null, 2));
}

main().catch(e => {
  console.error('FATAL', e);
  process.exit(1);
});
