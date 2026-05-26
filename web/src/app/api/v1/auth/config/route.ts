import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/api/v1/auth/config`, { cache: "no-store" });
    const text = await res.text();
    let data: unknown = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
    return NextResponse.json(data ?? {}, { status: res.status });
  } catch {
    return NextResponse.json({ auth_enabled: false, public_mode: true }, { status: 200 });
  }
}
