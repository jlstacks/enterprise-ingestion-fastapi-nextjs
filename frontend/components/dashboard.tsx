'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { emptyMetrics, type Health, type Job, type Metrics, type RecordPage } from '@/lib/api';
import { readOperationalState, servicesOnline } from '@/lib/operational-state';
import { ArchitectureFlow } from './architecture-flow';
import { HealthStrip } from './health-strip';
import { IngestionConsole } from './ingestion-console';
import { JobsTable } from './jobs-table';
import { MetricCard } from './metric-card';
import { RecordsTable } from './records-table';

const emptyPage: RecordPage = { items: [], total: 0, limit: 12, offset: 0 };

export function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics>(emptyMetrics);
  const [health, setHealth] = useState<Health | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [records, setRecords] = useState<RecordPage>(emptyPage);
  const [source, setSource] = useState('');
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const generation = useRef(0);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const current = ++generation.current;
    const snapshot = await readOperationalState(source, signal, (nextHealth) => {
      if (current === generation.current && !signal?.aborted) setHealth(nextHealth);
    });
    if (current !== generation.current || signal?.aborted) return;
    setHealth(snapshot.health);
    setError(snapshot.error);
    if (snapshot.data) {
      setMetrics(snapshot.data.metrics);
      setJobs(snapshot.data.jobs);
      setRecords(snapshot.data.records);
      setLastUpdated(new Date());
    }
  }, [source]);

  useEffect(() => {
    const controller = new AbortController();
    const kickoff = window.setTimeout(() => void refresh(controller.signal), 0);
    const timer = window.setInterval(() => void refresh(controller.signal), 3000);
    return () => {
      controller.abort();
      generation.current += 1;
      window.clearTimeout(kickoff);
      window.clearInterval(timer);
    };
  }, [refresh]);

  function accepted(job: Job) {
    setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)].slice(0, 10));
    window.setTimeout(() => void refresh(), 700);
  }

  const online = servicesOnline(health);

  return (
    <main className="mx-auto min-h-screen w-[min(1440px,calc(100%-2rem))] pb-12 sm:w-[min(1440px,calc(100%-4rem))]">
      <header className="flex min-h-24 flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 py-5">
        <div className="flex items-center gap-4">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-cyan/30 bg-cyan/10 font-black tracking-[-0.08em] text-cyan">EI</div>
          <div><strong className="block text-sm tracking-wide text-white">ENTERPRISE INGESTION</strong><span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Operations control plane</span></div>
        </div>
        <div className="flex items-center gap-4">
          <span className={`flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.15em] ${online ? 'text-mint' : 'text-amber-200'}`}><i className="h-2 w-2 rounded-full bg-current shadow-[0_0_12px_currentColor]" />{online ? 'Core services online' : health ? 'Services degraded' : 'Services unavailable'}</span>
          <a className="rounded-lg border border-slate-700 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-300 transition hover:border-cyan hover:text-cyan" href={process.env.NEXT_PUBLIC_API_DOCS_URL || 'http://localhost:8000/docs'} target="_blank" rel="noreferrer">OpenAPI docs ↗</a>
        </div>
      </header>

      <section className="grid gap-10 py-14 lg:grid-cols-[1.1fr_.9fr] lg:items-end lg:py-20">
        <div>
          <p className="label">DISTRIBUTED SYSTEMS / WORKING DEMONSTRATION</p>
          <h1 className="mt-5 max-w-4xl text-5xl font-semibold leading-[.98] tracking-[-0.055em] text-white sm:text-7xl">Move data without <span className="text-cyan">blocking the request.</span></h1>
          <p className="mt-6 max-w-2xl text-base leading-7 text-slate-400">A five-service pipeline that validates incoming events, tracks durable job state, retries transient worker failures, and serves bounded record views through a short-lived Redis cache.</p>
        </div>
        <div>
          <HealthStrip health={health} />
          <p className="mt-3 text-right text-[10px] uppercase tracking-[0.13em] text-slate-600">{lastUpdated ? `Last refreshed ${lastUpdated.toLocaleTimeString()}` : 'Awaiting first health response'}</p>
        </div>
      </section>

      {error && <div className="mb-5 rounded-xl border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-200" role="alert">{error}</div>}

      <section aria-labelledby="overview-title">
        <div className="mb-5 flex items-end justify-between">
          <div><p className="label">01 / OPERATIONAL OVERVIEW</p><h2 id="overview-title" className="section-title">Pipeline at a glance</h2></div>
          <span className="badge">{error ? 'DATA MAY BE STALE' : 'CACHED DATABASE COUNTS'}</span>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard label="Persisted records" value={metrics.records} detail="Current PostgreSQL rows" accent="cyan" />
          <MetricCard label="Total jobs" value={metrics.jobs} detail="Durable job ledger" accent="cyan" />
          <MetricCard label="Completed" value={metrics.completed} detail="Worker commits" accent="mint" />
          <MetricCard label="Active / queued" value={metrics.processing + metrics.queued} detail="Outstanding work" accent="amber" />
          <MetricCard label="Failed" value={metrics.failed} detail="Requires inspection" accent="rose" />
        </div>
      </section>

      <div className="mt-5"><ArchitectureFlow /></div>
      <div className="mt-5 grid gap-5 xl:grid-cols-[.9fr_1.1fr]"><IngestionConsole online={online} onAccepted={accepted} /><JobsTable jobs={jobs} /></div>
      <div className="mt-5"><RecordsTable page={records} source={source} onSourceChange={setSource} /></div>

      <footer className="mt-10 flex flex-col justify-between gap-3 border-t border-slate-800 py-7 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-600 sm:flex-row">
        <span>Enterprise ingestion / local demonstration</span>
        <span>No production telemetry or benchmark claims</span>
      </footer>
    </main>
  );
}
