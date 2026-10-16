/**
 * QuantaAlpha API Service
 *
 * Centralized API client for communicating with the FastAPI backend.
 * Uses fetch (no extra dependency) with the Vite proxy (/api -> localhost:8000).
 */

import type {
  ApiResponse,
  Factor,
  Task,
  WsMessage,
} from '@/types';

// ========================== HTTP Helpers ==========================

const BASE = ''; // Vite proxy handles /api -> backend

async function request<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers as any },
    });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    throw new Error('暂时无法连接研究服务，请检查服务是否已启动后重试。');
  }
  if ([502, 503, 504].includes(res.status)) {
    throw new Error('研究服务暂时不可用，请稍后重试。');
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API Error ${res.status}: ${text}`);
  }
  return res.json();
}

// ========================== Mining API ==========================

export interface MiningStartParams {
  direction: string;
  numDirections?: number;
  maxRounds?: number;
  maxLoops?: number;
  factorsPerHypothesis?: number;
  librarySuffix?: string;
  qualityGateEnabled?: boolean;
  miningLightgbmEnabled?: boolean;
  parallelEnabled?: boolean;
  evaluationFrequencies?: Array<'day' | 'week' | 'month'>;
  dataSource?: 'qlib' | 'wrds' | 'cn_duckdb' | 'binance_futures';
  marketMode?: 'us' | 'cn' | 'crypto';
  market?: 'sp500' | 'csi300' | 'csi500' | 'sme_composite' | 'binance_usdm';
  excludeSt?: boolean;
  excludeNewStocks?: boolean;
  excludeChiNext?: boolean;
  excludeStar?: boolean;
  excludeBse?: boolean;
  newStockMinTradingDays?: number;
  trainStartDate?: string;
  trainEndDate?: string;
  validStartDate?: string;
  validEndDate?: string;
  testStartDate?: string;
  testEndDate?: string;
}

export async function startMining(params: MiningStartParams) {
  return request<{ taskId: string; task: Task }>('/api/v1/mining/start', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function getWrdsStatus() {
  return request<any>('/api/v1/wrds/status');
}

export async function startWrdsBuild(startDate: string, endDate: string) {
  return request<{ taskId: string; task: Task }>('/api/v1/wrds/build', {
    method: 'POST',
    body: JSON.stringify({ startDate, endDate }),
  });
}

export async function getWrdsBuild(taskId: string) {
  return request<{ task: Task }>(`/api/v1/wrds/build/${taskId}`);
}

export async function getChinaStatus() {
  return request<any>('/api/v1/china/status');
}

export async function startChinaBuild(startDate: string, endDate: string) {
  return request<{ taskId: string; task: Task }>('/api/v1/china/build', {
    method: 'POST', body: JSON.stringify({ startDate, endDate }),
  });
}

export async function getChinaBuild(taskId: string) {
  return request<{ task: Task }>(`/api/v1/china/build/${taskId}`);
}

export async function getCryptoStatus() {
  return request<any>('/api/v1/crypto/status');
}

export async function startCryptoBuild(startDate: string, endDate: string, maxSymbols: number) {
  return request<{ taskId: string; task: Task }>('/api/v1/crypto/build', {
    method: 'POST',
    body: JSON.stringify({ startDate, endDate, maxSymbols }),
  });
}

export async function getCryptoBuild(taskId: string) {
  return request<{ task: Task }>(`/api/v1/crypto/build/${taskId}`);
}

export async function getMiningStatus(taskId: string) {
  return request<{ task: Task }>(`/api/v1/mining/${taskId}`);
}

export async function cancelMining(taskId: string) {
  return request(`/api/v1/mining/${taskId}`, { method: 'DELETE' });
}

export async function listTasks() {
  return request<{ tasks: Task[] }>('/api/v1/mining/tasks/list');
}

// ========================== Factor API ==========================

export interface FactorListParams {
  quality?: string;
  search?: string;
  limit?: number;
  offset?: number;
  library?: string;
  marketMode?: 'us' | 'cn' | 'crypto';
  market?: 'sp500' | 'csi300' | 'csi500' | 'sme_composite' | 'binance_usdm';
}

export interface FactorLibraryScope {
  filename: string;
  marketMode: 'us' | 'cn' | 'crypto';
  market: 'sp500' | 'csi300' | 'csi500' | 'sme_composite' | 'binance_usdm';
  label: string;
}

export interface FactorListResponse {
  factors: Factor[];
  total: number;
  limit: number;
  offset: number;
  metadata?: any;
  libraries?: string[];
  libraryScopes?: FactorLibraryScope[];
  activeScope?: { marketMode: 'us' | 'cn' | 'crypto'; market: string };
}

export async function getFactors(params: FactorListParams = {}) {
  const qs = new URLSearchParams();
  if (params.quality) qs.set('quality', params.quality);
  if (params.search) qs.set('search', params.search);
  if (params.limit) qs.set('limit', String(params.limit));
  if (params.offset) qs.set('offset', String(params.offset));
  if (params.library) qs.set('library', params.library);
  if (params.marketMode) qs.set('marketMode', params.marketMode);
  if (params.market) qs.set('market', params.market);
  return request<FactorListResponse>(`/api/v1/factors?${qs.toString()}`);
}

export async function getFactorDetail(factorId: string, library?: string) {
  const qs = library ? `?library=${encodeURIComponent(library)}` : '';
  return request<{ factor: any }>(`/api/v1/factors/${factorId}${qs}`);
}

export type EvaluationSplit = 'train' | 'valid' | 'test';

export async function getFactorSplitEvaluation(
  factorId: string,
  split: EvaluationSplit,
  library?: string,
  force = false,
) {
  const qs = new URLSearchParams({ split });
  if (library) qs.set('library', library);
  if (force) qs.set('force', 'true');
  return request<{ evaluation: any; cacheHit: boolean }>(
    `/api/v1/factors/${factorId}/split-evaluation?${qs.toString()}`,
  );
}

export async function deleteFactors(
  factorIds: string[],
  library?: string,
  scope?: { marketMode: 'us' | 'cn' | 'crypto'; market: 'sp500' | 'csi300' | 'csi500' | 'sme_composite' | 'binance_usdm' },
) {
  return request<{ deleted: string[]; deletedCount: number; remaining: number; library: string }>(
    '/api/v1/factors/delete',
    { method: 'POST', body: JSON.stringify({ factorIds, library: library || null, ...scope }) },
  );
}

export async function listFactorLibraries() {
  return request<{ libraries: string[] }>('/api/v1/factors/libraries');
}

export interface FactorCorrelationResponse {
  method: 'spearman' | 'pearson';
  frequency: string;
  aggregation: string;
  startDate: string;
  endDate: string;
  minCrossSection: number;
  evaluatedMonths: number;
  factors: Array<{ factorId: string; factorName: string }>;
  matrix: Array<Array<number | null>>;
  pairMonths: number[][];
  unavailable: Array<{ factorId: string; factorName: string; reason: string }>;
  cacheHit?: boolean;
}

export async function getFactorCorrelation(params: {
  factorIds: string[];
  library?: string;
  method: 'spearman' | 'pearson';
  startDate?: string;
  endDate?: string;
}) {
  return request<FactorCorrelationResponse>('/api/v1/factors/correlation', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// ========================== Factor Cache API ==========================

export interface CacheStatusResponse {
  total: number;
  h5_cached: number;
  md5_cached: number;
  need_compute: number;
  factors: Array<{
    factor_id: string;
    factor_name: string;
    status: 'h5_cached' | 'md5_cached' | 'need_compute';
  }>;
}

export interface WarmCacheResponse {
  total: number;
  synced: number;
  skipped: number;
  failed: number;
}

export async function getCacheStatus(library?: string) {
  const qs = new URLSearchParams();
  if (library) qs.set('library', library);
  return request<CacheStatusResponse>(`/api/v1/factors/cache-status?${qs.toString()}`);
}

export async function warmCache(library?: string) {
  const qs = new URLSearchParams();
  if (library) qs.set('library', library);
  return request<WarmCacheResponse>(`/api/v1/factors/warm-cache?${qs.toString()}`, {
    method: 'POST',
  });
}

// ========================== Backtest API ==========================

export interface BacktestStartParams {
  factorJson: string;
  factorSource?: 'custom' | 'combined' | 'kelly_jkp';
  configPath?: string;
  portfolioMode?: 'long' | 'short' | 'long_short';
  qualityFilter?: 'all' | 'high' | 'medium' | 'low';
  kellyMissingThreshold?: number;
  model?: 'lightgbm' | 'pls5' | 'lasso';
  kellyModel?: 'lightgbm' | 'pls5' | 'lasso';
  kellyRetrainMonths?: number;
  kellyMinTrainYears?: number;
  retrainMonths?: number;
  minTrainYears?: number;
  portfolioOptimization?: boolean;
  correlationPruning?: boolean;
  correlationThreshold?: number;
}

export interface KellyBacktestStatus {
  ready: boolean;
  panelPath: string;
  reportPath: string;
  factorCount: number;
  memberMonths?: number;
  modelRows?: number;
  startMonth?: string;
  endMonth?: string;
  thresholdCounts: Record<string, number>;
  factors?: Array<{
    factor: string;
    missing_rate_sp500: number;
    missing_rate_model_sample: number;
    nonmissing_sp500: number;
    nonmissing_model_sample: number;
    first_valid_month: string | null;
    last_valid_month: string | null;
  }>;
}

export interface BacktestConfigResponse {
  region: string;
  market: string;
  startTime: string;
  endTime: string;
  benchmark: string;
  trainStartDate?: string;
  trainEndDate?: string;
  validStartDate?: string;
  validEndDate?: string;
  testStartDate?: string;
  testEndDate?: string;
  supportedModels?: Array<'lightgbm' | 'pls5' | 'lasso'>;
  kelly?: KellyBacktestStatus;
}

export async function getBacktestConfig() {
  return request<BacktestConfigResponse>('/api/v1/backtest/config');
}

export async function startBacktest(params: BacktestStartParams) {
  return request<{ taskId: string; task: Task }>('/api/v1/backtest/start', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function getBacktestStatus(taskId: string) {
  return request<{ task: Task }>(`/api/v1/backtest/${taskId}`);
}

export async function getLatestBacktest() {
  return request<{ task: Task }>('/api/v1/backtest/latest');
}

export async function cancelBacktest(taskId: string) {
  return request(`/api/v1/backtest/${taskId}`, { method: 'DELETE' });
}

// ========================== System Config API ==========================

export async function getSystemConfig() {
  return request<{ env: Record<string, string>; experimentYaml: string; factorLibraries: string[] }>(
    '/api/v1/system/config'
  );
}

export async function updateSystemConfig(update: Record<string, string>) {
  return request('/api/v1/system/config', {
    method: 'PUT',
    body: JSON.stringify(update),
  });
}

// ========================== Health Check ==========================

export async function healthCheck() {
  return request<{ status: string; timestamp: string }>('/api/health');
}

// ========================== WebSocket ==========================

export type WsCallback = (msg: WsMessage) => void;

export function connectMiningWs(
  taskId: string,
  onMessage: WsCallback,
  onClose?: () => void,
  onError?: (e: Event) => void
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/mining/${taskId}`;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log(`[WS] Connected to ${taskId}`);
  };

  ws.onmessage = (event) => {
    try {
      const msg: WsMessage = JSON.parse(event.data);
      onMessage(msg);
    } catch (e) {
      console.warn('[WS] Failed to parse message:', event.data);
    }
  };

  ws.onclose = () => {
    console.log(`[WS] Disconnected from ${taskId}`);
    onClose?.();
  };

  ws.onerror = (e) => {
    console.error('[WS] Error:', e);
    onError?.(e);
  };

  // Heartbeat every 30s
  const heartbeat = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send('ping');
    } else {
      clearInterval(heartbeat);
    }
  }, 30000);

  return ws;
}
