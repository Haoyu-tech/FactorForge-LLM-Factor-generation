import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { formatNumber, formatPercent } from '@/utils';
import {
  BenchmarkModelResult,
  BenchmarkModelsResponse,
  getBenchmarkModels,
  getBenchmarkRun,
  runBenchmarkModels,
} from '@/services/api';

/** One mined factor on the radar. Values come straight from the backend factor record. */
export interface RadarFactorInput {
  name: string;
  /** Short legend label (e.g. the card rank "#3"); defaults to the plot order "#1", "#2", ... */
  label?: string;
  ic?: number | null;
  rankIc?: number | null;
  icir?: number | null;
  /** Annualised net return as a fraction (0.046 = 4.6%). */
  annualReturn?: number | null;
  /** Maximum drawdown as a fraction; sign is ignored (0.627 and -0.627 both mean 62.7%). */
  maxDrawdown?: number | null;
}

interface FactorRadarChartProps {
  factors: RadarFactorInput[];
  /** Qlib universe the factors were evaluated on; benchmark rows are fetched for the same market. */
  market?: string;
  /** How many factors to plot (the first N in the order given). */
  maxFactors?: number;
  title?: string;
  className?: string;
}

type AxisKey = 'ic' | 'rankIc' | 'icir' | 'annualReturn' | 'mdd';

/** Axis order clockwise from the top: Rank IC, IC, -MDD, AR, ICIR. */
const AXES: Array<{ key: AxisKey; label: string; definition: string; percent: boolean }> = [
  { key: 'rankIc', label: 'Rank IC', definition: 'Rank IC', percent: false },
  { key: 'ic', label: 'IC', definition: 'IC', percent: false },
  { key: 'mdd', label: '-MDD', definition: 'MDD', percent: true },
  { key: 'annualReturn', label: 'AR', definition: 'AR', percent: true },
  { key: 'icir', label: 'ICIR', definition: 'ICIR', percent: false },
];

// Categorical slots (validated for CVD separation and contrast on both surfaces).
const FACTOR_COLORS_LIGHT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948'];
const FACTOR_COLORS_DARK = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#0ca30c', '#9085e9', '#e66767'];
// Benchmarks are neutral and dashed so they never compete with factor hues.
const BENCHMARK_STYLES = [
  { light: '#52514e', dark: '#c3c2b7', dash: '6 3' },
  { light: '#898781', dark: '#a09e96', dash: '2 3' },
  { light: '#0b0b0b', dark: '#f0efec', dash: '8 3 2 3' },
];

const finite = (value: number | null | undefined): value is number =>
  typeof value === 'number' && Number.isFinite(value);

/** Map a backend benchmark result onto the radar inputs using its preferred portfolio leg. */
function benchmarkToRadar(result: BenchmarkModelResult): RadarFactorInput {
  const leg = result.portfolio?.[result.preferred_leg] ?? result.portfolio?.long_short;
  return {
    name: result.label,
    ic: result.metrics?.IC,
    rankIc: result.metrics?.['Rank IC'],
    icir: result.metrics?.ICIR,
    annualReturn: leg?.annualized_net_return,
    maxDrawdown: leg?.max_drawdown,
  };
}

/** Raw value on an axis, oriented so that larger is always better. */
function rawValue(series: RadarFactorInput, key: AxisKey): number | null {
  if (key === 'mdd') return finite(series.maxDrawdown) ? -Math.abs(series.maxDrawdown) : null;
  const value = series[key];
  return finite(value) ? value : null;
}

