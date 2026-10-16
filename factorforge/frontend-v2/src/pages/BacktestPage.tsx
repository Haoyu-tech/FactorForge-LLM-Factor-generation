import { useLanguage } from '@/context/LanguageContext';
import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import {
  Play,
  Square,
  Loader2,
  FileText,
  TrendingUp,
  AlertCircle,
  Info,
  Clock,
  BarChart3,
  Database,
  RefreshCw,
  CheckCircle2,
} from 'lucide-react';
import {
  getFactors,
  getCacheStatus,
  getBacktestConfig,
  warmCache,
} from '@/services/api';
import type { BacktestConfigResponse, CacheStatusResponse } from '@/services/api';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from 'recharts';
import { formatDate, formatPercent } from '@/utils';

// ... (existing MetricCard component)

const CumulativeReturnChart: React.FC<{ data: { date: string; value: number }[] }> = ({ data }) => {
  if (!data || data.length === 0) return null;

  // Generate ticks for every 6 months
  const ticks = [];
  if (data.length > 0) {
    const startDate = new Date(data[0].date);
    const endDate = new Date(data[data.length - 1].date);
    let currentDate = new Date(startDate);
    
    // Align to start of month
    currentDate.setDate(1);
    
    while (currentDate <= endDate) {
      ticks.push(currentDate.toISOString().split('T')[0]);
      // Add 6 months
      currentDate.setMonth(currentDate.getMonth() + 6);
    }
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="glass-strong rounded-lg p-3 shadow-xl border border-border/50">
          <p className="text-xs text-muted-foreground mb-1">{formatDate(label)}</p>
          <p className="text-sm font-bold text-primary">
            累计净收益: {formatPercent(payload[0].value)}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="colorReturn" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} vertical={false} />
          <XAxis 
            dataKey="date" 
            tick={{ fill: '#9CA3AF', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            ticks={ticks}
            tickFormatter={(value) => formatDate(value).split('/').slice(0, 2).join('/')} 
          />
          <YAxis 
            tick={{ fill: '#9CA3AF', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#374151', strokeWidth: 1, strokeDasharray: '4 4' }} />
          <Area
            type="monotone"
            dataKey="value"
            stroke="#10B981"
            strokeWidth={2}
            fill="url(#colorReturn)"
            animationDuration={1000}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

const MultiStrategyReturnChart: React.FC<{ analytics: Record<string, any> }> = ({ analytics }) => {
  const labels: Record<string, string> = { long: 'Long', short: 'Short', long_short: 'Long–Short' };
  const colors: Record<string, string> = { long: '#10B981', short: '#EF4444', long_short: '#6366F1' };
  const rows = new Map<string, Record<string, string | number>>();
  Object.entries(analytics || {}).forEach(([name, result]: [string, any]) => {
    (result?.curve || []).forEach((point: { date: string; value: number }) => {
      const row = rows.get(point.date) || { date: point.date };
      row[name] = point.value;
      rows.set(point.date, row);
    });
  });
  const data = Array.from(rows.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  if (data.length === 0) return null;

  return (
    <div className="h-[320px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} vertical={false} />
          <XAxis dataKey="date" tick={{ fill: '#9CA3AF', fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={60} />
          <YAxis tick={{ fill: '#9CA3AF', fontSize: 11 }} tickLine={false} tickFormatter={(value) => `${(value * 100).toFixed(0)}%`} />
          <Tooltip formatter={(value: number) => `${(value * 100).toFixed(2)}%`} />
          <Legend />
          {Object.keys(labels).map(name => (
            <Line key={name} type="monotone" dataKey={name} name={labels[name]} stroke={colors[name]} dot={false} strokeWidth={2} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

const DecileReturnChart: React.FC<{ analytics: Record<string, any> }> = ({ analytics }) => {
  const colors = [
    '#DC2626', '#EA580C', '#F59E0B', '#EAB308', '#84CC16',
    '#22C55E', '#14B8A6', '#06B6D4', '#3B82F6', '#7C3AED',
  ];
  const rows = new Map<string, Record<string, string | number>>();
  for (let number = 1; number <= 10; number += 1) {
    const name = `group_${number}`;
    (analytics?.[name]?.curve || []).forEach((point: { date: string; value: number }) => {
      const row = rows.get(point.date) || { date: point.date };
      row[name] = point.value;
      rows.set(point.date, row);
    });
  }
  const data = Array.from(rows.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  if (data.length === 0) return null;

  return (
    <div className="h-[380px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} vertical={false} />
          <XAxis dataKey="date" tick={{ fill: '#9CA3AF', fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={60} />
          <YAxis tick={{ fill: '#9CA3AF', fontSize: 11 }} tickLine={false} tickFormatter={(value) => `${(value * 100).toFixed(0)}%`} />
          <Tooltip formatter={(value: number, name: string) => [`${(value * 100).toFixed(2)}%`, `第${name.split('_')[1]}组`]} />
          <Legend formatter={(value) => `第${String(value).split('_')[1]}组`} />
          {colors.map((color, index) => {
            const number = index + 1;
            return (
              <Line
                key={number}
                type="monotone"
                dataKey={`group_${number}`}
                name={`group_${number}`}
                stroke={color}
                dot={false}
                strokeWidth={number === 1 || number === 10 ? 2.5 : 1.4}
                opacity={number === 1 || number === 10 ? 1 : 0.75}
              />
            );
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

import { useTaskContext } from '@/context/TaskContext';

// ========================== Component ==========================

export const BacktestPage: React.FC = () => {
  const { language } = useLanguage();
  const zh = language === 'zh';
  const {
    backendAvailable,
    backtestTask: task,
    backtestLogs: logs,
    startBacktestTask,
    stopBacktestTask,
  } = useTaskContext();

  // -- Local UI State --
  const selectedLibrary = '__all__';
  const [factorSource, setFactorSource] = useState<'custom' | 'combined' | 'kelly_jkp'>('custom');
  const [portfolioMode, setPortfolioMode] = useState<'long' | 'short' | 'long_short'>('long_short');
  const [portfolioOptimization, setPortfolioOptimization] = useState(false);
  const [correlationPruning, setCorrelationPruning] = useState(true);
  const [correlationThreshold, setCorrelationThreshold] = useState(0.85);
  const [qualityFilter, setQualityFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');
  const [kellyMissingThreshold, setKellyMissingThreshold] = useState(0.20);
  const [kellyModel, setKellyModel] = useState<'lightgbm' | 'pls5' | 'lasso'>('lightgbm');
  const [kellyRetrainMonths, setKellyRetrainMonths] = useState(12);
  const [kellyMinTrainYears, setKellyMinTrainYears] = useState(10);
  const [factorCount, setFactorCount] = useState(0);
  const [qualityCounts, setQualityCounts] = useState({ all: 0, high: 0, medium: 0, low: 0 });
  const [isStarting, setIsStarting] = useState(false);
  const [backtestConfig, setBacktestConfig] = useState<BacktestConfigResponse | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Cache status state
  const [cacheStatus, setCacheStatus] = useState<CacheStatusResponse | null>(null);
  const [cacheLoading, setCacheLoading] = useState(false);
  const [warmingCache, setWarmingCache] = useState(false);
  const [warmCacheResult, setWarmCacheResult] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const loadConfig = () => getBacktestConfig()
      .then(resp => {
        if (active && resp.success && resp.data) setBacktestConfig(resp.data);
      })
      .catch(() => {
        if (active) setBacktestConfig(null);
      });
    loadConfig();
    const timer = window.setInterval(loadConfig, 30_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (backtestConfig?.region !== 'us' && factorSource === 'kelly_jkp') {
      setFactorSource('custom');
    }
  }, [backtestConfig?.region, factorSource]);

  useEffect(() => {
    if (backtestConfig?.region !== 'us' || portfolioMode !== 'long_short') {
      setPortfolioOptimization(false);
    }
  }, [backtestConfig?.region, portfolioMode, factorSource]);

  useEffect(() => {
    setKellyMinTrainYears(backtestConfig?.region === 'crypto' ? 3 : 10);
  }, [backtestConfig?.region]);

  // Load factor count and cache status when library changes
  useEffect(() => {
    if (!selectedLibrary) return;
    (async () => {
      try {
        const marketMode = backtestConfig?.region === 'crypto' ? 'crypto' : (backtestConfig?.region === 'cn' ? 'cn' : 'us');
        const scopedMarket = (backtestConfig?.market || (marketMode === 'crypto' ? 'binance_usdm' : marketMode === 'cn' ? 'csi300' : 'sp500')) as 'sp500' | 'csi300' | 'csi500' | 'sme_composite' | 'binance_usdm';
        const scope = { library: '__all__', marketMode, market: scopedMarket, limit: 1 } as const;
        const [allResp, highResp, mediumResp, lowResp] = await Promise.all([
          getFactors(scope),
          getFactors({ ...scope, quality: 'high' }),
          getFactors({ ...scope, quality: 'medium' }),
          getFactors({ ...scope, quality: 'low' }),
        ]);
        if (allResp.success && allResp.data) {
          const counts = {
            all: allResp.data.total || 0,
            high: highResp.data?.total || 0,
            medium: mediumResp.data?.total || 0,
            low: lowResp.data?.total || 0,
          };
          setQualityCounts(counts);
        }
      } catch { /* ignore */ }
    })();
    setCacheStatus(null);
    setCacheLoading(false);
  }, [selectedLibrary, backtestConfig?.region, backtestConfig?.market]);

  useEffect(() => {
    if (factorSource === 'kelly_jkp') {
      const key = String(kellyMissingThreshold);
      setFactorCount(backtestConfig?.kelly?.thresholdCounts?.[key] || 0);
    } else {
      setFactorCount(qualityFilter === 'all' ? qualityCounts.all : qualityCounts[qualityFilter]);
    }
  }, [factorSource, qualityFilter, qualityCounts, kellyMissingThreshold, backtestConfig]);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // -- Start backtest --
  const handleStart = async () => {
    if (!backtestConfig?.supportedModels?.includes(kellyModel)) return;
    if (factorSource !== 'kelly_jkp' && !selectedLibrary) return;
    if (factorSource === 'kelly_jkp' && !backtestConfig?.kelly?.ready) return;
    setIsStarting(true);
    try {
      await startBacktestTask({
        factorJson: factorSource === 'kelly_jkp' ? '' : selectedLibrary,
        factorSource,
        portfolioMode,
        qualityFilter,
        kellyMissingThreshold,
        model: kellyModel,
        kellyModel,
        kellyRetrainMonths,
        kellyMinTrainYears,
        retrainMonths: kellyRetrainMonths,
        minTrainYears: kellyMinTrainYears,
        portfolioOptimization,
        correlationPruning,
        correlationThreshold,
      });
    } catch (err: any) {
      console.error('Failed to start backtest:', err);
    } finally {
      setIsStarting(false);
    }
  };

  // -- Cancel backtest --
  const handleCancel = async () => {
    stopBacktestTask();
  };

  // -- Warm cache --
  const handleWarmCache = async () => {
    if (!selectedLibrary) return;
    setWarmingCache(true);
    setWarmCacheResult(null);
    try {
      const resp = await warmCache(selectedLibrary);
      if (resp.success) {
        // Use the detailed message from backend
        setWarmCacheResult(resp.message || '完成');
      }
      // Refresh cache status
      const cs = await getCacheStatus(selectedLibrary);
      if (cs.success && cs.data) {
        setCacheStatus(cs.data as unknown as CacheStatusResponse);
      }
    } catch (err: any) {
      setWarmCacheResult(`预热失败: ${err.message}`);
    }
    setWarmingCache(false);
  };

  const isRunning = task?.status === 'running';
  const modelBackendReady = Boolean(backtestConfig?.supportedModels?.includes(kellyModel));
  const isFinished = task?.status === 'completed' || task?.status === 'failed' || task?.status === 'cancelled';

  // -- Render metric card --
  const MetricCard = ({ label, value, unit }: { label: string; value: any; unit?: string }) => (
    <div className="glass rounded-xl p-4 text-center">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className="text-lg font-bold text-foreground">
        {typeof value === 'number' ? value.toFixed(4) : value ?? '--'}
        {unit && <span className="text-xs text-muted-foreground ml-1">{unit}</span>}
      </div>
    </div>
  );

  // Extract metrics from task
  const metrics = task?.metrics || {};
  const marketLabel = backtestConfig?.market === 'sp500'
    ? (zh ? 'S&P 500（标普500）' : 'S&P 500')
    : backtestConfig?.market === 'csi500'
      ? (zh ? 'CSI 500（中证500）' : 'CSI 500')
      : backtestConfig?.market === 'csi300'
        ? (zh ? 'CSI 300（沪深300）' : 'CSI 300')
        : backtestConfig?.market === 'binance_usdm'
          ? (zh ? 'Binance USDⓈ-M USDT 永续' : 'Binance USDⓈ-M USDT perpetuals')
          : backtestConfig?.market === 'sme_composite' ? (zh ? '中小综指' : 'SME Composite') : backtestConfig?.market || '--';
  const benchmarkLabel = backtestConfig?.benchmark === '^GSPC'
    ? (zh ? '^GSPC（标普500指数）' : '^GSPC (S&P 500 Index)')
    : backtestConfig?.benchmark || '--';
  const isKellyResult = task?.config?.factorSource === 'kelly_jkp';
  const isCryptoMarket = backtestConfig?.region === 'crypto' || backtestConfig?.market === 'binance_usdm';

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <BarChart3 className="h-8 w-8 text-primary" />
          独立回测
        </h1>
        <p className="text-muted-foreground mt-1">
          使用因子库进行全周期回测评估
        </p>
      </div>

      {/* Info Banner */}
      <Card className="glass border-primary/30">
        <CardContent className="p-4">
          <div className="flex gap-3">
            <Info className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
            <div className="text-sm space-y-1">
              <p className="text-muted-foreground">
                {zh ? '独立回测在测试集评估样本外表现：' : 'Out-of-sample evaluation on the test set: '}
                <strong className="text-foreground">{backtestConfig?.testStartDate || backtestConfig?.startTime || '--'} ~ {backtestConfig?.testEndDate || backtestConfig?.endTime || '--'}</strong>。
                {zh ? '所有因子源均采用 Expanding Window，可选择 LightGBM、PLS5 或 Lasso。' : ' All factor sources use an expanding window with LightGBM, PLS5, or Lasso.'}
              </p>
              {isCryptoMarket && (
                <p className="text-muted-foreground">
                  <strong className="text-foreground">{zh ? 'Crypto 选择口径：' : 'Crypto selection: '}</strong>
                  {zh ? '验证集仅用 RankIC/RankICIR 评价预测能力；IC只作诊断。高相关因子保留验证集正向 RankIC 更高者，测试集仅作最终样本外评价。' : 'Predictive power is evaluated using validation RankIC and RankICIR; IC is diagnostic only. Among highly correlated factors, retain the one with the higher positive validation RankIC. The test set is reserved for final out-of-sample evaluation.'}
                </p>
              )}
              <p className="text-muted-foreground">
                {zh ? 'Custom 仅使用当前市场的自定义因子；Combined 将自定义因子与 Alpha158(20) 基线因子组合使用；WRDS Kelly 153 使用历史 S&P 500 成分股月频数据，仅限美股。' : 'Custom uses custom factors from the current market. Combined adds Alpha158(20) baseline factors. WRDS Kelly 153 uses monthly data for historical S&P 500 constituents and is available for US stocks only.'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Backend Status */}
      {backendAvailable === false && (
        <Card className="glass border-destructive/50">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <span className="text-sm text-destructive">
              后端服务未连接。请先启动后端：<code className="bg-secondary px-2 py-0.5 rounded">cd frontend-v2 && bash start.sh</code>
            </span>
          </CardContent>
        </Card>
      )}

      {/* Configuration Panel */}
      <Card className="glass card-hover">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            回测配置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">因子源类型</label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <button
                  onClick={() => setFactorSource('custom')}
                  disabled={isRunning}
                  className={factorSource === 'custom'
                    ? 'px-4 py-3 rounded-lg border text-sm font-medium border-primary bg-primary/10 text-primary'
                    : 'px-4 py-3 rounded-lg border text-sm font-medium border-input bg-background text-muted-foreground hover:border-primary/50'}
                >
                  Custom
                  <span className="block text-xs font-normal mt-1">{zh ? '当前市场总 LLM 因子库 · Expanding Window' : 'All LLM factors in this market · Expanding window'}</span>
                </button>
                <button
                  onClick={() => setFactorSource('combined')}
                  disabled={isRunning}
                  className={factorSource === 'combined'
                    ? 'px-4 py-3 rounded-lg border text-sm font-medium border-primary bg-primary/10 text-primary'
                    : 'px-4 py-3 rounded-lg border text-sm font-medium border-input bg-background text-muted-foreground hover:border-primary/50'}
                >
                  Combined
                  <span className="block text-xs font-normal mt-1">{zh ? '总 LLM 因子库 + Alpha158(20) · Expanding Window' : 'All LLM factors + Alpha158(20) · Expanding window'}</span>
                </button>
                <button
                  onClick={() => setFactorSource('kelly_jkp')}
                  disabled={isRunning || backtestConfig?.region !== 'us'}
                  className={factorSource === 'kelly_jkp'
                    ? 'px-4 py-3 rounded-lg border text-sm font-medium border-primary bg-primary/10 text-primary'
                    : `px-4 py-3 rounded-lg border text-sm font-medium border-input bg-background text-muted-foreground hover:border-primary/50 ${backtestConfig?.region !== 'us' ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  WRDS Kelly 153
                  <span className="block text-xs font-normal mt-1">
                    {backtestConfig?.region !== 'us' ? (zh ? '仅限美股模式' : 'US stocks only') : (zh ? '历史 S&P 500 · 月频 Expanding Window' : 'Historical S&P 500 · Monthly expanding window')}
                  </span>
                </button>
              </div>
            </div>

            {factorSource === 'kelly_jkp' ? (
              <div className="rounded-xl border border-primary/25 bg-primary/5 p-4 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="font-medium">JKP/Kelly 153 因子面板</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {backtestConfig?.kelly?.startMonth || '--'} ～ {backtestConfig?.kelly?.endMonth || '--'} ·
                      历史成分股月度样本 {backtestConfig?.kelly?.memberMonths?.toLocaleString('zh-CN') || '--'}
                    </div>
                  </div>
                  <Badge variant={backtestConfig?.kelly?.ready ? 'success' : 'destructive'}>
                    {backtestConfig?.kelly?.ready ? '数据已就绪' : '数据未生成'}
                  </Badge>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">训练样本缺失率上限</label>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                    {[0.10, 0.20, 0.30, 0.40].map(value => (
                      <button
                        key={value}
                        onClick={() => setKellyMissingThreshold(value)}
                        disabled={isRunning}
                        className={kellyMissingThreshold === value
                          ? 'rounded-lg border border-primary bg-primary/10 text-primary px-3 py-2.5 text-sm font-medium'
                          : 'rounded-lg border border-input bg-background text-muted-foreground px-3 py-2.5 text-sm'}
                      >
                        ≤ {(value * 100).toFixed(0)}%
                        <span className="block text-xs font-normal mt-0.5">
                          全样本参考 {backtestConfig?.kelly?.thresholdCounts?.[String(value)] || 0} 个
                        </span>
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    实际因子集合在每次重训时仅根据当时已有训练样本重新筛选，不使用未来月份的缺失情况。
                  </p>
                  <details className="mt-3 rounded-lg border border-border/60 bg-background/60">
                    <summary className="cursor-pointer px-3 py-2 text-sm font-medium">
                      查看全部 153 个因子的 S&amp;P 500 缺失率
                    </summary>
                    <div className="max-h-80 overflow-auto border-t border-border/50">
                      <table className="w-full min-w-[650px] text-xs">
                        <thead className="sticky top-0 bg-background text-muted-foreground">
                          <tr>
                            <th className="px-3 py-2 text-left">因子</th>
                            <th className="px-3 py-2 text-right">模型样本缺失率</th>
                            <th className="px-3 py-2 text-right">有效观测</th>
                            <th className="px-3 py-2 text-left">最早有效月</th>
                            <th className="px-3 py-2 text-left">最近有效月</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(backtestConfig?.kelly?.factors || []).map(row => (
                            <tr key={row.factor} className="border-t border-border/30">
                              <td className="px-3 py-2 font-mono">{row.factor}</td>
                              <td className="px-3 py-2 text-right">
                                {(row.missing_rate_model_sample * 100).toFixed(2)}%
                              </td>
                              <td className="px-3 py-2 text-right">
                                {row.nonmissing_model_sample.toLocaleString('zh-CN')}
                              </td>
                              <td className="px-3 py-2">{row.first_valid_month || '--'}</td>
                              <td className="px-3 py-2">{row.last_valid_month || '--'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">重新训练间隔</label>
                    <select
                      value={kellyRetrainMonths}
                      onChange={event => setKellyRetrainMonths(Number(event.target.value))}
                      disabled={isRunning}
                      className="w-full rounded-lg border border-input bg-background px-4 py-2.5 text-sm"
                    >
                      <option value={1}>每月重训</option>
                      <option value={3}>每3个月重训</option>
                      <option value={6}>每6个月重训</option>
                      <option value={12}>每12个月重训（默认）</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">最短训练历史</label>
                    <select
                      value={kellyMinTrainYears}
                      onChange={event => setKellyMinTrainYears(Number(event.target.value))}
                      disabled={isRunning}
                      className="w-full rounded-lg border border-input bg-background px-4 py-2.5 text-sm"
                    >
{backtestConfig?.region === 'crypto' && <option value={3}>{zh ? '3年（Crypto默认）' : '3 years (Crypto default)'}</option>}
                      <option value={5}>{zh ? '5年' : '5 years'}</option>
                      <option value={10}>{zh ? '10年' : '10 years'}{backtestConfig?.region === 'crypto' ? '' : (zh ? '（默认）' : ' (default)')}</option>
                      <option value={15}>{zh ? '15年' : '15 years'}</option>
                      <option value={20}>{zh ? '20年' : '20 years'}</option>
                    </select>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-primary/25 bg-primary/5 p-4">
                <div className="font-medium">
                  {backtestConfig?.region === 'crypto'
                    ? (zh ? '币安 USDT 永续总因子库' : 'Binance USDT Perpetual — All Factors')
                    : backtestConfig?.region === 'cn'
                    ? (zh ? `${marketLabel} 总因子库` : `${marketLabel} — All Factors`)
                    : (zh ? '美股 S&P 500 总因子库' : 'US S&P 500 — All Factors')}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {zh ? `自动合并全部历史快照并按公式去重；当前质量筛选下包含 ${factorCount} 个因子。` : `All historical snapshots are merged and deduplicated by formula. ${factorCount} factors match the current quality filter.`}
                </p>
              </div>
            )}

            {factorSource !== 'kelly_jkp' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 rounded-xl border border-border/60 bg-background/50 p-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Expanding Window 重新训练间隔</label>
                  <select
                    value={kellyRetrainMonths}
                    onChange={event => setKellyRetrainMonths(Number(event.target.value))}
                    disabled={isRunning}
                    className="w-full rounded-lg border border-input bg-background px-4 py-2.5 text-sm"
                  >
                    <option value={1}>每月重训</option>
                    <option value={3}>每3个月重训</option>
                    <option value={6}>每6个月重训</option>
                    <option value={12}>每12个月重训（默认）</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">最短训练历史</label>
                  <select
                    value={kellyMinTrainYears}
                    onChange={event => setKellyMinTrainYears(Number(event.target.value))}
                    disabled={isRunning}
                    className="w-full rounded-lg border border-input bg-background px-4 py-2.5 text-sm"
                  >
{backtestConfig?.region === 'crypto' && <option value={3}>{zh ? '3年（Crypto默认）' : '3 years (Crypto default)'}</option>}
                    <option value={5}>{zh ? '5年' : '5 years'}</option>
                    <option value={10}>{zh ? '10年' : '10 years'}{backtestConfig?.region === 'crypto' ? '' : (zh ? '（默认）' : ' (default)')}</option>
                    <option value={15}>{zh ? '15年' : '15 years'}</option>
                    <option value={20}>{zh ? '20年' : '20 years'}</option>
                  </select>
                </div>
              </div>
            )}
          </div>


          <div className="pt-2 border-t border-border/50 space-y-4">
            {!modelBackendReady && (
              <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
                当前挖掘任务结束后，后端将自动安全重载并启用模型选择；页面每30秒自动检测。
              </div>
            )}
            <div>
              <label className="block text-sm font-medium mb-2">预测模型</label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                {([
                  ['lightgbm', 'LightGBM', '非线性树模型，验证集选择迭代轮数'],
                  ['pls5', 'PLS5', '最多5个偏最小二乘潜变量，验证集选择维数'],
                  ['lasso', 'Lasso', '稀疏线性模型，验证集选择惩罚强度'],
                ] as const).map(([value, label, description]) => (
                  <button
                    key={value}
                    onClick={() => setKellyModel(value)}
                    disabled={isRunning}
                    className={kellyModel === value
                      ? 'rounded-lg border border-primary bg-primary/10 text-primary px-3 py-2.5 text-sm font-medium text-left'
                      : 'rounded-lg border border-input bg-background text-muted-foreground px-3 py-2.5 text-sm text-left'}
                  >
                    {label}
                    <span className="block text-xs font-normal mt-1">{description}</span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">训练、验证和测试区间</label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
                <div className="rounded-lg bg-background/70 border border-border/50 p-3">
                  <div className="text-muted-foreground">训练集</div>
                  <div className="font-medium mt-1">{backtestConfig?.trainStartDate || '--'} ～ {backtestConfig?.trainEndDate || '--'}</div>
                </div>
                <div className="rounded-lg bg-background/70 border border-border/50 p-3">
                  <div className="text-muted-foreground">验证集</div>
                  <div className="font-medium mt-1">{backtestConfig?.validStartDate || '--'} ～ {backtestConfig?.validEndDate || '--'}</div>
                </div>
                <div className="rounded-lg bg-background/70 border border-border/50 p-3">
                  <div className="text-muted-foreground">测试 / 回测集</div>
                  <div className="font-medium mt-1">{backtestConfig?.testStartDate || '--'} ～ {backtestConfig?.testEndDate || '--'}</div>
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {factorSource === 'kelly_jkp'
                  ? 'Kelly 使用月频 Expanding Window；进入测试期后训练窗口持续扩张。'
                  : 'Custom / Combined 使用日频 Expanding Window；验证集只选择模型复杂度，测试期按上方间隔扩展历史并重新训练。'}
              </p>
            </div>
          </div>

          {factorSource !== 'kelly_jkp' && (
          <div className="pt-2 border-t border-border/50">
            <label className="block text-sm font-medium mb-2">因子质量</label>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {([
                ['all', '全部', '不按质量筛选'],
                ['high', '高质量', '综合分 ≥ 70且证据充分'],
                ['medium', '中质量', '综合分 ≥ 45'],
                ['low', '低质量', '综合分不足或关键指标为负'],
              ] as const).map(([value, title, description]) => (
                <button
                  key={value}
                  onClick={() => setQualityFilter(value)}
                  disabled={isRunning}
                  className={`px-4 py-2.5 rounded-lg border text-sm font-medium transition-all ${
                    qualityFilter === value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-input bg-background text-muted-foreground hover:border-primary/50'
                  }`}
                >
                  {title} ({qualityCounts[value]})
                  <span className="block text-xs font-normal mt-0.5">{description}</span>
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              质量筛选在因子计算和训练前执行；每个档位单独保存回测结果。
            </p>
          </div>

          )}

          <div className="pt-2 border-t border-border/50">
            <div className={`flex flex-col sm:flex-row sm:items-center gap-3 rounded-lg border p-3 ${correlationPruning ? 'border-primary/50 bg-primary/5' : ''}`}>
              <label className="flex flex-1 items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4"
                  checked={correlationPruning}
                  onChange={(event) => setCorrelationPruning(event.target.checked)}
                  disabled={isRunning}
                />
                <span>
                  <span className="block text-sm font-medium">验证集相关性去冗余</span>
                  <span className="block text-xs text-muted-foreground mt-0.5">按验证集月末股票横截面 Spearman 聚类；每个高相关簇只向模型输入一个代表因子，因子库原始记录不删除。</span>
                </span>
              </label>
              <select
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                value={correlationThreshold}
                onChange={(event) => setCorrelationThreshold(Number(event.target.value))}
                disabled={isRunning || !correlationPruning}
                aria-label="相关性阈值"
              >
                <option value={0.8}>|ρ| ≥ 0.80</option>
                <option value={0.85}>|ρ| ≥ 0.85（推荐）</option>
                <option value={0.9}>|ρ| ≥ 0.90</option>
                <option value={0.95}>|ρ| ≥ 0.95</option>
              </select>
            </div>
          </div>

          <div className="pt-2 border-t border-border/50">
            <label className={`flex items-start gap-3 rounded-lg border p-3 ${backtestConfig?.region !== 'us' || portfolioMode !== 'long_short' ? 'opacity-50' : 'cursor-pointer hover:border-primary/50'}`}>
              <input
                type="checkbox"
                className="mt-1 h-4 w-4"
                checked={portfolioOptimization}
                onChange={(event) => setPortfolioOptimization(event.target.checked)}
                disabled={isRunning || backtestConfig?.region !== 'us' || portfolioMode !== 'long_short'}
              />
              <span>
                <span className="block text-sm font-medium">MAXSER-PR 组合优化</span>
                <span className="block text-xs text-muted-foreground mt-0.5">POET 风险估计 + 正弹性网；月度调仓，过去 756 个交易日，目标年化波动 4%，净敞口为 0。支持美股总因子库与 WRDS Kelly 因子库。</span>
              </span>
            </label>
          </div>

          <div className="pt-2 border-t border-border/50">
            <label className="block text-sm font-medium mb-2">组合方向</label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {([
                ['long', 'Long', '做多预测排名前10%'],
                ['short', 'Short', '做空预测排名后10%'],
                ['long_short', 'Long–Short', '50%多头 + 50%空头'],
              ] as const).map(([value, title, description]) => (
                <button
                  key={value}
                  onClick={() => setPortfolioMode(value)}
                  disabled={isRunning}
                  className={`px-4 py-2.5 rounded-lg border text-sm font-medium transition-all ${
                    portfolioMode === value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-input bg-background text-muted-foreground hover:border-primary/50'
                  }`}
                >
                  {title}
                  <span className="block text-xs font-normal mt-0.5">{description}</span>
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              三种方向都会计算并展示；该选项决定顶部摘要和主累计曲线。换手成本按成交名义金额的 5 bps 计入。
            </p>
          </div>

          {/* Cache Status */}
          {selectedLibrary && selectedLibrary !== '__all__' && factorSource !== 'kelly_jkp' && (
            <div className="pt-2 border-t border-border/50">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Database className="h-4 w-4 text-primary" />
                  因子缓存状态
                </div>
                <div className="flex items-center gap-2">
                  {warmCacheResult && (
                    <span className="text-xs text-muted-foreground">{warmCacheResult}</span>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleWarmCache}
                    disabled={warmingCache || isRunning || !cacheStatus}
                  >
                    {warmingCache ? (
                      <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3 w-3 mr-1" />
                    )}
                    同步缓存
                  </Button>
                </div>
              </div>
              {cacheLoading ? (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  正在检查缓存状态...
                </div>
              ) : cacheStatus ? (
                <div className="space-y-2">
                  {/* Summary bar */}
                  <div className="flex items-center gap-3 text-xs flex-wrap">
                    <span className="text-muted-foreground">共 {cacheStatus.total} 个因子</span>
                    {(cacheStatus.h5_cached + cacheStatus.md5_cached) > 0 && (
                      <span className="flex items-center gap-1 text-green-500">
                        <CheckCircle2 className="h-3 w-3" />
                        已缓存: {cacheStatus.h5_cached + cacheStatus.md5_cached}
                        <span className="text-muted-foreground font-normal">
                          (HDF5 {cacheStatus.h5_cached} + MD5 {cacheStatus.md5_cached})
                        </span>
                      </span>
                    )}
                    {cacheStatus.need_compute > 0 && (
                      <span className="flex items-center gap-1 text-muted-foreground/70">
                        <AlertCircle className="h-3 w-3" />
                        未缓存: {cacheStatus.need_compute}（回测时计算）
                      </span>
                    )}
                  </div>
                  {/* Progress bar */}
                  <div className="h-2 bg-secondary rounded-full overflow-hidden flex">
                    {cacheStatus.total > 0 && (
                      <>
                        <div
                          className="h-full bg-green-500 transition-all"
                          style={{ width: `${(cacheStatus.h5_cached / cacheStatus.total) * 100}%` }}
                          title={`HDF5 缓存: ${cacheStatus.h5_cached}`}
                        />
                        <div
                          className="h-full bg-blue-500 transition-all"
                          style={{ width: `${(cacheStatus.md5_cached / cacheStatus.total) * 100}%` }}
                          title={`MD5 缓存: ${cacheStatus.md5_cached}`}
                        />
                        <div
                          className="h-full bg-muted-foreground/20 transition-all"
                          style={{ width: `${(cacheStatus.need_compute / cacheStatus.total) * 100}%` }}
                          title={`未缓存（跳过）: ${cacheStatus.need_compute}`}
                        />
                      </>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {cacheStatus.need_compute === 0
                      ? '所有因子已缓存，回测将快速执行'
                      : `将使用 ${cacheStatus.h5_cached + cacheStatus.md5_cached} 个已缓存因子进行回测，${cacheStatus.need_compute} 个未缓存因子已自动跳过`}
                  </p>
                </div>
              ) : null}
            </div>
          )}

          {/* Fixed display fields */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-border/50">
            <div className="text-sm">
              <span className="text-muted-foreground">市场：</span>
              <span className="font-medium ml-1">{marketLabel}</span>
            </div>
            <div className="text-sm">
              <span className="text-muted-foreground">回测区间：</span>
              <span className="font-medium ml-1">{backtestConfig?.testStartDate || backtestConfig?.startTime || '--'} ~ {backtestConfig?.testEndDate || backtestConfig?.endTime || '--'}</span>
            </div>
            <div className="text-sm">
              <span className="text-muted-foreground">基准：</span>
              <span className="font-medium ml-1">{benchmarkLabel}</span>
            </div>
          </div>

          {/* Start / Cancel Button */}
          <div className="flex justify-end gap-3 pt-2">
            {isRunning ? (
              <Button variant="outline" onClick={handleCancel}>
                <Square className="h-4 w-4 mr-2" />
                停止回测
              </Button>
            ) : (
              <Button
                variant="primary"
                onClick={handleStart}
                disabled={backendAvailable === false || !modelBackendReady || isStarting || (factorSource === 'kelly_jkp' ? !backtestConfig?.kelly?.ready : !selectedLibrary)}
              >
                {isStarting ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Play className="h-4 w-4 mr-2" />
                )}
                开始回测
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Progress + Status */}
      {task && (
        <Card className={`glass card-hover ${isRunning ? 'border-primary/50' : ''}`}>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {isRunning ? (
                  <div className="relative h-5 w-5">
                    <div className="absolute inset-0 rounded-full bg-primary/30 animate-ping" />
                    <BarChart3 className="relative h-5 w-5 text-primary" />
                  </div>
                ) : task.status === 'completed' ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                ) : task.status === 'failed' ? (
                  <AlertCircle className="h-5 w-5 text-red-500" />
                ) : (
                  <Clock className="h-5 w-5" />
                )}
                回测进度
              </div>
              <Badge
                variant={
                  task.status === 'completed' ? 'default' :
                  task.status === 'running' ? 'default' :
                  task.status === 'failed' ? 'destructive' : 'outline'
                }
              >
                {task.status === 'running' ? '运行中' :
                 task.status === 'completed' ? '已完成' :
                 task.status === 'failed' ? '失败' :
                 task.status === 'cancelled' ? '已取消' : task.status}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Running animation banner */}
            {isRunning && (
              <div className="mb-4 rounded-lg bg-primary/5 border border-primary/20 p-3 flex items-center gap-3">
                <Loader2 className="h-5 w-5 text-primary animate-spin flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-primary">
                    回测正在执行中
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {task.progress?.message || '正在加载因子数据并训练模型...'}
                  </p>
                </div>
              </div>
            )}

            {/* Progress bar */}
            <div className="mb-4">
              <div className="flex justify-between text-sm mb-1">
                <span className="text-muted-foreground">{task.progress?.message || '等待中...'}</span>
                <span className="text-muted-foreground">
                  {task.status === 'completed' ? '100%' :
                   task.status === 'failed' ? '失败' :
                   task.progress?.progress > 0 ? `${Math.round(task.progress.progress)}%` :
                   isRunning ? '运行中...' : ''}
                </span>
              </div>
              <div className="h-2 bg-secondary rounded-full overflow-hidden">
                {isRunning && (!task.progress?.progress || task.progress.progress <= 0) ? (
                  /* Indeterminate shimmer animation when no progress % */
                  <div
                    className="h-full w-1/3 rounded-full bg-gradient-to-r from-transparent via-primary to-transparent"
                    style={{
                      animation: 'shimmer 1.5s ease-in-out infinite',
                    }}
                  />
                ) : (
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      task.status === 'completed' ? 'bg-green-500' :
                      task.status === 'failed' ? 'bg-red-500' :
                      'bg-primary'
                    }`}
                    style={{
                      width: task.status === 'completed' ? '100%' :
                             task.status === 'failed' ? '100%' :
                             task.progress?.progress > 0 ? `${task.progress.progress}%` :
                             '0%',
                    }}
                  />
                )}
              </div>
            </div>

            {/* Task info */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-muted-foreground">
              <div>任务 ID: <span className="font-mono text-foreground">{task.taskId}</span></div>
              <div>开始时间: {new Date(task.createdAt).toLocaleTimeString()}</div>
              <div>因子源: {task.config?.factorSource === 'kelly_jkp' ? 'WRDS Kelly 153' : (task.config?.factorJson || selectedLibrary)}</div>
              <div>方向: {task.config?.portfolioMode || portfolioMode} · 模型: {(task.config?.model || task.config?.kellyModel || kellyModel).toUpperCase()}</div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {isFinished && task?.status === 'completed' && Object.keys(metrics).length > 0 && (
        <Card className="glass card-hover animate-fade-in-up">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-green-500" />
                回测结果
              </div>
              {metrics.__num_factors != null && (
                <span className="text-xs text-muted-foreground font-normal">
                  {metrics.__num_factors} 个因子 · 模型 {(metrics.model || metrics.model_type || task?.config?.model || 'lightgbm').toUpperCase()} · 训练耗时 {metrics.training_seconds != null ? `${Math.round(metrics.training_seconds)}s` : '--'} · 总耗时 {metrics.__elapsed_seconds != null ? `${Math.round(metrics.__elapsed_seconds)}s` : '--'}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {metrics.correlation_pruning?.enabled && (
              <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
                <span className="font-medium">相关性去冗余：</span>
                验证集月末 Spearman 阈值 |ρ| ≥ {Number(metrics.correlation_pruning.threshold).toFixed(2)}，
                因子数 {metrics.correlation_pruning.before_count} → {metrics.correlation_pruning.after_count}，
                归并 {metrics.correlation_pruning.removed_count} 个；测试集未参与筛选。
              </div>
            )}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard label="IC" value={metrics.IC || metrics.ic} />
              <MetricCard label="ICIR" value={metrics.ICIR || metrics.icir} />
              <MetricCard label="Rank IC" value={metrics['Rank IC'] || metrics.RankIC || metrics.rankIc} />
              <MetricCard label="Rank ICIR" value={metrics['Rank ICIR'] || metrics.RankICIR || metrics.rankIcir} />
              <MetricCard
                label="年化扣费收益"
                value={metrics.annualized_return != null ? (metrics.annualized_return * 100) : undefined}
                unit="%"
              />
              <MetricCard
                label="最大回撤"
                value={metrics.max_drawdown != null ? (metrics.max_drawdown * 100) : undefined}
                unit="%"
              />
              <MetricCard label="Sharpe" value={metrics.sharpe_ratio} />
              <MetricCard
                label={isKellyResult ? "月均换手" : "日均换手"}
                value={metrics.average_daily_turnover != null ? metrics.average_daily_turnover * 100 : undefined}
                unit="%"
              />
            </div>

            {metrics.portfolio_analytics && (
              <div className="pt-4 border-t border-border/50 space-y-4">
                <h4 className="text-sm font-medium">Long / Short / Long–Short 明细（均已扣换手成本）</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-muted-foreground border-b border-border/50">
                      <tr>
                        <th className="text-left py-2 pr-4">组合</th>
                        <th className="text-right py-2 px-2">年化毛收益</th>
                        <th className="text-right py-2 px-2">年化净收益</th>
                        <th className="text-right py-2 px-2">Sharpe</th>
                        <th className="text-right py-2 px-2">最大回撤</th>
                        <th className="text-right py-2 px-2">{isKellyResult ? '月均换手' : '日均换手'}</th>
                        <th className="text-right py-2 px-2">累计交易成本</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(['long', 'short', 'long_short'] as const).map(name => {
                        const row = metrics.portfolio_analytics[name];
                        if (!row) return null;
                        const label = name === 'long_short' ? 'Long–Short' : name[0].toUpperCase() + name.slice(1);
                        return (
                          <tr key={name} className="border-b border-border/30">
                            <td className="py-2 pr-4 font-medium">{label}</td>
                            <td className="text-right py-2 px-2">{(row.annualized_gross_return * 100).toFixed(2)}%</td>
                            <td className="text-right py-2 px-2">{(row.annualized_net_return * 100).toFixed(2)}%</td>
                            <td className="text-right py-2 px-2">{row.sharpe_ratio.toFixed(3)}</td>
                            <td className="text-right py-2 px-2">{(row.max_drawdown * 100).toFixed(2)}%</td>
                            <td className="text-right py-2 px-2">{(row.average_daily_turnover * 100).toFixed(2)}%</td>
                            <td className="text-right py-2 px-2">{(row.total_transaction_cost * 100).toFixed(2)}%</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <MultiStrategyReturnChart analytics={metrics.portfolio_analytics} />
                <p className="text-xs text-muted-foreground">
                  换手为每次调仓时权重变化绝对值之和；Long–Short 使用50%多头和50%空头，总敞口100%。当前未计借券费和滑点。
                </p>
              </div>
            )}

            {metrics.decile_analytics && (
              <div className="pt-4 border-t border-border/50 space-y-3">
                <h4 className="text-sm font-medium flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-primary" />
                  十分组累计净收益
                </h4>
                <p className="text-xs text-muted-foreground">
                  每个{isKellyResult ? '月' : '交易日'}按模型预测值排序并等量分成10组；第1组分数最低，第10组分数最高。各组等权并扣除5 bps换手成本。
                </p>
                <DecileReturnChart analytics={metrics.decile_analytics} />
              </div>
            )}

            {/* Cumulative Excess Return Chart */}
            {metrics.cumulative_curve && (
              <div className="pt-4 border-t border-border/50">
                <h4 className="text-sm font-medium mb-4 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-primary" />
                  当前所选方向累计净收益曲线
                </h4>
                <CumulativeReturnChart data={metrics.cumulative_curve} />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Logs Panel */}
      {(logs.length > 0 || isRunning) && (
        <Card className="glass card-hover">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                运行日志
              </span>
              <span className="text-xs text-muted-foreground font-normal">
                {logs.length} 条日志
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="bg-black/50 rounded-lg p-4 max-h-[400px] overflow-y-auto font-mono text-xs">
              {logs.length === 0 && isRunning && (
                <div className="text-muted-foreground flex items-center gap-2">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  等待日志输出...
                </div>
              )}
              {logs.map((log) => (
                <div key={log.id} className="py-0.5 flex gap-2">
                  <span className="text-muted-foreground whitespace-nowrap">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span
                    className={
                      log.level === 'error' ? 'text-red-400' :
                      log.level === 'warning' ? 'text-yellow-400' :
                      log.level === 'success' ? 'text-green-400' :
                      'text-gray-300'
                    }
                  >
                    {log.message}
                  </span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
