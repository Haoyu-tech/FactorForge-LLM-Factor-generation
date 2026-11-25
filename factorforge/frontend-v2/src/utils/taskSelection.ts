/**
 * Which mining run a browser should display, and when a run is over.
 *
 * Kept as pure functions so the selection rule can be exercised directly
 * against a recorded backend task list.
 */

import type { Task, TaskStatus } from '@/types';

/**
 * A run the backend will not advance any further.
 *
 * `cancelled` belongs here: it was missing from `TaskStatus`, so a stopped run
 * kept its poll running and a late `progress` frame could flip it back to
 * `running`.
 */
export function isTerminalStatus(status: TaskStatus | string | undefined): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled';
}

/** Mining tasks only; the backend's list also carries backtest tasks. */
function isMiningTask(task: any): boolean {
  return task?.type !== 'backtest' && task?.config && 'direction' in task.config;
}

/** When a run was last active, for ordering. */
function lastActivity(task: Task): string {
  return task.updatedAt || task.createdAt || '';
}

/**
 * Pick the run that every browser on this URL should be showing.
 *
 * The backend is the single source of truth: an active run wins, otherwise the
 * most recently active one. Selecting from the server's list rather than from a
 * per-browser localStorage pin is what stops two browsers pointed at the same
 * URL from sitting on two different runs.
 *
 * Recency is `updatedAt`, not `createdAt`: a long run that finishes late is the
 * one whose results matter, even when a short run was started after it and
 * abandoned.
 */
export function pickCurrentMiningTask(tasks: Task[]): Task | undefined {
  const newestFirst = tasks
    .filter(isMiningTask)
    .sort((a, b) => (lastActivity(a) < lastActivity(b) ? 1 : lastActivity(a) > lastActivity(b) ? -1 : 0));
  return newestFirst.find((t) => t.status === 'running') || newestFirst[0];
}
