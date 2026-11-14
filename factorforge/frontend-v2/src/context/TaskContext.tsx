/**
 * TaskContext — Global Task State Management
 *
 * Lifts mining and backtest task state, WebSocket connection, and polling logic
 * to App level, so running state is not lost when switching pages.
 */

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import type {
  Task,
  TaskConfig,
  LogEntry,
  RealtimeMetrics,
  TimeSeriesData,
  WsMessage,
} from '@/types';
import { generateId } from '@/utils';
import {
  startMining as apiStartMining,
  getMiningStatus,
  cancelMining as apiCancelMining,
  listTasks,
  startBacktest as apiStartBacktest,
  getBacktestStatus,
  getLatestBacktest,
  cancelBacktest as apiCancelBacktest,
  connectMiningWs,
  healthCheck,
} from '@/services/api';
import type { BacktestStartParams } from '@/services/api';
import { getDefaultMiningDirection } from '@/utils/miningDirections';

// ========================== Backtest local type ==========================

export interface BacktestTask {
  taskId: string;
  status: string;
  progress: {
    phase: string;
    progress: number;
    message: string;
    timestamp: string;
  };
  logs: LogEntry[];
  metrics: Record<string, any>;
  config: Record<string, any>;
  createdAt: string;
  updatedAt: string;
}

// ========================== Context Value ==========================

interface TaskContextValue {
  // Backend health
  backendAvailable: boolean | null;

  // ---- Mining ----
  miningTask: Task | null;
  miningEquityCurve: TimeSeriesData[];
  miningDrawdownCurve: TimeSeriesData[];
  miningIcTimeSeries: TimeSeriesData[];
  startMining: (config: TaskConfig) => void;
  stopMining: () => void;
  resetMiningTask: () => void;

  // ---- Backtest ----
  backtestTask: BacktestTask | null;
  backtestLogs: LogEntry[];
  startBacktestTask: (params: BacktestStartParams) => Promise<void>;
  stopBacktestTask: () => void;
}

const TaskContext = createContext<TaskContextValue | null>(null);

/** Frontend log retention, matching the cap used by the WebSocket handler. */
const MAX_LOGS = 2000;

/**
 * Union two log lists by entry id.
 *
 * The backend keeps a rolling 500-entry window while the browser keeps more, so
 * a REST refresh must not truncate history. Entries are re-sorted by timestamp
 * because a refresh can fill a gap left by a dropped WebSocket.
 */
function mergeLogs(existing: LogEntry[] = [], incoming: LogEntry[] = []): LogEntry[] {
  if (incoming.length === 0) return existing;
  const seen = new Set(existing.map((entry) => entry.id));
  const added = incoming.filter((entry) => !seen.has(entry.id));
  if (added.length === 0) return existing;
  return [...existing, ...added]
    .sort((a, b) => (a.timestamp < b.timestamp ? -1 : a.timestamp > b.timestamp ? 1 : 0))
    .slice(-MAX_LOGS);
}

/**
 * Fold a REST task snapshot into the task already held in state.
 *
 * The backend is authoritative for status, progress and metrics, but
 * `top10Factors` is also scraped from log lines on the client, so a snapshot
 * that has not caught up yet must not blank the list the user is looking at.
 */
function mergeTaskSnapshot(prev: Task | null, snapshot: Task): Task {
  if (!prev) return snapshot;
  const metrics = snapshot.metrics
    ? {
        ...snapshot.metrics,
        top10Factors: snapshot.metrics.top10Factors?.length
          ? snapshot.metrics.top10Factors
          : prev.metrics?.top10Factors ?? [],
      }
    : prev.metrics;
  return {
    ...snapshot,
    metrics,
    logs: mergeLogs(prev.logs, snapshot.logs),
  };
}

// ========================== Provider ==========================

