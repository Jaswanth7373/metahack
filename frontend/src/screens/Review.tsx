import { useEffect, useMemo, useRef, useState } from "react";
import { api, errorMessage, urls } from "../api";
import type { Field, Task } from "../types";
import { pct } from "../format";
import { Badge } from "../components/Badge";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ErrorBanner } from "../components/ErrorBanner";
import { IconAlert, IconCheck, IconLock } from "../components/Icons";
import { PageImage } from "../components/PageImage";
import { Spinner } from "../components/Spinner";

function confidenceTone(f: Field) {
  if (f.needs_review) return "warn" as const;
  if (f.confidence >= 0.9) return "local" as const;
  return "neutral" as const;
}

export function Review({ task, onTask, onConfirmed }: { task: Task; onTask: (t: Task) => void; onConfirmed: (t: Task) => void }) {
  const [page, setPage] = useState(0);
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(task.fields.map((f) => [f.name, f.value])));
  const [letter, setLetter] = useState(task.letter?.body ?? "");
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [dialog, setDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [version, setVersion] = useState(() => Date.now());
  const [active, setActive] = useState<string | null>(null);
  const fieldRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    setValues(Object.fromEntries(task.fields.map((f) => [f.name, f.value])));
  }, [task.fields]);

  const dirty = useMemo(() => task.fields.some((f) => (values[f.name] ?? "") !== f.value), [task.fields, values]);
  const needsReview = task.fields.filter((f) => f.needs_review);
  const pages = Math.max(1, task.page_count || 1);
  const confirmed = task.status === "confirmed";

  async function save(): Promise<Task | null> {
    setError(null);
    setSaving(true);
    try {
      const changed: Record<string, string> = {};
      for (const f of task.fields) if ((values[f.name] ?? "") !== f.value) changed[f.name] = values[f.name] ?? "";
      const t = await api.saveFields(task.task_id, changed);
      onTask(t);
      setVersion(Date.now());
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
      return t;
    } catch (e) {
      setError(errorMessage(e));
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function confirm() {
    setConfirming(true);
    setError(null);
    try {
      if (dirty) {
        const t = await save();
        if (!t) return;
      }
      const t = await api.confirm(task.task_id, task.letter ? letter : undefined);
      onTask(t);
      setDialog(false);
      onConfirmed(t);
    } catch (e) {
      setError(errorMessage(e));
      setDialog(false);
    } finally {
      setConfirming(false);
    }
  }

  function focusField(name: string) {
    setActive(name);
    const el = fieldRefs.current[name];
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    el?.querySelector<HTMLElement>("input,textarea,select")?.focus({ preventScroll: true });
  }

  return (
    <div className="animate-fade-in">
      {needsReview.length > 0 ? (
        <div className="mt-5 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
          <IconAlert className="mt-0.5 h-5 w-5" />
          <p>
            <strong>{needsReview.length} field{needsReview.length === 1 ? "" : "s"} need your review.</strong> They're highlighted in amber.
          </p>
        </div>
      ) : (
        <div className="mt-5 flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-900">
          <IconCheck className="h-5 w-5" />
          <p>All fields were verified with high confidence. Please still check them.</p>
        </div>
      )}

      {pages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-2" role="group" aria-label="Page">
          {Array.from({ length: pages }, (_, i) => (
            <button
              key={i}
              onClick={() => setPage(i)}
              aria-current={page === i ? "page" : undefined}
              className={`h-11 min-w-[44px] rounded-xl px-3 text-sm font-semibold ${page === i ? "bg-ink-900 text-white" : "bg-white text-ink-700 ring-1 ring-ink-200"}`}
            >
              Page {i + 1}
            </button>
          ))}
        </div>
      )}

      <section className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <p className="eyebrow mb-2">Original</p>
          <PageImage src={urls.originalPage(task.document_id, page)} alt={`Original document, page ${page + 1}`} />
        </div>
        <div>
          <p className="eyebrow mb-2 flex items-center gap-1.5">
            Filled <span className="normal-case tracking-normal text-ink-400">· values restored locally</span>
          </p>
          <PageImage
            src={urls.filledPage(task.task_id, page, version)}
            alt={`Filled document preview, page ${page + 1}`}
            fields={task.fields}
            page={page}
            activeField={active}
            onFieldClick={focusField}
          />
        </div>
      </section>

      <section className="card mt-5 p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-bold">Form fields</h2>
          {saved && <Badge tone="local">Saved</Badge>}
        </div>
        {task.fields.length === 0 && <p className="mt-3 text-ink-600">This document has no fillable fields.</p>}
        <div className="mt-3 space-y-4">
          {task.fields.map((f) => {
            const id = `field-${f.name}`;
            const v = values[f.name] ?? "";
            return (
              <div
                key={f.name}
                ref={(el) => (fieldRefs.current[f.name] = el)}
                className={`rounded-xl p-3 transition-colors ${f.needs_review ? "bg-amber-50 ring-1 ring-inset ring-amber-200" : ""} ${
                  active === f.name ? "ring-2 ring-accent-500" : ""
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label htmlFor={id} className="label mb-0 flex items-center gap-1.5">
                    {f.label}
                    {f.contains_pii && (
                      <span title="Personal value — filled locally, never sent to cloud AI" className="text-emerald-600">
                        <IconLock className="h-3.5 w-3.5" />
                      </span>
                    )}
                  </label>
                  <Badge tone={confidenceTone(f)}>
                    {f.needs_review ? "⚠ Please review · " : ""}
                    AI confidence {pct(f.confidence)}
                  </Badge>
                </div>
                {f.kind === "checkbox" ? (
                  <label className="mt-2 inline-flex min-h-[44px] cursor-pointer items-center gap-3">
                    <input
                      id={id}
                      type="checkbox"
                      className="h-5 w-5 rounded border-ink-300 text-accent-600 focus:ring-accent-500"
                      checked={v === "Yes"}
                      onChange={(e) => setValues((s) => ({ ...s, [f.name]: e.target.checked ? "Yes" : "Off" }))}
                      onFocus={() => setActive(f.name)}
                    />
                    <span className="text-ink-800">{v === "Yes" ? "Checked" : "Not checked"}</span>
                  </label>
                ) : f.kind === "multiline" ? (
                  <textarea
                    id={id}
                    className="input mt-2 min-h-[96px] resize-y"
                    value={v}
                    dir="auto"
                    onFocus={() => setActive(f.name)}
                    onChange={(e) => setValues((s) => ({ ...s, [f.name]: e.target.value }))}
                  />
                ) : (
                  <input
                    id={id}
                    className="input mt-2"
                    value={v}
                    dir="auto"
                    onFocus={() => setActive(f.name)}
                    onChange={(e) => setValues((s) => ({ ...s, [f.name]: e.target.value }))}
                  />
                )}
                {f.note && <p className={`mt-1.5 text-sm ${f.needs_review ? "text-amber-800" : "text-ink-500"}`}>{f.note}</p>}
              </div>
            );
          })}
        </div>
        {task.fields.length > 0 && (
          <button className="btn-secondary mt-4 w-full" onClick={save} disabled={!dirty || saving || confirmed}>
            {saving && <Spinner className="h-4 w-4" />} Save changes
          </button>
        )}
      </section>

      {task.letter && (
        <section className="card mt-4 p-5 sm:p-6">
          <h2 className="text-lg font-bold">Response letter</h2>
          <p className="mt-1 text-sm text-ink-500">Drafted for you — edit anything before confirming.</p>
          <p className="mt-3 text-sm font-semibold text-ink-700">Subject: {task.letter.subject}</p>
          <label htmlFor="letter" className="sr-only">
            Letter body
          </label>
          <textarea
            id="letter"
            className="input mt-2 min-h-[260px] resize-y font-[450] leading-relaxed"
            value={letter}
            dir="auto"
            onChange={(e) => setLetter(e.target.value)}
            disabled={confirmed}
          />
        </section>
      )}

      {task.verification && (
        <section className="card mt-4 p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-bold">Verification</h2>
            <Badge tone={task.verification.overall_confidence >= 0.85 ? "local" : "warn"}>
              Overall {pct(task.verification.overall_confidence)}
            </Badge>
          </div>
          <p className="mt-2 text-ink-700">{task.verification.summary}</p>
          {task.verification.issues.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {task.verification.issues.map((i, k) => (
                <li key={k} className="flex gap-2 text-sm text-amber-900">
                  <IconAlert className="mt-0.5 h-4 w-4 text-amber-600" /> {i}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      {!confirmed && (
        <div className="sticky bottom-4 z-20 mt-6">
          <button className="btn-primary w-full py-3.5 text-[1.05rem] shadow-lift" onClick={() => setDialog(true)} disabled={saving}>
            <IconCheck className="h-5 w-5" /> Confirm &amp; generate
          </button>
        </div>
      )}

      <ConfirmDialog
        open={dialog}
        busy={confirming}
        hasLetter={!!task.letter}
        deadlineCount={task.deadlines.length}
        onCancel={() => setDialog(false)}
        onConfirm={confirm}
      />
    </div>
  );
}
