import { IconAlert } from "./Icons";

export function ErrorBanner({ message, onRetry, onDismiss }: { message: string; onRetry?: () => void; onDismiss?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-rose-900 animate-fade-in">
      <IconAlert className="mt-0.5 h-5 w-5 text-rose-600" />
      <div className="flex-1 text-[0.95rem]">{message}</div>
      <div className="flex shrink-0 gap-1">
        {onRetry && (
          <button className="rounded-lg px-2.5 py-1.5 text-sm font-semibold text-rose-800 hover:bg-rose-100" onClick={onRetry}>
            Retry
          </button>
        )}
        {onDismiss && (
          <button className="rounded-lg px-2.5 py-1.5 text-sm text-rose-700 hover:bg-rose-100" onClick={onDismiss} aria-label="Dismiss">
            ✕
          </button>
        )}
      </div>
    </div>
  );
}
