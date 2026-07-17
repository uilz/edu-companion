"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { authedFetch } from "@/lib/api/api";

// ── 类型 ──────────────────────────────────────────────────

interface ProfilePref {
  label: string;
  value: string;
}

interface ProfileData {
  mirror_narrative: string;
  prefs: ProfilePref[];
}

// ── 组件 ──────────────────────────────────────────────────

export default function ProfilePage() {
  const [data, setData] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadProfile();
  }, []);

  async function loadProfile() {
    setLoading(true);
    setError(null);
    try {
      const res = await authedFetch("/api/profile");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json as ProfileData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  // ── Loading ──
  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  // ── Error ──
  if (error) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12 text-center">
        <p className="text-red-500 mb-4">加载失败：{error}</p>
        <Button variant="outline" onClick={loadProfile}>重试</Button>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-8 fade-in">
      {/* ── 页面标题 ── */}
      <h1 className="text-[28px] font-bold tracking-[-0.02em] mb-6">
        苹果果眼中的你
      </h1>

      {/* ── 镜像叙事 ── */}
      <section
        className="profile-mirror"
        dangerouslySetInnerHTML={{ __html: data.mirror_narrative }}
      />

      {/* ── 关于你的学习 ── */}
      <section className="space-y-3">
        <h3 className="text-[13px] font-semibold text-muted-foreground uppercase tracking-[0.05em] mb-3">
          关于你的学习
        </h3>
        <div className="flex flex-col gap-2.5">
          {data.prefs.map((p) => (
            <div
              key={p.label}
              className="flex justify-between items-center bg-card border rounded-xl p-4"
            >
              <span className="text-sm text-ink-secondary">{p.label}</span>
              <span className="text-sm font-semibold">{p.value}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
