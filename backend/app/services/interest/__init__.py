"""
InterestExplorer 服务层

按 docs/modules/interest-explorer/overview.md + ADR 0007 实现。
严格遵循以下关键设计:

- **不**调用 LLM (决策 3)
- **不**支持任意 URL 抓取 (决策 5)
- 链接级别去重 (决策 7)
- 3 层标签 (决策 9)
- 本地权重 (决策 10)
- 复用秘书 Proposal 机制 (决策 2)
- 复用 FlashCard 临时状态作为"稍后读"列表

子模块:
- store:        数据访问层 (interest_* 表 CRUD)
- source_fetcher: 信息源抓取 (feedparser + httpx)
- tag_matcher:  兴趣标签匹配 (关键词匹配，不使用 LLM/embedding)
- push_scheduler: 推送调度 (用户配置 + 时区感知)
- cross_module_importer: 跨模块导入 (5 个目标)
- proposal_notifier: Proposal 通知
"""
