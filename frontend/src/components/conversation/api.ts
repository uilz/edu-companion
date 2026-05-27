"use client";

// ══════════════════ API 封装 ══════════════════

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api/conversations${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    cache: 'no-store',
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

// ══════════════════ Phase 8 API 封装 ══════════════════

async function v2Fetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v2${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    cache: 'no-store',
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`v2 API error ${res.status}: ${text}`);
  }
  return res.json();
}

export function fireClassify(convId: string, text: string) {
  v2Fetch("/classify", {
    method: "POST",
    body: JSON.stringify({ conversation_id: convId, message: text }),
  }).catch(() => {}); // fire-and-forget
}
