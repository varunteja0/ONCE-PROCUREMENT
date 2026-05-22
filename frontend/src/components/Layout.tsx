import { Outlet } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import { useAuth } from '@/hooks/useAuth';

export default function Layout(): JSX.Element {
  const { user, logout } = useAuth();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 text-slate-900">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header
          className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6"
          role="banner"
        >
          <div className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-slate-900 text-xs font-bold text-white"
            >
              O
            </span>
            <span className="text-base font-semibold tracking-tight">
              Once
            </span>
            <span className="ml-2 hidden text-xs text-slate-500 sm:inline">
              Submit once. Prove it forever.
            </span>
          </div>
          <div className="flex items-center gap-4">
            {user ? (
              <span
                className="hidden text-sm text-slate-600 sm:inline"
                aria-label="Signed-in user email"
              >
                {user.email}
              </span>
            ) : null}
            <button
              type="button"
              onClick={logout}
              aria-label="Log out"
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
            >
              <LogOut aria-hidden="true" className="h-4 w-4" />
              <span>Log out</span>
            </button>
          </div>
        </header>
        <main
          className="min-h-0 flex-1 overflow-auto bg-slate-50 p-6"
          role="main"
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
