# ADR 0017: 文件系统浏览体验分析与改进方案 (Round 3 Step 4)

> 生成日期: 2026-06-16 | 状态: Draft
> 前置: ADR 0014 (全景), ADR 0015 (深层分析), ADR 0016 (接口+索引)
> 目标: 完整分析当前浏览体验，提出改进方案

---

## 1. 当前浏览体验全景

### 1.1 前端页面结构

```
/resources       → ResourcesPage (资源管理主页, 908行)
  ├── tab: 文件资料    → 文件列表(列表/网格模式)
  ├── tab: 题库资料    → 题库列表
  ├── tab: 统计        → 文件统计仪表盘
  └── tab: 回收站      → 已删除文件管理

/files/[material_id] → FileDetailPage (文件详情, 212行)
  ├── 面包屑导航 → /resources
  ├── 文件头部   → icon + 文件名 + 类型/分块/章节/日期
  ├── TOC侧栏    → 可展开目录树
  └── 内容分块列表 → 分块卡片
```

### 1.2 后端 API (已实现)

| 端点 | 返回数据 | 前端使用 |
|------|----------|----------|
| `GET /api/files` | 分页列表 + 过滤 | 文件列表/搜索/类型过滤 |
| `GET /api/files/tags` | 标签集合 | 标签下拉过滤 |
| `GET /api/files/folders` | 文件夹列表 | 文件夹导航 |
| `GET /api/files/stats` | 统计信息 | 统计tab |
| `GET /api/files/trash` | 回收站列表 | 回收站tab |
| `GET /api/files/{id}` | 文件详情 | 详情页头部 |
| `GET /api/files/{id}/download` | 二进制流 | 下载/预览 |
| `GET /api/files/{id}/toc` | TOC树 | 目录侧栏 |
| `GET /api/files/{id}/chunks` | 分块列表(截断1000字符) | 内容展示 |
| `POST /api/files/search` | 搜索结果 | 语义搜索 |
| `DELETE /api/files/{id}` | 删除确认 | 硬删除 |
| `PATCH /api/files/{id}` | 更新确认 | 编辑元数据 |
| `PUT /api/files/{id}/tags` | 标签确认 | 编辑标签 |
| `POST /api/files/{id}/trash` | 移入确认 | 删除操作 |
| `POST /api/files/{id}/restore` | 恢复确认 | 恢复操作 |
| `DELETE /api/files/{id}/permanent` | 永久删除 | 回收站操作 |
| `POST /api/files/trash/empty` | 清空确认 | 清空回收站 |
| `POST /api/files/cleanup` | 清理确认 | （前端未调用） |
| `POST /api/files/folder` | 创建确认 | 新建文件夹 |
| `PATCH /api/files/folder/{id}` | 更新确认 | 编辑文件夹 |
| `DELETE /api/files/folder/{id}` | 删除确认 | 删除文件夹 |
| `POST /api/files/generate-practice` | 题目列表 | （前端未调用） |
| `POST /api/files/batch` | 批量结果 | 批量删除 |

### 1.3 可用后端数据 (已存在但前端未展示/未使用)

| 数据 | 存储位置 | 当前使用 | 改进机会 |
|------|----------|----------|----------|
| `heading_path` | material_chunks | 后端搜索返回 恒空 | 分块列表应展示面包屑 |
| `skills_covered_json` | materials | 列表返回但未展示 | 详情页展示技能标签 |
| `summary` | materials | 返回但未展示 | 列表/详情摘要预览 |
| `tags_json` | materials | 列表+详情已展示 | ✅ 已使用 |
| `chunk.text 完整内容` | DB(8000字符) | 截断1000 | 展开全文 |
| `chunk.page_number`(预留) | material_chunks | 返回NULL | 预留不可用 |
| `indexed_at` | materials | 返回未展示 | 索引时间信息 |
| `parent_id` | materials | 用于文件夹导航 | 路径导航更直观 |
| `embedding` | material_chunks | 搜索专用 | 可视化作"相似分块" |

---

## 2. 当前浏览体验缺陷

### 2.1 分块浏览 (P1)

