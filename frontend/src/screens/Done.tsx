import { useEffect, useState } from "react";
import { api } from "../api";
import type { Task } from "../types";
import { dateTile, usd } from "../format";
import { IconCalendar, IconCheck, IconDownload, IconShield } from "../components/Icons";

export function Done({ task, onDeadlines, onNew }: { task: Task; onDeadlines: () => void; onNew: () => void }) {
  const [rawSent, setRawSent] = useState<number | null>(null);
  const [protectedCount, setProtectedCount] = useState<number | null>(null);
  useEffect(() => {
    api
      .privacy(task.task_id)
      .then((p) => {
        setRawSent(p.raw_pii_sent);
        setProtectedCount(p.protected_count);
      })
      .catch(() => setRawSent(null));
  }, [task.task_id]);

  return (
    <div className="animate-fade-in pt-6">
      <div className="flex flex-col items-center text-center">
        <span className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-emerald-600 text-white shadow-lift">
          <IconCheck className="h-8 w-8" />
        </span>
        <h1 className="mt-4 text-[1.75rem] font-bold sm:text-3xl">Your paperwork is ready</h1>
        <p className="mt-2 max-w-md text-ink-600">
          You confirmed everything. Download your files below — PaperPilot has not sent or submitted anything on your behalf.
        </p>
      </div>

      <section className="mt-6 grid gap-3 sm:grid-cols-2">
        {task.final_pdf_url && (
          <a href={task.final_pdf_url} download className="card flex min-h-[72px] items-center gap-3 p-4 transition hover:border-accent-300 hover:shadow-lift">
            <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-accent-600 text-white">
              <IconDownload />
            </span>
            <span>
              <span className="block font-semibold">Completed form</span>
              <span className="block text-sm text-ink-500">PDF</span>
            </span>
          </a>
        )}
        {task.letter_pdf_url && (
          <a href={task.letter_pdf_url} download className="card flex min-h-[72px] items-center gap-3 p-4 transition hover:border-accent-300 hover:shadow-lift">
            <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-ink-900 text-white">
              <IconDownload />
            </span>
            <span>
              <span className="block font-semibold">Response letter</span>
              <span className="block text-sm text-ink-500">PDF</span>
            </span>
          </a>
        )}
      </section>

      <section className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="card p-4">
          <p className="eyebrow flex items-center gap-1">
            <IconCalendar className="h-3.5 w-3.5" /> Deadline saved
          </p>
          {task.deadlines.length ? (
            task.deadlines.slice(0, 2).map((d, i) => {
              const t = dateTile(d.date);
              return (
                <p key={i} className="mt-1 font-semibold">
                  {t.month} {t.day} <span className="font-normal text-ink-600">· {d.title}</span>
                </p>
              );
            })
          ) : (
            <p className="mt-1 text-ink-600">No deadlines found</p>
          )}
        </div>
        <div className="card p-4">
          <p className="eyebrow">This task cost</p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{usd(task.cost_usd)}</p>
        </div>
        <div className="card p-4">
          <p className="eyebrow flex items-center gap-1">
            <IconShield className="h-3.5 w-3.5" /> Privacy
          </p>
          <p className="mt-1 font-semibold text-emerald-700">
            {rawSent === null ? "—" : `${rawSent} raw personal values sent to cloud`}
          </p>
          {protectedCount !== null && <p className="text-sm text-ink-500">{protectedCount} values protected locally</p>}
        </div>
      </section>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <button className="btn-secondary" onClick={onDeadlines}>
          <IconCalendar className="h-5 w-5" /> View deadlines
        </button>
        <button className="btn-primary" onClick={onNew}>
          Handle another document
        </button>
      </div>
    </div>
  );
}
