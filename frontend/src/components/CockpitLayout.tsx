import { useEffect } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import { LogOut, Shield } from 'lucide-react';
import { useCockpit } from '@/hooks/useCockpit';
import { Button } from '@/components/ui/Button';
import ActingAsBanner from '@/components/ActingAsBanner';

const NAV = [
  { to: '/cockpit', label: 'Dashboard', end: true },
  { to: '/cockpit/tenants', label: 'Tenants' },
  { to: '/cockpit/operate-as', label: 'Operate As' },
  { to: '/cockpit/audit', label: 'Audit log' },
  { to: '/cockpit/account', label: 'Account' },
];

export default function CockpitLayout(): JSX.Element {
  const { operator, logout, refreshMe } = useCockpit();

  useEffect(() => {
    void refreshMe().catch(() => {
      /* token may be stale; the response interceptor will redirect */
    });
    // run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className="flex min-h-screen w-full flex-col bg-amber-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100"
      data-testid="cockpit-layout"
    >
      <ActingAsBanner />
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-amber-300 bg-amber-200/60 px-4 dark:border-amber-800 dark:bg-amber-950/40 sm:px-6">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-amber-700 dark:text-amber-300" aria-hidden="true" />
          <Link
            to="/cockpit"
            className="text-base font-semibold tracking-tight text-amber-900 dark:text-amber-100"
          >
            Founder Cockpit
          </Link>
          <span className="ml-2 rounded bg-amber-700 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-50">
            internal
          </span>
        </div>
        <div className="flex items-center gap-3">
          {operator ? (
            <span className="text-xs text-amber-900 dark:text-amber-200">
              {operator.email} · {operator.role}
            </span>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              void logout();
            }}
          >
            <LogOut className="mr-1 h-4 w-4" aria-hidden="true" />
            Sign out
          </Button>
        </div>
      </header>
      <div className="flex flex-1">
        <nav
          aria-label="Cockpit navigation"
          className="w-48 shrink-0 border-r border-amber-200 bg-amber-100/50 py-4 dark:border-amber-900 dark:bg-amber-950/30"
        >
          <ul className="space-y-1 px-2">
            {NAV.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    [
                      'block rounded px-3 py-2 text-sm',
                      isActive
                        ? 'bg-amber-300/70 font-semibold text-amber-950 dark:bg-amber-800/60 dark:text-amber-50'
                        : 'text-amber-900 hover:bg-amber-200 dark:text-amber-200 dark:hover:bg-amber-900/40',
                    ].join(' ')
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
