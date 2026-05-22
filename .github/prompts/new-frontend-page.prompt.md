---
mode: agent
description: "Scaffold a new operator-console page: route, page component, hook, types, tests."
---

# New frontend page

You will add a new page to the operator console under `frontend/src/`.
Follow [../../frontend/AGENTS.md](../../frontend/AGENTS.md) and
[../instructions/frontend.instructions.md](../instructions/frontend.instructions.md).

## Inputs to gather

- **Page name** (PascalCase, e.g. `ConsentLedger`).
- **Route path** (e.g. `/consent-ledger`).
- **Auth required?** (default: yes — wrap in `ProtectedRoute`).
- **Backend resource(s):** which API endpoint(s) feed the page.
- **Sidebar entry?** (yes for top-level pages, no for sub-pages).

## Plan

1. **API layer:** add or extend `frontend/src/api/<resource>.ts` with
   typed functions. All calls go through the shared axios instance from
   `services/api.ts`. Never `import axios` directly.
2. **Types:** add response shapes to `frontend/src/types/api.ts`. No `any`.
3. **Hook:** create `frontend/src/hooks/use<Resource>.ts` with TanStack
   Query (`useQuery` for reads, `useMutation` for writes). Server state
   lives in the query cache, **not** Zustand.
4. **Page component:** create `frontend/src/pages/<Page>.tsx`:
   - Loading state (use shared spinner / skeleton component).
   - Error state (use shared `EmptyState` with retry).
   - Empty state when the query returns `[]`.
   - Success state with the actual UI.
   - Tailwind for styling; no new CSS files.
5. **Router:** register the route in `frontend/src/router/`. Wrap in
   `ProtectedRoute` unless explicitly public.
6. **Navigation:** add a `Sidebar.tsx` entry for top-level pages with a
   Lucide icon.
7. **Tests:** add `frontend/src/pages/__tests__/<Page>.test.tsx` (or
   colocated `<Page>.test.tsx`) that mocks the query and asserts the
   loading → success → empty paths render correctly.

## Quality gates

```powershell
cd frontend
npm run lint
npm run typecheck
npm test
```

All three must be green. No new `any`. ESLint `--max-warnings 0`.
