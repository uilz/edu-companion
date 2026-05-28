// ── Shared API base URL ──
// Import this from other modules instead of re-declaring API_BASE in each file.
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ══════════════════════════════════════════════════════════════
//  Unified request helpers
// ══════════════════════════════════════════════════════════════
async function apiFetch<T>(base: string, path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text.slice(0, 100)}`);
  }
  return res.json();
}

/** v2 API helper — uses /api/v2 prefix */
export const v2 = <T,>(p: string, o?: RequestInit) => apiFetch<T>("/api/v2", p, o);

/** tree/conversations API helper — uses /api/conversations prefix */
export const tree = <T,>(p: string, o?: RequestInit) => apiFetch<T>("/api/conversations", p, o);
