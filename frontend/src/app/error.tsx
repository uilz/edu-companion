'use client'; // 标记为客户端组件，因为使用了 React Hooks 和浏览器事件

import { useEffect } from 'react'; // 引入副作用 Hook，用于错误日志记录

/**
 * 错误边界（Error Boundary）fallback 组件
 * 当页面渲染过程中抛出异常时，Next.js 会自动渲染此组件来替代崩溃的页面
 *
 * @param error   捕获到的错误对象，包含错误信息和可选的 digest（服务端错误标识）
 * @param reset   重置函数，调用后重新渲染原页面组件
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // 组件挂载时或 error 变化时，将错误信息输出到控制台以便调试
  useEffect(() => {
    console.error('Page error:', error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center">
      <div className="text-5xl mb-4">💥</div>
      <h2 className="text-xl font-semibold text-red-500 mb-2">
        页面出错了
      </h2>
      {/* 显示具体错误信息；如果 error.message 为空则展示默认文案 */}
      <p className="text-gray-500 dark:text-gray-400 mb-4 max-w-md text-sm">
        {error.message || '发生了意外错误'}
      </p>
      {/* 点击按钮触发 reset，尝试重新加载页面 */}
      <button
        onClick={reset}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
      >
        再试一次
      </button>
    </div>
  );
}
