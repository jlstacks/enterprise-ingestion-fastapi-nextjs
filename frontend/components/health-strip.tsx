import type { Health } from '@/lib/api';

function ServiceState({ label, state, healthy }: { label: string; state: string; healthy: boolean }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/45 px-3 py-2">
      <span className={`h-2 w-2 rounded-full ${healthy ? 'bg-mint shadow-[0_0_12px_#5ee4b2]' : 'bg-amber-300'}`} />
      <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">{label}</span>
      <span className="text-xs text-slate-300">{state}</span>
    </div>
  );
}

export function HealthStrip({ health }: { health: Health | null }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4" aria-label="Infrastructure health">
      <ServiceState label="API" state={health?.api ?? 'connecting'} healthy={health?.api === 'online'} />
      <ServiceState label="Postgres" state={health?.database ?? 'connecting'} healthy={health?.database === 'connected'} />
      <ServiceState label="Redis" state={health?.redis ?? 'connecting'} healthy={health?.redis === 'connected'} />
      <ServiceState label="Worker" state={health?.worker ?? 'connecting'} healthy={health?.worker === 'online'} />
    </div>
  );
}
