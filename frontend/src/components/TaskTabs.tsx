export type TaskTab = "results" | "privacy" | "review";

export function TaskTabs({ active, onChange, needsReview }: { active: TaskTab; onChange: (t: TaskTab) => void; needsReview: number }) {
  const tabs: { id: TaskTab; label: string }[] = [
    { id: "results", label: "Explanation" },
    { id: "privacy", label: "Privacy" },
    { id: "review", label: "Review & confirm" },
  ];
  return (
    <nav className="mt-4 flex gap-1 rounded-2xl bg-ink-100 p-1" role="tablist" aria-label="Task sections">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          onClick={() => onChange(t.id)}
          className={`relative min-h-[44px] flex-1 rounded-xl px-2 text-sm font-semibold transition-colors sm:text-[0.95rem] ${
            active === t.id ? "bg-white text-ink-900 shadow-card" : "text-ink-600 hover:text-ink-900"
          }`}
        >
          {t.label}
          {t.id === "review" && needsReview > 0 && (
            <span className="ml-1.5 inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-amber-500 px-1 text-xs text-white">
              {needsReview}
            </span>
          )}
        </button>
      ))}
    </nav>
  );
}
