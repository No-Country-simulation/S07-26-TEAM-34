import type { ReactNode } from "react";

export function DimensionCard({
  index,
  title,
  children,
}: {
  index: number;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-ink-800/60 p-6 sm:p-8">
      <div className="mb-6 flex items-center gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-500/15 font-mono text-xs font-semibold text-brand-400">
          {String(index).padStart(2, "0")}
        </span>
        <h3 className="text-lg font-semibold text-white">{title}</h3>
      </div>
      <div className="grid gap-6 sm:grid-cols-2">{children}</div>
    </div>
  );
}
