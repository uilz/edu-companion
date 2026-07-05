# Task #34 — 导航按用户角色 / 订阅显示不同入口

> 任务 #45 更新：admin 后台入口已从主前端 navConfig 移除（admin 走独立 3001 项目）。
> 本文档保留历史设计记录，最新代码以任务 #45 提交为准。

## 背景

`navConfig` 之前是静态的，所有登录用户看到相同的 12 项入口。
实际产品规划里：
- **Pro 专属**入口（LiveKit 语言房间）：按房间分钟计费，需订阅档位控制
- **Admin 后台**：独立 Next.js 项目（端口 3001），主前端不再挂入口
- **guest / 学生** 不需要看到需要权限的入口
- 后端 `AuthUser.role` 有 `super_admin` / `admin` / `user` 三种值，但 admin 不再出现在主前端导航

## 设计决策

### 1. 类型抽象

```typescript
// 任务 #45：admin 已从此处移除
export type UserRole = "student" | "guest";
export type SubscriptionTier = "free" | "pro" | "enterprise";
```

- **UserRole**：业务层抽象，1 个真实角色 + 1 个"未登录"角色
- **SubscriptionTier**：当前后端未提供字段，统一默认 `free`，dev 模式可覆盖

### 2. NavItem 扩展字段

```typescript
interface NavItem {
  // ... 原字段保留
  requiredRoles?: UserRole[];     // 白名单；空 = 不限制
  requiredTiers?: SubscriptionTier[];  // 白名单；空 = 不限制
  badgePro?: boolean;              // Pro 徽章
  // 任务 #45：badgeAdmin 已删除（admin 入口从 navConfig 移除）
}
```

语义：**空数组 = 不限制**（默认放空保持向后兼容）

### 3. getNavItemsFor 接收 context

```typescript
export function getNavItemsFor(
  slot: keyof NavVisibility,
  context?: NavContext,  // 旧调用方式仍支持
): NavItem[]
```

不传 context 时不过滤 role/tier，向后兼容已有代码。

### 4. 过滤优先级

`isItemVisible(item, slot, ctx)`：
1. 槽位包含（`item.visibleIn[slot]`）
2. 角色匹配（`requiredRoles` 空 OR 包含 `userRole`）
3. 档位匹配（`requiredTiers` 空 OR 包含 `subscriptionTier`）

任一不满足则不显示。

### 5. 入口角色配置矩阵（任务 #45 后）

| 路径 | 标签 | 角色 | 档位 | 徽章 | sidebar | drawer | bottomNav | quickAction |
|------|------|------|------|------|---------|--------|-----------|-------------|
| /conversation | 学习空间 | 全部 | 全部 | - | ✓ | ✓ | ✓ | ✓ |
| /practice | 练习 | 全部 | 全部 | - | ✓ | ✓ | ✓ | ✓ |
| /project | 项目 | 全部 | 全部 | - | ✓ | ✓ | - | - |
| /knowledge-tree | 知识树 | 全部 | 全部 | - | ✓ | ✓ | - | ✓ |
| /secretary | 秘书 | 全部 | 全部 | - | ✓ | ✓ | - | - |
| /resources | 我的资源 | 全部 | 全部 | - | ✓ | ✓ | - | - |
| /analytics | 学情分析 | 全部 | 全部 | - | - | - | - | ✓ |
| /settings | 设置 | 全部 | 全部 | - | - | - | - | ✓ |
| /flashcard | 卡片复习 | 全部 | 全部 | - | ✓ | ✓ | ✓ | ✓ |
| /reading | 阅读 | 全部 | 全部 | - | ✓ | ✓ | ✓ | ✓ |
| **/liveroom** | **语言房间** | 全部 | **pro+** | **Pro** | ✓ | ✓ | - | - |
| /emotion | 心情压力 | 全部 | 全部 | - | ✓ | ✓ | - | - |
| /planning | 规划 | 全部 | 全部 | - | ✓ | ✓ | ✓ | ✓ |
| /interest | 兴趣探索 | 全部 | 全部 | - | ✓ | ✓ | ✓ | ✓ |

