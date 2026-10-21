export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed';

export interface Job {
  id: string;
  source: string;
  status: JobStatus;
  item_count: number;
  attempts: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface RecordItem {
  id: number;
  job_id: string;
  source: string;
  external_id: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface RecordPage {
  items: RecordItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface Metrics {
  records: number;
  jobs: number;
  queued: number;
  processing: number;
  completed: number;
  failed: number;
}

export interface Health {
  status: 'ok' | 'degraded' | 'unavailable';
  api: 'online';
  database: 'connected' | 'unavailable';
  redis: 'connected' | 'unavailable';
  worker: 'online' | 'offline' | 'unknown';
}

export const emptyMetrics: Metrics = {
  records: 0,
  jobs: 0,
  queued: 0,
  processing: 0,
  completed: 0,
  failed: 0,
};

async function request<T>(path: string, options?: RequestInit, healthResponse = false): Promise<T> {
  const timeout = AbortSignal.timeout(8000);
  const signal = options?.signal ? AbortSignal.any([options.signal, timeout]) : timeout;
  const response = await fetch(`/api/${path}`, { cache: 'no-store', ...options, signal });
  let value: T & { detail?: string | unknown };
  try {
    value = await response.json();
  } catch {
    throw new Error(`API returned an invalid response (${response.status})`);
  }
  const healthValue = value as unknown as Partial<Health>;
  const unavailableHealth = healthResponse && response.status === 503 &&
    healthValue.status === 'unavailable' && healthValue.api === 'online';
  if (!response.ok && !unavailableHealth) {
    const detail = typeof value.detail === 'string' ? value.detail : JSON.stringify(value.detail);
    throw new Error(detail || `API request failed (${response.status})`);
  }
  return value;
}

export async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  return request<T>(path, options);
}

export async function apiHealth(options?: RequestInit): Promise<Health> {
  return request<Health>('health', options, true);
}

export function formatTimestamp(value: string | null): string {
  if (!value) return '—';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
}
