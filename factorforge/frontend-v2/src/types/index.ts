// Task status
export type TaskStatus = 'idle' | 'running' | 'completed' | 'failed';

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

  // Return metrics
  annualReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;

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
  createdAt: string;
  updatedAt: string;
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
  | 'error';

// WebSocket message
export interface WsMessage {
  type: WsMessageType;
  taskId: string;
  data: any;
  timestamp: string;
}
