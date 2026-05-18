# 智能伴学系统 · 开发进度

> 最后更新: 2026-05-18

---

## 总体进度

```
Phase 1 MVP:  ████████████████████░  ~80%
练习系统:     ████████████████████   done
对话系统:     ████████████░░░░░░░░   ~60%
```

---

## 已完成 ✅

### 基础设施
| 模块 | 说明 | 状态 |
|------|------|------|
| 项目骨架 | 后端 FastAPI + 前端 Next.js | ✅ |
| Git 仓库 | GitHub: uilz/edu-companion | ✅ |
| Docker 配置 | PostgreSQL + Redis | ✅ |
| DeepSeek 模型 | deepseek-v4-flash 接入 | ✅ |

### 练习系统 ⭐ v2.0 完成
| 模块 | 文件 | 说明 |
|------|------|------|
| 数据模型 | `schemas/practice.py` | 12个模型(Question/Session/Attempt/Material/KnowledgeState等) |
| BKT引擎 | `core/knowledge_trace.py` | 4维知识状态+提示打折+解释评分+遗忘曲线 |
| LLM出题 | `services/question_generator.py` | 7学科知识点模板+干扰项标注 |
| ZPD调度 | `services/zpd_scheduler.py` | 甜蜜点计算+疲劳感知+SM-2间隔重复 |
| 练习API | `api/practice.py` | 12端点(生成/会话/答题/提示/错题/统计) |
| 前端练习页 | `practice/page.tsx` | 创建→答题→提示→反馈完整流 |
| 前端错题本 | `errors/page.tsx` | 状态筛选+标记掌握+材料引用 |
| 前端学情分析 | `analytics/page.tsx` | 总览卡片+薄弱/掌握进度条 |
| 设计文档 | `docs/practice-system-design-v2.md` | 2443行完整设计 |

### 前端
| 模块 | 说明 | 状态 |
|------|------|------|
| 响应式布局 | 手机底部Tab / 桌面左侧栏 | ✅ |
| 瑞士设计风格 | 极简、强排版、留白 | ✅ |
| 首页仪表盘 | 今日任务、周概览、快捷操作 | ✅ |
| 练习界面 | 选择题、进度、反馈(对接真实API) | ✅ |
| 错题本页面 | 错题复习、标记已掌握 | ✅ |
| 学情分析页面 | 统计数据、薄弱/掌握知识点 | ✅ |
| 对话界面 | 树结构对话、分区/分支管理 | ✅ |
| KaTeX公式 | LaTeX数学渲染 | ✅ |
| 主题切换 | 暗色/亮色(CSS变量) | ✅ |

### 后端 - 对话系统
| 模块 | 说明 | 状态 |
|------|------|------|
| 数据模型 | TreeNode/Partition/Branch/ContentBlock/ResponseBlock | ✅ |
| JSON存储引擎 | 线程安全+内存缓存 | ✅ |
| 树操作 | 增删改查+分叉+切换+修改+删除 | ✅ |
| 分区分类 | Embedding+关键词权重 | ✅ |
| LLM对话 | DeepSeek流式+上下文构建 | ✅ |
| 多模态回复 | ToolExecutor(5种工具)+ResponseBlock | ✅ |
| WebSocket | 流式token输出+对话管理 | ✅ |
| API路由 | 9 REST + WebSocket | ✅ |

### 后端 - 其他
| 模块 | 说明 | 状态 |
|------|------|------|
| Agent 调度器 | 意图分析 + 情绪感知 | ✅ |
| BKT 引擎 | 贝叶斯知识追踪(增强版) | ✅ |
| LLM 服务 | LiteLLM 封装、流式输出 | ✅ |

---

## 待开发 🔲

### P0 — 下一个必做

| 模块 | 说明 | 依赖 |
|------|------|------|
| 对话系统树结构会话完善 | partition/branch/node 数据持久化+API完整实现 | — |
| 用户按角色/组织隔离 | role + org_id 字段，数据结构预留 | — |

### P1 — 对话×练习联动

| 模块 | 说明 | 依赖 |
|------|------|------|
| 对话内联练习 | 对话中直接做题，不跳转 | P0 |
| 练习结果→对话记忆 | 练习session挂载到branch | P0 |
| 对话上下文→练习选题 | ContextAwarePracticeTrigger | P0 |
| 练习来源标签 | 前端显示练习来自哪个分区/分支 | P0 |
| SharedKnowledgeState | 对话和练习统一知识状态 | P0 |

### P2 — 增强功能

| 模块 | 说明 |
|------|------|
| 用户资料索引(RAG) | PDF/图片上传→OCR→Embedding→语义搜索出题 |
| 行为分析+习惯养成 | 最佳学习时段+番茄钟+TinyHabits |
| 前置知识点卡控 | PREREQUISITES配置+难度调整 |
| 题目质量监控 | 自动淘汰太简单/有歧义的题 |
| B站视频真实搜索API | 替换模拟数据 |
| 文生图集成 | 函数图像/思维导图 |
| 间隔复习系统 | SM-2完整实现+解释能力复习 |
| 跨分区整理 | 自动检测合并相似分区 |

### 前端待完善
- [ ] 对话分区/分支管理完善
- [ ] 知识图谱对接真实数据
- [ ] 错误边界处理
- [ ] 自动化测试

---

## 技术债务
- 后端状态存储用JSON文件(MVP)，需迁移至 PostgreSQL
- Embedding模型未安装(sentence-transformers太大)
- Agent prompt 需要根据实际效果调优
- B站/文生图等工具返回模拟数据
