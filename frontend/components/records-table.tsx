import { formatTimestamp, type RecordPage } from '@/lib/api';

export function RecordsTable({ page, source, onSourceChange }: { page: RecordPage; source: string; onSourceChange: (value: string) => void }) {
  return (
    <section className="panel p-6 sm:p-7" aria-labelledby="records-title">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="label">05 / RECORDS EXPLORER</p>
          <h2 id="records-title" className="section-title">Persisted events</h2>
        </div>
        <div>
          <label htmlFor="source-filter" className="mb-1.5 block text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Filter by source</label>
          <input id="source-filter" value={source} onChange={(event) => onSourceChange(event.target.value)} placeholder="crm-demo" className="rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-xs text-white outline-none focus:border-cyan" />
        </div>
      </div>
      <div className="mt-6 overflow-x-auto">
        <table className="w-full min-w-[780px] text-left text-xs">
          <thead className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
            <tr><th className="table-head">Record</th><th className="table-head">Source</th><th className="table-head">External ID</th><th className="table-head">Payload</th><th className="table-head">Updated</th></tr>
          </thead>
          <tbody>
            {page.items.map((record) => (
              <tr key={record.id} className="border-b border-slate-800/80 last:border-0">
                <td className="table-cell font-mono text-cyan">#{record.id}</td>
                <td className="table-cell text-slate-200">{record.source}</td>
                <td className="table-cell font-mono">{record.external_id}</td>
                <td className="table-cell max-w-md"><code className="block whitespace-normal break-all text-[11px] leading-5 text-slate-400">{JSON.stringify(record.payload)}</code></td>
                <td className="table-cell whitespace-nowrap">{formatTimestamp(record.updated_at)}</td>
              </tr>
            ))}
            {page.items.length === 0 && <tr><td className="py-16 text-center text-sm text-slate-500" colSpan={5}>No matching records. Completed ingestion jobs will appear here.</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="mt-4 text-xs text-slate-500">Showing {page.items.length} of {page.total} matching records. Retrieval uses versioned Redis caching with PostgreSQL fallback.</p>
    </section>
  );
}
