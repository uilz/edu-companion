# Import（题库导入）

> 从文本或文件导入题目到题库，支持 AI 解析、预览编辑和批量导入。

---

## 1. 模块定位

Import 是**题库导入工具**。用户粘贴题目文本或上传文件（docx/xlsx/txt/json/pdf），系统自动解析为结构化题目，支持预览、编辑和确认后导入到指定题库。

**解决**：用户如何批量导入题目到题库 —— 从各种格式的源材料中提取题目并结构化存储。

**不解决**：题目的练习和考试（由 practice 和 exam 负责）；题目的质量分析（由 quality 负责）；题库的日常管理（由 resources 负责）。

---

## 2. 核心功能

### 2.1 输入方式

- **粘贴文本**：支持自然语言格式（题干 + 选项 + 答案 + 解析）和 JSON 格式
- **上传文件**：支持 docx / xlsx / txt / json / pdf，自动解析
- 提供 JSON 模板下载

### 2.2 解析预览

- AI 解析后展示题目列表
- 每题显示：序号、题干、题型、选项（正确答案高亮）、答案、解析
- 置信度标注（高置信 / 需修正）
- 统计：总题数、高置信数、需修正数

### 2.3 编辑与修正

- 单题内联编辑：修改题干、选项、答案、解析
- 单题删除/移除
- AI 全部修正（重新解析）
- 移除计数

### 2.4 导入确认

- 选择题库（或新建题库）
- 确认导入（过滤已移除题目）
- 导入结果展示：成功数、失败数、失败详情
- 导入历史记录

---

## 3. 前端路由

- `/import` — 题库导入页面

---

## 4. 前端代码路径

- 前端页面: `frontend/src/app/import/`
- 编辑卡片: `frontend/src/components/import/EditCard.tsx`
- 类型定义: `frontend/src/components/import/types.ts`
- 题干渲染: `frontend/src/components/practice/components/QuestionStem.tsx`
- 拖拽上传: `frontend/src/lib/dnd/FileDropZone.tsx`

---

## 5. 后端 API

| 端点 | 用途 |
|------|------|
| `POST /api/practice/import/preview` | 解析文本为题目预览 |
| `POST /api/practice/import/upload` | 上传文件并解析为题目预览 |
| `POST /api/practice/import/confirm` | 确认导入题目到题库 |
| `POST /api/practice/import/batch` | 批量导入 |
| `GET /api/practice/import/history` | 导入历史记录 |
| `POST /api/files/upload` | 上传导入文件 |
| `GET /api/practice/banks` | 获取题库列表（选择导入目标） |
| `POST /api/practice/banks` | 新建题库 |

---

## 6. 模块联动

| 方向 | 内容 |
|------|------|
| Resources → Import | 从 Resources 页面跳转到导入 |
| 题库 → Import | 导入的题目写入题库 |
| 练习 → Import | 导入完成后可跳转去练习 |
| Quality → Import | 导入的题目后续纳入质量分析 |

---

## 7. 相关文档

- [`docs/modules/practice-system/overview.md`](../practice-system/overview.md) — 练习系统（题库和练习）
- [`docs/modules/resources/overview.md`](../resources/overview.md) — 我的资源（题库管理入口）
- [`docs/modules/quality/overview.md`](../quality/overview.md) — 题库质量分析