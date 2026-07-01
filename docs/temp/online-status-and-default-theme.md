# 在线状态重设计 + 系统默认浅色主题

> 临时设计文档。实施完成后迁移到 `docs/architecture/overview.md` 与 `backend/docs/CONTEXT.md`。

---

## 1. 现状问题

| # | 现象 | 根因 |
|---|------|------|
| 1 | `/users` 列表没有"在线"列 | `UserRow` 没返回 `is_online` 字段；前端表格也没列 |
| 2 | 详情里"在线"判定错误 | `get_user_online_status` 用 `login_events.created_at`，15 分钟后永远离线 |
| 3 | `last_active_at` 字段存在但从不更新 | 只有登录那一刻被写一次，没有任何中间件在每次请求时刷新 |
| 4 | `/api/admin/users/online/list` 永远 0 | 调用 `le_repo.get_online_users/get_all_online_count()`，方法不存在 |
| 5 | 架构文档与代码不一致 | 文档说"5 分钟节流、30 分钟阈值"，代码是"无节流、15 分钟阈值" |
| 6 | admin 是硬编码深色主题 | 没有主题切换，色值直接写死在 `tailwind.config.js` |
| 7 | 前端（Next.js）默认深色 | `ThemeContext.DEFAULT_THEME = 'dark'` |
| 8 | **修复后又新发现：时区 bug** | `_is_online` 用 `datetime.utcnow()` 与 DB 的 CST `NOW()` 比较，导致 0~8 小时内的活跃时间被误判为在线（Python 中负 delta < 30min 为 True） |

---

## 2. 目标

1. **在线状态基于 `users.last_active_at`**，单一数据源
2. **中间件每次认证请求都尝试刷新** `last_active_at`，5 分钟节流（DB 内判断，避免每次都写）
3. **30 分钟内活跃 = 在线**（与架构文档对齐）
4. **`/users` 列表直接显示在线/离线 badge**，可按"在线"过滤
5. **列表页 30 秒自动轮询**，状态实时变化
6. **前端 + admin 都默认浅色**，保留暗色切换

---

## 3. 后端变更

### 3.1 仓储层 — `backend/app/infrastructure/db/auth_repository.py`

在 `UserRepository`（或现有 `AuthRepository`）中：

```python
# 5 分钟节流更新 last_active_at
def touch_last_active(self, user_id: str, throttle_sec: int = 300) -> None:
    """仅当 last_active_at 距今 > throttle_sec 时才更新（DB 内 NOW() 计算）"""
    self._db.execute(
        "UPDATE users SET last_active_at = NOW() "
        "WHERE id = %s AND (last_active_at IS NULL "
        "  OR last_active_at < NOW() - (%s || ' seconds')::interval)",
        (user_id, throttle_sec),
    )
```

`LoginEventRepo.get_user_online_status` 改为：

```python
def get_user_online_status(self, user_id: str) -> dict:
    row = self._db.fetchone(
        "SELECT last_active_at FROM users WHERE id = %s", (user_id,),
    )
    last = row["last_active_at"] if row else None
    online = False
    if last:
        # 关键：用 datetime.now() 与 DB CST 墙钟对齐，禁止用 utcnow()
        online = (datetime.now() - last) < timedelta(minutes=30)
    return {"online": online, "last_seen": last.isoformat() if last else None}
```

新增：

```python
def get_online_users(self, limit: int = 50) -> list[dict]:
    return self._db.fetchall(
        """SELECT u.id, u.username, u.display_name, u.role, u.last_active_at
           FROM users u
           WHERE u.last_active_at > NOW() - INTERVAL '30 minutes'
           ORDER BY u.last_active_at DESC LIMIT %s""",
        (limit,),
    )

def get_all_online_count(self) -> int:
    row = self._db.fetchone(
        "SELECT COUNT(*) AS c FROM users "
        "WHERE last_active_at > NOW() - INTERVAL '30 minutes'"
    )
    return int(row["c"]) if row else 0
```

