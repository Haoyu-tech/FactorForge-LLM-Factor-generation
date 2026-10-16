import React, { useEffect, useState } from 'react';
import { ArrowUpRight, BrainCircuit, BarChart3, Database, ShieldCheck, Wifi, WifiOff } from 'lucide-react';
import { ChatInput } from '@/components/ChatInput';
import { Layout } from '@/components/layout/Layout';
import type { PageId } from '@/components/layout/Layout';
import { useTaskContext } from '@/context/TaskContext';
import { useLanguage } from '@/context/LanguageContext';
import { getSystemConfig } from '@/services/api';

interface HomePageProps {
  onNavigate?: (page: PageId) => void;
}

export const HomePage: React.FC<HomePageProps> = ({ onNavigate }) => {
  const { backendAvailable, miningTask: task, startMining, stopMining } = useTaskContext();
  const { language } = useLanguage();
  const isZh = language === 'zh';
  const [systemInfo, setSystemInfo] = useState({
    train: '1987-01-01 ～ 2004-12-31',
    valid: '2005-01-03 ～ 2014-12-31',
    test: '2015-01-02 ～ 2025-12-31',
    dataSource: 'WRDS',
    lightgbmEnabled: false,
  });

  useEffect(() => {
    getSystemConfig().then((response) => {
      const env = response.data?.env || {};
      setSystemInfo({
        train: `${env.TRAIN_START_DATE || '1987-01-01'} ～ ${env.TRAIN_END_DATE || '2004-12-31'}`,
        valid: `${env.VALID_START_DATE || '2005-01-03'} ～ ${env.VALID_END_DATE || '2014-12-31'}`,
        test: `${env.TEST_START_DATE || '2015-01-02'} ～ ${env.TEST_END_DATE || '2025-12-31'}`,
        dataSource: String(env.DATA_SOURCE || 'wrds').toUpperCase(),
        lightgbmEnabled: String(env.MINING_LIGHTGBM_ENABLED || 'false').toLowerCase() === 'true',
      });
    }).catch(() => { /* retain safe display defaults */ });
  }, []);

  const features = [
    {
      page: 'home' as PageId,
      icon: BrainCircuit,
      index: '01',
      title: isZh ? 'AI 因子研究' : 'AI Factor Research',
      text: isZh ? '从研究假设到表达式、统计检验与迭代优化。' : 'From hypotheses to expressions, statistical tests, and iterative refinement.',
    },
    {
      page: 'library' as PageId,
      icon: Database,
      index: '02',
      title: isZh ? '多市场因子库' : 'Multi-Market Library',
      text: isZh ? '统一管理美股、A股与 Crypto 因子及完整证据。' : 'Manage US, China A-share, and Crypto factors with full evidence.',
    },
    {
      page: 'backtest' as PageId,
      icon: BarChart3,
      index: '03',
      title: isZh ? '独立样本外回测' : 'Independent OOS Tests',
      text: isZh ? '严格隔离训练、验证和测试，支持 Expanding Window。' : 'Strict train, validation, and test isolation with expanding windows.',
    },
  ];

  return (
    <Layout currentPage="home" onNavigate={onNavigate || (() => {})} showNavigation={!!onNavigate}>
      <section className="animate-fade-in-up pb-10 pt-5">
        <div className="grid items-center gap-10 lg:grid-cols-[1.18fr_.82fr] lg:gap-16">
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-900/10 bg-white/80 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-800 shadow-sm">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              {isZh ? 'AI 原生量化研究工作台' : 'AI-native quantitative research workspace'}
            </div>
            <h1 className="max-w-4xl text-5xl font-semibold leading-[1.06] tracking-[-0.045em] text-[#071b24] sm:text-6xl xl:text-[72px]">
              {isZh ? '把投资直觉，' : 'Turn market intuition'}
              <span className="block text-emerald-700">{isZh ? '锻造成可验证的因子。' : 'into testable factors.'}</span>
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-7 text-slate-600 sm:text-lg">
              {isZh
                ? 'FactorForge 连接因子生成、统计检验、资产定价与样本外回测，让每个结论都能追溯到数据。'
                : 'FactorForge connects factor generation, statistical testing, asset pricing, and out-of-sample backtesting so every conclusion is traceable to data.'}
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <span className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-sm font-medium ${
                backendAvailable === true
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                  : backendAvailable === false
                    ? 'border-amber-200 bg-amber-50 text-amber-800'
                    : 'border-slate-200 bg-white text-slate-600'
              }`}>
                {backendAvailable === true ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
                {backendAvailable === true
                  ? (isZh ? '研究引擎已连接' : 'Research engine connected')
                  : backendAvailable === false
                    ? (isZh ? '研究引擎未连接' : 'Research engine offline')
                    : (isZh ? '正在检查服务' : 'Checking service')}
              </span>
              <span className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-600">
                <ShieldCheck className="h-4 w-4 text-emerald-700" />
                {isZh ? '训练 / 验证 / 测试严格隔离' : 'Strict train / validation / test isolation'}
              </span>
            </div>
          </div>

          <aside className="relative overflow-hidden rounded-[28px] border border-white/10 bg-[#071b24] p-7 text-white shadow-[0_30px_80px_rgba(7,27,36,.20)] sm:p-8">
            <div className="absolute -right-20 -top-20 h-52 w-52 rounded-full bg-emerald-300/10 blur-2xl" />
            <div className="relative">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">{isZh ? '研究环境' : 'Research environment'}</p>
                  <h2 className="mt-2 text-2xl font-semibold">{isZh ? '当前数据分区' : 'Current data split'}</h2>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/[0.06] px-3 py-2 text-xs font-semibold text-slate-300">{systemInfo.dataSource}</div>
              </div>
              <div className="mt-8 space-y-5">
                {[
                  [isZh ? '训练' : 'TRAIN', systemInfo.train],
                  [isZh ? '验证' : 'VALID', systemInfo.valid],
                  [isZh ? '测试' : 'TEST', systemInfo.test],
                ].map(([label, range], index) => (
                  <div key={label}>
                    <div className="mb-2 flex items-center justify-between gap-4 text-xs">
                      <span className="font-semibold tracking-[0.12em] text-slate-400">{label}</span>
                      <span className="font-mono text-slate-200">{range}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                      <div className={`h-full rounded-full ${index === 2 ? 'bg-emerald-300' : 'bg-slate-500'}`} style={{ width: '100%' }} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-8 border-t border-white/10 pt-5 text-sm leading-6 text-slate-400">
                {systemInfo.lightgbmEnabled
                  ? (isZh ? '单因子评价 + LightGBM 组合训练已启用' : 'Single-factor evaluation + LightGBM ensemble enabled')
                  : (isZh ? '当前使用逐因子独立评价' : 'Individual factor evaluation is active')}
              </div>
            </div>
          </aside>
        </div>

        <div className="mt-14 grid gap-4 md:grid-cols-3">
          {features.map(({ page, icon: Icon, index, title, text }) => (
            <button
              type="button"
              key={index}
              onClick={() => onNavigate?.(page)}
              className="group rounded-[22px] border border-slate-200/80 bg-white/85 p-6 text-left shadow-[0_12px_36px_rgba(15,23,42,.05)] transition-all hover:-translate-y-1 hover:border-emerald-300 hover:shadow-[0_18px_46px_rgba(15,118,110,.10)]"
            >
              <div className="flex items-start justify-between">
                <span className="flex h-11 w-11 items-center justify-center rounded-[14px] bg-emerald-50 text-emerald-800"><Icon className="h-5 w-5" /></span>
                <span className="font-mono text-xs text-slate-400">{index}</span>
              </div>
              <h3 className="mt-7 text-lg font-semibold tracking-[-0.02em] text-[#071b24]">{title}</h3>
              <p className="mt-2 min-h-[48px] text-sm leading-6 text-slate-500">{text}</p>
              <span className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-emerald-700">
                {isZh ? '进入模块' : 'Open module'} <ArrowUpRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </span>
            </button>
          ))}
        </div>
      </section>

      <ChatInput onSubmit={startMining} onStop={stopMining} isRunning={task?.status === 'running'} />
    </Layout>
  );
};