| 问题 | 位置 | 描述 |
|------|------|------|
| text截断1000字符 | browse.py:401 | 分块内容永远只返回前1000字符，用户看不到完整内容 |
| 无展开功能 | frontend detail page | chunk卡片line-clamp-4，无"查看全文" |
| heading_path丢失 | browse.py:401 + material_search.py:93 | DB有 heading_path 但搜索返回硬编码空字符串，分页列表正确返回 |
| 无分块全文搜索 | 无此功能 | 不可在单个文件中搜索文本 |
| 无embedding相似chunk | 无此功能 | 不可查看"与此分块相似的其他分块" |

### 2.2 文件预览 (P2)

| 问题 | 位置 | 描述 |
|------|------|------|
| 仅图片+PDF可预览 | frontend:748-754 | image: `<img>`, PDF: `<iframe>`, 其他→下载 |
| 无音频播放 | 无 UI | 音频文件仅有文件 icon，不可在线试听 |
| 无视频播放 | 后端不支持 | 视频扩展名全部不在 ALLOWED_EXTENSIONS |
| 无Markdown渲染 | 无 UI | markdown 文件以纯文本片段展示 |
| 无DOCX/PPTX在线预览 | 无 | 只能下载 |
| 无全屏阅读模式 | 无 | 大文件需边滚动边看小卡片 |

### 2.3 导航体验 (P2)

| 问题 | 位置 | 描述 |
|------|------|------|
| 文件列表列过多 | resources page | 7列: checkbox/文件名/标签/大小/状态/日期/操作 → 小屏下拥挤 |
| 网格模式下操作隐藏 | frontend:665-669 | hover才显示操作，移动端不可用 |
| 无右键菜单 | 无 | 全部操作靠按钮 |
| 无拖拽排序 | 无 | 不可拖动调整文件位置 |
| 无批量打标签UI | 无 | 批量操作仅支持删除 |
| 详情页缺下载按钮 | detail page | header有信息无操作 |
| 详情页缺"生成练习"按钮 | detail page | API有但前端无入口 |
| 根/原路返回缺路径导航 | resources page | 面包屑仅文件夹路径，不显示当前文件 |

### 2.4 信息展示 (P3)

| 问题 | 位置 | 描述 |
|------|------|------|
| skills_covered_json不展示 | browse.py:121返回skills | 前端从未渲染 |
| summary不展示 | browse.py:122返回summary | 前端从未渲染 |
| toc_count不展示 | detail page header | 只有chunk_count |
| indexed_at不展示 | browse.py:130返回 | 未展示 |
| 无"相关题库" | 无 | 文件关联的题库不显示 |
| 无"关联对话" | 无 | 文件中内容被哪些对话引用 |

---

## 3. 改进方案

### 3.1 P0 修复 (不增加API, 纯修复)

| # | 修复 | 涉及 |
|---|------|------|
| F1 | 分块列表展示 heading_path | browse.py:401 已有数据, 前端渲染 |
| F2 | 详情页加下载/生成练习按钮 | frontend detail page |
| F3 | 详情页展示 skills + summary | frontend detail page (后端已返回) |
| F4 | 全文展开: chunk text >1000 部分加展开/折叠 | frontend detail page |

### 3.2 P1 新增后端 API

| # | 端点 | 功能 | 优先级 |
|---|------|------|--------|
| A1 | `GET /api/files/{id}/chunks/{index}` | 获取单个 chunk 全文(非截断) | P1 |
| A2 | `GET /api/files/{id}/search?q=...` | 在单个文件内全文搜索(ts_query) | P1 |
| A3 | `GET /api/files/{id}/similar?chunk_index=N` | 查找语义相似的分块 | P1 |
| A4 | `GET /api/files/{id}/preview` | 文件内容在线预览(HTML渲染 / 音频流 / 视频流) | P2 |

### 3.3 P1 新增前端功能

| # | 功能 | 实现方式 | 优先级 |
|---|------|----------|--------|
| U1 | 分块卡片可点击展开全文 | API A1 + 前端展开状态 | P1 |
| U2 | 文件内搜索框 + 高亮匹配 | API A2 + 前端`<mark>` | P1 |
| U3 | 音频播放器 | `<audio>` + download URL | P2 |
| U4 | TOC点击跳转到对应chunk | scrollIntoView + highlight | P2 |
| U5 | 列表模式减少列数(响应式) | 隐藏某些列于`<md` | P2 |
| U6 | 分块内容 heading_path 展示 | 后端已有数据, 前端渲染 | P1 |
| U7 | 技能标签展示 | 后端已有 skills 字段 | P2 |
| U8 | 摘要行展示 | 后端已有 summary 字段 | P2 |
| U9 | 文件详情页下载按钮 | href → download URL | P1 |
| U10 | 文件详情页"生成练习"按钮 | 调 POST /api/files/generate-practice | P2 |
| U11 | 多选→批量移动/加标签 | 前端现有 batch API → 扩展 action | P2 |

