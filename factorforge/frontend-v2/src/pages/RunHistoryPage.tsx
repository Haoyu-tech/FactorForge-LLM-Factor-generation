import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, Database, History, LayoutDashboard, RefreshCw } from 'lucide-react';
import {
  CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FactorList } from '@/components/FactorList';
import { RoundFeedbackPanel } from '@/components/RoundFeedbackPanel';
import type { PageId } from '@/components/layout/Layout';
import { useLanguage } from '@/context/LanguageContext';
import { getExperiment, listExperiments } from '@/services/api';
import type { RunDetail, RunStatus, RunSummary } from '@/services/api';
import { formatClock, formatDuration, formatTokens, formatUsd } from '@/utils/runInfo';
import { requestOpenLibrary } from '@/utils/libraryNavigation';

interface RunHistoryPageProps {
  onNavigate: (page: PageId) => void;
  /** The page stays mounted while hidden; it refreshes when shown again. */
  isActive: boolean;
}

const SELECTED_KEY = 'factorforge_history_run';
const POLL_MS = 15000;

const readSelected = (): string | null => {
  try { return localStorage.getItem(SELECTED_KEY); } catch { return null; }
};
const writeSelected = (id: string | null) => {
  try {
    if (id) localStorage.setItem(SELECTED_KEY, id); else localStorage.removeItem(SELECTED_KEY);
  } catch { /* per-viewer convenience only */ }
};

const num = (value: number | null | undefined, digits: number) =>
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—';
const pct = (value: number | null | undefined) =>
  typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : '—';

