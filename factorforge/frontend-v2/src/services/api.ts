/**
 * QuantaAlpha API Service
 *
 * Centralized API client for communicating with the FastAPI backend.
 * Uses fetch (no extra dependency) with the Vite proxy (/api -> localhost:8000).
 */

import type {
  ApiResponse,
  Factor,
  LlmChannel,
  RealtimeMetrics,
  Task,
  TokenUsage,
  WsMessage,
} from '@/types';

// ========================== HTTP Helpers ==========================

const BASE = ''; // Vite proxy handles /api -> backend

/**
 * An error the backend answered with, as opposed to a connection failure.
 *
 * Callers need the difference: a 409 "a run is already active" means the
 * service is healthy and declining, and must not be reported as offline.
 */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** Pull FastAPI's `detail` out of an error body, falling back to raw text. */
function errorDetail(status: number, body: string): string {
  try {
    const parsed = JSON.parse(body);
    const detail = parsed?.detail ?? parsed?.error;
    if (typeof detail === 'string' && detail.trim()) return detail;
  } catch {
    // Not JSON; fall through to the raw body.
  }
  return body.trim() ? `API Error ${status}: ${body}` : `API Error ${status}`;
}

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
    throw new ApiError(res.status, errorDetail(res.status, text));
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

// ===================== Research direction check =====================

export interface DataSourceLink {
  name: string;
  url: string;
  kind?: string;
  access?: string;
}

export interface PaperLink {
  citation: string;
  url: string;
}

export interface DataCategory {
  id: string;
  label: string;
  labelZh: string;
  appliesToMarket: boolean;
  sources: DataSourceLink[];
  papers: PaperLink[];
  note?: string | null;
}

export type ConceptStatus = 'available' | 'proxy' | 'missing' | 'wrong_market';

export interface DirectionConcept {
  concept: string;
  status: ConceptStatus;
  fields: string[];
  inventedFields: string[];
  note?: string | null;
  categories: DataCategory[];
  searchTerms: string[];
  searchLinks: { name: string; url: string }[];
}

export type DirectionVerdict = 'feasible' | 'partial' | 'unavailable' | 'unclear' | 'no_data';

export interface DirectionCheckResult {
  verdict: DirectionVerdict;
  reply: string;
  marketMode: 'us' | 'cn' | 'crypto';
  storeFieldCount: number;
  storeFields: string[];
  storePath?: string | null;
  concepts: DirectionConcept[];
  suggestedDirection?: string | null;
  /** The direction to mine with the data check appended; null when it cannot be tested. */
  runDirection?: string | null;
  replication?: { sources: DataSourceLink[]; papers: PaperLink[] } | null;
  keywordHits: string[];
  llm: { used: boolean; error?: string | null };
}

