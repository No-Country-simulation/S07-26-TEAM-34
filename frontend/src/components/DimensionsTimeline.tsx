import { IconClock, IconEye, IconGauge, IconLink, IconLock } from "./icons";

const DIMENSIONES = [
  { n: "01", title: "Visibilidad cross-layer", desc: "¿Tenés una vista unificada de energía, cooling y workload?", Icon: IconEye },
  { n: "02", title: "Atribución de fricción", desc: "¿En qué interfaz perciben la mayor pérdida de capacidad?", Icon: IconLink },
  { n: "03", title: "Latencia de coordinación", desc: "¿Qué tan rápido se ajustan cooling y energía ante un cambio de carga?", Icon: IconClock },
  { n: "04", title: "Auto-cuantificación", desc: "¿Saben, con números, cuánta capacidad tienen varada hoy?", Icon: IconGauge },
  { n: "05", title: "Bloqueantes", desc: "Si supieran dónde está el problema, ¿qué les impediría resolverlo?", Icon: IconLock },
];

export function DimensionsTimeline() {
  return (
    <section id="metodologia" className="mx-auto max-w-6xl px-6 py-24 sm:px-8">
      <div className="mb-16 max-w-xl">
        <span className="font-mono text-xs tracking-widest text-brand-400 uppercase">Metodología</span>
        <h2 className="mt-3 text-3xl font-bold text-white sm:text-4xl">
          Cinco dimensiones, una secuencia lógica
        </h2>
        <p className="mt-3 text-white/50">
          No medimos madurez en abstracto — medimos cómo tu organización enfrenta, en orden,
          un problema real de coordinación entre capas.
        </p>
      </div>

      {/* Desktop: timeline horizontal */}
      <div className="relative hidden lg:block">
        <div className="absolute top-8 right-0 left-0 h-px bg-white/10" />
        <div className="animate-draw-line absolute top-8 left-0 h-px bg-gradient-to-r from-brand-500 via-brand-400 to-accent-500" />
        <div className="grid grid-cols-5 gap-6">
          {DIMENSIONES.map((d, i) => (
            <div
              key={d.n}
              className="animate-fade-up group relative flex flex-col items-center text-center"
              style={{ animationDelay: `${i * 140}ms` }}
            >
              <div className="relative z-10 flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-ink-900 text-brand-400 shadow-[0_0_0_6px_var(--color-ink-950)] transition duration-300 group-hover:border-brand-500/50 group-hover:text-brand-300 group-hover:shadow-[0_0_30px_-6px_theme(colors.brand.500)]">
                <d.Icon className="h-7 w-7" />
              </div>
              <span className="mt-4 font-mono text-[11px] text-white/30">{d.n}</span>
              <h3 className="mt-2 text-sm font-semibold text-white">{d.title}</h3>
              <p className="mt-2 text-xs leading-relaxed text-white/45">{d.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Mobile / tablet: timeline vertical */}
      <div className="relative flex flex-col gap-8 lg:hidden">
        <div className="absolute top-2 bottom-2 left-8 w-px bg-white/10" />
        {DIMENSIONES.map((d, i) => (
          <div
            key={d.n}
            className="animate-fade-up relative flex items-start gap-5 pl-0"
            style={{ animationDelay: `${i * 120}ms` }}
          >
            <div className="relative z-10 flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-ink-900 text-brand-400">
              <d.Icon className="h-7 w-7" />
            </div>
            <div className="pt-1">
              <span className="font-mono text-[11px] text-white/30">{d.n}</span>
              <h3 className="mt-1 text-sm font-semibold text-white">{d.title}</h3>
              <p className="mt-1.5 text-xs leading-relaxed text-white/45">{d.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
