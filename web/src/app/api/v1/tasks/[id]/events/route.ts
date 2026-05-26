/**
 * Proxy for GET /api/v1/tasks/[id]/events �?backend /api/v1/tasks/{id}/events.
 * Streams SSE task progress events from the backend directly to the client.
 */
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 300;

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> }
) {
  const { id: taskId } = await ctx.params;
  const url = `${BACKEND}/api/v1/tasks/${taskId}/events`;

  try {
    const headers = new Headers();
    headers.set("Accept", "text/event-stream");
    headers.set("Cache-Control", "no-cache");

    const res = await fetch(url, {
      method: "GET",
      headers,
      cache: "no-store",
      redirect: "manual",
    });

    const responseHeaders = new Headers(res.headers);
    responseHeaders.set("Cache-Control", "no-cache, no-transform");
    responseHeaders.set("Connection", "keep-alive");
    responseHeaders.delete("Content-Encoding");
    responseHeaders.delete("Content-Length");

    return new Response(res.body, {
      status: res.status,
      headers: responseHeaders,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("[tasks-events-proxy] GET /api/v1/tasks/{id}/events failed:", msg);
    return NextResponse.json(
      { error: "Task events request failed", detail: msg },
      { status: 502 }
    );
  }
}
