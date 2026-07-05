"use client";

// ============================================================
//  VersionHistory — 节点版本历史弹窗 (Task #89 从 page.tsx 提取)
// ============================================================

import { useState } from "react";
import { X } from "lucide-react";
import { ProjectNode, Version, formatDate } from "../types";

export interface VersionHistoryProps {
  versions: Version[];
  node: ProjectNode;
  onClose: () => void;
  onRollback: (version: number, fields?: string[]) => Promise<void>;
  onDiff: (a: number, b: number) => Promise<void>;
}

export function VersionHistory({
  versions,
  node,
  onClose,
  onRollback,
  onDiff,
}: VersionHistoryProps) {
  const [a, setA] = useState<number | null>(null);
  const [b, setB] = useState<number | null>(null);

  return (
    <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
      <div className="bg-page rounded-xl border border-divider w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-divider">
          <h2 className="text-lg font-semibold text-ink-primary">版本历史 — {node.title}</h2>
          <button onClick={onClose} className="p-1.5 rounded text-ink-secondary hover:text-ink-primary">
            <X size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {versions.length === 0 ? (
            <p className="text-ink-secondary text-center py-8">暂无历史版本</p>
          ) : (
            <div className="space-y-2">
              {versions.map((v) => (
                <div
                  key={v.version_id}
                  className="p-3 rounded-lg border border-divider bg-surface"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-ink-primary">
                        v{v.version_number}
                        {v.is_rollback && (
                          <span className="ml-2 text-xs text-amber-500">
                            回滚自 v{v.rolled_back_from_version}
                          </span>
                        )}
                        <span className="ml-2 text-xs text-ink-secondary">
                          [{v.change_source}]
                        </span>
                      </div>
                      <div className="text-xs text-ink-secondary mt-1">
                        {formatDate(v.created_at)} · {v.changed_fields.join(", ")}
                      </div>
                      {v.diff_summary && (
                        <div className="text-xs text-ink-secondary mt-1">{v.diff_summary}</div>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => {
                          if (a === null) setA(v.version_number);
                          else if (b === null) setB(v.version_number);
                          else { setA(v.version_number); setB(null); }
                        }}
                        className={`px-2 py-1 text-xs rounded ${
                          a === v.version_number || b === v.version_number
                            ? "bg-[var(--color-accent)] text-white"
                            : "bg-surface-hover text-ink-secondary hover:text-ink-primary"
                        }`}
                      >
                        {a === v.version_number ? "A" : b === v.version_number ? "B" : "选择"}
                      </button>
                      <button
                        onClick={() => onRollback(v.version_number)}
                        className="px-2 py-1 text-xs rounded text-ink-secondary hover:text-ink-primary hover:bg-surface-hover"
                      >
                        回滚到此版
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        {a !== null && b !== null && (
          <div className="p-3 border-t border-divider flex justify-end">
            <button
              onClick={() => onDiff(a, b)}
              className="px-3 py-1.5 rounded-lg bg-[var(--color-accent)] text-white text-sm hover:opacity-90"
            >
              对比 v{a} ↔ v{b}
            </button>
          </div>
        )}
        {a !== null && b === null && (
          <div className="p-3 border-t border-divider text-xs text-ink-secondary text-center">
            请再选一个版本作为 B 进行对比
          </div>
        )}
      </div>
    </div>
  );
}
