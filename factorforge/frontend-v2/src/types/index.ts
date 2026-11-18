// Task status. `cancelled` is what the backend sets when a run is stopped from
// the UI (DELETE /api/v1/mining/{id}); it was missing here, so callers silently
// treated a stopped run as still running.
export type TaskStatus = 'idle' | 'running' | 'completed' | 'failed' | 'cancelled';

// Execution phase
export type ExecutionPhase =
  | 'parsing'      // Parsing requirements
  | 'planning'     // Planning direction
  | 'evolving'     // Evolving
  | 'backtesting'  // Backtesting
  | 'analyzing'    // Analyzing results
  | 'completed';   // Completed

// Factor quality level
export type FactorQuality = 'high' | 'medium' | 'low';

// Task configuration
export interface TaskConfig {
  // Basic configuration
  userInput: string;
  /** When true, use options in "Settings -> Mining Direction" (selected/random), ignoring input box content */
  useCustomMiningDirection?: boolean;
  numDirections?: number;
  maxRounds?: number;
  librarySuffix?: string;

  // LLM configuration
  apiKey?: string;
  apiUrl?: string;
  modelName?: string;

  // Backtest configuration
  market?: 'csi300' | 'csi500' | 'sp500';
  startDate?: string;
  endDate?: string;

  // Advanced configuration
  parallelExecution?: boolean;
  qualityGateEnabled?: boolean;
  backtestTimeout?: number;
  evaluationFrequencies?: Array<'day' | 'week' | 'month'>;
  dataSource?: 'qlib' | 'wrds';
  trainStartDate?: string;
  trainEndDate?: string;
  validStartDate?: string;
  validEndDate?: string;
  testStartDate?: string;
  testEndDate?: string;
}

// Real-time metrics
export interface RealtimeMetrics {
  // IC metrics
  ic: number;
  icir: number;
  rankIc: number;
  rankIcir: number;
  
  // Optional factor name if available (e.g. best factor)
  factorName?: string;
  
  // Top 10 factors list
  top10Factors?: Array<{
    factorName: string;
    factorExpression: string;
    rankIc: number;
    rankIcir: number;
    ic: number;
    icir: number;
    quality?: 'high' | 'medium' | 'low';
    qualityScore?: number;
    frequency?: string;
    /** Portfolio leg that annualReturn / sharpeRatio / maxDrawdown describe. */
    preferredPortfolioLeg?: 'long' | 'long_short';
    portfolioStats?: Record<'long' | 'short' | 'long_short', {
      annualizedGrossReturn?: number | null;
      annualizedNetReturn?: number | null;
      sharpeRatio?: number | null;
      maxDrawdown?: number | null;
      turnover?: number | null;
      transactionCost?: number | null;
      borrowCost?: number | null;
    }> & { decileMonotonicity?: number | null };
    assetPricing?: Record<string, {
      alphaAnnualized?: number | null;
      alphaTStat?: number | null;
      alphaPValue?: number | null;
      rSquared?: number | null;
      adjustedRSquared?: number | null;
      observations?: number | null;
      betas: Record<string, { value?: number | null; tStat?: number | null; pValue?: number | null }>;
    }>;
    industryStatistics?: {
      primaryLevel: 'gsector';
      robustnessLevel: 'ggroup';
      levels: Record<string, {
        coverage?: number | null;
        meanAbsExposure?: number | null;
        maxAbsExposure?: number | null;
        exposureHhi?: number | null;
        groupCount?: number | null;
      }>;
      ggroupRobustness: {
        ic?: number | null;
        icir?: number | null;
        rankIc?: number | null;
        rankIcir?: number | null;
        annualizedNetReturn?: number | null;
        sharpeRatio?: number | null;
        maxDrawdown?: number | null;
        decileMonotonicity?: number | null;
      };
    };
    annualReturn?: number;
    sharpeRatio?: number;
    maxDrawdown?: number;
    calmarRatio?: number;
    cumulativeCurve?: Array<{date: string, value: number}>;
  }>;

