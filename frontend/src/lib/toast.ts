import { toast as sonnerToast } from 'sonner';
import { extractErrorMessage } from '@/services/api';

/**
 * Thin wrapper around sonner so the rest of the app does not import sonner
 * directly. Provides a uniform `toast.error(err, fallback)` helper that
 * extracts a useful message from axios errors / Error instances.
 */
export const toast = {
  success: (message: string): void => {
    sonnerToast.success(message);
  },
  info: (message: string): void => {
    sonnerToast(message);
  },
  warning: (message: string): void => {
    sonnerToast.warning(message);
  },
  error: (err: unknown, fallback = 'Something went wrong'): void => {
    const msg =
      typeof err === 'string' ? err : extractErrorMessage(err, fallback);
    sonnerToast.error(msg);
  },
};

export default toast;
