import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  BACKEND_UNREACHABLE_MESSAGE,
  NetworkError,
  TIMEOUT_MESSAGE,
  api,
  clearTokens,
} from "./api";

/**
 * A fetch that never settles, so the abort path can be exercised without
 * waiting on a real network stack.
 */
function hangingFetch() {
  return vi.fn(
    (_input: RequestInfo | URL, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          const err = new Error("The operation was aborted.");
          err.name = "AbortError";
          reject(err);
        });
      })
  );
}

/** A fetch that records its arguments and returns an empty JSON body. */
function mockOk() {
  return vi.fn((_input: RequestInfo | URL, _init?: RequestInit) =>
    Promise.resolve(new Response("{}", { status: 200 }))
  );
}

function headersFrom(fetchMock: ReturnType<typeof mockOk>): Headers {
  const init = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
  return new Headers(init?.headers);
}

describe("api client failure reporting", () => {
  beforeEach(() => {
    clearTokens();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    clearTokens();
  });

  it("aborts a request that never settles and reports it as a timeout", async () => {
    const fetchMock = hangingFetch();
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.post("/api/v1/auth/login", { email: "a@b.com" }, { timeoutMs: 20 })).rejects.toThrow(
      TIMEOUT_MESSAGE
    );

    // A NetworkError, not an ApiError: nothing reached the API, so this must
    // not be presented to a user as a rejected credential.
    await expect(api.post("/api/v1/auth/login", {}, { timeoutMs: 20 })).rejects.toBeInstanceOf(NetworkError);
  });

  it("reports a refused connection as the backend being unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch")))
    );

    const err = await api.get("/api/v1/auth/me").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(NetworkError);
    expect((err as NetworkError).message).toBe(BACKEND_UNREACHABLE_MESSAGE);
  });

  it("maps a gateway error from the proxy to the unreachable message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("Bad Gateway", { status: 502 })))
    );

    const err = await api.get("/api/v1/auth/me").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(502);
    expect((err as ApiError).message).toBe(BACKEND_UNREACHABLE_MESSAGE);
  });

  it("does not leak raw HTML from a gateway error page into the message", async () => {
    const html = "<html><head><title>502 Bad Gateway</title></head><body>nginx</body></html>";
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(html, { status: 502 }))));

    const err = await api.get("/api/v1/auth/me").catch((e: unknown) => e);
    expect((err as ApiError).message).not.toContain("<html>");
    expect((err as ApiError).message).toBe(BACKEND_UNREACHABLE_MESSAGE);
  });

  it("sends only the auth header, with no local dev-tunnel headers", async () => {
    const fetchMock = mockOk();
    vi.stubGlobal("fetch", fetchMock);

    await api.post("/api/v1/auth/login", { email: "a@b.com" }, { skipAuth: true });

    const headers = headersFrom(fetchMock);
    expect(headers.get("bypass-tunnel-reminder")).toBeNull();
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("does not attach a JSON content type to form uploads", async () => {
    const fetchMock = mockOk();
    vi.stubGlobal("fetch", fetchMock);

    const form = new FormData();
    form.append("image", new Blob(["x"]), "leaf.jpg");
    await api.post("/api/v1/disease/predict", form, { skipAuth: true });

    const headers = headersFrom(fetchMock);
    // The browser must set the multipart boundary itself.
    expect(headers.get("Content-Type")).toBeNull();
  });
});