  // Return metrics. For the best factor these are the net, annualized figures
  // of `bestFactorLeg` (long–short for US/crypto, long-only for A-shares).
  annualReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  bestFactorLeg?: 'long' | 'long_short' | null;
  bestFactorLongReturn?: number | null;

  // Factor statistics
  totalFactors: number;
  highQualityFactors: number;
  mediumQualityFactors: number;
  lowQualityFactors: number;
}

// Execution progress
export interface ExecutionProgress {
  phase: ExecutionPhase;
  currentRound: number;
  totalRounds: number;
  progress: number; // 0-100
  message: string;
  timestamp: string;
}

// Log entry
export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
}

// Factor information
export interface Factor {
  factorId: string;
  factorName: string;
  factorExpression: string;
  factorDescription: string;
  quality: FactorQuality;
  qualityScore?: number;
  qualityAssessment?: any;
  sourceLibrary?: string;

  // Backtest metrics
  ic: number;
  icir: number;
  rankIc: number;
  rankIcir: number;

  // Metadata
  round: number;
  direction: string;
  createdAt: string;
}

// Backtest result
export interface BacktestResult {
  // Overall metrics
  metrics: RealtimeMetrics;

  // Time series data
  equityCurve: TimeSeriesData[];
  drawdownCurve: TimeSeriesData[];
  icTimeSeries: TimeSeriesData[];

  // Factor list
  factors: Factor[];

  // Quality distribution
  qualityDistribution: {
    high: number;
    medium: number;
    low: number;
  };
}

// Time series data point
export interface TimeSeriesData {
  date: string;
  value: number;
}

// Task information
export interface Task {
  taskId: string;
  status: TaskStatus;
  config: TaskConfig;
  progress: ExecutionProgress;
  metrics?: RealtimeMetrics;
  result?: BacktestResult;
  logs: LogEntry[];
  /** LLM token totals for the run, summed by the backend from every call. */
  usage?: TokenUsage;
  /** How this run reaches its LLM, recorded at launch. */
  llm?: LlmChannel | null;
  createdAt: string;
  /** When the run completed, failed or was stopped; null while running. */
  completedAt?: string | null;
  durationSeconds?: number | null;
  updatedAt: string;
}

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  calls: number;
  /** Cost the provider actually reported. Null means none was reported, which
   *  is not the same as a cost of zero. */
  costUsd?: number | null;
  /** Per-model breakdown; a run can mix a chat model and an embedding model. */
  byModel?: ModelUsage[];
}

/** How a model was reached. CLI calls go through a local subscription-backed
 *  binary, API calls are billed per token by the gateway. */
export type UsageTransport = 'cli' | 'api' | 'other';

/**
 * Which LLM channel a run was configured to use, recorded when it launched.
 *
 * Taken from configuration rather than from call records, so it is known before
 * the first call and still known for a run that never made one.
 */
export interface LlmChannel {
  channel: 'claude_cli' | 'codex_cli' | 'openai_api';
  transport: UsageTransport;
  /** Human label, e.g. "本地 Claude CLI". */
  label: string;
  model: string;
  /** Host of the API endpoint; null for local CLI channels. */
  endpoint?: string | null;
}

export interface ModelUsage {
  /** Model the provider says served the call, or 'unknown' if it said nothing. */
  model: string;
  transport: UsageTransport;
  /** Raw provider tag, e.g. 'claude_cli', 'codex_cli', 'openai'. */
  source: string;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  calls: number;
  costUsd?: number | null;
}

// API Response
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// WebSocket message type
export type WsMessageType =
  | 'progress'
  | 'metrics'
  | 'log'
  | 'result'
  | 'usage'
  | 'error';

// WebSocket message
export interface WsMessage {
  type: WsMessageType;
  taskId: string;
  data: any;
  timestamp: string;
}
