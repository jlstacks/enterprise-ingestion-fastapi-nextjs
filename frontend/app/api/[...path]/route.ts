import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext, method: 'GET' | 'POST') {
  const apiBase = process.env.API_INTERNAL_URL || 'http://api:8000';
  const { path } = await context.params;
  const safePath = path.map(encodeURIComponent).join('/');
  const target = `${apiBase.replace(/\/$/, '')}/${safePath}${request.nextUrl.search}`;
  const headers: Record<string, string> = { Accept: 'application/json' };
  const idempotencyKey = request.headers.get('Idempotency-Key');
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
  if (method === 'POST') headers['Content-Type'] = 'application/json';

  try {
    const upstream = await fetch(target, {
      method,
      headers,
      body: method === 'POST' ? await request.text() : undefined,
      cache: 'no-store',
    });
    const response = new NextResponse(await upstream.text(), { status: upstream.status });
    response.headers.set('Content-Type', upstream.headers.get('Content-Type') || 'application/json');
    for (const name of ['X-Cache', 'Idempotency-Replayed']) {
      const value = upstream.headers.get(name);
      if (value) response.headers.set(name, value);
    }
    return response;
  } catch {
    return NextResponse.json({ detail: 'API is unavailable. Check the Docker services.' }, { status: 502 });
  }
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context, 'GET');
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context, 'POST');
}
