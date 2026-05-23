/**
 * Proxy for resume API requests to the backend.
 * Next.js rewrites buffer SSE responses, so we use an explicit
 * API route with fetch + ReadableStream to pass through streaming POST requests.
 * GET/DELETE are also proxied here as a fallback to rewrites.
 */
import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const BACKEND = process.env.BACKEND_URL || 'http://localhost:8000';

function buildUrl(request: NextRequest, params: { path: string[] }): { url: string; headers: Headers; method: string } {
  const path = params.path.join('/');
  const url = `${BACKEND}/api/v1/resumes${path ? '/' + path : ''}`;

  const headers = new Headers(request.headers);
  headers.delete('connection');
  headers.delete('host');
  headers.delete('content-length');

  return { url, headers, method: request.method };
}

// POST — SSE streaming passthrough (parse-stream, upload, etc.)
export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const { url, headers } = buildUrl(request, params);
  const body = await request.arrayBuffer();

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body,
    cache: 'no-store',
  });

  const responseHeaders = new Headers(response.headers);
  responseHeaders.set('Cache-Control', 'no-cache');
  responseHeaders.set('Connection', 'keep-alive');
  responseHeaders.delete('Content-Encoding');
  responseHeaders.delete('Content-Length');

  return new Response(response.body, {
    status: response.status,
    headers: responseHeaders,
  });
}

// GET — proxy list and detail requests
export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const { url, headers } = buildUrl(request, params);

  const response = await fetch(url, {
    method: 'GET',
    headers,
    cache: 'no-store',
  });

  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
}

// DELETE — proxy delete requests
export async function DELETE(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const { url, headers } = buildUrl(request, params);

  const response = await fetch(url, {
    method: 'DELETE',
    headers,
  });

  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
}
