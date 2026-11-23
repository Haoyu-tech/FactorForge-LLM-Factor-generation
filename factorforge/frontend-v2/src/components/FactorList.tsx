import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { ExternalLink } from 'lucide-react';
import { RealtimeMetrics } from '@/types';
import { formatNumber, formatPercent } from '@/utils';
import { factorPageUrl } from '@/utils/factorPage';

interface FactorListProps { metrics: RealtimeMetrics | null; }
type FactorRow = NonNullable<RealtimeMetrics['top10Factors']>[number];

const frequencyNames: Record<string, string> = { day: '日频', week: '周频', month: '月频' };

const missing = <span className="text-muted-foreground/50">N/A</span>;

export const FactorList: React.FC<FactorListProps> = ({ metrics }) => {
  const truncate = (value: string, max: number) => value && value.length > max ? `${value.slice(0, max)}...` : (value || '');
  const valid = (value: number | null | undefined): value is number =>
    value !== undefined && value !== null && Number.isFinite(value);
  const metric = (value: number | null | undefined, digits = 3) => valid(value) ? formatNumber(value, digits) : missing;
  const percent = (value: number | null | undefined) => valid(value) ? formatPercent(value) : missing;
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
              {metrics?.top10Factors?.length ? metrics.top10Factors.map((factor, index) => {
                // Each factor opens its own page in a new tab; rows from metrics
                // computed before factor ids were recorded have no link.
                const href = factor.factorId
                  ? factorPageUrl({ id: factor.factorId, library: factor.library, marketMode: factor.marketMode })
                  : null;
                const open = () => { if (href) window.open(href, '_blank', 'noopener'); };
                return (
                  <tr
                    key={`${factor.factorName}-${index}`}
                    onClick={open}
                    className={`hover:bg-muted/50 transition-colors border-b border-border/50 last:border-0 ${href ? 'cursor-pointer' : ''}`}
                  >
                    <td className="py-3 px-3 font-medium max-w-[150px] truncate" title={factor.factorName}>
                      {href ? (
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(event) => event.stopPropagation()}
                          className="inline-flex items-center gap-1 text-primary hover:underline"
                        >
                          {truncate(factor.factorName, 17)}
                          <ExternalLink className="h-3 w-3 shrink-0" />
                        </a>
                      ) : truncate(factor.factorName, 17)}
                    </td>
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
                );
              }) : <tr><td colSpan={10} className="py-8 text-center text-muted-foreground">暂无因子数据</td></tr>}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};