function useIsDark(): boolean {
  const read = () => typeof document !== 'undefined' && document.documentElement.classList.contains('dark');
  const [dark, setDark] = useState(read);
  useEffect(() => {
    if (typeof MutationObserver === 'undefined') return;
    const observer = new MutationObserver(() => setDark(read()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);
  return dark;
}

/** Benchmark results and metric definitions for one market, with run/poll controls. */
function useBenchmarkModels(market?: string) {
  const [data, setData] = useState<BenchmarkModelsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runTaskId, setRunTaskId] = useState<string | null>(null);
  const [runMessage, setRunMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const resp = await getBenchmarkModels(market);
      if (resp.success && resp.data) {
        setData(resp.data);
        setError(null);
        const active = resp.data.running[0];
        if (active && !runTaskId) setRunTaskId(active.taskId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [market, runTaskId]);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    if (!runTaskId) return;
    const timer = window.setInterval(async () => {
      try {
        const resp = await getBenchmarkRun(runTaskId);
        const task = resp.data?.task;
        if (!task) return;
        setRunMessage(task.progress?.message || null);
        if (task.status !== 'running') {
          window.clearInterval(timer);
          setRunTaskId(null);
          setRunMessage(task.status === 'completed' ? null : task.progress?.message || task.status);
          void refresh();
        }
      } catch {
        /* keep polling */
      }
    }, 5000);
    return () => window.clearInterval(timer);
  }, [runTaskId, refresh]);

  const start = useCallback(async () => {
    if (!data) return;
    try {
      const resp = await runBenchmarkModels({ models: data.available_models.map((m) => m.id), market });
      if (resp.success && resp.data) {
        setRunTaskId(resp.data.taskId);
        setRunMessage(resp.data.task.progress?.message || null);
      }
    } catch (err) {
      setRunMessage(err instanceof Error ? err.message : String(err));
    }
  }, [data, market]);

  return { data, error, running: !!runTaskId, runMessage, start };
}

export const FactorRadarChart: React.FC<FactorRadarChartProps> = ({
  factors,
  market,
  maxFactors = 5,
  title = '因子表现雷达图',
  className = '',
}) => {
  const [showBenchmarks, setShowBenchmarks] = useState(true);
  const [panel, setPanel] = useState<'none' | 'table' | 'formulas'>('none');
  const isDark = useIsDark();
  const benchmarks = useBenchmarkModels(market);
  const benchmarkResults = benchmarks.data?.models ?? [];

  const plotted = useMemo(() => {
    const picked = factors
      .filter((f) => AXES.some((axis) => rawValue(f, axis.key) !== null))
      .slice(0, maxFactors);
    // Legend and series key use a short rank label; the full factor name stays in the tooltip and table.
    return picked.map((f, index) => ({
      ...f, fullName: f.name, name: f.label || `#${index + 1}`, kind: 'factor' as const, index,
    }));
  }, [factors, maxFactors]);

  const series = useMemo(
    () => [
      ...plotted,
      ...(showBenchmarks
        ? benchmarkResults.slice(0, BENCHMARK_STYLES.length).map((b, index) => {
            const radar = benchmarkToRadar(b);
            return { ...radar, fullName: radar.name, kind: 'benchmark' as const, index, source: b };
          })
        : []),
    ],
    [plotted, showBenchmarks, benchmarkResults]
  );

  // Per-axis min–max across every displayed series: 1 = best shown, 0 = worst shown.
  const axisRange = useMemo(() => {
    const range: Record<string, { min: number; max: number }> = {};
    AXES.forEach((axis) => {
      const values = series.map((s) => rawValue(s, axis.key)).filter(finite);
      range[axis.label] = {
        min: values.length ? Math.min(...values) : 0,
        max: values.length ? Math.max(...values) : 0,
      };
    });
    return range;
  }, [series]);

  const chartData = useMemo(
    () =>
      AXES.map((axis) => {
        const { min, max } = axisRange[axis.label];
        const row: Record<string, number | string | null> = { axis: axis.label };
        series.forEach((s) => {
          const raw = rawValue(s, axis.key);
          row[`raw:${s.name}`] = raw;
          row[s.name] = raw === null ? null : max === min ? 1 : (raw - min) / (max - min);
        });
        return row;
      }),
    [series, axisRange]
  );

  const colorFor = (s: (typeof series)[number]) =>
    s.kind === 'factor'
      ? (isDark ? FACTOR_COLORS_DARK : FACTOR_COLORS_LIGHT)[s.index % FACTOR_COLORS_LIGHT.length]
      : (isDark ? BENCHMARK_STYLES[s.index].dark : BENCHMARK_STYLES[s.index].light);
  const ink = isDark ? '#c3c2b7' : '#52514e';
  const grid = isDark ? '#2c2c2a' : '#e1e0d9';

  const formatRaw = (axisLabel: string, value: number | null) => {
    if (value === null) return 'N/A';
    const axis = AXES.find((a) => a.label === axisLabel);
    return axis?.percent ? formatPercent(value, 2) : formatNumber(value, 4);
  };

  const fullNameOf = (name: string) => series.find((s) => s.name === name)?.fullName ?? name;

  const renderTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    const range = axisRange[label];
    return (
      <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-md">
        <div className="mb-1 font-medium">{label}</div>
        {payload.map((entry: any) => (
          <div key={entry.name} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: entry.color }} />
              <span className="font-medium text-foreground">{entry.name}</span>
              {fullNameOf(entry.name) !== entry.name && (
                <span className="max-w-[260px] truncate">{fullNameOf(entry.name)}</span>
              )}
            </span>
            <span className="font-mono">
              {formatRaw(label, entry.payload[`raw:${entry.name}`])}
              <span className="ml-1 text-muted-foreground">({formatNumber(entry.value, 2)})</span>
            </span>
          </div>
        ))}
        {range && (
          <div className="mt-1 border-t border-border/50 pt-1 font-mono text-muted-foreground">
            min {formatRaw(label, range.min)} · max {formatRaw(label, range.max)}
          </div>
        )}
      </div>
    );
  };

  const definitions = benchmarks.data?.definitions;
  const normalization = benchmarks.data?.normalization;
  const hasBenchmarks = benchmarkResults.length > 0;
  const toggle = (target: 'table' | 'formulas') => setPanel((p) => (p === target ? 'none' : target));

  return (
    <Card className={`glass card-hover animate-fade-in-up w-full ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-primary" />
              {title}
            </CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              各轴按显示序列做 min–max 归一化（1 = 最好，0 = 最差），悬停查看原始值。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs">
            {hasBenchmarks && (
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showBenchmarks}
                  onChange={(e) => setShowBenchmarks(e.target.checked)}
                />
                显示基准模型
              </label>
            )}
            {!hasBenchmarks && benchmarks.data && (
              <button
                type="button"
                className="text-primary hover:underline disabled:opacity-50"
                disabled={benchmarks.running || !benchmarks.data.torch_available}
                onClick={() => void benchmarks.start()}
                title={benchmarks.data.torch_available ? undefined : 'PyTorch is not installed in the backend environment.'}
              >
                {benchmarks.running ? '基准模型训练中…' : '训练基准模型（LSTM / Transformer）'}
              </button>
            )}
            <button type="button" className="text-primary hover:underline" onClick={() => toggle('formulas')}>
              {panel === 'formulas' ? '隐藏公式' : '查看公式'}
            </button>
            <button type="button" className="text-primary hover:underline" onClick={() => toggle('table')}>
              {panel === 'table' ? '隐藏数据表' : '查看数据表'}
            </button>
          </div>
        </div>
        {(benchmarks.runMessage || benchmarks.error) && (
          <p className="text-xs text-muted-foreground">{benchmarks.runMessage || benchmarks.error}</p>
        )}
      </CardHeader>
      <CardContent>
        {plotted.length === 0 ? (
          <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
            暂无可绘制的因子指标
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={420}>
            <RadarChart data={chartData} outerRadius="72%" margin={{ top: 16, right: 24, bottom: 16, left: 24 }}>
              <PolarGrid stroke={grid} />
              <PolarAngleAxis dataKey="axis" tick={{ fill: ink, fontSize: 12 }} />
              <PolarRadiusAxis
                domain={[0, 1]}
                tickCount={6}
                tick={{ fill: ink, fontSize: 10 }}
                axisLine={false}
                stroke={grid}
              />
              <Tooltip content={renderTooltip} />
              {series.map((s) => (
                <Radar
                  key={s.name}
                  name={s.name}
                  dataKey={s.name}
                  stroke={colorFor(s)}
                  strokeWidth={s.kind === 'factor' ? 2 : 1.5}
                  strokeDasharray={s.kind === 'benchmark' ? BENCHMARK_STYLES[s.index].dash : undefined}
                  fill={colorFor(s)}
                  fillOpacity={s.kind === 'factor' ? 0.12 : 0}
                  dot={{ r: 3, strokeWidth: 0, fill: colorFor(s) }}
                  isAnimationActive={false}
                />
              ))}
              <Legend
                wrapperStyle={{ fontSize: 12 }}
                iconType="line"
                formatter={(value: string) => <span style={{ color: ink }}>{value}</span>}
              />
            </RadarChart>
          </ResponsiveContainer>
        )}

        {panel === 'table' && series.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border/50 text-muted-foreground">
                  <th className="py-2 pr-3 text-left font-medium">序列</th>
                  {AXES.map((axis) => (
                    <th key={axis.key} className="py-2 px-3 text-right font-medium">{axis.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {series.map((s) => (
                  <tr key={s.name} className="border-b border-border/30">
                    <td className="py-1.5 pr-3">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="inline-block h-2 w-2 rounded-full" style={{ background: colorFor(s) }} />
                        <span className="font-medium">{s.name}</span>
                        {s.fullName !== s.name && <span className="text-muted-foreground">{s.fullName}</span>}
                      </span>
                    </td>
                    {AXES.map((axis) => (
                      <td key={axis.key} className="py-1.5 px-3 text-right font-mono">
                        {formatRaw(axis.label, rawValue(s, axis.key))}
                      </td>
                    ))}
                  </tr>
                ))}
                <tr className="text-muted-foreground">
                  <td className="py-1.5 pr-3">min</td>
                  {AXES.map((axis) => (
                    <td key={axis.key} className="py-1.5 px-3 text-right font-mono">{formatRaw(axis.label, axisRange[axis.label].min)}</td>
                  ))}
                </tr>
                <tr className="text-muted-foreground">
                  <td className="py-1.5 pr-3">max</td>
                  {AXES.map((axis) => (
                    <td key={axis.key} className="py-1.5 px-3 text-right font-mono">{formatRaw(axis.label, axisRange[axis.label].max)}</td>
                  ))}
                </tr>
              </tbody>
            </table>
            {showBenchmarks && hasBenchmarks && (
              <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                {benchmarkResults.slice(0, BENCHMARK_STYLES.length).map((b) => (
                  <p key={b.model}>
                    <span className="font-medium text-foreground">{b.label}</span>
                    {' · '}{b.implementation}
                    {' · '}{b.features.count} features × {b.features.step_len} days
                    {' · '}train {b.split.train[0]}→{b.split.train[1]}, test {b.split.test[0]}→{b.split.test[1]}
                    {' · '}{b.training.epochs_run} epochs
                    {' · '}{b.generated_at}
                    {b.smoke_run ? ' · smoke run' : ''}
                  </p>
                ))}
              </div>
            )}
          </div>
        )}

        {panel === 'formulas' && (
          <div className="mt-4 space-y-3 text-xs">
            {normalization && (
              <div>
                <div className="font-medium">归一化</div>
                <code className="block rounded bg-muted px-2 py-1 font-mono">{normalization.formula}</code>
                <p className="text-muted-foreground">{normalization.description}</p>
              </div>
            )}
            {definitions
              ? AXES.map((axis) => {
                  const def = definitions[axis.definition];
                  if (!def) return null;
                  return (
                    <div key={axis.key}>
                      <div className="font-medium">{axis.label}</div>
                      <code className="block rounded bg-muted px-2 py-1 font-mono">{def.formula}</code>
                      <p className="text-muted-foreground">{def.description}</p>
                      <p className="font-mono text-muted-foreground">
                        {def.implementation}{def.line ? ` · ${def.file}:${def.line}` : ''}
                      </p>
                    </div>
                  );
                })
              : <p className="text-muted-foreground">公式定义加载中…</p>}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
