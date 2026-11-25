import React from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ExecutionProgress, Task, TaskStatus } from '@/types';
import { Sparkles, Brain, TrendingUp, CheckCircle2, XOctagon, Clock, Coins } from 'lucide-react';
import { displayProgress, displayRound, formatClock, formatDuration, formatRatePerMillion, formatTokens, formatUsd, hasUsage, transportLabel, useRunTiming } from '@/utils/runInfo';

interface ProgressSidebarProps {
  progress: ExecutionProgress;
  /** Timing and token usage for the run; the run-info card is hidden without it. */
  task?: Pick<Task, 'status' | 'createdAt' | 'updatedAt' | 'completedAt' | 'durationSeconds' | 'usage' | 'llm'>;
  /**
   * The run's status. The timeline used to be drawn from `progress.phase`
   * alone, and the backend leaves the phase at whatever step a run died on, so
   * a stopped or failed run rendered an animated "in progress" marker forever.
   */
  status: TaskStatus;
}

const phaseConfig = {
  parsing: { icon: Sparkles, label: '解析需求', color: 'text-blue-400' },
  planning: { icon: Brain, label: '规划方向', color: 'text-purple-400' },
  evolving: { icon: TrendingUp, label: '进化中', color: 'text-yellow-400' },
  backtesting: { icon: TrendingUp, label: '回测中', color: 'text-green-400' },
  analyzing: { icon: Brain, label: '分析结果', color: 'text-cyan-400' },
  completed: { icon: CheckCircle2, label: '完成', color: 'text-success' },
};

/** Phases the backend can report but this panel has no entry for. */
const unknownPhase = { icon: TrendingUp, label: '执行中', color: 'text-slate-400' };

