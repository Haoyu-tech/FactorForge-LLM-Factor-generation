/**
 * Reference mining directions list and default direction parsing (consistent with "Mining Direction" in settings)
 * Each direction can attach up to 3 factors' "short name", "expression", "meaning", displayed on hover
 */

export interface FactorHint {
  shortName: string;
  expression: string;
  meaning: string;
}

export interface MiningDirectionItem {
  label: string;
  labelEn: string;
  /** Up to 3 factors, displayed when hovering over the direction */
  factors?: FactorHint[];
}

/** Reference mining directions (Alpha158(20) style, can be added/deleted/modified as needed; factors can be filled from original_direction.json) */
export const REFERENCE_MINING_DIRECTIONS: MiningDirectionItem[] = [
  {
    label: '价量关系与开盘收益率', labelEn: 'Price–volume relationships and open-to-close returns',
    factors: [
      { shortName: 'KMID', expression: '(close-open)/open', meaning: '开盘收益率' },
      { shortName: 'KUP', expression: '(high-max(open,close))/open', meaning: '上影线相对开盘' },
      { shortName: 'KLOW', expression: '(min(open,close)-low)/open', meaning: '下影线相对开盘' },
    ],
  },
  { label: '短期动量与收益率', labelEn: 'Short-term momentum and returns', factors: [] },
  { label: '成交量比率与放量确认', labelEn: 'Volume ratios and volume confirmation', factors: [] },
  { label: '波动率与价格稳定性', labelEn: 'Volatility and price stability', factors: [] },
  { label: '振幅与高低价区间', labelEn: 'Price amplitude and high–low ranges', factors: [] },
  { label: 'RSV 与超买超卖', labelEn: 'RSV and overbought / oversold conditions', factors: [] },
  { label: '均线比率与趋势', labelEn: 'Moving-average ratios and trends', factors: [] },
  { label: '影线比例与 K 线形态', labelEn: 'Wick ratios and candlestick patterns', factors: [] },
  { label: '实体比例与多空力量', labelEn: 'Body ratios and buying / selling pressure', factors: [] },
  { label: '收益率波动与风险', labelEn: 'Return volatility and risk', factors: [] },
  { label: '高低价相对位置', labelEn: 'Relative position within the high–low range', factors: [] },
  { label: '量价背离与确认', labelEn: 'Price–volume divergence and confirmation', factors: [] },
  { label: '多周期动量组合', labelEn: 'Multi-horizon momentum combinations', factors: [] },
  { label: '成交量标准化特征', labelEn: 'Standardized volume features', factors: [] },
  { label: '价格相对均线位置', labelEn: 'Price relative to moving averages', factors: [] },
  { label: '盈利能力：ROA、ROE 与经营利润率', labelEn: 'Profitability: ROA, ROE, and operating margin', factors: [] },
  { label: '毛利率与持续盈利质量', labelEn: 'Gross margins and persistent earnings quality', factors: [] },
  { label: '资产增长与投资因子', labelEn: 'Asset growth and investment factors', factors: [] },
  { label: '销售增长与收入加速度', labelEn: 'Sales growth and revenue acceleration', factors: [] },
  { label: '资本结构、杠杆与去杠杆', labelEn: 'Capital structure, leverage, and deleveraging', factors: [] },
  { label: '现金持有与流动性质量', labelEn: 'Cash holdings and liquidity quality', factors: [] },
  { label: '账面价值、规模与价值因子', labelEn: 'Book value, size, and value factors', factors: [] },
  { label: '应计项目与现金流质量', labelEn: 'Accruals and cash flow quality', factors: [] },
  { label: '短期反转与中期动量', labelEn: 'Short-term reversal and medium-term momentum', factors: [] },
  { label: '特质波动率与市场 Beta', labelEn: 'Idiosyncratic volatility and market beta', factors: [] },
  { label: '盈利公告后漂移与基本面动量', labelEn: 'Post-earnings-announcement drift and fundamental momentum', factors: [] },
  { label: '行业中性基本面相对价值', labelEn: 'Industry-neutral fundamental relative value', factors: [] },
  { label: '质量减投资复合因子', labelEn: 'Quality-minus-investment composite factors', factors: [] },
  { label: '价值、动量与质量交互', labelEn: 'Value, momentum, and quality interactions', factors: [] },
  { label: '规模分层下的异常收益', labelEn: 'Abnormal returns across size groups', factors: [] },
  { label: 'FF3 无法解释的候选 Alpha', labelEn: 'Candidate alpha unexplained by FF3', factors: [] },
  { label: 'FF5 无法解释的候选 Alpha', labelEn: 'Candidate alpha unexplained by FF5', factors: [] },
  { label: '动量控制后的独立 Alpha', labelEn: 'Independent alpha after controlling for momentum', factors: [] },
  { label: '分析师预期与盈利修正', labelEn: 'Analyst expectations and earnings revisions', factors: [] },
  { label: '机构、卖空与拥挤度', labelEn: 'Institutional activity, short selling, and crowding', factors: [] },
];

/** Get direction label (compatible with object or string) */
export function getDirectionLabel(item: MiningDirectionItem, language: 'zh' | 'en' = 'zh'): string {
  return typeof item === 'string' ? item : (language === 'en' ? item.labelEn : item.label);
}

interface StoredMiningDirectionConfig {
  miningDirectionMode?: 'selected' | 'random';
  selectedMiningDirectionIndices?: number[];
}

/** Get a default mining direction from saved config (one of the selected list, or a random one) */
export function getDefaultMiningDirection(): string {
  try {
    const raw = localStorage.getItem('quantaalpha_config');
    if (!raw) return '';
    const config = JSON.parse(raw) as StoredMiningDirectionConfig;
    const indices = config?.selectedMiningDirectionIndices ?? [];
    const list = REFERENCE_MINING_DIRECTIONS;
    if (!list.length || !indices.length) return '';
    const validIndices = indices.filter((i) => i >= 0 && i < list.length);
    if (!validIndices.length) return '';
    if (config?.miningDirectionMode === 'random') {
      const idx = validIndices[Math.floor(Math.random() * validIndices.length)];
      return getDirectionLabel(list[idx]);
    }
    return getDirectionLabel(list[validIndices[0]]);
  } catch {
    return '';
  }
}
