import { useEffect, useRef } from "react";
import { IconCheck } from "./Icons";
import { Spinner } from "./Spinner";

export function ConfirmDialog({
  open,
  deadlineCount,
  hasLetter,
  busy,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  deadlineCount: number;
  hasLetter: boolean;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    confirmRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;
  const items = [
    "Completed form",
    ...(hasLetter ? ["Response letter"] : []),
    ...(deadlineCount > 0 ? [deadlineCount > 1 ? `${deadlineCount} deadline reminders` : "Deadline reminder"] : []),
  ];
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink-950/40 p-0 sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <div className="w-full max-w-md rounded-t-3xl bg-white p-6 shadow-lift animate-fade-in sm:rounded-3xl">
        <h2 id="confirm-title" className="text-xl font-bold">
          Review before you continue
        </h2>
        <p className="mt-2 text-ink-600">PaperPilot has prepared:</p>
        <ul className="mt-3 space-y-2">
          {items.map((t) => (
            <li key={t} className="flex items-center gap-2.5 text-[1rem] font-medium">
              <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                <IconCheck className="h-4 w-4" />
              </span>
              {t}
            </li>
          ))}
        </ul>
        <p className="mt-4 rounded-xl bg-ink-50 p-3 text-sm text-ink-700">
          Nothing is sent or submitted anywhere — this only generates your final files. Nothing will be finalized without your
          confirmation.
        </p>
        <div className="mt-5 grid grid-cols-2 gap-3">
          <button className="btn-secondary" onClick={onCancel} disabled={busy}>
            Go back
          </button>
          <button ref={confirmRef} className="btn-primary" onClick={onConfirm} disabled={busy}>
            {busy ? <Spinner className="h-4 w-4" /> : <IconCheck className="h-4 w-4" />}
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}
