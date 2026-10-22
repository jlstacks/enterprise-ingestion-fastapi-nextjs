import { formatTimestamp, type Job } from '@/lib/api';
import { StatusPill } from './status-pill';

export function JobsTable({ jobs }: { jobs: Job[] }) {
  return (
    <section className="panel min-w-0 p-6 sm:p-7" aria-labelledby="jobs-title">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="label">04 / JOB MONITOR</p>
          <h2 id="jobs-title" className="section-title">Recent queue activity</h2>
        </div>
        <span className="badge">POLLING / 3 SEC</span>
      </div>
      <div className="mt-6 overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-xs">
          <thead className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
            <tr><th className="table-head">Job</th><th className="table-head">Source</th><th className="table-head">Records</th><th className="table-head">Created</th><th className="table-head">Attempts</th><th className="table-head">Status</th></tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id} className="border-b border-slate-800/80 last:border-0">
                <td className="table-cell font-mono text-cyan">{job.id.slice(0, 8)}</td>
                <td className="table-cell text-slate-200">{job.source}</td>
                <td className="table-cell">{job.item_count}</td>
                <td className="table-cell whitespace-nowrap">{formatTimestamp(job.created_at)}</td>
                <td className="table-cell">{job.attempts}</td>
                <td className="table-cell"><StatusPill status={job.status} /></td>
              </tr>
            ))}
            {jobs.length === 0 && <tr><td className="py-16 text-center text-sm text-slate-500" colSpan={6}>No jobs yet. Submit the demonstration batch to start the pipeline.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
