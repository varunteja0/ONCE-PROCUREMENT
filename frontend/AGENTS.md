# frontend/ — Agent rules

> Authoritative rules: [CONTRACTS.md](../CONTRACTS.md) §9, §12 (rows 20–23).

## Stack snapshot

- React 18 + TypeScript (**strict**) · Vite · Tailwind
- TanStack Query v5 (server state) · Zustand (client state)
- axios (with JWT refresh interceptor) · Lucide icons · react-hot-toast
- Vitest + Testing Library for tests

## Layout

```
src/
  api/         # raw axios endpoints (one file per resource)
  services/    # api.ts (axios instance + interceptors), auth.ts
  store/       # Zustand stores (auth.ts, etc.)
  hooks/       # TanStack Query hooks (useSubmissions, useReceipts, ...)
  pages/       # route-level components
  components/  # reusable UI pieces
  features/    # feature-grouped composites
  schemas/     # zod / runtime validation
  router/      # react-router setup
  providers/   # QueryClientProvider, AuthProvider, etc.
  types/api.ts # backend response shapes
```

## Hard rules (frontend)

1. **Server state ⇒ TanStack Query.** Do not store API responses in Zustand
   or React state. Client-only state (modal open, form draft) ⇒ Zustand or
   local state.
2. **One axios instance** in `services/api.ts` with the JWT refresh
   interceptor. Never `import axios` directly in components.
3. **Tokens** in `localStorage`. Refresh flow lives in the interceptor —
   do not duplicate it in components.
4. **No `any`.** Use `types/api.ts` (generated/handwritten) for response
   shapes.
5. **TypeScript strict.** `tsc --noEmit` clean. `eslint --max-warnings 0`.
6. **No inline `fetch`** — always go through `api/<resource>.ts`.
7. **Tailwind only** for styling. No CSS modules, no styled-components.
8. **Routes** registered in `router/`. New page → add the route there, add a
   nav entry in `Sidebar.tsx` if user-facing.
9. **Loading + error states** for every query. Use the shared `EmptyState`
   and `StatusPill` components for consistency.
10. **Tests** for non-trivial components and hooks under colocated
    `__tests__/` or `*.test.tsx` next to the source.

## Running locally

```powershell
cd frontend
npm install
npm run dev          # vite dev on :5173
npm run typecheck
npm run lint
npm test
```

## Never do

- Bypass the axios instance / refresh interceptor.
- Store JWT in Zustand (use the interceptor + localStorage).
- Cache server data in Zustand instead of TanStack Query.
- Add a new UI library (MUI, AntD, Chakra, etc.).
- Skip the loading/error state on a query.
