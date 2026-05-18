# 智能伴学系统 · 开发进度

> 最后更新: 2026-05-18

---

## 总体进度

```
Phase 1 MVP:  ████████████████████░  ~90%
练习系统:     ████████████████████   完成
对话系统:     ███████████████░░░░░   ~75%
知识图谱:     ████████████████░░░░   ~85%
多模态交互:   ██████████████░░░░░░   ~80%
部署:         ████████████████████   双服务器就绪
```

---

## 项目规模

| 维度 | 数据 |
|------|------|
| 后端 Python 文件 | 56 个 |
| 后端代码行数 | ~12,000 行 |
| API 端点 | 68 个 |
| 前端 TSX/TS 文件 | 33 个 |
| 前端代码行数 | ~6,000 行 |
| 前端页面 | 10 个 |
| 设计/技术文档 | 14 篇 |
| 知识图谱 | 38 节点 × 38 学科映射 |
| 数据库 | PostgreSQL 14 |
| LLM | DeepSeek v4 Flash (via LiteLLM) |
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
| DeepSeek 模型 | deepseek-v4-flash 接入 | ✅ |

### 练习系统 ⭐ 完整
| 模块 | 文件 | 说明 |
|------|------|------|
| 数据模型 | `schemas/practice.py` | 12个模型 |
| BKT引擎 | `core/knowledge_trace.py` | 4维知识状态+提示打折+遗忘曲线 |
| LLM出题 | `services/question_generator.py` | 7学科模板+干扰项标注 |
| ZPD调度 | `services/zpd_scheduler.py` | 甜蜜点计算+疲劳感知+SM-2间隔 |
| 练习API | `api/practice.py` | 12端点 |
| 前端练习页 | `practice/page.tsx` | 完整答题流 |
| 前端错题本 | `errors/page.tsx` | 状态筛选+标记掌握 |
| 前端学情分析 | `analytics/page.tsx` | 7面板含遗忘曲线 |
| 前端统计页 | `stats/page.tsx` | 概览+薄弱/掌握分布 |
| 前端进度页 | `progress/page.tsx` | 掌握度+趋势+日历+错题分析 |

### 知识图谱
| 模块 | 说明 | 状态 |
|------|------|------|
| 前置依赖定义 | 38个技能的前置关系 | ✅ |
| 前置卡控 | 未掌握前置技能不可练习 | ✅ |
| 最优学习路径 | 拓扑排序推荐顺序 | ✅ |
| 力导向布局 | Fruchterman-Reingold 算法 | ✅ |
| 遗忘曲线面板 | BKT + Ebbinghaus 可视化 | ✅ |
| 前端图谱页 | `/graph` 交互式DAG | ✅ |

### 对话系统
| 模块 | 说明 | 状态 |
|------|------|------|
| 树形对话 | TreeNode/Partition/Branch | ✅ |
| WebSocket | 流式token输出 | ✅ |
| 分区管理 | Embedding+关键词自动分类 | ✅ |
| 多模态回复 | ResponseBlock (5种工具) | ✅ |
| 前端对话页 | `/chat` 分区侧栏+分支列表 | ✅ |

### 多模态交互
| 模块 | 说明 | 状态 |
|------|------|------|
| 语音输入 | Web Speech API + MediaRecorder双通道 | ✅ |
| 视频嵌入 | B站/YouTube iframe响应块 | ✅ |
| 媒体搜索 | 自动搜索B站视频+资料 | ✅ |
| 内联练习 | 对话中嵌入答题组件 | ✅ |
| TTS语音合成 | `/api/multimodal/tts` | ✅ |

### 前端
| 模块 | 说明 | 状态 |
|------|------|------|
| 响应式布局 | 手机底部Tab / 桌面左侧栏 | ✅ |
| 瑞士设计风格 | 暗色 `#0a0a0a`，强调 `#0066FF` | ✅ |
| 主题切换 | 暗色/亮色 CSS变量 | ✅ |
| KaTeX公式 | LaTeX数学渲染 | ✅ |
| 10个页面 | 首页/练习/对话/学情/图谱/错题/进度/统计/资料/设置 | ✅ |

### 后端 - 其他
| 模块 | 说明 | 状态 |
|------|------|------|
| Agent 调度器 | 意图分析 + 情绪感知 | ✅ |
| LiteLLM 封装 | 流式输出 + 路由 | ✅ |
| 资料上传/解析 | PDF/DOCX/PPTX/图片 | ✅ |
| 向量搜索 | 资料语义索引 | ✅ |

---

## 待开发 🔲

### P0 — 下一步

| 模块 | 说明 |
|------|------|
| 对话×练习联动 | 练习结果→对话记忆、ContextAware触发 |
| SharedKnowledgeState | 对话和练习统一知识状态 |
| 前台资料页完善 | `/materials` 搜索+预览完善 |

### P1 — 增强功能

| 模块 | 说明 |
|------|------|
| 行为分析+习惯养成 | 最佳学习时段+番茄钟+TinyHabits |
| B站真实视频搜索API | 替换模拟数据 |
| 间隔复习系统 | SM-2完整实现 |
| 题目质量监控 | 自动淘汰太简单/有歧义的题 |
| 跨分区整理 | 自动合并相似分区 |

### P2 — 远期
- 文生图集成（函数图像/思维导图）
- 心理陪伴模块
- 用户资料 RAG 深度集成

---

## 修复记录（2026-05-17~18）

| 提交 | 问题 | 修复 |
|------|------|------|
| `2291015` | backend从未加载.env | 添加 `load_dotenv()` |
| `badad11` | .env模板缺DB_PASSWORD | 自动创建+补全 |
| `4cdbdb6` | csstype@3.2.3 编译失败 | 锁 csstype@3.1.3 |
| `d4a52b4` | 构建失败静默 | 清缓存+检查exit code |
| `f9afa4e` | edu-server DB端口5433 | 修复repull脚本 |
| `ab4e0cc` | HeatmapCell/questions→count | 字段名修复 |
| | Sidebar/BottomNav /knowledge→/graph | 导航404修复 |

---

## 技术债务
- 对话树结构 → PostgreSQL（当前JSON文件）
- Embedding模型未装（sentence-transformers太大）
- Agent prompt 需调优
- B站/文生图等返回模拟数据
- 自动化测试覆盖率低
