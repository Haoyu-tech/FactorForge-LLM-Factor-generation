/**
 * Ask the Factor Library page to show one library.
 *
 * Every page stays mounted (hidden with CSS), so a page that wants to open a
 * library fires this event and then navigates; FactorLibraryPage listens.
 */
export const OPEN_LIBRARY_EVENT = 'factorforge:open-library';

export interface OpenLibraryDetail {
  /** Library file name, e.g. all_factors_library_us_sp500_exp_20261121_181720.json */
  file: string;
  marketMode?: 'us' | 'cn' | 'crypto' | null;
  market?: string | null;
}

export function requestOpenLibrary(detail: OpenLibraryDetail): void {
  window.dispatchEvent(new CustomEvent<OpenLibraryDetail>(OPEN_LIBRARY_EVENT, { detail }));
}
