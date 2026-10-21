interface MetricCardProps {
  label: string;
  value: number;
  detail: string;
  accent?: 'cyan' | 'mint' | 'amber' | 'rose';
}

const accents = {
  cyan: 'from-cyan/25 text-cyan',
  mint: 'from-mint/25 text-mint',
  amber: 'from-amber-300/20 text-amber-200',
  rose: 'from-rose-400/20 text-rose-300',
};

export function MetricCard({ label, value, detail, accent = 'cyan' }: MetricCardProps) {
  return (
    <article className="panel relative overflow-hidden p-5 sm:p-6">
      <div className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r ${accents[accent]} to-transparent`} />
      <p className="label">{label}</p>
      <div className="mt-5 flex items-end justify-between gap-4">
        <strong className="text-4xl font-semibold tracking-[-0.04em] text-white sm:text-5xl">
          {value.toLocaleString()}
        </strong>
        <span className={`mb-1 h-2.5 w-2.5 rounded-full ${accents[accent].split(' ')[1]} bg-current shadow-[0_0_18px_currentColor]`} />
      </div>
      <p className="mt-4 text-xs text-slate-400">{detail}</p>
    </article>
  );
}
