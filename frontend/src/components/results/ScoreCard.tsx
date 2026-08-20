import { DIMENSION_LABELS } from "../../lib/questionnaire";
import type { ScoreDimension } from "../../types";

export function ScoreCard({
  score,
  destacada,
}: {
  score: ScoreDimension;
  destacada?: boolean;
}) {
  const label = DIMENSION_LABELS[score.dimension] ?? score.dimension;

  return (
    <div
      className={`relative rounded-2xl border p-6 ${
        destacada
          ? "border-accent-500/40 bg-accent-500/[0.06] ring-1 ring-accent-500/20"
          : "border-white/10 bg-ink-800/60"
      }`}
    >
      {destacada && (
        <span className="absolute -top-2.5 left-5 rounded-full border border-accent-500/40 bg-ink-900 px-2.5 py-0.5 font-mono text-[10px] tracking-wide text-accent-400 uppercase">
          Fricción principal
        </span>
      )}

      <div className="mb-4 flex items-start justify-between gap-4">
        <h4 className="text-sm font-medium text-white/70">{label}</h4>
        <span className="rounded-full bg-white/5 px-2.5 py-1 font-mono text-[11px] text-white/50">
          percentil {score.percentil.toFixed(0)}
        </span>
      </div>

      <div className="mb-3 flex items-baseline gap-1">
        <span className="font-mono text-4xl font-semibold text-white">{score.score.toFixed(0)}</span>
        <span className="font-mono text-sm text-white/30">/100</span>
      </div>

      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
        <div
          className="h-full rounded-full bg-gradient-to-r from-brand-500 to-accent-500"
          style={{ width: `${Math.max(score.score, 3)}%` }}
        />
      </div>

      {score.descripcion_breve && (
        <p className="mt-4 text-xs leading-relaxed text-white/40">{score.descripcion_breve}</p>
      )}
    </div>
  );
}
