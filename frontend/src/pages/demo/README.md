# Demo / marketing pages

Standalone landing and demo pages for presentations — **not** tied to any research
component under `src/features/`.

## Structure

```
pages/demo/
├── index.tsx              # Route registration (mounted outside AppShell)
├── landing-page.tsx       # Main landing page composition
├── demo-theme.css         # Scoped dark-theme CSS variables
└── components/            # Page-specific UI sections
    ├── demo-header.tsx
    ├── demo-hero.tsx
    ├── demo-stats-bar.tsx
    ├── demo-modules-section.tsx
    └── demo-cta-section.tsx
```

## Styling approach

- **Tailwind CSS v4** for layout, spacing, responsive grids, and utilities.
- **`demo-theme.css`** for scoped palette tokens (`--demo-bg`, `--demo-accent`, …) so
  the dark marketing theme does not override the main app shell theme in `index.css`.
- **lucide-react** for icons; **react-router** `Link` for in-app navigation.

## Routes

| Path    | Page              |
| ------- | ----------------- |
| `/demo` | Marketing landing |

Add new demo pages here and register them in `index.tsx` alongside `demoRoutes`.
