# 文件管理系统

> 文件上传 / 解析 / 索引 / TOC / RAG / 练习生成。

---

## 双区设计

```
工作空间 /files
├── 📁 知识库 (library)     → 永久保留，建 TOC 索引，AI 优先检索
└── 📋 临时文件 (session)   → 生命周期跟随对话（+7 天），小文件按段落分块
```

## purpose 自动判定

| 条件 | 归类 |
|------|------|
| 文件 > 5MB 或 > 15 页 | library |
| 从 /files 页面上传 | library |
| 从对话上传 | session |
| 用户手动覆盖 | 按用户选择 |

## 索引策略

| 文件规模 | TOC | 分块策略 |
|----------|:---:|---------|
| > 15 页 / > 5MB | ✅ 完整目录树 | 按标题层级 |
| ≤ 15 页 / ≤ 5MB | ❌ | 直接按段落 |

## 功能清单

| 功能 | 状态 |
|------|------|
| 文件上传 | ✅ 已实现 |
| PDF/文档解析 | ✅ 已实现 |
| TOC 层次索引 | ✅ 已实现 |
| RAG 检索 | ✅ 已实现 |
| 练习生成 | ✅ 已实现 |

## 前端代码路径

- 前端页面: `frontend/src/app/files/`
- 前端组件: `frontend/src/components/ui/FilePreview.tsx`

## 后端 API

- 路由模块: `backend/app/api/system/files_routes/`（browse / upload / manage）
- 端点前缀: `/api/files/*`

> 完整设计文档见 [subsystems/file-management/README.md](../../subsystems/file-management/README.md)。
