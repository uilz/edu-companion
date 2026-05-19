# P5 · 资料→分区→分支引用

> 打破孤岛: 资料 → 分区归属 → 分支引用 → 知识图谱联动
> 
> **设计决策**：资料不复制，按分区归属，分支按需引用。

---

## 一、架构变更

### Before
```
/materials 独立页面 ← 全局扁平资料列表
workspace    ← 分支本地文件（无法引用资料）
知识图谱     ← 与资料无关联
```

### After
```
Partition (分区)
├── 分支 A ──引用──→ 导数讲义.pdf ──关联──→ 📊 知识图谱节点
├── 分支 B
├── 分支 C ──引用──→ 极限习题.docx
└── 📁 资料（本分区所有资料）
    ├── 导数讲义.pdf    partition_id = "math"
    ├── 极限习题.docx   partition_id = "math"
    └── ...
```

---

## 二、数据模型变更

### 2.1 materials 表新增字段

```sql
ALTER TABLE materials ADD COLUMN partition_id VARCHAR(64);
ALTER TABLE materials ADD COLUMN linked_skill_ids TEXT[];  -- 关联的知识图谱节点
```

### 2.2 新建 branch_material_refs 表

```sql
CREATE TABLE branch_material_refs (
    id SERIAL PRIMARY KEY,
    branch_id VARCHAR(64) NOT NULL,
    material_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(branch_id, material_id)
);
```

### 2.3 默认「未分类」分区

初始化时自动创建 `partition_id = "uncategorized"`，所有无归属资料归入此处。

---

## 三、后端变更

### 3.1 material.py 修改

| 端点 | 变更 |
|------|------|
| `POST /upload` | 新增 `partition_id` 参数 |
| `GET /api/materials` | 支持 `?partition_id=X` 过滤 |
| `POST /promote` | 索引后标记 `linked_skill_ids` |

### 3.2 新增端点

| 端点 | 用途 |
|------|------|
| `GET /api/partitions/{id}/materials` | 获取分区下所有资料 |
| `POST /api/branches/{id}/materials` | 分支引用资料 `{material_id}` |
| `DELETE /api/branches/{id}/materials/{mid}` | 取消引用 |
| `GET /api/branches/{id}/materials` | 列出分支已引用的资料 |

---

## 四、前端变更

### 4.1 删除
- ❌ `frontend/src/app/materials/page.tsx` — 独立资料页

### 4.2 PartitionSidebar 升级

每个分区条目点击后展开子视图：
```
分区侧栏
├── 🧮 高等数学
│   ├── 💬 对话
│   ├── 📁 资料 (3)    ← 新增 tab
│   └── 🌿 分支列表
├── 💻 计算机
│   └── ...
└── 📦 未分类 (默认)
    └── ...
```

### 4.3 新增 MaterialPanel 组件

```
MaterialPanel (分区级资料管理)
├── 🔍 搜索框
├── 📤 上传按钮
├── 资料列表（网格/列表切换）
│   ├── 导数讲义.pdf  [索引✅] [关联: 导数, 极限]
│   └── ...
└── 展开/预览卡片
```

### 4.4 WorkspacePanel 升级

```
WorkspacePanel
├── 📤 上传文件
├── 📎 引用资料    ← 新增
├── 文件列表...
└── 引用列表
    ├── 🏷️ 导数讲义.pdf  [✕]
    └── 🏷️ 极限习题.docx  [✕]
```

**引用流程**: 点「📎 引用资料」→ 弹出 MaterialPicker → 按当前分支所属分区过滤 → 勾选 → 确认引用

### 4.5 对话中资料标签

引用的资料在对话中显示为标签行：
```
┌─────────────────────────────────────────┐
│ 📎 已引用资料: [导数讲义] [极限习题]     │
│ ┌───────────────────────────────────┐   │
│ │ 📄 导数讲义.pdf                   │   │  ← 点击展开
│ │ 第3章 导数的定义与应用...           │   │
│ │ 关联知识点: 导数, 微分             │   │
│ └───────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

---

## 五、知识图谱联动

资料 promote 时自动：
1. 提取文本 → LLM 识别知识点 → 存入 `linked_skill_ids`
2. 对应知识图谱节点显示 `📎 N份资料`
3. 点击节点可查看关联资料列表

---

## 六、实施步骤

| Step | 内容 | 估时 |
|------|------|:--:|
| 1 | DB migration（ALTER materials + 创建 refs 表 + 默认分区） | 0.3h |
| 2 | 后端 material API 改造（partition 过滤 + 引用 CRUD） | 1h |
| 3 | 前端 PartitionSidebar 加资料 tab + MaterialPanel 组件 | 1.5h |
| 4 | WorkspacePanel 加引用按钮 + MaterialPicker 弹窗 | 1h |
| 5 | 对话中资料标签展示 | 0.5h |
| 6 | 删除 /materials 页面，更新路由和导航 | 0.2h |
| 7 | 知识图谱节点关联资料计数 | 0.5h |

**总计：~5h**
