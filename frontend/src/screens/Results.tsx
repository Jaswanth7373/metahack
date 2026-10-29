import { useState } from "react";
import type { Task } from "../types";
import { dateTile, daysRemaining, humanize, isRtl, longDate, remainingLabel, usd } from "../format";
import { Badge } from "../components/Badge";
import { IconAlert, IconArrowRight, IconCalendar, IconSparkle } from "../components/Icons";

export function Results({ task, onReview }: { task: Task; onReview: () => void }) {
  const [planOpen, setPlanOpen] = useState(false);
  const ex = task.explanation;
  const rtl = isRtl(task.user_language?.code);
  const langCode = task.user_language?.code;

  return (
    <div className="animate-fade-in">
      <div className="mt-5 flex flex-wrap items-center gap-2">
        <Badge tone="accent">{task.document_title || humanize(task.document_type)}</Badge>
        {task.user_language?.name && <Badge>Explained in {task.user_language.name}</Badge>}
        <Badge>AI cost {usd(task.cost_usd)}</Badge>
      </div>

      {task.deadlines.length > 0 && (
        <section className="mt-4 space-y-3">
          {task.deadlines.map((d, i) => {
            const t = dateTile(d.date);
            const left = daysRemaining(d.date, d.days_remaining);
            const urgent = left !== null && left <= 7;
            return (
              <div
                key={`${d.date}-${i}`}
                className={`flex items-center gap-4 rounded-2xl border p-4 ${urgent ? "border-amber-300 bg-amber-50" : "border-ink-200 bg-white"}`}
              >
                <div className={`flex h-[72px] w-[68px] shrink-0 flex-col items-center justify-center rounded-xl ${urgent ? "bg-amber-500 text-white" : "bg-ink-900 text-white"}`}>
                  <span className="text-xs font-semibold tracking-wider">{t.month}</span>
                  <span className="text-2xl font-bold leading-none">{t.day}</span>
                </div>
                <div className="min-w-0">
                  <p className="eyebrow flex items-center gap-1">
                    <IconCalendar className="h-3.5 w-3.5" /> Important date
                  </p>
                  <p className="font-semibold">{d.title}</p>
                  <p className="text-sm text-ink-600">
                    {longDate(d.date, langCode)} · <span className={urgent ? "font-semibold text-amber-800" : ""}>{remainingLabel(left)}</span>
                  </p>
                </div>
              </div>
            );
          })}
        </section>
      )}

      {ex ? (
        <div dir={rtl ? "rtl" : "auto"} lang={langCode}>
          <section className="card mt-4 p-5 sm:p-6">
            <h2 className="text-xl font-bold">What this document means</h2>
            <p className="mt-3 text-[1.08rem] font-medium leading-relaxed text-ink-900">{ex.summary}</p>
            {ex.what_it_means && <p className="mt-3 whitespace-pre-line leading-relaxed text-ink-700">{ex.what_it_means}</p>}
          </section>

          {ex.steps.length > 0 && (
            <section className="card mt-4 p-5 sm:p-6">
              <h2 className="text-xl font-bold">What you need to do</h2>
              <ol className="mt-4 space-y-3">
                {ex.steps.map((s, i) => (
                  <li key={i} className="flex gap-3">
                    <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-600 text-sm font-bold text-white">
                      {i + 1}
                    </span>
                    <span className="pt-0.5 leading-relaxed">{s}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {ex.warnings.length > 0 && (
            <section className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-5">
              <h2 className="flex items-center gap-2 font-bold text-amber-900">
                <IconAlert className="h-5 w-5" /> Watch out for
              </h2>
              <ul className="mt-2 list-disc space-y-1.5 pl-5 text-amber-900 rtl:pl-0 rtl:pr-5">
                {ex.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </section>
          )}
        </div>
      ) : (
        <section className="card mt-4 p-5 text-ink-600">No explanation was produced for this document.</section>
      )}

      {task.plan && (
        <section className="card mt-4 overflow-hidden">
          <button
            className="flex min-h-[56px] w-full items-center justify-between gap-3 px-5 py-3 text-left"
            aria-expanded={planOpen}
            onClick={() => setPlanOpen((o) => !o)}
          >
            <span className="flex items-center gap-2 font-semibold">
              <IconSparkle className="h-5 w-5 text-accent-600" /> How PaperPilot planned this
            </span>
            <span className="text-sm text-ink-500">{planOpen ? "Hide" : `${task.plan.actions.length} steps`}</span>
          </button>
          {planOpen && (
            <div className="border-t border-ink-100 px-5 pb-5 pt-3 animate-fade-in">
              <p className="text-sm text-ink-600">
                Document type: <strong>{humanize(task.plan.document_type)}</strong> · Intent: <strong>{humanize(task.plan.intent)}</strong>
              </p>
              <ol className="mt-3 space-y-2">
                {task.plan.actions.map((a, i) => (
                  <li key={i} className="rounded-xl bg-ink-50 p-3">
                    <code className="rounded bg-white px-1.5 py-0.5 font-mono text-sm text-accent-700 ring-1 ring-ink-200">{a.tool}</code>
                    <p className="mt-1 text-sm text-ink-700">{a.reason}</p>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </section>
      )}

      <div className="sticky bottom-4 z-20 mt-6">
        <button className="btn-primary w-full py-3.5 text-[1.05rem] shadow-lift" onClick={onReview}>
          Review the filled form <IconArrowRight className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
