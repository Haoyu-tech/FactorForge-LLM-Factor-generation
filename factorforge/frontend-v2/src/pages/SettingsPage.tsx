import React, { useState, useEffect } from 'react';
import { useLanguage } from '@/context/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Settings, Save, RotateCcw, Eye, EyeOff, Check, X, AlertCircle, Loader2, Database, Sliders, Box, Cpu, Compass, Shuffle } from 'lucide-react';
import { getSystemConfig, updateSystemConfig, healthCheck, getWrdsStatus, startWrdsBuild, getWrdsBuild, getChinaStatus, startChinaBuild, getChinaBuild, getCryptoStatus, startCryptoBuild, getCryptoBuild } from '@/services/api';
import { REFERENCE_MINING_DIRECTIONS, getDirectionLabel, type MiningDirectionItem } from '@/utils/miningDirections';

interface SampleDateRange {
  trainStartDate: string;
  trainEndDate: string;
  validStartDate: string;
  validEndDate: string;
  testStartDate: string;
  testEndDate: string;
}

const US_DATE_RANGE: SampleDateRange = {
  trainStartDate: '1987-01-01', trainEndDate: '2010-12-31',
  validStartDate: '2011-01-01', validEndDate: '2014-12-31',
  testStartDate: '2015-01-01', testEndDate: '2025-12-31',
};

const CN_DATE_RANGE: SampleDateRange = {
  trainStartDate: '2010-07-01', trainEndDate: '2017-12-29',
  validStartDate: '2018-01-02', validEndDate: '2020-12-31',
  testStartDate: '2021-01-04', testEndDate: '2025-12-31',
};

const CRYPTO_DATE_RANGE: SampleDateRange = {
  trainStartDate: '2020-01-01', trainEndDate: '2022-12-31',
  validStartDate: '2023-01-01', validEndDate: '2023-12-31',
  testStartDate: '2024-01-01', testEndDate: '2025-12-31',
};

interface SystemConfig {
  // LLM
  llmProvider: 'codex_cli' | 'claude_cli' | 'openai_api';
  apiKey: string;
  apiUrl: string;
  modelName: string;
  codexModel: string;
  claudeModel: string;
  // Qlib
  qlibDataPath: string;
  resultsDir: string;
  dataSource: 'qlib' | 'wrds' | 'cn_duckdb' | 'binance_futures';
  marketMode: 'us' | 'cn' | 'crypto';
  cnDuckdbPath: string;
  cnQlibPath: string;
  cnExcludeSt: boolean;
  cnExcludeNewStocks: boolean;
  cnExcludeChiNext: boolean;
  cnExcludeStar: boolean;
  cnExcludeBse: boolean;
  cnNewStockMinTradingDays: number;
  wrdsRoot: string;
  wrdsQlibPath: string;
  cryptoQlibPath: string;
  cryptoMaxSymbols: number;
  cryptoMinListingDays: number;
  // Parameters
  defaultNumDirections: number;
  defaultMaxRounds: number;
  defaultMarket: 'csi300' | 'csi500' | 'sme_composite' | 'sp500' | 'binance_usdm';
  evaluationFrequencies: Array<'day' | 'week' | 'month'>;
  trainStartDate: string;
  trainEndDate: string;
  validStartDate: string;
  validEndDate: string;
  testStartDate: string;
  testEndDate: string;
  marketDateRanges: { us: SampleDateRange; cn: SampleDateRange; crypto: SampleDateRange };
  // Advanced
  parallelExecution: boolean;
  qualityGateEnabled: boolean;
  miningLightgbmEnabled: boolean;
  backtestTimeout: number;
  defaultLibrarySuffix: string;
  // Mining direction: use selected directions / random
  miningDirectionMode: 'selected' | 'random';
  selectedMiningDirectionIndices: number[];
}

const DEFAULT_CONFIG: SystemConfig = {
  llmProvider: 'codex_cli',
  apiKey: '',
  apiUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  modelName: 'deepseek-v3',
  codexModel: '',
  claudeModel: 'sonnet',
  qlibDataPath: '',
  resultsDir: '',
  dataSource: 'wrds',
  marketMode: 'us',
  cnDuckdbPath: '/mnt/e/A股数据库/AKshare交易/data/market.db',
  cnQlibPath: '/mnt/e/A股数据库/AKshare交易/data/qlib_cn_market',
  cnExcludeSt: true,
  cnExcludeNewStocks: true,
  cnExcludeChiNext: false,
  cnExcludeStar: false,
  cnExcludeBse: false,
  cnNewStockMinTradingDays: 375,
  wrdsRoot: '/mnt/d/桌面文件/US stock research/wrds',
  wrdsQlibPath: '/home/alpha/projects/QuantaAlpha/data/qlib/wrds_sp500',
  cryptoQlibPath: '/home/alpha/projects/QuantaAlpha/data/qlib/binance_usdm',
  cryptoMaxSymbols: 100,
  cryptoMinListingDays: 90,
  defaultNumDirections: 2,
  defaultMaxRounds: 3,
  defaultMarket: 'sp500',
  evaluationFrequencies: ['day', 'week', 'month'],
  ...US_DATE_RANGE,
  marketDateRanges: { us: US_DATE_RANGE, cn: CN_DATE_RANGE, crypto: CRYPTO_DATE_RANGE },
  parallelExecution: true,
  qualityGateEnabled: true,
  miningLightgbmEnabled: false,
  backtestTimeout: 600,
  defaultLibrarySuffix: '',
  miningDirectionMode: 'selected',
  selectedMiningDirectionIndices: REFERENCE_MINING_DIRECTIONS.map((_, index) => index),
};

type SettingsTab = 'api' | 'data' | 'params' | 'directions';

