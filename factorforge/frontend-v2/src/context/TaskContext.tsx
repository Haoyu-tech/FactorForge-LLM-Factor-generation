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

// ========================== Provider ==========================

export const TaskProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const BACKTEST_TASK_STORAGE_KEY = 'quantaalpha_last_backtest_task_id';
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
          case 'log':
            // Increased frontend log retention limit from 99 to 2000
            updated.logs = [...(updated.logs || []).slice(-2000), msg.data as LogEntry];
            
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
        setMiningTask(taskData);
        setMiningEquityCurve([]);
        setMiningDrawdownCurve([]);
        setMiningIcTimeSeries([]);

        // WebSocket
        const ws = connectMiningWs(
          resp.data.taskId,
          handleMiningWsMessage,
          () => {
            getMiningStatus(resp.data!.taskId).then((r) => {
              if (r.data?.task) setMiningTask(r.data.task as Task);
            });
          },
        );
        miningWsRef.current = ws;

        // Polling fallback
        miningPollingRef.current = setInterval(async () => {
          try {
            const r = await getMiningStatus(resp.data!.taskId);
            if (r.data?.task) {
              const t = r.data.task as Task;
              if (t.status === 'completed' || t.status === 'failed') {
                setMiningTask(t);
                clearInterval(miningPollingRef.current!);
                miningPollingRef.current = null;
              }
            }
          } catch {
            // ignore
          }
        }, 10000);
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
    [handleMiningWsMessage],
  );

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