/** Ask the backend whether a direction can be tested with the stored data. */
export async function checkResearchDirection(params: {
  direction: string;
  marketMode: 'us' | 'cn' | 'crypto';
  dataSource?: string;
}) {
  return request<DirectionCheckResult>('/api/v1/research/check-direction', {
    method: 'POST',
    body: JSON.stringify(params),
  });
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

/** One evolution round's LLM feedback, read by the backend from trajectory_pool.json. */
export interface RoundFeedback {
  trajectoryId: string;
  directionId: number | null;
  roundIdx: number | null;
  phase: 'original' | 'mutation' | 'crossover' | string;
  parentIds: string[];
  createdAt: string;
  hypothesis: string;
  /** null when the round produced no feedback (e.g. factor generation failed). */
  decision: boolean | null;
  observations: string;
  hypothesisEvaluation: string;
  newHypothesis: string;
  reason: string;
  factors: { name: string; expression: string }[];
  /** Best factor of the round on the validation split; null where not computed. */
  metrics: Record<string, number | null>;
}

export interface MiningFeedbackReport {
  experimentId: string;
  /** false until the run has finished its first round. */
  available: boolean;
  savedAt: string | null;
  rounds: RoundFeedback[];
}

/**
 * The run folder (log/exp_YYYYMMDD_HHMMSS) of a mining task. Tasks started
 * before the backend recorded experimentId only carry it in the default
 * library suffix; a custom suffix on such a task leaves it unknown.
 */
export function experimentIdForTask(task: Pick<Task, 'experimentId' | 'config'>): string | null {
  if (task.experimentId) return task.experimentId;
  return task.config?.librarySuffix?.match(/exp_\d{8}_\d{6}/)?.[0] ?? null;
}

export async function getExperimentFeedback(experimentId: string) {
  return request<MiningFeedbackReport>(`/api/v1/experiments/${encodeURIComponent(experimentId)}/feedback`);
}

/**
 * Outcome of a past run. `interrupted`: the backend stopped mid-run.
 * `unknown`: the run predates saved run records.
 */
export type RunStatus = 'pending' | 'running' | 'completed' | 'cancelled' | 'failed' | 'interrupted' | 'unknown';

/** One run folder under log/, summarised by the backend from the files it left. */
export interface RunSummary {
  experimentId: string;
  /** 'backend' for a record written live, 'backfilled' for one recovered later, null for none. */
  recordSource: 'backend' | 'backfilled' | null;
  status: RunStatus;
  statusMessage: string | null;
  direction: string | null;
  startedAt: string | null;
  completedAt: string | null;
  /** True when the end time was inferred from the files rather than stamped at the end. */
  completedAtEstimated: boolean;
  durationSeconds: number | null;
  llm: LlmChannel | null;
  usage: TokenUsage | null;
  roundsPlanned: number | null;
  roundsReached: number | null;
  rounds: { total: number; accepted: number; rejected: number; noFeedback: number } | null;
  /** The round with the highest evolution score; metrics are on the validation split. */
  best: {
    directionId: number | null;
    roundIdx: number | null;
    phase: string;
    decision: boolean | null;
    evolutionScore: number | null;
    ic: number | null;
    rankIc: number | null;
    annualizedReturn: number | null;
    sharpe: number | null;
    maxDrawdown: number | null;
  } | null;
  library: {
    file: string;
    factorCount: number;
    marketMode: 'us' | 'cn' | 'crypto' | null;
    market: string | null;
    scopeLabel: string | null;
    splitWindows: Record<'train' | 'valid' | 'test', [string, string]> | null;
  } | null;
  hasResults: boolean;
  /** Set when this backend is tracking the run live. */
  taskId?: string;
}

export interface RunDetail extends RunSummary {
  plannedDirections: (string | null)[];
  settings: Record<string, unknown>;
  evolutionConfig: Record<string, unknown>;
  scores: {
    createdAt: string;
    directionId: number | null;
    roundIdx: number | null;
    phase: string;
    decision: boolean | null;
    rankIc: number | null;
    evolutionScore: number | null;
  }[];
  /** Top factors from the run's library, computed as the live dashboard does. */
  factorMetrics: RealtimeMetrics | null;
}

export async function listExperiments() {
  return request<{ runs: RunSummary[] }>('/api/v1/experiments');
}

export async function getExperiment(experimentId: string) {
  return request<RunDetail>(`/api/v1/experiments/${encodeURIComponent(experimentId)}`);
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

// ========================== Benchmark models API ==========================

export interface MetricDefinition {
  label: string;
  formula: string;
  description: string;
  implementation: string;
  file: string;
  line: number | null;
}

export interface BenchmarkModelResult {
  model: string;
  label: string;
  market: string;
  implementation: string;
  metrics: { IC: number; ICIR: number; 'Rank IC': number; 'Rank ICIR': number };
  portfolio: Record<string, { annualized_net_return?: number; max_drawdown?: number; sharpe_ratio?: number }>;
  preferred_leg: 'long' | 'long_short';
  hyperparameters: Record<string, number | string>;
  training: { seconds: number; epochs_run: number };
  features: { handler: string; count: number; step_len: number };
  split: Record<'train' | 'valid' | 'test', [string, string]>;
  generated_at: string;
  smoke_run: boolean;
  file: string;
}

export interface BenchmarkModelsResponse {
  market: string;
  models: BenchmarkModelResult[];
  definitions: Record<string, MetricDefinition>;
  normalization: { formula: string; description: string };
  available_models: Array<{ id: string; label: string; implementation: string }>;
  torch_available: boolean;
  running: Array<{ taskId: string; status: string; progress: any }>;
}

export async function getBenchmarkModels(market?: string) {
  const query = market ? `?market=${encodeURIComponent(market)}` : '';
  return request<BenchmarkModelsResponse>(`/api/v1/benchmarks/models${query}`);
}

export async function runBenchmarkModels(params: { models: string[]; market?: string }) {
  return request<{ taskId: string; task: Task }>('/api/v1/benchmarks/run', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function getBenchmarkRun(taskId: string) {
  return request<{ task: Task }>(`/api/v1/benchmarks/run/${taskId}`);
}
