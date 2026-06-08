# 对话系统 · 前端设计

> 完整前端设计见 [subsystems/conversation/frontend-design.md](../../subsystems/conversation/frontend-design.md)（迁移中）。

---

## 组件架构

```
LearnPage
├── NewPartitionDialog           — 新建分区模态框
├── SwitchBanner                 — 上下文切换提示横幅
├── MobileBottomSheet            — 移动端底部面板
├── PartitionSidebar             — 侧栏树（分区→领域→专题→对话）
├── MessageList                  — 消息列表
│   └── ResponseBlockRenderer    — 响应块渲染器
└── ConversationChatInput        — 聊天输入框
    └── VoiceRecorder            — 语音录制器
```

## 状态管理

所有状态集中在 `LearnPage` 组件（~20 个 state），子组件通过 props 接收数据和回调。

## 消息渲染

`ResponseBlockRenderer` 按 `type` + `status` 分发渲染：

| 块类型 | 组件 |
|--------|------|
| text | TextBlock |
| video | VideoBlockRouter |
| practice | PracticeBlockRouter → InlinePracticeBlock |
| image | ImageBlock |
| audio | AudioBlock |
| mindmap | MindMapBlock |
| document | DocumentBlock |
| media_search | MediaSearchBlock |
| quote | QuoteBlock |

## 侧栏树

后端提供扁平节点列表，前端构建树结构：

```
后端存储 (PgStorageEngine)         前端渲染 (PartitionSidebar)
Partition → Domain → Topic → Conv  →  TreeItem 层级树
  path: Node[] 字段                   expanded 字段管理展开状态
```

## 子支 UI

- 子支标识嵌入消息气泡内
- 引用块（QuoteBlock）类似文件附件展示
- 子支内支持递归创建更深层级子支
