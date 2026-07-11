'use client';

import { type ImgHTMLAttributes } from 'react';
import { cn } from '@/lib/utils/utils';

export type AvatarSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

interface AvatarProps extends Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'> {
  src?: string | null;
  alt?: string;
  fallback?: string;
  size?: AvatarSize;
  className?: string;
}

const SIZE_CLS: Record<AvatarSize, string> = {
  xs: 'w-6 h-6 text-[10px]',
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-14 h-14 text-base',
  xl: 'w-20 h-20 text-xl',
};

/**
 * Avatar — 头像组件（Design System 1.0）
 *
 * 支持图片加载失败时显示 fallback 文字。
 */
export function Avatar({ src, alt = '', fallback, size = 'md', className, ...rest }: AvatarProps) {
  const fallbackText = fallback || alt.slice(0, 1).toUpperCase() || '?';

  return (
    <div
      className={cn(
        'relative inline-flex items-center justify-center overflow-hidden rounded-full',
        'bg-surface-hover text-ink-secondary border border-divider',
        SIZE_CLS[size],
        className,
      )}
      title={alt}
    >
      {src ? (
        <img
          src={src}
          alt={alt}
          className="w-full h-full object-cover"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = 'none';
          }}
          {...rest}
        />
      ) : null}
      <span className="font-medium select-none">{fallbackText}</span>
    </div>
  );
}

export default Avatar;
