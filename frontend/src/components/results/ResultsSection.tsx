import { DIMENSION_ORDER } from "../../lib/questionnaire";
import type { ResultadoResponse } from "../../types";
import { DiagnosticoCard } from "./DiagnosticoCard";
import { ScoreCard } from "./ScoreCard";
import { SegmentComparisonChart } from "./SegmentComparisonChart";

export function ResultsSection({ resultado }: { resultado: ResultadoResponse | null }) {
  return (
    <section className="mx-auto max-w-5xl px-6 py-16 sm:px-8">
      <div className="mb-12">
        <span className="font-mono text-xs tracking-widest text-accent-400 uppercase">Tu diagnóstico</span>
        <h2 className="mt-3 text-3xl font-bold text-white sm:text-4xl">Tu posición en el benchmark</h2>
        <p className="mt-3 max-w-xl text-white/50">
          Comparado contra la distribución de operadores de tu misma industria.
        </p>
      </div>

      {!resultado ? (
        <div className="rounded-2xl border border-dashed border-white/10 bg-ink-800/30 px-8 py-16 text-center">
          <p className="text-white/40">Todavía no hay un diagnóstico para mostrar.</p>
        </div>
      ) : (
        <div className="grid gap-8">
          <DiagnosticoCard resultado={resultado} />

          <div>
            <h3 className="mb-4 text-sm font-semibold tracking-wide text-white/40 uppercase">
              Score por dimensión
            </h3>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[...resultado.scores]
                .sort((a, b) => DIMENSION_ORDER.indexOf(a.dimension) - DIMENSION_ORDER.indexOf(b.dimension))
                .map((score) => (
                  <ScoreCard
                    key={score.dimension}
                    score={score}
                    destacada={score.dimension === resultado.friccion_principal}
                  />
                ))}
            </div>
          </div>

          <div>
            <h3 className="mb-4 text-sm font-semibold tracking-wide text-white/40 uppercase">
              Comparación por segmento
            </h3>
            <SegmentComparisonChart scores={resultado.scores} />
          </div>
        </div>
      )}
    </section>
  );
}
