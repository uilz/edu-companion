# Task #75 — 撤销 liveroom Pro 档位过滤

## 背景

Task #34 引入了 `requiredTiers: ["pro", "enterprise"]` 给 liveroom 入口。
这是过度设计：

- 用户从来没要求过"Pro 档位"机制
- 后端 `AuthUser` 没有 `subscriptionTier` 字段；前端硬编码 `"free"`
- e2e_admin（后端 `role=user`）登录后看不到 liveroom 入口
- 6 个 liveroom 页面全都 200，但导航上找不到入口

正确做法：liveroom 恢复为"所有已登录用户可见"。

## 改动清单

### 1. `frontend/src/lib/navConfig.ts`

**liveroom 配置**：删除 `requiredTiers: ["pro", "enterprise"]` 和 `badgePro: true`。

```diff
-  // ── 任务 #34：liveroom 改为 Pro 专属 ──
-  // LiveKit 实时音视频服务是按房间分钟计费的，按订阅档位限制可见性。
-  // 免费用户看不到入口；Pro / Enterprise 可见。
   {
     path: "/liveroom",
     label: "语言房间",
     mobileLabel: "语言",
     icon: Mic,
     priority: 11,
     requiresAuth: true,
-    // Pro 档位才看得到
-    requiredTiers: ["pro", "enterprise"],
-    badgePro: true,
     // 语言房间使用频率相对低，桌面 + 平板抽屉 + 首页四宫格；移动 BottomNav 不放
     visibleIn: { sidebar: true, drawer: true, bottomNav: false, quickAction: false },
   },
```

**`isItemVisible` 函数**：增加 `requiresAuth` 检查。

```diff
 export function isItemVisible(
   item: NavItem,
   slot: keyof NavVisibility,
   ctx: NavContext,
 ): boolean {
   if (!item.visibleIn[slot]) return false;
+  if (item.requiresAuth && ctx.userRole === "guest") return false;
   if (!matchesRole(item, ctx.userRole)) return false;
   if (!matchesTier(item, ctx.subscriptionTier)) return false;
   return true;
 }
```

> 任务 #75 把 `requiresAuth` 收口到 navConfig，让"guest 看不到 liveroom"
> 可在单测中直接断言（之前只能依赖 AuthGuard 在更外层跳转）。
> 当 `context` 不传时（向后兼容旧调用方），跳过 requiresAuth 检查。

### 2. `frontend/src/hooks/useUser.ts`

`realTier` 硬编码 `"free"`，dev 模式可覆盖。已为最新状态，仅补充注释。

```ts
// 任务 #75：realTier 硬编码 free。
// 后端目前没有 subscriptionTier 字段；统一默认 free。dev 模式可覆盖。
const realUserRole: UserRole = user ? mapBackendRole(user.role) : "guest";
const realTier: SubscriptionTier = "free";
```

### 3. `frontend/src/lib/__tests__/navConfig-role.test.ts`

更新所有 liveroom 相关测试：

- `student+free` 现在能看到 liveroom
- `student+pro` 保留（也看到）
- `guest`（未登录）看不到 liveroom（isItemVisible 在 guest 上下文下拦截）
- 断言 liveroom 数据字段 `requiredTiers` 和 `badgePro` 为 `undefined`

## 验证

1. `npx vitest run src/lib/__tests__/navConfig-role.test.ts`：15 个测试全部通过
2. `bash rebuild.sh --skip-admin` 重启前后端
3. 浏览器登录 e2e_admin：侧栏 12 项入口 + /liveroom 可见
4. /liveroom 6 个页面 200 + 0 console error

## 设计原则

> 任务 #34 引入的 Pro 档位机制是过度设计 — 后端没有对应字段，
> 前端硬编码 `"free"` 本身就是在假装有档位。撤销后保持代码诚实。
