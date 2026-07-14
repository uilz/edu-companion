# 苹果果学习助手 · Cloudflare 生产部署

> 本文档说明如何将 edu-companion 通过 Cloudflare Tunnel 部署到公网，
> 实现零暴露端口的安全外网访问。

---

## 架构概览

```
用户 ──→ https://gapple.bond ──→ Cloudflare Edge
                                      │
                              Cloudflare Tunnel (cloudflared)
                                      │
                              VM (192.168.13.134)
                              ├─ Nginx :8080（反向代理/统一网关）
                              ├─ 主站前端 :3000（Next.js）
                              ├─ 后端 API :8000（FastAPI）
                              ├─ 认证网关 :18001（独立鉴权服务）
                              ├─ Admin 前端 :3001（独立管理后台）
                              └─ Admin 后端 :8001（独立管理API）
```

### 域名路由

| 域名 | 目标服务 | 端口 |
|------|---------|------|
| `gapple.bond` | 主站前端 (Next.js) | `:3000` |
| `api.gapple.bond` | 后端 API | `:8000` |
| `auth.gapple.bond` | 认证网关 | `:18001` |

### 内部请求流

```
浏览器 → gapple.bond/login
  → Cloudflare Tunnel → localhost:3000 (Next.js)
  → Next.js rewrite /api/auth/* → localhost:8080 (Nginx)
  → Nginx /api/auth/ → authgw (:18001)
  → Nginx /api/* → backend (:8000)
  → Nginx / → nextjs (:3000)
```

---

## 一、前置条件

| 条件 | 说明 |
|------|------|
| 域名 | 已托管在 Cloudflare（如 `gapple.bond`） |
| VM | 一台能出网的服务器（任意架构） |
| 项目 | 已在 VM 上通过 `init.sh` 完成初始化 |

---

## 二、安装 cloudflared

```bash
# 下载安装（已装可跳过）
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb

# 验证
cloudflared version
```

> 当前服务器 cloudflared 位置：`/home/deploy/bin/cloudflared`
> 运行协议：`--protocol quic`

---

## 三、登录并创建 Tunnel

```bash
# 登录 Cloudflare 账号
cloudflared tunnel login
```
会打开浏览器，选择你的域名（如 `gapple.bond`），授权后令牌自动保存。

```bash
# 创建 Tunnel
cloudflared tunnel create edu-companion
```
记录生成的 Tunnel ID（如 `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`）。

---

## 四、配置 DNS 路由

```bash
# 绑定子域名到 Tunnel
cloudflared tunnel route dns edu-companion gapple.bond
cloudflared tunnel route dns edu-companion api.gapple.bond
cloudflared tunnel route dns edu-companion auth.gapple.bond
```

或者在 Cloudflare Dashboard → DNS 手动添加 CNAME 记录：
| 类型 | 名称 | 目标 |
|------|------|------|
| CNAME | `@` | `tunnel-id.cfargotunnel.com` |
| CNAME | `api` | `tunnel-id.cfargotunnel.com` |
| CNAME | `auth` | `tunnel-id.cfargotunnel.com` |

---

## 五、配置文件

当前实际配置 `~/.cloudflared/config.yml`：

```yaml
tunnel: 6fb501f6-dc13-447d-ac0f-5ac8fa2ad686
credentials-file: /home/deploy/.cloudflared/6fb501f6-dc13-447d-ac0f-5ac8fa2ad686.json

ingress:
  # → 主站前端（Next.js :3000）
  # 注意：gapple.bond 走 :3000 而非 :8080，
  # 因为前端需要处理页面路由/rewrite，Nginx 8080 是 API 网关
  - hostname: gapple.bond
    service: http://localhost:3000

  # → 后端 API
  - hostname: api.gapple.bond
    service: http://localhost:8000

  # → 认证网关
  - hostname: auth.gapple.bond
    service: http://localhost:18001

  # 兜底：404
  - service: http_status:404
```

---

## 六、启动 Tunnel

