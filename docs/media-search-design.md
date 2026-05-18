# 媒体搜索系统设计 v1.0

> 核心理念：不调API，不爬数据。AI生成搜索词 + 平台搜索链接，用户点新窗口打开。

---

## 一、设计原则

```
传统方案: 调B站API → 需申请key → 有限流 → 有合规风险 → 只有B站
本方案:   AI生成搜索词 → 构建平台URL → 用户自己搜 → 零风险 → 10平台
```

| 对比 | API方案 | 本方案 |
|------|--------|--------|
| 合规 | 需要申请、有条款限制 | 零风险，纯URL跳转 |
| 限流 | 有QPS限制 | 无限制 |
| 平台 | 单一平台 | 10个平台 |
| 搜索词 | 用户原始输入 | AI优化后精准词 |
| 维护 | API变更需改代码 | URL模板稳定 |

---

## 二、支持的平台

| 平台 | 用途 | 搜索URL |
|------|------|---------|
| 🎬 B站 | 教学视频、课程 | `search.bilibili.com/all?keyword=` |
| ▶️ YouTube | 英文教程 | `youtube.com/results?search_query=` |
| 💬 知乎 | 深度问答 | `zhihu.com/search?type=content&q=` |
| 📄 百度文库 | 课件习题 | `wenku.baidu.com/search?word=` |
| 🎵 抖音 | 短视频科普 | `douyin.com/search/` |
| 📕 小红书 | 笔记经验 | `xiaohongshu.com/search_result?keyword=` |
| 🔍 Bing | 全球搜索 | `bing.com/search?q=` |
| 🌐 百度 | 国内搜索 | `baidu.com/s?wd=` |
| 🇨🇳 学习强国 | 官方课程 | `xuexi.cn/search.html?q=` |
| 📖 知网 | 学术论文 | `kns.cnki.net/...?kwd=` |

---

## 三、两条触发路径

### 3.1 对话触发（用户主动）

```
用户: "导数的几何意义有视频讲解吗"
  ↓
tool_executor 检测关键词 → search_media
  ↓
MediaSearchService.search(query="导数几何意义")
  ├── LLM生成优化搜索词:
  │   B站: "导数几何意义 入门讲解"
  │   YouTube: "derivative geometric meaning"
  │   知乎: "导数几何意义 如何理解"
  └── 构建搜索链接
  ↓
前端 MediaSearchBlock 渲染可点击卡片
```

### 3.2 练习错误触发（自动推荐）

```
学生做错题
  ↓
session完成 → complete_session API
  ↓
PracticeToDialogueRecommendation.should_recommend_media()
  ↓ (有错误 → 是)
MediaSearchService.recommend_for_error(skill, error_type)
  ├── 概念错误 → "XXX 概念讲解 通俗"
  ├── 计算错误 → "XXX 解题技巧 易错"
  └── 程序错误 → "XXX 详细步骤 例题"
  ↓
返回 media_recommend: {message, platforms}
  ↓
前端在练习结果页显示搜索链接卡片
```

---

## 四、AI搜索词优化

LLM 根据平台特点生成不同搜索词：

| 平台 | 优化策略 | 示例 |
|------|---------|------|
| B站 | +"讲解/入门/速成" | "导数几何意义 入门讲解" |
| YouTube | 英文翻译 | "derivative geometric meaning" |
| 知乎 | +"如何理解/详解" | "导数几何意义 如何理解" |
| 百度文库 | +"课件/习题" | "导数几何意义 知识点总结" |
| 小红书 | +"笔记/经验" | "导数几何意义 学习笔记" |
| Bing | 中英混合 | "derivative 几何意义 tutorial" |

---

## 五、前端交互

```
┌─ 🔍 搜索视频教程 · 导数几何意义 ─────────────┐
│                                                │
│  🎬 B站 · 国内最大学习视频平台                  │
│  ↗ 导数几何意义 入门讲解        [新窗口打开]    │
│  ↗ 导数几何意义 通俗理解                       │
│                                                │
│  ▶️ YouTube · 全球视频平台                      │
│  ↗ derivative geometric meaning                │
│                                                │
│  💬 知乎 · 高质量问答和深度解析                 │
│  ↗ 导数几何意义 如何理解                       │
│                                                │
│  📕 小红书 · 学习笔记、经验分享                 │
│  ↗ 导数几何意义 学习笔记                       │
│                                                │
│  点击链接在新窗口打开 · AI优化搜索词             │
└────────────────────────────────────────────────┘
```

## 六、文件索引

| 文件 | 内容 |
|------|------|
| `services/media_search.py` | 10平台URL模板 + LLM搜索词优化 + 错误推荐 |
| `services/tool_executor.py` | search_media 工具定义和处理 |
| `services/dialogue_recommender.py` | should_recommend_media() |
| `services/conversation_llm.py` | 对话中媒体搜索触发+困惑信号 |
| `api/practice.py` | session完成→自动推荐媒体搜索 |
| `components/MediaSearchBlock.tsx` | 多平台搜索链接卡片UI |
| `components/ResponseBlockRenderer.tsx` | Video路由到MediaSearchBlock |
