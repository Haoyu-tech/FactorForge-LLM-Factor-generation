import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/context/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Factor, FactorQuality } from '@/types';
import { formatNumber, getQualityBadgeClass } from '@/utils';
import { getFactors, getFactorDetail, getFactorSplitEvaluation, EvaluationSplit, deleteFactors, getFactorCorrelation, FactorCorrelationResponse, listTasks } from '@/services/api';
import {
  Database,
  Search,
  Download,
  RefreshCw,
  TrendingUp,
  Code,
  Calendar,
  BarChart3,
  AlertCircle,
  Trash2,
} from 'lucide-react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export const FactorLibraryPage: React.FC = () => {
  const { language } = useLanguage();
  const savedMarket = (() => {
    try { return JSON.parse(localStorage.getItem('quantaalpha_config') || '{}'); }
    catch { return {}; }
  })();
  const [marketMode, setMarketMode] = useState<'us' | 'cn' | 'crypto'>(savedMarket.marketMode === 'crypto' ? 'crypto' : (savedMarket.marketMode === 'cn' ? 'cn' : 'us'));
  const [market, setMarket] = useState<'sp500' | 'csi300' | 'csi500' | 'sme_composite' | 'binance_usdm'>(
    savedMarket.marketMode === 'crypto' ? 'binance_usdm' : savedMarket.marketMode === 'cn' && ['csi300', 'csi500', 'sme_composite'].includes(savedMarket.defaultMarket)
      ? savedMarket.defaultMarket
      : 'sp500'
  );
  const [factors, setFactors] = useState<Factor[]>([]);
  const [filteredFactors, setFilteredFactors] = useState<Factor[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [qualityFilter, setQualityFilter] = useState<FactorQuality | 'all'>('all');
  const [sortBy, setSortBy] = useState<'score_desc' | 'score_asc' | 'newest' | 'rank_ic' | 'ic'>('score_desc');
  const [selectedFactor, setSelectedFactor] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [libraries, setLibraries] = useState<string[]>([]);
  const [selectedLibrary, setSelectedLibrary] = useState<string>('');
  const [metadata, setMetadata] = useState<any>(null);
  const [selectedFactorIds, setSelectedFactorIds] = useState<Set<string>>(new Set());
  const [curveFrequency, setCurveFrequency] = useState('');
  const [showBenchmark, setShowBenchmark] = useState(true);
  const [evaluationSplit, setEvaluationSplit] = useState<EvaluationSplit>('test');
  const [splitLoading, setSplitLoading] = useState(false);
  const [splitRefreshRequested, setSplitRefreshRequested] = useState(false);
  const [splitError, setSplitError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [correlationMethod, setCorrelationMethod] = useState<'spearman' | 'pearson'>('spearman');
  const [correlationLimit, setCorrelationLimit] = useState(10);
  const [correlationData, setCorrelationData] = useState<FactorCorrelationResponse | null>(null);
  const [correlationLoading, setCorrelationLoading] = useState(false);
  const [correlationError, setCorrelationError] = useState<string | null>(null);
  const [correlationExpanded, setCorrelationExpanded] = useState(true);

  useEffect(() => {
    setSelectedFactorIds(new Set());
    setCorrelationData(null);
    setCorrelationError(null);
    loadFactors();
  }, [selectedLibrary, marketMode, market]);

  useEffect(() => {
    filterFactors();
  }, [factors, searchQuery, qualityFilter, sortBy]);

  const loadFactors = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await getFactors({
        library: selectedLibrary || undefined,
        marketMode,
        market,
        limit: 5000,
      });
      if (resp.success && resp.data) {
        const apiFactors: Factor[] = resp.data.factors.map((f: any) => {
          const bt = f.backtestResults || {};
          return {
            factorId: f.factorId || '',
            factorName: f.factorName || 'Unknown',
            factorExpression: f.factorExpression || '',
            factorDescription: f.factorDescription || '',
            quality: (f.quality || 'low') as FactorQuality,
            qualityScore: f.qualityScore ?? 0,
            qualityAssessment: f.qualityAssessment,
            // Prioritize specific metrics from backtest results to match detail view
            ic: (typeof bt['IC'] === 'number' ? bt['IC'] : (f.ic || bt['1day.excess_return_without_cost.information_coefficient'] || 0)),
            icir: (typeof bt['ICIR'] === 'number' ? bt['ICIR'] : (f.icir || bt['1day.excess_return_without_cost.information_coefficient_ir'] || 0)),
            rankIc: (typeof bt['Rank IC'] === 'number' ? bt['Rank IC'] : (f.rankIc || bt['rank_ic'] || bt['1day.excess_return_without_cost.rank_ic'] || 0)),
            rankIcir: (typeof bt['Rank ICIR'] === 'number' ? bt['Rank ICIR'] : (f.rankIcir || bt['rank_ic_ir'] || bt['1day.excess_return_without_cost.rank_ic_ir'] || 0)),
            round: f.round || 0,
            direction: String(f.direction ?? ''),
            createdAt: f.createdAt || new Date().toISOString(),
            // Extra fields from API
            backtestResults: f.backtestResults,
            factorFormulation: f.factorFormulation,
            annualReturn: f.annualReturn,
            maxDrawdown: f.maxDrawdown,
            sharpeRatio: f.sharpeRatio,
            sourceLibrary: f.sourceLibrary,
            marketMode: f.marketMode,
            market: f.market,
            splitResults: f.splitResults || f.split_results || {},
          };
        });
        setFactors(apiFactors);
        setLibraries(resp.data.libraries || []);
        setMetadata(resp.data.metadata || null);
      }
    } catch (err: any) {
      console.error('Failed to load factors from API:', err);
      setError(err?.message || (language === 'zh'
        ? '因子库加载失败，请刷新后重试。'
        : 'Failed to load factor libraries. Refresh and try again.'));
      // Never mix demo factors into a real research library.
      loadMockFactors();
    } finally {
      setIsLoading(false);
    }
  }, [selectedLibrary, marketMode, market]);

  const changeMarketMode = (next: 'us' | 'cn' | 'crypto') => {
    setMarketMode(next);
    setMarket(next === 'crypto' ? 'binance_usdm' : (next === 'cn' ? 'csi300' : 'sp500'));
    setSelectedLibrary('');
  };

  const changeMarket = (next: 'csi300' | 'csi500' | 'sme_composite') => {
    setMarket(next);
    setSelectedLibrary('');
  };

  const loadMockFactors = () => {
    setFactors([]);
    setLibraries([]);
    setMetadata(null);
  };

  const filterFactors = () => {
    let filtered = [...factors];
    if (qualityFilter !== 'all') {
      filtered = filtered.filter((f) => f.quality === qualityFilter);
    }
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (f) =>
          f.factorName.toLowerCase().includes(query) ||
          f.factorExpression.toLowerCase().includes(query) ||
          f.factorDescription.toLowerCase().includes(query)
      );
    }
    const finite = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? value : 0;
    filtered.sort((a, b) => {
      if (sortBy === 'score_asc') return finite(a.qualityScore) - finite(b.qualityScore);
      if (sortBy === 'newest') return new Date(b.createdAt || 0).getTime() - new Date(a.createdAt || 0).getTime();
      if (sortBy === 'rank_ic') return Math.abs(finite(b.rankIc)) - Math.abs(finite(a.rankIc));
      if (sortBy === 'ic') return Math.abs(finite(b.ic)) - Math.abs(finite(a.ic));
      return finite(b.qualityScore) - finite(a.qualityScore);
    });
    setFilteredFactors(filtered);
  };

  const handleExport = () => {
    const dataStr = JSON.stringify(factors, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `factors_${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const loadSplitEvaluation = async (
    factor: any,
    split: EvaluationSplit,
    library?: string,
    force = false,
  ) => {
    const existingResults = {
      ...(factor.split_results || {}),
      ...(factor.splitResults || {}),
    };
    const existing = existingResults[split];
    const factorMarketMode = factor.marketMode || factor.market_mode || marketMode;
    const needsBenchmark = factorMarketMode === 'us'
      && !(existing?.benchmarkCurve || existing?.benchmark_curve)?.length;
    if (existing && !force && !needsBenchmark) {
      const curves = existing.decileCurves || existing.decile_curves || {};
      setCurveFrequency(Object.keys(curves)[0] || '');
      return;
    }
    setSplitLoading(true);
    setSplitError(null);
    try {
      const response = await getFactorSplitEvaluation(
        factor.factorId || factor.factor_id,
        split,
        library,
        force,
      );
      if (response.success && response.data?.evaluation) {
        const evaluation = response.data.evaluation;
        setSelectedFactor((current: any) => {
          if (!current) return current;
          return {
            ...current,
            splitResults: {
              ...(current.split_results || {}),
              ...(current.splitResults || {}),
              [split]: evaluation,
            },
          };
        });
        const curves = evaluation.decileCurves || evaluation.decile_curves || {};
        setCurveFrequency(Object.keys(curves)[0] || '');
      }
    } catch (error: any) {
      const message = String(error?.message || '');
      if (message.includes('404') || message.includes('Not Found')) {
        setSplitError(language === 'zh'
          ? '当前挖掘仍在使用旧版后端。任务结束后系统会自动重载，届时可计算测试集结果。'
          : 'The active mining run is still using the previous backend. The system will reload automatically when it finishes, then test results can be calculated.');
      } else if (message.includes('409') || message.includes('测试集保持锁定')) {
        setSplitError(language === 'zh'
          ? '测试集暂时锁定，防止其进入 LLM 反馈或进化选择；本轮挖掘完成后自动解锁。'
          : 'The test split is locked to keep it out of LLM feedback and evolution selection. It unlocks when mining finishes.');
      } else {
        setSplitError(message || (language === 'zh' ? '该区间统计暂时无法计算' : 'Statistics for this split are temporarily unavailable.'));
      }
    } finally {
      setSplitLoading(false);
    }
  };

  const handleRecalculateSplit = async () => {
    if (!selectedFactor || splitLoading) return;
    const detailLibrary = selectedFactor.sourceLibrary || (selectedLibrary !== '__all__' ? selectedLibrary : undefined);
    setSplitRefreshRequested(true);
    try {
      await loadSplitEvaluation(
        selectedFactor,
        evaluationSplit,
        detailLibrary || undefined,
        true,
      );
    } finally {
      setSplitRefreshRequested(false);
    }
  };

  const handleSelectFactor = async (factor: Factor) => {
    const factorId = factor.factorId;
    setEvaluationSplit('test');
    setShowBenchmark(true);
    setSplitError(null);
    // Open immediately from the list payload. The full detail request enriches
    // the modal afterward and must never block the click interaction.
    setSelectedFactor(factor);
    const listSplitResults = {
      ...((factor as any).split_results || {}),
      ...((factor as any).splitResults || {}),
    };
    const cachedFromList = listSplitResults.test;
    if (cachedFromList) {
      const curves = cachedFromList.decileCurves || cachedFromList.decile_curves || {};
      setCurveFrequency(Object.keys(curves)[0] || '');
    }
    try {
      const detailLibrary = factor.sourceLibrary || (selectedLibrary !== '__all__' ? selectedLibrary : undefined);
      const resp = await getFactorDetail(factor.factorId, detailLibrary || undefined);
      if (resp.success && resp.data?.factor) {
        const detailPayload = resp.data.factor as any;
        const detail = {
          ...factor,
          ...detailPayload,
          splitResults: {
            ...((factor as any).split_results || {}),
            ...((factor as any).splitResults || {}),
            ...(detailPayload.split_results || {}),
            ...(detailPayload.splitResults || {}),
          },
        };
        setSelectedFactor((current: any) => {
          const currentId = current?.factorId || current?.factor_id;
          return currentId === factorId ? { ...current, ...detail } : current;
        });
        const savedTest = detail.splitResults?.test;
        if (savedTest) {
          const curves = savedTest.decileCurves || savedTest.decile_curves || {};
          setCurveFrequency(Object.keys(curves)[0] || '');
          const factorMarketMode = detail.marketMode || detail.market_mode || marketMode;
          const benchmark = savedTest.benchmarkCurve || savedTest.benchmark_curve || [];
          if (factorMarketMode === 'us' && !benchmark.length) {
            await loadSplitEvaluation(detail, 'test', detailLibrary || undefined);
          }
        }
        return;
      }
    } catch (error: any) {
      setSplitError(error?.message || '因子详情加载失败');
    }
  };

  const handleSplitChange = async (split: EvaluationSplit) => {
    if (!selectedFactor || splitLoading) return;
    setEvaluationSplit(split);
    setSplitError(null);
    if (split === 'test') {
      try {
        const taskResponse = await listTasks();
        const miningActive = Boolean(
          taskResponse.success && taskResponse.data?.tasks?.some(
            (task: any) => task.status === 'running' || task.status === 'pending'
          )
        );
        if (miningActive) {
          setSplitError(language === 'zh'
            ? '测试集保持锁定：当前因子挖掘仍在运行。任务完成后将自动重载后端，届时可计算测试集结果。'
            : 'The test split is locked while factor mining is running. It becomes available after the task finishes.');
          return;
        }
      } catch {
        // The API remains the final authority if task status cannot be loaded.
      }
    }
    const detailLibrary = selectedFactor.sourceLibrary || (selectedLibrary !== '__all__' ? selectedLibrary : undefined);
    await loadSplitEvaluation(selectedFactor, split, detailLibrary || undefined);
  };

  const toggleFactorSelection = (factorId: string) => {
    setSelectedFactorIds((current) => {
      const next = new Set(current);
      if (next.has(factorId)) next.delete(factorId);
      else next.add(factorId);
      return next;
    });
  };

  const handleDeleteFactors = async (factorIds: string[]) => {
    if (!factorIds.length) return;
    const scope = selectedLibrary === '__all__' ? '全部历史因子库中的对应记录' : '当前因子库';
    const deletePrompt = language === 'en'
      ? `Delete the selected ${factorIds.length} factors? This will modify ${selectedLibrary === '__all__' ? 'matching records in all historical factor libraries' : 'the current factor library'}.`
      : `确定删除选中的 ${factorIds.length} 个因子吗？此操作会修改${scope}。`;
    if (!confirm(deletePrompt)) return;
    setIsDeleting(true);
    setError(null);
    try {
      const latestSource = factors.find((factor) => factorIds.includes(factor.factorId))?.sourceLibrary;
      await deleteFactors(factorIds, selectedLibrary || latestSource || undefined, { marketMode, market });
      setSelectedFactorIds(new Set());
      setCorrelationData(null);
      if (selectedFactor && factorIds.includes(selectedFactor.factorId || selectedFactor.factor_id)) {
        setSelectedFactor(null);
      }
      await loadFactors();
    } catch (err: any) {
      setError(err?.message || '删除因子失败');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCorrelation = async () => {
    const selected = selectedFactorIds.size >= 2
      ? factors.filter((factor) => selectedFactorIds.has(factor.factorId)).slice(0, 40)
      : filteredFactors.slice(0, correlationLimit);
    if (selected.length < 2) {
      setCorrelationError('至少需要两个有缓存的因子才能计算相关性。');
      return;
    }
    setCorrelationLoading(true);
    setCorrelationError(null);
    try {
      const response = await getFactorCorrelation({
        factorIds: selected.map((factor) => factor.factorId),
        library: selectedLibrary || undefined,
        method: correlationMethod,
      });
      if (response.success && response.data) {
        setCorrelationData(response.data);
        setCorrelationExpanded(true);
      } else {
        setCorrelationError(response.error || '相关性计算失败');
      }
    } catch (err: any) {
      setCorrelationError(err?.message || '相关性计算失败');
    } finally {
      setCorrelationLoading(false);
    }
  };

  const stats = {
    total: factors.length,
    high: factors.filter((f) => f.quality === 'high').length,
    medium: factors.filter((f) => f.quality === 'medium').length,
    low: factors.filter((f) => f.quality === 'low').length,
  };

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Database className="h-8 w-8 text-primary" />
            因子库
          </h1>
          <p className="text-muted-foreground mt-1">
            {language === 'zh'
              ? (marketMode === 'crypto'
                  ? '综合质量评分：预测力、Long–Short Sharpe、收益与回撤、稳定性、换手、手续费和资金费率敏感性'
                  : marketMode === 'cn'
                  ? '综合质量评分：预测力、Long-only 多头 Sharpe、多头收益与回撤、稳定性、Alpha 显著性、换手和成本'
                  : '综合质量评分：预测力、Long–Short 收益与回撤、稳定性、FF Alpha 显著性、换手和成本')
              : (marketMode === 'crypto'
                  ? 'Quality score: predictiveness, long–short Sharpe, return and drawdown, stability, turnover, fees and funding sensitivity'
                  : marketMode === 'cn'
                  ? 'Quality score: predictiveness, long-only Sharpe, long return and drawdown, stability, alpha significance, turnover and costs'
                  : 'Quality score: predictiveness, long–short return and drawdown, stability, FF alpha significance, turnover and costs')}
            {metadata?.total_factors != null && (
              <span className="ml-2 text-xs">
                (更新于 {metadata.last_updated ? new Date(metadata.last_updated).toLocaleString('zh-CN') : '未知'})
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-3">
          <select
            value={marketMode}
            onChange={(event) => changeMarketMode(event.target.value as 'us' | 'cn' | 'crypto')}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm font-medium"
            aria-label={language === 'zh' ? '因子市场' : 'Factor market'}
          >
            <option value="us">{language === 'zh' ? '美股因子库' : 'US factor libraries'}</option>
            <option value="cn">{language === 'zh' ? 'A股因子库' : 'China A-share factor libraries'}</option>
            <option value="crypto">{language === 'zh' ? 'Crypto 永续因子库' : 'Crypto perpetual factor libraries'}</option>
          </select>
          {marketMode === 'cn' && (
            <select
              value={market}
              onChange={(event) => changeMarket(event.target.value as 'csi300' | 'csi500' | 'sme_composite')}
              className="rounded-lg border border-input bg-background px-3 py-2 text-sm font-medium"
              aria-label={language === 'zh' ? 'A股指数成分股' : 'A-share universe'}
            >
              <option value="csi300">{language === 'zh' ? '沪深300成分股' : 'CSI 300 constituents'}</option>
              <option value="csi500">{language === 'zh' ? '中证500成分股' : 'CSI 500 constituents'}</option>
              <option value="sme_composite">{language === 'zh' ? '中小综指成分股' : 'SME Composite constituents'}</option>
            </select>
          )}
          {libraries.length > 1 && (
            <select
              value={selectedLibrary}
              onChange={(e) => setSelectedLibrary(e.target.value)}
              className="rounded-lg border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">{language === 'zh' ? '当前市场最新因子库' : 'Latest library in this market'}</option>
              <option value="__all__">{language === 'zh' ? '当前市场全部历史因子（合并去重）' : 'All history in this market (deduplicated)'}</option>
              {libraries.map((lib) => (
                <option key={lib} value={lib}>{lib}</option>
              ))}
            </select>
          )}
          <Button variant="outline" onClick={loadFactors} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
          <Button variant="primary" onClick={handleExport}>
            <Download className="h-4 w-4 mr-2" />
            导出
          </Button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="glass rounded-lg p-4 flex items-center gap-3 bg-warning/10 border-warning/50">
          <AlertCircle className="h-5 w-5 text-warning flex-shrink-0" />
          <span className="text-sm text-warning">{error}</span>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="glass card-hover">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-muted-foreground">总因子数</div>
                <div className="text-2xl font-bold mt-1">{stats.total}</div>
              </div>
              <div className="p-3 rounded-lg bg-primary/20">
                <BarChart3 className="h-6 w-6 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass card-hover">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-muted-foreground">高质量</div>
                <div className="text-2xl font-bold mt-1 text-success">{stats.high}</div>
              </div>
              <div className="p-3 rounded-lg bg-success/20">
                <TrendingUp className="h-6 w-6 text-success" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass card-hover">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-muted-foreground">中等质量</div>
                <div className="text-2xl font-bold mt-1 text-warning">{stats.medium}</div>
              </div>
              <div className="p-3 rounded-lg bg-warning/20">
                <BarChart3 className="h-6 w-6 text-warning" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass card-hover">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-muted-foreground">低质量</div>
                <div className="text-2xl font-bold mt-1 text-destructive">{stats.low}</div>
              </div>
              <div className="p-3 rounded-lg bg-destructive/20">
                <BarChart3 className="h-6 w-6 text-destructive" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="glass">
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索因子名称、表达式或描述..."
                  className="w-full pl-10 pr-4 py-2 rounded-lg border border-input bg-background text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                />
              </div>
            </div>
            <select
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value as typeof sortBy)}
              className="rounded-lg border border-input bg-background px-3 py-2 text-sm"
              aria-label="因子排序方式"
            >
              <option value="score_desc">综合分：高到低</option>
              <option value="score_asc">综合分：低到高</option>
              <option value="newest">挖掘时间：新到旧</option>
              <option value="rank_ic">|RankIC|：高到低</option>
              <option value="ic">|IC|：高到低</option>
            </select>
            <div className="flex gap-2">
              <Button
                variant={qualityFilter === 'all' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => setQualityFilter('all')}
              >
                {language === 'zh' ? '全部' : 'All'} ({stats.total})
              </Button>
              <Button
                variant={qualityFilter === 'high' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => setQualityFilter('high')}
              >
                {language === 'zh' ? '高质量' : 'High Quality'} ({stats.high})
              </Button>
              <Button
                variant={qualityFilter === 'medium' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => setQualityFilter('medium')}
              >
                {language === 'zh' ? '中等' : 'Medium'} ({stats.medium})
              </Button>
              <Button
                variant={qualityFilter === 'low' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => setQualityFilter('low')}
              >
                {language === 'zh' ? '低质量' : 'Low Quality'} ({stats.low})
              </Button>
            </div>
          </div>
          <details className="mt-3 pt-3 border-t border-border/50">
            <summary className="cursor-pointer select-none text-sm font-medium text-muted-foreground">
              批量选择与删除 · 已选 {selectedFactorIds.size} 个
            </summary>
            <div className="flex flex-wrap items-center gap-2 mt-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedFactorIds(
                selectedFactorIds.size === filteredFactors.length
                  ? new Set()
                  : new Set(filteredFactors.map((factor) => factor.factorId))
              )}
              disabled={!filteredFactors.length}
            >
              {selectedFactorIds.size === filteredFactors.length && filteredFactors.length ? '取消全选' : '全选当前结果'}
            </Button>
            <span className="text-xs text-muted-foreground">已选 {selectedFactorIds.size} 个</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleDeleteFactors(Array.from(selectedFactorIds))}
              disabled={!selectedFactorIds.size || isDeleting}
              className="text-destructive border-destructive/40 hover:bg-destructive/10"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              {isDeleting ? '删除中...' : '删除所选'}
            </Button>
            {selectedLibrary === '__all__' && (
              <span className="text-xs text-muted-foreground">全部历史模式删除时，会从所有历史因子库移除对应因子</span>
            )}
            </div>
          </details>
        </CardContent>
      </Card>

      {/* Factor Correlation Heatmap */}
      <Card className="glass">
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary" />
              因子相关性热力图
            </CardTitle>
            <div className="flex gap-2">
              {correlationData && (
                <Button variant="outline" size="sm" onClick={() => setCorrelationData(null)}>
                  清空结果
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => setCorrelationExpanded((value) => !value)}>
                {correlationExpanded ? '收起' : '展开'}
              </Button>
            </div>
          </div>
        </CardHeader>
        {correlationExpanded && <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs text-muted-foreground mb-1">相关系数</label>
              <select
                value={correlationMethod}
                onChange={(event) => setCorrelationMethod(event.target.value as 'spearman' | 'pearson')}
                className="rounded-lg border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="spearman">Spearman（推荐）</option>
                <option value="pearson">Pearson</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">未勾选时取当前排序前N个</label>
              <select
                value={correlationLimit}
                onChange={(event) => setCorrelationLimit(Number(event.target.value))}
                className="rounded-lg border border-input bg-background px-3 py-2 text-sm"
              >
                {[10, 20, 30, 40].map((value) => <option key={value} value={value}>{value}个因子</option>)}
              </select>
            </div>
            <Button onClick={handleCorrelation} disabled={correlationLoading || filteredFactors.length < 2}>
              <RefreshCw className={`h-4 w-4 mr-2 ${correlationLoading ? 'animate-spin' : ''}`} />
              {correlationLoading ? '正在读取真实因子值...' : selectedFactorIds.size >= 2 ? `计算已选${Math.min(selectedFactorIds.size, 40)}个` : '计算热力图'}
            </Button>
            <div className="text-xs text-muted-foreground">
              每月取月末因子值，计算当月股票横截面相关系数，再对月份取平均。
            </div>
          </div>

          {correlationError && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {correlationError}
            </div>
          )}

          {correlationData && (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span>{correlationData.method === 'spearman' ? 'Spearman' : 'Pearson'}</span>
                <span>{correlationData.startDate} ～ {correlationData.endDate}</span>
                <span>{correlationData.evaluatedMonths}个月</span>
                <span>{correlationData.factors.length}个可用因子</span>
                {correlationData.cacheHit && <span>已使用缓存结果</span>}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-1 text-xs">
                {correlationData.factors.map((factor, index) => (
                  <div key={factor.factorId} className="truncate text-muted-foreground" title={factor.factorName}>
                    <span className="font-mono text-foreground mr-1">#{index + 1}</span>{factor.factorName}
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>-1</span>
                <div className="h-3 w-40 rounded" style={{ background: 'linear-gradient(90deg, #2563eb, #f8fafc, #dc2626)' }} />
                <span>+1</span>
              </div>
              <div className="overflow-auto rounded-lg border border-border/60 max-h-[720px]">
                <table className="border-collapse text-[11px]">
                  <thead className="sticky top-0 z-20 bg-background">
                    <tr>
                      <th className="sticky left-0 z-30 bg-background min-w-[210px] px-2 py-2 text-left">因子</th>
                      {correlationData.factors.map((factor, index) => (
                        <th key={factor.factorId} className="min-w-[52px] px-1 py-2 text-center" title={factor.factorName}>#{index + 1}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {correlationData.factors.map((rowFactor, rowIndex) => (
                      <tr key={rowFactor.factorId}>
                        <th className="sticky left-0 z-10 bg-background max-w-[210px] px-2 py-1.5 text-left font-normal truncate" title={rowFactor.factorName}>
                          <span className="font-mono mr-1">#{rowIndex + 1}</span>{rowFactor.factorName}
                        </th>
                        {correlationData.matrix[rowIndex].map((value, columnIndex) => {
                          const magnitude = value == null ? 0 : Math.min(1, Math.abs(value));
                          const background = value == null
                            ? 'rgba(100,116,139,0.12)'
                            : value >= 0
                              ? `rgba(220,38,38,${0.08 + magnitude * 0.78})`
                              : `rgba(37,99,235,${0.08 + magnitude * 0.78})`;
                          const foreground = value != null && magnitude >= 0.58 ? '#ffffff' : 'inherit';
                          const columnFactor = correlationData.factors[columnIndex];
                          return (
                            <td
                              key={columnFactor.factorId}
                              className="min-w-[52px] h-10 border border-background/50 text-center font-mono"
                              style={{ backgroundColor: background, color: foreground }}
                              title={`${rowFactor.factorName} × ${columnFactor.factorName}: ${value == null ? 'N/A' : value.toFixed(4)}（${correlationData.pairMonths[rowIndex]?.[columnIndex] || 0}个月）`}
                            >
                              {value == null ? '—' : value.toFixed(2)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {correlationData.unavailable.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  {correlationData.unavailable.length} 个因子暂无可用信号缓存，未纳入矩阵。
                </p>
              )}
            </div>
          )}
        </CardContent>}
      </Card>

      {/* Factor List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filteredFactors.map((factor, index) => (
          <Card
            key={factor.factorId}
            className="glass card-hover cursor-pointer"
            onClick={() => handleSelectFactor(factor)}
          >
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-3">
                <input
                  type="checkbox"
                  checked={selectedFactorIds.has(factor.factorId)}
                  onChange={() => toggleFactorSelection(factor.factorId)}
                  onClick={(event) => event.stopPropagation()}
                  className="mt-1 h-5 w-5 rounded border-input text-primary focus:ring-primary"
                  aria-label={`选择因子 ${factor.factorName}`}
                />
                <div className="flex-1">
                  <CardTitle className="text-base flex items-center gap-2">
                    <span className="text-xs text-muted-foreground font-mono">#{index + 1}</span>
                    {factor.factorName}
                  </CardTitle>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge className={getQualityBadgeClass(factor.quality)}>
                      {factor.quality === 'high' ? '高' : factor.quality === 'medium' ? '中' : '低'}
                    </Badge>
                    <span className="text-xs font-medium text-primary">
                      综合分 {formatNumber(factor.qualityScore ?? 0, 1)}
                    </span>
                    {factor.round > 0 && (
                      <span className="text-xs text-muted-foreground">
                        Round {factor.round}
                      </span>
                    )}
                    {factor.direction && (
                      <span className="text-xs text-muted-foreground">
                        方向 {factor.direction}
                      </span>
                    )}
                    {selectedLibrary === '__all__' && factor.sourceLibrary && (
                      <span className="text-xs text-muted-foreground" title={factor.sourceLibrary}>
                        来源 {factor.sourceLibrary.replace('all_factors_library_exp_', '').replace('.json', '')}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground line-clamp-2">
                {factor.factorDescription}
              </p>
              <div className="rounded-lg bg-secondary/30 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Code className="h-3 w-3 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">表达式</span>
                </div>
                <code className="text-xs font-mono line-clamp-2">
                  {factor.factorExpression}
                </code>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-muted-foreground">IC: </span>
                  <span className="font-mono font-medium">{formatNumber(factor.ic, 4)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">RankIC: </span>
                  <span className="font-mono font-medium">{formatNumber(factor.rankIc, 4)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">ICIR: </span>
                  <span className="font-mono font-medium">{formatNumber(factor.icir, 3)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">RankICIR: </span>
                  <span className="font-mono font-medium">{formatNumber(factor.rankIcir, 3)}</span>
                </div>
              </div>
              {factor.createdAt && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Calendar className="h-3 w-3" />
                  {new Date(factor.createdAt).toLocaleString('zh-CN')}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Empty State */}
      {filteredFactors.length === 0 && !isLoading && (
        <Card className="glass">
          <CardContent className="p-12 text-center">
            <Database className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">暂无因子</h3>
            <p className="text-sm text-muted-foreground">
              {searchQuery || qualityFilter !== 'all'
                ? '没有符合筛选条件的因子'
                : '开始挖掘因子后，结果将显示在这里'}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Factor Detail Modal */}
      {selectedFactor && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-6"
          onClick={() => setSelectedFactor(null)}
        >
          <Card
            className="glass-strong max-w-6xl w-full max-h-[86vh] overflow-y-auto animate-scale-in"
            onClick={(e: React.MouseEvent) => e.stopPropagation()}
          >
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <CardTitle className="text-xl">
                    {selectedFactor.factorName || selectedFactor.factor_name}
                  </CardTitle>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge className={getQualityBadgeClass(selectedFactor.quality || 'medium')}>
                      {selectedFactor.quality === 'high'
                        ? '高质量'
                        : selectedFactor.quality === 'medium'
                        ? '中等质量'
                        : '低质量'}
                    </Badge>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() => handleDeleteFactors([selectedFactor.factorId || selectedFactor.factor_id])}
                    disabled={isDeleting}
                    className="text-destructive border-destructive/40"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />删除
                  </Button>
                  <Button variant="ghost" onClick={() => setSelectedFactor(null)}>✕</Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Description */}
              <div>
                <h4 className="text-sm font-medium mb-2">因子描述</h4>
                <p className="text-sm text-muted-foreground">
                  {selectedFactor.factorDescription || selectedFactor.factor_description || '无描述'}
                </p>
              </div>

              {/* Expression */}
              <div>
                <h4 className="text-sm font-medium mb-2">因子表达式</h4>
                <div className="rounded-lg bg-secondary/30 p-4">
                  <code className="text-sm font-mono break-all">
                    {selectedFactor.factorExpression || selectedFactor.factor_expression || ''}
                  </code>
                </div>
              </div>

              {/* Formulation */}
              {(selectedFactor.factorFormulation || selectedFactor.factor_formulation) && (
                <div>
                  <h4 className="text-sm font-medium mb-2">数学公式</h4>
                  <div className="rounded-lg bg-secondary/30 p-4">
                    <code className="text-sm font-mono break-all">
                      {selectedFactor.factorFormulation || selectedFactor.factor_formulation}
                    </code>
                  </div>
                </div>
              )}

              {/* Dedicated LLM explanation */}
              {(() => {
                const explanation = selectedFactor.llmExplanation || selectedFactor.llm_explanation;
                const feedback = selectedFactor.feedback || {};
                const fields = explanation && typeof explanation === 'object'
                  ? [
                      ['经济逻辑', explanation.economic_logic || explanation.economicLogic],
                      ['信号含义', explanation.signal_interpretation || explanation.signalInterpretation],
                      ['统计证据', explanation.statistical_evidence || explanation.statisticalEvidence],
                      ['风险与局限', explanation.risks],
                      ['结论与用法', explanation.conclusion],
                    ].filter(([, value]) => value)
                  : explanation ? [['因子解释', explanation]] : [];
                const legacyFields = fields.length ? [] : [
                  ['本轮观察', feedback.observations],
                  ['假设评价', feedback.hypothesis_evaluation],
                  ['判断依据', feedback.reason],
                ].filter(([, value]) => value);
                const visibleFields = fields.length ? fields : legacyFields;
                return (
                  <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
                    <div className="flex items-center justify-between gap-3 mb-3">
                      <h4 className="text-sm font-semibold text-primary">LLM 因子解释</h4>
                      {!fields.length && legacyFields.length > 0 && (
                        <Badge variant="outline">历史因子 · 本轮综合反馈</Badge>
                      )}
                    </div>
                    {visibleFields.length ? (
                      <div className="space-y-3">
                        {visibleFields.map(([label, value]) => (
                          <div key={String(label)}>
                            <div className="text-xs font-medium text-foreground mb-1">{String(label)}</div>
                            <p className="text-sm leading-6 text-muted-foreground whitespace-pre-wrap">{String(value)}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        该历史因子尚未保存独立解释。后续挖掘会把每个因子的经济逻辑、信号含义、统计证据、风险和结论分别写入因子库。
                      </p>
                    )}
                  </div>
                );
              })()}

              {selectedFactor.qualityAssessment && (
                <div>
                  <h4 className="text-sm font-medium mb-2">
                    {language === 'zh' ? '综合质量评分（验证集筛选口径）：' : 'Composite Quality Score (validation selection): '}{formatNumber(selectedFactor.qualityScore ?? selectedFactor.qualityAssessment.score, 1)}
                    <span className="ml-2 text-xs text-muted-foreground">
                      指标覆盖 {formatNumber((selectedFactor.qualityAssessment.coverage || 0) * 100, 0)}%
                    </span>
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {Object.entries(selectedFactor.qualityAssessment.components || {}).map(([key, raw]: [string, any]) => (
                      <div key={key} className="rounded-lg bg-secondary/30 p-3 flex justify-between gap-3">
                        <span className="text-xs text-muted-foreground">{raw.label}</span>
                        <span className="text-xs font-mono">{formatNumber(raw.score, 1)} / {raw.maxScore}</span>
                      </div>
                    ))}
                  </div>
                  {(selectedFactor.qualityAssessment.reasons || []).length > 0 && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      {(selectedFactor.qualityAssessment.reasons || []).join('；')}
                    </p>
                  )}
                </div>
              )}

              {(() => {
                const splitResults = {
                  ...(selectedFactor.split_results || {}),
                  ...(selectedFactor.splitResults || {}),
                };
                const activeEvaluation = splitResults[evaluationSplit];
                const metadata = selectedFactor.statistics_metadata || {};
                const legacyName = String(metadata.evaluation_split || '').toLowerCase();
                const normalizedLegacy = legacyName === 'validation' ? 'valid' : legacyName;
                const useLegacy = !activeEvaluation && normalizedLegacy === evaluationSplit;
                const metrics = activeEvaluation?.metrics || (useLegacy
                  ? (selectedFactor.backtestResults || selectedFactor.backtest_results || {})
                  : null);
                const allCurves = activeEvaluation?.decileCurves || activeEvaluation?.decile_curves || (useLegacy
                  ? (selectedFactor.decileCurves || selectedFactor.decile_curves || {})
                  : {});
                const window = activeEvaluation
                  ? [activeEvaluation.startDate, activeEvaluation.endDate]
                  : useLegacy ? metadata.evaluation_window : null;
                const frequencies = Object.keys(allCurves);
                const activeFrequency = frequencies.includes(curveFrequency) ? curveFrequency : frequencies[0];
                const benchmarkCurve = activeEvaluation?.benchmarkCurve
                  || activeEvaluation?.benchmark_curve
                  || [];
                const chartData = activeFrequency
                  ? buildDecileChartData(allCurves[activeFrequency] || {}, benchmarkCurve)
                  : [];
                const splitLabels: Record<EvaluationSplit, { zh: string; en: string; hintZh: string; hintEn: string }> = {
                  train: { zh: '训练集', en: 'Train', hintZh: '拟合诊断', hintEn: 'Fit diagnostics' },
                  valid: { zh: '验证集', en: 'Validation', hintZh: '进化筛选依据', hintEn: 'Evolution selection' },
                  test: { zh: '测试集', en: 'Test', hintZh: '最终样本外评价', hintEn: 'Final out-of-sample' },
                };
                return (
                  <div className="space-y-4">
                    <div className="rounded-xl border border-border/60 bg-secondary/10 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex gap-2">
                          {(['train', 'valid', 'test'] as EvaluationSplit[]).map((split) => {
                            const label = splitLabels[split];
                            const available = Boolean(splitResults[split]) || normalizedLegacy === split;
                            return (
                              <Button
                                key={split}
                                size="sm"
                                variant={evaluationSplit === split ? 'primary' : 'outline'}
                                disabled={splitLoading}
                                onClick={() => handleSplitChange(split)}
                              >
                                {language === 'zh' ? label.zh : label.en}
                                <span className="ml-1 text-[10px] opacity-75">
                                  {available
                                    ? (language === 'zh' ? '（已缓存）' : ' (cached)')
                                    : (language === 'zh' ? '（首次计算）' : ' (calculate once)')}
                                </span>
                              </Button>
                            );
                          })}
                        </div>
                        <div className="text-xs text-muted-foreground text-right">
                          <div>{language === 'zh' ? splitLabels[evaluationSplit].hintZh : splitLabels[evaluationSplit].hintEn}</div>
                          {window?.[0] && window?.[1] && <div className="font-mono mt-0.5">{window[0]} ～ {window[1]}</div>}
                          {activeEvaluation?.computedAt && (
                            <div className="mt-1 flex items-center justify-end gap-2">
                              <span>
                                {language === 'zh' ? '已保存：' : 'Saved: '}
                                {new Date(activeEvaluation.computedAt).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-NZ')}
                              </span>
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={splitLoading}
                                onClick={handleRecalculateSplit}
                              >
                                <RefreshCw className={`h-3 w-3 mr-1 ${splitRefreshRequested ? 'animate-spin' : ''}`} />
                                {language === 'zh' ? '重新计算' : 'Recalculate'}
                              </Button>
                            </div>
                          )}
                        </div>
                      </div>
                      <p className="mt-2 text-xs text-muted-foreground">
                        {language === 'zh'
                          ? '验证集用于 LLM 反馈与进化排序；测试集在筛选完成后才解锁。首次计算后会永久保存，之后点击直接读取；只有点“重新计算”才会重跑。'
                          : 'Validation drives LLM feedback and evolution ranking. Test unlocks after selection. The first calculation is saved permanently and later views reuse it; only Recalculate runs it again.'}
                      </p>
                    </div>

                    {splitLoading && (
                      <div className="rounded-lg bg-primary/5 border border-primary/20 p-4 text-sm text-primary flex items-center gap-2">
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        {language === 'zh'
                          ? (splitRefreshRequested ? '正在重新计算该区间…' : '首次计算该区间并写入持久缓存…')
                          : (splitRefreshRequested ? 'Recalculating this split…' : 'Calculating once and saving to persistent cache…')}
                      </div>
                    )}
                    {splitError && !splitLoading && (
                      <div className="rounded-lg bg-destructive/5 border border-destructive/20 p-4 text-sm text-destructive">
                        {splitError}
                      </div>
                    )}

                    {!splitLoading && !metrics && !splitError && (
                      <div className="rounded-lg bg-secondary/30 p-4 text-sm text-muted-foreground">
                        {language === 'zh' ? '该区间尚未保存统计结果，点击区间按钮计算。' : 'No saved statistics for this split. Click the split button to calculate them.'}
                      </div>
                    )}

                    {!splitLoading && metrics && (
                      <>
                        <div>
                          <div className="flex items-center justify-between gap-3 mb-2">
                            <h4 className="text-sm font-medium">
                              {language === 'zh' ? '十组累计收益曲线' : 'Decile Cumulative Return Curves'}
                            </h4>
                            <div className="flex flex-wrap items-center justify-end gap-2">
                              {benchmarkCurve.length > 0 && (
                                <label className="flex cursor-pointer items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1.5 text-xs">
                                  <input
                                    type="checkbox"
                                    checked={showBenchmark}
                                    onChange={(event) => setShowBenchmark(event.target.checked)}
                                  />
                                  {language === 'zh' ? '同期 S&P 500' : 'S&P 500 benchmark'}
                                </label>
                              )}
                              {frequencies.map((frequency) => (
                                <Button
                                  key={frequency}
                                  size="sm"
                                  variant={activeFrequency === frequency ? 'primary' : 'outline'}
                                  onClick={() => setCurveFrequency(frequency)}
                                >
                                  {language === 'zh'
                                    ? (frequency === 'day' ? '日频' : frequency === 'week' ? '周频' : '月频')
                                    : (frequency === 'day' ? 'Daily' : frequency === 'week' ? 'Weekly' : 'Monthly')}
                                </Button>
                              ))}
                            </div>
                          </div>
                          {chartData.length ? (
                            <div className="h-80 rounded-lg bg-secondary/20 p-2">
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={chartData}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="#64748b33" />
                                  <XAxis dataKey="date" minTickGap={40} tick={{ fontSize: 10 }} />
                                  <YAxis tickFormatter={(value) => `${(Number(value) * 100).toFixed(0)}%`} tick={{ fontSize: 10 }} />
                                  <Tooltip formatter={(value: number) => `${(value * 100).toFixed(2)}%`} />
                                  <Legend />
                                  {DECILE_COLORS.map((color, index) => (
                                    <Line
                                      key={`group_${index + 1}`}
                                      type="monotone"
                                      dataKey={`group_${index + 1}`}
                                      name={language === 'zh' ? `第${index + 1}组` : `Decile ${index + 1}`}
                                      stroke={color}
                                      dot={false}
                                      strokeWidth={index === 0 || index === 9 ? 2.5 : 1.3}
                                      connectNulls
                                    />
                                  ))}
                                  {showBenchmark && benchmarkCurve.length > 0 && (
                                    <Line
                                      type="monotone"
                                      dataKey="benchmark"
                                      name={language === 'zh' ? '同期 S&P 500' : 'S&P 500 benchmark'}
                                      stroke="#111827"
                                      strokeDasharray="7 4"
                                      dot={false}
                                      strokeWidth={2.5}
                                      connectNulls
                                    />
                                  )}
                                </LineChart>
                              </ResponsiveContainer>
                            </div>
                          ) : (
                            <div className="rounded-lg bg-secondary/30 p-4 text-sm text-muted-foreground">
                              {language === 'zh' ? '该区间没有可绘制的十组曲线。' : 'No decile curve is available for this split.'}
                            </div>
                          )}
                        </div>
                        <FactorStatisticsPanel
                          metrics={metrics}
                          marketMode={(selectedFactor.marketMode || selectedFactor.market_mode || marketMode) as 'us' | 'cn' | 'crypto'}
                        />
                      </>
                    )}
                  </div>
                );
              })()}

              {/* Meta */}
              <div>
                <h4 className="text-sm font-medium mb-2">元信息</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">因子ID:</span>
                    <span className="font-mono">
                      {selectedFactor.factorId || selectedFactor.factor_id || ''}
                    </span>
                  </div>
                  {(selectedFactor.createdAt || selectedFactor.added_at) && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">创建时间:</span>
                      <span>
                        {new Date(
                          selectedFactor.createdAt || selectedFactor.added_at
                        ).toLocaleString('zh-CN')}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

type MetricKind = 'percent' | 'number' | 'count';

const FREQUENCY_LABELS: Record<string, string> = { day: '日频', week: '周频', month: '月频' };
const LEG_LABELS: Record<string, string> = { long: 'Long 多头', short: 'Short 空头', long_short: 'Long–Short' };
const PORTFOLIO_METRICS: Array<{ key: string; label: string; kind: MetricKind }> = [
  { key: 'annualized_gross_return', label: '年化毛收益', kind: 'percent' },
  { key: 'annualized_net_return', label: '年化净收益', kind: 'percent' },
  { key: 'sharpe_ratio', label: 'Sharpe', kind: 'number' },
  { key: 'max_drawdown', label: '最大回撤', kind: 'percent' },
  { key: 'average_turnover_per_rebalance', label: '单次调仓平均换手', kind: 'percent' },
  { key: 'annualized_turnover', label: '年化换手', kind: 'percent' },
  { key: 'total_transaction_cost', label: '累计交易成本', kind: 'percent' },
  { key: 'total_borrow_cost', label: '累计借券成本', kind: 'percent' },
  { key: 'rebalance_count', label: '调仓次数', kind: 'count' },
];

function finiteMetric(value: unknown): number | null {
  const number = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(number) ? number : null;
}

function displayMetric(value: unknown, kind: MetricKind = 'number'): string {
  const number = finiteMetric(value);
  if (number == null) return '—';
  if (kind === 'percent') return `${(number * 100).toFixed(2)}%`;
  if (kind === 'count') return Math.round(number).toLocaleString('zh-CN');
  return number.toFixed(4);
}

function significanceStars(value: unknown): string {
  const pValue = finiteMetric(value);
  if (pValue == null) return '';
  if (pValue < 0.01) return '***';
  if (pValue < 0.05) return '**';
  if (pValue < 0.10) return '*';
  return '';
}

function metricFrequencies(metrics: Record<string, unknown>): string[] {
  return ['day', 'week', 'month'].filter((frequency) =>
    Object.keys(metrics).some((key) => key.startsWith(`${frequency}.`))
  );
}

function rawMetricLabel(key: string): string {
  return key
    .replace(/^day\./, '日频 · ')
    .replace(/^week\./, '周频 · ')
    .replace(/^month\./, '月频 · ')
    .replace(/long_short/g, 'Long–Short')
    .replace(/\.long\./g, ' · Long · ')
    .replace(/\.short\./g, ' · Short · ')
    .replace(/_/g, ' ');
}

const FactorStatisticsPanel: React.FC<{
  metrics: Record<string, unknown>;
  marketMode: 'us' | 'cn' | 'crypto';
}> = ({ metrics, marketMode }) => {
  const frequencies = metricFrequencies(metrics);
  const [frequency, setFrequency] = useState(frequencies[0] || 'day');

  useEffect(() => {
    if (!frequencies.includes(frequency)) setFrequency(frequencies[0] || 'day');
  }, [metrics]);

  const prediction = [
    ['IC', metrics.IC ?? metrics.ic],
    ['ICIR', metrics.ICIR ?? metrics.icir],
    ['RankIC', metrics['Rank IC'] ?? metrics.rank_ic],
    ['RankICIR', metrics['Rank ICIR'] ?? metrics.rank_ic_ir],
  ];
  const decile = [
    ['十组单调性', metrics[`${frequency}.decile_monotonicity`]],
    ['第10组－第1组年化收益', metrics[`${frequency}.decile_top_minus_bottom_annualized_return`]],
  ];
  const models = ['ff3', 'ff3_mom', 'ff5', 'ff5_mom'].map((model) => {
    const prefix = `${frequency}.asset_pricing.${model}.`;
    const values = Object.fromEntries(
      Object.entries(metrics).filter(([key]) => key.startsWith(prefix)).map(([key, value]) => [key.slice(prefix.length), value])
    );
    return { model, values };
  }).filter(({ values }) => Object.keys(values).length > 0);

  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-sm font-semibold mb-2">因子预测统计</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {prediction.map(([label, value]) => (
            <div key={String(label)} className="rounded-lg border border-border/60 bg-secondary/20 p-3">
              <div className="text-xs text-muted-foreground">{String(label)}</div>
              <div className="text-base font-semibold font-mono mt-1">{displayMetric(value)}</div>
            </div>
          ))}
        </div>
      </div>

      {frequencies.length > 0 && (
        <div>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
            <div>
              <h4 className="text-sm font-semibold">
                {marketMode === 'cn' ? 'Long-only 多头为主；Short / Long–Short 诊断' : 'Long / Short / Long–Short 回测'}
              </h4>
              <p className="text-xs text-muted-foreground mt-1">
                {marketMode === 'crypto'
                  ? 'Crypto 使用全市场横截面，多空均计交易成本；资金费率另作敏感性诊断'
                  : marketMode === 'cn'
                  ? 'A 股质量评分与进化排序使用扣费后多头 Sharpe；其他组合腿仅作诊断'
                  : '收益、回撤、换手和成本按组合腿并列展示'}
              </p>
            </div>
            <div className="flex gap-1">
              {frequencies.map((item) => (
                <Button key={item} size="sm" variant={frequency === item ? 'primary' : 'outline'} onClick={() => setFrequency(item)}>
                  {FREQUENCY_LABELS[item] || item}
                </Button>
              ))}
            </div>
          </div>
          <div className="overflow-x-auto rounded-xl border border-border/60">
            <table className="w-full min-w-[660px] text-sm">
              <thead className="bg-secondary/40">
                <tr>
                  <th className="text-left py-3 px-4 font-medium">指标</th>
                  {['long', 'short', 'long_short'].map((leg) => (
                    <th key={leg} className="text-right py-3 px-4 font-medium">{LEG_LABELS[leg]}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {PORTFOLIO_METRICS.map((metric) => (
                  <tr key={metric.key} className="border-t border-border/50">
                    <td className="py-2.5 px-4 text-muted-foreground">{metric.label}</td>
                    {['long', 'short', 'long_short'].map((leg) => (
                      <td key={leg} className="py-2.5 px-4 text-right font-mono font-medium">
                        {displayMetric(metrics[`${frequency}.${leg}.${metric.key}`], metric.kind)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div>
        <h4 className="text-sm font-semibold mb-2">十组检验</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {decile.map(([label, value], index) => (
            <div key={String(label)} className="rounded-lg border border-border/60 bg-secondary/20 p-3 flex justify-between gap-4">
              <span className="text-xs text-muted-foreground">{String(label)}</span>
              <span className="text-sm font-mono font-semibold">{displayMetric(value, index === 1 ? 'percent' : 'number')}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="flex flex-wrap items-end justify-between gap-2 mb-3">
          <div>
            <h4 className="text-base font-semibold">资产定价回归</h4>
            <p className="text-xs text-muted-foreground mt-1">
              {marketMode === 'crypto'
                ? 'Crypto 永续不套用股票 FF 模型；本栏仅在存在适用回归结果时显示'
                : marketMode === 'cn'
                ? '基于该因子的 Long-only 多头净收益，使用 Newey–West 稳健标准误'
                : '基于该因子的 Long–Short 净收益，使用 Newey–West 稳健标准误'}
            </p>
          </div>
          <div className="text-xs text-muted-foreground">
            显著性：<strong>***</strong> p&lt;0.01，<strong>**</strong> p&lt;0.05，<strong>*</strong> p&lt;0.10
          </div>
        </div>

        {models.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {models.map(({ model, values }) => {
              const betaNames = Object.keys(values)
                .filter((key) => key.startsWith('beta_') && !key.endsWith('_t_stat') && !key.endsWith('_p_value'));
              const modelLabel = model === 'ff3'
                ? 'FF3'
                : model === 'ff3_mom'
                ? 'FF3 + Mom'
                : model === 'ff5'
                ? 'FF5'
                : 'FF5 + Mom';
              return (
                <div key={model} className="rounded-xl border border-border/70 overflow-hidden bg-background/30">
                  <div className="bg-secondary/40 px-4 py-3 text-lg font-bold">{modelLabel}</div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-3 px-4 py-4">
                    <div>
                      <div className="text-xs text-muted-foreground">Alpha 年化</div>
                      <div className="font-mono font-semibold mt-1">
                        {displayMetric(values.alpha_annualized, 'percent')}
                        <span className="text-primary ml-0.5">{significanceStars(values.alpha_p_value)}</span>
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Alpha t</div>
                      <div className="font-mono font-semibold mt-1">{displayMetric(values.alpha_t_stat)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Alpha p</div>
                      <div className="font-mono font-semibold mt-1">{displayMetric(values.alpha_p_value)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">R² / Adj.R²</div>
                      <div className="font-mono font-semibold mt-1">
                        {displayMetric(values.r_squared)} / {displayMetric(values.adjusted_r_squared)}
                      </div>
                    </div>
                  </div>

                  {betaNames.length > 0 && (
                    <div className="overflow-x-auto border-t border-border/50">
                      <table className="w-full text-xs">
                        <thead className="bg-secondary/20 text-muted-foreground">
                          <tr>
                            <th className="text-left py-2.5 px-4">Beta</th>
                            <th className="text-right py-2.5 px-3">系数</th>
                            <th className="text-right py-2.5 px-3">t 值</th>
                            <th className="text-right py-2.5 px-4">p 值 / 显著性</th>
                          </tr>
                        </thead>
                        <tbody>
                          {betaNames.map((key) => (
                            <tr key={key} className="border-t border-border/40">
                              <td className="py-2.5 px-4 font-medium">{key.slice(5).toUpperCase()}</td>
                              <td className="py-2.5 px-3 text-right font-mono">{displayMetric(values[key])}</td>
                              <td className="py-2.5 px-3 text-right font-mono">{displayMetric(values[`${key}_t_stat`])}</td>
                              <td className="py-2.5 px-4 text-right font-mono">
                                {displayMetric(values[`${key}_p_value`])}
                                <span className="text-primary font-bold ml-1">
                                  {significanceStars(values[`${key}_p_value`])}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  <div className="flex flex-wrap gap-x-5 gap-y-1 border-t border-border/40 px-4 py-2 text-[11px] text-muted-foreground">
                    <span>样本数：{displayMetric(values.observations, 'count')}</span>
                    <span>Newey–West 滞后：{displayMetric(values.hac_lags, 'count')}</span>
                    <span>残差年化波动：{displayMetric(values.residual_volatility_annualized, 'percent')}</span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border/70 p-5 text-sm text-muted-foreground">
            该历史因子尚未保存资产定价回归；重新运行单因子评价后会生成 FF3、FF3 + Mom、FF5 和 FF5 + Mom 结果。
          </div>
        )}
      </div>

      {Object.keys(metrics).some((key) => key.startsWith('industry.')) && (
        <div>
          <h4 className="text-sm font-semibold mb-2">行业中性与稳健性</h4>
          <div className="overflow-x-auto rounded-xl border border-border/60">
            <table className="w-full min-w-[620px] text-xs">
              <thead className="bg-secondary/30"><tr>
                <th className="text-left py-2.5 px-4">GICS 层级</th>
                <th className="text-right py-2.5 px-3">覆盖率</th>
                <th className="text-right py-2.5 px-3">平均绝对暴露</th>
                <th className="text-right py-2.5 px-3">最大绝对暴露</th>
                <th className="text-right py-2.5 px-3">暴露 HHI</th>
                <th className="text-right py-2.5 px-4">分组数</th>
              </tr></thead>
              <tbody>{['gsector', 'ggroup', 'gind', 'gsubind'].map((level) => (
                <tr key={level} className="border-t border-border/40">
                  <td className="py-2.5 px-4 font-medium">{level}</td>
                  <td className="py-2.5 px-3 text-right font-mono">{displayMetric(metrics[`industry.${level}.coverage`], 'percent')}</td>
                  <td className="py-2.5 px-3 text-right font-mono">{displayMetric(metrics[`industry.${level}.mean_abs_exposure`])}</td>
                  <td className="py-2.5 px-3 text-right font-mono">{displayMetric(metrics[`industry.${level}.max_abs_exposure`])}</td>
                  <td className="py-2.5 px-3 text-right font-mono">{displayMetric(metrics[`industry.${level}.exposure_hhi`])}</td>
                  <td className="py-2.5 px-4 text-right font-mono">{displayMetric(metrics[`industry.${level}.group_count`], 'count')}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
            {[
              ['ggroup RankIC', metrics['industry.ggroup.robustness.Rank IC'], 'number'],
              ['ggroup RankICIR', metrics['industry.ggroup.robustness.Rank ICIR'], 'number'],
              ['ggroup L–S 年化净收益', metrics[`industry.ggroup.robustness.${frequency}.long_short.annualized_net_return`], 'percent'],
              ['ggroup L–S Sharpe', metrics[`industry.ggroup.robustness.${frequency}.long_short.sharpe_ratio`], 'number'],
            ].map(([label, value, kind]) => (
              <div key={String(label)} className="rounded-lg bg-secondary/20 p-3">
                <div className="text-[11px] text-muted-foreground">{String(label)}</div>
                <div className="text-sm font-mono font-semibold mt-1">{displayMetric(value, kind as MetricKind)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <details className="rounded-xl border border-border/60">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium">
          完整原始指标（{Object.keys(metrics).length} 项）
        </summary>
        <div className="max-h-80 overflow-y-auto border-t border-border/50">
          {Object.entries(metrics).map(([key, value]) => (
            <div key={key} className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 px-4 py-2 border-b border-border/30 text-xs">
              <span className="text-muted-foreground break-words" title={key}>{rawMetricLabel(key)}</span>
              <span className="font-mono font-medium">{typeof value === 'number' ? formatNumber(value, 6) : String(value ?? '—')}</span>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
};

const DECILE_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16',
  '#22c55e', '#14b8a6', '#06b6d4', '#3b82f6', '#8b5cf6',
];

function buildDecileChartData(
  curves: Record<string, Array<{ date: string; value: number }>>,
  benchmarkCurve: Array<{ date: string; value: number }> = [],
) {
  const rows = new Map<string, Record<string, string | number>>();
  Object.entries(curves || {}).forEach(([group, points]) => {
    (points || []).forEach((point) => {
      const row = rows.get(point.date) || { date: point.date };
      row[group] = point.value;
      rows.set(point.date, row);
    });
  });
  (benchmarkCurve || []).forEach((point) => {
    const row = rows.get(point.date) || { date: point.date };
    row.benchmark = point.value;
    rows.set(point.date, row);
  });
  return Array.from(rows.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
}
