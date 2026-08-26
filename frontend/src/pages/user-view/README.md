# User View (taxpayer portal)

Dark-themed pages for **taxpayers** after they log in with credentials
created by an auditor. Separate from:

- `src/features/` — auditor-facing research component pages (AppShell sidebar)
- `src/pages/demo/` — public marketing landing

## Routes

| Path | Page |
| ---- | ---- |
| `/portal` | Dashboard (landing after login) |
| `/portal/summary` | Comp 3 taxpayer page (recommendations, impact, **My Profile**) |
| `/portal/profile` | Redirects to `/portal/summary?tab=profile` |
| `/portal/about-you` | Optional behavioural questions onboarding |

Sidebar Profile and the dashboard “Your profile” card go to the existing
Comp 3 user page (`/portal/summary?tab=profile`) — not a duplicate.

## Styling

Tailwind utilities + scoped tokens in `user-view-theme.css` (same palette as
the demo landing page).
