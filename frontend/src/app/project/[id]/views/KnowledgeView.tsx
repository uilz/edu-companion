"use client";

// ============================================================
//  KnowledgeView — 知识关联视图 (Task #89 保留 + 解耦)
// ============================================================

import { ProjectViewProps } from "../types";
import { NodeCard } from "../components/NodeCard";

export function KnowledgeView({ nodes, onOpenNode }: ProjectViewProps) {
  const linkedNodes = nodes.filter(
    (n) =>
      (n.linked_node_ids && n.linked_node_ids.length > 0) ||
      (n.linked_material_ids && n.linked_material_ids.length > 0) ||
      (n.linked_card_ids && n.linked_card_ids.length > 0),
  );

  return (
    <div>
      <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider mb-3">
        知识关联视图
      </h3>
      {linkedNodes.length === 0 ? (
        <div className="text-center text-ink-secondary py-12 border border-dashed border-divider rounded-lg">
          暂无知识关联。在节点编辑面板中关联 CognitiveNode / Material / FlashCard 后将显示在此。
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {linkedNodes.map((n) => (
            <NodeCard
              key={n.id}
              node={n}
              onOpen={() => onOpenNode(n)}
              footer={
                <div className="flex flex-wrap gap-1 text-xs mt-2">
                  {n.linked_node_ids && n.linked_node_ids.length > 0 && (
                    <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-500">
                      {n.linked_node_ids.length} 知识点
                    </span>
                  )}
                  {n.linked_material_ids && n.linked_material_ids.length > 0 && (
                    <span className="px-2 py-0.5 rounded bg-green-500/10 text-green-500">
                      {n.linked_material_ids.length} 材料
                    </span>
                  )}
                  {n.linked_card_ids && n.linked_card_ids.length > 0 && (
                    <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-500">
                      {n.linked_card_ids.length} 卡片
                    </span>
                  )}
                </div>
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
