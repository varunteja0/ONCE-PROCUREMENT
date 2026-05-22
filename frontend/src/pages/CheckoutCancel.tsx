import { Link } from 'react-router-dom';
import { XCircle } from 'lucide-react';

export default function CheckoutCancel(): JSX.Element {
  return (
    <main className="flex min-h-[60vh] items-center justify-center px-4 py-12">
      <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <XCircle
          aria-hidden="true"
          className="mx-auto h-12 w-12 text-slate-400"
        />
        <h1 className="mt-4 text-xl font-semibold text-slate-900">
          Checkout canceled
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          No payment was taken. You can subscribe whenever you&apos;re ready.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Link
            to="/pricing"
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-50"
          >
            View pricing
          </Link>
          <Link
            to="/billing"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            Back to billing
          </Link>
        </div>
      </div>
    </main>
  );
}
