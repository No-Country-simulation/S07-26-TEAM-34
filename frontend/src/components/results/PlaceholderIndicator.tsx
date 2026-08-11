export function PlaceholderIndicator({ title, description }: { title: string; description: string }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-dashed border-white/10 bg-ink-800/30 p-6">
      <div className="mb-4 flex items-start justify-between gap-4">
        <h4 className="text-sm font-medium text-white/40">{title}</h4>
        <span className="rounded-full border border-white/10 px-2.5 py-1 font-mono text-[10px] tracking-wide text-white/30 uppercase">
          Próximamente
        </span>
      </div>
      <p className="text-xs leading-relaxed text-white/30">{description}</p>
      <div className="mt-5 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
        <div className="h-full w-1/3 animate-pulse rounded-full bg-white/10" />
      </div>
    </div>
  );
}
