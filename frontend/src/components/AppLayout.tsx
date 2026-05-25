import { ErrorBoundary } from "@/components/ErrorBoundary";
import { IdleGuard } from "@/components/IdleGuard";
import Sidebar from "@/components/Sidebar";
import { TenantChip } from "@/components/TenantChip";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import { ChevronDown, KeyRound, LogOut, Menu, Repeat, Settings as SettingsIcon, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";

export default function AppLayout(): JSX.Element {
  const { user, tenantId, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const tenantSwitcherEnabled =
    import.meta.env.VITE_TENANT_SWITCHER === "true" || import.meta.env.VITE_TENANT_SWITCHER === "1";

  useEffect(() => {
    setMobileOpen(false);
    setMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    function onDown(e: MouseEvent): void {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKey(e: KeyboardEvent): void {
      if (e.key === "Escape") setMenuOpen(false);
    }
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const initial = user?.email?.[0]?.toUpperCase() ?? "?";
  const displayName = user?.full_name || user?.email || "Account";

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
              aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
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
            {tenantId ? <TenantChip tenantId={tenantId} className="hidden sm:inline-flex" /> : null}
            <ThemeToggle />
            <div ref={menuRef} className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((o) => !o)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                aria-label="Open account menu"
                className={cn(
                  "inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-2 py-1 text-sm text-slate-700 transition hover:bg-slate-50",
                  "dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800",
                  "focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900",
                )}
              >
                <span
                  aria-hidden="true"
                  className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white dark:bg-slate-100 dark:text-slate-900"
                >
                  {initial}
                </span>
                <span className="hidden max-w-[160px] truncate sm:inline">{displayName}</span>
                <ChevronDown className="h-3.5 w-3.5 text-slate-500 dark:text-slate-400" aria-hidden="true" />
              </button>
              {menuOpen ? (
                <div
                  role="menu"
                  aria-label="Account"
                  className={cn(
                    "absolute right-0 z-40 mt-2 w-60 overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg",
                    "dark:border-slate-700 dark:bg-slate-900",
                  )}
                >
                  {user ? (
                    <div className="border-b border-slate-100 px-3 py-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
                      <p className="truncate font-medium text-slate-900 dark:text-slate-100">
                        {user.full_name || user.email}
                      </p>
                      {user.full_name ? <p className="truncate">{user.email}</p> : null}
                    </div>
                  ) : null}
                  <ul className="py-1 text-sm">
                    <li>
                      <Link
                        to="/auth/change-password"
                        role="menuitem"
                        onClick={() => setMenuOpen(false)}
                        className="flex items-center gap-2 px-3 py-1.5 text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                      >
                        <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
                        Change password
                      </Link>
                    </li>
                    <li>
                      <Link
                        to="/settings"
                        role="menuitem"
                        onClick={() => setMenuOpen(false)}
                        className="flex items-center gap-2 px-3 py-1.5 text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                      >
                        <SettingsIcon className="h-3.5 w-3.5" aria-hidden="true" />
                        Settings
                      </Link>
                    </li>
                    {tenantSwitcherEnabled ? (
                      <li>
                        <button
                          type="button"
                          role="menuitem"
                          disabled
                          aria-disabled="true"
                          title="Tenant switching is not enabled in this build."
                          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-slate-400 dark:text-slate-500"
                        >
                          <Repeat className="h-3.5 w-3.5" aria-hidden="true" />
                          Switch tenant (coming soon)
                        </button>
                      </li>
                    ) : null}
                    <li className="border-t border-slate-100 dark:border-slate-800">
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setMenuOpen(false);
                          logout();
                          navigate("/login");
                        }}
                        className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                      >
                        <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                        Sign out
                      </button>
                    </li>
                  </ul>
                </div>
              ) : null}
            </div>
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
