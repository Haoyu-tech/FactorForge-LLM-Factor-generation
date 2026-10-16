import pickle
import sys
from pathlib import Path
from typing import List
import os
import numpy as np
import pandas as pd
from pandarallel import pandarallel

from quantaalpha.core.conf import RD_AGENT_SETTINGS
from quantaalpha.core.utils import cache_with_pickle, multiprocessing_wrapper
from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
from quantaalpha.backtest.long_short_analytics import (
    calculate_multi_frequency_analytics, flatten_analytics, calculate_ic_metrics,
    calculate_industry_aware_analytics,
)
from quantaalpha.backtest.asset_pricing import regress_asset_pricing, flatten_asset_pricing

pandarallel.initialize(verbose=1)

from quantaalpha.components.runner import CachedRunner
from quantaalpha.core.exception import FactorEmptyError
from quantaalpha.log import logger
from quantaalpha.factors.experiment import QlibFactorExperiment

DIRNAME = Path(__file__).absolute().resolve().parent
DIRNAME_local = Path.cwd()


def _mining_evaluation_window():
    """Return the split and dates used by mining feedback.

    Validation is the safe default. Test is reserved for a frozen final
    evaluation and must not be used by the evolutionary loop.
    """
    split = os.environ.get("MINING_EVALUATION_SPLIT", "valid").strip().lower()
    if split not in {"valid", "test"}:
        split = "valid"
    prefix = "VALID" if split == "valid" else "TEST"
    return split, os.environ.get(f"{prefix}_START_DATE"), os.environ.get(f"{prefix}_END_DATE")

# class QlibFactorExpWorkspace:

#     def prepare():
#         # create a folder;
#         # copy template
#         # place data inside the folder `combined_factors`
#         #
#     def execute():
#         de = DockerEnv()
#         de.run(local_path=self.ws_path, entry="qrun conf.yaml")

# TODO: supporting multiprocessing and keep previous results


