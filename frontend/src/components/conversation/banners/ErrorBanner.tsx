"use client";

/**
 * ErrorBanner — API 错误横幅
 */
export default function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex-shrink-0 mx-4 mt-2 px-4 py-3 bg-[var(--color-error)]/10 border border-[var(--color-error)]/30 rounded-lg text-sm text-[var(--color-error)]">
      {message}
    </div>
  );
}
