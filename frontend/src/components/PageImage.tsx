import { useState } from "react";
import type { Field } from "../types";

export function PageImage({
  src,
  alt,
  fields,
  page,
  activeField,
  onFieldClick,
}: {
  src: string;
  alt: string;
  fields?: Field[];
  page?: number;
  activeField?: string | null;
  onFieldClick?: (name: string) => void;
}) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const boxes = (fields ?? []).filter((f) => f.rect && f.page === page);
  return (
    <div className="relative overflow-hidden rounded-xl border border-ink-200 bg-white">
      {!loaded && !failed && <div className="aspect-[1/1.294] w-full animate-pulse bg-ink-100" aria-hidden />}
      {failed && (
        <div className="flex aspect-[1/1.294] w-full items-center justify-center p-6 text-center text-sm text-ink-500">
          Preview unavailable for this page.
        </div>
      )}
      <img
        src={src}
        alt={alt}
        className={`block w-full ${loaded ? "" : "absolute inset-0 opacity-0"}`}
        onLoad={() => {
          setLoaded(true);
          setFailed(false);
        }}
        onError={() => setFailed(true)}
      />
      {loaded &&
        boxes.map((f) => {
          const [x0, y0, x1, y1] = f.rect!;
          const active = activeField === f.name;
          return (
            <button
              key={f.name}
              type="button"
              aria-label={`${f.label}${f.needs_review ? " — needs review" : ""}`}
              onClick={() => onFieldClick?.(f.name)}
              className={`absolute rounded-[3px] transition-colors ${
                f.needs_review
                  ? "bg-amber-300/30 ring-2 ring-amber-500"
                  : "bg-emerald-300/10 ring-1 ring-emerald-500/60 hover:bg-emerald-300/25"
              } ${active ? "ring-[3px] ring-accent-600" : ""}`}
              style={{
                left: `${x0 * 100}%`,
                top: `${y0 * 100}%`,
                width: `${Math.max(0.5, (x1 - x0) * 100)}%`,
                height: `${Math.max(0.5, (y1 - y0) * 100)}%`,
              }}
            />
          );
        })}
    </div>
  );
}
