import { Link } from 'react-router-dom';
import { FileSearch } from 'lucide-react';
import { Button } from '@/components/ui/Button';

export default function NotFound(): JSX.Element {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <div className="max-w-md text-center">
        <div
          aria-hidden="true"
          className="mx-auto mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300"
        >
          <FileSearch className="h-6 w-6" />
        </div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Page not found
        </h1>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          The page you are looking for doesn&apos;t exist or has been moved.
        </p>
        <div className="mt-6">
          <Link to="/dashboard">
            <Button variant="primary">Back to dashboard</Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
