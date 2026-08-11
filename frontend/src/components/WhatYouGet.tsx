import { IconSpark } from "./icons";

const SAMPLE_SCORES = [
  { label: "Visibilidad", value: 81 },
  { label: "Latencia", value: 63 },
  { label: "Bloqueantes", value: 50 },
];

export function WhatYouGet() {
  return (
    <section className="mx-auto max-w-6xl px-6 py-24 sm:px-8">
      <div className="grid items-center gap-14 lg:grid-cols-2">
        <div>
          <span className="font-mono text-xs tracking-widest text-accent-400 uppercase">El resultado</span>
          <h2 className="mt-3 text-3xl font-bold text-white sm:text-4xl">
            No te devolvemos un número. Te devolvemos un diagnóstico.
          </h2>
          <p className="mt-4 max-w-md text-white/50">
            Un modelo de lenguaje redacta, a partir de tus respuestas y tu posición frente al resto
            de la industria, dónde está tu mayor fricción y qué explica esa brecha — sin inventar
            datos que no estén en tu diagnóstico.
          </p>
          <ul className="mt-8 grid gap-3 text-sm text-white/60">
            <li className="flex items-center gap-3">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-400" />
              Tu percentil en cada una de las 5 dimensiones
            </li>
            <li className="flex items-center gap-3">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-400" />
              Qué te separa del cuartil superior de tu industria
            </li>
            <li className="flex items-center gap-3">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-400" />
              % estimado de capacidad varada
            </li>
          </ul>
        </div>

        <div className="relative">
          <div className="pointer-events-none absolute -inset-6 -z-10 rounded-3xl bg-gradient-to-br from-brand-500/10 to-accent-500/10 blur-2xl" />
          <div className="rounded-3xl border border-white/10 bg-ink-800/70 p-6 sm:p-8">
            <div className="mb-5 flex items-center justify-between">
              <span className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 font-mono text-[10px] tracking-wide text-brand-400 uppercase">
                <IconSpark className="h-3 w-3" />
                Diagnóstico IA
              </span>
              <span className="font-mono text-[10px] text-white/25 uppercase">Ejemplo ilustrativo</span>
            </div>

            <p className="text-sm leading-relaxed text-white/70">
              "La principal fricción se concentra en bloqueantes estructurales, donde la restricción
              presupuestaria impide actuar sobre la pérdida de capacidad identificada en la interfaz
              cooling–workload…"
            </p>

            <div className="mt-6 grid grid-cols-3 gap-3">
              {SAMPLE_SCORES.map((s) => (
                <div key={s.label} className="rounded-xl border border-white/5 bg-ink-900 p-3">
                  <div className="font-mono text-xl font-semibold text-white">{s.value}</div>
                  <div className="mt-1 text-[10px] text-white/40">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