### 3.4 P2 新增后端 API

| # | 端点 | 功能 | 备注 |
|---|------|------|------|
| A5 | `GET /api/files/{id}/related-banks` | 文件关联的题库列表 | 查 practice_bank_materials 关联 |
| A6 | `GET /api/files/{id}/related-conversations` | 引用此文件的对话 | 查 events/conversation_meta |
| A7 | `GET /api/files/recent` | 最近访问文件 | 需新表 file_access_log |

### 3.5 P2 新增前端组件

| # | 组件 | 说明 |
|---|------|------|
| C1 | FilePreviewModal | 统一预览: image=img, PDF=iframe, audio=audio, md=MarkdownRenderer, 其他=下载提示 |
| C2 | TOCJumpNav | TOC树增强: 高亮当前浏览chunk对应标题 |
| C3 | ChunkFullTextPanel | 分块全文侧栏/弹窗: 类似DIJ文件阅读器 |
| C4 | SkillsTags | 技能标签气泡: 类似现有 getTagColor |
| C5 | RelatedResources | 关联题库/对话面板: 参考 ReferencePanel |

---

## 4. 浏览体验新旧对比

### 4.1 文件列表页 (/resources)

```
当前:                         改进后:
┌────────────────────┐       ┌────────────────────┐
│ 📁 文件资料         │       │ 📁 文件资料         │
│ 全部 | PDF | 文档   │       │ 全部 | PDF | 文档   │
│ [搜索框]            │       │ [搜索框] [🔍文件内] │
│ ┌─ ☐ 文件名  标签  │       │ ┌─ 文件名 摘要 标签│
│ │ ☐ math.pdf  ...  │       │ │ math.pdf "极限..."│
│ │ ☐ note.md   ...  │       │ │ note.md  "连续..."│
│ └────────────────── │       │ └────────────────── │
│ 列表/网格 视图       │       │ 列表/网格 视图       │
│ [上传] [新建文件夹]  │       │ [上传/拖拽] [新建]   │
└────────────────────┘       └────────────────────┘
```

### 4.2 文件详情页 (/files/{id})

```
当前:                         改进后:
┌────────────────────┐       ┌────────────────────┐
│ ← 返回              │       │ ← 返回 [下载] [出题] │
│ 📄 math.pdf         │       │ 📄 math.pdf         │
│ PDF · 31块 · 01-01 │       │ PDF · 31块/5章 · 01-01│
│                     │       │ 🏷️ 微积分·极限·导数  │
│ 📖目录导航│ 内容31块│       │ 📝 摘要: 高等数学... │
│ ┌ 第一章     │ #1   │       │ ┌ 第一章 → 5块     │ │
│ │ └ 1.1节   │ #2   │       │ │ └ 1.1节   → 3块  │ │
│ │ └ 1.2节   │ ...  │       │ │   #1 极限定义     │ │
│ #1 内容前1000字...  │       │ │   #2 极限性质     │ │
│ #2 内容前1000字...  │       │ │   🔍[搜索文件内]  │ │
│                     │       │ #1 极限定义... [全文]│
│                     │       │   相似: #5 #8 #12   │
└────────────────────┘       └────────────────────┘
```

### 4.3 预览模态框

```
当前:                         改进后:
┌────────────────────┐       ┌────────────────────┐
│ 图片/img            │       │ 图片/img            │
│ PDF/iframe          │       │ PDF/iframe          │
│ 其他→"不支持预览"  │       │ 音频/audio controls │
│                     │       │ 视频/video controls │
│                     │       │ Markdown/MD渲染     │
│                     │       │ 其他→下载提示       │
│                     │       │ [全屏][下载][打印]   │
└────────────────────┘       └────────────────────┘
```

---

## 5. 后端改动清单

### 5.1 现有 API 增强 (最小改动)

