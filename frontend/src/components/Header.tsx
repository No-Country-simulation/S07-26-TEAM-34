export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-ink-950/70 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4 sm:px-8">
        <a href="#top" className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-brand-500 to-accent-500 font-mono text-xs font-bold text-ink-950">
            S
          </span>
          <span className="font-semibold text-white">Stranded<span className="text-white/40">Bench</span></span>
        </a>
        <nav className="flex items-center gap-6">
          <a href="#como-funciona" className="hidden text-sm text-white/50 transition hover:text-white sm:block">
            Metodología
          </a>
          <a
            href="#encuesta"
            className="rounded-full border border-white/10 px-4 py-2 text-sm font-medium text-white transition hover:border-brand-500/50 hover:bg-brand-500/10"
          >
            Empezar
          </a>
        </nav>
      </div>
    </header>
  );
}
