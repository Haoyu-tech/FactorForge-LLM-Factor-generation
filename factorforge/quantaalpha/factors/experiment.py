"""
QuantaAlpha factor experiment module: Scenario and Experiment classes.
Uses project QlibFBWorkspace (no ProcessInf / pandas 1.5.x issues).
"""

from copy import deepcopy
from pathlib import Path

from rdagent.scenarios.qlib.experiment.factor_experiment import (  # type: ignore
    QlibFactorScenario,
    FactorExperiment,
    FactorTask,
    FactorFBWorkspace,
)
from rdagent.utils.agent.tpl import T

from quantaalpha.factors.workspace import QlibFBWorkspace
from rdagent.scenarios.qlib.experiment.factor_experiment import (
    QlibFactorExperiment as _OrigQlibFactorExperiment,
)


class QlibFactorExperiment(_OrigQlibFactorExperiment):
    """Override rdagent QlibFactorExperiment with project QlibFBWorkspace (correct config template)."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        import rdagent.scenarios.qlib.experiment.factor_experiment as _fe_mod

        rdagent_template_path = Path(_fe_mod.__file__).parent / "factor_template"
        self.experiment_workspace = QlibFBWorkspace(
            template_folder_path=rdagent_template_path
        )


class QlibAlphaAgentScenario(QlibFactorScenario):
    """Scenario wrapper for AlphaAgent: accepts use_local; when True uses local get_data_folder_intro (no Docker)."""

    def __init__(self, use_local: bool = True, *args, **kwargs):
        from rdagent.core.scenario import Scenario
        from quantaalpha.factors.qlib_utils import get_data_folder_intro as local_get_data_folder_intro

        Scenario.__init__(self)
        tpl_prefix = "scenarios.qlib.experiment.prompts"

        self._background = deepcopy(
            T(f"{tpl_prefix}:qlib_factor_background").r(
                runtime_environment=self.get_runtime_environment(),
            )
        )
        self._source_data = deepcopy(local_get_data_folder_intro(use_local=use_local))
        self._output_format = deepcopy(T(f"{tpl_prefix}:qlib_factor_output_format").r())
        self._interface = deepcopy(T(f"{tpl_prefix}:qlib_factor_interface").r())
        self._strategy = deepcopy(T(f"{tpl_prefix}:qlib_factor_strategy").r())
        self._simulator = deepcopy(T(f"{tpl_prefix}:qlib_factor_simulator").r())
        self._rich_style_description = deepcopy(T(f"{tpl_prefix}:qlib_factor_rich_style_description").r())
        self._experiment_setting = deepcopy(T(f"{tpl_prefix}:qlib_factor_experiment_setting").r())

        import os
        market_mode = os.environ.get("MARKET_MODE", "us").lower()
        if market_mode == "us":
            source = os.environ.get("DATA_SOURCE", "qlib")
            train = f"{os.environ.get('TRAIN_START_DATE', '1925-12-31')} to {os.environ.get('TRAIN_END_DATE', '1999-12-31')}"
            valid = f"{os.environ.get('VALID_START_DATE', '2000-01-03')} to {os.environ.get('VALID_END_DATE', '2009-12-31')}"
            test = f"{os.environ.get('TEST_START_DATE', '2010-01-04')} to {os.environ.get('TEST_END_DATE', '2025-12-31')}"
            self._background += (
                "\nMarket: US equities with historical S&P 500 membership. Use US market assumptions, "
                "PERMNO security identity, and never backfill current constituents into history."
            )
            if source == "wrds":
                from quantaalpha.data.wrds_adapter import (
                    RAW_QUARTERLY_FIELDS,
                    DERIVED_QUARTERLY_FIELDS,
                    FUNDAMENTAL_TIMING_FIELDS,
                    INDUSTRY_FIELDS,
                )
                raw_fields = ", ".join(f"${name}" for name in RAW_QUARTERLY_FIELDS)
                derived_fields = ", ".join(f"${name}" for name in DERIVED_QUARTERLY_FIELDS)
                timing_fields = ", ".join(f"${name}" for name in FUNDAMENTAL_TIMING_FIELDS)
                industry_fields = ", ".join(f"${name}" for name in INDUSTRY_FIELDS)
                self._background += (
                    "\nPrimary source is the configured WRDS folder. Daily CRSP price/volume data uses "
                    "historical MbrStartDt/MbrEndDt membership. Point-in-time Compustat raw quarterly fields: "
                    + raw_fields + ". Derived growth, profitability, margins and balance-sheet composition fields: "
                    + derived_fields + ". Timing fields: " + timing_fields
                    + ". GICS fields: " + industry_fields + ". Values become available on rdq "
                    "(or datadate+90 days when missing) and are only forward-filled afterward. "
                    "Do not replace missing accounting values with zero. Kelly 153 is catalogued but not unpacked automatically."
                )
            experiment_context = (
                f"S&P 500; data source {source}; train {train}, validation {valid}, test {test}. "
                "During factor mining, use validation statistics for every proposal, feedback, and evolution decision. "
                "The test segment is held out and is only reported by the independent final backtest after factors are frozen. "
                "Benchmark ^GSPC; 5 bps each side. Evaluate Long, Short, Long-Short, decile monotonicity, "
                "and FF3/FF3+Momentum/FF5/FF5+Momentum regressions with Newey-West alpha and beta tests "
                "for every candidate factor."
            )
            self._experiment_setting = experiment_context
            # Some prompt variants omit the experiment-setting section. Keep these
            # constraints in the always-visible scenario background as well.
            self._background += "\nExperiment setting: " + experiment_context
        elif market_mode == "cn":
            from quantaalpha.data.cn_duckdb_adapter import FINANCIAL_FIELDS, SW_FIELDS
            from quantaalpha.market.profile import get_market_profile
            profile = get_market_profile()
            train = f"{os.environ.get('TRAIN_START_DATE', '2010-07-01')} to {os.environ.get('TRAIN_END_DATE', '2017-12-31')}"
            valid = f"{os.environ.get('VALID_START_DATE', '2018-01-02')} to {os.environ.get('VALID_END_DATE', '2020-12-31')}"
            test = f"{os.environ.get('TEST_START_DATE', '2021-01-04')} to {os.environ.get('TEST_END_DATE', '2025-12-31')}"
            filters = []
            if os.environ.get("CN_EXCLUDE_ST", "true").lower() == "true":
                filters.append("exclude ST on each historical date")
            if os.environ.get("CN_EXCLUDE_NEW_STOCKS", "true").lower() == "true":
                filters.append(f"exclude stocks listed fewer than {os.environ.get('CN_NEW_STOCK_MIN_TRADING_DAYS', '375')} trading days")
            self._background += (
                f"\nMarket: China A shares, universe {profile.name}. Use China price-limit, suspension, "
                "T+1 and short-sale constraints when interpreting results. "
                f"Dynamic filters: {', '.join(filters) if filters else 'none'}. "
                "Never use ETF/minute tables. Financial values become usable only from ann_date onward. "
                "Available point-in-time financial fields: " + ", ".join(f"${field}" for field in FINANCIAL_FIELDS)
                + ". Shenwan industry fields: " + ", ".join(f"${field}" for field in SW_FIELDS) + "."
            )
            experiment_context = (
                f"{profile.name}; local DuckDB daily stocks; train {train}, validation {valid}, test {test}. "
                "Use validation statistics only for proposal, feedback and evolution; keep test held out until factors are frozen. "
                "Use Shenwan level-1 neutralization, level-2 robustness, China Barra style exposures, and locally derived "
                "China FF3/FF3+Momentum/FF5/FF5+Momentum Newey-West alpha/beta tests. The primary investable "
                "portfolio objective is transaction-cost-adjusted Long-only Sharpe, supported by Long-only net return "
                "and maximum drawdown. Use this Long-only evidence for candidate comparison and feedback. Also report "
                "Short and Long-Short as diagnostics, plus costs and decile monotonicity at every configured "
                "daily/weekly/monthly frequency."
            )
            self._experiment_setting = experiment_context
            self._background += "\nExperiment setting: " + experiment_context
        elif market_mode == "crypto":
            from quantaalpha.data.binance_futures_adapter import EXPORTED_FIELDS
            train = f"{os.environ.get('TRAIN_START_DATE', '2020-01-01')} to {os.environ.get('TRAIN_END_DATE', '2022-12-31')}"
            valid = f"{os.environ.get('VALID_START_DATE', '2023-01-01')} to {os.environ.get('VALID_END_DATE', '2023-12-31')}"
            test = f"{os.environ.get('TEST_START_DATE', '2024-01-01')} to {os.environ.get('TEST_END_DATE', '2025-12-31')}"
            available = ", ".join(f"${field}" for field in EXPORTED_FIELDS)
            self._background += (
                "\nMarket: Binance USD-M USDT-margined perpetual futures, traded 24/7 in UTC. "
                "Use perpetual-futures assumptions, including funding payments, high turnover, "
                "contract listing age and cross-sectional liquidity differences. Do not propose "
                "equity fundamentals, GICS, Shenwan, Fama-French or stock-only variables. "
                f"Available daily fields: {available}. The universe contains only USDT-settled "
                "PERPETUAL contracts and respects each contract onboard date."
            )
            experiment_context = (
                f"Binance USD-M USDT perpetuals; train {train}, validation {valid}, test {test}. "
                "Use validation statistics only for proposal, feedback and evolution; keep test held out. "
                "The primary evolution objective is a high positive validation-set cross-sectional RankIC, "
                "with daily RankIC >= 0.03 and |RankICIR| >= 0.25 as the high-quality gate. Orient factor signs "
                "so higher factor values predict higher next-period returns. Confirm the RankIC sign and strength "
                "across daily and weekly evaluations; never use the held-out test interval for selection. "
                "Report linear IC only as a diagnostic; it must not influence proposal ranking or selection. "
                "Also evaluate Long, Short and dollar-neutral Long-Short portfolios, turnover, trading cost, "
                "drawdown, decile monotonicity and funding-rate sensitivity. Prefer robust signals that survive "
                "different volatility and liquidity regimes."
            )
            self._experiment_setting = experiment_context
            self._background += "\nExperiment setting: " + experiment_context