export const TaskProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const BACKTEST_TASK_STORAGE_KEY = 'quantaalpha_last_backtest_task_id';
  const MINING_TASK_STORAGE_KEY = 'quantaalpha_last_mining_task_id';
  // ---- Backend health ----
  const [backendAvailable, setBackendAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    let disposed = false;
    const refresh = () => {
      healthCheck()
        .then(() => { if (!disposed) setBackendAvailable(true); })
        .catch(() => { if (!disposed) setBackendAvailable(false); });
    };
    refresh();
    const intervalId = window.setInterval(refresh, 5000);
    return () => {
      disposed = true;
      window.clearInterval(intervalId);
    };
  }, []);

  // ==================================================================
  // MINING
  // ==================================================================
  const [miningTask, setMiningTask] = useState<Task | null>(null);
  const [miningEquityCurve, setMiningEquityCurve] = useState<TimeSeriesData[]>([]);
  const [miningDrawdownCurve, setMiningDrawdownCurve] = useState<TimeSeriesData[]>([]);
  const [miningIcTimeSeries, setMiningIcTimeSeries] = useState<TimeSeriesData[]>([]);

  const miningWsRef = useRef<WebSocket | null>(null);
  const miningPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // WS handler for mining
  const handleMiningWsMessage = useCallback(
    (msg: WsMessage) => {
      setMiningTask((prev) => {
        if (!prev) return prev;
        const updated = { ...prev };
        switch (msg.type) {
          case 'progress':
            updated.progress = msg.data;
            updated.status = msg.data.phase === 'completed' ? 'completed' : 'running';
            break;
          case 'log': {
            const incoming = msg.data as LogEntry;
            // The backend replays recent logs on every WebSocket connect; skip
            // entries we already hold so a reconnect does not duplicate them.
            if (incoming.id && (updated.logs || []).some((l) => l.id === incoming.id)) {
              return prev;
            }
            // Increased frontend log retention limit from 99 to 2000
            updated.logs = [...(updated.logs || []).slice(-2000), incoming];
            
            // Try to extract factor from log message to show it immediately in the list
            // Pattern: "Added new factor: {name} with expression: {expr}"
            const logMsg = (msg.data as LogEntry).message;
            if (logMsg && logMsg.includes("Added new factor:")) {
              const match = logMsg.match(/Added new factor: (.+?) with expression: (.+)/);
              if (match) {
                const [_, name, expr] = match;
                const currentMetrics = updated.metrics || {
                    ic: 0, icir: 0, rankIc: 0, rankIcir: 0,
                    annualReturn: 0, sharpeRatio: 0, maxDrawdown: 0,
                    totalFactors: 0, highQualityFactors: 0, mediumQualityFactors: 0, lowQualityFactors: 0,
                    top10Factors: []
                };
                
                const currentFactors = currentMetrics.top10Factors || [];
                // Avoid duplicates
                if (!currentFactors.some((f: any) => f.factorName === name)) {
                    const newFactor = {
                        factorName: name,
                        factorExpression: expr,
                        rankIc: 0, rankIcir: 0, ic: 0, icir: 0,
                        annualReturn: 0, sharpeRatio: 0, maxDrawdown: 0, calmarRatio: 0,
                        cumulativeCurve: []
                    };
                    
                    // Recalculate best metrics from the updated list
                    const updatedFactors = [newFactor, ...currentFactors];
                    const bestFactor = updatedFactors.reduce((best, current) => {
                        // Prioritize RankIC, but handle potential missing values
                        const bestScore = best.rankIc || 0;
                        const currentScore = current.rankIc || 0;
                        return currentScore > bestScore ? current : best;
                    }, updatedFactors[0]);

                    updated.metrics = {
                        ...currentMetrics,
                        totalFactors: (currentMetrics.totalFactors || 0) + 1,
                        // Prepend new factor to the list so user sees it immediately
                        top10Factors: updatedFactors,
                        // Update best factor metrics
                        factorName: bestFactor.factorName,
                        rankIc: bestFactor.rankIc ?? 0,
                        rankIcir: bestFactor.rankIcir ?? 0,
                        ic: bestFactor.ic ?? 0,
                        icir: bestFactor.icir ?? 0,
                        annualReturn: bestFactor.annualReturn ?? 0,
                        sharpeRatio: bestFactor.sharpeRatio ?? 0,
                        maxDrawdown: bestFactor.maxDrawdown ?? 0,
                    };
                }
              }
            }
            break;
          }
          case 'metrics':
            updated.metrics = {
              ...(updated.metrics || {} as RealtimeMetrics),
              ...msg.data as RealtimeMetrics
            };
            break;
          case 'result':
            updated.status = msg.data.status === 'completed' ? 'completed' : 'failed';
            if (msg.data.metrics) updated.metrics = msg.data.metrics;
            break;
          case 'error':
            updated.status = 'failed';
            updated.logs = [
              ...(updated.logs || []),
              {
                id: generateId(),
                timestamp: new Date().toISOString(),
                level: 'error',
                message: msg.data.error || 'Unknown error',
              },
            ];
            break;
        }
        updated.updatedAt = new Date().toISOString();
        return updated;
      });
    },
    [],
  );

  // Attach live updates (WebSocket + polling fallback) for a mining task.
  // Shared by a fresh start and by the refresh-restore path below.
  const attachMiningStream = useCallback(
    (taskId: string) => {
      if (miningWsRef.current) {
        try { miningWsRef.current.close(); } catch {}
        miningWsRef.current = null;
      }
      if (miningPollingRef.current) {
        clearInterval(miningPollingRef.current);
        miningPollingRef.current = null;
      }

      const ws = connectMiningWs(
        taskId,
        handleMiningWsMessage,
        () => {
          getMiningStatus(taskId).then((r) => {
            const t = r.data?.task as Task | undefined;
            if (t) setMiningTask((prev) => mergeTaskSnapshot(prev, t));
          }).catch(() => {});
        },
      );
      miningWsRef.current = ws;

      miningPollingRef.current = setInterval(async () => {
        try {
          const r = await getMiningStatus(taskId);
          const t = r.data?.task as Task | undefined;
          if (!t) return;
          // Apply every poll, not just the terminal one. The WebSocket can drop
          // (sleep, proxy timeout, backend restart) with no reconnect, and when
          // that happens this poll is the only thing still advancing the log.
          setMiningTask((prev) => mergeTaskSnapshot(prev, t));
          if (t.status === 'completed' || t.status === 'failed') {
            clearInterval(miningPollingRef.current!);
            miningPollingRef.current = null;
          }
        } catch {
          // Transient backend hiccup; keep polling.
        }
      }, 10000);
    },
    [handleMiningWsMessage],
  );

  // Start mining (real backend)
  const startRealMining = useCallback(
    async (config: TaskConfig) => {
      try {
        // Load defaults from localStorage
        let defaults: any = {};
        const savedConfig = localStorage.getItem('quantaalpha_config');
        if (savedConfig) {
          try {
            defaults = JSON.parse(savedConfig);
          } catch {}
        }

        const direction =
          config.useCustomMiningDirection
            ? (getDefaultMiningDirection() || '价量因子挖掘')
            : (config.userInput && config.userInput.trim()) || getDefaultMiningDirection() || '价量因子挖掘';
        const marketMode: 'us' | 'cn' | 'crypto' = defaults.marketMode === 'crypto' ? 'crypto' : (defaults.marketMode === 'cn' ? 'cn' : 'us');
        const marketDates = defaults.marketDateRanges?.[marketMode] || defaults;
        const resp = await apiStartMining({
          direction,
          numDirections: config.numDirections || defaults.defaultNumDirections || 2,
          maxRounds: config.maxRounds || defaults.defaultMaxRounds || 3,
          librarySuffix: config.librarySuffix || defaults.defaultLibrarySuffix || undefined,
          qualityGateEnabled: config.qualityGateEnabled ?? defaults.qualityGateEnabled ?? true,
          miningLightgbmEnabled: defaults.miningLightgbmEnabled ?? false,
          parallelEnabled: config.parallelExecution ?? defaults.parallelExecution ?? false,
          evaluationFrequencies: defaults.evaluationFrequencies || ['day'],
          dataSource: marketMode === 'crypto' ? 'binance_futures' : (marketMode === 'cn' ? 'cn_duckdb' : (defaults.dataSource || 'wrds')),
          marketMode,
          market: defaults.defaultMarket || (marketMode === 'crypto' ? 'binance_usdm' : (marketMode === 'cn' ? 'csi300' : 'sp500')),
          excludeSt: defaults.cnExcludeSt ?? true,
          excludeNewStocks: defaults.cnExcludeNewStocks ?? true,
          excludeChiNext: defaults.cnExcludeChiNext ?? false,
          excludeStar: defaults.cnExcludeStar ?? false,
          excludeBse: defaults.cnExcludeBse ?? false,
          newStockMinTradingDays: defaults.cnNewStockMinTradingDays ?? 375,
          trainStartDate: marketDates.trainStartDate || (marketMode === 'crypto' ? '2020-01-01' : marketMode === 'cn' ? '2010-07-01' : '1987-01-01'),
          trainEndDate: marketDates.trainEndDate || (marketMode === 'crypto' ? '2022-12-31' : marketMode === 'cn' ? '2017-12-29' : '2010-12-31'),
          validStartDate: marketDates.validStartDate || (marketMode === 'crypto' ? '2023-01-01' : marketMode === 'cn' ? '2018-01-02' : '2011-01-01'),
          validEndDate: marketDates.validEndDate || (marketMode === 'crypto' ? '2023-12-31' : marketMode === 'cn' ? '2020-12-31' : '2014-12-31'),
          testStartDate: marketDates.testStartDate || (marketMode === 'crypto' ? '2024-01-01' : marketMode === 'cn' ? '2021-01-04' : '2015-01-01'),
          testEndDate: marketDates.testEndDate || '2025-12-31',
        });
        if (!resp.success || !resp.data) throw new Error(resp.error || 'Failed');

        const taskData = resp.data.task as Task;
        // Initialize metrics with empty top10Factors to avoid stale data
        if (taskData.metrics) {
            taskData.metrics.top10Factors = [];
            taskData.metrics.totalFactors = 0;
            taskData.metrics.highQualityFactors = 0;
            taskData.metrics.mediumQualityFactors = 0;
            taskData.metrics.lowQualityFactors = 0;
        }
        localStorage.setItem(MINING_TASK_STORAGE_KEY, resp.data.taskId);
        setMiningTask(taskData);
        setMiningEquityCurve([]);
        setMiningDrawdownCurve([]);
        setMiningIcTimeSeries([]);

        attachMiningStream(resp.data.taskId);
      } catch (err: any) {
        console.error('Failed to start mining task:', err);
        setBackendAvailable(false);
        const message = err?.message || '无法连接后端，挖掘任务未启动';
        const timestamp = new Date().toISOString();
        setMiningTask({
          taskId: generateId(),
          status: 'failed',
          config,
          progress: {
            phase: 'failed' as any,
            currentRound: 0,
            totalRounds: config.maxRounds || 0,
            progress: 0,
            message,
            timestamp,
          },
          metrics: {
            ic: 0, icir: 0, rankIc: 0, rankIcir: 0,
            annualReturn: 0, sharpeRatio: 0, maxDrawdown: 0,
            totalFactors: 0, highQualityFactors: 0,
            mediumQualityFactors: 0, lowQualityFactors: 0,
          },
          logs: [{
            id: generateId(),
            timestamp,
            level: 'error',
            message,
          }],
          createdAt: timestamp,
          updatedAt: timestamp,
        });
        setMiningEquityCurve([]);
        setMiningDrawdownCurve([]);
        setMiningIcTimeSeries([]);
      }
    },
    [attachMiningStream],
  );

  // Restore the mining task after a page refresh. Only the task ID lives in
  // the browser; status, progress and logs are re-read from the backend, and a
  // running task is re-attached to its WebSocket so live logs resume.
  useEffect(() => {
    let disposed = false;

    const restore = async () => {
      const savedId = localStorage.getItem(MINING_TASK_STORAGE_KEY);
      let restored: Task | undefined;

      if (savedId) {
        try {
          const r = await getMiningStatus(savedId);
          restored = r.data?.task as Task | undefined;
        } catch {
          // A backend restart invalidates an in-memory task ID.
          localStorage.removeItem(MINING_TASK_STORAGE_KEY);
        }
      }

      if (!restored) {
        try {
          const r = await listTasks();
          const miningTasks = (r.data?.tasks || []).filter(
            (t: any) => t?.type !== 'backtest' && t?.config && 'direction' in t.config,
          ) as Task[];
          restored = miningTasks.find((t) => t.status === 'running') || miningTasks[0];
        } catch {
          return;
        }
      }

      if (!restored || disposed) return;
      localStorage.setItem(MINING_TASK_STORAGE_KEY, restored.taskId);
      setMiningTask(restored);
      if (restored.status === 'running') {
        attachMiningStream(restored.taskId);
      }
    };

    void restore();
    return () => {
      disposed = true;
    };
    // Mount-only: attachMiningStream is stable (depends only on the WS handler).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Public start mining
  const startMining = useCallback(
    (config: TaskConfig) => {
      // Always ask the real backend. If it is unavailable, startRealMining
      // records an explicit failed task with zero metrics; it never fabricates
      // factors, curves, or completion logs.
      void startRealMining(config);
    },
    [startRealMining],
  );

  // Stop mining
  const stopMining = useCallback(async () => {
    if (!miningTask) return;
    miningWsRef.current?.close();
    miningWsRef.current = null;
    if (miningPollingRef.current) {
      clearInterval(miningPollingRef.current);
      miningPollingRef.current = null;
    }
    if (backendAvailable) {
      try {
        await apiCancelMining(miningTask.taskId);
      } catch {
        // ignore
      }
    }
    setMiningTask((prev) => (prev ? { ...prev, status: 'failed' } : prev));
  }, [miningTask, backendAvailable]);

  // Reset mining task
  const resetMiningTask = useCallback(() => {
    // Ensure stopped first
    miningWsRef.current?.close();
    miningWsRef.current = null;
    if (miningPollingRef.current) {
      clearInterval(miningPollingRef.current);
      miningPollingRef.current = null;
    }
    setMiningTask(null);
    setMiningEquityCurve([]);
    setMiningDrawdownCurve([]);
    setMiningIcTimeSeries([]);
  }, []);

  // ==================================================================
  // BACKTEST
  // ==================================================================
  const [backtestTask, setBacktestTask] = useState<BacktestTask | null>(null);
  const [backtestLogs, setBacktestLogs] = useState<LogEntry[]>([]);

  const backtestWsRef = useRef<WebSocket | null>(null);
  const backtestPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // WS handler for backtest
  // IMPORTANT: setBacktestLogs must NOT be inside setBacktestTask's updater function,
  // because React StrictMode double-invokes updater functions in development mode,
  // which would cause every log entry to be added twice.
  const handleBacktestWsMessage = useCallback((msg: WsMessage) => {
    switch (msg.type) {
      case 'progress':
        setBacktestTask((prev) => {
          if (!prev) return prev;
          return { ...prev, progress: msg.data, updatedAt: new Date().toISOString() };
        });
        break;
      case 'log':
        setBacktestLogs((l) => [...l.slice(-499), msg.data as LogEntry]);
        break;
      case 'metrics':
        setBacktestTask((prev) => {
          if (!prev) return prev;
          return { ...prev, metrics: msg.data, updatedAt: new Date().toISOString() };
        });
        break;
      case 'result':
        setBacktestTask((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            status: msg.data.status === 'completed' ? 'completed' : 'failed',
            metrics: msg.data.metrics || prev.metrics,
            updatedAt: new Date().toISOString(),
          };
        });
        break;
      case 'error':
        setBacktestTask((prev) => {
          if (!prev) return prev;
          return { ...prev, status: 'failed', updatedAt: new Date().toISOString() };
        });
        break;
    }
  }, []);

  // Restore the last backtest after a page refresh. Only the small task ID is
  // stored locally; metrics and curves always come from the backend so stale
  // browser data cannot be mistaken for a current result.
  useEffect(() => {
    let taskId = localStorage.getItem(BACKTEST_TASK_STORAGE_KEY);
    let disposed = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const restore = async () => {
      try {
        const response = taskId
          ? await getBacktestStatus(taskId)
          : await getLatestBacktest();
        const restored = response.data?.task as unknown as BacktestTask | undefined;
        if (!restored || disposed) return;
        taskId = restored.taskId;
        localStorage.setItem(BACKTEST_TASK_STORAGE_KEY, restored.taskId);
        setBacktestTask(restored);
        setBacktestLogs((restored.logs || []).slice(-500));
        if (restored.status === 'completed' || restored.status === 'failed' || restored.status === 'cancelled') {
          if (timer) window.clearInterval(timer);
          timer = null;
        }
      } catch {
        // A backend restart invalidates an in-memory task ID. Fall back to the
        // durable latest-result endpoint on the next poll.
        if (taskId) {
          localStorage.removeItem(BACKTEST_TASK_STORAGE_KEY);
          taskId = null;
          return;
        }
        if (timer) window.clearInterval(timer);
        timer = null;
      }
    };

    restore();
    timer = window.setInterval(restore, 5000);
    return () => {
      disposed = true;
      if (timer) window.clearInterval(timer);
    };
  }, []);

  // Start backtest
  const startBacktestTask = useCallback(
    async (params: BacktestStartParams) => {
      setBacktestLogs([]);
      const resp = await apiStartBacktest(params);
      if (!resp.success || !resp.data) throw new Error(resp.error || 'Failed');

      const taskData = resp.data.task as unknown as BacktestTask;
      localStorage.setItem(BACKTEST_TASK_STORAGE_KEY, resp.data.taskId);
      setBacktestTask(taskData);

      // WebSocket
      const ws = connectMiningWs(
        resp.data.taskId,
        handleBacktestWsMessage,
        () => {
          getBacktestStatus(resp.data!.taskId).then((r) => {
            if (r.data?.task) setBacktestTask(r.data.task as unknown as BacktestTask);
          });
        },
      );
      backtestWsRef.current = ws;

      // Polling fallback
      backtestPollingRef.current = setInterval(async () => {
        try {
          const r = await getBacktestStatus(resp.data!.taskId);
          if (r.data?.task) {
            const t = r.data.task as unknown as BacktestTask;

            // Always sync progress from polling (in case WS missed updates)
            setBacktestTask((prev) => {
              if (!prev) return t;
              return {
                ...prev,
                status: t.status,
                progress: t.progress || prev.progress,
                metrics: (t.metrics && Object.keys(t.metrics).length > 0) ? t.metrics : prev.metrics,
                updatedAt: t.updatedAt,
              };
            });

            if (t.status === 'completed' || t.status === 'failed' || t.status === 'cancelled') {
              // Final update: sync task + logs from backend (in case WS missed some)
              setBacktestTask(t);
              if (t.logs && t.logs.length > 0) {
                setBacktestLogs(t.logs.slice(-500));
              }
              clearInterval(backtestPollingRef.current!);
              backtestPollingRef.current = null;
            }
          }
        } catch {
          // ignore
        }
      }, 5000);
    },
    [handleBacktestWsMessage],
  );

  // Stop backtest
  const stopBacktestTask = useCallback(async () => {
    if (!backtestTask) return;
    backtestWsRef.current?.close();
    backtestWsRef.current = null;
    if (backtestPollingRef.current) {
      clearInterval(backtestPollingRef.current);
      backtestPollingRef.current = null;
    }
    try {
      await apiCancelBacktest(backtestTask.taskId);
    } catch {
      // ignore
    }
    setBacktestTask((prev) => (prev ? { ...prev, status: 'cancelled' } : prev));
  }, [backtestTask]);

  // ==================================================================
  // Context value
  // ==================================================================
  const value: TaskContextValue = {
    backendAvailable,
    // Mining
    miningTask,
    miningEquityCurve,
    miningDrawdownCurve,
    miningIcTimeSeries,
    startMining,
    stopMining,
    resetMiningTask,

    // ---- Backtest ----
    backtestTask,
    backtestLogs,
    startBacktestTask,
    stopBacktestTask,
  };

  return <TaskContext.Provider value={value}>{children}</TaskContext.Provider>;
};

// ========================== Hook ==========================

export function useTaskContext(): TaskContextValue {
  const ctx = useContext(TaskContext);
  if (!ctx) throw new Error('useTaskContext must be used inside <TaskProvider>');
  return ctx;
}
