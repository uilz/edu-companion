/** 工具中文显示名 + 图标映射（与后端 tool_repository.py 保持同步） */
export const TOOL_DISPLAY: Record<string, { zh: string; icon: string }> = {
  rename_conversation: { zh: "自动命名会话", icon: "✏️" },
  search_media: { zh: "搜索学习资源", icon: "🔍" },
  generate_practice: { zh: "生成练习题", icon: "📝" },
  query_question_banks: { zh: "查询题库", icon: "📚" },
  create_question_bank: { zh: "创建题库", icon: "➕" },
  secretary_diagnose: { zh: "学习诊断分析", icon: "🩺" },
  ask_question: { zh: "向学生提问", icon: "❓" },
  generate_image: { zh: "生成图片", icon: "🖼️" },
  generate_mindmap: { zh: "生成思维导图", icon: "🧠" },
  generate_document: { zh: "生成文档", icon: "📄" },
  knowledge_add_node: { zh: "添加知识点", icon: "🌱" },
  knowledge_edit_node: { zh: "编辑知识点", icon: "✍️" },
  knowledge_expand_node: { zh: "展开知识树", icon: "🌳" },
  knowledge_delete_node: { zh: "删除节点", icon: "🗑️" },
  knowledge_add_relation: { zh: "建立知识关联", icon: "🔗" },
  knowledge_get_node_context: { zh: "查询节点上下文", icon: "🔎" },
  knowledge_search_nodes: { zh: "搜索知识节点", icon: "🔍" },
  knowledge_recommend: { zh: "学习推荐", icon: "💡" },
};

export function getToolDisplay(name: string) {
  return TOOL_DISPLAY[name] || { zh: name, icon: "🔧" };
}
