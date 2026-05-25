import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { router } from '@/router';
import { queryClient } from '@/lib/queryClient';
import { applyTheme, readTheme } from '@/lib/theme';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import './index.css';

// Sentry init: install @sentry/react and uncomment the block below to
// enable production error reporting. Gate on VITE_SENTRY_DSN so dev / CI
// builds without the env var stay a no-op.
//
// import * as Sentry from '@sentry/react';
// const dsn = import.meta.env.VITE_SENTRY_DSN;
// if (dsn) {
//   Sentry.init({
//     dsn,
//     environment: import.meta.env.MODE,
//     tracesSampleRate: 0.1,
//     replaysSessionSampleRate: 0,
//     replaysOnErrorSampleRate: 1.0,
//   });
// }

applyTheme(readTheme());

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found in index.html');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
        <Toaster
          richColors
          closeButton
          position="top-right"
          toastOptions={{ className: 'text-sm' }}
        />
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
