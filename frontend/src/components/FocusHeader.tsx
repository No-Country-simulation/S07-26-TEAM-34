export function FocusHeader({ onBack, label }: { onBack: () => void; label?: string }) {
  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-ink-950/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4 sm:px-8">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-brand-500 to-accent-500 font-mono text-xs font-bold text-ink-950">
            S
          </span>
          <span className="font-semibold text-white">
            Stranded<span className="text-white/40">Bench</span>
          </span>
        </div>
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-white/50 transition hover:text-white"
        >
          {label ?? "Salir"}
          <span aria-hidden>×</span>
        </button>
      </div>
    </header>
  );
}
