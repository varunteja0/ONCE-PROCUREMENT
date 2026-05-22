import { cn } from '@/lib/cn';
import {
    BadgeCheck,
    FileBarChart2,
    FileCheck2,
    FileText,
    KeyRound,
    LayoutDashboard,
    ListChecks,
    Plug,
    ReceiptText,
    Send,
    Settings as SettingsIcon,
    ShieldAlert,
    ShieldCheck,
    Upload,
    Users,
    type LucideIcon,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';

export interface SidebarProps {
  /** When true, the sidebar is forced visible on small screens (overlay). */
  mobileOpen?: boolean;
  onNavigate?: () => void;
}

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

const NAV_ITEMS: readonly NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/suppliers', label: 'Suppliers', icon: Users },
  { to: '/submissions', label: 'Submissions', icon: Send },
  { to: '/receipts', label: 'Receipts', icon: ReceiptText },
  { to: '/consent-ledger', label: 'Consent Ledger', icon: ShieldCheck },
  { to: '/cois', label: 'COIs', icon: FileCheck2 },
  { to: '/loss-runs', label: 'Loss Runs', icon: FileBarChart2 },
  { to: '/producer-licenses', label: 'Producer Licenses', icon: BadgeCheck },
  { to: '/eo-certificates', label: 'E&O Certificates', icon: ShieldAlert },
  { to: '/acord-forms', label: 'ACORD Forms', icon: FileText },
  { to: '/risk-schedules', label: 'Risk Schedules', icon: ListChecks },
  { to: '/portals', label: 'Portals', icon: Plug },
  // --- L3.7 imports ---
  { to: '/imports', label: 'Imports', icon: Upload },
  // --- /L3.7 imports ---
  // --- L6.1 verifier API keys ---
  { to: '/verifier-keys', label: 'Verifier Keys', icon: KeyRound },
  // --- /L6.1 verifier API keys ---
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
];

export default function Sidebar({
  mobileOpen = false,
  onNavigate,
}: SidebarProps = {}): JSX.Element {
  return (
    <aside
      aria-label="Primary navigation"
      data-mobile-open={mobileOpen}
      className={cn(
        'fixed inset-y-0 left-0 z-30 flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white transition-transform duration-200 md:static md:translate-x-0 dark:border-slate-800 dark:bg-slate-900',
        mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
      )}
    >
      <div className="flex h-14 items-center gap-2 border-b border-slate-200 px-4 dark:border-slate-800">
        <span
          aria-hidden="true"
          className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-slate-900 text-xs font-bold text-white dark:bg-slate-100 dark:text-slate-900"
        >
          O
        </span>
        <span className="text-sm font-semibold tracking-tight dark:text-slate-100">Once</span>
      </div>
      <nav className="flex-1 overflow-y-auto p-3" aria-label="Sections">
        <ul className="space-y-0.5">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/dashboard'}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    'group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2',
                    isActive
                      ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                      : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      aria-hidden="true"
                      className={cn(
                        'h-4 w-4 shrink-0',
                        isActive
                          ? 'text-white dark:text-slate-900'
                          : 'text-slate-500 group-hover:text-slate-700 dark:text-slate-400 dark:group-hover:text-slate-100',
                      )}
                    />
                    <span>{label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="border-t border-slate-200 px-4 py-3 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
        v0 · Once Procurement
      </div>
    </aside>
  );
}