export const RunHistoryPage: React.FC<RunHistoryPageProps> = ({ onNavigate, isActive }) => {
  const { language } = useLanguage();
  const zh = language === 'zh';
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [showEmpty, setShowEmpty] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(readSelected);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const select = (id: string | null) => {
    setSelectedId(id);
    writeSelected(id);
    window.scrollTo({ top: 0 });
  };

  const loadRuns = useCallback(async () => {
    try {
      const response = await listExperiments();
      setRuns(response.data?.runs || []);
      setListError(null);
    } catch (err) {
      setListError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  // The run currently asked for; a slower answer for an earlier pick is dropped.
  const wantedId = useRef<string | null>(selectedId);
  wantedId.current = selectedId;

  const loadDetail = useCallback(async (id: string) => {
    try {
      const response = await getExperiment(id);
      if (wantedId.current !== id) return;
      if (response.data) setDetail(response.data);
      setDetailError(null);
    } catch (err) {
      if (wantedId.current !== id) return;
      setDetailError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    await Promise.all([loadRuns(), selectedId ? loadDetail(selectedId) : Promise.resolve()]);
    setLoading(false);
  }, [loadRuns, loadDetail, selectedId]);

  useEffect(() => {
    setDetail((prev) => (prev?.experimentId === selectedId ? prev : null));
    setDetailError(null);
    if (selectedId && isActive) loadDetail(selectedId);
  }, [selectedId, isActive, loadDetail]);

  useEffect(() => {
    if (isActive) loadRuns();
  }, [isActive, loadRuns]);

  // Keep a running run current while the page is open.
  const anyRunning = (runs || []).some((r) => r.status === 'running' || r.status === 'pending');
  useEffect(() => {
    if (!isActive || !anyRunning) return;
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [isActive, anyRunning, refresh]);

  const statusLabel = (status: RunStatus) => ({
    completed: zh ? '已完成' : 'Finished',
    cancelled: zh ? '已停止' : 'Stopped',
    failed: zh ? '失败' : 'Failed',
    interrupted: zh ? '中断' : 'Interrupted',
    running: zh ? '运行中' : 'Running',
    pending: zh ? '等待中' : 'Pending',
    unknown: zh ? '未记录' : 'Not recorded',
  }[status] || status);

  const statusBadge = (status: RunStatus) => {
    const variant = ({
      completed: 'success', failed: 'destructive', cancelled: 'warning', interrupted: 'warning',
      running: 'default', pending: 'default', unknown: 'outline',
    } as const)[status] || 'outline';
    return <Badge variant={variant} className="whitespace-nowrap">{statusLabel(status)}</Badge>;
  };

  const visibleRuns = useMemo(
    () => (runs || []).filter((r) => showEmpty || r.hasResults || r.experimentId === selectedId),
    [runs, showEmpty, selectedId],
  );
  const hiddenCount = (runs || []).length - (runs || []).filter((r) => r.hasResults).length;

  const snippet = (text: string | null, length: number) => {
    const flat = (text || '').replace(/\s+/g, ' ').trim();
    if (!flat) return zh ? '（未保存提示词）' : '(prompt not saved)';
    return flat.length > length ? `${flat.slice(0, length)}…` : flat;
  };

  const approx = (estimated: boolean) => (estimated ? '≈ ' : '');

  // A saved round counter can run one past the plan; never show more done than planned.
  const roundsText = (run: RunSummary) => {
    const planned = run.roundsPlanned;
    const reached = run.roundsReached != null && planned != null ? Math.min(run.roundsReached, planned) : run.roundsReached;
    return `${reached ?? '—'} / ${planned ?? '—'}`;
  };

  const header = (
    <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
      <div className="flex items-center gap-3">
        <History className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-xl font-semibold">{zh ? '运行历史' : 'Run History'}</h1>
          <p className="text-xs text-muted-foreground">
            {zh ? '每次挖掘运行的提示词、结果、用量与 LLM 反馈，读取自 log/ 下的运行目录。'
              : 'Prompt, outcome, usage and LLM feedback for every mining run, read from its folder under log/.'}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor="run-picker">{zh ? '选择运行' : 'Choose a run'}</label>
        <select
          id="run-picker"
          data-no-translate=""
          value={selectedId || ''}
          onChange={(e) => select(e.target.value || null)}
          className="max-w-[min(520px,90vw)] rounded-lg border border-input bg-background px-3 py-2 text-sm"
        >
          <option value="">{zh ? '全部运行' : 'All runs'}</option>
          {visibleRuns.map((run) => (
            <option key={run.experimentId} value={run.experimentId}>
              {`${formatClock(run.startedAt)} · ${statusLabel(run.status)} · ${snippet(run.direction, 48)}`}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <input type="checkbox" checked={showEmpty} onChange={(e) => setShowEmpty(e.target.checked)} />
          {zh ? `显示无结果的运行（${hiddenCount}）` : `Show runs without results (${hiddenCount})`}
        </label>
        <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
          {zh ? '刷新' : 'Refresh'}
        </Button>
      </div>
    </div>
  );

  if (!selectedId) {
    return (
      <div className="animate-fade-in-up">
        {header}
        {listError && <p className="text-sm text-destructive mb-3">{zh ? '运行列表加载失败：' : 'Could not load runs: '}{listError}</p>}
        {!runs && !listError && <p className="text-sm text-muted-foreground">{zh ? '正在加载…' : 'Loading…'}</p>}
        {runs && visibleRuns.length === 0 && (
          <p className="text-sm text-muted-foreground">{zh ? '还没有运行记录。' : 'No runs yet.'}</p>
        )}
        {visibleRuns.length > 0 && (
          <Card className="glass">
            <CardContent className="p-0 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-muted-foreground border-b border-border/60">
                  <tr className="text-left">
                    <th className="px-4 py-3 font-medium whitespace-nowrap">{zh ? '开始时间' : 'Started'}</th>
                    <th className="px-4 py-3 font-medium min-w-[260px]">{zh ? '提示词' : 'Prompt'}</th>
                    <th className="px-4 py-3 font-medium">{zh ? '状态' : 'Status'}</th>
                    <th className="px-4 py-3 font-medium text-right whitespace-nowrap">{zh ? '轮次' : 'Rounds'}</th>
                    <th className="px-4 py-3 font-medium text-right whitespace-nowrap">{zh ? '采纳' : 'Accepted'}</th>
                    <th className="px-4 py-3 font-medium text-right whitespace-nowrap">{zh ? '因子数' : 'Factors'}</th>
                    <th className="px-4 py-3 font-medium text-right whitespace-nowrap" title={zh ? '进化评分最高的一轮，验证集' : 'Round with the highest evolution score, validation split'}>
                      {zh ? '最佳轮 Rank IC' : 'Best round Rank IC'}
                    </th>
                    <th className="px-4 py-3 font-medium text-right whitespace-nowrap">Sharpe</th>
                    <th className="px-4 py-3 font-medium text-right whitespace-nowrap">{zh ? '用时' : 'Duration'}</th>
                    <th className="px-4 py-3 font-medium text-right whitespace-nowrap">{zh ? '费用' : 'Cost'}</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRuns.map((run) => (
                    <tr
                      key={run.experimentId}
                      onClick={() => select(run.experimentId)}
                      className="border-b border-border/40 last:border-0 cursor-pointer hover:bg-muted/30"
                    >
                      <td className="px-4 py-3 whitespace-nowrap font-mono text-xs">{formatClock(run.startedAt)}</td>
                      <td className="px-4 py-3"><span className="line-clamp-2" data-no-translate="">{snippet(run.direction, 160)}</span></td>
                      <td className="px-4 py-3">{statusBadge(run.status)}</td>
                      <td className="px-4 py-3 text-right font-mono whitespace-nowrap">{roundsText(run)}</td>
                      <td className="px-4 py-3 text-right font-mono whitespace-nowrap">
                        {run.rounds ? `${run.rounds.accepted} / ${run.rounds.total}` : '—'}
                      </td>
                      <td className="px-4 py-3 text-right font-mono">{run.library?.factorCount ?? '—'}</td>
                      <td className="px-4 py-3 text-right font-mono">{num(run.best?.rankIc, 4)}</td>
                      <td className="px-4 py-3 text-right font-mono">{num(run.best?.sharpe, 2)}</td>
                      <td className="px-4 py-3 text-right font-mono whitespace-nowrap">
                        {run.durationSeconds != null ? `${approx(run.completedAtEstimated)}${formatDuration(run.durationSeconds)}` : '—'}
                      </td>
                      <td className="px-4 py-3 text-right font-mono">{formatUsd(run.usage?.costUsd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}
        <p className="text-xs text-muted-foreground mt-3">
          {zh
            ? '“未记录”的运行早于运行记录功能：提示词和时间从运行目录恢复（时间为估计值），模型、用量、费用和结果未保存。'
            : '"Not recorded" runs predate run records: prompt and times were recovered from the run folder (times are estimates); model, usage, cost and outcome were never saved.'}
        </p>
      </div>
    );
  }

  const run = detail;
  const fact = (label: string, value: React.ReactNode) => (
    <div className="rounded-lg bg-muted/30 px-3 py-2 min-w-0">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="text-sm font-medium break-words">{value}</div>
    </div>
  );

  let bestSoFar: number | null = null;
  const points = (run?.scores || []).map((score, index) => {
    if (score.rankIc != null) bestSoFar = bestSoFar == null ? score.rankIc : Math.max(bestSoFar, score.rankIc);
    return { ...score, order: index + 1, bestSoFar };
  });
  const series = (decision: boolean | null) => points.filter((p) => p.decision === decision && p.rankIc != null);
  const splits = run?.library?.splitWindows;
  const leg = run?.library?.marketMode === 'cn' ? 'Long' : 'Long–Short';

  return (
    <div className="animate-fade-in-up space-y-6">
      {header}
      <Button variant="ghost" size="sm" onClick={() => select(null)}>
        <ArrowLeft className="h-4 w-4 mr-1.5" />{zh ? '全部运行' : 'All runs'}
      </Button>
      {detailError && <p className="text-sm text-destructive">{zh ? '运行详情加载失败：' : 'Could not load this run: '}{detailError}</p>}
      {!run && !detailError && <p className="text-sm text-muted-foreground">{zh ? '正在加载…' : 'Loading…'}</p>}
      {run && (
        <>
          <Card className="glass">
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <CardTitle className="text-base flex flex-wrap items-center gap-2">
                  <span className="font-mono">{run.experimentId}</span>
                  {statusBadge(run.status)}
                </CardTitle>
                <div className="flex flex-wrap gap-2">
                  {run.taskId && run.status === 'running' && (
                    <Button variant="outline" size="sm" onClick={() => onNavigate('mining_dashboard')}>
                      <LayoutDashboard className="h-4 w-4 mr-1.5" />{zh ? '打开实时面板' : 'Open live dashboard'}
                    </Button>
                  )}
                  {run.library && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        requestOpenLibrary({ file: run.library!.file, marketMode: run.library!.marketMode, market: run.library!.market });
                        onNavigate('library');
                      }}
                    >
                      <Database className="h-4 w-4 mr-1.5" />{zh ? '在因子库中打开' : 'Open in Factor Library'}
                    </Button>
                  )}
                </div>
              </div>
              {run.statusMessage && <p className="text-xs text-muted-foreground">{run.statusMessage}</p>}
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="text-xs font-medium mb-1">{zh ? '提示词' : 'Prompt'}</div>
                <p className="text-sm leading-6 whitespace-pre-wrap rounded-lg bg-muted/30 px-3 py-2" data-no-translate="">
                  {run.direction || (zh ? '（未保存提示词）' : '(prompt not saved)')}
                </p>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {fact(zh ? '开始' : 'Started', formatClock(run.startedAt))}
                {fact(zh ? '结束' : 'Ended', run.completedAt ? `${approx(run.completedAtEstimated)}${formatClock(run.completedAt)}` : '—')}
                {fact(zh ? '用时' : 'Duration', run.durationSeconds != null ? `${approx(run.completedAtEstimated)}${formatDuration(run.durationSeconds)}` : '—')}
                {fact(zh ? '轮次' : 'Rounds', roundsText(run))}
                {fact('LLM', run.llm ? `${run.llm.label} · ${run.llm.model}` : '—')}
                {fact(zh ? 'Token 用量' : 'Tokens', run.usage
                  ? `${formatTokens(run.usage.totalTokens)} (${run.usage.calls} ${zh ? '次调用' : 'calls'})`
                  : '—')}
                {fact(zh ? '费用' : 'Cost', formatUsd(run.usage?.costUsd))}
                {fact(zh ? '轮次决策' : 'Round decisions', run.rounds
                  ? (zh
                    ? `采纳 ${run.rounds.accepted} · 未采纳 ${run.rounds.rejected}${run.rounds.noFeedback ? ` · 无反馈 ${run.rounds.noFeedback}` : ''}`
                    : `${run.rounds.accepted} accepted · ${run.rounds.rejected} rejected${run.rounds.noFeedback ? ` · ${run.rounds.noFeedback} no feedback` : ''}`)
                  : '—')}
                {fact(zh ? '市场' : 'Market', run.library?.scopeLabel || run.library?.market || '—')}
                {fact(zh ? '因子库' : 'Library', run.library ? `${run.library.file} (${run.library.factorCount})` : '—')}
                {fact(zh ? '样本区间' : 'Sample splits', splits
                  ? (
                    <span className="block font-mono text-xs leading-5">
                      {(['train', 'valid', 'test'] as const).map((key) => (
                        <span key={key} className="block whitespace-nowrap">
                          {({ train: zh ? '训练' : 'Train', valid: zh ? '验证' : 'Valid', test: zh ? '测试' : 'Test' })[key]}{' '}
                          {splits[key]?.join(' → ') ?? '—'}
                        </span>
                      ))}
                    </span>
                  )
                  : '—')}
                {fact(zh ? '方向 × 轮次' : 'Directions × rounds', `${String(run.evolutionConfig.num_directions ?? run.settings.numDirections ?? '—')} × ${String(run.evolutionConfig.max_rounds ?? run.settings.maxRounds ?? '—')}`)}
              </div>
              {run.usage?.byModel && run.usage.byModel.length > 1 && (
                <div className="text-xs text-muted-foreground">
                  {run.usage.byModel.map((m) => `${m.model}: ${formatTokens(m.totalTokens)} · ${formatUsd(m.costUsd)}`).join('  |  ')}
                </div>
              )}
              {run.recordSource !== 'backend' && (
                <p className="text-xs text-muted-foreground">
                  {zh
                    ? '此运行早于运行记录功能：提示词和时间从运行目录恢复，时间为估计值（≈）；模型、用量、费用和结果未保存。'
                    : 'This run predates run records: the prompt and times were recovered from its folder, and times are estimates (≈). Model, usage, cost and outcome were never saved.'}
                </p>
              )}
            </CardContent>
          </Card>

          {run.plannedDirections.length > 0 && (
            <Card className="glass">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{zh ? `规划出的探索方向（${run.plannedDirections.length}）` : `Planned exploration directions (${run.plannedDirections.length})`}</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="space-y-2 text-sm list-decimal pl-5" data-no-translate="">
                  {run.plannedDirections.map((direction, index) => (
                    <li key={index} className="leading-6 text-muted-foreground">
                      {direction || (zh ? '（无）' : '(none)')}
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          )}

          {points.length > 0 && (
            <Card className="glass">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{zh ? '每轮验证集 Rank IC' : 'Validation Rank IC by round'}</CardTitle>
                <p className="text-xs text-muted-foreground">
                  {zh
                    ? '每个点是一轮中评分最高的因子，按完成时间排序；折线为截至该轮的最高值。'
                    : "Each point is the round's highest-scoring factor, in order of completion; the line is the best so far."}
                </p>
              </CardHeader>
              <CardContent className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={points} margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                    <XAxis dataKey="order" type="number" domain={[1, 'dataMax']} allowDecimals={false} tick={{ fontSize: 11 }}
                      label={{ value: zh ? '轮次（按完成顺序）' : 'Round (completion order)', position: 'insideBottom', offset: -4, fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => v.toFixed(3)} width={56} />
                    <Tooltip
                      formatter={(value: number) => (typeof value === 'number' ? value.toFixed(4) : value)}
                      labelFormatter={(order: number) => {
                        const p = points[order - 1];
                        return p ? `${zh ? '方向' : 'Direction'} ${p.directionId ?? '–'} · ${zh ? '第' : 'round'} ${p.roundIdx ?? '–'}${zh ? ' 轮' : ''} · ${p.phase}` : '';
                      }}
                    />
                    <Legend verticalAlign="top" wrapperStyle={{ fontSize: 12, paddingBottom: 8 }} />
                    <Line dataKey="bestSoFar" name={zh ? '截至当前最高' : 'Best so far'} stroke="#0ea5e9" dot={false} strokeWidth={2} connectNulls isAnimationActive={false} />
                    <Scatter data={series(true)} dataKey="rankIc" name={zh ? '采纳' : 'Accepted'} fill="#10b981" isAnimationActive={false} />
                    <Scatter data={series(false)} dataKey="rankIc" name={zh ? '未采纳' : 'Rejected'} fill="#f43f5e" isAnimationActive={false} />
                    {series(null).length > 0 && (
                      <Scatter data={series(null)} dataKey="rankIc" name={zh ? '无反馈' : 'No feedback'} fill="#94a3b8" isAnimationActive={false} />
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {run.best && (
            <p className="text-xs text-muted-foreground -mt-3">
              {zh
                ? `进化评分最高的一轮：方向 ${run.best.directionId ?? '–'} 第 ${run.best.roundIdx ?? '–'} 轮，Rank IC ${num(run.best.rankIc, 4)}，${leg} 年化净收益 ${pct(run.best.annualizedReturn)}，Sharpe ${num(run.best.sharpe, 2)}，最大回撤 ${pct(run.best.maxDrawdown)}（验证集）。`
                : `Highest evolution score: direction ${run.best.directionId ?? '–'}, round ${run.best.roundIdx ?? '–'}; Rank IC ${num(run.best.rankIc, 4)}, ${leg} net annual return ${pct(run.best.annualizedReturn)}, Sharpe ${num(run.best.sharpe, 2)}, max drawdown ${pct(run.best.maxDrawdown)} (validation split).`}
            </p>
          )}

          {run.factorMetrics?.top10Factors?.length ? <FactorList metrics={run.factorMetrics} /> : null}

          <RoundFeedbackPanel
            experimentId={run.experimentId}
            isRunning={isActive && run.status === 'running'}
            marketMode={run.library?.marketMode ?? undefined}
          />
        </>
      )}
    </div>
  );
};
