import { Fragment, useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import type { Privacy as PrivacyT } from "../types";
import { Badge, Dot } from "../components/Badge";
import { ErrorBanner } from "../components/ErrorBanner";
import { IconArrowRight, IconCloud, IconEye, IconEyeOff, IconLock, IconShield } from "../components/Icons";
import { Spinner } from "../components/Spinner";

const PH = /(\[[A-Z][A-Z_]*_\d+\])/g;

function Highlighted({ text }: { text: string }) {
  const parts = text.split(PH);
  return (
    <>
      {parts.map((p, i) =>
        /^\[[A-Z][A-Z_]*_\d+\]$/.test(p) ? (
          <span key={i} className="chip-ph">
            {p}
          </span>
        ) : (
          <Fragment key={i}>{p}</Fragment>
        ),
      )}
    </>
  );
}

export function Privacy({ taskId }: { taskId: string }) {
  const [data, setData] = useState<PrivacyT | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revealAll, setRevealAll] = useState(false);
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});

  const load = () => {
    setError(null);
    api
      .privacy(taskId)
      .then(setData)
      .catch((e) => setError(errorMessage(e)));
  };
  useEffect(load, [taskId]);

  if (error) return <div className="mt-5"><ErrorBanner message={error} onRetry={load} /></div>;
  if (!data)
    return (
      <div className="mt-8 flex items-center justify-center gap-2 text-ink-500">
        <Spinner className="h-5 w-5" /> Loading privacy report…
      </div>
    );

  const zero = data.raw_pii_sent === 0;
  const isGlimmer = data.engine.mode === "glimmer";

  return (
    <div className="animate-fade-in">
      <section className="mt-5 overflow-hidden rounded-3xl bg-ink-950 p-6 text-white sm:p-8">
        <div className="flex items-center gap-2 text-emerald-300">
          <IconShield className="h-6 w-6" />
          <span className="text-sm font-semibold uppercase tracking-[0.1em]">Privacy Center</span>
        </div>
        <h1 className="mt-3 text-[1.75rem] font-bold leading-tight sm:text-4xl">Your information stays under your control.</h1>
        <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-sm ring-1 ring-inset ring-white/15">
          <Dot className={isGlimmer ? "bg-emerald-400" : "bg-ink-300"} />
          <span className="font-medium">Privacy engine: {data.engine.label}</span>
          {data.engine.model && <span className="text-white/60">· {data.engine.model}</span>}
        </div>
        <div className="mt-6 grid grid-cols-2 gap-3">
          <div className="rounded-2xl bg-white/[0.06] p-4 ring-1 ring-inset ring-white/10">
            <p className="text-4xl font-bold tabular-nums text-emerald-300">{data.protected_count}</p>
            <p className="mt-1 text-sm text-white/80">sensitive values protected on this device</p>
          </div>
          <div className={`rounded-2xl p-4 ring-1 ring-inset ${zero ? "bg-emerald-400/10 ring-emerald-300/30" : "bg-rose-500/15 ring-rose-300/40"}`}>
            <p className={`text-4xl font-bold tabular-nums ${zero ? "text-emerald-300" : "text-rose-300"}`}>{data.raw_pii_sent}</p>
            <p className="mt-1 text-sm text-white/80">raw personal values sent to cloud AI</p>
          </div>
        </div>
      </section>

      <section className="card mt-4 p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="flex items-center gap-2 text-lg font-bold">
            <IconLock className="h-5 w-5 text-emerald-600" /> Protected on this device
          </h2>
          {data.items.length > 0 && (
            <button className="btn-ghost min-h-[40px] px-3 text-sm" onClick={() => setRevealAll((r) => !r)}>
              {revealAll ? <IconEyeOff className="h-4 w-4" /> : <IconEye className="h-4 w-4" />}
              {revealAll ? "Hide values" : "Show values"}
            </button>
          )}
        </div>
        <p className="mt-1 text-sm text-ink-500">Detected locally and replaced with placeholders. The mapping never leaves this device.</p>
        {data.items.length === 0 ? (
          <p className="mt-4 text-ink-600">No personal data was detected in this document.</p>
        ) : (
          <ul className="mt-4 divide-y divide-ink-100">
            {data.items.map((it) => {
              const show = revealAll || revealed[it.placeholder];
              return (
                <li key={it.placeholder} className="flex items-center gap-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-ink-500">{it.type_label}</p>
                    <button
                      className="mt-0.5 max-w-full truncate text-left font-medium text-ink-900"
                      onClick={() => setRevealed((r) => ({ ...r, [it.placeholder]: !r[it.placeholder] }))}
                      aria-label={show ? `Hide ${it.type_label}` : `Reveal ${it.type_label}`}
                    >
                      <span className={show ? "" : "blur-secret"}>{it.original}</span>
                    </button>
                  </div>
                  <IconArrowRight className="h-4 w-4 shrink-0 text-ink-300" />
                  <span className="chip-ph shrink-0 font-mono text-sm">{it.placeholder}</span>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="card mt-4 p-5 sm:p-6">
        <h2 className="flex items-center gap-2 text-lg font-bold">
          <IconCloud className="h-5 w-5 text-sky-600" /> Sent to AI
        </h2>
        <p className="mt-1 text-sm text-ink-500">This is the sanitized text cloud models received — placeholders instead of your details.</p>
        <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-ink-50 p-4 font-mono text-[0.8rem] leading-relaxed text-ink-800 ring-1 ring-inset ring-ink-200">
          <Highlighted text={data.sanitized_excerpt || "(nothing sent)"} />
        </pre>
      </section>

      <section className="card mt-4 p-5 sm:p-6">
        <h2 className="text-lg font-bold">Cloud requests audit</h2>
        <p className="mt-1 text-sm text-ink-500">Every outgoing payload is scanned for your original values before and after it is sent.</p>
        {data.cloud_requests.length === 0 ? (
          <p className="mt-3 text-ink-600">No cloud requests were made.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {data.cloud_requests.map((r, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2 rounded-xl bg-ink-50 px-3 py-2.5 text-sm">
                <Badge tone="cloud">{r.model}</Badge>
                <span className="font-medium text-ink-800">{r.task}</span>
                {r.replayed && <Badge tone="replay">replayed</Badge>}
                <span className="ml-auto tabular-nums text-ink-500">{r.chars.toLocaleString()} chars</span>
                <Badge tone={r.raw_pii_found === 0 ? "local" : "danger"}>
                  {r.raw_pii_found === 0 ? "0 raw PII" : `${r.raw_pii_found} raw PII`}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
