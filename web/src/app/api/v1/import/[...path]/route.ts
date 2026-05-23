/**
 * Proxy for import API requests to the backend.
 * Handles file upload (multipart/form-data), text import, and SSE streaming.
 */
import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const BACKEND = process.env.BACKEND_URL || 'http://localhost:8000';

function buildUrl(request: NextRequest, params: { path: string[] }): { url: string; headers: Headers; method: string } {
  const path = params.path.join('/');
  const url = `${BACKEND}/api/v1/import${path ? '/' + path : ''}`;

  const headers = new Headers(request.headers);
  headers.delete('connection');
  headers.delete('host');
  headers.delete('content-length');

  return { url, headers, method: request.method };
}

// POST — file upload, text import, streaming
export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const { url, headers } = buildUrl(request, params);

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: request.body,
    duplex: 'half',
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

// GET — supported-formats, etc.
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
