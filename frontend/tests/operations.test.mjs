import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { apiRequest } from '../lib/api.ts';
import { readOperationalState, servicesOnline } from '../lib/operational-state.ts';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });
const healthy = { status: 'ok', api: 'online', database: 'connected', redis: 'connected', worker: 'online' };

test('503 dependency health replaces green state even if other endpoints fail', async () => {
  globalThis.fetch = async (url) => new Response(JSON.stringify(url === '/api/health'
    ? { ...healthy, status: 'unavailable', redis: 'unavailable', worker: 'unknown' }
    : { detail: 'Database unavailable; retry later' }), { status: 503 });
  let visibleHealth = healthy;
  const snapshot = await readOperationalState('', undefined, (value) => { visibleHealth = value; });
  assert.equal(visibleHealth.redis, 'unavailable');
  assert.equal(servicesOnline(visibleHealth), false);
  assert.equal(snapshot.data, null);
  assert.match(snapshot.error, /stale/);
});

test('a transport outage clears previous green health', async () => {
  globalThis.fetch = async () => { throw new Error('connection refused'); };
  let visibleHealth = healthy;
  await readOperationalState('', undefined, (value) => { visibleHealth = value; });
  assert.equal(visibleHealth, null);
  assert.equal(servicesOnline(visibleHealth), false);
});

test('worker offline is degraded and prevents claiming all services online', async () => {
  globalThis.fetch = async (url) => new Response(JSON.stringify(url === '/api/health'
    ? { ...healthy, status: 'degraded', worker: 'offline' } : {}));
  const snapshot = await readOperationalState('all');
  assert.equal(servicesOnline(snapshot.health), false);
  assert.match(snapshot.error, /degraded/);
});

test('health updates independently of a slow records request', async () => {
  let release;
  let healthUpdated;
  const updated = new Promise((resolve) => { healthUpdated = resolve; });
  globalThis.fetch = async (url) => url.startsWith('/api/records')
    ? await new Promise((resolve) => { release = () => resolve(new Response('{}')); })
    : new Response(JSON.stringify(url === '/api/health' ? healthy : {}));
  const pending = readOperationalState('', undefined, healthUpdated);
  assert.deepEqual(await updated, healthy);
  release();
  assert.equal((await pending).error, '');
});

test('a plain-text server error produces a useful response-contract error', async () => {
  globalThis.fetch = async () => new Response('Internal Server Error', { status: 500 });
  await assert.rejects(apiRequest('jobs'), /invalid response \(500\)/);
});
