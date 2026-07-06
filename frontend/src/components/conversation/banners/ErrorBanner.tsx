"use client";

/**
 * ErrorBanner — API 错误横幅（demo 红色）
 */
export default function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      className="flex-shrink-0 mx-4 mt-2 px-4 py-3 rounded-lg text-sm"
      style={{
        backgroundColor: "var(--banner-error-bg)",
        border: "1px solid var(--banner-error-border)",
        color: "var(--color-red)",
      }}
    >
      {message}
    </div>
  );
}
