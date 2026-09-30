"use client";

// Tokens are kept in localStorage rather than cookies. The app can be
// rendered inside a cross-site/embedded preview iframe, and browsers
// increasingly block or partition cookies (and, in some embedding
// contexts, all Web Storage) set from within that kind of frame — which
// would silently break session persistence right after a successful
// login. We prefer localStorage (not subject to the cookie restriction),
// but fall back to an in-memory store if storage access throws or is
// unavailable, so auth still works for the lifetime of the tab even under
// the strictest embedding policy.
const ACCESS_TOKEN_KEY = "bhoomi_access_token";
const REFRESH_TOKEN_KEY = "bhoomi_refresh_token";

let memoryAccessToken: string | undefined;
let memoryRefreshToken: string | undefined;

function safeGetItem(key: string): string | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    return window.localStorage.getItem(key) ?? undefined;
  } catch {
    return undefined;
  }
}

function safeSetItem(key: string, value: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

function safeRemoveItem(key: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore — nothing was persisted if storage is unavailable
  }
}

export function getAccessToken(): string | undefined {
  return safeGetItem(ACCESS_TOKEN_KEY) ?? memoryAccessToken;
}

function getRefreshToken(): string | undefined {
  return safeGetItem(REFRESH_TOKEN_KEY) ?? memoryRefreshToken;
}

export function setTokens(accessToken: string, refreshToken: string) {
  memoryAccessToken = accessToken;
  memoryRefreshToken = refreshToken;
  safeSetItem(ACCESS_TOKEN_KEY, accessToken);
  safeSetItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens() {
  memoryAccessToken = undefined;
  memoryRefreshToken = undefined;
  safeRemoveItem(ACCESS_TOKEN_KEY);
  safeRemoveItem(REFRESH_TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/**
 * Thrown when the request never reached the API: the browser could not connect,
 * or the Next.js proxy could not reach the backend. Kept distinct from
 * ApiError so callers can tell "the backend is down" apart from "your
 * credentials were wrong".
 */
export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

export const BACKEND_UNREACHABLE_MESSAGE =
  "Cannot reach the BHOOMI API. The service may be temporarily unavailable — please try again in a moment.";

function defaultMessageFor(status: number): string {
  if (status === 502 || status === 503 || status === 504) return BACKEND_UNREACHABLE_MESSAGE;
  if (status === 429) return "Too many attempts. Please wait a minute and try again.";
  if (status >= 500) return `The server had a problem (HTTP ${status}). Please try again.`;
  return `Request failed (HTTP ${status}).`;
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;
  try {
    const resp = await request("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    setTokens(data.access_token, data.refresh_token);
    return data.access_token as string;
  } catch {
    return null;
  }
}

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
}

async function parseErrorBody(response: Response): Promise<{ message?: string; code?: string }> {
  const text = await response.text();
  if (!text) return {};
  try {
    const body = JSON.parse(text);
    return {
      message: body?.error?.message || body?.detail || body?.message,
      code: body?.error?.code,
    };
  } catch {
    // Not JSON. The Next.js dev proxy answers with a bare "Internal Server
    // Error" / "Bad Gateway" when the backend is unreachable, so surface that
    // status directly rather than a generic failure.
    return { message: text.trim().slice(0, 200) };
  }
}

async function request(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(path, init);
  } catch {
    throw new NetworkError(BACKEND_UNREACHABLE_MESSAGE);
  }
}

export async function apiFetch<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const isFormData = options.body instanceof FormData;
  const headers = new Headers(options.headers);
  if (!isFormData && !headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token && !options.skipAuth) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response = await request(path, { ...options, headers });

  if (response.status === 401 && !options.skipAuth) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers.set("Authorization", `Bearer ${newToken}`);
      response = await request(path, { ...options, headers });
    }
  }

  if (!response.ok) {
    const { message, code } = await parseErrorBody(response);
    throw new ApiError(message || defaultMessageFor(response.status), response.status, code);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown, options: RequestOptions = {}) =>
    apiFetch<T>(path, { ...options, method: "POST", body: body instanceof FormData ? body : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};
