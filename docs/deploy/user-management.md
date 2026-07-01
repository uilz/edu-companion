# 用户管理 — VM 终端运维手册

## 一键脚本（推荐）

```bash
# 直接运行交互式菜单，无需手动拼 curl 命令
sudo -u deploy bash /home/deploy/edu-companion/scripts/manage-users.sh
```

脚本功能：
- 列出/搜索用户、创建用户、重置密码、改角色、封禁/解封、踢下线、删除用户
- 自动从 `.env` 读取数据库密码，直接操作数据库
- 首次部署选 **9) 创建/重置超级管理员** 即可

## 系统说明

- **所有用户**存在 PostgreSQL `edu_companion` 数据库的 `users` 表中
- auth-gateway (18001) 和 admin-backend (8001) 共用同一张表，不区分两套用户
- 建议通过 **admin API (curl)** 执行日常操作，紧急情况用 **psql**

## 前提

```bash
# 获取 super_admin JWT（替换 admin 密码）
ADMIN_TOKEN=$(curl -s -X POST http://localhost:18001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"你的密码"}' | python3 -c \
  "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

## 查找用户

```bash
# 所有用户（分页）
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8001/api/admin/users?page=1&page_size=20" | python3 -m json.tool

# 搜索（模糊匹配用户名/邮箱/显示名）
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8001/api/admin/users?q=关键词" | python3 -m json.tool

# 查看单个用户详情
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8001/api/admin/users/u_user_id_here | python3 -m json.tool
```

## 创建用户

> **安全**：`username` 有 UNIQUE 约束。如果用户名已存在，API 会返回错误，**不会**覆盖或影响已有用户。
> 不确定系统是否有用户时直接执行即可，不会破坏现有数据。

```bash
# 创建普通用户
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"newuser","password":"Hello123","email":"new@example.com","display_name":"新用户","role":"user"}' \
  http://localhost:8001/api/admin/users/create | python3 -m json.tool

# 创建管理员
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin2","password":"StrongP@ss1","email":"admin2@example.com","display_name":"管理员","role":"super_admin"}' \
  http://localhost:8001/api/admin/users/create | python3 -m json.tool
```

## 修改密码

```bash
# 重置指定用户的密码
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"new_password":"NewP@ss123"}' \
  http://localhost:8001/api/admin/users/u_user_id_here/reset-pwd

# 检查结果
echo $?
```

## 修改角色

```bash
# 改为分析员
curl -s -X PATCH -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role":"analyst"}' \
  http://localhost:8001/api/admin/users/u_user_id_here | python3 -m json.tool

# 角色可选值: user, analyst, data_admin, super_admin
```

## 封禁 / 解封

```bash
# 封禁（用户无法登录）
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8001/api/admin/users/u_user_id_here/ban

# 解封
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8001/api/admin/users/u_user_id_here/unban
```

## 强制踢下线

```bash
# 递增 token_version，该用户所有设备需重新登录
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8001/api/admin/users/u_user_id_here/force-logout
```

## 删除用户

```bash
# 不可恢复！会级联删除关联数据
curl -s -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8001/api/admin/users/u_user_id_here
```

## 批量操作

```bash
# 批量改角色
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"user_ids":["u_id1","u_id2"],"role":"analyst"}' \
  http://localhost:8001/api/admin/users/bulk/role

# 批量封禁
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"user_ids":["u_id1","u_id2"]}' \
  http://localhost:8001/api/admin/users/bulk/ban

# 批量删除（不可恢复）
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"user_ids":["u_id1","u_id2"]}' \
  http://localhost:8001/api/admin/users/bulk/delete
```

## 查看登录历史 / 在线用户

```bash
# 指定用户的登录设备历史
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8001/api/admin/users/u_user_id_here/login-log | python3 -m json.tool

# 当前在线用户列表
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8001/api/admin/users/online/list | python3 -m json.tool
```

---

# psql 紧急操作

> 当 admin 服务不可用时，直接操作数据库。

```bash
psql -h 127.0.0.1 -U companion -d edu_companion
```

## 查找用户

```sql
-- 全部用户
SELECT id, username, email, role, is_active, last_login, created_at
FROM users ORDER BY created_at DESC;

