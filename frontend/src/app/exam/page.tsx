"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { authedFetch } from "@/lib/api/api";
import {
  FileText, Clock, AlertTriangle, Loader2, ChevronRight,
  Brain, BookOpen,
} from "lucide-react";
import ExamPanel from "@/components/practice/panels/ExamPanel";

type Phase = "select" | "exam";

export default function ExamPage() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("select");
  const [banks, setBanks] = useState<any[]>([]);
  const [selectedBank, setSelectedBank] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authedFetch("/api/practice/banks")
      .then((r) => r.json())
      .then((data) => {
        setBanks(Array.isArray(data) ? data : data?.items || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (phase === "exam" && selectedBank) {
    return (
      <div className="min-h-screen bg-page">
        <div className="max-w-4xl mx-auto" style={{ height: "100vh" }}>
          <ExamPanel
            bankId={selectedBank.id}
            bankName={selectedBank.name}
            onClose={() => setPhase("select")}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-page px-4 py-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => router.back()}
          className="text-[11px] text-muted hover:text">
          ← 返回
        </button>
        <span className="text-[11px] text-muted">|</span>
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-danger" />
          <h1 className="text-base font-bold text">模拟考试</h1>
        </div>
      </div>

      {/* 说明 */}
      <div className="p-4 rounded-xl bg-danger/5 border border-danger/20 mb-6">
        <div className="flex items-start gap-3">
          <AlertTriangle size={16} className="text-danger mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-[12px] font-medium text-danger mb-1">考试须知</p>
            <ul className="text-[10px] text-danger/70 space-y-1 leading-relaxed">
              <li>• 选择题库和考试时长后开始计时答题</li>
              <li>• 答题卡可随时查看已答/未答题目</li>
              <li>• 到时间自动交卷，未答题目记错</li>
              <li>• 交卷后生成成绩报告（含逐题分析）</li>
            </ul>
          </div>
        </div>
      </div>

      {/* 题库选择 */}
      <h2 className="text-[11px] font-medium text-muted mb-3 uppercase tracking-wider">选择题库</h2>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={20} className="animate-spin text-muted" />
        </div>
      ) : banks.length === 0 ? (
        <div className="text-center py-12">
          <BookOpen size={24} className="mx-auto text-muted mb-3" />
          <p className="text-[13px] text-muted">暂无题库</p>
          <p className="text-[10px] text-muted mt-1">请先在练习中生成题目</p>
        </div>
      ) : (
        <div className="space-y-2">
          {banks.map((bank) => (
            <button key={bank.id} onClick={() => { setSelectedBank(bank); setPhase("exam"); }}
              className="w-full flex items-center justify-between p-4 rounded-xl bg-surface border border/50 hover:border-danger/30 transition-all">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-danger/10 flex items-center justify-center">
                  <FileText size={18} className="text-danger" />
                </div>
                <div className="text-left">
                  <p className="text-[13px] font-medium text">{bank.name}</p>
                  <p className="text-[10px] text-muted">{bank.question_count || 0} 道题</p>
                </div>
              </div>
              <ChevronRight size={16} className="text-muted" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
