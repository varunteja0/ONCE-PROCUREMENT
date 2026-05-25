import { ErrorState } from "@/components/ui/ErrorState";
import { logger } from "@/lib/logger";
import { Component, type ErrorInfo, type ReactNode } from "react";

export interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface State {
  error: Error | null;
}

/**
 * Top-level and per-route React error boundary. Logs through the central
 * logger (which is wired so Sentry can be added in production without
 * changing call sites).
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, State> {
  override state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    logger.error("react-error-boundary", {
      error: error.message,
      stack: error.stack,
      componentStack: info.componentStack,
    });
    logger.captureException(error, { componentStack: info.componentStack });
    this.props.onError?.(error, info);
  }

  reset = (): void => {
    this.setState({ error: null });
  };

  override render(): ReactNode {
    if (this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.reset);
      }
      return (
        <div className="p-6">
          <ErrorState title="This view crashed" error={this.state.error} onRetry={this.reset} />
        </div>
      );
    }
    return this.props.children;
  }
}
