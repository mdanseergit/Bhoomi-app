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
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("Bad Gateway", { status: 502 })))
    );

    const pending = api.get("/api/v1/auth/me").catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(60_000);
    const err = await pending;

    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(502);
    expect((err as ApiError).message).toBe(BACKEND_UNREACHABLE_MESSAGE);
    vi.useRealTimers();
  });

  it("does not leak raw HTML from a gateway error page into the message", async () => {
    vi.useFakeTimers();
    const html = "<html><head><title>502 Bad Gateway</title></head><body>nginx</body></html>";
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(html, { status: 502 }))));

    const pending = api.get("/api/v1/auth/me").catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(60_000);
    const err = await pending;

    expect((err as ApiError).message).not.toContain("<html>");
    expect((err as ApiError).message).toBe(BACKEND_UNREACHABLE_MESSAGE);
    vi.useRealTimers();
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

describe("cold start retries", () => {
  beforeEach(() => {
    clearTokens();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    clearTokens();
  });

  /** Resolves once the pending retry timers have been flushed. */
  async function settle() {
    await vi.advanceTimersByTimeAsync(60_000);
  }

  it("retries a read that fails with a gateway error and returns the eventual success", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("Bad Gateway", { status: 502 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ farms: [] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const pending = api.get("/api/v1/farms");
    await settle();

    await expect(pending).resolves.toEqual({ farms: [] });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("gives up after a bounded number of attempts rather than retrying forever", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response("Bad Gateway", { status: 502 })));
    vi.stubGlobal("fetch", fetchMock);

    const pending = api.get("/api/v1/farms").catch((e: unknown) => e);
    await settle();

    const err = await pending;
    expect((err as ApiError).status).toBe(502);
    // One initial attempt plus the two configured retries.
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("does not retry a rejected credential", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response("{}", { status: 401 })));
    vi.stubGlobal("fetch", fetchMock);

    await api.get("/api/v1/farms").catch(() => undefined);
    await settle();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry a write, so a submission cannot be duplicated", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response("Service Unavailable", { status: 503 })));
    vi.stubGlobal("fetch", fetchMock);

    const err = await api.post("/api/v1/advisories", { farm_id: 1 }, { skipAuth: true }).catch((e: unknown) => e);
    await settle();

    expect((err as ApiError).status).toBe(503);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry a 500, which is a server fault rather than a cold start", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response("boom", { status: 500 })));
    vi.stubGlobal("fetch", fetchMock);

    await api.get("/api/v1/farms").catch(() => undefined);
    await settle();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
