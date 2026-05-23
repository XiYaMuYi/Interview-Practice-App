import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
// Increase timeout for long-running LLM calls (can take 30-60s)
export const maxDuration = 300; // 5 minutes max (Vercel); no effect on local dev

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
) {
  const { path } = await ctx.params;
  const url = `${BACKEND}/api/v1/ai/${path.join("/")}`;

  try {
    const body = await req.json();
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      // No explicit timeout — let the LLM call finish naturally
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    console.error(`[ai-proxy] POST /api/v1/${path} failed:`, err);
    return NextResponse.json(
      { error: "AI service request failed" },
      { status: 502 }
    );
  }
}
