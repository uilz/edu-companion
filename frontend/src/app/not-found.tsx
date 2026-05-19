'use client';

import Link from 'next/link';
import EmptyState from '@/components/ui/EmptyState';

export default function NotFound() {
  return (
    <EmptyState
      icon="🔍"
      title="页面未找到"
      description="你访问的页面不存在或已被移除"
      action={
        <Link
          href="/dashboard"
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors inline-block"
        >
          返回首页
        </Link>
      }
    />
  );
}
