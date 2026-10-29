import { useEffect, useRef, useState } from "react";
import { api, errorMessage, urls } from "../api";
import type { AgentEvent, Step, Task } from "../types";
import { usd } from "../format";
import { Badge } from "../components/Badge";
import { IconAlert, IconArrowRight, IconCheck, IconCloud, IconLock } from "../components/Icons";
import { Spinner } from "../components/Spinner";

function StepIcon({ status }: { status: Step["status"] }) {
  const base = "relative z-10 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-4 ring-white";
  switch (status) {
    case "done":
      return (
        <span className={`${base} bg-emerald-600 text-white`} aria-label="Done">
          <IconCheck className="h-4 w-4" />
        </span>
      );
    case "running":
      return (
        <span className={`${base} bg-accent-50 text-accent-600`} aria-label="Running">
          <Spinner className="h-5 w-5" />
        </span>
      );
    case "waiting":
      return (
        <span className={`${base} bg-amber-100 text-amber-800 text-xs font-bold`} aria-label="Waiting for you">
          ❚❚
        </span>
      );
    case "error":
      return (
        <span className={`${base} bg-rose-600 text-white font-bold`} aria-label="Error">
          !
        </span>
      );
    default:
      return <span className={`${base} border-2 border-ink-300 bg-white`} aria-label="Pending" />;
  }
}

