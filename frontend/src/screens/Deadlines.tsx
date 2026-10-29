import { useEffect, useState } from "react";
import { api, errorMessage, urls } from "../api";
import type { Deadline } from "../types";
import { dateTile, daysRemaining, remainingLabel } from "../format";
import { ErrorBanner } from "../components/ErrorBanner";
import { IconCalendar, IconDownload, IconTrash } from "../components/Icons";
import { Spinner } from "../components/Spinner";

export function Deadlines() {
  const [items, setItems] = useState<Deadline[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [description, setDescription] = useState("");
  const [adding, setAdding] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const load = () => {
    setError(null);
    api
      .deadlines()
      .then((d) => setItems([...d].sort((a, b) => a.date.localeCompare(b.date))))
      .catch((e) => setError(errorMessage(e)));
  };
  useEffect(load, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !date) return;
    setAdding(true);
    setError(null);
    try {
      await api.addDeadline({ title: title.trim(), date, description: description.trim() });
      setTitle("");
      setDate("");
      setDescription("");
      setShowForm(false);
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setAdding(false);
    }
  }

  async function remove(id: number) {
    setError(null);
    try {
      await api.deleteDeadline(id);
      setItems((s) => (s ?? []).filter((d) => d.id !== id));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="animate-fade-in pt-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Stay on time</p>
          <h1 className="mt-1 text-2xl font-bold sm:text-3xl">Upcoming deadlines</h1>
        </div>
        <a href={urls.exportIcs} className="btn-secondary text-sm" download>
          <IconDownload className="h-4 w-4" /> Export all (.ics)
        </a>
      </div>

      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} onRetry={load} onDismiss={() => setError(null)} />
        </div>
      )}

      <section className="mt-5 space-y-3">
        {items === null && !error && (
          <div className="card flex items-center gap-2 p-4 text-ink-500">
            <Spinner className="h-5 w-5" /> Loading…
          </div>
        )}
        {items?.length === 0 && (
          <div className="card p-6 text-center text-ink-600">
            <IconCalendar className="mx-auto h-8 w-8 text-ink-300" />
            <p className="mt-2">No deadlines yet. Confirmed tasks add their deadlines here automatically.</p>
          </div>
        )}
        {items?.map((d) => {
          const t = dateTile(d.date);
          const left = daysRemaining(d.date, d.days_remaining);
          const urgent = left !== null && left <= 7 && left >= 0;
          const overdue = left !== null && left < 0;
          return (
            <article key={d.id ?? `${d.title}-${d.date}`} className="card flex items-center gap-4 p-4">
              <div
                className={`flex h-[72px] w-[68px] shrink-0 flex-col items-center justify-center rounded-xl text-white ${
                  overdue ? "bg-rose-600" : urgent ? "bg-amber-500" : "bg-ink-900"
                }`}
              >
                <span className="text-xs font-semibold tracking-wider">{t.month}</span>
                <span className="text-2xl font-bold leading-none">{t.day}</span>
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{d.title}</p>
                <p className={`text-sm ${overdue ? "text-rose-700" : urgent ? "font-semibold text-amber-800" : "text-ink-600"}`}>
                  {remainingLabel(left)}
                </p>
                {d.description && <p className="mt-0.5 line-clamp-2 text-sm text-ink-500">{d.description}</p>}
              </div>
              {typeof d.id === "number" && (
                <div className="flex shrink-0 flex-col gap-1 sm:flex-row">
                  <a href={urls.deadlineIcs(d.id)} download className="inline-flex h-11 w-11 items-center justify-center rounded-xl text-ink-600 hover:bg-ink-100" aria-label={`Add “${d.title}” to calendar`}>
                    <IconCalendar />
                  </a>
                  <button onClick={() => remove(d.id!)} className="inline-flex h-11 w-11 items-center justify-center rounded-xl text-ink-500 hover:bg-rose-50 hover:text-rose-700" aria-label={`Delete “${d.title}”`}>
                    <IconTrash />
                  </button>
                </div>
              )}
            </article>
          );
        })}
      </section>

      <section className="mt-6">
        {!showForm ? (
          <button className="btn-secondary w-full" onClick={() => setShowForm(true)}>
            + Add deadline
          </button>
        ) : (
          <form className="card space-y-3 p-5 animate-fade-in" onSubmit={add}>
            <h2 className="text-lg font-bold">Add deadline</h2>
            <div>
              <label className="label" htmlFor="dl-title">
                Title
              </label>
              <input id="dl-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />
            </div>
            <div>
              <label className="label" htmlFor="dl-date">
                Date
              </label>
              <input id="dl-date" type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} required />
            </div>
            <div>
              <label className="label" htmlFor="dl-desc">
                Notes (optional)
              </label>
              <textarea id="dl-desc" className="input min-h-[80px]" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={1000} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button type="submit" className="btn-primary" disabled={adding || !title.trim() || !date}>
                {adding && <Spinner className="h-4 w-4" />} Save
              </button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