class QlibFactorRunner(CachedRunner[QlibFactorExperiment]):
    """
    Docker run
    Everything in a folder
    - config.yaml
    - price-volume data dumper
    - `data.py` + Adaptor to Factor implementation
    - results in `mlflow`
    """

    def calculate_information_coefficient(
        self, concat_feature: pd.DataFrame, SOTA_feature_column_size: int, new_feature_columns_size: int
    ) -> pd.DataFrame:
        res = pd.Series(index=range(SOTA_feature_column_size * new_feature_columns_size))
        for col1 in range(SOTA_feature_column_size):
            for col2 in range(SOTA_feature_column_size, SOTA_feature_column_size + new_feature_columns_size):
                res.loc[col1 * new_feature_columns_size + col2 - SOTA_feature_column_size] = concat_feature.iloc[
                    :, col1
                ].corr(concat_feature.iloc[:, col2])
        return res

    def deduplicate_new_factors(self, SOTA_feature: pd.DataFrame, new_feature: pd.DataFrame) -> pd.DataFrame:
        # calculate the IC between each column of SOTA_feature and new_feature
        # if the IC is larger than a threshold, remove the new_feature column
        # return the new_feature

        concat_feature = pd.concat([SOTA_feature, new_feature], axis=1)
        IC_max = (
            concat_feature.groupby("datetime")
            .parallel_apply(
                lambda x: self.calculate_information_coefficient(x, SOTA_feature.shape[1], new_feature.shape[1])
            )
            .mean()
        )
        IC_max.index = pd.MultiIndex.from_product([range(SOTA_feature.shape[1]), range(new_feature.shape[1])])
        IC_max = IC_max.unstack().max(axis=0)
        return new_feature.iloc[:, IC_max[IC_max < 0.99].index]

    @cache_with_pickle(CachedRunner.get_cache_key, CachedRunner.assign_cached_result)
    def develop(self, exp: QlibFactorExperiment, use_local: bool = True) -> QlibFactorExperiment:
        
        """
        Generate the experiment by processing and combining factor data,
        then passing the combined data to Docker or local environment for backtest results.
        """
        
        lightgbm_enabled = os.environ.get("MINING_LIGHTGBM_ENABLED", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }
        factor_portfolio_analytics = {}
        if exp.based_experiments and exp.based_experiments[-1].result is None:
            baseline = exp.based_experiments[-1]
            # The first trace entry is an empty placeholder used by RD-Agent.
            # Pure single-factor mode neither needs nor can evaluate it.
            if lightgbm_enabled or getattr(baseline, "sub_tasks", None):
                exp.based_experiments[-1] = self.develop(baseline, use_local=use_local)

        # Every round, including the first one, must materialize the newly
        # generated factor values. Previous code only did this when a based
        # experiment existed, leaving combined_factors undefined in round 0.
        SOTA_factor = None
        if len(exp.based_experiments) > 1:
            try:
                SOTA_factor = self.process_factor_data(exp.based_experiments)
            except FactorEmptyError:
                logger.warning("SOTA factors processing failed, continuing with new factors only.")

        try:
            new_factors = self.process_factor_data(exp)
        except FactorEmptyError as error:
            logger.error(f"Failed to process new factors: {error}")
            logger.info("Attempting to manually execute factors...")
            for ws in exp.sub_workspace_list:
                if (ws.workspace_path / "result.h5").exists():
                    continue
                try:
                    data_source = Path(FACTOR_COSTEER_SETTINGS.data_folder).absolute()
                    if not data_source.is_absolute():
                        data_source = (
                            Path(__file__).parent.parent.parent.parent.parent
                            / FACTOR_COSTEER_SETTINGS.data_folder
                        )
                    daily_pv_link = ws.workspace_path / "daily_pv.h5"
                    if not daily_pv_link.exists() and (data_source / "daily_pv.h5").exists():
                        os.symlink(str(data_source / "daily_pv.h5"), str(daily_pv_link))

                    import subprocess
                    env = os.environ.copy()
                    project_root = Path(__file__).parent.parent.parent.parent.parent
                    env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")
                    subprocess.check_output(
                        [sys.executable, str(ws.workspace_path / "factor.py")],
                        cwd=str(ws.workspace_path),
                        stderr=subprocess.STDOUT,
                        env=env,
                        timeout=1200,
                    )
                except Exception as exec_error:
                    logger.warning(f"Failed to manually execute factor {ws.workspace_path}: {exec_error}")
            try:
                new_factors = self.process_factor_data(exp)
            except FactorEmptyError as retry_error:
                raise FactorEmptyError(
                    "No valid factor data found after executing candidate factors"
                ) from retry_error

        if new_factors is None or new_factors.empty:
            raise FactorEmptyError("No valid candidate factor data was produced")

        # Mining evaluates the candidates from this round independently. SOTA
        # factors remain available to the evolution controller for comparison,
        # but are not mixed into the candidate's own quality statistics.
        combined_factors = new_factors.sort_index()
        combined_factors = combined_factors.loc[
            :, ~combined_factors.columns.duplicated(keep="last")
        ]
        combined_factors = combined_factors.replace([np.inf, -np.inf], np.nan)
        invalid_columns = {}
        for column in combined_factors.columns:
            values = combined_factors[column].dropna()
            if values.empty:
                invalid_columns[column] = "no finite values"
                continue
            if "datetime" in values.index.names:
                has_cross_sectional_variation = (
                    values.groupby(level="datetime").nunique().gt(1).any()
                )
                if not has_cross_sectional_variation:
                    invalid_columns[column] = "no cross-sectional variation"
        if invalid_columns:
            logger.warning(
                "Skipping unusable candidate factors: "
                + "; ".join(
                    f"{column} ({reason})" for column, reason in invalid_columns.items()
                )
            )
            combined_factors = combined_factors.drop(columns=list(invalid_columns))
        if combined_factors.shape[1] == 0:
            raise FactorEmptyError(
                "All candidate factors are unusable: no finite values or no cross-sectional variation"
            )
        empty_row_mask = combined_factors.isna().all(axis=1)
        if empty_row_mask.any():
            logger.info(
                f"Dropping {int(empty_row_mask.sum())} rows where every candidate factor is missing"
            )
            combined_factors = combined_factors.loc[~empty_row_mask]
        if len(combined_factors.columns) >= 2:
            pd.set_option("display.width", 1000)
            logger.info(f"Candidate factor correlation: \n\n{combined_factors.corr()}\n")

        new_columns = pd.MultiIndex.from_product(
            [["feature"], combined_factors.columns]
        )
        combined_factors.columns = new_columns
        logger.info(f"Factor values this round: \n\n{combined_factors.tail()}\n\n")

        parquet_path = exp.experiment_workspace.workspace_path / "combined_factors_df.parquet"
        combined_factors.to_parquet(parquet_path, engine="pyarrow")
        logger.info(f"Saved combined factors to {parquet_path}")

        if not lightgbm_enabled:
            logger.info(
                "Mining LightGBM combination is disabled; evaluating every candidate factor independently."
            )
            import qlib
            from qlib.data import D
            from quantaalpha.market.profile import (
                apply_market_eligibility, eligibility_fields, get_market_profile, qlib_region,
            )

            profile = get_market_profile()
            provider_uri = os.environ.get("QLIB_DATA_DIR")
            qlib.init(provider_uri=provider_uri, region=qlib_region(profile))
            instruments = D.instruments(profile.instrument)
            label_expression = "Ref($close, -2) / Ref($close, -1) - 1"
            evaluation_split, evaluation_start, evaluation_end = _mining_evaluation_window()
            realized_frame = D.features(
                instruments,
                [label_expression],
                start_time=evaluation_start,
                end_time=evaluation_end,
                freq="day",
            )
            if realized_frame.empty:
                raise FactorEmptyError(f"No {profile.name} {evaluation_split}-period returns available for single-factor evaluation")
            realized = realized_frame.iloc[:, 0].rename("label")
            market_fields = profile.qlib_classification_fields + eligibility_fields(profile)
            industry_frame = D.features(
                instruments, market_fields, start_time=evaluation_start,
                end_time=evaluation_end, freq="day",
            )
            industry_frame.columns = [field[1:] for field in market_fields]

            raw_frequencies = os.environ.get("MINING_EVALUATION_FREQUENCIES", "day")
            frequencies = [
                value.strip().lower()
                for value in raw_frequencies.split(",")
                if value.strip().lower() in {"day", "week", "month"}
            ] or ["day"]
            wrds_root = os.environ.get("WRDS_ROOT", "").strip()
            flat_metrics = {}
            factor_frame = combined_factors.copy()
            if isinstance(factor_frame.columns, pd.MultiIndex):
                factor_frame.columns = [str(column[-1]) for column in factor_frame.columns]

            for factor_name in factor_frame.columns:
                signal = apply_market_eligibility(factor_frame[factor_name], industry_frame)
                classifications = industry_frame[list(profile.classification_fields)]
                neutral_signal, factor_analytics, group_analytics, own = calculate_industry_aware_analytics(
                    signal, realized, classifications,
                    frequencies=frequencies,
                    classification_levels=profile.classification_fields,
                    primary_level=profile.primary_classification,
                    robustness_level=profile.robustness_classification,
                    quantile=float(os.environ.get("LONG_SHORT_QUANTILE", "0.1")),
                    min_positions=int(os.environ.get("LONG_SHORT_MIN_POSITIONS", "20")),
                    transaction_cost=float(os.environ.get("LONG_SHORT_TRANSACTION_COST", "0.0005")),
                    short_borrow_rate=float(os.environ.get("LONG_SHORT_BORROW_RATE", "0")),
                )
                if profile.mode == "crypto" and "funding_rate" in industry_frame:
                    from quantaalpha.data.binance_futures_adapter import funding_sensitivity
                    own.update(funding_sensitivity(signal, industry_frame["funding_rate"]))
                safe_name = str(factor_name).replace(".", "_").replace(" ", "_")
                factor_portfolio_analytics[safe_name] = {
                    **factor_analytics,
                    f"industry_{profile.robustness_classification}_robustness": group_analytics,
                }
                flat_metrics.update({f"factor.{safe_name}.{key}": value for key, value in own.items()})

                for frequency, payload in factor_analytics.items():
                    pricing_leg = "long" if profile.mode == "cn" else "long_short"
                    portfolio = payload.get("portfolio_analytics", {}).get(pricing_leg, {})
                    daily_returns = portfolio.get("daily_net_returns", [])
                    if not daily_returns:
                        continue
                    if profile.mode == "cn":
                        from quantaalpha.backtest.china_evaluation import (
                            calculate_barra_style_exposures, regress_china_asset_pricing,
                        )
                        regressions = regress_china_asset_pricing(
                            daily_returns, instruments, evaluation_start, evaluation_end
                        )
                        barra_metrics = calculate_barra_style_exposures(
                            signal, instruments, evaluation_start, evaluation_end
                        )
                        flat_metrics.update({
                            f"factor.{safe_name}.{key}": value for key, value in barra_metrics.items()
                        })
                    elif profile.mode == "us" and wrds_root and Path(wrds_root).exists():
                        regressions = regress_asset_pricing(daily_returns, wrds_root)
                    else:
                        regressions = {}
                    flat_metrics.update(flatten_asset_pricing(
                        regressions, prefix=f"factor.{safe_name}.{frequency}.asset_pricing",
                    ))

            result = pd.DataFrame({"value": pd.Series(flat_metrics, dtype=float)})
            exp.portfolio_analytics = {}
            exp.factor_portfolio_analytics = factor_portfolio_analytics
            exp.evaluation_split = evaluation_split
            exp.evaluation_window = [evaluation_start, evaluation_end]
            exp.result = result
            logger.info(
                f"{profile.name} {profile.primary_classification}-neutral single-factor {evaluation_split} evaluation "
                f"completed for {len(factor_frame.columns)} factors; {profile.robustness_classification} is the robustness check."
            )
            return exp

        # Run backtest (local or Docker). Config name must match factor_template files (e.g. conf_baseline.yaml).
        config_name = "conf_baseline.yaml" if len(exp.based_experiments) == 0 else "conf_combined_factors.yaml"
        logger.info(f"Execute factor backtest (Use {'Local' if use_local else 'Docker container'}): {config_name}")
        
        # Ensure workspace and config are ready (execute() does not call before_execute()).
        exp.experiment_workspace.before_execute()
        
        # execute() returns (result_df, execute_qlib_log) or (None, execute_qlib_log)
        result_tuple = exp.experiment_workspace.execute(
            qlib_config_name=config_name,
            run_env={}
        )
        
        # Unpack tuple; take first element (DataFrame)
        result = result_tuple[0] if isinstance(result_tuple, tuple) else result_tuple
        
        if result is not None:
            logger.info(f"Backtesting results: \n{result.iloc[2:] if hasattr(result, 'iloc') else result}")
        else:
            logger.warning("Backtesting result is None. Check the execution logs above for errors.")
            if isinstance(result_tuple, tuple) and len(result_tuple) > 1:
                logger.info(f"Execution log: {result_tuple[1][:500]}...")
        
        if result is not None:
            try:
                workspace = exp.experiment_workspace.workspace_path
                pred_paths = sorted(workspace.rglob("pred.pkl"), key=lambda path: path.stat().st_mtime, reverse=True)
                artifact = next(
                    (path for path in pred_paths if path.with_name("label.pkl").exists()),
                    None,
                )
                if artifact is None:
                    raise FileNotFoundError("No matching pred.pkl/label.pkl artifacts found")
                signal = pd.read_pickle(artifact)
                realized = pd.read_pickle(artifact.with_name("label.pkl"))
                evaluation_split, evaluation_start, evaluation_end = _mining_evaluation_window()
                raw_frequencies = os.environ.get("MINING_EVALUATION_FREQUENCIES", "day")
                frequencies = [
                    value.strip().lower()
                    for value in raw_frequencies.split(",")
                    if value.strip()
                ] or ["day"]
                from qlib.data import D
                from quantaalpha.market.profile import (
                    apply_market_eligibility, eligibility_fields, get_market_profile,
                )
                profile = get_market_profile()
                instruments = D.instruments(profile.instrument)
                market_fields = profile.qlib_classification_fields + eligibility_fields(profile)
                industry_frame = D.features(
                    instruments, market_fields, start_time=evaluation_start,
                    end_time=evaluation_end, freq="day",
                )
                industry_frame.columns = [field[1:] for field in market_fields]
                signal = apply_market_eligibility(signal, industry_frame)
                neutral_signal, analytics, group_analytics, flat_metrics = calculate_industry_aware_analytics(
                    signal, realized, industry_frame[list(profile.classification_fields)],
                    frequencies=frequencies,
                    classification_levels=profile.classification_fields,
                    primary_level=profile.primary_classification,
                    robustness_level=profile.robustness_classification,
                    quantile=float(os.environ.get("LONG_SHORT_QUANTILE", "0.1")),
                    min_positions=int(os.environ.get("LONG_SHORT_MIN_POSITIONS", "20")),
                    transaction_cost=float(os.environ.get("LONG_SHORT_TRANSACTION_COST", "0.0005")),
                    short_borrow_rate=float(os.environ.get("LONG_SHORT_BORROW_RATE", "0")),
                )
                if profile.mode == "crypto" and "funding_rate" in industry_frame:
                    from quantaalpha.data.binance_futures_adapter import funding_sensitivity
                    flat_metrics.update(funding_sensitivity(signal, industry_frame["funding_rate"]))
                wrds_root = os.environ.get("WRDS_ROOT", "").strip()
                if profile.mode == "cn" or (profile.mode == "us" and wrds_root and Path(wrds_root).exists()):
                    for frequency, frequency_payload in analytics.items():
                        pricing_leg = "long" if profile.mode == "cn" else "long_short"
                        portfolio = frequency_payload.get("portfolio_analytics", {}).get(pricing_leg, {})
                        daily_returns = portfolio.get("daily_net_returns", [])
                        if daily_returns:
                            if profile.mode == "cn":
                                from quantaalpha.backtest.china_evaluation import regress_china_asset_pricing
                                regressions = regress_china_asset_pricing(
                                    daily_returns, instruments, evaluation_start, evaluation_end
                                )
                            else:
                                regressions = regress_asset_pricing(daily_returns, wrds_root)
                            flat_metrics.update(
                                flatten_asset_pricing(
                                    regressions,
                                    prefix=f"{frequency}.asset_pricing",
                                )
                            )

                    factor_file = workspace / "combined_factors_df.parquet"
                    if factor_file.exists():
                        factor_frame = pd.read_parquet(factor_file)
                        if isinstance(factor_frame.columns, pd.MultiIndex):
                            factor_frame.columns = [
                                str(column[-1]) for column in factor_frame.columns
                            ]
                        for factor_name in factor_frame.columns:
                            _, factor_analytics, factor_group_analytics, factor_flat = calculate_industry_aware_analytics(
                                apply_market_eligibility(factor_frame[factor_name], industry_frame),
                                realized,
                                industry_frame[list(profile.classification_fields)],
                                frequencies=frequencies,
                                classification_levels=profile.classification_fields,
                                primary_level=profile.primary_classification,
                                robustness_level=profile.robustness_classification,
                                quantile=float(os.environ.get("LONG_SHORT_QUANTILE", "0.1")),
                                min_positions=int(os.environ.get("LONG_SHORT_MIN_POSITIONS", "20")),
                                transaction_cost=float(os.environ.get("LONG_SHORT_TRANSACTION_COST", "0.0005")),
                                short_borrow_rate=float(os.environ.get("LONG_SHORT_BORROW_RATE", "0")),
                            )
                            safe_name = str(factor_name).replace(".", "_").replace(" ", "_")
                            factor_portfolio_analytics[safe_name] = {
                                **factor_analytics,
                                f"industry_{profile.robustness_classification}_robustness": factor_group_analytics,
                            }
                            flat_metrics.update({
                                f"factor.{safe_name}.{key}": value
                                for key, value in factor_flat.items()
                            })
                            for frequency, frequency_payload in factor_analytics.items():
                                pricing_leg = "long" if profile.mode == "cn" else "long_short"
                                portfolio = frequency_payload.get("portfolio_analytics", {}).get(pricing_leg, {})
                                daily_returns = portfolio.get("daily_net_returns", [])
                                if daily_returns:
                                    if profile.mode == "cn":
                                        from quantaalpha.backtest.china_evaluation import regress_china_asset_pricing
                                        regressions = regress_china_asset_pricing(
                                            daily_returns, instruments, evaluation_start, evaluation_end
                                        )
                                    else:
                                        regressions = regress_asset_pricing(daily_returns, wrds_root)
                                    flat_metrics.update(
                                        flatten_asset_pricing(
                                            regressions,
                                            prefix=f"factor.{safe_name}.{frequency}.asset_pricing",
                                        )
                                    )

                value_column = result.columns[0] if len(result.columns) else 0
                extra = pd.DataFrame({value_column: pd.Series(flat_metrics)})
                result = pd.concat([result, extra.loc[~extra.index.isin(result.index)]])
                exp.portfolio_analytics = analytics
                exp.factor_portfolio_analytics = factor_portfolio_analytics
                exp.evaluation_split = evaluation_split
                exp.evaluation_window = [evaluation_start, evaluation_end]
                logger.info(
                    f"Added {profile.name} {profile.primary_classification}-neutral {evaluation_split} analytics "
                    f"for frequencies {frequencies}; {profile.robustness_classification} robustness was also calculated."
                )
            except Exception as analytics_error:
                logger.exception(f"Failed to calculate multi-frequency portfolio analytics: {analytics_error}")

        exp.result = result

        return exp

    def process_factor_data(self, exp_or_list: List[QlibFactorExperiment] | QlibFactorExperiment) -> pd.DataFrame:
        """
        Process and combine factor data from experiment implementations.

        Args:
            exp (ASpecificExp): The experiment containing factor data.

        Returns:
            pd.DataFrame: Combined factor data without NaN values.
        """
        if isinstance(exp_or_list, QlibFactorExperiment):
            exp_or_list = [exp_or_list]
        factor_dfs = []

        # Collect all exp's dataframes
        for exp in exp_or_list:
            # Iterate over sub-implementations and execute them to get each factor data
            message_and_df_list = multiprocessing_wrapper(
                [(implementation.execute, ("All",)) for implementation in exp.sub_workspace_list],
                n=RD_AGENT_SETTINGS.multi_proc_n,
            )
            for idx, (message, df) in enumerate(message_and_df_list):
                # Check if factor generation was successful
                if df is not None and "datetime" in df.index.names:
                    # Convert Series to DataFrame if needed
                    if isinstance(df, pd.Series):
                        # Get factor name from the corresponding workspace (order should match)
                        if idx < len(exp.sub_workspace_list):
                            factor_name = getattr(exp.sub_workspace_list[idx].target_task, 'factor_name', None)
                            if factor_name:
                                df = df.to_frame(name=factor_name)
                            else:
                                df = df.to_frame(name=df.name if df.name else f'factor_{idx}')
                        else:
                            df = df.to_frame(name=df.name if df.name else f'factor_{idx}')
                    time_diff = df.index.get_level_values("datetime").to_series().diff().dropna().unique()
                    if pd.Timedelta(minutes=1) not in time_diff:
                        factor_dfs.append(df)

        # Combine all successful factor data
        if factor_dfs:
            return pd.concat(factor_dfs, axis=1)
        else:
            raise FactorEmptyError("No valid factor data found to merge.")
