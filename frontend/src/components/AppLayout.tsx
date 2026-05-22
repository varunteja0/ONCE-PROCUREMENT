import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { LogOut, Menu, X } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import { ThemeToggle } from '@/components/ThemeToggle';
import { IdleGuard } from '@/components/IdleGuard';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';

export default function AppLayout(): JSX.Element {
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <IdleGuard />
      <Sidebar mobileOpen={mobileOpen} onNavigate={() => setMobileOpen(false)} />
      {mobileOpen ? (
        <button
          type="button"
          aria-label="Close navigation overlay"
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-20 bg-slate-900/40 md:hidden"
        />
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col">
        <header
          className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 dark:border-slate-800 dark:bg-slate-900 sm:px-6"
          role="banner"
        >
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'}
              aria-expanded={mobileOpen}
              className="md:hidden"
              onClick={() => setMobileOpen((o) => !o)}
            >
              {mobileOpen ? (
                <X className="h-4 w-4" aria-hidden="true" />
              ) : (
                <Menu className="h-4 w-4" aria-hidden="true" />
              )}
            </Button>
            <span
              aria-hidden="true"
              className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-slate-900 text-xs font-bold text-white dark:bg-slate-100 dark:text-slate-900"
            >
              O
            </span>
            <span className="text-base font-semibold tracking-tight">Once</span>
            <span className="ml-2 hidden text-xs text-slate-500 dark:text-slate-400 sm:inline">
              Submit once. Prove it forever.
            </span>
          </div>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            {user ? (
              <span
                className="hidden text-sm text-slate-600 dark:text-slate-300 sm:inline"
                aria-label="Signed-in user email"
              >
                {user.email}
              </span>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              onClick={logout}
              aria-label="Log out"
              leadingIcon={<LogOut className="h-3.5 w-3.5" />}
            >
              Log out
            </Button>
          </div>
        </header>
        <main
          className="min-h-0 flex-1 overflow-auto bg-slate-50 p-4 dark:bg-slate-950 sm:p-6"
          role="main"
          id="main-content"
        >
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
