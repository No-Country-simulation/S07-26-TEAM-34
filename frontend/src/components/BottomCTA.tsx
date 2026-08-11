export function BottomCTA({ onStart }: { onStart: () => void }) {
  return (
    <section className="relative overflow-hidden border-t border-white/5">
      <div className="pointer-events-none absolute top-1/2 left-1/2 h-80 w-[40rem] -translate-x-1/2 -translate-y-1/2 animate-glow rounded-full bg-brand-500/10 blur-[100px]" />
      <div className="relative mx-auto max-w-2xl px-6 py-24 text-center sm:px-8">
        <h2 className="text-3xl font-bold text-white sm:text-4xl">¿Dónde estás parado hoy?</h2>
        <p className="mt-4 text-white/50">
          Menos de 10 minutos. Sin login, sin datos personales. Tu diagnóstico, listo al toque.
        </p>
        <button
          type="button"
          onClick={onStart}
          className="mt-8 rounded-full bg-gradient-to-r from-brand-500 to-accent-500 px-8 py-3.5 text-sm font-semibold text-ink-950 transition hover:opacity-90"
        >
          Empezar diagnóstico gratis →
        </button>
      </div>
    </section>
  );
}
