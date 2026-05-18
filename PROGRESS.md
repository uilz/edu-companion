# 智能伴学系统 · 开发进度

> 最后更新: 2026-05-19  (Phase 1 审计完成，状态修正)

---

## 总体进度

```
Phase 1 MVP:  █████████████████████  ~98%  (5缺口全部打通)
练习系统:     ████████████████████   完成
对话系统:     ████████████████████   ~95%
知识图谱:     ████████████████████   ~85%
多模态交互:   █████████████████░░░   ~85%
学习规划:     ████████░░░░░░░░░░░░   ~45%  ← 后端完成/前端缺失
部署:         ████████████████████   双服务器就绪
```

---

## 项目规模

| 维度 | 数据 |
|------|------|
| 后端 Python 文件 | 60+ 个 |
| 后端代码行数 | ~14,000 行 |
| API 端点 | 71 个 |
| 前端 TSX/TS 文件 | 35+ 个 |
| 前端代码行数 | ~6,500 行 |
| 前端页面 | 10 个 |
| 设计/技术文档 | 15+ 篇 |
| 知识图谱 | 40 技能/38 节点 |
| 数据库 | PostgreSQL 14 + pgvector |
| LLM | DeepSeek v4 Flash/Pro (via LiteLLM) |
| 仓库 | github.com/uilz/edu-companion |

---

## 已完成 ✅

### 基础设施
| 模块 | 说明 | 状态 |
|------|------|------|
| 项目骨架 | 后端 FastAPI + 前端 Next.js 14 | ✅ |
| Git 仓库 | GitHub: uilz/edu-companion | ✅ |
| 开发服务器 | deploy@dev (当前机) | ✅ |
| 生产服务器 | deploy@edu-server (192.168.13.134) | ✅ |
| 一键部署 | edu-companion-repull 脚本 | ✅ |
| DeepSeek 模型 | v4-flash/v4-pro 接入 | ✅ |

### 练习系统 ⭐ 完整
| 模块 | 文件 | 说明 |
|------|------|------|
| 数据模型 | `schemas/practice.py` | 12个模型 |
| BKT引擎 | `core/knowledge_trace.py` | 4维知识状态+提示打折+遗忘曲线+持久化 |
| LLM出题 | `services/question_generator.py` | 7学科模板+干扰项标注 |
| ZPD调度 | `services/zpd_scheduler.py` | 甜蜜点计算+疲劳感知 |
| 前置卡控 | `domain/knowledge/checker.py` | 40技能依赖图+多层传递 |
| 自适应规划 | `services/adaptive_planner.py` | 知识升级→自动重调 |
| 题目质量 | `services/quality_analyzer.py` | IRT 6维分析+自动淘汰 |
| 练习API | `api/practice.py` | 18+端点 |
| 前端练习页 | `practice/page.tsx` | 完整答题流 |
| 前端错题本 | `errors/page.tsx` | 状态筛选+标记掌握 |
| 前端学情 | `analytics/page.tsx` | 7面板+习惯Tab |
| 前端统计 | `stats/page.tsx` | 概览+薄弱/掌握分布 |
| 前端进度 | `progress/page.tsx` | 掌握度+趋势+日历 |

### 知识图谱 (85%)
| 模块 | 说明 | 状态 |
|------|------|------|
| 前置依赖定义 | 40个技能的前置关系 | ✅ |
| 前置卡控 | 未掌握前置技能不可练习 | ✅ |
| 最优学习路径 | 拓扑排序推荐顺序 | ✅ |
| 力导向布局 | Fruchterman-Reingold 算法 | ✅ |
| 遗忘曲线面板 | BKT + Ebbinghaus 可视化 | ✅ |
| 前端图谱页 | `/graph` 交互式DAG | ✅ |

