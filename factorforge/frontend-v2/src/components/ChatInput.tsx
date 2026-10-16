import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Square, Compass } from 'lucide-react';
import { useLanguage } from '@/context/LanguageContext';
import { TaskConfig } from '@/types';

interface ChatInputProps {
  onSubmit: (config: TaskConfig) => void;
  onStop?: () => void;
  isRunning?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSubmit, onStop, isRunning = false }) => {
  const { language } = useLanguage();
  const zh = language === 'zh';
  const [input, setInput] = useState('');
  const [useCustomMiningDirection, setUseCustomMiningDirection] = useState(false);
  const [config] = useState<Partial<TaskConfig>>({
    librarySuffix: '',
  });
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  const canSubmit = !isRunning && (input.trim().length > 0 || useCustomMiningDirection);

  const handleSubmit = () => {
    if (!canSubmit) return;
    const suffix = config.librarySuffix?.trim() || undefined;
    onSubmit({
      userInput: input.trim(),
      useCustomMiningDirection,
      ...config,
      librarySuffix: suffix,
    } as TaskConfig);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
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
        
        {/* Example Prompts */}
        {!input && !isRunning && (
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
                      onClick={handleSubmit}
                      disabled={!canSubmit}
                      className="p-2.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:scale-105 active:scale-95"
                      title={canSubmit ? '发送 (Enter)' : '请输入挖掘需求，或开启自选挖掘方向'}
                    >
                      <Send className="h-5 w-5" />
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
