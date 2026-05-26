/**
 * Proxy for resume API requests to the backend.
 * Next.js rewrites buffer SSE responses, so we use an explicit
 * API route with fetch + ReadableStream to pass through streaming POST requests.
 * GET/DELETE are also proxied here as a fallback to rewrites.
 *
 * Routes handled here:
 *   - GET    /api/v1/resumes
 *   - GET    /api/v1/resumes/{id}
 *   - POST   /api/v1/resumes/upload
 *   - POST   /api/v1/resumes/{id}/parse-stream
 *   - DELETE /api/v1/resumes/{id}
 *   - GET    /api/v1/resumes/tasks/{taskId}
 */
import { NextRequest } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 300;

const BACKEND = process.env.BACKEND_URL || 'http://localhost:8000';

function buildUrl(request: NextRequest, params: { path: string[] }): { url: string; headers: Headers } {
  const path = params.path.join('/');
  const url = `${BACKEND}/api/v1/resumes${path ? '/' + path : ''}${request.nextUrl.search}`;

  const headers = new Headers(request.headers);
  headers.delete('connection');
  headers.delete('host');
  headers.delete('content-length');

  return { url, headers };
}

function responseHeadersWithProxyMarker(headers: Headers): Headers {
  const responseHeaders = new Headers(headers);
  responseHeaders.set('X-Resume-Proxy', 'app-route');
  return responseHeaders;
}

// POST �?SSE streaming passthrough (parse-stream, upload, etc.)
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
  responseHeaders.set('X-Accel-Buffering', 'no');
  responseHeaders.set('X-Resume-Proxy', 'app-route');
  responseHeaders.delete('Content-Encoding');
  responseHeaders.delete('Content-Length');
  responseHeaders.delete('Transfer-Encoding');

  if (responseHeaders.get('content-type')?.includes('event-stream')) {
    const stream = new ReadableStream({
      async start(controller) {
        const reader = response.body?.getReader();
        if (!reader) {
          controller.close();
          return;
        }

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            controller.enqueue(value);
          }
        } catch (error) {
          controller.error(error);
        } finally {
          controller.close();
          reader.releaseLock();
        }
      },
    });

    return new Response(stream, {
      status: response.status,
      headers: responseHeaders,
    });
  }

  return new Response(response.body, {
    status: response.status,
    headers: responseHeaders,
  });
}

// GET �?proxy list and detail requests
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
    headers: responseHeadersWithProxyMarker(response.headers),
  });
}

// DELETE �?proxy delete requests
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
    headers: responseHeadersWithProxyMarker(response.headers),
  });
}
