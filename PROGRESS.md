# 智能伴学系统 · 开发进度

> 最后更新: 2026-05-26 (Phase 8 — 流式续写/后台解耦/ActiveStreamTracker)

---

## 总体进度

```
Phase 1 MVP:  █████████████████████  ~99%  (工作空间打通)
练习系统:     ████████████████████   完成
对话系统:     █████████████████████  ✅ PG 持久化
知识图谱:     █████████████████████  ✅ CognitiveNode + 备降
多模态交互:   █████████████████████  ~90% (+分支文件上传)
学习规划:     ████████████████████   ~95%
认知画像:     █████████████████████  ✅ Phase 6 (15子系统+22方程+18步Pipeline+PG默认)
秘书系统:     █████████████████████  ✅ Phase 7 (8子系统+勿扰/去重/上限/关系记忆)
部署:         ████████████████████   双服务器就绪
```

---

## 项目规模

| 维度 | 数据 |
|------|------|
| 后端 Python 文件 | 60+ 个 |
| 后端代码行数 | ~14,000 行 |
| API 端点 | 80+ 个 |
| 前端 TSX/TS 文件 | 35+ 个 |
| 前端代码行数 | ~7,500 行 |
| 前端页面 | 12 个 (+study, +quality) |
| 设计/技术文档 | 15+ 篇 |
| 知识图谱 | 40 技能/38 节点 |
| 数据库 | PostgreSQL 14 + pgvector |
| LLM | DeepSeek v4 Flash/Pro (via LiteLLM) |
| 仓库 | github.com/uilz/edu-companion |
| Phase 1 状态 | 5缺口打通+工作空间 ~99% |

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

### 对话系统 (完成 ✅)
| 模块 | 说明 | 状态 |
|------|------|------|
| 树形对话 | TreeNode/Partition/Branch | ✅ |
| WebSocket | 流式token输出 | ✅ |
| 分区分类 |关键词+规则自动分类 | ✅ |
| 多模态回复 | ResponseBlock (5种工具) | ✅ |
| 分支管理 | 创建/切换/LLM自动命名(含推理模型支持)/摘要 | ✅ |
| 树编辑 | 消息编辑→新分支分叉 | ✅ |
| 分支工作空间 | 文件上传/列表/获取/删除(Branch Workspace) | ✅ |
| 前端对话页 | `/chat` 完整功能 (含WorkspacePanel) | ✅ |
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

## Phase 7 — 秘书系统 (Secretary System)

| 模块 | 说明 | 状态 |
|------|------|------|
| 策略引擎 (PolicyEngine) | 勿扰/去重/上限/关系记忆 | ✅ |
| 事件总线 | 订阅 AnswerSubmitted/SessionCompleted/KnowledgeStateUpdated | ✅ |
| 冷启动对话 + 备考模式 + 数据导出/删除 | 初始化策略和合规功能 | ✅ |
| 前端铃铛红点 (SecretaryBellBadge) + 提案卡片 API | 通知组件与对应端点 | ✅ |
| 回归用户检测 (return_user_detection) | 识别旧用户并触发恢复策略 | ✅ |
| 元认知反思 (meta_cognitive_prompt) | 8种提示池，引导深度反思 | ✅ |
| 静默任务 (silent_task) | 后台记账零提案，无干扰 | ✅ |
| 模块管理 | 9个内置模块，设置页开关 | ✅ |

---

## Phase 8 — 流式续写 + 后台解耦

| 模块 | 说明 | 状态 |
|------|------|------|
| 流式增量持久化 | send_and_reply_stream 每 20 token 覆写 DB | ✅ |
| 后台 generator 解耦 | asyncio.Queue 解耦，WS 断连后流继续跑 | ✅ |
| ActiveStreamTracker | 追踪活跃流，GET 端点检测 | ✅ |
| 轮询续流 | 刷新后检测活跃流 → 每 2s loadMessages | ✅ |
| 用户功能栏修复 | group 类补回 / AI 不可编辑 / 去掉空白行 | ✅ |
| isSendingRef | 阻断 loadMessages 竞争条件（无树下发消息修复） | ✅ |
| 默认→临时 | 前后端全部替换命名 | ✅ |

