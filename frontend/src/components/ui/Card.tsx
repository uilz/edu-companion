'use client';

interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
  accent?: boolean;
}

export default function Card({ title, children, className = "", accent = false }: CardProps) {
  return (
    <div
      className={`border bg-[var(--color-card)] p-5 sm:p-6 rounded-lg transition-all duration-200
        ${accent ? 'border-[var(--color-border)] hover:border-[var(--color-accent)]' : 'border-[var(--color-border)]'}
        hover:shadow-md hover:-translate-y-0.5
        ${className}`}
    >
      {title && (
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] mb-4 flex items-center gap-2">
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}
