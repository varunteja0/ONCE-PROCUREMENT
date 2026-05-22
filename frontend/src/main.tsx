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
