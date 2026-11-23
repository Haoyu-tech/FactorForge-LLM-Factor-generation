import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, MessageSquareText } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { useLanguage } from '@/context/LanguageContext';
import { ApiError, getExperimentFeedback } from '@/services/api';
import type { MiningFeedbackReport, RoundFeedback } from '@/services/api';
import { formatNumber, formatPercent } from '@/utils';

interface RoundFeedbackPanelProps {
  /** Run folder name; null when the task does not record one. */
  experimentId: string | null;
  isRunning: boolean;
  marketMode?: string;
}

type DecisionFilter = 'all' | 'accepted' | 'rejected';

// The pool is rewritten once per round, and a round takes minutes.
const POLL_MS = 15000;

export const RoundFeedbackPanel: React.FC<RoundFeedbackPanelProps> = ({ experimentId, isRunning, marketMode }) => {
  const { language } = useLanguage();
  const zh = language === 'zh';
  const [report, setReport] = useState<MiningFeedbackReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<DecisionFilter>('all');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    setReport(null);
    setError(null);
    if (!experimentId) return;
    let cancelled = false;
    const load = async () => {
      try {
        const response = await getExperimentFeedback(experimentId);
        if (cancelled) return;
        if (response.data) setReport(response.data);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        // 409: the backend caught the file mid-write; the next poll will read it.
        if (err instanceof ApiError && err.status === 409) return;
        setError(err instanceof Error ? err.message : String(err));
      }
    };
    load();
    // Runs once more when isRunning turns false, which picks up the final round.
    if (!isRunning) return () => { cancelled = true; };
    const timer = setInterval(load, POLL_MS);
    return () => { cancelled = true; clearInterval(timer); };
  }, [experimentId, isRunning]);

  const rounds = useMemo(() => [...(report?.rounds || [])].reverse(), [report]);
  const acceptedCount = rounds.filter((r) => r.decision === true).length;
  const rejectedCount = rounds.filter((r) => r.decision === false).length;
  const visible = rounds.filter((r) =>
    filter === 'all' || (filter === 'accepted' ? r.decision === true : r.decision === false));
  const legLabel = marketMode === 'cn' ? 'Long' : 'Long–Short';

  const toggle = (id: string) => setExpanded((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const phaseLabel = (phase: string) => ({
    original: zh ? '初始探索' : 'Original',
    mutation: zh ? '变异' : 'Mutation',
    crossover: zh ? '交叉' : 'Crossover',
  }[phase] || phase);

  const decisionBadge = (decision: boolean | null) => {
    if (decision === true) return <Badge variant="success">{zh ? '采纳' : 'Accepted'}</Badge>;
    if (decision === false) return <Badge variant="destructive">{zh ? '未采纳' : 'Rejected'}</Badge>;
    return <Badge variant="outline">{zh ? '无反馈' : 'No feedback'}</Badge>;
  };

  const metricCells = (m: RoundFeedback['metrics']) => [
    ['IC', formatNumber(m.IC, 4)],
    ['Rank IC', formatNumber(m.RankIC, 4)],
    [`${legLabel} ${zh ? '年化净收益' : 'net ann. return'}`, formatPercent(m.annualized_return)],
    [`${legLabel} Sharpe`, formatNumber(m.information_ratio, 2)],
    [`${legLabel} ${zh ? '最大回撤' : 'max DD'}`, formatPercent(m.max_drawdown)],
    [zh ? '进化评分' : 'Evolution score', formatNumber(m.evolution_score, 1)],
  ];

  const section = (label: string, text: string) => text ? (
    <div>
      <div className="text-xs font-medium text-foreground mb-1">{label}</div>
      <p className="text-sm leading-6 text-muted-foreground whitespace-pre-wrap" data-no-translate="">{text}</p>
    </div>
  ) : null;

  const filterButton = (value: DecisionFilter, label: string) => (
    <button
      key={value}
      onClick={() => setFilter(value)}
      className={`rounded-md px-2.5 py-1 text-xs transition-colors ${
        filter === value ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground'}`}
    >
      {label}
    </button>
  );

  return (
    <Card className="glass card-hover animate-fade-in-up w-full">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="text-base flex items-center gap-2">
            <MessageSquareText className="h-4 w-4 text-primary" />
            {zh ? '每轮 LLM 反馈' : 'Round Feedback from the LLM'}
            {report?.available && (
              <span className="text-xs font-normal text-muted-foreground">
                {zh
                  ? `${rounds.length} 轮 · 采纳 ${acceptedCount} · 未采纳 ${rejectedCount}`
                  : `${rounds.length} rounds · ${acceptedCount} accepted · ${rejectedCount} rejected`}
              </span>
            )}
          </CardTitle>
          {report?.available && rounds.length > 0 && (
            <div className="flex items-center gap-1 rounded-lg border border-border/50 p-0.5">
              {filterButton('all', zh ? '全部' : 'All')}
              {filterButton('accepted', zh ? '采纳' : 'Accepted')}
              {filterButton('rejected', zh ? '未采纳' : 'Rejected')}
            </div>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {zh
            ? `指标为该轮评分最高的因子在验证集上的表现；收益、Sharpe 和回撤为 ${legLabel} 组合的扣费后结果。`
            : `Metrics are for the round's highest-scoring factor on the validation split; return, Sharpe, and drawdown are net of costs for the ${legLabel} portfolio.`}
        </p>
      </CardHeader>
      <CardContent>
        {error && (
          <p className="text-sm text-destructive mb-3">
            {zh ? '反馈加载失败：' : 'Could not load feedback: '}{error}
          </p>
        )}
        {!error && report && !report.available && (
          <p className="text-sm text-muted-foreground">
            {zh ? '第一轮完成后将显示 LLM 反馈。' : 'LLM feedback appears here once the first round finishes.'}
          </p>
        )}
        {!experimentId && (
          <p className="text-sm text-muted-foreground">
            {zh
              ? '该任务未记录运行目录（旧任务且使用了自定义因子库名称），无法定位其反馈文件。'
              : 'This task has no recorded run folder (an older task with a custom library name), so its feedback file cannot be located.'}
          </p>
        )}
        {experimentId && !error && !report && (
          <p className="text-sm text-muted-foreground">{zh ? '正在加载反馈…' : 'Loading feedback…'}</p>
        )}
        {report?.available && rounds.length > 0 && visible.length === 0 && (
          <p className="text-sm text-muted-foreground">{zh ? '没有符合筛选条件的轮次。' : 'No rounds match this filter.'}</p>
        )}
        <div className="space-y-3 max-h-[760px] overflow-y-auto pr-1">
          {visible.map((round) => {
            const open = expanded.has(round.trajectoryId);
            return (
              <div key={round.trajectoryId} className="rounded-xl border border-border/60 bg-background/40">
                <button
                  onClick={() => toggle(round.trajectoryId)}
                  className="w-full text-left p-4 flex gap-3"
                  aria-expanded={open}
                >
                  {open
                    ? <ChevronDown className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
                    : <ChevronRight className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />}
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">
                        {zh
                          ? `方向 ${round.directionId ?? '–'} · 第 ${round.roundIdx ?? '–'} 轮`
                          : `Direction ${round.directionId ?? '–'} · Round ${round.roundIdx ?? '–'}`}
                      </span>
                      <Badge variant="outline">{phaseLabel(round.phase)}</Badge>
                      {decisionBadge(round.decision)}
                      <span>{round.createdAt ? new Date(round.createdAt).toLocaleString() : ''}</span>
                    </div>
                    <p className={`text-sm text-foreground ${open ? 'whitespace-pre-wrap' : 'line-clamp-2'}`} data-no-translate="">
                      {round.hypothesis || (zh ? '（无假设文本）' : '(no hypothesis text)')}
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-2">
                      {metricCells(round.metrics).map(([label, value]) => (
                        <div key={label} className="rounded-md bg-muted/30 px-2 py-1">
                          <div className="text-[11px] text-muted-foreground truncate">{label}</div>
                          <div className="text-sm font-mono">{value}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </button>
                {open && (
                  <div className="px-4 pb-4 pl-11 space-y-3 border-t border-border/40 pt-3">
                    {section(zh ? '本轮观察' : 'Observations', round.observations)}
                    {section(zh ? '假设评价' : 'Hypothesis evaluation', round.hypothesisEvaluation)}
                    {section(zh ? '判断依据' : 'Reasoning', round.reason)}
                    {section(zh ? '下一步假设' : 'Next hypothesis', round.newHypothesis)}
                    {round.decision === null && !round.observations && (
                      <p className="text-sm text-muted-foreground">
                        {zh ? '本轮没有生成反馈（可能因子生成或回测失败）。' : 'This round produced no feedback (factor generation or the backtest may have failed).'}
                      </p>
                    )}
                    {round.factors.length > 0 && (
                      <div>
                        <div className="text-xs font-medium text-foreground mb-1">
                          {zh ? `本轮因子（${round.factors.length}）` : `Factors this round (${round.factors.length})`}
                        </div>
                        <ul className="space-y-1.5" data-no-translate="">
                          {round.factors.map((factor) => (
                            <li key={factor.name} className="text-xs">
                              <span className="font-medium text-foreground">{factor.name}</span>
                              <code className="block mt-0.5 break-all rounded bg-muted/40 px-2 py-1 text-muted-foreground">
                                {factor.expression}
                              </code>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};
