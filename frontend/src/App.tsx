function App() {
  return (
    <div className="min-h-screen bg-[var(--color-bg-canvas)] text-[var(--color-text-primary)]">
      <header className="border-b border-[var(--color-border-soft)] bg-white/95">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
              R26-DS-004
            </p>
            <h1 className="mt-1 text-xl font-semibold text-[var(--color-brand-maroon)]">
              Intelligent Tax Advisory
            </h1>
          </div>
          <span className="rounded-full border border-[var(--color-border-accent)] bg-[var(--color-brand-cream)] px-3 py-1 text-xs font-medium text-[var(--color-brand-maroon)]">
            Theme v0
          </span>
        </div>
      </header>

      <main className="mx-auto grid w-full max-w-6xl gap-6 px-6 py-8 md:grid-cols-3">
        <section className="card md:col-span-2">
          <h2 className="section-title">Style Foundation Ready</h2>
          <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
            Colors are derived from your presentation palette with a white-first UI strategy.
            This is now the base for upcoming uploader and extracted-transaction screens.
          </p>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <div className="token-swatch">
              <span className="swatch" style={{ backgroundColor: 'var(--color-brand-maroon)' }} />
              <div>
                <p className="token-name">Brand Maroon</p>
                <p className="token-value">#8E3F46</p>
              </div>
            </div>
            <div className="token-swatch">
              <span className="swatch" style={{ backgroundColor: 'var(--color-brand-gold)' }} />
              <div>
                <p className="token-name">Brand Gold</p>
                <p className="token-value">#B49A5C</p>
              </div>
            </div>
            <div className="token-swatch">
              <span className="swatch" style={{ backgroundColor: 'var(--color-brand-cream)' }} />
              <div>
                <p className="token-name">Brand Cream</p>
                <p className="token-value">#F4EEDC</p>
              </div>
            </div>
            <div className="token-swatch">
              <span className="swatch" style={{ backgroundColor: 'var(--color-surface-panel)' }} />
              <div>
                <p className="token-name">Surface White</p>
                <p className="token-value">#FFFFFF</p>
              </div>
            </div>
          </div>
        </section>

        <aside className="card">
          <h3 className="section-title">Next UI Modules</h3>
          <ul className="mt-3 space-y-3 text-sm text-[var(--color-text-secondary)]">
            <li className="rounded-lg border border-[var(--color-border-soft)] bg-white p-3">
              Upload card (PDF/JPG/CSV/XLSX/TXT)
            </li>
            <li className="rounded-lg border border-[var(--color-border-soft)] bg-white p-3">
              Extraction summary (counts + status)
            </li>
            <li className="rounded-lg border border-[var(--color-border-soft)] bg-white p-3">
              Transaction table + validation flags
            </li>
          </ul>
          <button className="btn-primary mt-6 w-full">Continue to Backend Ingestion</button>
        </aside>
      </main>
    </div>
  )
}

export default App