```bash
# 前台启动（测试）
/home/deploy/bin/cloudflared tunnel run --protocol quic

# 后台启动（生产，使用自定义路径）
nohup /home/deploy/bin/cloudflared tunnel run --protocol quic > ~/cloudflared.log 2>&1 &

# 查看日志
tail -f ~/cloudflared.log
```

看到 `Registered tunnel connection` 和 `Connection xxxxxx registered` 表示连接成功。

---

## 七、Turnstile 人机验证

### 架构

Turnstile 分两层：

```
前端登录页（Turnstile 组件渲染）         后端 auth-gateway（Turnstile token 验证）
  ├─ NEXT_PUBLIC_TURNSTILE_SITE_KEY        ├─ TURNSTILE_SECRET_KEY
  ├─ 渲染 captcha widget                   ├─ 验证 token
  ├─ 提交时携带 turnstile_token            ├─ 验证失败拒绝请求
  └─ frontend/config/.env                  └─ auth-gateway/config/.env
```

### 开启人机验证

1. **后端**：取消注释 `auth-gateway/config/.env` 中的 `TURNSTILE_SECRET_KEY`
2. **前端**：取消注释 `frontend/config/.env` 中的 `NEXT_PUBLIC_TURNSTILE_SITE_KEY`
3. **重建前端**：`bash rebuild.sh`（Next.js 在 build 时注入环境变量到 JS 包）
4. **重启 auth-gateway**：
   ```bash
   kill $(cat /home/deploy/edu-companion/logs/auth_gateway.pid)
   cd /home/deploy/edu-companion/auth-gateway
   nohup ../backend/venv/bin/python -m uvicorn auth_app.main:app --host 0.0.0.0 --port 18001 > /dev/null 2>&1 &
   ```

### 关闭人机验证

1. **后端**：注释 `auth-gateway/config/.env` 中的 `TURNSTILE_SECRET_KEY` 行
   ```bash
   sed -i '/^TURNSTILE_SECRET_KEY=/s/^/#/' /home/deploy/edu-companion/auth-gateway/config/.env
   ```
2. **前端**：注释 `frontend/config/.env` 中的 `NEXT_PUBLIC_TURNSTILE_SITE_KEY` 行
   ```bash
   sed -i '/^NEXT_PUBLIC_TURNSTILE_SITE_KEY=/s/^/#/' /home/deploy/edu-companion/frontend/config/.env
   ```
3. **重建前端 + 重启服务**：
   ```bash
   cd /home/deploy/edu-companion/frontend
   rm -rf .next && npm run build
   fuser -k 3000/tcp
   export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
   nohup npx next start -p 3000 > /home/deploy/edu-companion/logs/frontend_new.log 2>&1 &
   kill $(cat /home/deploy/edu-companion/logs/auth_gateway.pid)
   cd /home/deploy/edu-companion/auth-gateway
   nohup ../backend/venv/bin/python -m uvicorn auth_app.main:app --host 0.0.0.0 --port 18001 > /dev/null 2>&1 &
   ```

### 冷却系统

auth-gateway 内置攻击冷却（纯内存，重启后重置）：

| 条件 | 后果 |
|------|------|
| 1分钟内登录失败 ≥5次 | Level 1 → 强制 Turnstile 验证 |
| Level 1 期间继续攻击 ≥3次 | Level 2 → IP 临时封禁 30 分钟 |
| 1分钟内登录失败 ≥15次 | 直升 Level 2（IP 封禁） |

清除冷却：重启 auth-gateway 即可。

---

## 八、验证部署

```bash
# 等 DNS 生效（1~5 分钟）
curl -s -o /dev/null -w "%{http_code}" https://gapple.bond
# 期望：200

curl -s -o /dev/null -w "%{http_code}" https://api.gapple.bond/health
# 期望：200

# 查看 Tunnel 连接状态
/home/deploy/bin/cloudflared tunnel list
/home/deploy/bin/cloudflared tunnel info edu-companion
```

---

## 九、日常运维

