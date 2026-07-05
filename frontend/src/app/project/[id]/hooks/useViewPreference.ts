"use client";

// ============================================================
//  useViewPreference — 项目详情页视图偏好 (Task #89)
// ============================================================

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { authedFetch, API_BASE } from "@/lib/api/api";
import { ProjectViewName, PROJECT_VIEW_NAMES } from "../types";

const DEFAULT_VIEW: ProjectViewName = "document";

export function useViewPreference(projectId: string | undefined) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [view, setViewState] = useState<ProjectViewName>(DEFAULT_VIEW);
  const [loading, setLoading] = useState(true);

  // 1. 初始化：URL ?view= 优先于服务端偏好，缺省回退 default
  useEffect(() => {
    if (!projectId) return;
    const urlView = searchParams?.get("view");
    if (urlView && (PROJECT_VIEW_NAMES as string[]).includes(urlView)) {
      setViewState(urlView as ProjectViewName);
      setLoading(false);
      return;
    }
    // 从服务端拉偏好
    let cancelled = false;
    (async () => {
      try {
        const res = await authedFetch(
          `${API_BASE}/api/settings/view/${projectId}`,
        );
        if (cancelled) return;
        const json = await res.json();
        const v = json.view as ProjectViewName;
        if (v && (PROJECT_VIEW_NAMES as string[]).includes(v)) {
          setViewState(v);
        } else {
          setViewState(DEFAULT_VIEW);
        }
      } catch {
        if (!cancelled) setViewState(DEFAULT_VIEW);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, searchParams]);

  // 2. setView：立即更新本地 state + 同步 URL + 后台 PUT
  const setView = useCallback(
    (next: ProjectViewName) => {
      if (!(PROJECT_VIEW_NAMES as string[]).includes(next)) return;
      setViewState(next);
      // 同步 URL（不刷新页面）
      const url = new URL(window.location.href);
      url.searchParams.set("view", next);
      window.history.replaceState({}, "", url.toString());
      // 后台 PUT 偏好
      if (projectId) {
        authedFetch(`${API_BASE}/api/settings/view/${projectId}`, {
          method: "PUT",
          body: JSON.stringify({ view: next }),
        }).catch(() => {
          // 静默失败，不影响 UX
        });
      }
    },
    [projectId],
  );

  return { view, setView, loading };
}
