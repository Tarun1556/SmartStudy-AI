import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(input: string | Date | null | undefined): string {
  if (!input) return "—";
  const d = typeof input === "string" ? new Date(input) : input;
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatCoverage(score: number): string {
  const pct = Math.max(0, Math.min(100, Math.round(score * 100)));
  return `${pct}%`;
}

export function coverageBadge(score: number): string {
  if (score >= 0.7) return "bg-rose-500/10 text-rose-400 border-rose-500/30";
  if (score >= 0.4) return "bg-amber-500/10 text-amber-400 border-amber-500/30";
  return "bg-cyan-500/10 text-cyan-300 border-cyan-500/30";
}

export function coverageLabel(score: number): string {
  if (score >= 0.7) return "Frequently Covered";
  if (score >= 0.4) return "Revisited Across Lectures";
  return "Introduced";
}