export function Timeline({
  taskId,
  onDone,
  onViewResults,
  onRetry,
  onBack,
  onSpend,
}: {
  taskId: string;
  onDone: (t: Task) => void;
  onViewResults: () => void;
  onRetry: () => void;
  onBack: () => void;
  onSpend: () => void;
}) {
  const [steps, setSteps] = useState<Step[]>([]);
  const [cost, setCost] = useState(0);
  const [finished, setFinished] = useState<Task | null>(null);
  const [error, setError] = useState<string | null>(null);
  const doneRef = useRef(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;
  const onSpendRef = useRef(onSpend);
  onSpendRef.current = onSpend;

  useEffect(() => {
    doneRef.current = false;
    setSteps([]);
    setCost(0);
    setFinished(null);
    setError(null);
    let poll: number | null = null;
    const es = new EventSource(urls.events(taskId));

    const finish = (t: Task) => {
      if (doneRef.current) return;
      doneRef.current = true;
      setSteps(t.steps);
      setCost(t.cost_usd);
      if (t.status === "error") {
        setError(t.error || "Something went wrong while processing your document.");
      } else {
        setFinished(t);
        onDoneRef.current(t);
      }
      onSpendRef.current();
    };

    const upsert = (s: Step) =>
      setSteps((prev) => {
        const i = prev.findIndex((p) => p.id === s.id);
        if (i === -1) return [...prev, s];
        const next = prev.slice();
        next[i] = s;
        return next;
      });

    es.onmessage = (msg) => {
      let ev: AgentEvent;
      try {
        ev = JSON.parse(msg.data) as AgentEvent;
      } catch {
        return;
      }
      if (ev.type === "step") {
        upsert(ev.step);
        if (typeof ev.task_cost_usd === "number") setCost(ev.task_cost_usd);
      } else if (ev.type === "done") {
        es.close();
        finish(ev.task);
      } else if (ev.type === "error") {
        es.close();
        doneRef.current = true;
        setError(ev.message || "Something went wrong while processing your document.");
        onSpendRef.current();
      }
    };

    // If the stream drops, fall back to polling the task until it settles.
    es.onerror = () => {
      if (doneRef.current) return;
      es.close();
      if (poll) return;
      poll = window.setInterval(async () => {
        try {
          const t = await api.task(taskId);
          setSteps(t.steps);
          setCost(t.cost_usd);
          if (t.status !== "running") {
            if (poll) window.clearInterval(poll);
            finish(t);
          }
        } catch (e) {
          if (poll) window.clearInterval(poll);
          if (!doneRef.current) setError(errorMessage(e));
        }
      }, 1500);
    };

    return () => {
      es.close();
      if (poll) window.clearInterval(poll);
    };
  }, [taskId]);

  const doneCount = steps.filter((s) => s.status === "done").length;
  const total = steps.length;
  const cloudCalls = steps.filter((s) => s.location === "cloud").length;

  return (
    <div className="animate-fade-in pt-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Agent at work</p>
          <h1 className="mt-1 text-2xl font-bold sm:text-3xl">
            {finished ? "Ready for your review" : error ? "We hit a problem" : "Working on your paperwork…"}
          </h1>
        </div>
        <div className="text-right">
          <p className="eyebrow">This task</p>
          <p className="text-xl font-bold tabular-nums">{usd(cost)}</p>
        </div>
      </div>

      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-ink-200" aria-hidden>
        <div
          className={`h-full rounded-full transition-all duration-500 ${error ? "bg-rose-500" : "bg-accent-600"}`}
          style={{ width: `${total ? Math.round((doneCount / total) * 100) : 6}%` }}
        />
      </div>
      <div className="mt-2 flex flex-wrap gap-2 text-sm text-ink-500">
        <span className="inline-flex items-center gap-1">
          <IconLock className="h-4 w-4 text-emerald-600" /> Local steps keep raw data on this device
        </span>
        <span className="inline-flex items-center gap-1">
          <IconCloud className="h-4 w-4 text-sky-600" /> {cloudCalls} cloud step{cloudCalls === 1 ? "" : "s"} see redacted text only
        </span>
      </div>

      <ol className="card relative mt-5 p-4 sm:p-6" aria-live="polite">
        {steps.length === 0 && !error && (
          <li className="flex items-center gap-3 text-ink-500">
            <Spinner className="h-5 w-5" /> Starting the agent…
          </li>
        )}
        {steps.map((s, i) => (
          <li key={s.id} className="relative flex gap-3 pb-5 last:pb-0 animate-fade-in">
            {i < steps.length - 1 && <span className="absolute left-[15px] top-8 h-[calc(100%-2rem)] w-0.5 bg-ink-200" aria-hidden />}
            <StepIcon status={s.status} />
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <p className={`font-semibold ${s.status === "pending" ? "text-ink-400" : "text-ink-900"}`}>{s.title}</p>
                {s.cost_usd > 0 && <span className="text-sm tabular-nums text-ink-500">{usd(s.cost_usd)}</span>}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                {s.model && <Badge>{s.model}</Badge>}
                {s.location === "local" ? (
                  <Badge tone="local">
                    <IconLock className="h-3 w-3" /> Local
                  </Badge>
                ) : (
                  <Badge tone="cloud">
                    <IconCloud className="h-3 w-3" /> Cloud
                  </Badge>
                )}
                {s.replayed && (
                  <Badge tone="replay" title="Response replayed from the demo cache">
                    replayed
                  </Badge>
                )}
              </div>
              {s.detail && <p className={`mt-1.5 text-sm ${s.status === "error" ? "text-rose-700" : "text-ink-600"}`}>{s.detail}</p>}
            </div>
          </li>
        ))}
      </ol>

      {error && (
        <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-900" role="alert">
          <div className="flex items-start gap-2">
            <IconAlert className="mt-0.5 h-5 w-5 text-rose-600" />
            <p>{error}</p>
          </div>
          <div className="mt-3 flex gap-2">
            <button className="btn-primary" onClick={onRetry}>
              Try again
            </button>
            <button className="btn-secondary" onClick={onBack}>
              Back
            </button>
          </div>
        </div>
      )}

      {finished && (
        <div className="sticky bottom-4 z-20 mt-5">
          <button className="btn-primary w-full py-3.5 text-[1.05rem] shadow-lift" onClick={onViewResults}>
            See what this means <IconArrowRight className="h-5 w-5" />
          </button>
        </div>
      )}
    </div>
  );
}
