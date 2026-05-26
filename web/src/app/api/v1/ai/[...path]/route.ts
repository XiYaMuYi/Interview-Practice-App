/**
 * Catch-all proxy for AI API requests to the backend.
 * Detects SSE responses (text/event-stream) and passes them through as-is;
 * falls back to JSON for regular API responses.
 *
 * NOTE: The following paths have dedicated proxy routes and do NOT fall through:
 *   - POST /api/v1/ai/explain-stream          â†?explain-stream/route.ts
 *   - POST /api/v1/ai/evaluate-stream         â†?evaluate-stream/route.ts
 *   - POST /api/v1/ai/interview/turn-stream   â†?interview/turn-stream/route.ts
 *
 * This catch-all handles all remaining paths, e.g.:
 *   - POST /api/v1/ai/interview/start
 *   - GET  /api/v1/ai/interview/stats
 *   - Any future AI endpoints without dedicated proxy routes.
 */
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 300;
export const runtime = "nodejs";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

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
      key === "content-length"
    ) return;
    h.set(key, value);
  });
  return h;
}

async function handleProxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const url = `${BACKEND}/api/v1/ai/${path.join("/")}`;
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const bodyText = hasBody ? await req.text() : undefined;

  try {
    const forwardHeaders = stripForwardHeaders(req.headers);
    const res = await fetch(url, {
      method: req.method,
      headers: forwardHeaders,
      body: bodyText,
      cache: "no-store",
      redirect: "manual",
    });

    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("text/event-stream")) {
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

    const text = await res.text();
    let data: unknown = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }
    return NextResponse.json(data ?? {}, { status: res.status });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    const code = (err as { cause?: { code?: string } }).cause?.code
      || (err as { code?: string })?.code
      || "";
    console.error(`[ai-proxy] ${req.method} /api/v1/ai/${path.join("/")} failed:`, msg, code ? `(${code})` : "");
    return NextResponse.json(
      { error: "AI service request failed", detail: msg, code },
      { status: 502 }
    );
  }
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return handleProxy(req, ctx);
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return handleProxy(req, ctx);
}
