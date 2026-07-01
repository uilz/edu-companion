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
                              ├─ Nginx :8080（反向代理）
                              ├─ 前端 :3000（Next.js）
                              ├─ 后端 :8000（FastAPI）
                              └─ 认证网关 :18001
```

- **Cloudflare Tunnel** 建立一条从 Cloudflare Edge → VM 的加密隧道
- VM 不需要开任何公网端口（80/443 都关），只需 cloudflared 能出站即可
- 所有 HTTPS 证书由 Cloudflare 自动管理，无需 Let's Encrypt

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
# 下载安装
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb

# 验证
cloudflared version
```

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

创建 `~/.cloudflared/config.yml`：

```yaml
tunnel: edu-companion
credentials-file: /home/deploy/.cloudflared/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.json

ingress:
  # → Nginx 网关（前端的路径）
  - hostname: gapple.bond
    service: http://localhost:8080

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
cloudflared tunnel run edu-companion

# 后台启动（生产）
nohup cloudflared tunnel run edu-companion > ~/cloudflared.log 2>&1 &

# 查看日志
tail -f ~/cloudflared.log
```

看到 `Registered tunnel connection` 和 `Connection xxxxxx registered` 表示连接成功。

---

## 七、开机自启（systemd）

```bash
# 安装为系统服务
sudo cloudflared service install

# 或手动创建 service 文件
sudo tee /etc/systemd/system/cloudflared.service << 'EOF'
[Unit]
Description=Cloudflare Tunnel (edu-companion)
After=network.target

[Service]
Type=simple
User=deploy
ExecStart=/usr/bin/cloudflared tunnel run edu-companion
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared
# 注意：如果使用 user=deploy，需用 systemctl --user
```

---

## 八、验证部署

```bash
# 等 DNS 生效（1~5 分钟）
curl -s -o /dev/null -w "%{http_code}" https://gapple.bond
# 期望：200

curl -s -o /dev/null -w "%{http_code}" https://api.gapple.bond/health
# 期望：200

# 查看 Tunnel 连接状态
cloudflared tunnel list
cloudflared tunnel info edu-companion
```

---

## 九、日常运维

### 更新代码 + 重启

```bash
cd /home/deploy/edu-companion
git pull
bash rebuild.sh
```

### 快速重启

```bash
bash rebuild.sh --skip-build
```

### 查看服务状态

```bash
ps aux | grep -E 'uvicorn|next|nginx|cloudflared'
ss -tlnp | grep -E '3000|8000|18001|8080'
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
nohup cloudflared tunnel run edu-companion > ~/cloudflared.log 2>&1 &

# 8. 验证
curl https://gapple.bond
```
