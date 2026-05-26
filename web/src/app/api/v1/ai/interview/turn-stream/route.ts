/**
 * Proxy for POST /api/v1/ai/interview/turn-stream â†?backend /api/v1/ai/interview/turn-stream.
 * Forwards SSE responses from the backend directly to the client.
 */
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 300;

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";
const BACKEND_TIMEOUT_MS = 30_000; // 30s timeout for initial task creation

function stripForwardHeaders(headers: Headers): Headers {
  const h = new Headers();
  Array.from(headers.entries()).forEach(([key, value]) => {
    if (
      key.startsWith("sec-ch-") ||
      key.startsWith("sec-fetch-") ||
      key === "purpose" ||
      key === "pragma" ||
      key === "host" ||
      key === "connection" ||
      key === "content-length" ||
      key === "transfer-encoding"
    ) return;
    h.set(key, value);
  });
  return h;
}

export async function POST(req: NextRequest) {
  const url = `${BACKEND}/api/v1/ai/interview/turn-stream`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);

  try {
    const forwardHeaders = stripForwardHeaders(req.headers);
    // Ensure Content-Type is set for JSON bodies
    if (!forwardHeaders.has("content-type")) {
      forwardHeaders.set("content-type", "application/json");
    }
    const bodyText = await req.text();
    const res = await fetch(url, {
      method: "POST",
      headers: forwardHeaders,
      body: bodyText || "{}",
      cache: "no-store",
      redirect: "manual",
      signal: controller.signal,
    });

    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("text/event-stream")) {
      // SSE: pipe the stream directly, but keep the timeout active for the initial response.
      // Long-lived SSE won't be aborted by the initial timeout since fetch() already returned.
      clearTimeout(timeoutId);
      const responseHeaders = new Headers(res.headers);
      responseHeaders.set("Cache-Control", "no-cache");
      responseHeaders.set("Connection", "keep-alive");
      responseHeaders.delete("Content-Encoding");
      responseHeaders.delete("Content-Length");
      return new Response(res.body, {
        status: res.status,
        headers: responseHeaders,
      });
    }

    // Non-SSE response (e.g., validation error JSON).
    const text = await res.text();
    if (!res.ok) {
      console.error(`[turn-stream-proxy] Backend ${res.status} for ${url}: ${text.slice(0, 500)}`);
    }
    let data: unknown = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }
    return NextResponse.json(data ?? {}, { status: res.status });
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    const msg = err instanceof Error ? err.message : String(err);
    const isTimeout = err instanceof DOMException && err.name === "AbortError";
    const isConnectionRefused = msg.includes("ECONNREFUSED") || msg.includes("fetch failed");
    console.error(
      `[turn-stream-proxy] POST ${url} failed: ${isTimeout ? "timeout" : "error"} â€?${msg}`
    );
    return NextResponse.json(
      {
        error: isConnectionRefused ? "Backend service unavailable" : isTimeout ? "Backend request timed out" : "AI service request failed",
        detail: isTimeout ? `Request to ${url} exceeded ${BACKEND_TIMEOUT_MS}ms` : msg,
      },
      { status: 502 }
    );
  }
}
