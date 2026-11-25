/**
 * Display helpers for a mining run's round counter, wall-clock time and
 * LLM token consumption. Shared by the dashboard sidebar and the home page.
 */
import { useEffect, useState } from 'react';
import type { ExecutionProgress, Task, TaskStatus, TokenUsage } from '@/types';

/**
 * Rounds to show as "x / total".
 *
 * The backend reports the 1-based round being worked on. A completed run has
 * finished every round, so it always reads total/total, including runs recorded
 * by an older backend that never advanced the counter.
 */
export function displayRound(progress: ExecutionProgress | undefined, status: TaskStatus): { current: number; total: number } {
  const total = Math.max(progress?.totalRounds ?? 0, 0);
  if (status === 'completed') return { current: total, total };
  const reported = progress?.currentRound ?? 0;
  const current = status === 'running' ? Math.max(reported, total > 0 ? 1 : 0) : reported;
  return { current: Math.min(current, total), total };
}

/** Progress percentage; a completed run is 100% whatever the last report said. */
export function displayProgress(progress: ExecutionProgress | undefined, status: TaskStatus): number {
  if (status === 'completed') return 100;
  return Math.max(0, Math.min(100, progress?.progress ?? 0));
}

/** "1h 02m 05s", "4m 09s", "12s". */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return '—';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  if (h > 0) return `${h}h ${pad(m)}m ${pad(s)}s`;
  if (m > 0) return `${m}m ${pad(s)}s`;
  return `${s}s`;
}

/** "1.23M", "45.6K", "812". */
export function formatTokens(count: number | null | undefined): string {
  if (count === null || count === undefined || !Number.isFinite(count)) return '—';
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(2)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return String(Math.round(count));
}

/**
 * A dollar amount that never renders a real charge as free.
 *
 * Sub-cent spend is normal for a short run, and `toFixed(4)` bottoms out at
 * "$0.0000" for anything under $0.00005 — which reads as costing nothing. Below
 * the last representable digit we say "<$0.0001" instead. Only a genuine zero
 * prints as "$0.00".
 */
export function formatUsd(cost: number | null | undefined): string {
  if (cost === null || cost === undefined || !Number.isFinite(cost)) return '—';
  if (cost === 0) return '$0.00';
  const magnitude = Math.abs(cost);
  if (magnitude >= 0.01) return `$${cost.toFixed(2)}`;
  if (magnitude >= 0.0001) return `$${cost.toFixed(4)}`;
  return cost < 0 ? '>-$0.0001' : '<$0.0001';
}

/**
 * Effective price per million tokens, derived from what the provider billed.
 *
 * This is a realized blended rate — total cost over total tokens — not a list
 * price, so it already reflects the run's own input/output mix and any caching
 * discount. Returns null when the provider reported no cost, or when no tokens
 * were counted, so the caller can show "—" rather than invent a rate.
 */
export function effectiveRatePerMillion(
  cost: number | null | undefined,
  totalTokens: number | null | undefined,
): number | null {
  if (cost === null || cost === undefined || !Number.isFinite(cost)) return null;
  if (!totalTokens || !Number.isFinite(totalTokens) || totalTokens <= 0) return null;
  return (cost / totalTokens) * 1_000_000;
}

/** The effective rate as text, e.g. "$8.64 / 1M". */
export function formatRatePerMillion(
  cost: number | null | undefined,
  totalTokens: number | null | undefined,
): string {
  const rate = effectiveRatePerMillion(cost, totalTokens);
  if (rate === null) return '—';
  // Same rule as formatUsd: a rate that rounds away to zero would imply the
  // tokens were free. A true zero rate is still shown as $0.00.
  return `${rate === 0 ? '$0.00' : formatUsd(rate)} / 1M`;
}

/** Short label for how a model was reached. */
export function transportLabel(transport: string | undefined): string {
  if (transport === 'cli') return 'CLI';
  if (transport === 'api') return 'API';
  return '其他';
}

/** Local "YYYY-MM-DD HH:MM" for an ISO timestamp. */
export function formatClock(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export interface RunTiming {
  startedAt: string | null;
  finishedAt: string | null;
  /** Total runtime once finished, otherwise elapsed so far. */
  seconds: number | null;
  isFinished: boolean;
}

/**
 * Wall-clock timing for a run. While running it re-renders once a second so
 * the elapsed time ticks. A finished run recorded before the backend stamped
 * `completedAt` falls back to `updatedAt`.
 */
export function useRunTiming(task: Pick<Task, 'status' | 'createdAt' | 'updatedAt' | 'completedAt' | 'durationSeconds'> | null): RunTiming {
  const isRunning = task?.status === 'running';
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!isRunning) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [isRunning]);

  if (!task) return { startedAt: null, finishedAt: null, seconds: null, isFinished: false };

  const startedMs = Date.parse(task.createdAt);
  if (isRunning) {
    return {
      startedAt: task.createdAt,
      finishedAt: null,
      seconds: Number.isNaN(startedMs) ? null : Math.max(0, (now - startedMs) / 1000),
      isFinished: false,
    };
  }

  const finishedAt = task.completedAt || task.updatedAt || null;
  let seconds = task.durationSeconds ?? null;
  if (seconds === null && finishedAt && !Number.isNaN(startedMs)) {
    const finishedMs = Date.parse(finishedAt);
    if (!Number.isNaN(finishedMs)) seconds = Math.max(0, (finishedMs - startedMs) / 1000);
  }
  return { startedAt: task.createdAt, finishedAt, seconds, isFinished: true };
}

/** True when the backend has recorded at least one LLM call for the run. */
export function hasUsage(usage: TokenUsage | undefined | null): usage is TokenUsage {
  return !!usage && (usage.calls > 0 || usage.totalTokens > 0);
}
