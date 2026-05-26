# 🚀 智能伴学系统 — 开发进度

## 最新里程碑: v0.5.0 (Phase 8) ✅

### Phase 8 完成情况

| 项 | 状态 | 备注 |
|----|------|------|
| 知识图谱数据迁移 | ✅ | 10节点从旧JSON迁至cognitive_nodes表 |
| storage 序列化修复 | ✅ | path_id/node_type/is_visible 不再双序列化 |
| WebSocket asyncio 补丁 | ✅ | import asyncio |
| Phase8Sidebar 替换PartitionSidebar | ✅ | 知识图谱树+会话混合展示 |
| Classify 自动归类 | ✅ | 发送消息时 fire-and-forget 调用 /api/v2/classify |
| 旧代码清理 | ✅ | PartitionSidebar.tsx 删除 |
| 蓝线闪现修复 | ✅ | 非会话节点不设borderLeft |
| 后端健康 | ✅ | Phase 8 API 正常返回图节点 |

### 知识图谱结构
- 分区: 数学 (1个)
- 概念: 声母h/n、韵母ao/i、第三声、变调规则、正式与非正式用法 (7个)
- 原子: 问候应答、文化含义 (2个)

### 待未来迭代
- 48h 临时对话清理后台任务
- 旧 partition/domain/topic 表归档
- 前端图谱可视化页（力导向布局）
- Classify 用户确认/选择UI
