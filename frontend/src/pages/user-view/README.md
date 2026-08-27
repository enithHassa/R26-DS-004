# User View — TaxWise (taxpayer portal)

Dark-themed **TaxWise** shell for taxpayers after they log in with credentials
created by an auditor.

**Code name / URL prefix:** `/taxwise`

Separate from:

- `src/features/` — **auditor** research pages under AppShell (`/profile`, `/hybrid`, …)
- `src/pages/demo/` — public marketing landing (`/demo`)
- Comp 3 taxpayer hub still under `/portal/*` (onboarding + recommendations summary)

## Route map (do not mix these)

| Audience | Path | What it is |
| -------- | ---- | ---------- |
| TaxWise (new) | `/taxwise` | Dashboard home |
| TaxWise (new) | `/taxwise/profile` | Bridge → Comp 3 My Profile (until TaxWise profile page exists) |
| Comp 3 taxpayer | `/portal/financial-intake` | First-time financial questions |
| Comp 3 taxpayer | `/portal/about-you` | Optional behavioural questions |
| Comp 3 taxpayer | `/portal/summary` | Recommendations / impact / **My Profile** tabs |
| Auditor Comp 3 | `/profile` | Auditor profile wizard (create/manage profiles) |
| Shared | `/login` | Same login; role picks TaxWise vs AppShell |

Legacy redirects: `/portal` → `/taxwise`, `/portal/profile` → `/taxwise/profile`.

## Styling

Tailwind utilities + scoped tokens in `user-view-theme.css` (same palette as
the demo landing page).

## Adding more TaxWise pages

Use the prefix consistently, e.g.:

- `/taxwise/transactions`
- `/taxwise/tax-strategy`
- `/taxwise/ai-advisor`
- `/taxwise/recommendations`

Do **not** put new TaxWise pages under `/portal` or under auditor `/profile`.
