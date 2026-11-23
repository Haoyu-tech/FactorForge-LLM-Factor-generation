import React, { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Sigma } from 'lucide-react';
import { useLanguage } from '@/context/LanguageContext';
import { Card } from '@/components/ui/Card';
import { FactorDetail } from '@/components/FactorDetail';
import { readFactorPageParams } from '@/utils/factorPage';

/** factor.html?id=<factor id>&library=<library file>&market=<us|cn|crypto> */
export const FactorPage: React.FC = () => {
  const { language, setLanguage } = useLanguage();
  const params = useMemo(() => readFactorPageParams(window.location.search), []);
  const zh = language === 'zh';
  const [factorName, setFactorName] = useState<string | null>(null);

  // LanguageContext rewrites the title on every language switch; name the factor after it.
  useEffect(() => {
    if (factorName) document.title = `${factorName} — FactorForge`;
  }, [factorName, language]);

  return (
    <div className="min-h-screen bg-background research-grid">
      <header className="border-b border-white/10 bg-[#071b24] text-white">
        <div className="mx-auto flex h-16 max-w-[1480px] items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
          <a href="/" className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-[12px] bg-[#a7f3d0] text-[#071b24]">
              <Sigma className="h-5 w-5" strokeWidth={2.4} />
            </span>
            <span className="text-[17px] font-semibold tracking-[-0.02em]">FactorForge</span>
          </a>
          <div className="flex items-center gap-3">
            <a href="/" className="inline-flex items-center gap-1.5 text-sm text-slate-300 hover:text-white">
              <ArrowLeft className="h-4 w-4" />{zh ? '返回平台' : 'Back to FactorForge'}
            </a>
            <div data-no-translate="" className="flex items-center rounded-xl border border-white/10 bg-white/[0.05] p-1">
              {(['zh', 'en'] as const).map((item) => (
                <button
                  type="button"
                  key={item}
                  onClick={() => setLanguage(item)}
                  aria-pressed={language === item}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${
                    language === item ? 'bg-white text-[#071b24]' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {item === 'zh' ? '中' : 'EN'}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        <Card className="glass-strong">
          {params ? (
            <FactorDetail
              factorId={params.id}
              library={params.library}
              marketMode={params.marketMode || 'us'}
              onLoaded={(factor) => setFactorName(factor.factorName || factor.factor_name || params.id)}
            />
          ) : (
            <div className="p-10 text-center text-sm text-muted-foreground">
              {zh ? '链接缺少因子 id。' : 'This link has no factor id.'}
            </div>
          )}
        </Card>
      </main>
    </div>
  );
};
