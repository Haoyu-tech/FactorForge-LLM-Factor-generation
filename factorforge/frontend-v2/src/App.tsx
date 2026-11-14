import React, { useState, useEffect } from 'react';
import { HomePage } from '@/pages/HomePage';
import { MiningDashboardPage } from '@/pages/MiningDashboardPage';
import { FactorLibraryPage } from '@/pages/FactorLibraryPage';
import { BacktestPage } from '@/pages/BacktestPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { Layout } from '@/components/layout/Layout';
import type { PageId } from '@/components/layout/Layout';
import { TaskProvider, useTaskContext } from '@/context/TaskContext';
import { LanguageProvider } from '@/context/LanguageContext';

// The active page lives in localStorage so a refresh returns the user to the
// view they were on instead of dropping them back on Home.
const PAGE_STORAGE_KEY = 'quantaalpha_last_page';
const VALID_PAGES: readonly PageId[] = ['home', 'mining_dashboard', 'library', 'backtest', 'settings'];

const readLastPage = (): PageId => {
  try {
    const saved = localStorage.getItem(PAGE_STORAGE_KEY);
    if (saved && VALID_PAGES.includes(saved as PageId)) return saved as PageId;
  } catch {
    // Storage can be unavailable (private mode, blocked cookies); use the default.
  }
  return 'home';
};

// Inner component to access context
const AppContent: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<PageId>(readLastPage);
  const { miningTask } = useTaskContext();

  useEffect(() => {
    try {
      localStorage.setItem(PAGE_STORAGE_KEY, currentPage);
    } catch {
      // Losing the remembered page is not worth failing a render over.
    }
  }, [currentPage]);

  // Auto-switch to dashboard when task starts
  useEffect(() => {
    if (miningTask && miningTask.status === 'running' && currentPage === 'home') {
       // Only auto-redirect if we are on home and a new task starts
       // But wait, user requirement says: "Don't disconnect when going back to home"
       // So we should redirect to dashboard ONLY when a NEW task is created via ChatInput
       // The ChatInput in HomePage calls startMining.
       // We can detect this change.
       setCurrentPage('mining_dashboard');
    }
  }, [miningTask?.taskId]); // Only trigger on new task ID

  return (
    <>
      {/*
        Use display:none to hide non-current pages instead of conditional unmounting.
        This ensures that components are not unmounted when switching pages, so WebSocket/task state is not lost.
      */}
      <div style={{ display: currentPage === 'home' ? 'block' : 'none' }}>
        <HomePage onNavigate={setCurrentPage} />
      </div>
      <div style={{ display: currentPage === 'mining_dashboard' ? 'block' : 'none' }}>
        <MiningDashboardPage onNavigate={setCurrentPage} />
      </div>
      <div style={{ display: currentPage === 'library' ? 'block' : 'none' }}>
        <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
          <FactorLibraryPage />
        </Layout>
      </div>
      <div style={{ display: currentPage === 'backtest' ? 'block' : 'none' }}>
        <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
          <BacktestPage />
        </Layout>
      </div>
      <div style={{ display: currentPage === 'settings' ? 'block' : 'none' }}>
        <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
          <SettingsPage />
        </Layout>
      </div>
    </>
  );
};

export const App: React.FC = () => {
  return (
    <LanguageProvider>
      <TaskProvider>
        <AppContent />
      </TaskProvider>
    </LanguageProvider>
  );
};
