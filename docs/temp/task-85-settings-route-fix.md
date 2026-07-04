# Settings 路由修复 (task-#85)

## 背景
TopBar 用户菜单的"账户"链接写死为 `/settings/account`，但该路由不存在（HTTP 404），
点击后落到 not-found 页（用户报告"账户点开没有页面"）。

## 根因
- `frontend/src/app/settings/page.tsx` 是单文件 1325 行设计，8 个 tab 全部装在内部 state
- TopBar 链接却按"路由化"的预期去 link `/settings/account`
- 这是单页状态与路由化链接之间的设计脱节

## 设计决策
原 3 个候选方案：
1. **独立账户页 + AccountTab 抽组件** — 简单，但 settings 其他 7 个 tab 仍单文件，重复模式
2. **Settings 改用 `?tab=account` URL 参数** (选用) — 单一真相源、URL 可分享、改动小
3. **Settings 拆 `/settings/[tab]`** — 最 Next.js 范儿，但要拆 8 份文件，scope 太大

**选 B 的核心理由**：
- 单一组件，单一真相源
- 改 1 个文件（settings page）+ 1 个 href（TopBar）
- 后续如果需要 SEO/路由级 deep link，可平滑迁移到 C，不需要重写业务逻辑

## 实现要点

### 派生式 state 避免 race condition
第一版用 `useState<TabKey>` + useEffect 同步 URL，发现 race：
- `setActiveTab("account")` 触发 render 时 `searchParams` 还未更新（router.replace 是异步）
- useEffect 拿到的是旧 `?tab=llm`，把 activeTab 又拉回 "llm"
- 用户表现：从 LLM tab 点回 Account，URL 变成 `/settings` 但内容仍是 LLM

**最终方案**：完全不用 useState 存 activeTab，直接从 searchParams 派生。
URL 是唯一真相源，无 state 缓存 → 无 race。

```tsx
const tabFromUrl = searchParams.get("tab");
const activeTab: TabKey = isValidTab(tabFromUrl) ? tabFromUrl : "account";

const switchTab = useCallback((tab: TabKey) => {
  // 只更新 URL，state 自动从 URL 派生
  router.replace(tab === "account" ? "/settings" : `/settings?tab=${tab}`, { scroll: false });
}, [router]);
```

### Suspense 包裹
`useSearchParams` 在 client component 中需要 Suspense 边界，否则 build 报错。
将 SettingsPage 拆为外层 wrapper（带 Suspense fallback）和内层 SettingsContent（用 hook）。

### URL 清理
`account` 是默认 tab，URL 上不加 `?tab=account`（保持干净）。
其他 tab 都带 `?tab=xxx` 便于 deep link。

## 改动文件
- `frontend/src/app/settings/page.tsx` — 拆 SettingsPage / SettingsContent，派生 activeTab
- `frontend/src/components/layout/TopBar.tsx` — 链接 `/settings/account` → `/settings?tab=account`

## 验证
1. `?tab=account` 直接访问 → 账户信息 ✓
2. `?tab=llm` 直接访问 → LLM 配置 ✓
3. `/settings` 直接访问 → 默认账户信息 ✓
4. 任意 tab 互相切换 → URL 与内容同步 ✓
5. 浏览器后退/前进 → 内容跟着 URL 走 ✓
6. TopBar → 账户 → 落到 `/settings?tab=account` + 账户信息 ✓

## 后续可考虑的优化（未做）
- 把 settings 整体拆为 `/settings/[tab]` 路由（task candidate）
- 8 个 tab 全部支持 deep link（已实现）
- 各 tab 表单状态保留（切换 tab 不丢正在编辑的草稿，目前直接重渲染）
