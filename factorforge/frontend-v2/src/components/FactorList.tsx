import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/HoverCard';
import { RealtimeMetrics } from '@/types';
import { formatNumber, formatPercent } from '@/utils';

interface FactorListProps { metrics: RealtimeMetrics | null; }
type FactorRow = NonNullable<RealtimeMetrics['top10Factors']>[number];

const frequencyNames: Record<string, string> = { day: '日频', week: '周频', month: '月频' };
const modelNames: Record<string, string> = {
  ff3: 'FF3', ff3_mom: 'FF3 + Mom', ff5: 'FF5', ff5_mom: 'FF5 + Mom',
};

const missing = <span className="text-muted-foreground/50">N/A</span>;

export const FactorList: React.FC<FactorListProps> = ({ metrics }) => {
  const truncate = (value: string, max: number) => value && value.length > max ? `${value.slice(0, max)}...` : (value || '');
  const valid = (value: number | null | undefined): value is number =>
    value !== undefined && value !== null && Number.isFinite(value);
  const metric = (value: number | null | undefined, digits = 3) => valid(value) ? formatNumber(value, digits) : missing;
  const percent = (value: number | null | undefined) => valid(value) ? formatPercent(value) : missing;
  const stars = (p: number | null | undefined) => {
    if (!valid(p)) return '';
    if (p < 0.01) return '***';
    if (p < 0.05) return '**';
    if (p < 0.1) return '*';
    return '';
  };
  const leg = (factor: FactorRow, name: 'long' | 'short' | 'long_short') => factor.portfolioStats?.[name];

  return (
    <Card className="glass card-hover animate-fade-in-up w-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-purple-500 animate-pulse" />
          当前因子库 综合质量 Top 10
          {metrics?.top10Factors?.[0]?.frequency && (
            <span className="text-xs font-normal text-muted-foreground">
              （{frequencyNames[metrics.top10Factors[0].frequency!] || metrics.top10Factors[0].frequency}调仓）
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[1120px]">
            <thead>
              <tr className="border-b border-border/50">
                <th className="py-3 px-3 text-left font-medium text-muted-foreground">因子名</th>
                <th className="py-3 px-3 text-left font-medium text-muted-foreground">公式</th>
                <th className="py-3 px-3 text-right font-medium text-muted-foreground">评分</th>
                <th className="py-3 px-3 text-right font-medium text-muted-foreground">IC</th>
                <th className="py-3 px-3 text-right font-medium text-muted-foreground">RankIC</th>
                <th className="py-3 px-3 text-right font-medium text-muted-foreground">Long ARR</th>
                <th className="py-3 px-3 text-right font-medium text-muted-foreground">Short ARR</th>
                <th className="py-3 px-3 text-right font-medium text-primary">L–S ARR</th>
                <th className="py-3 px-3 text-right font-medium text-muted-foreground">L–S Sharpe</th>
                <th className="py-3 px-3 text-right font-medium text-muted-foreground">L–S MDD</th>
              </tr>
            </thead>
            <tbody>
              {metrics?.top10Factors?.length ? metrics.top10Factors.map((factor, index) => (
                <HoverCard key={`${factor.factorName}-${index}`} openDelay={150}>
                  <HoverCardTrigger asChild>
                    <tr className="hover:bg-muted/50 transition-colors border-b border-border/50 last:border-0 cursor-help">
                      <td className="py-3 px-3 font-medium max-w-[150px] truncate" title={factor.factorName}>{truncate(factor.factorName, 17)}</td>
                      <td className="py-3 px-3 font-mono text-xs text-muted-foreground max-w-[220px] truncate" title={factor.factorExpression}>{truncate(factor.factorExpression, 34)}</td>
                      <td className="py-3 px-3 text-right font-mono">{metric(factor.qualityScore, 1)}</td>
                      <td className="py-3 px-3 text-right font-mono">{metric(factor.ic, 4)}</td>
                      <td className="py-3 px-3 text-right font-mono font-bold text-primary">{metric(factor.rankIc, 4)}</td>
                      <td className="py-3 px-3 text-right font-mono">{percent(leg(factor, 'long')?.annualizedNetReturn)}</td>
                      <td className="py-3 px-3 text-right font-mono">{percent(leg(factor, 'short')?.annualizedNetReturn)}</td>
                      <td className="py-3 px-3 text-right font-mono font-bold text-primary">{percent(leg(factor, 'long_short')?.annualizedNetReturn ?? factor.annualReturn)}</td>
                      <td className="py-3 px-3 text-right font-mono">{metric(leg(factor, 'long_short')?.sharpeRatio ?? factor.sharpeRatio, 3)}</td>
                      <td className="py-3 px-3 text-right font-mono text-destructive">{percent(leg(factor, 'long_short')?.maxDrawdown ?? factor.maxDrawdown)}</td>
                    </tr>
                  </HoverCardTrigger>
                  <HoverCardContent className="w-[860px] max-h-[75vh] overflow-y-auto glass-strong p-5 shadow-xl border border-primary/20" side="top" align="center" sideOffset={10} collisionPadding={20}>
                    <div className="space-y-5">
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="font-bold text-primary text-base">{factor.factorName}</h4>
                          <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs border border-primary/20">综合评分 {valid(factor.qualityScore) ? formatNumber(factor.qualityScore, 1) : 'N/A'}</span>
                        </div>
                        <div className="p-3 bg-secondary/40 rounded-lg font-mono text-xs break-all border border-border/50">{factor.factorExpression}</div>
                      </div>

                      <section>
                        <h5 className="font-semibold mb-2">Long / Short / Long–Short 统计</h5>
                        <div className="overflow-x-auto rounded-lg border border-border/50">
                          <table className="w-full text-xs">
                            <thead className="bg-secondary/40"><tr>
                              <th className="p-2 text-left">组合</th><th className="p-2 text-right">毛年化</th><th className="p-2 text-right">净年化</th><th className="p-2 text-right">Sharpe</th><th className="p-2 text-right">最大回撤</th><th className="p-2 text-right">年化换手</th><th className="p-2 text-right">交易成本</th>
                            </tr></thead>
                            <tbody>{(['long', 'short', 'long_short'] as const).map(name => {
                              const row = leg(factor, name);
                              return <tr key={name} className="border-t border-border/40"><td className="p-2 font-medium">{{ long: 'Long', short: 'Short', long_short: 'Long–Short' }[name]}</td><td className="p-2 text-right">{percent(row?.annualizedGrossReturn)}</td><td className="p-2 text-right">{percent(row?.annualizedNetReturn)}</td><td className="p-2 text-right">{metric(row?.sharpeRatio)}</td><td className="p-2 text-right">{percent(row?.maxDrawdown)}</td><td className="p-2 text-right">{percent(row?.turnover)}</td><td className="p-2 text-right">{percent(row?.transactionCost)}</td></tr>;
                            })}</tbody>
                          </table>
                        </div>
                      </section>

                      <section>
                        <h5 className="font-semibold mb-2">GICS 行业检验</h5>
                        {factor.industryStatistics ? <div className="space-y-3">
                          <div className="grid grid-cols-4 gap-2 text-xs">
                            {Object.entries(factor.industryStatistics.levels).map(([level, row]) => <div key={level} className="rounded-lg border border-border/50 p-2">
                              <div className="font-semibold mb-1">{level}</div>
                              <div>覆盖率：{percent(row.coverage)}</div>
                              <div>平均暴露：{metric(row.meanAbsExposure)}</div>
                              <div>最大暴露：{metric(row.maxAbsExposure)}</div>
                              <div>集中度 HHI：{metric(row.exposureHhi)}</div>
                            </div>)}
                          </div>
                          <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs grid grid-cols-4 gap-2">
                            <div><span className="text-muted-foreground block">ggroup RankIC</span>{metric(factor.industryStatistics.ggroupRobustness.rankIc, 4)}</div>
                            <div><span className="text-muted-foreground block">ggroup L–S 年化</span>{percent(factor.industryStatistics.ggroupRobustness.annualizedNetReturn)}</div>
                            <div><span className="text-muted-foreground block">ggroup Sharpe</span>{metric(factor.industryStatistics.ggroupRobustness.sharpeRatio)}</div>
                            <div><span className="text-muted-foreground block">ggroup 十组单调性</span>{metric(factor.industryStatistics.ggroupRobustness.decileMonotonicity)}</div>
                          </div>
                        </div> : <div className="p-3 text-center text-sm text-muted-foreground border rounded-lg">该因子尚无 GICS 行业检验，请重新评估。</div>}
                      </section>

                      <section>
                        <div className="flex items-baseline justify-between mb-2"><h5 className="font-semibold">资产定价回归</h5><span className="text-[11px] text-muted-foreground">显著性：*** p&lt;0.01，** p&lt;0.05，* p&lt;0.10</span></div>
                        {factor.assetPricing && Object.keys(factor.assetPricing).length ? (
                          <div className="grid grid-cols-2 gap-3">{['ff3', 'ff3_mom', 'ff5', 'ff5_mom'].map(model => {
                            const regression = factor.assetPricing?.[model];
                            if (!regression) return null;
                            return <div key={model} className="rounded-lg border border-border/50 overflow-hidden">
                              <div className="px-3 py-2 bg-secondary/50 font-semibold">{modelNames[model]}</div>
                              <div className="grid grid-cols-4 gap-1 p-3 text-xs border-b border-border/40">
                                <div><span className="text-muted-foreground block">Alpha 年化</span>{percent(regression.alphaAnnualized)}{stars(regression.alphaPValue)}</div>
                                <div><span className="text-muted-foreground block">Alpha t</span>{metric(regression.alphaTStat)}</div>
                                <div><span className="text-muted-foreground block">Alpha p</span>{metric(regression.alphaPValue, 4)}</div>
                                <div><span className="text-muted-foreground block">R² / Adj.R²</span>{metric(regression.rSquared)} / {metric(regression.adjustedRSquared)}</div>
                              </div>
                              <table className="w-full text-[11px]"><thead><tr className="text-muted-foreground"><th className="p-1.5 text-left">Beta</th><th className="p-1.5 text-right">系数</th><th className="p-1.5 text-right">t 值</th><th className="p-1.5 text-right">p 值 / 显著性</th></tr></thead><tbody>
                                {Object.entries(regression.betas).map(([name, beta]) => <tr key={name} className="border-t border-border/30"><td className="p-1.5 font-medium">{name}</td><td className="p-1.5 text-right">{metric(beta.value)}</td><td className="p-1.5 text-right">{metric(beta.tStat)}</td><td className="p-1.5 text-right">{metric(beta.pValue, 4)} <span className="text-primary font-bold">{stars(beta.pValue)}</span></td></tr>)}
                              </tbody></table>
                            </div>;
                          })}</div>
                        ) : <div className="p-4 text-center text-sm text-muted-foreground border rounded-lg">该因子尚无 FF 回归结果，请重新评估该因子。</div>}
                      </section>
                    </div>
                  </HoverCardContent>
                </HoverCard>
              )) : <tr><td colSpan={10} className="py-8 text-center text-muted-foreground">暂无因子数据</td></tr>}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};
