"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BookOpen, Plus, ChevronRight, Library,
} from "lucide-react";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { api } from "@/lib/api/api";

export default function PracticeBanksPage() {
  const router = useRouter();
  const [banks, setBanks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<any[]>("/api/practice/banks")
      .then(data => setBanks(Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-page">
      <div className="sticky top-0 z-10 bg-page/80 backdrop-blur-sm border-b border/50">
        <div className="max-w-3xl mx-auto px-4 flex items-center h-12">
          <button onClick={() => router.back()}
            className="text-xs text-muted hover:text mr-3">
            ← 返回
          </button>
          <Library size={15} className="text-muted mr-2" />
          <span className="text-sm font-semibold text">题库浏览</span>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-5">
        {loading ? (
          <PageSkeleton />
        ) : banks.length === 0 ? (
          <div className="text-center py-16">
            <BookOpen size={24} className="mx-auto text-muted mb-2" />
            <p className="text-sm text-muted">暂无题库</p>
          </div>
        ) : (
          <div className="space-y-2">
            {banks.map((bank: any) => (
              <div key={bank.id}
                onClick={() => router.push(`/practice/banks/${bank.id}`)}
                className="flex items-center gap-3 p-4 rounded-xl bg-surface border border/50 cursor-pointer hover:border-accent/30 transition-all">
                <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                  <BookOpen size={18} className="text-accent" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text truncate">
                    {bank.name || "未命名题库"}
                  </p>
                  <p className="text-[10px] text-muted">
                    {bank.description || ""}
                    {bank.total_questions != null ? ` · ${bank.total_questions}题` : ""}
                  </p>
                </div>
                <ChevronRight size={14} className="text-muted" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
