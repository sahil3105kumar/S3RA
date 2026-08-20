import type { Source } from "@/lib/types";

export function SourceList({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;

  return (
    <div className="mt-2 space-y-1 border-l-2 border-ink-700 pl-2.5">
      <p className="text-[10.5px] font-medium uppercase tracking-wide text-ink-400">Cited</p>
      <ul className="space-y-0.5">
        {sources.map((s, i) => (
          <li key={`${s.source}-${s.page}-${i}`} className="font-mono text-[11.5px] text-ink-300">
            {s.source}
            {s.page !== null && s.page !== undefined ? (
              <span className="text-ink-500"> · p.{s.page}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
