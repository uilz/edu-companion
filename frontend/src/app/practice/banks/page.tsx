"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BookOpen, Plus, Loader2, ChevronRight, Library,
} from "lucide-react";

const API = "/api/v7/practice";

export default function PracticeBanksPage() {
  const router = useRouter();
  const [banks, setBanks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/banks`)
      .then(r => r.json())
      .then(data => setBanks(Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="sticky top-0 z-10 bg-[var(--color-bg)]/80 backdrop-blur-sm border-b border-[var(--color-border)]/50">
        <div className="max-w-3xl mx-auto px-4 flex items-center h-12">
          <button onClick={() => router.back()}
            className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] mr-3">
            ← 返回
          </button>
          <Library size={15} className="text-[var(--color-text-muted)] mr-2" />
          <span className="text-sm font-semibold text-[var(--color-text)]">题库浏览</span>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-5">
        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" />
          </div>
        ) : banks.length === 0 ? (
          <div className="text-center py-16">
            <BookOpen size={24} className="mx-auto text-[var(--color-text-muted)] mb-2" />
            <p className="text-sm text-[var(--color-text-muted)]">暂无题库</p>
          </div>
        ) : (
          <div className="space-y-2">
            {banks.map((bank: any) => (
              <div key={bank.id}
                onClick={() => router.push(`/practice/banks/${bank.id}`)}
                className="flex items-center gap-3 p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 cursor-pointer hover:border-[var(--color-accent)]/30 transition-all">
                <div className="w-10 h-10 rounded-lg bg-[var(--color-accent)]/10 flex items-center justify-center">
                  <BookOpen size={18} className="text-[var(--color-accent)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[var(--color-text)] truncate">
                    {bank.name || "未命名题库"}
                  </p>
                  <p className="text-[10px] text-[var(--color-text-muted)]">
                    {bank.description || ""}
                    {bank.total_questions != null ? ` · ${bank.total_questions}题` : ""}
                  </p>
                </div>
                <ChevronRight size={14} className="text-[var(--color-text-muted)]" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
