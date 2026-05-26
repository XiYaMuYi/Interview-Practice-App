/**
 * Proxy for POST /api/v1/ai/evaluate-stream → backend /api/v1/ai/evaluate-stream.
 * Forwards SSE responses from the backend directly to the client.
 */
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 300;

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export async function POST(req: NextRequest) {
  const url = `${BACKEND}/api/v1/ai/evaluate-stream`;

  try {
    const forwardHeaders = stripForwardHeaders(req.headers);
    const bodyText = await req.text();
    const res = await fetch(url, {
      method: "POST",
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
    console.error("[evaluate-stream-proxy] POST /api/v1/ai/evaluate-stream failed:", msg);
    return NextResponse.json(
      { error: "AI service request failed", detail: msg },
      { status: 502 }
    );
  }
}
