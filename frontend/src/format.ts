export function usd(n: number | null | undefined, digits = 4): string {
  const v = typeof n === "number" && isFinite(n) ? n : 0;
  return `$${v.toFixed(digits)}`;
}

export function usdShort(n: number | null | undefined): string {
  const v = typeof n === "number" && isFinite(n) ? n : 0;
  if (v >= 1) return `$${v.toFixed(2)}`;
  return `$${v.toFixed(4)}`;
}

export function pct(n: number | null | undefined): string {
  const v = typeof n === "number" && isFinite(n) ? n : 0;
  return `${Math.round(v * 100)}%`;
}

const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

export function parseISODate(s: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s ?? "");
  if (!m) return null;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

export function dateTile(s: string): { month: string; day: string; year: string } {
  const d = parseISODate(s);
  if (!d) return { month: "—", day: "?", year: "" };
  return { month: MONTHS[d.getMonth()], day: String(d.getDate()).padStart(2, "0"), year: String(d.getFullYear()) };
}

export function longDate(s: string, locale?: string): string {
  const d = parseISODate(s);
  if (!d) return s;
  try {
    return d.toLocaleDateString(locale || undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
  } catch {
    return d.toDateString();
  }
}

export function daysRemaining(s: string, given?: number): number | null {
  if (typeof given === "number") return given;
  const d = parseISODate(s);
  if (!d) return null;
  const today = new Date();
  const t0 = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  return Math.round((d.getTime() - t0) / 86400000);
}

export function remainingLabel(n: number | null): string {
  if (n === null) return "";
  if (n < 0) return `${Math.abs(n)} day${Math.abs(n) === 1 ? "" : "s"} overdue`;
  if (n === 0) return "Due today";
  if (n === 1) return "1 day remaining";
  return `${n} days remaining`;
}

export function humanize(s: string): string {
  return (s ?? "").replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function isRtl(code: string | undefined): boolean {
  return !!code && /^(ar|he|fa|ur)(-|$)/i.test(code);
}