> **任务 #45**：原 /admin 行已删除。admin 后台改走独立项目（端口 3001）。

### 6. 角色配置矩阵（任务验收用，任务 #45 后）

| 入口 | student + free | student + pro | guest |
|------|----------------|---------------|-------|
| /conversation | ✓ | ✓ | ✓ |
| /practice | ✓ | ✓ | ✓ |
| /project | ✓ | ✓ | ✓ |
| /knowledge-tree | ✓ | ✓ | ✓ |
| /secretary | ✓ | ✓ | ✓ |
| /resources | ✓ | ✓ | ✓ |
| /analytics | ✓ | ✓ | ✓ |
| /settings | ✓ | ✓ | ✓ |
| /flashcard | ✓ | ✓ | ✓ |
| /reading | ✓ | ✓ | ✓ |
| **/liveroom** | **✗** | **✓** | **✗** |
| /emotion | ✓ | ✓ | ✓ |
| /planning | ✓ | ✓ | ✓ |
| /interest | ✓ | ✓ | ✓ |
| **sidebar 总数** | **11** | **12** | **11** |

> **注 1**：guest 列展示的是 navConfig 过滤后的可见项。`requiresAuth` 的拦截由 `AuthGuard` 负责 — 未登录用户被强制跳转到 /login，所以侧边栏实际上根本不会渲染给 guest。
> **注 2**：「admin 也要付钱」产品决策点已作废 — admin 不再出现在主前端。Liveroom 仅按 `requiredTiers` 过滤。
> **注 3**：主前端 UserRole 已从 3 档精简为 2 档（student / guest），admin 走独立项目。

## 实施清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `frontend/src/lib/navConfig.ts` | 重大扩展（#34） + 清理（#45） | 加 UserRole/SubscriptionTier/NavContext 类型，扩展 NavItem 字段，新增匹配辅助函数；#45 移除 admin 入口 / badgeAdmin / admin 角色 / Shield 重导出 |
| `frontend/src/hooks/useUser.ts` | 新增（#34） + 清理（#45） | 聚合 AuthUser + dev 模式 localStorage 覆盖；#45 简化 mapBackendRole 为永远返回 student |
| `frontend/src/components/layout/NavBadge.tsx` | 新增（#34） + 清理（#45） | Pro / Admin 徽章组件；#45 移除 admin 徽章分支 |
| `frontend/src/components/layout/DevRoleSwitcher.tsx` | 新增（#34） + 清理（#45） | dev 模式角色切换浮窗（生产构建不渲染）；#45 角色从 3 档减为 2 档（student / guest） |
| `frontend/src/components/layout/AppShell.tsx` | 小幅修改 | 挂载 DevRoleSwitcher |
| `frontend/src/components/layout/Sidebar.tsx` | 中等修改 | 调用 `getNavItemsFor('sidebar', navContext)` + 渲染 NavBadge |
| `frontend/src/components/layout/MobileDrawer.tsx` | 中等修改 | 同上 |
| `frontend/src/components/layout/BottomNav.tsx` | 中等修改 | 同上 |
| `frontend/src/components/dashboard/tabs/OverviewTab.tsx` | 中等修改 | `getQuickActions(ctx)` 移到组件内 useMemo |
| `frontend/src/app/page.tsx` | 中等修改 | 同上 |
| `frontend/src/lib/__tests__/navConfig-role.test.ts` | 新增（#34） + 更新（#45） | 单测覆盖所有角色/订阅档位组合；#45 删除 admin 相关测试，更新 sidebar 总数期望，新增 admin-已移除断言 |

## Dev 模式

