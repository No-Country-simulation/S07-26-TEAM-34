import { PERFIL_LABELS } from "../../lib/questionnaire";

export function DiagnosticoCard({
  perfil,
  diagnosticoTexto,
  porcentajeCapacidadVarada,
}: {
  perfil: string;
  diagnosticoTexto: string;
  porcentajeCapacidadVarada: number | null;
}) {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-brand-500/20 bg-gradient-to-br from-ink-800 to-ink-900 p-8 sm:p-10">
      <div className="pointer-events-none absolute -top-24 -right-24 h-64 w-64 animate-glow rounded-full bg-brand-500/20 blur-3xl" />

      <div className="relative">
        <span className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 font-mono text-[11px] tracking-wide text-brand-400 uppercase">
          <span className="h-1.5 w-1.5 rounded-full bg-brand-400" />
          Diagnóstico generado por IA
        </span>

        <h3 className="mt-4 text-2xl font-bold text-white sm:text-3xl">
          {PERFIL_LABELS[perfil] ?? perfil}
        </h3>

        <p className="mt-5 max-w-2xl text-base leading-relaxed text-white/70">{diagnosticoTexto}</p>

        {porcentajeCapacidadVarada !== null && (
          <div className="mt-8 inline-flex items-baseline gap-2 rounded-xl border border-white/10 bg-ink-950/50 px-5 py-3">
            <span className="font-mono text-3xl font-semibold text-white">
              {porcentajeCapacidadVarada.toFixed(0)}%
            </span>
            <span className="text-xs text-white/40">de capacidad estimada como varada</span>
          </div>
        )}
      </div>
    </div>
  );
}
