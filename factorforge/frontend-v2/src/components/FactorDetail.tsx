import React, { useEffect, useRef, useState } from 'react';
import { useLanguage } from '@/context/LanguageContext';
import { CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { formatNumber, getQualityBadgeClass } from '@/utils';
import type { MarketMode } from '@/utils/factorPage';
import { getFactorDetail, getFactorSplitEvaluation, EvaluationSplit, listTasks } from '@/services/api';
import { RefreshCw } from 'lucide-react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

interface FactorDetailProps {
  factorId: string;
  /** Library file holding the factor; undefined searches every library. */
  library?: string;
  /** Market of the surrounding view, for factors that do not record their own. */
  marketMode: MarketMode;
  /** Called with the full detail once it has loaded. */
  onLoaded?: (factor: any) => void;
}

function splitResultsOf(factor: any): Record<string, any> {
  return { ...(factor?.split_results || {}), ...(factor?.splitResults || {}) };
}

function firstCurveFrequency(evaluation: any): string {
  return Object.keys(evaluation?.decileCurves || evaluation?.decile_curves || {})[0] || '';
}

/**
 * Everything known about one factor: description, LLM explanation, the round
 * feedback that produced it, quality score, and train/valid/test statistics
 * with decile curves. Rendered by factor.html, which every factor link opens.
 */
export const FactorDetail: React.FC<FactorDetailProps> = ({
  factorId,
  library,
  marketMode,
  onLoaded,
}) => {
  const { language } = useLanguage();
  const [factor, setFactor] = useState<any | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [curveFrequency, setCurveFrequency] = useState('');
  const [showBenchmark, setShowBenchmark] = useState(true);
  const [evaluationSplit, setEvaluationSplit] = useState<EvaluationSplit>('test');
  const [splitLoading, setSplitLoading] = useState(false);
  const [splitRefreshRequested, setSplitRefreshRequested] = useState(false);
  const [splitError, setSplitError] = useState<string | null>(null);
  // Read inside the load effect without making it re-run on every parent render.
  const onLoadedRef = useRef(onLoaded);
  onLoadedRef.current = onLoaded;

  const loadSplitEvaluation = async (target: any, split: EvaluationSplit, force = false) => {
    const existing = splitResultsOf(target)[split];
    const factorMarketMode = target.marketMode || target.market_mode || marketMode;
    const needsBenchmark = factorMarketMode === 'us'
      && !(existing?.benchmarkCurve || existing?.benchmark_curve)?.length;
    if (existing && !force && !needsBenchmark) {
      setCurveFrequency(firstCurveFrequency(existing));
      return;
    }
    setSplitLoading(true);
    setSplitError(null);
    try {
      const response = await getFactorSplitEvaluation(factorId, split, library, force);
      if (response.success && response.data?.evaluation) {
        const evaluation = response.data.evaluation;
        setFactor((current: any) => current && {
          ...current,
          splitResults: { ...splitResultsOf(current), [split]: evaluation },
        });
        setCurveFrequency(firstCurveFrequency(evaluation));
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

  useEffect(() => {
    let cancelled = false;
    setFactor(null);
    setLoadError(null);
    setSplitError(null);
    setEvaluationSplit('test');
    setShowBenchmark(true);
    setCurveFrequency('');
    (async () => {
      try {
        const resp = await getFactorDetail(factorId, library);
        if (cancelled) return;
        if (!(resp.success && resp.data?.factor)) {
          setLoadError(resp.error || (language === 'zh' ? '未找到该因子' : 'Factor not found'));
          return;
        }
        const payload = resp.data.factor as any;
        const detail = {
          factorId,
          sourceLibrary: library,
          ...payload,
          splitResults: splitResultsOf(payload),
        };
        setFactor(detail);
        onLoadedRef.current?.(detail);
        const savedTest = detail.splitResults.test;
        if (savedTest) {
          setCurveFrequency(firstCurveFrequency(savedTest));
          const factorMarketMode = detail.marketMode || detail.market_mode || marketMode;
          const benchmark = savedTest.benchmarkCurve || savedTest.benchmark_curve || [];
          if (factorMarketMode === 'us' && !benchmark.length) {
            await loadSplitEvaluation(detail, 'test');
          }
        }
      } catch (error: any) {
        if (!cancelled) setLoadError(error?.message || (language === 'zh' ? '因子详情加载失败' : 'Could not load the factor'));
      }
    })();
    return () => { cancelled = true; };
  }, [factorId, library]);

  const handleRecalculateSplit = async () => {
    if (!factor || splitLoading) return;
    setSplitRefreshRequested(true);
    try {
      await loadSplitEvaluation(factor, evaluationSplit, true);
    } finally {
      setSplitRefreshRequested(false);
    }
  };

  const handleSplitChange = async (split: EvaluationSplit) => {
    if (!factor || splitLoading) return;
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
    await loadSplitEvaluation(factor, split);
  };

  if (!factor) {
    return (
      <CardContent className="p-10 text-center text-sm">
        {loadError
          ? <span className="text-destructive">{loadError}</span>
          : (
            <span className="inline-flex items-center gap-2 text-muted-foreground">
              <RefreshCw className="h-4 w-4 animate-spin" />
              {language === 'zh' ? '正在读取因子…' : 'Loading factor…'}
            </span>
          )}
      </CardContent>
    );
  }

  const selectedFactor = factor;
  return (
    <>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <CardTitle className="text-xl break-words">
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
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loadError && (
          <div className="rounded-lg bg-destructive/5 border border-destructive/20 p-3 text-sm text-destructive">
            {loadError}
          </div>
        )}
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
          const zh = language === 'zh';
          const feedbackFields = [
            [zh ? '本轮观察' : 'Observations', feedback.observations],
            [zh ? '假设评价' : 'Hypothesis evaluation', feedback.hypothesis_evaluation],
            [zh ? '判断依据' : 'Reasoning', feedback.reason],
            [zh ? '下一步假设' : 'Next hypothesis', feedback.new_hypothesis],
          ].filter(([, value]) => value);
          // Stored as a bool by new runs and as the string "True"/"False" by older ones.
          const rawDecision = feedback.decision;
          const decision = rawDecision === undefined || rawDecision === null || rawDecision === ''
            ? null
            : String(rawDecision).toLowerCase() === 'true';
          const textBlock = ([label, value]: unknown[]) => (
            <div key={String(label)}>
              <div className="text-xs font-medium text-foreground mb-1">{String(label)}</div>
              <p className="text-sm leading-6 text-muted-foreground whitespace-pre-wrap">{String(value)}</p>
            </div>
          );
          return (
            <>
              <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
                <h4 className="text-sm font-semibold text-primary mb-3">LLM 因子解释</h4>
                {fields.length ? (
                  <div className="space-y-3">{fields.map(textBlock)}</div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    该历史因子尚未保存独立解释。后续挖掘会把每个因子的经济逻辑、信号含义、统计证据、风险和结论分别写入因子库。
                  </p>
                )}
              </div>
              {feedbackFields.length > 0 && (
                <div className="rounded-xl border border-border/60 bg-background/40 p-4">
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <h4 className="text-sm font-semibold">
                      {zh ? '产生该因子那一轮的 LLM 反馈' : 'LLM feedback on the round that produced this factor'}
                    </h4>
                    {decision !== null && (
                      <Badge variant={decision ? 'success' : 'destructive'}>
                        {decision ? (zh ? '该轮采纳' : 'Round accepted') : (zh ? '该轮未采纳' : 'Round rejected')}
                      </Badge>
                    )}
                  </div>
                  <div className="space-y-3">{feedbackFields.map(textBlock)}</div>
                </div>
              )}
            </>
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
    </>
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
