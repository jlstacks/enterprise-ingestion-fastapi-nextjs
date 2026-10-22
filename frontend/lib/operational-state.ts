import { apiHealth, apiRequest, type Health, type Job, type Metrics, type RecordPage } from './api.ts';

export function servicesOnline(health: Health | null): boolean {
  return health?.status === 'ok' && health.database === 'connected' &&
    health.redis === 'connected' && health.worker === 'online';
}

export async function readOperationalState(source: string, signal?: AbortSignal, onHealth?: (value: Health | null) => void) {
  const healthRequest = apiHealth({ signal }).then((value) => {
    onHealth?.(value);
    return value;
  }).catch(() => {
    onHealth?.(null);
    return null;
  });
  const sourceQuery = source.trim() ? `&source=${encodeURIComponent(source.trim())}` : '';
  const dataRequest = Promise.all([
    apiRequest<Metrics>('metrics', { signal }),
    apiRequest<Job[]>('jobs?limit=10', { signal }),
    apiRequest<RecordPage>(`records?limit=12${sourceQuery}`, { signal }),
  ]).then(([metrics, jobs, records]) => ({ metrics, jobs, records })).catch(() => null);
  const [health, data] = await Promise.all([healthRequest, dataRequest]);
  const error = !health || health.status === 'unavailable'
    ? 'Services unavailable. Retained counts and records may be stale.'
    : !data ? 'Operational data unavailable. Displayed counts and records may be stale.'
    : health.status === 'degraded' ? 'Services degraded; background processing may be unavailable.' : '';
  return { health, data, error };
}
