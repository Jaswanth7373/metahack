import type { Health } from "../types";
import { usdShort } from "../format";
import { Badge, Dot } from "./Badge";
import { IconCalendar } from "./Icons";

export function TopBar({
  health,
  onHome,
  onDeadlines,
  active,
}: {
  health: Health | null;
  onHome: () => void;
  onDeadlines: () => void;
  active: "deadlines" | "other";
}) {
  const b = health?.budget;
  const engine = health?.privacy_engine;
  return (
    <header className="sticky top-0 z-30 border-b border-ink-200/70 bg-white/90 backdrop-blur supports-[backdrop-filter]:bg-white/75">
      <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-2.5">
        <button onClick={onHome} className="flex min-h-[44px] items-center gap-2 rounded-lg pr-1" aria-label="PaperPilot home">
          <img src="/favicon.svg" alt="" className="h-8 w-8" />
          <span className="text-[1.05rem] font-bold tracking-tight text-ink-900">PaperPilot</span>
        </button>
        <div className="ml-auto flex items-center gap-1.5 overflow-hidden">
          {health?.demo_mode && (
            <Badge tone="replay" title="Model responses are replayed from the local demo cache">
              Demo mode
            </Badge>
          )}
          {engine && (
            <span className="hidden sm:inline-flex">
              <Badge tone={engine.mode === "glimmer" ? "local" : "neutral"} title={engine.model ?? undefined}>
                <Dot className={engine.mode === "glimmer" ? "bg-emerald-500" : "bg-ink-400"} />
                {engine.label}
              </Badge>
            </span>
          )}
          {b && (
            <span
              className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium tabular-nums ring-1 ring-inset ${
                b.blocked ? "bg-rose-50 text-rose-800 ring-rose-200" : "bg-ink-50 text-ink-700 ring-ink-200"
              }`}
              title="Meta Model API spend against the configured budget cap"
            >
              {usdShort(b.used_usd)} <span className="text-ink-400">of</span> ${b.cap_usd.toFixed(0)}
            </span>
          )}
          <button
            onClick={onDeadlines}
            aria-label="Deadlines"
            aria-current={active === "deadlines" ? "page" : undefined}
            className={`ml-1 inline-flex h-11 w-11 items-center justify-center rounded-xl ${
              active === "deadlines" ? "bg-accent-50 text-accent-700" : "text-ink-600 hover:bg-ink-100"
            }`}
          >
            <IconCalendar />
          </button>
        </div>
      </div>
      {engine && (
        <div className="mx-auto flex max-w-3xl px-4 pb-2 sm:hidden">
          <Badge tone={engine.mode === "glimmer" ? "local" : "neutral"} title={engine.model ?? undefined}>
            <Dot className={engine.mode === "glimmer" ? "bg-emerald-500" : "bg-ink-400"} />
            Privacy engine: {engine.label}
          </Badge>
        </div>
      )}
      {b?.blocked && (
        <div className="border-t border-rose-200 bg-rose-50 px-4 py-2 text-center text-sm text-rose-800" role="alert">
          Budget limit reached. No additional paid AI requests will be made.
        </div>
      )}
    </header>
  );
}