### 3.2 中间件 — `backend/app/domain/auth/middleware.py`

`AuthMiddleware.__call__` 验证通过后，拿到 `user_id`，**fire-and-forget** 调度一次 `touch_last_active`：

```python
# 验证通过后
scope["state"]["user_id"] = user["user_id"]
# 异步触发活跃时间刷新（不阻塞请求；同一 user 5 分钟内最多一次）
asyncio.create_task(_touch_active(user["user_id"]))
```

`_touch_active` 是一个 module-level 协程，包一层 try/except 防止 DB 异常影响请求。考虑到高频请求，用 `asyncio.create_task` 而非 `BackgroundTasks`，避免污染响应体。

`AdminAuthMiddleware`（`backend/app_admin/deps.py`）做相同处理。

### 3.3 admin 路由 — `backend/app_admin/routers/users.py`

- `UserRow` 加 `is_online: bool` 字段
- `list_users` 的 SELECT 增加 `last_active_at`，模型里 `is_online = (now - last_active_at) < 30min`
- 补齐 `le_repo.get_online_users / get_all_online_count` 调用（已迁移到仓储）
- `/api/admin/users/online/list` 真正可用

---

## 4. 前端（admin）变更

### 4.1 主题切换

admin 之前是硬编码深色（无切换），改为与 frontend 对齐：
- `tailwind.config.js` 所有颜色 → `var(--color-*)`
- `globals.css` 定义 `[data-theme="light"]` / `[data-theme="dark"]` 两套变量
- `layout.tsx` 注入 `<html data-theme="light">` + ThemeProvider
- Topbar 加切换按钮
- 默认 `light`

### 4.2 用户列表

- `UserRow` 类型加 `is_online: boolean`
- 表格新增"在线"列（在"角色"和"状态"之间），badge 样式与现有 `is_active` 一致
- 工具栏新增"在线/离线"过滤器
- `useEffect` 注册 `setInterval(load, 30_000)`，卸载时 clear
- 切换过滤/搜索时立即 refetch，重置 interval

---

## 5. 前端（Next.js）变更

`frontend/src/contexts/ThemeContext.tsx`：
```diff
- const DEFAULT_THEME: Theme = 'dark';
+ const DEFAULT_THEME: Theme = 'light';
```

其余不变（保留 localStorage 优先、保留切换能力）。

---

## 6. 文档同步

- `docs/architecture/overview.md` 第四节"登录事件追踪"表 → 增加 last_active_at 说明；明确"30 分钟内活跃 = 在线"
- `backend/docs/CONTEXT.md` Online Status 段 → 与实现对齐
- 本临时文档完成后归档到 `docs/architecture/online-status.md`（或并入 overview.md）

---

## 7. 测试计划

- 真实登录用户后访问 `/users` → 该用户显示绿色"在线"
- 等待 35 分钟无活动 → 应自动变"离线"
- 切换过滤器"仅在线" → 只显示在线用户
- 浏览器 devtools 观察 30s 后是否触发 `/users` 请求
- admin 主题切换按钮可切深浅，刷新后保留选择
- Next.js 前端首屏默认浅色（清 localStorage 后）

---

## 8. 时区一致性约束（新增）

**现状：DB 列 `timestamp without time zone`，NOW() 返回 CST 墙钟；Python 进程也在 CST。**

| 场景 | 正确做法 | 错误做法 |
|------|----------|----------|
| 写入 `last_active_at` | `NOW()` 或 `datetime.now()` | ❌ `datetime.utcnow()` |
| 读取并比较 | `datetime.now()` | ❌ `datetime.utcnow()` |

**未来若要彻底消除时区耦合**：将 `users.last_active_at` 改为 `TIMESTAMPTZ`，存 UTC，Python 统一用 `datetime.now(timezone.utc)` 比较。本次仅做最小修复（`utcnow` → `now`），不迁移列类型。
