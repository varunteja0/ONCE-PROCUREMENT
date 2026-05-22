/**
 * Legacy entry point. The application now uses `createBrowserRouter` from
 * `@/router`; this module is kept so legacy imports of `@/App` resolve, and
 * re-exports the route table for any tooling that still references it.
 */
export { routes as default, router, routes } from '@/router';
