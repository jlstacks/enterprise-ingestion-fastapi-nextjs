import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Enterprise Ingestion | Operations Control Plane',
  description: 'A working Next.js, FastAPI, Celery, Redis, and PostgreSQL ingestion demonstration.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
