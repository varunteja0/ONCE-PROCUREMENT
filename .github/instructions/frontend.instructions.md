---
applyTo: "frontend/src/**/*.{ts,tsx}"
description: "Frontend rules — TanStack Query for server state, one axios instance, strict TS"
---

# Frontend — required behavior

1. **Server state ⇒ TanStack Query v5.** Do not store API responses in
   Zustand or React state. Client-only state (modal open, form draft) ⇒
   Zustand or local state.
2. **One axios instance** in `services/api.ts` with the JWT refresh
   interceptor. Never `import axios from "axios"` elsewhere.
3. **JWT** lives in `localStorage`. The refresh flow is in the interceptor —
   do not duplicate it in components or hooks.
4. **API calls** live in `src/api/<resource>.ts`. Hooks in `src/hooks/`
   consume them via `useQuery` / `useMutation`. Components consume hooks,
   never raw API functions.
5. **No `any`.** Use `src/types/api.ts` for backend shapes. Add fields there
   when the backend changes.
6. **TypeScript strict.** `tsc --noEmit` clean. `eslint --max-warnings 0`.
7. **No inline `fetch`.** Always go through the axios instance / API layer.
8. **Tailwind only** for styling. No CSS Modules, styled-components, Emotion,
   or new UI libraries.
9. **Routes** registered in `src/router/`. User-facing pages get a `Sidebar`
   nav entry.
10. **Loading + error states** are mandatory for every query. Use shared
    `EmptyState` and `StatusPill` components for consistency.

## Tests

Non-trivial components and hooks need Vitest + Testing Library tests under
`__tests__/` next to the source or `*.test.tsx` siblings.

Run: `cd frontend && npm run lint && npm run typecheck && npm test`.
