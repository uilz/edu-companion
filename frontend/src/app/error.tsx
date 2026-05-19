'use client';

import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Page error:', error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center">
      <div className="text-5xl mb-4">💥</div>
      <h2 className="text-xl font-semibold text-red-500 mb-2">
        页面出错了
      </h2>
      <p className="text-gray-500 dark:text-gray-400 mb-4 max-w-md text-sm">
        {error.message || '发生了意外错误'}
      </p>
      <button
        onClick={reset}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
      >
        再试一次
      </button>
    </div>
  );
}
