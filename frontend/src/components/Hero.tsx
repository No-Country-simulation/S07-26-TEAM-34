export function Hero({ onStart }: { onStart: () => void }) {
  return (
    <section className="relative overflow-hidden border-b border-white/5">
      <div className="bg-grid absolute inset-0 [mask-image:radial-gradient(ellipse_60%_60%_at_50%_20%,black,transparent)]" />
      <div className="pointer-events-none absolute top-[-10%] left-1/2 h-[36rem] w-[36rem] -translate-x-1/2 animate-glow rounded-full bg-brand-500/20 blur-[120px]" />
      <div className="pointer-events-none absolute top-[10%] right-[10%] h-72 w-72 animate-glow rounded-full bg-accent-500/20 blur-[110px]" />

      <div className="relative mx-auto max-w-4xl px-6 py-28 text-center sm:px-8 sm:py-36">
        <div className="animate-fade-up inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 font-mono text-xs text-white/60">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-400" />
          Benchmark abierto · en construcción con la industria
        </div>

        <h1 className="animate-fade-up mt-8 text-4xl leading-[1.1] font-extrabold tracking-tight text-white sm:text-6xl [animation-delay:80ms]">
          Tu data center pierde capacidad
          <br />
          <span className="text-gradient">que ya pagaste.</span>
        </h1>

        <p className="animate-fade-up mx-auto mt-6 max-w-xl text-lg text-white/50 [animation-delay:160ms]">
          Medimos qué tan bien coordinás energía, cooling y workload — y te mostramos, con datos,
          dónde estás parado frente al resto de la industria.
        </p>

        <div className="animate-fade-up mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center [animation-delay:240ms]">
          <button
            type="button"
            onClick={onStart}
            className="rounded-full bg-gradient-to-r from-brand-500 to-accent-500 px-8 py-3.5 text-sm font-semibold text-ink-950 transition hover:opacity-90"
          >
            Empezar diagnóstico gratis →
          </button>
          <a
            href="#metodologia"
            className="text-sm font-medium text-white/50 transition hover:text-white"
          >
            Cómo funciona
          </a>
        </div>

        <dl className="animate-fade-up mx-auto mt-20 grid max-w-2xl grid-cols-3 gap-8 border-t border-white/5 pt-10 [animation-delay:320ms]">
          <Stat value="< 10 min" label="Para completarlo" />
          <Stat value="5" label="Dimensiones de madurez" />
          <Stat value="100%" label="Anónimo, sin login" />
        </dl>
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="font-mono text-2xl font-semibold text-white sm:text-3xl">{value}</div>
      <div className="mt-1 text-xs text-white/40">{label}</div>
    </div>
  );
}
