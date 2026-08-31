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
| TaxWise (new) | `/taxwise/profile` | 8-section tax return profile wizard (save/update to DB) |
| TaxWise (new) | `/taxwise/recommendations` | Personalized recommendations |
| TaxWise (new) | `/taxwise/financial-impact` | Long-term financial impact |
| TaxWise (new) | `/taxwise/optimization-explainable` | OE Engine user Overview (what’s best / auditor-approved) |
| TaxWise (new) | `/taxwise/optimization-explainable/income` | My Income |
| TaxWise (new) | `/taxwise/optimization-explainable/reliefs` | My Reliefs |
| TaxWise (new) | `/taxwise/optimization-explainable/result` | My Tax Result |
| Comp 3 taxpayer | `/portal/financial-intake` | First-time financial questions |
| Comp 3 taxpayer | `/portal/about-you` | Optional behavioural questions |
| Comp 3 taxpayer | `/portal/summary` | Legacy redirect → TaxWise recommendations pages |
| Auditor Comp 3 | `/profile` | Auditor profile wizard (create/manage profiles) |
| Shared | `/login` | Same login; role picks TaxWise vs AppShell |

Legacy redirects: `/portal` → `/taxwise`, `/portal/profile` → `/taxwise/profile`.

## Styling

Tailwind utilities + scoped tokens in `user-view-theme.css` (same palette as
the demo landing page).

## Adding more TaxWise pages

Use the prefix consistently, e.g.:

- `/taxwise/transactions`
- `/taxwise/optimization-explainable`
- `/taxwise/ai-advisor`
- `/taxwise/recommendations`

Do **not** put new TaxWise pages under `/portal` or under auditor `/profile`.
Auditor OE Engine remains at `/optimization-explainable-engine/**` (Approve for taxpayer
publishes a finalized snapshot that TaxWise OE reads).