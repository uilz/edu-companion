# Resources（我的资源）

> 学习文件管理、题库管理和文件统计的统一入口。

---

## 1. 模块定位

Resources 是学习资料的**统一管理中心**。整合了文件管理（上传/浏览/搜索/标签）、题库管理和文件统计，提供一站式资源管理体验。

**解决**：用户如何管理所有学习资料 —— 文件的上传、分类、检索、预览、下载，以及题库的管理和统计。

**不解决**：文件的阅读体验（由 reading 负责）；从文件生成练习的详细流程（由 practice 负责）；文件的知识图谱关联（由知识图谱负责）。

---

## 2. 核心功能

### 2.1 文件资料（主 Tab）

- 文件上传（支持拖拽、批量）
- 文件列表（列表/网格视图切换）
- 文件夹导航（面包屑、层级）
- 类型筛选（全部 / PDF / 文档 / 图片 / 笔记）
- 标签筛选和管理
- 文件预览（支持缩放、键盘导航）
- 文件下载
- 文件编辑（重命名、标签、层级）
- 批量操作（选择、删除、移动）
- 回收站（恢复、永久删除、清空）

### 2.2 题库

- 题库列表展示
- 题库管理入口（跳转 `/practice/banks/{id}`）
- 快速练习入口
- 题库删除

### 2.3 统计

- 文件总数、总大小、文件夹数、回收站数
- 文件类型分布（条形图）
- 最近上传列表

### 2.4 回收站

- 回收站文件列表
- 恢复文件
- 永久删除
- 清空回收站

---

## 3. 前端路由

- `/resources` — 我的资源主页
- `/resources?tab=files` — 文件资料
- `/resources?tab=banks` — 题库
- `/resources?tab=stats` — 统计
- `/resources?tab=trash` — 回收站

---

## 4. 前端代码路径

- 前端页面: `frontend/src/app/resources/`
- 文件预览组件: `frontend/src/components/ui/FilePreview.tsx`
- 拖拽上传组件: `frontend/src/lib/dnd/FileDropZone.tsx`

---

## 5. 后端 API

| 端点 | 用途 |
|------|------|
| `GET /api/files` | 文件列表（分页、筛选） |
| `POST /api/files/upload` | 上传文件 |
| `GET /api/files/{id}` | 文件详情 |
| `GET /api/files/{id}/download` | 下载文件 |
| `GET /api/files/{id}/preview` | 文件预览 |
| `PATCH /api/files/{id}` | 更新文件元数据 |
| `PUT /api/files/{id}/tags` | 更新文件标签 |
| `POST /api/files/{id}/trash` | 移入回收站 |
| `POST /api/files/{id}/restore` | 从回收站恢复 |
| `DELETE /api/files/{id}/permanent` | 永久删除 |
| `POST /api/files/trash/empty` | 清空回收站 |
| `GET /api/files/folders` | 文件夹列表 |
| `POST /api/files/folder` | 创建文件夹 |
| `GET /api/files/tags` | 获取所有标签 |
| `GET /api/files/stats` | 文件统计 |
| `POST /api/files/batch` | 批量操作 |
| `GET /api/practice/banks` | 题库列表 |

---

## 6. 模块联动

| 方向 | 内容 |
|------|------|
| Reading → Resources | 阅读模块消费文件列表和下载 |
| 练习 → Resources | 题库管理和练习入口 |
| 导入 → Resources | 从 Resources 跳转到导入页面 |
| 对话 → Resources | 对话中上传文件关联到 Resources |

---

## 7. 相关文档

- [`docs/modules/file-management/overview.md`](../file-management/overview.md) — 文件管理子系统
- [`docs/modules/reading/overview.md`](../reading/overview.md) — 阅读模块（消费文件）
- [`docs/modules/practice-system/overview.md`](../practice-system/overview.md) — 练习系统（题库管理）