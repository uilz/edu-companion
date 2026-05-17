'use client';

interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export default function Card({ title, children, className = "" }: CardProps) {
  return (
    <div
      className={`border border-[var(--color-border)] bg-[var(--color-card)] p-6 ${className}`}
    >
      {title && (
        <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--color-text-muted)] mb-4">
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}
