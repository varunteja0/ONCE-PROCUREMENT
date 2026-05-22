import { useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle2 } from 'lucide-react';
import { useInvalidateBilling } from '@/hooks/useBilling';

export default function CheckoutSuccess(): JSX.Element {
  const [params] = useSearchParams();
  const sessionId = params.get('session_id');
  const invalidate = useInvalidateBilling();

  useEffect(() => {
    // The webhook is the source of truth — but invalidate the local cache so
    // the next render of /billing fetches the freshly-created subscription.
    invalidate();
  }, [invalidate]);

  return (
    <main className="flex min-h-[60vh] items-center justify-center px-4 py-12">
      <div className="max-w-md rounded-2xl border border-emerald-200 bg-white p-8 text-center shadow-sm">
        <CheckCircle2
          aria-hidden="true"
          className="mx-auto h-12 w-12 text-emerald-600"
        />
        <h1 className="mt-4 text-xl font-semibold text-slate-900">
          Payment confirmed
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Thanks — your subscription is being activated. It may take a few
          seconds for everything to show up on your billing page.
        </p>
        {sessionId ? (
          <p className="mt-3 text-xs text-slate-400" aria-label="Stripe session id">
            Session: <code className="font-mono">{sessionId}</code>
          </p>
        ) : null}
        <Link
          to="/billing"
          className="mt-6 inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          Go to billing
        </Link>
      </div>
    </main>
  );
}