右下角浮窗（仅 NODE_ENV !== "production" 时显示）：
- 显示真实身份 vs 当前生效
- 2 角色 × 3 档位 = 6 种组合一键切换（任务 #45：admin 已移除）
- 覆盖值存 localStorage (`edu-dev-role-override`)，跨标签页同步
- 一键"重置为真实身份"

## 验收测试

`src/lib/__tests__/navConfig-role.test.ts` 单元测试：
- matchesRole 边界
- matchesTier 边界
- isItemVisible 组合
- getNavItemsFor student+free / student+pro / guest
- getQuickActions 受限项过滤
- 向后兼容（不传 context）
- priority 排序保持
- 任务 #45：admin 入口已移除断言（路径不存在、badgeAdmin 字段不存在）

`npm run build` 通过。
`npx vitest frontend/src/lib/__tests__/navConfig-role.test.ts` 全过。

## 关键代码片段

### navConfig.ts 核心类型（任务 #45 后）

```typescript
export type UserRole = "student" | "guest";
export type SubscriptionTier = "free" | "pro" | "enterprise";

export interface NavContext {
  userRole: UserRole;
  subscriptionTier: SubscriptionTier;
}

export interface NavItem {
  // ... 原字段
  requiredRoles?: UserRole[];
  requiredTiers?: SubscriptionTier[];
  badgePro?: boolean;
  // badgeAdmin 已删除
}

export function isItemVisible(
  item: NavItem,
  slot: keyof NavVisibility,
  ctx: NavContext,
): boolean {
  if (!item.visibleIn[slot]) return false;
  if (!matchesRole(item, ctx.userRole)) return false;
  if (!matchesTier(item, ctx.subscriptionTier)) return false;
  return true;
}
```

### useUser.ts 核心逻辑（任务 #45 后）

```typescript
// 任务 #45：admin 已从主前端 navConfig 移除，所有已登录用户都映射为 student。
// 后端 role 字段（super_admin / admin / user）保留在 user.role 上，前端如需
// 展示"超级管理员/管理员/用户"标签可读 user.role 自行判断。
function mapBackendRole(_backendRole: string | undefined | null): UserRole {
  return "student";
}

export function useUser(): UseUserResult {
  const { user } = useAuth();
  // ...
  const realUserRole: UserRole = user ? mapBackendRole(user.role) : "guest";
  const realTier: SubscriptionTier = "free";
  return {
    userRole: devOverride?.userRole ?? realUserRole,
    subscriptionTier: devOverride?.subscriptionTier ?? realTier,
    // ...
  };
}
```

### Sidebar 消费

```typescript
const { navContext } = useUser();
const navItems = useMemo<ReturnType<typeof getNavItemsFor>>(
  () => getNavItemsFor('sidebar', navContext as NavContext),
  [navContext],
);
```

## 已知问题 / 后续工作

1. **后端订阅字段缺失**：当前所有用户实际 tier = free。要让 Pro 功能真正生效，需：
   - 后端 `AuthUser` 加 `subscription_tier` 字段
   - 前端 `useUser` 把 `realTier` 从 `fetchCurrentUser()` 读出来
   - 现状：dev 模式可模拟，但生产环境所有人都看不到 Pro 入口（这是设计意图）
2. **admin 入口已迁移到独立项目**（任务 #45）：/home/deploy/edu-companion/admin/（端口 3001），主前端不再混挂 admin 链接。原 /admin 路径保持空目录占位（不创建页面），如需清理可后续删除 `frontend/src/app/admin/`。
3. **订阅付费墙**：当前是隐藏入口策略（不展示），不是"展示但锁住"。未来如需"展示+锁+升级弹窗"，需要把 navConfig 扩展为"返回带锁定状态的项"。

## 相关文档

- 任务 #30：navConfig 单一源改造
- 任务 #31：6 个新模块入口补齐
- 任务 #37：tool dataclass 合并（与本任务正交）
- 任务 #45：从主前端 navConfig 移除 admin 入口（admin 走独立 3001 项目）
