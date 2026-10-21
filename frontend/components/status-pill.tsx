import type { JobStatus } from '@/lib/api';

const styles: Record<JobStatus, string> = {
  queued: 'border-amber-400/20 bg-amber-400/10 text-amber-200',
  processing: 'border-cyan/20 bg-cyan/10 text-cyan',
  completed: 'border-mint/20 bg-mint/10 text-mint',
  failed: 'border-rose-400/20 bg-rose-400/10 text-rose-300',
};

export function StatusPill({ status }: { status: JobStatus }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] ${styles[status]}`}>
      {status}
    </span>
  );
}
