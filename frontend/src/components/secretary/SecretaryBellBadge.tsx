"use client";

import { useEffect, useState } from "react";

/**
 * SecretaryBellBadge — 秘书铃铛小红点组件
 *
 * 自包含轮询组件：每 60 秒查询待处理提案数量，
 * 在有未读提案时显示带计数的红色圆形徽章。
 * 无需父组件传 props，直接放在导航项旁边即可。
 */
export default function SecretaryBellBadge() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let active = true;

    const fetchCount = async () => {
      try {
        const res = await fetch(
          "/api/secretary/proposals/pending?user_id=default_user"
        );
        if (!res.ok) return;
        const data = await res.json();
        // data is an array of proposals
        if (Array.isArray(data) && active) {
          setCount(data.length);
        }
      } catch {
        // silently fail — badge just won't show
      }
    };

    fetchCount();

    const interval = setInterval(fetchCount, 60_000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  if (count === 0) return null;

  return (
    <span className="absolute -top-1 -right-1.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold leading-none px-1 shadow-sm">
      {count > 99 ? "99+" : count}
    </span>
  );
}