export const ProgressSidebar: React.FC<ProgressSidebarProps> = ({ progress, status, task }) => {
  const currentPhase = phaseConfig[progress.phase] ?? unknownPhase;
  const round = displayRound(progress, status);
  const percent = displayProgress(progress, status);
  const timing = useRunTiming(task ?? null);
  const usage = task?.usage;
  const llm = task?.llm;
  // A run that ended short of 'completed' is stopped, not working.
  const isStopped = status === 'cancelled' || status === 'failed';
  const isLive = status === 'running';
  const Icon = isStopped ? XOctagon : currentPhase.icon;
  const statusLabel = status === 'cancelled' ? '已停止' : '已失败';
  const stoppedTone = status === 'cancelled' ? 'text-amber-500' : 'text-destructive';

  return (
    <div className="space-y-4">
      {/* Phase Status */}
      <Card className="glass card-hover animate-fade-in-left h-[140px]">
        <CardContent className="p-4 h-full flex flex-col justify-center">
          <div className="flex items-center gap-3 mb-4">
            <div className={`p-3 rounded-xl bg-secondary/50 ${isStopped ? stoppedTone : currentPhase.color}`}>
              <Icon className={`h-6 w-6 ${isLive ? 'animate-pulse' : ''}`} />
            </div>
            <div className="flex-1">
              <div className="text-sm font-medium mb-1">
                {isStopped ? `${statusLabel} · ${currentPhase.label}` : currentPhase.label}
              </div>
              <div className="text-xs text-muted-foreground">
                {/* One string, so the EN translator sees "第 x/y 轮" in a single text node. */}
                {`${status === 'completed' ? '已完成 · ' : ''}第 ${round.current}/${round.total} 轮`}
              </div>
            </div>
            <Badge
              variant={isStopped ? 'warning' : 'default'}
              className={isLive ? 'animate-pulse' : ''}
            >
              {percent.toFixed(0)}%
            </Badge>
          </div>

          {/* Progress Bar */}
          <div className="relative h-2 rounded-full overflow-hidden bg-secondary/30 mb-2">
            <div
              className={`absolute left-0 top-0 h-full transition-all duration-500 ${
                isStopped ? 'bg-muted-foreground/50' : 'progress-gradient'
              }`}
              style={{ width: `${percent}%` }}
            />
          </div>
        </CardContent>
      </Card>

      {/* Run time and LLM token consumption */}
      {task && (
        <Card className="glass card-hover animate-fade-in-left" style={{ animationDelay: '0.05s' }}>
          <CardContent className="p-4 space-y-3 text-xs">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Clock className="h-4 w-4 text-muted-foreground" />
              {timing.isFinished ? '运行耗时' : '已运行'}
              <span className="ml-auto font-mono">{formatDuration(timing.seconds)}</span>
            </div>
            <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-muted-foreground">
              <span>开始</span>
              <span className="text-right font-mono text-foreground/80">{formatClock(timing.startedAt)}</span>
              <span>{status === 'completed' ? '完成' : status === 'running' ? '结束' : '停止'}</span>
              <span className="text-right font-mono text-foreground/80">
                {timing.isFinished ? formatClock(timing.finishedAt) : '进行中'}
              </span>
            </div>
            <div className="border-t border-border/50 pt-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Coins className="h-4 w-4 text-muted-foreground" />
                Token 消耗
                <span className="ml-auto font-mono">{hasUsage(usage) ? formatTokens(usage.totalTokens) : '—'}</span>
              </div>
              <div className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-muted-foreground">
                <span>LLM 通道</span>
                <span className="flex items-center justify-end gap-1.5 text-right">
                  {llm ? (
                    <>
                      <span className="shrink-0 rounded border border-border/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                        {transportLabel(llm.transport)}
                      </span>
                      <span className="truncate font-mono text-foreground/80" title={llm.endpoint || llm.label}>
                        {llm.label}
                      </span>
                    </>
                  ) : (
                    <span className="font-mono text-foreground/80">未记录</span>
                  )}
                </span>
                {llm && (
                  <>
                    <span>模型</span>
                    <span className="truncate text-right font-mono text-foreground/80" title={llm.model}>
                      {llm.model}
                    </span>
                    {llm.endpoint && (
                      <>
                        <span>端点</span>
                        <span className="truncate text-right font-mono text-foreground/80" title={llm.endpoint}>
                          {llm.endpoint}
                        </span>
                      </>
                    )}
                  </>
                )}
              </div>
              {hasUsage(usage) ? (
                <div className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-muted-foreground">
                  <span>输入 / 输出</span>
                  <span className="text-right font-mono text-foreground/80">
                    {formatTokens(usage.promptTokens)} / {formatTokens(usage.completionTokens)}
                  </span>
                  <span>LLM 调用</span>
                  <span className="text-right font-mono text-foreground/80">{usage.calls}</span>
                  {usage.costUsd != null && (
                    <>
                      <span>实际费用</span>
                      <span className="text-right font-mono text-foreground/80">{formatUsd(usage.costUsd)}</span>
                    </>
                  )}
                </div>
              ) : (
                <p className="mt-1 text-muted-foreground">
                  {usage ? '尚无 LLM 调用记录' : '此任务启动时未记录 token 用量'}
                </p>
              )}
              {hasUsage(usage) && !!usage.byModel?.length && (
                <div className="mt-3 space-y-2 border-t border-border/40 pt-2">
                  {usage.byModel.map((row) => (
                    <div key={`${row.model}|${row.source}`}>
                      <div className="flex items-center gap-2">
                        <span className="truncate font-mono text-foreground/90" title={row.model}>
                          {row.model}
                        </span>
                        <span className="shrink-0 rounded border border-border/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                          {transportLabel(row.transport)}
                        </span>
                      </div>
                      <div className="grid grid-cols-[auto_1fr] gap-x-3 text-muted-foreground">
                        <span>用量</span>
                        <span className="text-right font-mono text-foreground/80">
                          {formatTokens(row.totalTokens)}
                          <span className="text-muted-foreground">
                            {' '}({formatTokens(row.promptTokens)} / {formatTokens(row.completionTokens)})
                          </span>
                        </span>
                        <span>单价</span>
                        <span className="text-right font-mono text-foreground/80">
                          {formatRatePerMillion(row.costUsd, row.totalTokens)}
                        </span>
                        <span>费用</span>
                        <span className="text-right font-mono text-foreground/80">
                          {row.costUsd != null ? formatUsd(row.costUsd) : '— 未计费'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Timeline */}
      <Card className="glass card-hover animate-fade-in-left h-[400px]" style={{ animationDelay: '0.1s' }}>
        <CardContent className="p-4 h-full flex flex-col">
          <div className="text-sm font-medium mb-4">执行时间线</div>
          <div className="flex-1 flex flex-col justify-between relative">
            {/* Vertical Connecting Line */}
            <div className="absolute left-[15px] top-4 bottom-4 w-[2px] bg-gradient-to-b from-secondary/50 via-secondary to-secondary/50" />
            
            {Object.entries(phaseConfig).map(([phase, config]) => {
              const isActive = phase === progress.phase;
              const isPassed = Object.keys(phaseConfig).indexOf(phase) < Object.keys(phaseConfig).indexOf(progress.phase);
              // The step the run died on: marked stopped, never animated.
              const isHalted = isActive && isStopped;
              const PhaseIcon = config.icon;

              return (
                <div key={phase} className="flex items-center gap-4 relative z-10 bg-background/50 backdrop-blur-[2px] rounded-lg p-1 -ml-1">
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-full border-2 transition-all ${
                      isHalted
                        ? 'border-amber-500 bg-amber-500/10 text-amber-500 scale-110'
                        : isActive
                        ? 'border-primary bg-primary text-primary-foreground shadow-[0_0_10px_rgba(59,130,246,0.5)] scale-110'
                        : isPassed
                        ? 'border-success bg-success/10 text-success'
                        : 'border-muted bg-background text-muted-foreground'
                    }`}
                  >
                    {isHalted ? (
                      <XOctagon className="h-4 w-4" />
                    ) : isPassed ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      <PhaseIcon className={`h-4 w-4 ${isActive && isLive ? 'animate-pulse' : ''}`} />
                    )}
                  </div>
                  <div className="flex-1">
                    <div className={`text-sm transition-colors ${isHalted ? 'font-bold text-amber-600' : isActive ? 'font-bold text-primary' : isPassed ? 'text-foreground' : 'text-muted-foreground'}`}>
                      {config.label}
                    </div>
                  </div>
                  {isHalted && (
                    <span className="text-xs font-semibold text-amber-600">{statusLabel}</span>
                  )}
                  {isActive && isLive && (
                    <div className="flex items-center gap-2">
                      <span className="relative flex h-3 w-3">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-primary"></span>
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
