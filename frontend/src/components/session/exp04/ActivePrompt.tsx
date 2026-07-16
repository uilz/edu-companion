"use client";

interface Props {
  prompts: string[];
  onPromptClick: (prompt: string) => void;
}

export default function ActivePrompt({ prompts, onPromptClick }: Props) {
  if (!prompts.length) return null;

  return (
    <div className="flex gap-2 flex-wrap px-5 pb-3" aria-label="active-prompts">
      {prompts.map((prompt) => (
        <button
          key={prompt}
          onClick={() => onPromptClick(prompt)}
          className="px-3.5 py-2 rounded-full bg-surface border border-border/60 text-[13px] text-ink-secondary hover:border-ink-muted hover:text-ink-primary transition-colors"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}
