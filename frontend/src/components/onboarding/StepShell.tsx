// --- L3.6 onboarding ---
import type { ReactNode } from 'react';
import ProgressRail from './ProgressRail';

interface StepShellProps {
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export default function StepShell({
  title,
  description,
  children,
  footer,
}: StepShellProps): JSX.Element {
  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-950">
      <aside className="hidden w-72 shrink-0 border-r border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900 md:block">
        <div className="mb-6 text-lg font-semibold text-slate-900 dark:text-slate-100">
          Once
        </div>
        <ProgressRail />
      </aside>
      <main className="flex-1 px-4 py-10 sm:px-8 md:px-12">
        <div className="mx-auto w-full max-w-2xl">
          <header className="mb-6">
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              {title}
            </h1>
            {description ? (
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {description}
              </p>
            ) : null}
          </header>
          <section
            className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
            aria-labelledby="onboarding-step"
          >
            {children}
          </section>
          {footer ? <div className="mt-4">{footer}</div> : null}
        </div>
      </main>
    </div>
  );
}
// --- /L3.6 onboarding ---
