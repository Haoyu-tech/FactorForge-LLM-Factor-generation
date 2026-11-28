import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Square, Compass, Loader2, X } from 'lucide-react';
import { useLanguage } from '@/context/LanguageContext';
import { TaskConfig } from '@/types';
import { checkResearchDirection } from '@/services/api';
import type { DirectionCheckResult } from '@/services/api';
import { getDefaultMiningDirection } from '@/utils/miningDirections';
import { marketSelectionFrom, readSavedConfig } from '@/utils/marketSettings';
import { DirectionCheckReply } from '@/components/DirectionCheckReply';

/** One turn of the direction-check conversation shown above the input. */
interface ChatTurn {
  id: number;
  direction: string;
  status: 'checking' | 'done' | 'error' | 'started';
  result?: DirectionCheckResult;
  error?: string;
}

interface ChatInputProps {
  onSubmit: (config: TaskConfig) => void;
  onStop?: () => void;
  isRunning?: boolean;
  /** Why the last start was refused, e.g. a run is already active elsewhere. */
  startError?: string | null;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSubmit, onStop, isRunning = false, startError = null }) => {
  const { language } = useLanguage();
  const zh = language === 'zh';
  const [input, setInput] = useState('');
  const [useCustomMiningDirection, setUseCustomMiningDirection] = useState(false);
  const [config] = useState<Partial<TaskConfig>>({
    librarySuffix: '',
  });
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const threadEndRef = useRef<HTMLDivElement>(null);
  const turnIdRef = useRef(0);
  const checking = turns.some((t) => t.status === 'checking');

  const examplePrompts = [
    { label: zh ? '动量与反转' : 'Momentum & reversal', prompt: zh
      ? '在当前市场和股票池中研究动量与短期反转，结合成交量确认信号，以验证集 RankIC 和 RankICIR 为主要筛选依据。'
      : 'Research momentum and short-term reversal in the configured market and universe, confirm signals with volume, and prioritize validation RankIC and RankICIR.' },
    { label: zh ? '流动性与交易行为' : 'Liquidity & trading activity', prompt: zh
      ? '使用当前市场可用的成交量和交易行为字段，挖掘流动性变化因子，检验验证集 RankIC、稳定性、换手及交易成本。'
      : 'Use available volume and trading-activity fields in the configured market to research liquidity factors; evaluate validation RankIC, stability, turnover, and costs.' },
    { label: zh ? '低相关性新因子' : 'Low-correlation factors', prompt: zh
      ? '研究与现有因子库相关性较低的新因子，仅使用当前市场可用字段，以验证集 RankIC 和稳定性评价，保留测试集作独立检验。'
      : 'Research new factors with low correlation to the existing library using fields available in the configured market. Evaluate validation RankIC and stability, reserving the test set for independent evaluation.' },
  ];

  const canSubmit = !isRunning && !checking && (input.trim().length > 0 || useCustomMiningDirection);

  const startRun = (turnId: number, direction: string) => {
    const suffix = config.librarySuffix?.trim() || undefined;
    // The checked direction is passed as text, so a "random" Settings choice
    // cannot change between the check and the run.
    onSubmit({
      ...config,
      userInput: direction,
      useCustomMiningDirection: false,
      librarySuffix: suffix,
    } as TaskConfig);
    setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, status: 'started' } : t)));
  };

  // Sending asks the backend whether the stored data can test the direction.
  // Mining starts only from the reply, so a direction that needs missing data
  // gets an explanation and sources instead of unrelated formulas.
  const handleSubmit = async () => {
    if (!canSubmit) return;
    const direction = useCustomMiningDirection
      ? (getDefaultMiningDirection() || '价量因子挖掘')
      : input.trim();
    const selection = marketSelectionFrom(readSavedConfig());
    const id = ++turnIdRef.current;
    setTurns((prev) => [...prev, { id, direction, status: 'checking' }]);
    if (!useCustomMiningDirection) setInput('');
    try {
      const resp = await checkResearchDirection({
        direction,
        marketMode: selection.marketMode,
        dataSource: selection.dataSource,
      });
      if (!resp.success || !resp.data) throw new Error(resp.error || 'Check failed');
      const result = resp.data;
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, status: 'done', result } : t)));
    } catch (err: any) {
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, status: 'error', error: err?.message || String(err) } : t)));
    }
  };

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit();
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [input]);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 pb-6">
      <div className="container mx-auto px-6">
        
        {/* A start the backend refused: say so instead of failing silently. */}
        {startError && (
          <div className="mx-auto mb-3 max-w-3xl rounded-xl border border-amber-300 bg-amber-50/95 px-4 py-2.5 text-sm text-amber-900 shadow-sm">
            {startError}
          </div>
        )}

        {/* Example Prompts */}
        {turns.length > 0 && (
          <div className="mx-auto mb-3 max-w-3xl rounded-2xl border border-slate-200 bg-white/95 shadow-[0_18px_46px_rgba(15,23,42,.12)] backdrop-blur">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                {zh ? '研究方向数据检查' : 'Research direction data check'}
              </span>
              <button
                type="button"
                onClick={() => setTurns([])}
                disabled={checking}
                className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-40"
                title={zh ? '清空对话' : 'Clear conversation'}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="max-h-[52vh] space-y-4 overflow-y-auto px-4 py-3">
              {turns.map((turn) => (
                <div key={turn.id} className="space-y-2">
                  <div className="flex justify-end">
                    <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary/10 px-3 py-2 text-sm text-slate-800">
                      {turn.direction}
                    </div>
                  </div>
                  <div className="rounded-2xl rounded-bl-sm border border-slate-100 bg-slate-50/70 px-3 py-3">
                    {turn.status === 'checking' && (
                      <div className="flex items-center gap-2 text-sm text-slate-600">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        {zh ? '正在对照数据库字段检查这个方向需要的数据…' : 'Checking the data this direction needs against the database fields…'}
                      </div>
                    )}
                    {turn.status === 'error' && (
                      <div className="text-sm text-rose-700">{turn.error}</div>
                    )}
                    {(turn.status === 'done' || turn.status === 'started') && turn.result && (
                      <DirectionCheckReply
                        result={turn.result}
                        zh={zh}
                        disabled={isRunning || turn.status === 'started'}
                        onStart={(direction) => startRun(turn.id, direction)}
                        onUseSuggestion={(direction) => {
                          setUseCustomMiningDirection(false);
                          setInput(direction);
                          textareaRef.current?.focus();
                        }}
                      />
                    )}
                    {turn.status === 'started' && (
                      <div className="mt-2 text-xs font-semibold text-emerald-700">
                        {zh ? '已提交挖掘任务，可在仪表盘查看进度。' : 'Mining request sent. Follow progress on the dashboard.'}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={threadEndRef} />
            </div>
          </div>
        )}

        {!input && !isRunning && turns.length === 0 && (
          <div className="flex flex-wrap justify-center gap-2 mb-3 overflow-x-auto pb-2 scrollbar-hide">
            {examplePrompts.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => setInput(prompt.prompt)}
                className="glass rounded-xl px-4 py-2 text-sm text-muted-foreground hover:text-foreground hover:scale-105 transition-all whitespace-nowrap flex items-center gap-2 card-hover"
              >
                <Sparkles className="h-3 w-3" />
                {prompt.label}
              </button>
            ))}
          </div>
        )}

        {/* Main Input */}
        <div className="gradient-border">
          <div className="gradient-border-content">
            <div className="glass-strong rounded-xl p-4">
              {/* Icon bar: Custom mining direction etc. */}
              <div className="flex items-center gap-1 mb-3">
                <button
                  type="button"
                  onClick={() => setUseCustomMiningDirection((v) => !v)}
                  title={useCustomMiningDirection ? '使用设置中的挖掘方向（已开）' : '使用设置中的挖掘方向（点击开启）'}
                  className={`p-2 rounded-lg transition-all ${
                    useCustomMiningDirection
                      ? 'bg-primary/15 text-primary ring-1 ring-primary/30'
                      : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
                  }`}
                >
                  <Compass className="h-4 w-4" />
                </button>
                <span
                  className={`text-xs ml-1 ${
                    useCustomMiningDirection ? 'text-primary font-medium' : 'text-muted-foreground'
                  }`}
                >
                  {zh ? '自选挖掘方向' : 'Custom research directions'}
                </span>
              </div>
              <div className="flex items-end gap-3">
                <div className="flex-1">
                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={
                      isRunning
                        ? (zh ? '实验运行中，可切换页面查看进度' : 'Research is running. You can switch pages to view progress.')
                        : useCustomMiningDirection
                        ? (zh ? '将使用设置中选中的挖掘方向' : 'Using the research directions selected in Settings.')
                        : (zh ? '描述研究假设、因子方向或筛选目标…（Enter 发送，Shift+Enter 换行）' : 'Describe a hypothesis, factor idea, or selection goal… (Enter to send, Shift+Enter for a new line)')
                    }
                    disabled={isRunning}
                    className="w-full bg-transparent text-base placeholder:text-muted-foreground focus:outline-none resize-none"
                    rows={1}
                    style={{ maxHeight: '120px' }}
                  />
                </div>

                <div className="flex items-center gap-2">
                  {isRunning && onStop ? (
                    <button
                      onClick={onStop}
                      className="p-2.5 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-all hover:scale-105 active:scale-95"
                      title="中断实验"
                    >
                      <Square className="h-5 w-5" />
                    </button>
                  ) : (
                    <button
                      onClick={() => void handleSubmit()}
                      disabled={!canSubmit}
                      className="p-2.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:scale-105 active:scale-95"
                      title={canSubmit ? (zh ? '检查数据并回复 (Enter)' : 'Check the data and reply (Enter)') : (zh ? '请输入挖掘需求，或开启自选挖掘方向' : 'Type a direction, or turn on custom research directions')}
                    >
                      {checking ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
