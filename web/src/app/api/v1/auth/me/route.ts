import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  try {
    const res = await fetch(`${BACKEND}/api/v1/auth/me`, {
      method: "GET",
      headers: {
        Authorization: req.headers.get("authorization") || "",
      },
      cache: "no-store",
    });
    const text = await res.text();
    let data: unknown = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
    return NextResponse.json(data ?? {}, { status: res.status });
  } catch (err) {
    return NextResponse.json({ error: "Auth me failed" }, { status: 502 });
  }
}
