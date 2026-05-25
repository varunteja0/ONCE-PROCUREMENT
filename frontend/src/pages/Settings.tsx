import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from '@/lib/toast';
import { Download, Key, Loader2, LogOut, User } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { api, extractErrorMessage, tokenStorage } from '@/services/api';

type TabId = 'profile' | 'account' | 'tokens';

interface ProfileTabProps {
  initialName: string;
}

function ProfileTab({ initialName }: ProfileTabProps): JSX.Element {
  const { refreshMe } = useAuth();
  const [fullName, setFullName] = useState(initialName);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setFullName(initialName);
  }, [initialName]);

  async function onSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    try {
      await api.patch('/auth/me', { full_name: fullName.trim() });
      await refreshMe();
      toast.success('Profile updated.');
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Update failed'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="max-w-md space-y-4">
      <div>
        <label
          htmlFor="full_name"
          className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200"
        >
          Full name
        </label>
        <input
          id="full_name"
          type="text"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          disabled={saving}
        />
      </div>
      <button
        type="submit"
        disabled={saving || fullName.trim().length === 0}
        className="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
      >
        {saving && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        Save
      </button>
    </form>
  );
}

function truncateMiddle(s: string, head = 8, tail = 4): string {
  if (s.length <= head + tail + 1) return s;
  return `${s.slice(0, head)}…${s.slice(-tail)}`;
}

function AccountTab(): JSX.Element {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function onSignOutEverywhere(): void {
    // BACKEND-COUPLED: this currently only clears local tokens. A real
    // "sign out everywhere" needs POST /auth/sessions/revoke-all on the
    // backend to invalidate every issued refresh token for this user.
    logout();
    toast.success('Signed out on this device.');
    navigate('/login', { replace: true });
  }

  return (
    <div className="max-w-md space-y-6">
      <dl className="grid grid-cols-[7rem,1fr] gap-y-2 text-sm">
        <dt className="text-slate-500 dark:text-slate-400">Email</dt>
        <dd className="font-medium text-slate-900 dark:text-slate-100">
          {user?.email ?? '—'}
        </dd>
        <dt className="text-slate-500 dark:text-slate-400">Role</dt>
        <dd className="font-medium text-slate-900 dark:text-slate-100">
          {user?.role ?? '—'}
        </dd>
        <dt className="text-slate-500 dark:text-slate-400">Tenant ID</dt>
        <dd className="font-mono text-xs text-slate-700 dark:text-slate-300">
          {user?.tenant_id ? truncateMiddle(user.tenant_id) : '—'}
        </dd>
      </dl>

      <div className="flex flex-wrap gap-2">
        <Link
          to="/auth/change-password"
          className="inline-flex items-center gap-2 rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          <Key className="h-4 w-4" aria-hidden="true" />
          Change password
        </Link>
        <button
          type="button"
          onClick={onSignOutEverywhere}
          className="inline-flex items-center gap-2 rounded border border-red-300 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-100 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200 dark:hover:bg-red-950/60"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          Sign out everywhere
        </button>
      </div>
    </div>
  );
}

function TokensTab(): JSX.Element {
  const [downloading, setDownloading] = useState(false);

  const access = tokenStorage.getAccess();
  const refresh = tokenStorage.getRefresh();

  function mask(token: string | null): string {
    if (!token) return '— none —';
    if (token.length <= 12) return token;
    return `${token.slice(0, 6)}…${token.slice(-4)}`;
  }

  async function onDownloadKey(): Promise<void> {
    if (downloading) return;
    setDownloading(true);
    try {
      const resp = await api.get<{ public_key_pem: string; key_id: string }>(
        '/keys/me',
      );
      const blob = new Blob([resp.data.public_key_pem], {
        type: 'application/x-pem-file',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `once-signing-key-${resp.data.key_id}.pem`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Failed to download key'));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="max-w-md space-y-6">
      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Active tokens
        </h3>
        <dl className="grid grid-cols-[6rem,1fr] gap-y-1 text-xs text-slate-600 dark:text-slate-400">
          <dt className="text-slate-400">Access</dt>
          <dd className="font-mono">{mask(access)}</dd>
          <dt className="text-slate-400">Refresh</dt>
          <dd className="font-mono">{mask(refresh)}</dd>
        </dl>
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Receipt signing key
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Download the public key Once uses to sign your submission receipts.
          Distribute this PEM to anyone who needs to verify a receipt offline.
        </p>
        <button
          type="button"
          onClick={() => void onDownloadKey()}
          disabled={downloading}
          className="inline-flex items-center gap-2 rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-60 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          {downloading ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Download className="h-4 w-4" aria-hidden="true" />
          )}
          Download public key PEM
        </button>
      </section>
    </div>
  );
}

const TABS: ReadonlyArray<{ id: TabId; label: string; icon: typeof User }> = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'account', label: 'Account', icon: Key },
  { id: 'tokens', label: 'Tokens & keys', icon: Key },
];

export default function Settings(): JSX.Element {
  const { user } = useAuth();
  const [tab, setTab] = useState<TabId>('profile');

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Settings
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Manage your profile, account, and credentials.
        </p>
      </header>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div
          role="tablist"
          aria-label="Settings sections"
          className="flex border-b border-slate-200 dark:border-slate-800"
        >
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                role="tab"
                aria-selected={active}
                type="button"
                onClick={() => setTab(t.id)}
                className={`inline-flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium ${
                  active
                    ? 'border-slate-900 text-slate-900 dark:border-slate-100 dark:text-slate-100'
                    : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
                }`}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {t.label}
              </button>
            );
          })}
        </div>

        <div className="p-5">
          {tab === 'profile' && (
            <ProfileTab initialName={user?.full_name ?? ''} />
          )}
          {tab === 'account' && <AccountTab />}
          {tab === 'tokens' && <TokensTab />}
        </div>
      </div>
    </div>
  );
}
