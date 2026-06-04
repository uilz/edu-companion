好问题！整个对话系统的代码结构清晰，我来给你画一张"地图"：
## 🗺️ 对话系统代码地图
### 后端（Python + FastAPI）
```
backend/app/
├── api/
│   └── conversation_routes.py    ← 🌐 API 路由（所有 REST 端点）
│       ├── GET    /tree/{level}          查列表
│       ├── POST   /tree/{level}          创建
│       ├── PATCH  /tree/{level}/{id}    改名
│       ├── DELETE /tree/{level}/{id}    删除
│       └── POST   /conversations/ws      WebSocket 消息
│
├── services/                        ← 🧠 核心业务逻辑
│   ├── tree_ops.py                  ← 组合所有 mixin
│   ├── tree_crud.py                 ← CRUD + 自动创建逻辑
│   ├── tree_sync.py                 ← 同步到认知图谱
│   ├── tree_naming.py               ← 重命名逻辑
│   ├── storage.py                   ← 存储抽象层
│   └── pg_storage.py                ← PostgreSQL 持久化
│
├── schemas/
│   └── conversation.py              ← 📦 数据模型
│       ├── Partition  (分区)
│       ├── Domain     (领域)
│       ├── Topic      (专题)
│       └── Conversation (对话)
│
├── db/
│   └── conversation_schema.sql      ← 🗄️ 数据库表结构
│
├── cognitive/                       ← 🧠 认知图谱系统
│   ├── storage.py                   ← 认知节点存取
│   └── models.py                    ← CognitiveNode 模型
│
└── api/
    └── learning.py                  ← 图谱/分类 API
```
### 层级关系
```
分区 (Partition)          ← 最高层，如"高等数学"
  └── 领域 (Domain)       ← 如"微积分"
       └── 专题 (Topic)   ← 如"导数"
            └── 对话 (Conversation) ← 实际的聊天
```
## 🔧 常见修改场景
### 1️⃣ **加一个新字段到分区**
1. `schemas/conversation.py` → `Partition` 类加字段
2. `db/conversation_schema.sql` → 加 `ALTER TABLE` 列
3. `services/pg_storage.py` → `save()` 的 INSERT 加字段
### 2️⃣ **改"新建会话"的自动行为**
→ 改 `services/tree_crud.py` 的 `_ensure_conversation_parent_path()` 这是你刚才看到的——控制对话找不到父节点时，是走认知图谱还是走临时分区
### 3️⃣ **改重命名逻辑**
→ 改 `services/tree_naming.py` 的 `_rename_node()`
### 4️⃣ **改 API 端点**
→ 改 `api/conversation_routes.py` 比如加个 "移动对话到其他分区" 的端点
### 5️⃣ **改对话 WebSocket 消息处理**
→ 搜 `def handle_message` 或 `api/conversation.py` 里的 `ws_router`
### 6️⃣ **改前端侧栏/对话列表**
```
frontend/src/components/conversation/
├── Phase8Sidebar.tsx      ← 📋 左侧分区树
├── ConversationPanel.tsx   ← 🗣️ 主对话面板
├── FocusModePanel.tsx      ← 🔍 专注模式
├── MessageList.tsx         ← 💬 消息列表
├── ChatInput.tsx           ← ⌨️ 输入框
└── CognitiveTag.tsx        ← 🏷️ 分类标签
```
## 🚀 修改后重启
```bash
cd ~/edu-companion
bash rebuild.sh    # 一键构建+重启
```
> **小贴士**：想快速实验可以直接改代码跑 `bash rebuild.sh`，如果只是改后端也可以用 `systemctl restart edu-companion`（如果配了 systemd）。
现在有什么功能想自己动手改吗？我可以给你指具体改哪个文件、哪几行。
deepseek-v4-flash · 40% · ~