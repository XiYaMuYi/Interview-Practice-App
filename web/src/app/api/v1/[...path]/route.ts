import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Server-side backend URL (not exposed to browser)
const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  return proxy(req, "GET");
}

export async function POST(req: NextRequest) {
  return proxy(req, "POST");
}

export async function PUT(req: NextRequest) {
  return proxy(req, "PUT");
}

export async function PATCH(req: NextRequest) {
  return proxy(req, "PATCH");
}

export async function DELETE(req: NextRequest) {
  return proxy(req, "DELETE");
}

async function proxy(req: NextRequest, method: string) {
  try {
    // Reconstruct the backend URL from the catch-all path
    const path = req.nextUrl.pathname.replace(/^\/api\/v1/, "/api/v1");
    const search = req.nextUrl.search;
    const url = `${BACKEND}${path}${search}`;

    // Forward headers (except hop-by-hop headers)
    const headers = new Headers();
    req.headers.forEach((value, key) => {
      const lower = key.toLowerCase();
      if (!["host", "connection", "content-length"].includes(lower)) {
        headers.set(key, value);
      }
    });

    // Read body for methods that have one
    let body: string | undefined;
    if (["POST", "PUT", "PATCH"].includes(method)) {
      body = await req.text();
      if (!headers.has("content-type")) {
        headers.set("content-type", "application/json");
      }
    }

    const res = await fetch(url, {
      method,
      headers,
      body,
      cache: "no-store",
    });

    // Forward the response
    const responseHeaders = new Headers();
    res.headers.forEach((value, key) => {
      const lower = key.toLowerCase();
      if (!["content-encoding", "transfer-encoding", "connection"].includes(lower)) {
        responseHeaders.set(key, value);
      }
    });

    // For SSE endpoints, disable buffering
    if (path.includes("stream") || path.includes("events")) {
      responseHeaders.set("Content-Type", "text/event-stream");
      responseHeaders.set("Cache-Control", "no-cache, no-transform");
      responseHeaders.set("Connection", "keep-alive");
      responseHeaders.set("X-Accel-Buffering", "no");
    }

    const text = await res.text();
    return new Response(text, {
      status: res.status,
      headers: responseHeaders,
    });
  } catch (err) {
    console.error(`[proxy ${method}]`, (err as Error).message);
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 502 }
    );
  }
}