-- 模糊搜索
SELECT id, username, email, display_name, role
FROM users
WHERE username ILIKE '%关键词%' OR email ILIKE '%关键词%';
```

## 创建第一个超级管理员

项目没有种子脚本。部署后首次操作：

```bash
# 1) 用 Python 生成 bcrypt 哈希
python3 -c "
import bcrypt, hashlib, time
pw = bcrypt.hashpw(b'YourAdminP@ss123', bcrypt.gensalt()).decode()
uid = 'u_' + hashlib.md5(f'admin{time.time()}'.encode()).hexdigest()[:12]
print(f'ID: {uid}')
print(f'HASH: {pw}')
"

# 2) 用 psql 插入
psql -h 127.0.0.1 -U companion -d edu_companion -c "
INSERT INTO users (id, username, email, password_hash, display_name, role)
VALUES ('u_xxx...', 'admin', 'admin@example.com', '上面生成的哈希', '超级管理员', 'super_admin');
"
```

## 修改密码 (psql)

```bash
# 在 shell 中用 Python 生成哈希，直接传给 psql
python3 -c "
import bcrypt
h = bcrypt.hashpw(b'NewP@ss123', bcrypt.gensalt()).decode()
print(h)
" | xargs -I{} psql -h 127.0.0.1 -U companion -d edu_companion -c \
  "UPDATE users SET password_hash='{}', updated_at=NOW() WHERE id='u_user_id_here';"
```

或分两步：

```sql
-- 先在 shell 中生成
python3 -c "import bcrypt; print(bcrypt.hashpw(b'NewP@ss123', bcrypt.gensalt()).decode())"

-- 再在 psql 中执行
UPDATE users SET password_hash='上面输出的哈希', updated_at=NOW() WHERE id='u_user_id_here';
```

## 修改角色 (psql)

```sql
UPDATE users SET role='super_admin', updated_at=NOW() WHERE id='u_user_id_here';
```

## 封禁 / 解封 (psql)

```sql
UPDATE users SET is_active=false, updated_at=NOW() WHERE id='u_user_id_here';
UPDATE users SET is_active=true,  updated_at=NOW() WHERE id='u_user_id_here';
```

## 删除用户 (psql)

删除用户前需清理关联数据：

```sql
BEGIN;
DELETE FROM login_events          WHERE user_id='u_user_id_here';
DELETE FROM practice_attempts     WHERE user_id='u_user_id_here';
DELETE FROM practice_sessions     WHERE user_id='u_user_id_here';
DELETE FROM conversation_user_meta WHERE user_id='u_user_id_here';
DELETE FROM knowledge_nodes       WHERE user_id='u_user_id_here';
DELETE FROM events                WHERE user_id='u_user_id_here';
DELETE FROM users                 WHERE id='u_user_id_here';
COMMIT;
```

---

# 常见问题

### Q: 不知道 admin 密码怎么办？

```bash
# 直接改数据库
python3 -c "import bcrypt; print(bcrypt.hashpw(b'NewAdminP@ss123', bcrypt.gensalt()).decode())"
# 复制输出的哈希
psql -h 127.0.0.1 -U companion -d edu_companion -c \
  "UPDATE users SET password_hash='粘贴哈希', updated_at=NOW() WHERE role='super_admin';"
```

### Q: admin 不好使，admin API 返回 401？

- 检查 `JWT_SECRET` 是否一致（`backend/config/.env` 和 `auth-gateway/config/.env`）
- 检查用户 `role` 是否为 `super_admin`
- 检查 token 是否过期（重新登录获取新 token）

### Q: 数据库连接信息？

- Host: `127.0.0.1`
- Port: `5432`
- User: `companion`
- DB: `edu_companion`
- 密码: 在 `backend/config/.env` 中 `DB_PASSWORD=...`
