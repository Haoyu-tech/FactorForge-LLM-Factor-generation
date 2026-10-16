import React from 'react';
import { Sigma, Database, BarChart3, Settings as SettingsIcon, Languages, Sparkles } from 'lucide-react';
import { useTaskContext } from '@/context/TaskContext';
import { useLanguage } from '@/context/LanguageContext';

export type PageId = 'home' | 'library' | 'backtest' | 'settings' | 'mining_dashboard';

interface LayoutProps {
  children: React.ReactNode;
  currentPage: PageId;
  onNavigate: (page: PageId) => void;
  showNavigation?: boolean;
}

export const Layout: React.FC<LayoutProps> = ({
  children,
  currentPage,
  onNavigate,
  showNavigation = true,
}) => {
  const { miningTask } = useTaskContext();
  const { language, setLanguage } = useLanguage();

  const handleNavClick = (itemId: PageId) => {
    if (itemId === 'home' && miningTask && miningTask.status !== 'idle') {
      onNavigate('mining_dashboard');
      return;
    }
    onNavigate(itemId);
  };

  const navItems = [
    { id: 'home' as const, zh: '因子挖掘', en: 'Research', icon: Sparkles },
    { id: 'library' as const, zh: '因子库', en: 'Library', icon: Database },
    { id: 'backtest' as const, zh: '组合回测', en: 'Backtest', icon: BarChart3 },
    { id: 'settings' as const, zh: '系统设置', en: 'Settings', icon: SettingsIcon },
  ];

  return (
    <div className="min-h-screen bg-background research-grid">
      <header className="fixed inset-x-0 top-0 z-40 border-b border-white/10 bg-[#071b24]/95 text-white shadow-[0_10px_30px_rgba(7,27,36,0.12)] backdrop-blur-xl">
        <div className="mx-auto flex h-[76px] max-w-[1480px] items-center justify-between px-4 sm:px-6 lg:px-8">
          <button
            type="button"
            className="group flex items-center gap-3 text-left"
            onClick={() => onNavigate('home')}
            aria-label={language === 'zh' ? '返回首页' : 'Go to home'}
          >
            <span className="relative flex h-11 w-11 items-center justify-center overflow-hidden rounded-[14px] bg-[#a7f3d0] text-[#071b24] shadow-[0_0_0_1px_rgba(167,243,208,.28)]">
              <Sigma className="h-6 w-6" strokeWidth={2.4} />
              <span className="absolute bottom-1 right-1 h-1.5 w-1.5 rounded-full bg-[#0f766e]" />
            </span>
            <span>
              <span className="block text-[19px] font-semibold tracking-[-0.02em]">FactorForge</span>
              <span className="block text-[10px] font-medium uppercase tracking-[0.18em] text-slate-400">
                {language === 'zh' ? '因子智研平台' : 'Quant Research OS'}
              </span>
            </span>
          </button>

          <div className="flex items-center gap-2 lg:gap-4">
            {showNavigation && (
              <nav className="hidden items-center gap-1 rounded-xl border border-white/10 bg-white/[0.04] p-1 md:flex">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = currentPage === item.id || (item.id === 'home' && currentPage === 'mining_dashboard');
                  return (
                    <button
                      type="button"
                      key={item.id}
                      onClick={() => handleNavClick(item.id)}
                      className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-all ${
                        isActive
                          ? 'bg-[#a7f3d0] text-[#071b24] shadow-sm'
                          : 'text-slate-300 hover:bg-white/[0.07] hover:text-white'
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                      <span>{language === 'zh' ? item.zh : item.en}</span>
                    </button>
                  );
                })}
              </nav>
            )}

            <div className="flex items-center rounded-xl border border-white/10 bg-white/[0.05] p-1" title={language === 'zh' ? '切换语言' : 'Switch language'}>
              <Languages className="mx-2 h-4 w-4 text-slate-400" />
              {(['zh', 'en'] as const).map((item) => (
                <button
                  type="button"
                  key={item}
                  onClick={() => setLanguage(item)}
                  aria-pressed={language === item}
                  className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-all ${
                    language === item ? 'bg-white text-[#071b24]' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {item === 'zh' ? '中' : 'EN'}
                </button>
              ))}
            </div>
          </div>
        </div>
      {showNavigation && (
        <nav aria-label={language === 'zh' ? '模块导航' : 'Module navigation'} className="grid grid-cols-4 gap-1 border-t border-white/10 px-3 py-2 md:hidden">
          {navItems.map(item => (
            <button type="button" key={item.id} onClick={() => handleNavClick(item.id)}
              className={`rounded-lg px-1 py-2 text-xs ${currentPage === item.id || (item.id === 'home' && currentPage === 'mining_dashboard') ? 'bg-[#a7f3d0] text-[#071b24]' : 'text-slate-300'}`}>
              {language === 'zh' ? item.zh : item.en}
            </button>
          ))}
        </nav>
      )}</header>

      <main className="relative z-10 pb-48 pt-[150px] md:pt-[100px]">
        <div className="mx-auto max-w-[1480px] px-4 sm:px-6 lg:px-8">{children}</div>
      </main>
    </div>
  );
};
