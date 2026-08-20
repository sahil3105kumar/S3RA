import type { ToolName } from "@/lib/types";

const LABELS: Record<string, string> = {
  search_internal_db: "your documents",
  search_the_web: "web search",
};

export function ToolBadges({ tools }: { tools: ToolName[] }) {
  if (!tools.length) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {tools.map((tool) => (
        <span
          key={tool}
          className="inline-flex items-center gap-1 rounded-full border border-ink-600 bg-ink-800 px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wide text-ink-300"
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              tool === "search_internal_db" ? "bg-flag" : "bg-signal"
            }`}
          />
          {LABELS[tool] ?? tool}
        </span>
      ))}
    </div>
  );
}
