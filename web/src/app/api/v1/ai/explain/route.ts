import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  const url = `${BACKEND}/api/v1/ai/explain`;
  console.log(`[ai-proxy] POST ${url}`);

  try {
    const body = await req.json();
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    console.error(`[ai-proxy] POST ${url} failed:`, err);
    return NextResponse.json(
      { error: "AI service request failed" },
      { status: 502 }
    );
  }
}
