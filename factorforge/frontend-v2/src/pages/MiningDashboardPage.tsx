import React from 'react';
import { ProgressSidebar } from '@/components/ProgressSidebar';
import { LiveCharts } from '@/components/LiveCharts';
import { ChatInput } from '@/components/ChatInput';
import { FactorStatsRow } from '@/components/FactorStatsRow';
import { FactorList } from '@/components/FactorList';
import { FactorRadarChart } from '@/components/FactorRadarChart';
import { RoundFeedbackPanel } from '@/components/RoundFeedbackPanel';
import { experimentIdForTask } from '@/services/api';
import { useTaskContext } from '@/context/TaskContext';
import { Layout } from '@/components/layout/Layout';
import type { PageId } from '@/components/layout/Layout';

interface MiningDashboardPageProps {
  onNavigate?: (page: PageId) => void;
}

export const MiningDashboardPage: React.FC<MiningDashboardPageProps> = ({ onNavigate }) => {
  const {
    miningTask: task,
    miningEquityCurve: equityCurve,
    miningDrawdownCurve: drawdownCurve,
    startMining,
    stopMining,
    miningStartError,
  } = useTaskContext();

  // If no task, this page shouldn't be active (or show empty state)
  if (!task) {
    return (
      <Layout
        currentPage="home"
        onNavigate={onNavigate || (() => {})}
        showNavigation={!!onNavigate}
      >
        <div className="flex flex-col items-center justify-center min-h-[60vh] animate-fade-in-up">
          <p className="text-muted-foreground">当前无进行中的挖掘任务</p>
          <button 
            className="mt-4 text-primary hover:underline"
            onClick={() => onNavigate?.('home')}
          >
            返回主页
          </button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout
      currentPage="home"
      onNavigate={onNavigate || (() => {})}
      showNavigation={!!onNavigate}
    >
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1">
          <ProgressSidebar progress={task.progress} status={task.status} task={task} />
        </div>
        <div className="lg:col-span-3">
          <LiveCharts
            equityCurve={equityCurve}
            drawdownCurve={drawdownCurve}
            metrics={task.metrics || null}
            isRunning={task.status === 'running'}
            logs={task.logs}
          />
        </div>

        {/* New Rows - Full Width */}
        <div className="lg:col-span-4">
           <FactorStatsRow 
             metrics={task.metrics || null} 
             onBacktest={() => {
               // Set active library for backtest page
               if (task.config?.librarySuffix) {
                 const libName = `all_factors_library_${task.config.librarySuffix}.json`;
                 localStorage.setItem('quantaalpha_active_library', libName);
               } else {
                 localStorage.setItem('quantaalpha_active_library', 'all_factors_library.json');
               }
               onNavigate?.('backtest');
             }}
           />
        </div>
        <div className="lg:col-span-4">
           <FactorRadarChart
             title="Top 5 因子表现雷达图"
             market={task.config?.market}
             factors={(task.metrics?.top10Factors || []).map((f) => ({
               name: f.factorName,
               ic: f.ic,
               rankIc: f.rankIc,
               icir: f.icir,
               annualReturn: f.portfolioStats?.long_short?.annualizedNetReturn ?? f.annualReturn,
               maxDrawdown: f.portfolioStats?.long_short?.maxDrawdown ?? f.maxDrawdown,
             }))}
           />
        </div>
        <div className="lg:col-span-4">
           <FactorList metrics={task.metrics || null} />
        </div>
        <div className="lg:col-span-4">
           <RoundFeedbackPanel
             experimentId={experimentIdForTask(task)}
             isRunning={task.status === 'running'}
             marketMode={task.config?.marketMode}
           />
        </div>
      </div>

      {/* Bottom Chat Input */}
      <ChatInput
        onSubmit={startMining}
        onStop={stopMining}
        isRunning={task?.status === 'running'}
        startError={miningStartError}
      />
    </Layout>
  );
};
