// 导入 clsx 用于条件类名拼接，ClassValue 为其类型定义
import { type ClassValue, clsx } from 'clsx';
// 导入 tailwind-merge 用于智能合并 Tailwind CSS 类名，避免样式冲突
import { twMerge } from 'tailwind-merge';

/**
 * 合并 Tailwind CSS 类名的工具函数
 * 结合 clsx（条件类名拼接）和 twMerge（智能合并 Tailwind 类名冲突）
 * 常用于 shadcn/ui 组件库中动态组合 className
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ══════════════════════════════════════════════════════════════
//  Immutable collection helpers
// ══════════════════════════════════════════════════════════════
/** Map immutable set */
export function mapSet<K, V>(prev: Map<K, V>, key: K, value: V): Map<K, V> {
  const next = new Map(prev);
  next.set(key, value);
  return next;
}
/** Map immutable delete */
export function mapDelete<K, V>(prev: Map<K, V>, key: K): Map<K, V> {
  const next = new Map(prev);
  next.delete(key);
  return next;
}
/** Set immutable add */
export function setAdd(prev: Set<string>, value: string): Set<string> {
  if (prev.has(value)) return prev;
  return new Set(prev).add(value);
}
/** Set immutable delete */
export function setDelete(prev: Set<string>, value: string): Set<string> {
  const next = new Set(prev);
  next.delete(value);
  return next;
}
