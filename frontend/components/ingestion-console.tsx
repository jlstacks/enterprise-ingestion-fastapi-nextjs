import { useState } from 'react';

import { apiRequest, type Job } from '@/lib/api';

export const samplePayload = {
  source: 'crm-demo',
  items: [
    { external_id: 'opp-1042', payload: { account: 'Northstar Health', event: 'qualified', value: 85000 } },
    { external_id: 'opp-1043', payload: { account: 'Evergreen Labs', event: 'stage_changed', stage: 'Review' } },
    { external_id: 'opp-1044', payload: { account: 'Seabright Systems', event: 'created', value: 142000 } },
  ],
};

export function IngestionConsole({ online, onAccepted }: { online: boolean; onAccepted: (job: Job) => void }) {
  const [body, setBody] = useState(JSON.stringify(samplePayload, null, 2));
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState('Demonstration data only. Edit or submit this sample batch.');
  const [error, setError] = useState('');

  async function submit() {
    setSending(true);
    setError('');
    try {
      const parsed: unknown = JSON.parse(body);
      const job = await apiRequest<Job>('ingest', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': crypto.randomUUID(),
        },
        body: JSON.stringify(parsed),
      });
      setNotice(`Job ${job.id.slice(0, 8)} accepted with ${job.item_count} record${job.item_count === 1 ? '' : 's'}.`);
      onAccepted(job);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? 'Invalid JSON. Correct the payload and try again.' : (caught as Error).message);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="panel p-6 sm:p-7" aria-labelledby="ingestion-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label">03 / INGESTION CONSOLE</p>
          <h2 id="ingestion-title" className="section-title">Submit a validated batch</h2>
        </div>
        <span className="badge">DEMO PAYLOAD</span>
      </div>
      <p className="mt-4 text-sm leading-6 text-slate-400">
        FastAPI validates 1–100 items, persists a job, and returns HTTP 202 before Celery completes processing.
      </p>
      <label htmlFor="payload" className="sr-only">JSON ingestion payload</label>
      <textarea
        id="payload"
        spellCheck={false}
        value={body}
        onChange={(event) => setBody(event.target.value)}
        className="mt-5 h-72 w-full resize-y rounded-xl border border-slate-700 bg-slate-950/80 p-4 font-mono text-xs leading-6 text-cyan outline-none transition focus:border-cyan focus:ring-2 focus:ring-cyan/10"
      />
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button className="primary-button" type="button" onClick={submit} disabled={sending || !online}>
          {sending ? 'Submitting…' : 'Run ingestion job'} <span aria-hidden="true">→</span>
        </button>
        <button className="text-xs font-semibold text-slate-400 hover:text-white" type="button" onClick={() => setBody(JSON.stringify(samplePayload, null, 2))}>
          Reset demonstration data
        </button>
      </div>
      <p className="mt-4 text-xs leading-5 text-slate-400" role="status">{notice}</p>
      {error && <p className="mt-3 rounded-lg border border-rose-400/20 bg-rose-400/10 p-3 text-xs text-rose-200" role="alert">{error}</p>}
    </section>
  );
}
