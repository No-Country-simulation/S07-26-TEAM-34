import { DIMENSION_LABELS, PERFIL_LABELS } from "../../lib/questionnaire";
import type { ResultadoResponse } from "../../types";

const CONFIANZA_ESTILOS: Record<string, string> = {
  alto: "border-brand-500/30 bg-brand-500/10 text-brand-400",
  medio: "border-amber-400/30 bg-amber-400/10 text-amber-400",
  bajo: "border-rose-400/30 bg-rose-400/10 text-rose-400",
};

const CONFIANZA_LABELS: Record<string, string> = {
  alto: "Confianza alta",
  medio: "Confianza media",
  bajo: "Confianza baja",
};

export function DiagnosticoCard({ resultado }: { resultado: ResultadoResponse }) {
  const friccion = resultado.scores.find((s) => s.dimension === resultado.friccion_principal);
  const friccionLabel = DIMENSION_LABELS[resultado.friccion_principal] ?? resultado.friccion_principal;
  const confianzaEstilo = CONFIANZA_ESTILOS[resultado.confianza_nivel] ?? CONFIANZA_ESTILOS.bajo;
  const confianzaLabel = CONFIANZA_LABELS[resultado.confianza_nivel] ?? "Confianza";

  return (
    <div className="relative overflow-hidden rounded-3xl border border-brand-500/20 bg-gradient-to-br from-ink-800 to-ink-900 p-8 sm:p-10">
      <div className="pointer-events-none absolute -top-24 -right-24 h-64 w-64 animate-glow rounded-full bg-brand-500/20 blur-3xl" />

      <div className="relative">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 font-mono text-[11px] tracking-wide text-brand-400 uppercase">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-400" />
            Diagnóstico generado por IA
          </span>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[11px] tracking-wide uppercase ${confianzaEstilo}`}
            title={resultado.confianza_descripcion}
          >
            {confianzaLabel}
          </span>
        </div>

        <h3 className="mt-4 text-2xl font-bold text-white sm:text-3xl">{resultado.titular}</h3>
        <p className="mt-1 text-sm text-white/40">{PERFIL_LABELS[resultado.perfil] ?? resultado.perfil}</p>

        {friccion && (
          <div className="mt-5 inline-flex items-center gap-3 rounded-xl border border-white/10 bg-ink-950/50 px-4 py-2.5">
            <span className="text-xs text-white/50">Fricción principal</span>
            <span className="text-sm font-medium text-white">{friccionLabel}</span>
            <span className="font-mono text-sm text-white/60">
              {friccion.score.toFixed(0)}/100 · percentil {friccion.percentil.toFixed(0)}
            </span>
          </div>
        )}

        <p className="mt-5 max-w-2xl text-base leading-relaxed text-white/70">
          {resultado.diagnostico_texto}
        </p>

        <div className="mt-6 rounded-2xl border border-accent-500/20 bg-accent-500/5 p-5">
          <span className="font-mono text-[11px] tracking-wide text-accent-400 uppercase">
            Próximo paso
          </span>
          <p className="mt-1.5 text-sm leading-relaxed text-white/70">{resultado.accion_sugerida}</p>
        </div>

        {resultado.porcentaje_capacidad_varada !== null && (
          <div className="mt-6 inline-flex items-baseline gap-2 rounded-xl border border-white/10 bg-ink-950/50 px-5 py-3">
            <span className="font-mono text-3xl font-semibold text-white">
              {resultado.porcentaje_capacidad_varada.toFixed(0)}%
            </span>
            <span className="text-xs text-white/40">de capacidad estimada como varada</span>
          </div>
        )}
      </div>
    </div>
  );
}
