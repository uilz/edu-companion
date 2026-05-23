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