export const SettingsPage: React.FC = () => {
  const { language } = useLanguage();
  const [config, setConfig] = useState<SystemConfig>(DEFAULT_CONFIG);
  const [activeTab, setActiveTab] = useState<SettingsTab>('api');
  const [showApiKey, setShowApiKey] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [factorLibraries, setFactorLibraries] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [wrdsStatus, setWrdsStatus] = useState<any>(null);
  const [checkingWrds, setCheckingWrds] = useState(false);
  const [buildingWrds, setBuildingWrds] = useState(false);
  const [chinaStatus, setChinaStatus] = useState<any>(null);
  const [checkingChina, setCheckingChina] = useState(false);
  const [buildingChina, setBuildingChina] = useState(false);
  const [cryptoStatus, setCryptoStatus] = useState<any>(null);
  const [checkingCrypto, setCheckingCrypto] = useState(false);
  const [buildingCrypto, setBuildingCrypto] = useState(false);

  // Load config from backend on mount
  useEffect(() => {
    loadConfig();
  }, []);

  // Keep the indicator current after an automatic backend restart. The old
  // implementation checked only once when the page mounted, so a transient
  // outage left a permanent red "未连接" label until a full page reload.
  useEffect(() => {
    let disposed = false;

    const refreshBackendStatus = async () => {
      try {
        await healthCheck();
        if (!disposed) setBackendStatus('online');
      } catch {
        if (!disposed) setBackendStatus('offline');
      }
    };

    const handleFocus = () => void refreshBackendStatus();
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') void refreshBackendStatus();
    };
    const intervalId = window.setInterval(refreshBackendStatus, 5000);

    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      disposed = true;
      window.clearInterval(intervalId);
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);

  const loadConfig = async () => {
    setIsLoading(true);
    setError(null);

    // Check backend health
    try {
      await healthCheck();
      setBackendStatus('online');
    } catch {
      setBackendStatus('offline');
    }

    // Load config
    try {
      // The frontend can become ready slightly before the backend after a restart.
      // Retry transient startup failures so a stale cache warning is not left on screen.
      let resp: Awaited<ReturnType<typeof getSystemConfig>> | undefined;
      let lastError: unknown;
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          resp = await getSystemConfig();
          break;
        } catch (err) {
          lastError = err;
          if (attempt < 2) {
            await new Promise((resolve) => window.setTimeout(resolve, 800 * (attempt + 1)));
          }
        }
      }
      if (!resp) throw lastError;
      if (resp.success && resp.data) {
        const env = resp.data.env || {};
        const saved = localStorage.getItem('quantaalpha_config');
        let miningDirectionMode = DEFAULT_CONFIG.miningDirectionMode;
        let selectedMiningDirectionIndices = DEFAULT_CONFIG.selectedMiningDirectionIndices;
        if (saved) {
          try {
            const parsed = JSON.parse(saved);
            if (parsed.miningDirectionMode) miningDirectionMode = parsed.miningDirectionMode;
            if (Array.isArray(parsed.selectedMiningDirectionIndices) && parsed.selectedMiningDirectionIndices.length > 3) {
              selectedMiningDirectionIndices = parsed.selectedMiningDirectionIndices;
            }
          } catch { /* use defaults */ }
        }
        const activeMarketMode: 'us' | 'cn' | 'crypto' = env.MARKET_MODE === 'crypto' ? 'crypto' : (env.MARKET_MODE === 'cn' ? 'cn' : 'us');
        const legacyRange: SampleDateRange = {
          trainStartDate: env.TRAIN_START_DATE || '',
          trainEndDate: env.TRAIN_END_DATE || '',
          validStartDate: env.VALID_START_DATE || '',
          validEndDate: env.VALID_END_DATE || '',
          testStartDate: env.TEST_START_DATE || '',
          testEndDate: env.TEST_END_DATE || '',
        };
        const usRange: SampleDateRange = {
          trainStartDate: env.US_TRAIN_START_DATE || (activeMarketMode === 'us' && legacyRange.trainStartDate) || US_DATE_RANGE.trainStartDate,
          trainEndDate: env.US_TRAIN_END_DATE || (activeMarketMode === 'us' && legacyRange.trainEndDate) || US_DATE_RANGE.trainEndDate,
          validStartDate: env.US_VALID_START_DATE || (activeMarketMode === 'us' && legacyRange.validStartDate) || US_DATE_RANGE.validStartDate,
          validEndDate: env.US_VALID_END_DATE || (activeMarketMode === 'us' && legacyRange.validEndDate) || US_DATE_RANGE.validEndDate,
          testStartDate: env.US_TEST_START_DATE || (activeMarketMode === 'us' && legacyRange.testStartDate) || US_DATE_RANGE.testStartDate,
          testEndDate: env.US_TEST_END_DATE || (activeMarketMode === 'us' && legacyRange.testEndDate) || US_DATE_RANGE.testEndDate,
        };
        const cnRange: SampleDateRange = {
          trainStartDate: env.CN_TRAIN_START_DATE || (activeMarketMode === 'cn' && legacyRange.trainStartDate) || CN_DATE_RANGE.trainStartDate,
          trainEndDate: env.CN_TRAIN_END_DATE || (activeMarketMode === 'cn' && legacyRange.trainEndDate) || CN_DATE_RANGE.trainEndDate,
          validStartDate: env.CN_VALID_START_DATE || (activeMarketMode === 'cn' && legacyRange.validStartDate) || CN_DATE_RANGE.validStartDate,
          validEndDate: env.CN_VALID_END_DATE || (activeMarketMode === 'cn' && legacyRange.validEndDate) || CN_DATE_RANGE.validEndDate,
          testStartDate: env.CN_TEST_START_DATE || (activeMarketMode === 'cn' && legacyRange.testStartDate) || CN_DATE_RANGE.testStartDate,
          testEndDate: env.CN_TEST_END_DATE || (activeMarketMode === 'cn' && legacyRange.testEndDate) || CN_DATE_RANGE.testEndDate,
        };
        const cryptoRange: SampleDateRange = {
          trainStartDate: env.CRYPTO_TRAIN_START_DATE || (activeMarketMode === 'crypto' && legacyRange.trainStartDate) || CRYPTO_DATE_RANGE.trainStartDate,
          trainEndDate: env.CRYPTO_TRAIN_END_DATE || (activeMarketMode === 'crypto' && legacyRange.trainEndDate) || CRYPTO_DATE_RANGE.trainEndDate,
          validStartDate: env.CRYPTO_VALID_START_DATE || (activeMarketMode === 'crypto' && legacyRange.validStartDate) || CRYPTO_DATE_RANGE.validStartDate,
          validEndDate: env.CRYPTO_VALID_END_DATE || (activeMarketMode === 'crypto' && legacyRange.validEndDate) || CRYPTO_DATE_RANGE.validEndDate,
          testStartDate: env.CRYPTO_TEST_START_DATE || (activeMarketMode === 'crypto' && legacyRange.testStartDate) || CRYPTO_DATE_RANGE.testStartDate,
          testEndDate: env.CRYPTO_TEST_END_DATE || (activeMarketMode === 'crypto' && legacyRange.testEndDate) || CRYPTO_DATE_RANGE.testEndDate,
        };
        const activeRange = activeMarketMode === 'crypto' ? cryptoRange : (activeMarketMode === 'cn' ? cnRange : usRange);
        setConfig({
          llmProvider: String(env.USE_CLAUDE_CLI || '').toLowerCase() === 'true'
            ? 'claude_cli'
            : String(env.USE_CODEX_CLI || '').toLowerCase() === 'true' ? 'codex_cli' : 'openai_api',
          apiKey: env.OPENAI_API_KEY || '',
          apiUrl: env.OPENAI_BASE_URL || DEFAULT_CONFIG.apiUrl,
          modelName: env.CHAT_MODEL || DEFAULT_CONFIG.modelName,
          codexModel: env.CODEX_CLI_MODEL || '',
          claudeModel: env.CLAUDE_CLI_MODEL || 'sonnet',
          qlibDataPath: env.QLIB_DATA_DIR || '',
          resultsDir: env.DATA_RESULTS_DIR || '',
          dataSource: (env.DATA_SOURCE === 'binance_futures' ? 'binance_futures' : env.DATA_SOURCE === 'cn_duckdb' ? 'cn_duckdb' : env.DATA_SOURCE === 'qlib' ? 'qlib' : 'wrds'),
          marketMode: activeMarketMode,
          cnDuckdbPath: env.CN_DUCKDB_PATH || DEFAULT_CONFIG.cnDuckdbPath,
          cnQlibPath: env.CN_QLIB_DATA_DIR || DEFAULT_CONFIG.cnQlibPath,
          cnExcludeSt: String(env.CN_EXCLUDE_ST || 'true').toLowerCase() === 'true',
          cnExcludeNewStocks: String(env.CN_EXCLUDE_NEW_STOCKS || 'true').toLowerCase() === 'true',
          cnExcludeChiNext: String(env.CN_EXCLUDE_CHINEXT || 'false').toLowerCase() === 'true',
          cnExcludeStar: String(env.CN_EXCLUDE_STAR || 'false').toLowerCase() === 'true',
          cnExcludeBse: String(env.CN_EXCLUDE_BSE || 'false').toLowerCase() === 'true',
          cnNewStockMinTradingDays: Number(env.CN_NEW_STOCK_MIN_TRADING_DAYS || 375),
          wrdsRoot: env.WRDS_ROOT || DEFAULT_CONFIG.wrdsRoot,
          wrdsQlibPath: env.WRDS_QLIB_DATA_DIR || DEFAULT_CONFIG.wrdsQlibPath,
          cryptoQlibPath: env.CRYPTO_QLIB_DATA_DIR || DEFAULT_CONFIG.cryptoQlibPath,
          cryptoMaxSymbols: Number(env.CRYPTO_MAX_SYMBOLS || 100),
          cryptoMinListingDays: Number(env.CRYPTO_MIN_LISTING_DAYS || 90),
          defaultNumDirections: 2,
          defaultMaxRounds: 3,
          defaultMarket: (env.DEFAULT_MARKET || 'sp500') as SystemConfig['defaultMarket'],
          evaluationFrequencies: String(env.MINING_EVALUATION_FREQUENCIES || 'day')
            .split(',')
            .map((value) => value.trim())
            .filter((value): value is 'day' | 'week' | 'month' =>
              ['day', 'week', 'month'].includes(value)
            ),
          ...activeRange,
          marketDateRanges: { us: usRange, cn: cnRange, crypto: cryptoRange },
          parallelExecution: true,
          qualityGateEnabled: true,
          miningLightgbmEnabled: String(env.MINING_LIGHTGBM_ENABLED || 'false').toLowerCase() === 'true',
          backtestTimeout: 600,
          defaultLibrarySuffix: '',
          miningDirectionMode,
          selectedMiningDirectionIndices,
        });
        setFactorLibraries(resp.data.factorLibraries || []);
      }
    } catch (err: any) {
      console.error('Failed to load config:', err);
      // Fallback to localStorage
      const saved = localStorage.getItem('quantaalpha_config');
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          const parsedMode: 'us' | 'cn' | 'crypto' = parsed.marketMode === 'crypto' ? 'crypto' : (parsed.marketMode === 'cn' ? 'cn' : 'us');
          const legacySavedRange: SampleDateRange = {
            trainStartDate: parsed.trainStartDate || (parsedMode === 'crypto' ? CRYPTO_DATE_RANGE.trainStartDate : parsedMode === 'cn' ? CN_DATE_RANGE.trainStartDate : US_DATE_RANGE.trainStartDate),
            trainEndDate: parsed.trainEndDate || (parsedMode === 'crypto' ? CRYPTO_DATE_RANGE.trainEndDate : parsedMode === 'cn' ? CN_DATE_RANGE.trainEndDate : US_DATE_RANGE.trainEndDate),
            validStartDate: parsed.validStartDate || (parsedMode === 'crypto' ? CRYPTO_DATE_RANGE.validStartDate : parsedMode === 'cn' ? CN_DATE_RANGE.validStartDate : US_DATE_RANGE.validStartDate),
            validEndDate: parsed.validEndDate || (parsedMode === 'crypto' ? CRYPTO_DATE_RANGE.validEndDate : parsedMode === 'cn' ? CN_DATE_RANGE.validEndDate : US_DATE_RANGE.validEndDate),
            testStartDate: parsed.testStartDate || (parsedMode === 'crypto' ? CRYPTO_DATE_RANGE.testStartDate : parsedMode === 'cn' ? CN_DATE_RANGE.testStartDate : US_DATE_RANGE.testStartDate),
            testEndDate: parsed.testEndDate || (parsedMode === 'crypto' ? CRYPTO_DATE_RANGE.testEndDate : parsedMode === 'cn' ? CN_DATE_RANGE.testEndDate : US_DATE_RANGE.testEndDate),
          };
          const marketDateRanges = parsed.marketDateRanges || {
            us: parsedMode === 'us' ? legacySavedRange : US_DATE_RANGE,
            cn: parsedMode === 'cn' ? legacySavedRange : CN_DATE_RANGE,
            crypto: parsedMode === 'crypto' ? legacySavedRange : CRYPTO_DATE_RANGE,
          };
          setConfig({
            ...DEFAULT_CONFIG,
            ...parsed,
            ...marketDateRanges[parsedMode],
            marketDateRanges,
            selectedMiningDirectionIndices: Array.isArray(parsed.selectedMiningDirectionIndices)
              ? parsed.selectedMiningDirectionIndices
              : DEFAULT_CONFIG.selectedMiningDirectionIndices,
          });
        } catch {
          // use defaults
        }
      }
      setError('无法从后端加载配置，显示的是本地缓存配置');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    const validRange = (range: SampleDateRange) => (
      range.trainStartDate <= range.trainEndDate &&
      range.trainEndDate < range.validStartDate &&
      range.validStartDate <= range.validEndDate &&
      range.validEndDate < range.testStartDate &&
      range.testStartDate <= range.testEndDate
    );
    if (!validRange(config.marketDateRanges.us) || !validRange(config.marketDateRanges.cn) || !validRange(config.marketDateRanges.crypto)) {
      setError('美股、A股和 Crypto 各自的训练、验证、测试区间都必须按顺序排列且不能重叠');
      setIsSaving(false);
      return;
    }

    // Always save to localStorage as backup
    localStorage.setItem('quantaalpha_config', JSON.stringify(config));

    // Try to save to backend
    try {
      const update: Record<string, string> = {};
      update.USE_CODEX_CLI = config.llmProvider === 'codex_cli' ? 'true' : 'false';
      update.USE_CLAUDE_CLI = config.llmProvider === 'claude_cli' ? 'true' : 'false';
      if (config.llmProvider === 'codex_cli') {
        update.CODEX_CLI_MODEL = config.codexModel;
      }
      if (config.llmProvider === 'claude_cli') {
        update.CLAUDE_CLI_MODEL = config.claudeModel;
      }
      if (config.llmProvider === 'openai_api' && config.apiKey && !config.apiKey.includes('...')) {
        update.OPENAI_API_KEY = config.apiKey;
      }
      if (config.apiUrl) update.OPENAI_BASE_URL = config.apiUrl;
      if (config.modelName) {
        update.CHAT_MODEL = config.modelName;
        update.REASONING_MODEL = config.modelName;
      }
      if (config.qlibDataPath) update.QLIB_DATA_DIR = config.qlibDataPath;
      if (config.resultsDir) update.DATA_RESULTS_DIR = config.resultsDir;
      update.DATA_SOURCE = config.marketMode === 'crypto' ? 'binance_futures' : (config.marketMode === 'cn' ? 'cn_duckdb' : config.dataSource);
      update.MARKET_MODE = config.marketMode;
      update.DEFAULT_MARKET = config.defaultMarket;
      update.CN_DUCKDB_PATH = config.cnDuckdbPath;
      update.CN_QLIB_DATA_DIR = config.cnQlibPath;
      update.CN_EXCLUDE_ST = config.cnExcludeSt ? 'true' : 'false';
      update.CN_EXCLUDE_NEW_STOCKS = config.cnExcludeNewStocks ? 'true' : 'false';
      update.CN_EXCLUDE_CHINEXT = config.cnExcludeChiNext ? 'true' : 'false';
      update.CN_EXCLUDE_STAR = config.cnExcludeStar ? 'true' : 'false';
      update.CN_EXCLUDE_BSE = config.cnExcludeBse ? 'true' : 'false';
      update.CN_NEW_STOCK_MIN_TRADING_DAYS = String(config.cnNewStockMinTradingDays);
      update.WRDS_ROOT = config.wrdsRoot;
      update.WRDS_QLIB_DATA_DIR = config.wrdsQlibPath;
      update.CRYPTO_QLIB_DATA_DIR = config.cryptoQlibPath;
      update.CRYPTO_MAX_SYMBOLS = String(config.cryptoMaxSymbols);
      update.CRYPTO_MIN_LISTING_DAYS = String(config.cryptoMinListingDays);
      update.TRAIN_START_DATE = config.trainStartDate;
      update.TRAIN_END_DATE = config.trainEndDate;
      update.VALID_START_DATE = config.validStartDate;
      update.VALID_END_DATE = config.validEndDate;
      update.TEST_START_DATE = config.testStartDate;
      update.TEST_END_DATE = config.testEndDate;
      update.US_TRAIN_START_DATE = config.marketDateRanges.us.trainStartDate;
      update.US_TRAIN_END_DATE = config.marketDateRanges.us.trainEndDate;
      update.US_VALID_START_DATE = config.marketDateRanges.us.validStartDate;
      update.US_VALID_END_DATE = config.marketDateRanges.us.validEndDate;
      update.US_TEST_START_DATE = config.marketDateRanges.us.testStartDate;
      update.US_TEST_END_DATE = config.marketDateRanges.us.testEndDate;
      update.CN_TRAIN_START_DATE = config.marketDateRanges.cn.trainStartDate;
      update.CN_TRAIN_END_DATE = config.marketDateRanges.cn.trainEndDate;
      update.CN_VALID_START_DATE = config.marketDateRanges.cn.validStartDate;
      update.CN_VALID_END_DATE = config.marketDateRanges.cn.validEndDate;
      update.CN_TEST_START_DATE = config.marketDateRanges.cn.testStartDate;
      update.CN_TEST_END_DATE = config.marketDateRanges.cn.testEndDate;
      update.CRYPTO_TRAIN_START_DATE = config.marketDateRanges.crypto.trainStartDate;
      update.CRYPTO_TRAIN_END_DATE = config.marketDateRanges.crypto.trainEndDate;
      update.CRYPTO_VALID_START_DATE = config.marketDateRanges.crypto.validStartDate;
      update.CRYPTO_VALID_END_DATE = config.marketDateRanges.crypto.validEndDate;
      update.CRYPTO_TEST_START_DATE = config.marketDateRanges.crypto.testStartDate;
      update.CRYPTO_TEST_END_DATE = config.marketDateRanges.crypto.testEndDate;
      update.MINING_EVALUATION_FREQUENCIES = config.evaluationFrequencies.join(',');
      update.MINING_LIGHTGBM_ENABLED = config.miningLightgbmEnabled ? 'true' : 'false';

      if (Object.keys(update).length > 0) {
        await updateSystemConfig(update);
      }
    } catch (err: any) {
      console.warn('Failed to save to backend, saved locally:', err);
    }

    setIsSaved(true);
    setIsDirty(false);
    setIsSaving(false);
    setTimeout(() => setIsSaved(false), 2000);
  };

  const handleCheckWrds = async () => {
    setCheckingWrds(true);
    try {
      const response = await getWrdsStatus();
      setWrdsStatus(response.data || { error: response.error });
    } catch (err: any) {
      setWrdsStatus({ error: err?.message || 'WRDS 检查失败' });
    } finally {
      setCheckingWrds(false);
    }
  };

  const handleBuildWrds = async () => {
    setBuildingWrds(true);
    setError(null);
    try {
      const response = await startWrdsBuild(
        config.marketDateRanges.us.trainStartDate,
        config.marketDateRanges.us.testEndDate,
      );
      const taskId = response.data?.taskId;
      if (!taskId) throw new Error(response.error || '无法启动 WRDS 构建');
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const status = await getWrdsBuild(taskId);
        const task = status.data?.task;
        if (task?.status === 'completed') break;
        if (task?.status === 'failed') throw new Error(task.progress?.message || 'WRDS 构建失败');
      }
      await handleCheckWrds();
    } catch (err: any) {
      setError(err?.message || 'WRDS 构建失败');
    } finally {
      setBuildingWrds(false);
    }
  };

  const handleCheckChina = async () => {
    setCheckingChina(true);
    try {
      const response = await getChinaStatus();
      setChinaStatus(response.data || { error: response.error });
    } catch (err: any) {
      setChinaStatus({ error: err?.message || 'A股数据检查失败' });
    } finally { setCheckingChina(false); }
  };

  const handleBuildChina = async () => {
    setBuildingChina(true); setError(null);
    try {
      const response = await startChinaBuild('2010-01-04', config.marketDateRanges.cn.testEndDate);
      const taskId = response.data?.taskId;
      if (!taskId) throw new Error(response.error || '无法启动A股数据构建');
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const status = await getChinaBuild(taskId);
        const task = status.data?.task;
        if (task?.status === 'completed') break;
        if (task?.status === 'failed') throw new Error(task.progress?.message || 'A股数据构建失败');
      }
      await handleCheckChina();
    } catch (err: any) { setError(err?.message || 'A股数据构建失败'); }
    finally { setBuildingChina(false); }
  };

  const handleCheckCrypto = async () => {
    setCheckingCrypto(true);
    try {
      const response = await getCryptoStatus();
      setCryptoStatus(response.data || { error: response.error });
    } catch (err: any) {
      setCryptoStatus({ error: err?.message || '币安永续数据检查失败' });
    } finally { setCheckingCrypto(false); }
  };

  const handleBuildCrypto = async () => {
    setBuildingCrypto(true); setError(null);
    try {
      const range = config.marketDateRanges.crypto;
      const response = await startCryptoBuild(range.trainStartDate, range.testEndDate, config.cryptoMaxSymbols);
      const taskId = response.data?.taskId;
      if (!taskId) throw new Error(response.error || '无法启动币安永续数据构建');
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const status = await getCryptoBuild(taskId);
        const task = status.data?.task;
        if (task?.status === 'completed') break;
        if (task?.status === 'failed') throw new Error(task.progress?.message || '币安永续数据构建失败');
      }
      await handleCheckCrypto();
    } catch (err: any) { setError(err?.message || '币安永续数据构建失败'); }
    finally { setBuildingCrypto(false); }
  };

  const handleMarketModeChange = (mode: 'us' | 'cn' | 'crypto') => {
    setConfig((prev) => {
      const currentRange: SampleDateRange = {
        trainStartDate: prev.trainStartDate, trainEndDate: prev.trainEndDate,
        validStartDate: prev.validStartDate, validEndDate: prev.validEndDate,
        testStartDate: prev.testStartDate, testEndDate: prev.testEndDate,
      };
      const marketDateRanges = {
        ...prev.marketDateRanges,
        [prev.marketMode]: currentRange,
      };
      const nextRange = marketDateRanges[mode];
      return mode === 'crypto' ? {
        ...prev, ...nextRange, marketDateRanges,
        marketMode: 'crypto', dataSource: 'binance_futures', defaultMarket: 'binance_usdm',
        evaluationFrequencies: ['day', 'week', 'month'],
      } : mode === 'cn' ? {
        ...prev, ...nextRange, marketDateRanges,
        marketMode: 'cn', dataSource: 'cn_duckdb', defaultMarket: 'csi300',
        evaluationFrequencies: ['day', 'week', 'month'],
      } : {
        ...prev, ...nextRange, marketDateRanges,
        marketMode: 'us', dataSource: prev.dataSource === 'qlib' ? 'qlib' : 'wrds', defaultMarket: 'sp500',
      };
    });
    setIsDirty(true);
  };

  const handleReset = () => {
    if (confirm(language === 'en' ? 'Reset to default settings?' : '确定要重置为默认配置吗？')) {
      setConfig(DEFAULT_CONFIG);
      setIsDirty(true);
    }
  };

  const updateConfigField = (key: keyof SystemConfig, value: any) => {
    setConfig((prev) => {
      const next = { ...prev, [key]: value };
      if ([
        'trainStartDate', 'trainEndDate', 'validStartDate',
        'validEndDate', 'testStartDate', 'testEndDate',
      ].includes(String(key))) {
        next.marketDateRanges = {
          ...prev.marketDateRanges,
          [prev.marketMode]: {
            ...prev.marketDateRanges[prev.marketMode],
            [key]: value,
          },
        };
      }
      return next;
    });
    setIsDirty(true);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-3 text-muted-foreground">加载配置中...</span>
      </div>
    );
  }

  const TabButton = ({ id, label, icon: Icon }: { id: SettingsTab; label: string; icon: any }) => (
    <button
      onClick={() => setActiveTab(id)}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
        activeTab === id
          ? 'bg-primary text-primary-foreground shadow-lg scale-105'
          : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
      }`}
    >
      <Icon className="h-4 w-4" />
      <span className="font-medium">{label}</span>
    </button>
  );

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Settings className="h-8 w-8 text-primary" />
            系统配置
          </h1>
          <p className="text-muted-foreground mt-1">
            管理 API 连接、数据源及实验参数
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={handleReset}>
            <RotateCcw className="h-4 w-4 mr-2" />
            重置
          </Button>
          <Button variant="primary" onClick={handleSave} disabled={!isDirty || isSaving}>
            {isSaving ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            保存配置
          </Button>
        </div>
      </div>

      {/* Status Banners */}
      {isSaved && (
        <div className="glass rounded-lg p-4 flex items-center gap-3 bg-success/10 border-success/50 animate-fade-in-down">
          <Check className="h-5 w-5 text-success" />
          <span className="text-success">配置已保存</span>
        </div>
      )}
      {isDirty && !isSaved && (
        <div className="glass rounded-lg p-4 flex items-center gap-3 bg-warning/10 border-warning/50 animate-fade-in-down">
          <X className="h-5 w-5 text-warning" />
          <span className="text-warning">有未保存的更改</span>
        </div>
      )}
      {error && (
        <div className="glass rounded-lg p-4 flex items-center gap-3 bg-warning/10 border-warning/50">
          <AlertCircle className="h-5 w-5 text-warning flex-shrink-0" />
          <span className="text-sm text-warning flex-1">{error}</span>
          {error === '无法从后端加载配置，显示的是本地缓存配置' && (
            <Button variant="outline" size="sm" onClick={loadConfig} disabled={isLoading}>
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : '重新连接'}
            </Button>
          )}
        </div>
      )}

      {/* Tabs Navigation */}
      <div className="flex gap-2 p-1 bg-secondary/20 rounded-xl w-fit flex-wrap">
        <TabButton id="api" label="配置 API" icon={Cpu} />
        <TabButton id="data" label="数据路径" icon={Database} />
        <TabButton id="params" label="默认参数" icon={Sliders} />
        <TabButton id="directions" label="挖掘方向" icon={Compass} />
      </div>

      {/* Tab Content */}
      <div className="grid grid-cols-1 gap-6">
        
        {/* API Configuration Tab */}
        {activeTab === 'api' && (
          <Card className="glass card-hover animate-fade-in-up">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                🤖 LLM 模型配置
                <Badge variant="default">核心</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-2">调用方式</label>
                <select
                  value={config.llmProvider}
                  onChange={(e) => updateConfigField('llmProvider', e.target.value as SystemConfig['llmProvider'])}
                  className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                >
                  <option value="codex_cli">本地 GPT / Codex CLI（无需 API Key）</option>
                  <option value="claude_cli">本地 Claude / Claude CLI（复用登录）</option>
                  <option value="openai_api">OpenAI 兼容 API</option>
                </select>
              </div>

              {config.llmProvider === 'codex_cli' && (
                <div>
                  <label className="block text-sm font-medium mb-2">Codex 模型（可留空）</label>
                  <input
                    type="text"
                    value={config.codexModel}
                    onChange={(e) => updateConfigField('codexModel', e.target.value)}
                    placeholder="留空使用 Codex 当前默认模型"
                    className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    复用 Windows Codex 已登录账号；修改后重启后端生效。
                  </p>
                </div>
              )}

              {config.llmProvider === 'claude_cli' && (
                <div>
                  <label className="block text-sm font-medium mb-2">Claude 模型</label>
                  <input
                    type="text"
                    value={config.claudeModel}
                    onChange={(e) => updateConfigField('claudeModel', e.target.value)}
                    placeholder="sonnet（也可填 haiku、opus 或留空）"
                    className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    复用本机 Claude Code 登录；默认使用 sonnet 控制成本。保存后重启后端生效。
                  </p>
                </div>
              )}

              {config.llmProvider === 'openai_api' && (<>
              <div>
                <label className="block text-sm font-medium mb-2">
                  API Key <span className="text-destructive">*</span>
                </label>
                <div className="flex gap-2">
                  <input
                    type={showApiKey ? 'text' : 'password'}
                    value={config.apiKey}
                    onChange={(e) => updateConfigField('apiKey', e.target.value)}
                    placeholder="sk-..."
                    className="flex-1 rounded-lg border border-input bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  />
                  <Button
                    variant="outline"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="px-3"
                  >
                    {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  支持 OpenAI 兼容格式的 API Key（如 DashScope, DeepSeek 等）
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">API Base URL</label>
                <input
                  type="text"
                  value={config.apiUrl}
                  onChange={(e) => updateConfigField('apiUrl', e.target.value)}
                  placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1"
                  className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  LLM 服务端点地址
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">模型名称</label>
                <select
                  value={config.modelName}
                  onChange={(e) => updateConfigField('modelName', e.target.value)}
                  className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                >
                  <option value="deepseek-v3">DeepSeek V3</option>
                  <option value="qwen38-27b">Auckland Qwen3.8-27B</option>
                  <option value="gemma-4-26B-A4B-it">Auckland Gemma 4 26B A4B</option>
                  <option value="deepseek-r1">DeepSeek R1</option>
                  <option value="qwen-max">Qwen Max</option>
                  <option value="qwen-plus">Qwen Plus</option>
                  <option value="gpt-4">GPT-4</option>
                  <option value="gpt-4-turbo">GPT-4 Turbo</option>
                  <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                </select>
              </div>
              </>)}

              {/* Connection Status */}
              <div className="pt-4 border-t border-border/50">
                <div className="flex items-center gap-3">
                  <div
                    className={`h-3 w-3 rounded-full ${
                      backendStatus === 'online'
                        ? 'bg-success animate-pulse'
                        : backendStatus === 'offline'
                        ? 'bg-destructive'
                        : 'bg-warning animate-pulse'
                    }`}
                  />
                  <span className="text-sm">
                    后端连接状态：
                    {backendStatus === 'online' ? <span className="text-success font-medium">已连接</span> : 
                     backendStatus === 'offline' ? <span className="text-destructive font-medium">未连接</span> : 
                     '检测中...'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Data Path Configuration Tab */}
        {activeTab === 'data' && (
          <Card className="glass card-hover animate-fade-in-up">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                📊 数据存储路径
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-2">{language === 'en' ? 'Market mode' : '市场模式'}</label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <button type="button" onClick={() => handleMarketModeChange('us')}
                    className={`rounded-xl border p-4 text-left ${config.marketMode === 'us' ? 'border-primary bg-primary/10' : 'border-border'}`}>
                    <div className="font-semibold">🇺🇸 {language === 'en' ? 'US stocks' : '美股模式'}</div>
                    <div className="text-xs text-muted-foreground mt-1">S&amp;P 500 · GICS · WRDS FF3/FF5/Mom</div>
                  </button>
                  <button type="button" onClick={() => handleMarketModeChange('cn')}
                    className={`rounded-xl border p-4 text-left ${config.marketMode === 'cn' ? 'border-primary bg-primary/10' : 'border-border'}`}>
                    <div className="font-semibold">🇨🇳 {language === 'en' ? 'China A shares' : 'A股模式'}</div>
                    <div className="text-xs text-muted-foreground mt-1">{language === 'zh' ? "沪深300 / 中证500 / 中小综指 · 申万 · Barra" : "CSI 300 / CSI 500 / SME Composite \u00b7 Shenwan \u00b7 Barra"}</div>
                  </button>
                  <button type="button" onClick={() => handleMarketModeChange('crypto')}
                    className={`rounded-xl border p-4 text-left ${config.marketMode === 'crypto' ? 'border-primary bg-primary/10' : 'border-border'}`}>
                    <div className="font-semibold">₿ {language === 'en' ? 'Crypto perpetuals' : 'Crypto 永续合约'}</div>
                    <div className="text-xs text-muted-foreground mt-1">{language === 'zh' ? "Binance USDⓈ-M · USDT 本位 · 24×7" : "Binance USD\u24c8-M \u00b7 USDT-margined \u00b7 24/7"}</div>
                  </button>
                </div>
              </div>

              {config.marketMode === 'us' && <div>
                <label className="block text-sm font-medium mb-2">主数据源</label>
                <select value={config.dataSource}
                  onChange={(event) => updateConfigField('dataSource', event.target.value as 'qlib' | 'wrds')}
                  className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm">
                  <option value="qlib">现有 Qlib 数据</option>
                  <option value="wrds">WRDS：CRSP 动态 S&amp;P 500 + Compustat + Fama–French</option>
                </select>
              </div>}

              {config.marketMode === 'us' && config.dataSource === 'wrds' && (
                <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">WRDS 根目录</label>
                    <input
                      type="text"
                      value={config.wrdsRoot}
                      onChange={(event) => updateConfigField('wrdsRoot', event.target.value)}
                      className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm font-mono"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      对应 Windows 的 D:/桌面文件/US stock research/wrds。原始文件保持在该目录，不复制 Kelly 153 压缩包。
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">WRDS 生成的 Qlib 目录</label>
                    <input
                      type="text"
                      value={config.wrdsQlibPath}
                      onChange={(event) => updateConfigField('wrdsQlibPath', event.target.value)}
                      className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm font-mono"
                    />
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button variant="outline" onClick={handleCheckWrds} disabled={checkingWrds}>
                      {checkingWrds && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                      检查 WRDS 数据
                    </Button>
                    <Button variant="primary" onClick={handleBuildWrds} disabled={buildingWrds}>
                      {buildingWrds && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                      构建/刷新动态 S&amp;P 500 Qlib
                    </Button>
                  </div>
                  {wrdsStatus && (
                    <div className="text-sm rounded-lg bg-background/70 p-3 space-y-1">
                      {wrdsStatus.error ? (
                        <div className="text-destructive">{wrdsStatus.error}</div>
                      ) : (
                        <>
                          <div>WRDS 文件：{wrdsStatus.ready ? '齐全' : '缺少必要文件'}</div>
                          <div>Qlib 数据：{wrdsStatus.qlib?.built ? '已构建' : '尚未构建'}</div>
                          <div>FF 日频范围：{wrdsStatus.factor_ranges?.ff5_mom?.start} ～ {wrdsStatus.factor_ranges?.ff5_mom?.end}</div>
                          <div>标识口径：PERMNO；成分口径：按 MbrStartDt/MbrEndDt 动态替换</div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              )}

              {config.marketMode === 'cn' && (
                <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 space-y-4">
                  <div><label className="block text-sm font-medium mb-2">{language === 'zh' ? "A股 DuckDB（只读原始库）" : "China A-share DuckDB (read-only source)"}</label>
                    <input value={config.cnDuckdbPath} onChange={(e) => updateConfigField('cnDuckdbPath', e.target.value)}
                      className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm font-mono" />
                    <p className="text-xs text-muted-foreground mt-1">{language === 'zh' ? "仅读取股票日频、财务、成分、ST和申万行业表；忽略 ETF、基金和分钟表。" : "Reads daily stock prices, financials, constituents, ST status, and Shenwan industries. ETF, fund, and minute tables are excluded."}</p>
                  </div>
                  <div><label className="block text-sm font-medium mb-2">{language === 'zh' ? "A股生成的 Qlib 目录" : "China A-share Qlib directory"}</label>
                    <input value={config.cnQlibPath} onChange={(e) => updateConfigField('cnQlibPath', e.target.value)}
                      className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm font-mono" />
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button variant="outline" onClick={handleCheckChina} disabled={checkingChina}>
                      {checkingChina && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}{language === 'zh' ? "检查A股数据库" : "Check A-share database"}
                    </Button>
                    <Button variant="primary" onClick={handleBuildChina} disabled={buildingChina}>
                      {buildingChina && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}{language === 'zh' ? "构建/刷新A股 Qlib" : "Build / refresh A-share Qlib"}
                    </Button>
                  </div>
                  {chinaStatus && <div className="text-sm rounded-lg bg-background/70 p-3 space-y-1">
                    {chinaStatus.error ? <div className="text-destructive">{chinaStatus.error}</div> : <>
                      <div>原始库：{chinaStatus.ready ? '可用' : '缺少必要表'}（{chinaStatus.sizeGb} GB）</div>
                      <div>日频：{chinaStatus.daily?.start} ～ {chinaStatus.daily?.end}，{chinaStatus.daily?.stocks} 只</div>
                      <div>生成数据：{chinaStatus.qlib?.built ? '已构建' : '尚未构建'}</div>
                      <div className="text-warning">CSI 300/500 官方快照前按历史流动性和市值重建并标记为近似，绝不倒填当前成分。</div>
                    </>}
                  </div>}
                </div>
              )}

              {config.marketMode === 'crypto' && (
                <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">{language === 'zh' ? "币安永续 Qlib 目录" : "Binance perpetual Qlib directory"}</label>
                    <input value={config.cryptoQlibPath} onChange={(e) => updateConfigField('cryptoQlibPath', e.target.value)}
                      className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm font-mono" />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div><label className="block text-sm font-medium mb-2">{language === 'zh' ? "合约数量（按24小时成交额）" : "Number of contracts (by 24-hour turnover)"}</label>
                      <input type="number" min={10} max={300} value={config.cryptoMaxSymbols}
                        onChange={(e) => updateConfigField('cryptoMaxSymbols', Number(e.target.value))}
                        className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm" />
                    </div>
                    <div><label className="block text-sm font-medium mb-2">{language === 'zh' ? "最短上市天数" : "Minimum days since listing"}</label>
                      <input type="number" min={0} max={3650} value={config.cryptoMinListingDays}
                        onChange={(e) => updateConfigField('cryptoMinListingDays', Number(e.target.value))}
                        className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm" />
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">{language === 'zh' ? "仅下载 USDT 本位 USDⓈ-M PERPETUAL 日频数据；不包含币本位、交割合约和现货。公开行情接口无需 API Key。" : "Downloads daily USDT-margined USD\u24c8-M perpetual data only. Coin-margined, delivery futures, and spot markets are excluded. Public market data requires no API key."}</p>
                  <div className="flex flex-wrap gap-3">
                    <Button variant="outline" onClick={handleCheckCrypto} disabled={checkingCrypto}>
                      {checkingCrypto && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}{language === 'zh' ? "检查币安永续数据" : "Check Binance perpetual data"}
                    </Button>
                    <Button variant="primary" onClick={handleBuildCrypto} disabled={buildingCrypto}>
                      {buildingCrypto && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}{language === 'zh' ? "构建/刷新 USDT 永续 Qlib" : "Build / refresh USDT perpetual Qlib"}
                    </Button>
                  </div>
                  {cryptoStatus && <div className="text-sm rounded-lg bg-background/70 p-3 space-y-1">
                    {cryptoStatus.error ? <div className="text-destructive">{cryptoStatus.error}</div> : <>
                      <div>{language === 'zh' ? 'Qlib 数据：' : 'Qlib data: '}{cryptoStatus.built ? (language === 'zh' ? '已构建' : 'Built') : (language === 'zh' ? '尚未构建' : 'Not built')}</div>
                      <div>{language === 'zh' ? "合约数量：" : "Contracts: "}{cryptoStatus.symbols || 0}</div>
                      <div>{language === 'zh' ? "日期范围：" : "Date range: "}{cryptoStatus.start || '—'} ～ {cryptoStatus.end || '—'}</div>
                      <div>{language === 'zh' ? "市场：Binance USDⓈ-M USDT 永续" : "Market: Binance USD\u24c8-M USDT perpetuals"}</div>
                    </>}
                  </div>}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium mb-2">
                  Qlib 数据目录 <span className="text-destructive">*</span>
                </label>
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    value={config.qlibDataPath}
                    onChange={(e) => updateConfigField('qlibDataPath', e.target.value)}
                    placeholder="/path/to/qlib/cn_data"
                    className="flex-1 rounded-lg border border-input bg-background px-4 py-2 text-sm font-mono focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-1 ml-6">
                  需包含 calendars/, features/, instruments/ 等 Qlib 标准数据子目录
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  实验结果输出目录
                </label>
                <div className="flex items-center gap-2">
                  <Box className="h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    value={config.resultsDir}
                    onChange={(e) => updateConfigField('resultsDir', e.target.value)}
                    placeholder="/path/to/results"
                    className="flex-1 rounded-lg border border-input bg-background px-4 py-2 text-sm font-mono focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-1 ml-6">
                  用于存放挖掘出的因子、回测报告及日志文件
                </p>
              </div>

              {factorLibraries.length > 0 && (
                <div className="bg-secondary/20 rounded-lg p-4 mt-4">
                  <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                    <Check className="h-4 w-4 text-success" />
                    已识别的因子库
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {factorLibraries.map((lib, idx) => (
                      <Badge key={idx} variant="outline" className="bg-background/50">
                        {lib}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Default Parameters Tab */}
        {activeTab === 'params' && (
          <Card className="glass card-hover animate-fade-in-up">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                ⚙️ 实验默认参数
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium mb-2">并行方向数</label>
                  <input
                    type="number"
                    value={config.defaultNumDirections}
                    onChange={(e) => updateConfigField('defaultNumDirections', parseInt(e.target.value))}
                    min={1}
                    max={10}
                    className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    单次实验同时探索的独立方向数量 (1-10)
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">进化轮次</label>
                  <input
                    type="number"
                    value={config.defaultMaxRounds}
                    onChange={(e) => updateConfigField('defaultMaxRounds', parseInt(e.target.value))}
                    min={1}
                    max={20}
                    className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    因子自我进化和优化的最大迭代次数 (1-20)
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">默认市场</label>
                  <select
                    value={config.defaultMarket}
                    onChange={(e) => updateConfigField('defaultMarket', e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  >
                    <option value="csi300">CSI 300 (沪深300)</option>
                    <option value="csi500">CSI 500 (中证500)</option>
                    <option value="sp500">S&P 500</option>
                    <option value="binance_usdm">Binance USDT 永续</option>
                  </select>
                </div>

                {config.marketMode === 'cn' && <div className="md:col-span-2 rounded-xl border border-border/60 p-4">
                  <div className="font-medium mb-3">A股动态样本过滤</div>
                  <div className="flex flex-wrap gap-5">
                    <label className="flex items-center gap-2"><input type="checkbox" checked={config.cnExcludeSt}
                      onChange={(e) => updateConfigField('cnExcludeSt', e.target.checked)} />剔除当期 ST / *ST</label>
                    <label className="flex items-center gap-2"><input type="checkbox" checked={config.cnExcludeNewStocks}
                      onChange={(e) => updateConfigField('cnExcludeNewStocks', e.target.checked)} />剔除次新股</label>
                    <label className="flex items-center gap-2"><input type="checkbox" checked={config.cnExcludeChiNext}
                      onChange={(e) => updateConfigField('cnExcludeChiNext', e.target.checked)} />剔除创业板（300/301）</label>
                    <label className="flex items-center gap-2"><input type="checkbox" checked={config.cnExcludeStar}
                      onChange={(e) => updateConfigField('cnExcludeStar', e.target.checked)} />剔除科创板（688）</label>
                    <label className="flex items-center gap-2"><input type="checkbox" checked={config.cnExcludeBse}
                      onChange={(e) => updateConfigField('cnExcludeBse', e.target.checked)} />剔除北交所</label>
                    <label className="flex items-center gap-2">最少上市交易日
                      <input type="number" min={0} max={2000} value={config.cnNewStockMinTradingDays}
                        onChange={(e) => updateConfigField('cnNewStockMinTradingDays', Number(e.target.value))}
                        className="w-28 rounded-lg border border-input bg-background px-3 py-2" /></label>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">过滤按每个历史交易日执行，默认 375 个交易日；不会用今天的 ST 状态回填历史。</p>
                </div>}

                <div>
                  <label className="block text-sm font-medium mb-2">回测超时 (秒)</label>
                  <input
                    type="number"
                    value={config.backtestTimeout}
                    onChange={(e) => updateConfigField('backtestTimeout', parseInt(e.target.value))}
                    min={60}
                    max={3600}
                    className="w-full rounded-lg border border-input bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    单次回测最大执行时间 (秒)
                  </p>
                </div>

                <div className="md:col-span-2">
                  <label className="block text-sm font-medium mb-2">默认因子库名称后缀</label>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground font-mono">all_factors_library_</span>
                    <input
                      type="text"
                      value={config.defaultLibrarySuffix}
                      onChange={(e) => {
                        const val = e.target.value.replace(/[^a-zA-Z0-9_\-]/g, '');
                        updateConfigField('defaultLibrarySuffix', val);
                      }}
                      placeholder="例如 momentum_v1 (留空则无后缀)"
                      className="flex-1 rounded-lg border border-input bg-background px-4 py-2 text-sm font-mono focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                    />
                    <span className="text-sm text-muted-foreground font-mono">.json</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    生成的因子将保存到此文件。支持字母、数字、下划线。
                  </p>
                </div>
              </div>

              <div className="pt-4 border-t border-border/50 space-y-4">
                <div>
                  <h4 className="text-sm font-medium mb-1">
                    {config.marketMode === 'crypto' ? 'Crypto 独立训练、验证和测试区间' : (config.marketMode === 'cn' ? 'A 股独立训练、验证和测试区间' : '美股独立训练、验证和测试区间')}
                  </h4>
                  <p className="text-xs text-muted-foreground mb-3">
                    切换市场时会自动保存当前区间并加载另一市场的独立区间，两者不会互相覆盖。
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {([
                      ['训练集', 'trainStartDate', 'trainEndDate'],
                      ['验证集', 'validStartDate', 'validEndDate'],
                      ['测试集', 'testStartDate', 'testEndDate'],
                    ] as const).map(([label, startKey, endKey]) => (
                      <div key={label} className="rounded-lg border border-border/50 p-3">
                        <div className="font-medium mb-2">{label}</div>
                        <div className="space-y-2">
                          <input type="date" value={config[startKey]} onChange={(event) => updateConfigField(startKey, event.target.value)}
                            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" />
                          <input type="date" value={config[endKey]} onChange={(event) => updateConfigField(endKey, event.target.value)}
                            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" />
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    区间必须依次衔接且不能重叠；测试集同时作为 Long/Short 和资产定价检验区间。
                  </p>
                </div>

                <div className="pt-3 border-t border-border/50">
                  <h4 className="text-sm font-medium mb-3">挖掘评价调仓频率</h4>
                  <div className="flex flex-wrap gap-4">
                    {([
                      ['day', '日频'],
                      ['week', '周频'],
                      ['month', '月频'],
                    ] as const).map(([value, label]) => (
                      <label key={value} className="flex items-center gap-2 cursor-pointer rounded-lg border border-border/50 px-4 py-3 hover:bg-secondary/20">
                        <input
                          type="checkbox"
                          checked={config.evaluationFrequencies.includes(value)}
                          onChange={(event) => {
                            const next = event.target.checked
                              ? [...config.evaluationFrequencies, value]
                              : config.evaluationFrequencies.filter((item) => item !== value);
                            if (next.length > 0) updateConfigField('evaluationFrequencies', next);
                          }}
                          className="h-5 w-5 rounded border-input text-primary focus:ring-primary"
                        />
                        <span className="font-medium">{label}</span>
                      </label>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    每个选中频率都会计算 Long、Short、Long–Short、换手成本和十组单调性，并反馈给 LLM；至少保留一种。
                  </p>
                </div>

                <div className="pt-3 border-t border-border/50">
                  <h4 className="text-sm font-medium mb-3">{config.marketMode === 'crypto' ? '永续合约评价处理' : (config.marketMode === 'cn' ? '申万行业与 Barra 风格处理' : 'GICS 行业处理')}</h4>
                  <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 space-y-2 text-sm">
                    {config.marketMode === 'crypto' ? <>
                      <div><span className="font-semibold">市场：</span>币安 USDⓈ-M USDT 本位永续，UTC 24×7</div>
                      <div><span className="font-semibold">横截面：</span>全市场排名与去均值，不使用股票行业分类</div>
                      <div><span className="font-semibold">特有字段：</span>资金费率、主动买入占比、成交额、成交笔数、上市天数</div>
                      <div><span className="font-semibold">评价：</span>IC/RankIC、Long–Short Sharpe、回撤、换手、手续费及资金费率敏感性</div>
                    </> : config.marketMode === 'cn' ? <>
                      <div><span className="font-semibold">默认主口径：</span>申万一级行业内排名与中性化</div>
                      <div><span className="font-semibold">稳健性检验：</span>申万二级行业；三级用于集中度诊断</div>
                      <div><span className="font-semibold">风格暴露：</span>规模、价值、盈利、动量、波动、流动性、杠杆、成长</div>
                      <div><span className="font-semibold">资产定价：</span>本地历史数据派生 CN FF3、FF3+Mom、FF5、FF5+Mom</div>
                    </> : <>
                      <div><span className="font-semibold">默认主口径：</span>gsector 板块内排名与行业中性化</div>
                      <div><span className="font-semibold">稳健性检验：</span>ggroup 行业组内排名</div>
                      <div><span className="font-semibold">暴露诊断：</span>gsector、ggroup、gind、gsubind</div>
                    </>}
                  </div>
                </div>

                <h4 className="text-sm font-medium pt-2">高级控制</h4>
                
                <label className="flex items-center gap-3 cursor-pointer group p-3 rounded-lg border border-border/50 hover:bg-secondary/20 transition-all">
                  <input
                    type="checkbox"
                    checked={config.parallelExecution}
                    onChange={(e) => updateConfigField('parallelExecution', e.target.checked)}
                    className="h-5 w-5 rounded border-input text-primary focus:ring-primary"
                  />
                  <div className="flex-1">
                    <div className="font-medium group-hover:text-primary transition-colors">
                      启用并行执行
                    </div>
                    <div className="text-xs text-muted-foreground">
                      允许多个挖掘方向同时运行，显著加快实验速度，但会增加系统负载
                    </div>
                  </div>
                </label>

                <label className="flex items-center gap-3 cursor-pointer group p-3 rounded-lg border border-border/50 hover:bg-secondary/20 transition-all">
                  <input
                    type="checkbox"
                    checked={config.miningLightgbmEnabled}
                    onChange={(e) => updateConfigField('miningLightgbmEnabled', e.target.checked)}
                    className="h-5 w-5 rounded border-input text-primary focus:ring-primary"
                  />
                  <div className="flex-1">
                    <div className="font-medium group-hover:text-primary transition-colors">
                      挖掘阶段启用 LightGBM 组合训练
                    </div>
                    <div className="text-xs text-muted-foreground">
                      默认关闭：逐个评价候选因子并建立因子库。开启后额外训练组合模型；独立模型回测不受影响。
                    </div>
                  </div>
                </label>

                <label className="flex items-center gap-3 cursor-pointer group p-3 rounded-lg border border-border/50 hover:bg-secondary/20 transition-all">
                  <input
                    type="checkbox"
                    checked={config.qualityGateEnabled}
                    onChange={(e) => updateConfigField('qualityGateEnabled', e.target.checked)}
                    className="h-5 w-5 rounded border-input text-primary focus:ring-primary"
                  />
                  <div className="flex-1">
                    <div className="font-medium group-hover:text-primary transition-colors">
                      启用质量门控
                    </div>
                    <div className="text-xs text-muted-foreground">
                      自动检测并过滤低质量因子，防止其进入下一轮迭代，保证最终结果质量
                    </div>
                  </div>
                </label>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Mining Direction Tab */}
        {activeTab === 'directions' && (
          <Card className="glass card-hover animate-fade-in-up">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Compass className="h-5 w-5" />
                挖掘方向（价量 + WRDS 基本面 + 资产定价）
              </CardTitle>
              <p className="text-sm text-muted-foreground mt-1">
                选择作为默认参考的挖掘方向；启动任务时可从中选用或随机一条
              </p>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-3">使用方式</label>
                <div className="flex flex-wrap gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="miningDirectionMode"
                      checked={config.miningDirectionMode === 'selected'}
                      onChange={() => updateConfigField('miningDirectionMode', 'selected')}
                      className="h-4 w-4 text-primary focus:ring-primary"
                    />
                    <span>使用下方选中的方向（启动时从选中中取一条或按业务逻辑使用）</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="miningDirectionMode"
                      checked={config.miningDirectionMode === 'random'}
                      onChange={() => updateConfigField('miningDirectionMode', 'random')}
                      className="h-4 w-4 text-primary focus:ring-primary"
                    />
                    <span className="flex items-center gap-1.5">
                      <Shuffle className="h-4 w-4" />
                      随机（从选中方向中随机选一条）
                    </span>
                  </label>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-3">
                  <label className="text-sm font-medium">参考方向（可多选）</label>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        updateConfigField(
                          'selectedMiningDirectionIndices',
                          REFERENCE_MINING_DIRECTIONS.map((_: MiningDirectionItem, i: number) => i)
                        );
                      }}
                    >
                      全选
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => updateConfigField('selectedMiningDirectionIndices', [])}
                    >
                      取消全选
                    </Button>
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-[320px] overflow-y-auto rounded-lg border border-border/50 bg-secondary/10 p-3">
                  {REFERENCE_MINING_DIRECTIONS.map((item: MiningDirectionItem, idx: number) => {
                    const label = getDirectionLabel(item, language);
                    return (
                      <label
                        key={idx}
                        className="flex items-center gap-2 p-2 rounded-lg hover:bg-secondary/20 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={config.selectedMiningDirectionIndices.includes(idx)}
                          onChange={(e) => {
                            const next = e.target.checked
                              ? [...config.selectedMiningDirectionIndices, idx].sort((a, b) => a - b)
                              : config.selectedMiningDirectionIndices.filter((i) => i !== idx);
                            updateConfigField('selectedMiningDirectionIndices', next);
                          }}
                          className="h-4 w-4 rounded border-input text-primary focus:ring-primary"
                        />
                        <span className="text-sm truncate flex-1" title={label}>
                          {label}
                        </span>
                      </label>
                    );
                  })}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  {language === 'zh'
                    ? `已选 ${config.selectedMiningDirectionIndices.length} / ${REFERENCE_MINING_DIRECTIONS.length} 项。`
                    : `Selected ${config.selectedMiningDirectionIndices.length} / ${REFERENCE_MINING_DIRECTIONS.length} directions.`}
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Info Footer */}
      <Card className="glass border-primary/20 bg-primary/5">
        <CardContent className="p-4 flex gap-3">
          <div className="text-xl">💡</div>
          <div className="text-sm text-muted-foreground">
            <p className="mb-1 font-medium text-foreground">配置提示</p>
            <p>所有配置修改后会自动保存至后端环境文件及本地浏览器缓存。涉及 API 或路径的修改，建议在保存后重启相关服务以确保生效。</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