| # | 文件 | 改动 | 行 |
|---|------|------|-----|
| E1 | browse.py:401 | `/chunks` 增加 `full_text` 可选参数 | +2 |
| E2 | browse.py:393 | `/chunks` 排序按 chunk_index | 已有 |
| E3 | browse.py:329 | `/toc` 返回增加 `chunk_count` 统计 | +1 |
| E4 | upload.py | 支持视频扩展名 (.mp4 .avi .mov .mkv) | ~ +5 |
| E5 | upload.py | 将 ALLOWED_EXTENSIONS 改为配置化 | ~ +10 |

### 5.2 新增 API

| # | 文件 | 新增端点 | 行 |
|---|------|----------|-----|
| A1 | browse.py | `GET /api/files/{id}/chunks/{index}` | ~20 |
| A2 | browse.py | `GET /api/files/{id}/search?q=` | ~30 |
| A3 | browse.py | `GET /api/files/{id}/similar?chunk=` | ~30 |
| A4 | browse.py | `GET /api/files/{id}/preview` | ~20 |

### 5.3 前端改动清单

| # | 文件 | 改动 | 估计行 |
|---|------|------|--------|
| U1 | `resources/page.tsx` | 摘要展示、技能标签、响应式列 | ~50 |
| U2 | `resources/page.tsx` | 批量操作扩展(加标签/移动) | ~30 |
| U3 | `resources/page.tsx` | 预览增强(音频/MD渲染) | ~40 |
| U4 | `[material_id]/page.tsx` | 下载按钮、生成练习按钮、skills展示 | ~30 |
| U5 | `[material_id]/page.tsx` | heading_path、全文展开、高亮 | ~60 |
| U6 | `[material_id]/page.tsx` | TOC增强(点击跳转、chunk计数) | ~40 |
| U7 | `[material_id]/page.tsx` | 文件内搜索 | ~40 |
| U8 | 新增 `ChunkFullText.tsx` | 分块全文弹窗 | ~80 |
| U9 | 新增 `AudioPlayer.tsx` | 音频播放器组件 | ~40 |

---

## 6. 现有前端 vs 后端数据映射 (确认哪些已有)

| 前端需求 | 后端是否已有 | 备注 |
|----------|-------------|------|
| skills标签 | ✅ `GET /api/files/{id}` 返回 skills | 前端未渲染 |
| summary摘要 | ✅ `GET /api/files` 返回 summary | 前端未渲染 |
| heading_path | ✅ `GET /api/files/{id}/chunks` 返回 | 前端第402行有 heading_path 字段 |
| chunk全文 | ✅ DB存8000字符 | 前端截断1000 |
| TOC章节chunk数 | ✅ DB | 需新增SQL计算 |
| 文件内搜索 | ❌ 无此API | 需新增 |
| 相似分块 | ❌ 需调用向量搜索 | 需新增 |
| 音频播放 | ✅ 下载API已存在 | 需前端加 `<audio>` |
| 视频支持 | ❌ 扩展名不在 ALLOWED_EXTENSIONS | 需后端加扩展名 |
| Markdown渲染 | ✅ 下载API | 需前端用 react-markdown |
| 生成练习 | ✅ `POST /api/files/generate-practice` | 前端未触发 |

---

## 7. 执行优先级建议

| 轮次 | 改动 | 影响 |
|------|------|------|
| **立即** (前端仅改动) | skills展示 + summary展示 + heading_path展示 + 下载按钮 | 零后端改动, 提升大 |
| **第1批** (后端微调) | chunk全文展开(A1) + 文件内搜索(A2) + 视频扩展名 | 核心浏览能力 |
| **第2批** (中等复杂度) | 预览增强(音频+MD渲染) + TOC增强 + 批量操作扩展 | 体验提升 |
| **第3批** (高复杂度) | 相似分块(A3) + 文件预览(A4) + 关联资源 | 进阶功能 |

---

## 8. Step 4 决策记录 (2026-06-16 讨论确认)

| 决策 | 结论 | 参考 |
|------|------|------|
| S4-Q1. 前端数据展示 | 纯前端改动: skills 标签 + summary 摘要 + heading_path 面包屑 | ADR 0019 |
| S4-Q2. 分块全文展开 | 新增 `/api/files/{id}/chunks/{index}` 返回全文, 前端点"展开"调用 | ADR 0019 |
| S4-Q3. 预览增强 | 分步: 先音频 `<audio>`, 再加 Markdown `react-markdown`, 最后视频支持 | ADR 0019 |
| S4-Q4. TOC 交互 | `scrollIntoView()` + IntersectionObserver 高亮当前 visible chunk | ADR 0019 |