import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/context/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { FactorRadarChart } from '@/components/FactorRadarChart';
import { Factor, FactorQuality } from '@/types';
import { formatNumber, getQualityBadgeClass } from '@/utils';
import { OPEN_LIBRARY_EVENT, type OpenLibraryDetail } from '@/utils/libraryNavigation';
import { getFactors, deleteFactors, getFactorCorrelation, FactorCorrelationResponse } from '@/services/api';
import { factorPageUrl, type MarketMode } from '@/utils/factorPage';
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
  ExternalLink,
} from 'lucide-react';

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
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [libraries, setLibraries] = useState<string[]>([]);
  const [selectedLibrary, setSelectedLibrary] = useState<string>('');
  const [metadata, setMetadata] = useState<any>(null);
  const [selectedFactorIds, setSelectedFactorIds] = useState<Set<string>>(new Set());
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

  // Another page (Run History) asks to show a specific run's library.
  useEffect(() => {
    const open = (event: Event) => {
      const { file, marketMode: mode, market: scope } = (event as CustomEvent<OpenLibraryDetail>).detail;
      if (mode) setMarketMode(mode);
      if (scope) setMarket(scope as typeof market);
      setSelectedLibrary(file);
    };
    window.addEventListener(OPEN_LIBRARY_EVENT, open);
    return () => window.removeEventListener(OPEN_LIBRARY_EVENT, open);
  }, []);

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
  }, [selectedLibrary, marketMode, market, language]);

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

  // Each factor has its own page (factor.html); open it beside the library.
  const factorHref = (factor: Factor) => factorPageUrl({
    id: factor.factorId,
    library: factor.sourceLibrary || (selectedLibrary && selectedLibrary !== '__all__' ? selectedLibrary : undefined),
    marketMode: (factor as Factor & { marketMode?: MarketMode }).marketMode || marketMode,
  });

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

      {/* Factor radar: selected factors, or the top 5 of the current sort */}
      {filteredFactors.length > 0 && (
        <FactorRadarChart
          title={selectedFactorIds.size > 0 ? '已选因子表现雷达图' : '当前排序 Top 5 因子表现雷达图'}
          factors={filteredFactors.map((factor, index) => ({ factor, rank: index + 1 }))
            .filter(({ factor }, index) => (selectedFactorIds.size > 0 ? selectedFactorIds.has(factor.factorId) : index < 5))
            .map(({ factor, rank }) => {
            const extra = factor as Factor & { annualReturn?: number | null; maxDrawdown?: number | null };
            return {
              name: factor.factorName,
              label: `#${rank}`,
              ic: factor.ic,
              rankIc: factor.rankIc,
              icir: factor.icir,
              annualReturn: extra.annualReturn,
              maxDrawdown: extra.maxDrawdown,
            };
          })}
          maxFactors={8}
          market={(filteredFactors[0] as Factor & { market?: string }).market}
        />
      )}

      {/* Factor List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filteredFactors.map((factor, index) => (
          <Card
            key={factor.factorId}
            className="glass card-hover cursor-pointer"
            onClick={() => window.open(factorHref(factor), '_blank', 'noopener')}
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
                    <a
                      href={factorHref(factor)}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(event) => event.stopPropagation()}
                      className="inline-flex items-center gap-1 hover:text-primary hover:underline"
                    >
                      {factor.factorName}
                      <ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    </a>
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

    </div>
  );
};