### 对话系统 (95%)
| 模块 | 说明 | 状态 |
|------|------|------|
| 树形对话 | TreeNode/Partition/Branch | ✅ |
| WebSocket | 流式token输出 | ✅ |
| 分区分类 |关键词+规则自动分类 | ✅ |
| 多模态回复 | ResponseBlock (5种工具) | ✅ |
| 分支管理 | 创建/切换/命名/摘要 | ✅ |
| 树编辑 | 消息编辑→新分支分叉 | ✅ |
| 前端对话页 | `/chat` 完整功能 | ✅ |
| 工具调用 | 规则预判+上下文感知 | ✅ |

### 对话×练习联动 (5点模型完成)
| # | 集成点 | 方向 | 状态 |
|---|--------|------|------|
| ③ | SharedKnowledgeState | 双向 | ✅ |
| ② | PracticeResultIntegrator | 练习→对话 | ✅ |
| ① | ContextAwareTrigger | 对话→练习 | ✅ |
| ④ | InlinePractice | 双向 | ✅ |
| ⑤ | DialogueRecommendation | 练习→对话 | ✅ |
| — | Citation Tracing | — | ✅ |
| — | 情绪分析(11类) | — | ✅ |

### 多模态交互 (85%)
| 模块 | 说明 | 状态 |
|------|------|------|
| 语音输入 | Web Speech API + MediaRecorder双通道 | ✅ |
| 视频嵌入 | B站/YouTube iframe响应块 | ✅ |
| 媒体搜索 | 10平台搜索链接生成 | ✅ |
| 内联练习 | 对话中嵌入答题组件 | ✅ |
| TTS朗读 | `/api/multimodal/tts` | ✅ |
| 文件上传 | 图片/文档可上传 | ✅ |
| 图片生成 | tool_executor占位 | ⚠️ |

### 资料系统
| 模块 | 说明 | 状态 |
|------|------|------|
| 上传解析 | PDF/DOCX/PPTX/MD/TXT+音频 | ✅ |
| 向量搜索 | pgvector语义索引 | ✅ |
| Promote模式 | session→permanent升级 | ✅ |
| 智能建议 | 哪些文档值得存知识库 | ✅ |
| LLM出题 | 资料→练习题 | ✅ |
| 前端资料页 | 筛选/排序/批量/预览/搜索 | ✅ |

### 学习行为分析
| 模块 | 说明 | 状态 |
|------|------|------|
| 行为分析 | streak/best-hours/regularity/fatigue | ✅ |
| 习惯养成 | TinyHabits/番茄钟/每日目标 | ✅ |
| 情绪感知 | 11类情绪分类+趋势追踪 | ✅ |
| 心理陪伴 | 挫败/焦虑共情+策略注入 | ✅ |

---

## 🔴 Phase 1 缺口状态

| # | 缺口 | 状态 | 提交 |
|---|------|:--:|:--:|
| 1 | 学习规划前端 | ✅ | `96bb474` — /study 页 |
| 2 | 题目质量监控 | ✅ | `6d5486e` — /quality 页 |
| 3 | SharedKnowledgeState | ✅ | `7e2885a` — 集成到 /stats |
| 4 | 内容搜索浏览 | ✅ | `c6aba12` — 首页搜索栏 |
| 5 | 分区消息列表 | ✅ | 已由聊天页 loadMessages 覆盖 |

---

## 修正记录 (vs 旧版)

| 旧版 | 修正 |
|------|------|
| P1 "行为分析+习惯养成" | → DONE ✅ |
| P1 "题目质量监控" | → DONE ✅ (后端) |
| P2 "心理陪伴模块" | → DONE ✅ |
| P2 "文生图集成" | → ⚠️ 占位 |
| 知识图谱 20% | → 85% (前端已完整) |
| 多模态 40% | → 85% |
| API 68个 | → 71个 |
| 学习规划未列出 | → 45% (后端完整/前端缺失) |

---

## 技术债务
- Embedding模型未装（sentence-transformers太大）→ 分类器降级用关键词
- 文生图/思维导图/文档生成返回占位数据
- 自动化测试覆盖率低
- agent prompt 持续调优中
- 前端 `overflow: hidden` 曾导致移动端不可滚动（已修复）
- `.next` 构建缓存与 `npm run dev` 冲突（需 `rm -rf .next`）
