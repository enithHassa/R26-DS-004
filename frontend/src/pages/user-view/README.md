# User View (taxpayer portal)

Dark-themed pages for **taxpayers** after they log in with credentials
created by an auditor. Separate from:

- `src/features/` — auditor-facing research component pages (AppShell sidebar)
- `src/pages/demo/` — public marketing landing

## Routes

| Path | Page |
| ---- | ---- |
| `/portal` | Dashboard (landing after login) |
| `/portal/financial-intake` | First-time financial profile questions |
| `/portal/about-you` | Optional behavioural questions onboarding |
| `/portal/summary` | Comp 3 taxpayer page (recommendations, impact, **My Profile**) |
| `/portal/profile` | Redirects to `/portal/summary?tab=profile` |

Sidebar Profile and the dashboard “Your profile” card go to the existing
Comp 3 user page (`/portal/summary?tab=profile`) — not a duplicate.

Other sidebar nav items on the dashboard are **placeholders** until user-view
sub-pages are built — they are not wired to auditor routes like `/profile`
or `/hybrid`.

## Styling

Tailwind utilities + scoped tokens in `user-view-theme.css` (same palette as
the demo landing page).
