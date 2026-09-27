// Client-side API wrapper. Reads token from localStorage.
// All paths are proxied via next.config.js rewrites in dev,
// or hit NEXT_PUBLIC_API_BASE directly in production.

const BASE =
  typeof window === "undefined"
    ? process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"
    : ""; // browser uses same-origin /api/* proxied

export const TOKEN_KEY = "sezer.token";
const EXPIRY_KEY = "sezer.token.expires";
/** Fallback when the server doesn't say — matches the backend's JWT lifetime. */
const DEFAULT_TTL_SECONDS = 24 * 60 * 60;

/** The saved sign-in, or null once it has aged out.
 *
 *  An expired entry is cleared here rather than left to fail on the next
 *  request, so the app lands on the login screen instead of throwing 401s.
 */
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return null;
    const expires = Number(localStorage.getItem(EXPIRY_KEY) || 0);
    if (!expires || Date.now() >= expires) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(EXPIRY_KEY);
      return null;
    }
    return token;
  } catch { return null; }
}

export function setToken(t: string | null, expiresInSeconds = DEFAULT_TTL_SECONDS) {
  if (typeof window === "undefined") return;
  try {
    if (t) {
      localStorage.setItem(TOKEN_KEY, t);
      localStorage.setItem(EXPIRY_KEY, String(Date.now() + expiresInSeconds * 1000));
    } else {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(EXPIRY_KEY);
    }
  } catch {}
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message?: string) {
    super(message || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { form?: FormData; auth?: boolean } = {}
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (!init.form && init.body) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token && init.auth !== false) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
    body: init.form ?? init.body,
    cache: "no-store",
  });

  if (!res.ok) {
    // The sign-in lapsed or was revoked. Send them back to the login screen
    // and never settle: rejecting here would make every caller's catch block
    // paint an error card on a page that is already navigating away.
    if (res.status === 401 && init.auth !== false) {
      logout();
      return new Promise<never>(() => {});
    }
    let detail: unknown = null;
    try { detail = await res.json(); } catch {}
    throw new ApiError(res.status, detail, (detail as any)?.detail || res.statusText);
  }
  if (res.status === 204) return undefined as unknown as T;
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? await res.json() : (await res.text() as unknown as T);
}

export const api = {
  get:  <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put:  <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT",  body: body ? JSON.stringify(body) : undefined }),
  patch:<T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  del:  <T>(path: string) => request<T>(path, { method: "DELETE" }),
  form: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", form }),
};

export function loginWithPin(pin: string) {
  const form = new FormData();
  form.set("username", "owner");
  form.set("password", pin);
  return request<{ access_token: string; token_type: string; expires_in: number }>("/api/auth/login", {
    method: "POST",
    form,
    auth: false,
  });
}

export function logout() {
  setToken(null);
  if (typeof window !== "undefined") window.location.href = "/login";
}
