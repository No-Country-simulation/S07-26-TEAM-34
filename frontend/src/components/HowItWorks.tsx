const DIMENSIONES = [
  { n: "01", title: "Visibilidad cross-layer", desc: "¿Tenés una vista unificada de energía, cooling y workload?" },
  { n: "02", title: "Atribución de fricción", desc: "¿En qué interfaz perciben la mayor pérdida de capacidad?" },
  { n: "03", title: "Latencia de coordinación", desc: "¿Qué tan rápido se ajustan cooling y energía ante un cambio de carga?" },
  { n: "04", title: "Auto-cuantificación", desc: "¿Saben, con números, cuánta capacidad tienen varada hoy?" },
  { n: "05", title: "Bloqueantes", desc: "Si supieran dónde está el problema, ¿qué les impediría resolverlo?" },
];

export function HowItWorks() {
  return (
    <section id="como-funciona" className="mx-auto max-w-5xl px-6 py-24 sm:px-8">
      <div className="mb-14 max-w-xl">
        <span className="font-mono text-xs tracking-widest text-brand-400 uppercase">Metodología</span>
        <h2 className="mt-3 text-3xl font-bold text-white sm:text-4xl">
          Cinco dimensiones, una secuencia lógica
        </h2>
        <p className="mt-3 text-white/50">
          No medimos madurez en abstracto — medimos cómo tu organización enfrenta, en orden,
          un problema real de coordinación entre capas.
        </p>
      </div>

      <div className="grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/5 sm:grid-cols-2">
        {DIMENSIONES.map((d) => (
          <div key={d.n} className="bg-ink-900 p-6 transition hover:bg-ink-800/80 sm:p-7">
            <span className="font-mono text-xs text-white/30">{d.n}</span>
            <h3 className="mt-2 font-semibold text-white">{d.title}</h3>
            <p className="mt-2 text-sm text-white/50">{d.desc}</p>
          </div>
        ))}
        <div className="flex flex-col justify-center bg-gradient-to-br from-brand-500/10 to-accent-500/10 p-6 sm:p-7">
          <p className="text-sm text-white/70">
            Cada respuesta anónima se suma a un dataset propio que crece con el tiempo — mejorando
            la precisión del benchmark para todos los que lo usan después.
          </p>
        </div>
      </div>
    </section>
  );
}