---

## 修复记录

### 2026-05-23 — 模型路径修复 + gitignore + 文档清理
| 提交 | 内容 |
|------|------|
| `73f3df7` | chore: 整合模型目录到 gitignore，统一下载说明到 models/README.md |
| `9c6d394` | fix: 修正 embedding 模型路径（backend/models/），更新 README 与实际一致 |

### 2026-05-19 — Phase 1 缺口打通 + 工作空间 + 关键修复
| 提交 | 内容 |
|------|------|
| `96bb474` | feat: /study 学习规划页面 (7 API) |
| `6d5486e` | feat: /quality 题目质量页面 (5 API) |
| `7e2885a` | feat: SharedKS 集成到 /stats |
| `c6aba12` | feat: 首页全局内容搜索 |
| `065f8a8` | fix: 4项修复 (分支编辑/代码块/分支命名/工具感知) |
| `2f63bc9` | fix: 5项修复 (布局/LaTeX/语音/滚动/双头像) |
| `b8587d4` | fix: 分支自动命名(3层根因: DEEPSEEK_API_KEY→max_tokens→reasoning_content) + LaTeX regex + AI消息编辑权限 |
| `7e741fb` | feat: 分支工作空间 (4 API: upload/list/serve/delete + WorkspacePanel + ChatInput集成) |

### 2026-05-17~18
| 提交 | 问题 | 修复 |
|------|------|------|
| `2291015` | backend从未加载.env | 添加 `load_dotenv()` |
| `badad11` | .env模板缺DB_PASSWORD | 自动创建+补全 |
| `4cdbdb6` | csstype@3.2.3 编译失败 | 锁 csstype@3.1.3 |
| `f9afa4e` | edu-server DB端口5433 | 修复repull脚本 |
| `ab4e0cc` | HeatmapCell字段名错误 | questions→count |

---

## 技术债务
- 文生图/思维导图/文档生成返回占位数据
- 自动化测试覆盖率低
- agent prompt 持续调优中
- 前端 `overflow: hidden` 曾导致移动端不可滚动（已修复）
- `.next` 构建缓存与 `npm run dev` 冲突（需 `rm -rf .next`）

### 2026-05-24
| 提交 | 问题 | 修复 |
|------|------|------|
| - | 树节点 CRUD 路由重复，缓存策略混乱 | 归一化为 `/tree/{level}` 端点，前端统一 `apiFetch`，变更后强制刷新 |
| - | 创建节点后不会自动展开到对话 | 后端返回最底层对话 ID，前端跳转触发自动展开 |
| - | 自动展开只到领域级 | 强制刷新子列表，移除缓存读取 |
| - | 发送消息、删除分区 500 | 补全 `conversation_id` 参数，修复删除逻辑，统一异常处理 |
| - | 新建对话被空名称校验拦截 | 改为只拒绝 `None`，允许空字符串 |
| - | 列表 304 导致新节点不显示 | 后端 `no-cache`，变更后 `forceRefresh` 强制获取 |

### 2026-05-24 — Phase 7 秘书系统
| 提交 | 内容 |
|------|------|
| `fb58def` | feat: ProposalStore adapt to flat schema |
| `1e09420` | feat: Phase 7 G4+G5 features (秘书系统完整功能) |

### 2026-05-26 — Phase 8 流式续写 + 后台解耦
| 提交 | 内容 |
|------|------|
| `da1b7f3` | feat: WS断连后台流不中断 + 刷新后轮询加载活跃流 |
| `b0ead7b` | fix: 无树下发消息 + 默认→临时 + secretary检查 |
| `bdfef07` | fix: 恢复原 edu-companion-repull 脚本名，更新为 systemd 方式 |

## 技术债务
- 自动展开逻辑仍有极少数边界情况（刷新后未完全展开）待继续优化
- 前端 `PartitionSidebar` 组件较重，可考虑拆分为独立 hooks 和子组件
- 部分 Pylance 误报（如 `model_dump` 可能为 None）暂时保留 `# type: ignore`
