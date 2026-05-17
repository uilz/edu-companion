"use client";

interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export default function Card({ title, children, className = "" }: CardProps) {
  return (
    <div
      className={`border border-[#262626] bg-[#0d0d0d] p-6 ${className}`}
    >
      {title && (
        <h3 className="text-xs font-bold uppercase tracking-widest text-[#737373] mb-4">
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}
