import { Zap } from "lucide-react";
import { Link } from "react-router-dom";

const NAV_LINKS = [
  { label: "Features", href: "#features" },
  { label: "Pricing", href: "#pricing" },
  { label: "About", href: "#about" },
  { label: "Docs", href: "#docs" },
] as const;

export function DemoHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-[var(--demo-border)] bg-[var(--demo-bg)]/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link to="/demo" className="flex items-center gap-2.5">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-[var(--demo-accent)]">
            <Zap className="h-4 w-4 text-[var(--demo-accent-foreground)]" />
          </span>
          <span className="text-base font-bold tracking-tight text-[var(--demo-text)]">
            TaxWise AI
          </span>
        </Link>

        <nav className="hidden items-center gap-8 md:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-sm text-[var(--demo-text-muted)] transition-colors hover:text-[var(--demo-text)]"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="hidden rounded-lg border border-[var(--demo-border)] px-4 py-2 text-sm font-medium text-[var(--demo-text)] transition-colors hover:border-slate-500 sm:inline-flex"
          >
            Log In
          </Link>
          <a
            href="#get-started"
            className="inline-flex rounded-lg bg-[var(--demo-accent)] px-4 py-2 text-sm font-semibold text-[var(--demo-accent-foreground)] transition-colors hover:bg-[var(--demo-accent-hover)]"
          >
            Get Started
          </a>
        </div>
      </div>
    </header>
  );
}
