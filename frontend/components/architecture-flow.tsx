const nodes = [
  { name: 'Next.js', detail: 'Dashboard + API proxy', tone: 'cyan' },
  { name: 'FastAPI', detail: 'Validation + job ledger', tone: 'cyan' },
  { name: 'Redis', detail: 'Broker + read cache', tone: 'amber' },
  { name: 'Celery', detail: 'Retrying worker', tone: 'amber' },
  { name: 'PostgreSQL', detail: 'Durable records', tone: 'mint' },
];

export function ArchitectureFlow() {
  return (
    <section className="panel overflow-hidden p-6 sm:p-8" aria-labelledby="architecture-title">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <p className="label">02 / IMPLEMENTED ARCHITECTURE</p>
          <h2 id="architecture-title" className="section-title">Two paths, one source of truth</h2>
        </div>
        <div className="flex flex-wrap gap-2 text-[10px] font-bold uppercase tracking-[0.16em]">
          <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1.5 text-amber-200">Async write path</span>
          <span className="rounded-full border border-cyan/20 bg-cyan/10 px-3 py-1.5 text-cyan">Cache-backed read path</span>
        </div>
      </div>

      <div className="mt-8 grid gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr_auto_1fr] lg:items-center">
        {nodes.map((node, index) => (
          <div className="contents" key={node.name}>
            <div className="rounded-xl border border-slate-700/80 bg-slate-950/45 p-4">
              <span className="text-[10px] font-bold tracking-[0.18em] text-slate-500">0{index + 1}</span>
              <strong className="mt-3 block text-base text-white">{node.name}</strong>
              <span className="mt-1 block text-xs leading-5 text-slate-400">{node.detail}</span>
            </div>
            {index < nodes.length - 1 && <span className="hidden text-center text-xl text-slate-600 lg:block">→</span>}
          </div>
        ))}
      </div>

      <div className="mt-5 grid gap-3 text-xs leading-5 text-slate-400 md:grid-cols-2">
        <p className="rounded-lg border border-amber-300/10 bg-amber-300/[0.04] p-4">
          <strong className="text-amber-200">Write:</strong> accepted requests create a PostgreSQL job before Redis dispatch. Celery upserts records and invalidates cache versions after commit.
        </p>
        <p className="rounded-lg border border-cyan/10 bg-cyan/[0.04] p-4">
          <strong className="text-cyan">Read:</strong> bounded record queries check versioned Redis keys first, then load PostgreSQL and cache the response for a short TTL.
        </p>
      </div>
    </section>
  );
}
