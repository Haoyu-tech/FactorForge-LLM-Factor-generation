/**
 * The market a mining run will use, read from the saved Settings.
 *
 * The direction check and the mining start must agree on the market, or the
 * check would answer for a different data store than the run reads.
 */
export type MarketMode = 'us' | 'cn' | 'crypto';

export interface MarketSelection {
  marketMode: MarketMode;
  market: string;
  dataSource: 'qlib' | 'wrds' | 'cn_duckdb' | 'binance_futures';
}

export function readSavedConfig(): any {
  try {
    const raw = localStorage.getItem('quantaalpha_config');
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function marketSelectionFrom(defaults: any): MarketSelection {
  const marketMode: MarketMode =
    defaults?.marketMode === 'crypto' ? 'crypto' : defaults?.marketMode === 'cn' ? 'cn' : 'us';
  return {
    marketMode,
    market:
      defaults?.defaultMarket ||
      (marketMode === 'crypto' ? 'binance_usdm' : marketMode === 'cn' ? 'csi300' : 'sp500'),
    dataSource:
      marketMode === 'crypto'
        ? 'binance_futures'
        : marketMode === 'cn'
          ? 'cn_duckdb'
          : defaults?.dataSource || 'wrds',
  };
}
