import { Lock, Settings as SettingsIcon, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

export function Shell({ children }: { children: ReactNode }): JSX.Element {
  return (
    <div className="flex flex-col bg-slate-50 text-slate-900" style={{ width: 360, height: 560 }}>
      {children}
    </div>
  );
}

interface HeaderProps {
  email?: string | null;
  onSettings?: () => void;
  onLock?: () => void;
  lockable?: boolean;
}

export function Header({ email, onSettings, onLock, lockable }: HeaderProps): JSX.Element {
  return (
    <header className="flex items-center justify-between px-3 py-2 border-b border-slate-200 bg-white">
      <div className="flex items-center gap-2 min-w-0">
        <ShieldCheck className="h-5 w-5 text-brand-600 flex-shrink-0" aria-hidden />
        <div className="leading-tight min-w-0">
          <div className="text-sm font-semibold">Once</div>
          {email ? <div className="text-[10px] text-slate-500 truncate max-w-[220px]">{email}</div> : null}
        </div>
      </div>
      <div className="flex items-center gap-1">
        {lockable && onLock ? (
          <button
            type="button"
            className="btn-ghost h-7 w-7 p-0"
            title="Lock vault"
            aria-label="Lock vault"
            onClick={onLock}
          >
            <Lock className="h-3.5 w-3.5" aria-hidden />
          </button>
        ) : null}
        {onSettings ? (
          <button
            type="button"
            className="btn-ghost h-7 w-7 p-0"
            title="Open settings"
            aria-label="Open settings"
            onClick={onSettings}
          >
            <SettingsIcon className="h-3.5 w-3.5" aria-hidden />
          </button>
        ) : null}
      </div>
    </header>
  );
}

export function Banner({ kind, text }: { kind: "info" | "error" | "success"; text: string }): JSX.Element {
  const cls =
    kind === "error"
      ? "bg-red-50 text-red-800 border-red-200"
      : kind === "success"
        ? "bg-emerald-50 text-emerald-800 border-emerald-200"
        : "bg-blue-50 text-blue-800 border-blue-200";
  return (
    <div role="status" className={`px-3 py-1.5 text-[11px] border-b ${cls}`}>
      {text}
    </div>
  );
}
