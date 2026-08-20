import { DIMENSION_LABELS, DIMENSION_ORDER } from "../../lib/questionnaire";
import type { ScoreDimension } from "../../types";

function Barra({
  label,
  score,
  medianaRef,
  p75Ref,
}: {
  label: string;
  score: number;
  medianaRef: number;
  p75Ref: number;
}) {
  return (
    <div className="grid grid-cols-[1fr] gap-2 sm:grid-cols-[9rem_1fr] sm:items-center">
      <span className="text-sm font-medium text-white/70">{label}</span>
      <div className="relative h-6 w-full rounded-full bg-white/5">
        <div
          className="h-full rounded-full bg-gradient-to-r from-brand-500 to-accent-500"
          style={{ width: `${Math.max(score, 2)}%` }}
        />
        <div
          className="absolute top-0 h-full w-0.5 bg-white/50"
          style={{ left: `${medianaRef}%` }}
          title={`Mediana del grupo: ${medianaRef.toFixed(0)}`}
        />
        <div
          className="absolute top-0 h-full w-0.5 bg-emerald-400"
          style={{ left: `${p75Ref}%` }}
          title={`Cuartil superior del grupo: ${p75Ref.toFixed(0)}`}
        />
        <span className="absolute -top-5 right-0 font-mono text-[11px] text-white/40">
          {score.toFixed(0)}/100
        </span>
      </div>
    </div>
  );
}

export function SegmentComparisonChart({ scores }: { scores: ScoreDimension[] }) {
  const ordenadas = [...scores].sort(
    (a, b) => DIMENSION_ORDER.indexOf(a.dimension) - DIMENSION_ORDER.indexOf(b.dimension)
  );

  return (
    <div className="rounded-2xl border border-white/10 bg-ink-800/60 p-6 sm:p-8">
      <h4 className="text-sm font-semibold tracking-wide text-white/70">
        Tu score frente a la mediana y al cuartil superior del grupo comparable
      </h4>
      <p className="mt-1 text-xs leading-relaxed text-white/40">
        La barra de color es tu score. La línea blanca marca la mediana de operadores comparables;
        la línea verde marca el cuartil superior (top 25%).
      </p>

      <div className="mt-8 flex flex-col gap-6">
        {ordenadas.map((s) => (
          <Barra
            key={s.dimension}
            label={DIMENSION_LABELS[s.dimension] ?? s.dimension}
            score={s.score}
            medianaRef={s.mediana_ref}
            p75Ref={s.p75_ref}
          />
        ))}
      </div>

      <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-xs text-white/40">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-gradient-to-r from-brand-500 to-accent-500" />
          Tu score
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-0.5 bg-white/50" />
          Mediana del grupo
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-0.5 bg-emerald-400" />
          Cuartil superior
        </span>
      </div>
    </div>
  );
}
