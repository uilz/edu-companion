/**
 * @节点 引用解析工具 (Task #89)
 *
 * 文档描述中支持 @[节点标题] 语法，渲染为可点击跳转的引用链接。
 * 解析失败或目标不存在时回退为普通文本。
 */

export interface NodeRefToken {
  type: "text" | "ref";
  value: string;
  nodeId?: string;
  refTitle?: string;
}

const REF_PATTERN = /@\[([^\]]+)\]/g;

/**
 * 解析描述文本为 token 数组
 *
 * @param description  原始 description 文本
 * @param nodeResolver  标题 → 节点 id 的解析函数
 * @returns             tokens 数组
 */
export function parseNodeRefs(
  description: string,
  nodeResolver: (title: string) => string | undefined,
): NodeRefToken[] {
  if (!description) return [];
  const tokens: NodeRefToken[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  REF_PATTERN.lastIndex = 0;
  while ((match = REF_PATTERN.exec(description)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ type: "text", value: description.slice(lastIndex, match.index) });
    }
    const refTitle = match[1];
    const nodeId = nodeResolver(refTitle);
    if (nodeId) {
      tokens.push({ type: "ref", value: match[0], nodeId, refTitle });
    } else {
      // 找不到目标节点 → 保留原文本，不解析
      tokens.push({ type: "text", value: match[0] });
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < description.length) {
    tokens.push({ type: "text", value: description.slice(lastIndex) });
  }
  return tokens;
}

/**
 * 用节点列表构造 (title → id) 解析器
 */
export function makeTitleResolver(
  nodes: ReadonlyArray<{ id: string; title: string }>,
): (title: string) => string | undefined {
  const map = new Map<string, string>();
  for (const n of nodes) {
    if (n.title) map.set(n.title, n.id);
  }
  return (title) => map.get(title);
}
