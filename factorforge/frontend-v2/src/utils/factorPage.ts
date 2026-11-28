/** Each factor has its own page, factor.html, addressed by id and library file. */

export type MarketMode = 'us' | 'cn' | 'crypto';

export interface FactorPageParams {
  id: string;
  /** Library file holding the factor; omitted means search every library. */
  library?: string;
  /** Market to fall back on when the factor does not record its own. */
  marketMode?: MarketMode;
}

export function factorPageUrl({ id, library, marketMode }: FactorPageParams): string {
  const params = new URLSearchParams({ id });
  if (library) params.set('library', library);
  if (marketMode) params.set('market', marketMode);
  return `/factor.html?${params.toString()}`;
}

export function readFactorPageParams(search: string): FactorPageParams | null {
  const params = new URLSearchParams(search);
  const id = params.get('id');
  if (!id) return null;
  const market = params.get('market');
  return {
    id,
    library: params.get('library') || undefined,
    marketMode: market === 'us' || market === 'cn' || market === 'crypto' ? market : undefined,
  };
}
