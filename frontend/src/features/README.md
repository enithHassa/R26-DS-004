# Frontend feature modules

Each research component owns its own folder under `src/features/`. Everything
inside that folder — pages, API client, component-specific hooks, types — is
owned by that component's team.

## Adding a new component

1. Create `src/features/<your-component>/` (e.g. `transaction-semantic`, `tax-optimization`, `language-model`).
2. Build out `pages/`, `api.ts`, and any component-local hooks.
3. Export a `FeatureModule` as the default from `index.tsx`:

   ```tsx
   import type { FeatureModule } from "@/features/types";

   const transactionSemantic: FeatureModule = {
     id: "transaction-semantic",
     title: "Transaction Semantics",
     routes: [
       { path: "transactions", element: <TransactionsPage /> },
     ],
     nav: [
       { to: "/transactions", label: "Transactions", icon: ListIcon },
     ],
   };

   export default transactionSemantic;
   ```

4. Register it in `src/features/index.ts`.

## Shared pieces

| Path                             | Belongs to                                  |
| -------------------------------- | ------------------------------------------- |
| `src/components/ui/**`           | Shared shadcn primitives                    |
| `src/components/layout/**`       | Shared app shell                            |
| `src/lib/utils.ts`, `api-client.ts` | Shared helpers                           |
| `src/index.css`                  | Shared Tailwind v4 theme tokens             |

Do **not** put component-specific pages, API calls, or types in the folders
above.