### 更新代码 + 重启

```bash
cd /home/deploy/edu-companion
git pull
bash rebuild.sh
```

### 快速重启（不构建前端）

```bash
bash rebuild.sh --skip-build
```

### 单独启动 admin 前端

```bash
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
cd /home/deploy/edu-companion/admin
nohup npx next start -p 3001 -H 0.0.0.0 > /home/deploy/edu-companion/logs/admin_frontend.log 2>&1 &
```

### 查看服务状态

```bash
ps aux | grep -E 'uvicorn|next|nginx|cloudflared'
ss -tlnp | grep -E '3000|3001|8000|8001|8080|18001|80'
```

### 查看日志

```bash
tail -f /home/deploy/edu-companion/logs/*.log
```

---

## 十、故障排查

| 问题 | 可能原因 | 解决 |
|------|---------|------|
| Tunnel 连不上 | cloudflared 未登录 | `cloudflared tunnel login` |
| DNS 不生效 | 缓存未更新 | 等 5 分钟或 `curl -H 'accept: application/dns-json'` 验证 |
| 502 Bad Gateway | 本地服务未启动 | `bash rebuild.sh` |
| 连接被拒绝 | Nginx 没启动 | 检查 `ps aux \| grep nginx` |
| 登录 401 (Unauthorized) | 密码错误 / Turnstile 拦截 | 先测 API：`curl https://gapple.bond/api/auth/login -X POST -d '{"username":"admin","password":"..."}'` |
| 登录页面一直转圈 | 前端 build 版本与 API 不匹配 | `bash rebuild.sh` |
| admin 前端 3001 无法启动 | nvm 未加载 / node 版本不对 | `export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 22` 后再启动 |

### 快速登录验证

```bash
# 直接调 auth-gateway（绕过所有代理）
curl -s http://localhost:18001/api/auth/login -X POST -H 'Content-Type: application/json' -d '{"username":"admin","password":"123456"}'

# 通过 Nginx 网关
curl -s http://localhost:8080/api/auth/login -X POST -H 'Content-Type: application/json' -d '{"username":"admin","password":"123456"}'

# 通过公网域名
curl -s https://gapple.bond/api/auth/login -X POST -H 'Content-Type: application/json' -d '{"username":"admin","password":"123456"}'
```

### 数据库用户管理

查看所有用户：
```bash
PGPASSWORD=companion123 psql -h 127.0.0.1 -p 5433 -U companion -d edu_companion -c "SELECT username, role, password_hash FROM users;"
```

重置密码：
```bash
cd /home/deploy/edu-companion/backend
../backend/venv/bin/python3.11 << 'PYEOF'
import bcrypt
from psycopg2 import connect
conn = connect(host='127.0.0.1', port=5433, dbname='edu_companion',
               user='companion', password='companion123')
cur = conn.cursor()
pw = bcrypt.hashpw(b'新密码', bcrypt.gensalt()).decode()
cur.execute("UPDATE users SET password_hash = %s WHERE username = 'admin'", (pw,))
conn.commit()
print('OK')
PYEOF
```

---

## 十一、完整部署流程（速查）

```bash
# 1. 初始化环境（首次）
cd /home/deploy/edu-companion
bash init.sh
# 编辑 backend/config/.env 填入 OPENAI_API_KEY

# 2. 构建并启动
bash rebuild.sh

# 3. 安装 cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb

# 4. 登录 Cloudflare
cloudflared tunnel login

# 5. 创建并配置 Tunnel
cloudflared tunnel create edu-companion
cloudflared tunnel route dns edu-companion gapple.bond
cloudflared tunnel route dns edu-companion api.gapple.bond
cloudflared tunnel route dns edu-companion auth.gapple.bond

# 6. 创建 ~/.cloudflared/config.yml（见第五节）

# 7. 启动 Tunnel
nohup /home/deploy/bin/cloudflared tunnel run --protocol quic > ~/cloudflared.log 2>&1 &

# 8. 验证
curl https://gapple.bond
```
