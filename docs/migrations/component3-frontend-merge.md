# Component 3 frontend — merge onto `main` baseline

Goal: **`main` owns** Vite, Tailwind, ESLint, TS configs, and global styling.  
Your branch contributes **implementation only** (routes, features, API client, UI pieces).

## What was staged locally

A **gitignored** copy of your implementation lives at:

`migration/component3-frontend-hold/`

It mirrors these paths from your old tree:

| Hold path | Restore under `frontend/` after merge |
|-----------|----------------------------------------|
| `src/features/` | `frontend/src/features/` |
| `src/components/` | `frontend/src/components/` |
| `src/lib/` | `frontend/src/lib/` |
| `src/App.tsx` | `frontend/src/App.tsx` (merge with `main` — wire router / providers) |
| `src/main.tsx` | `frontend/src/main.tsx` (same) |
| `src/vite-env.d.ts` | `frontend/src/vite-env.d.ts` |
| `reference-index.css` | **Reference only** — merge tokens into `main`’s `index.css`; do not blindly overwrite |
| `reference-vite.config.ts` | **Reference only** — port `@/` alias + `/api` proxy into `main`’s `vite.config.ts` |
| `reference-package.json` | **Reference only** — add missing deps to `main`’s `package.json` |
| `reference-components.json` | **Reference only** — shadcn-style paths if you keep that convention |

Regenerate the hold folder anytime:

```bash
mkdir -p migration/component3-frontend-hold/src
rm -rf migration/component3-frontend-hold/src/*
cp -R frontend/src/features migration/component3-frontend-hold/src/
cp -R frontend/src/components migration/component3-frontend-hold/src/
cp -R frontend/src/lib migration/component3-frontend-hold/src/
cp frontend/src/App.tsx frontend/src/main.tsx frontend/src/vite-env.d.ts migration/component3-frontend-hold/src/
cp frontend/src/index.css migration/component3-frontend-hold/reference-index.css
cp frontend/vite.config.ts migration/component3-frontend-hold/reference-vite.config.ts
cp frontend/package.json migration/component3-frontend-hold/reference-package.json
test -f frontend/components.json && cp frontend/components.json migration/component3-frontend-hold/reference-components.json
```

## Recommended workflow

### 1. Commit anything else on your branch first

Backend / ML changes unrelated to this migration should already be committed so you only touch frontend in the next steps.

### 2. Remove the duplicate `frontend/` tree from Git **on your branch**

This deletes tracked frontend files so your merge won’t fight `main`.

```bash
git checkout recommendation-branch-supuni   # your branch name
git rm -r frontend || true                  # if frontend is tracked
rm -rf frontend                             # removes untracked + tracked remnants (careful)
git commit -m "chore(frontend): drop local scaffold before aligning with main"
```

If `frontend/` was never tracked, `git rm -r` may fail — **`rm -rf frontend` only** is fine; commit the deletion of any tracked paths you're removing.

### 3. Bring in `main`’s frontend

```bash
git fetch origin
git merge origin/main
```

Resolve any non-frontend conflicts as usual. After this step you should see **`main`’s** `frontend/` (Vite + Tailwind baseline).

### 4. Restore implementation from the hold folder

```bash
mkdir -p frontend/src
cp -R migration/component3-frontend-hold/src/features frontend/src/
cp -R migration/component3-frontend-hold/src/components frontend/src/
cp -R migration/component3-frontend-hold/src/lib frontend/src/
cp migration/component3-frontend-hold/src/vite-env.d.ts frontend/src/
```

For **`App.tsx`** and **`main.tsx`**, **do not blindly overwrite** `main`’s versions:

- Open **both** `main`’s file and `migration/component3-frontend-hold/src/App.tsx`.
- Integrate: router + `QueryClientProvider` + your `<Routes>` while keeping anything the owner wants globally (or replace demo content entirely per team agreement).

### 5. Extend `main`’s `package.json` (don’t swap in `reference-package.json` wholesale)

Compare `reference-package.json` with `frontend/package.json` and **add** missing runtime deps, for example:

- `react-router-dom`, `@tanstack/react-query`, `axios`, `zod`, `react-hook-form`, `@hookform/resolvers`
- UI helpers you use: `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `@radix-ui/react-slot`, etc.

Then:

```bash
cd frontend && npm install && cd ..
```

Commit `package-lock.json` updates.

### 6. Align `vite.config.ts`

Merge **only** what you need from `reference-vite.config.ts`:

- `@/` → `src` path alias  
- Dev **`/api` proxy** to the gateway if your client calls relative `/api`

### 7. Align styles

Merge **`reference-index.css`** into **`main`’s `index.css`** so you keep **`main`’s brand tokens** (`--color-brand-maroon`, etc.) and map shadcn-style `--primary` / surfaces to those colours where needed.

### 8. Verify

```bash
cd frontend && npm run build && npm run lint && npm run dev
```

### 9. Push & PR

```bash
git add frontend docs/migrations/component3-frontend-merge.md .gitignore
git commit -m "feat(frontend): component 3 dashboard on main baseline"
git push origin recommendation-branch-supuni
```

## Notes

- **`migration/component3-frontend-hold/` is gitignored** — it is a **local safety net**, not shared history. Keep this doc if you want teammates to repeat the flow.
- If you want the backup **in Git**, remove the ignore rule (not recommended long-term — duplicates noisy trees).
