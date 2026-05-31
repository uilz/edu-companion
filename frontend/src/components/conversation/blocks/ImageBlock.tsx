/** 图像块组件：显示生成的图片及对应的提示词 */
export function ImageBlock({ content }: { content: Record<string, unknown> }) {
  const prompt = (content.prompt as string) || "";
  const url = (content.url as string) || "";

  return (
    <div className="mt-2">
      {url ? (
        <div className="border border-[var(--color-border)] overflow-hidden">
          <img
            src={url}
            alt={prompt || "Generated image"}
            className="w-full max-w-md"
            loading="lazy"
          />
          {prompt && (
            <div className="px-3 py-2 bg-[var(--color-surface)]">
              <div className="text-[10px] text-[var(--color-text-muted)]">
                🎨 {prompt}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
          <div className="text-xs text-[var(--color-text-muted)]">
            🎨 {prompt || "图像"}
          </div>
        </div>
      )}
    </div>
  );
}
