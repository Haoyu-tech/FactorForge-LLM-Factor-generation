#!/usr/bin/env python3
"""
Backtest runner using Qlib: load factors (official/custom), compute custom factor values, train, backtest, evaluate.
Modes: official (Qlib DataLoader) or custom (expr_parser + function_lib).
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
import pandas as pd
import yaml

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

from quantaalpha.backtest.calendar_guard import clamp_backtest_end_date
from quantaalpha.backtest.long_short_analytics import (
    industry_rank_signal, calculate_industry_diagnostics,
)


class BacktestRunner:
    """Backtest executor."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._qlib_initialized = False

    def _load_config(self) -> Dict:
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        safe_end = clamp_backtest_end_date(config)
        if safe_end:
            logger.info(f"Adjusted portfolio backtest end to {safe_end} to preserve Qlib calendar lookahead")
        logger.info(f"Loaded config: {self.config_path}")
        return config

    def _init_qlib(self):
        if self._qlib_initialized:
            return
        import os
        import qlib
        provider_uri = (
            os.environ.get('QLIB_DATA_DIR')
            or os.environ.get('QLIB_PROVIDER_URI')
            or self.config['data']['provider_uri']
        )
        provider_uri = os.path.expanduser(provider_uri)
        region = self.config['data'].get('region', 'cn')
        qlib.init(provider_uri=provider_uri, region=region)
        self._qlib_initialized = True
        logger.info(f"Qlib initialized: {provider_uri} (region={region})")

    def run(self,
            factor_source: Optional[str] = None,
            factor_json: Optional[List[str]] = None,
            experiment_name: Optional[str] = None,
            output_name: Optional[str] = None,
            skip_uncached: bool = False,
            portfolio_mode: str = 'long',
            quality_filter: str = 'all',
            model_type: str = 'lightgbm',
            retrain_months: int = 12,
            min_train_years: int = 10,
            portfolio_optimization: bool = False,
            correlation_pruning: bool = False,
            correlation_threshold: float = 0.85) -> Dict:
        """Run full backtest; returns metrics dict."""
        start_time_total = time.time()
        self._init_qlib()
        if factor_source:
            self.config['factor_source']['type'] = factor_source
        if factor_json:
            self.config['factor_source']['custom']['json_files'] = factor_json
        normalized_quality = quality_filter if quality_filter in ('high', 'medium', 'low') else None
        self.config['factor_source']['custom']['quality_filter'] = normalized_quality
        normalized_model = str(model_type or 'lightgbm').lower()
        if normalized_model not in ('lightgbm', 'pls5', 'lasso'):
            raise ValueError(f"Unsupported prediction model: {normalized_model}")
        self.config['model']['type'] = 'lgb' if normalized_model == 'lightgbm' else normalized_model
        
        if output_name is None and factor_json:
            output_name = Path(factor_json[0]).stem
        if output_name is not None and normalized_quality:
            output_name = f"{output_name}_{normalized_quality}"

        exp_name = experiment_name or output_name or self.config['experiment']['name']
        rec_name = self.config['experiment']['recorder']

        print(f"\n{'='*50}")
        src = factor_json[0] if factor_json else exp_name
        print(f"Starting backtest: {src}")
        print(f"{'='*50}")

        factor_expressions, custom_factors = self._load_factors()
        print(f"[1/4] Loaded factors: Qlib {len(factor_expressions)}, custom {len(custom_factors)}")
        if not factor_expressions and not custom_factors:
            raise ValueError(
                f"No factors matched quality filter '{quality_filter}' in the selected library"
            )

        computed_factors = None
        correlation_report = {'enabled': False}
        if custom_factors:
            computed_factors = self._compute_custom_factors(custom_factors, skip_compute=skip_uncached)
            n_computed = len(computed_factors.columns) if computed_factors is not None and not computed_factors.empty else 0
            print(f"[2/4] Computed custom factors: {n_computed}")
            if correlation_pruning and n_computed > 1:
                from quantaalpha.backtest.correlation_pruning import prune_correlated_factors
                from quantaalpha.backtest.factor_loader import assess_factor_quality

                market_mode = str(
                    self.config.get('data', {}).get('market_mode')
                    or os.environ.get('MARKET_MODE', 'us')
                ).strip().lower()

                if market_mode == 'crypto':
                    # Mining statistics are validation-only.  For correlated
                    # Crypto factors, retain the factor with the strongest
                    # positive validation RankIC; linear IC is never used.
                    def stored_validation_rank_ic(item: Dict[str, Any]) -> float:
                        metrics = item.get('backtest_results') or item.get('backtestResults') or {}
                        candidates = (
                            metrics.get('Rank IC'), metrics.get('RankIC'), metrics.get('rank_ic'),
                            metrics.get('1day.excess_return_without_cost.rank_ic'),
                        )
                        for key, value in metrics.items():
                            if str(key).lower().endswith('.rank_ic'):
                                candidates += (value,)
                        for value in candidates:
                            if isinstance(value, (int, float)) and np.isfinite(float(value)):
                                return max(float(value), 0.0)
                        return 0.0

                    quality_scores = {
                        str(item.get('factor_name') or item.get('name')): stored_validation_rank_ic(item)
                        for item in custom_factors
                        if item.get('factor_name') or item.get('name')
                    }
                    selection_score = 'positive_validation_rank_ic_only'
                else:
                    quality_scores = {
                        str(item.get('factor_name') or item.get('name')): float(assess_factor_quality(item)['score'])
                        for item in custom_factors
                        if item.get('factor_name') or item.get('name')
                    }
                    selection_score = 'existing_multidimensional_quality_score'

                valid_start, valid_end = self.config['dataset']['segments']['valid']
                computed_factors, correlation_report = prune_correlated_factors(
                    computed_factors,
                    start=valid_start,
                    end=valid_end,
                    threshold=correlation_threshold,
                    scores=quality_scores,
                )
                correlation_report['selection_score'] = selection_score
                correlation_report['scope'] = 'custom_factor_columns'
                print(
                    f"[2/4] Correlation pruning: {correlation_report['before_count']} -> "
                    f"{correlation_report['after_count']} factors "
                    f"(|Spearman| >= {correlation_threshold:.2f})"
                )
        else:
            logger.debug("[2/4] No custom factors, skip")

        dataset = self._create_dataset(factor_expressions, computed_factors)
        print("[3/4] Dataset created")

        metrics = self._train_and_backtest(
            dataset,
            exp_name,
            rec_name,
            output_name=output_name,
            portfolio_mode=portfolio_mode,
            retrain_months=retrain_months,
            min_train_years=min_train_years,
            portfolio_optimization=portfolio_optimization,
        )
        metrics['correlation_pruning'] = correlation_report
        if not any(
            key in metrics
            for key in ('annualized_return', 'information_ratio', 'max_drawdown')
        ):
            raise RuntimeError(
                "Portfolio backtest produced no strategy metrics; "
                "see the preceding backtest traceback"
            )
        total_time = time.time() - start_time_total
        self._print_results(metrics, total_time)
        self._save_results(metrics, exp_name, factor_source or self.config['factor_source']['type'], 
                          len(factor_expressions) + (
                              len(computed_factors.columns) if computed_factors is not None else len(custom_factors)
                          ), total_time,
                          output_name=output_name)
        
        return metrics
    
    def _load_factors(self) -> Tuple[Dict[str, str], List[Dict]]:
        from .factor_loader import FactorLoader
        
        loader = FactorLoader(self.config)
        return loader.load_factors()
    
    def _compute_custom_factors(self, factors: List[Dict], skip_compute: bool = False) -> Optional[pd.DataFrame]:
        """Compute custom factors (expr_parser + function_lib); supports cache; loads stock data only when needed."""
        from .custom_factor_calculator import CustomFactorCalculator
        from pathlib import Path

        llm_config = self.config.get('llm', {})
        cache_dir = llm_config.get('cache_dir')
        if cache_dir:
            cache_dir = Path(cache_dir)
        auto_extract = llm_config.get('auto_extract_cache', True)
        calculator = CustomFactorCalculator(
            data_df=None,
            cache_dir=cache_dir,
            auto_extract_cache=auto_extract,
            config=self.config,
        )
        result_df = calculator.calculate_factors_batch(factors, use_cache=True, skip_compute=skip_compute)
        if result_df is None:
            logger.error("Factor computation returned None")
            return None
        if not isinstance(result_df, pd.DataFrame):
            logger.error(f"Factor computation returned wrong type: {type(result_df)}")
            return None
        
        if result_df.empty:
            logger.error("Factor computation returned empty DataFrame")
            return None
        
        if not isinstance(result_df.index, pd.MultiIndex):
            logger.warning("Factor data index is not MultiIndex, attempting fix...")
        logger.debug(f"  Factor computation done: {len(result_df.columns)} factors, {len(result_df)} rows")
        
        return result_df
    
    def _create_dataset(self, 
                       factor_expressions: Dict[str, str],
                       computed_factors: Optional[pd.DataFrame] = None):
        """Create Qlib dataset (QlibDataLoader or precomputed factors + StaticDataLoader)."""
        from qlib.data.dataset import DatasetH
        from qlib.data.dataset.handler import DataHandlerLP
        
        data_config = self.config['data']
        dataset_config = self.config['dataset']
        
        has_computed_factors = False
        if computed_factors is not None:
            if isinstance(computed_factors, pd.DataFrame):
                if len(computed_factors) > 0 and len(computed_factors.columns) > 0:
                    has_computed_factors = True
                    logger.debug(f"  Precomputed factors: {len(computed_factors.columns)} factors, {len(computed_factors)} rows")
                else:
                    logger.warning(f"  Precomputed factor DataFrame is empty: {computed_factors.shape}")
            else:
                logger.warning(f"  Precomputed factor type invalid: {type(computed_factors)}")
        
        # Prefer custom factor mode when computed factors exist
        if has_computed_factors:
            logger.debug("  Using custom factor mode (precomputed)")
            return self._create_dataset_with_computed_factors(
                factor_expressions, computed_factors
            )
        
        # Qlib-only factor mode
        expressions = list(factor_expressions.values())
        names = list(factor_expressions.keys())
        
        if not expressions:
            raise ValueError("No factor expressions available. If using custom factors, ensure factor computation succeeded.")
        
        handler_config = {
            'start_time': data_config['start_time'],
            'end_time': data_config['end_time'],
            'instruments': data_config['market'],
            'data_loader': {
                'class': 'QlibDataLoader',
                'module_path': 'qlib.contrib.data.loader',
                'kwargs': {
                    'config': {
                        'feature': (expressions, names),
                        'label': ([dataset_config['label']], ['LABEL0'])
                    }
                }
            },
            'learn_processors': dataset_config['learn_processors'],
            'infer_processors': dataset_config['infer_processors']
        }
        
        dataset = DatasetH(
            handler=DataHandlerLP(**handler_config),
            segments=dataset_config['segments']
        )
        
        logger.debug(f"  Qlib mode: {len(expressions)} factors, train={dataset_config['segments']['train']}")
        
        return dataset
    
    def _create_dataset_with_computed_factors(self,
                                              factor_expressions: Dict[str, str],
                                              computed_factors: pd.DataFrame):
        """Create dataset from precomputed factors: compute label, merge with factors, use custom DataHandler."""
        from qlib.data.dataset import DatasetH
        from qlib.data.dataset.handler import DataHandler
        from qlib.data import D
        
        data_config = self.config['data']
        dataset_config = self.config['dataset']
        
        logger.debug(f"  Computed factor count: {len(computed_factors.columns)}")
        label_expr = dataset_config['label']
        label_df = self._compute_label(label_expr)
        
        all_feature_dfs = [computed_factors]
        if factor_expressions:
            logger.debug(f"  Loading {len(factor_expressions)} Qlib-compatible factors")
            qlib_factors = self._load_qlib_factors(factor_expressions)
            if qlib_factors is not None and not qlib_factors.empty:
                all_feature_dfs.append(qlib_factors)
        
        features_df = pd.concat(all_feature_dfs, axis=1)
        features_df = features_df.loc[:, ~features_df.columns.duplicated()]
        logger.debug(f"  Total factor count: {len(features_df.columns)}")

        def _normalize_multiindex(df, df_name):
            """Ensure MultiIndex has standard (datetime, instrument) level names."""
            if not isinstance(df.index, pd.MultiIndex):
                logger.warning(f"  {df_name} index is not MultiIndex: {type(df.index)}")
                return df
            
            names = list(df.index.names)
            logger.debug(f"  {df_name} index levels: {names}, "
                        f"dtypes: {[str(df.index.get_level_values(i).dtype) for i in range(len(names))]}, "
                        f"len: {len(df)}")
            
            new_names = list(names)
            for i, name in enumerate(names):
                level_vals = df.index.get_level_values(i)
                if name == 'datetime' or name == 'date':
                    new_names[i] = 'datetime'
                elif name == 'instrument' or name == 'stock':
                    new_names[i] = 'instrument'
                elif name is None:
                    # Infer from dtype
                    if pd.api.types.is_datetime64_any_dtype(level_vals):
                        new_names[i] = 'datetime'
                    elif level_vals.dtype == object or pd.api.types.is_string_dtype(level_vals):
                        new_names[i] = 'instrument'
            
            if new_names != names:
                logger.debug(f"  {df_name} index renamed: {names} -> {new_names}")
                df.index = df.index.set_names(new_names)
            actual_names = list(df.index.names)
            if len(actual_names) == 2 and actual_names == ['instrument', 'datetime']:
                df = df.swaplevel()
                logger.debug(f"  {df_name} index swapped to (datetime, instrument)")

            # Cached/custom factors can contain a mixture of strings and
            # Timestamps in the datetime level. Pandas then keeps that level
            # as object dtype, and Qlib eventually fails while slicing a
            # Timestamp against a string value. Rebuilding the MultiIndex is
            # safer than set_levels because it preserves the row-to-key map.
            actual_names = list(df.index.names)
            if len(actual_names) == 2 and actual_names == ['datetime', 'instrument']:
                datetime_values = pd.to_datetime(
                    df.index.get_level_values('datetime'), errors='raise'
                )
                instrument_values = df.index.get_level_values('instrument').astype(str)
                df = df.copy()
                df.index = pd.MultiIndex.from_arrays(
                    [datetime_values, instrument_values],
                    names=['datetime', 'instrument'],
                )
                df = df.sort_index()
                logger.debug(
                    f"  {df_name} index normalized to "
                    "(datetime64[ns], string instrument)"
                )
            
            return df
        
        features_df = _normalize_multiindex(features_df, "features")
        label_df = _normalize_multiindex(label_df, "label")
        
        common_index = features_df.index.intersection(label_df.index)
        if len(common_index) == 0 and len(features_df) > 0 and len(label_df) > 0:
            logger.warning("  Index intersection empty, aligning datetime types...")
            feat_dt = features_df.index.get_level_values('datetime')
            label_dt = label_df.index.get_level_values('datetime')
            logger.debug(f"  features datetime dtype={feat_dt.dtype}, sample={feat_dt[:3].tolist()}")
            logger.debug(f"  label    datetime dtype={label_dt.dtype}, sample={label_dt[:3].tolist()}")
            
            feat_inst = features_df.index.get_level_values('instrument')
            label_inst = label_df.index.get_level_values('instrument')
            logger.debug(f"  features instrument sample={feat_inst[:3].tolist()}")
            logger.debug(f"  label    instrument sample={label_inst[:3].tolist()}")
            
            try:
                if not pd.api.types.is_datetime64_any_dtype(feat_dt):
                    features_df.index = features_df.index.set_levels(
                        pd.to_datetime(feat_dt.unique()), level='datetime'
                    )
                    logger.debug("  features datetime converted to Timestamp")
                if not pd.api.types.is_datetime64_any_dtype(label_dt):
                    label_df.index = label_df.index.set_levels(
                        pd.to_datetime(label_dt.unique()), level='datetime'
                    )
                    logger.debug("  label datetime converted to Timestamp")
            except Exception as e:
                logger.warning(f"  datetime type conversion failed: {e}")
            common_index = features_df.index.intersection(label_df.index)
            logger.debug(f"  Intersection size after align: {len(common_index)}")

        if len(common_index) == 0:
            logger.warning("  Index intersection still empty, trying merge...")
            feat_reset = features_df.reset_index()
            label_reset = label_df.reset_index()
            dt_col = 'datetime' if 'datetime' in feat_reset.columns else feat_reset.columns[0]
            inst_col = 'instrument' if 'instrument' in feat_reset.columns else feat_reset.columns[1]
            
            merged = pd.merge(
                feat_reset, label_reset,
                on=[dt_col, inst_col],
                how='inner'
            )
            logger.debug(f"  Merged rows: {len(merged)}")
            if len(merged) == 0:
                raise ValueError(
                    f"Factor and label data could not be aligned. "
                    f"features: {len(features_df)} rows, index names={list(features_df.index.names)}; "
                    f"label: {len(label_df)} rows, index names={list(label_df.index.names)}"
                )
            
            merged = merged.set_index([dt_col, inst_col])
            merged.index.names = ['datetime', 'instrument']
            
            feature_cols = [c for c in features_df.columns if c in merged.columns]
            label_cols = [c for c in label_df.columns if c in merged.columns]
            features_df = merged[feature_cols]
            label_df = merged[label_cols]
        else:
            features_df = features_df.loc[common_index]
            label_df = label_df.loc[common_index]
        
        logger.debug(f"  Data rows: {len(features_df)}")
        if len(features_df) == 0:
            raise ValueError("No rows after index alignment; cannot run backtest")
        combined_df = pd.concat([features_df, label_df], axis=1)
        from qlib.data.dataset.processor import Fillna, ProcessInf, CSRankNorm, DropnaLabel
        feature_cols = list(features_df.columns)
        label_cols = list(label_df.columns)
        combined_df[feature_cols] = combined_df[feature_cols].fillna(0)
        combined_df[feature_cols] = combined_df[feature_cols].replace([np.inf, -np.inf], 0)
        dt_level = combined_df.index.names[0] if combined_df.index.names[0] else 0
        for col in feature_cols:
            combined_df[col] = combined_df.groupby(level=dt_level)[col].transform(
                lambda x: (x.rank(pct=True) - 0.5) if len(x) > 1 else 0
            )
        combined_df = combined_df.dropna(subset=label_cols)
        for col in label_cols:
            combined_df[col] = combined_df.groupby(level=dt_level)[col].transform(
                lambda x: (x.rank(pct=True) - 0.5) if len(x) > 1 else 0
            )
        
        logger.debug(f"  Rows after preprocessing: {len(combined_df)}")
        feature_tuples = [('feature', col) for col in feature_cols]
        label_tuples = [('label', col) for col in label_cols]
        
        combined_df_multi = combined_df.copy()
        combined_df_multi.columns = pd.MultiIndex.from_tuples(
            feature_tuples + label_tuples
        )
        
        class PrecomputedDataHandler(DataHandler):
            """DataHandler for precomputed data."""
            
            def __init__(self, data_df, segments):
                self._data = data_df
                self._segments = segments
            
            @property
            def data_loader(self):
                return None
            
            @property
            def instruments(self):
                try:
                    return list(self._data.index.get_level_values('instrument').unique())
                except KeyError:
                    return list(self._data.index.get_level_values(1).unique())
            
            def fetch(self, selector=None, level='datetime', col_set='feature',
                     data_key=None, squeeze=False, proc_func=None):
                if col_set in ('feature', 'label'):
                    result = self._data[col_set].copy()
                elif col_set == '__all' or col_set is None:
                    result = self._data.copy()
                else:
                    if isinstance(col_set, (list, tuple)):
                        result = self._data[list(col_set)].copy()
                    else:
                        result = self._data.copy()
                if selector is not None:
                    try:
                        dates = result.index.get_level_values('datetime')
                    except KeyError:
                        dates = result.index.get_level_values(0)
                    # DatasetH stores YAML segments as two-item lists and
                    # passes them straight through to handler.fetch().
                    if isinstance(selector, (tuple, list)) and len(selector) == 2:
                        start, end = selector
                        mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
                        result = result.loc[mask]
                    elif isinstance(selector, slice):
                        start = selector.start
                        end = selector.stop
                        if start is not None and end is not None:
                            mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
                            result = result.loc[mask]
                
                if squeeze and result.shape[1] == 1:
                    result = result.iloc[:, 0]
                
                return result
            
            def get_cols(self, col_set='feature'):
                if col_set in self._data.columns.get_level_values(0):
                    return list(self._data[col_set].columns)
                return list(self._data.columns.get_level_values(1))
            
            def setup_data(self, **kwargs):
                pass
            
            def config(self, **kwargs):
                pass
        
        handler = PrecomputedDataHandler(combined_df_multi, dataset_config['segments'])
        dataset = DatasetH(
            handler=handler,
            segments=dataset_config['segments']
        )
        
        logger.debug(f"  Custom factor mode: {len(feature_cols)} factors, {len(combined_df)} rows, train={dataset_config['segments']['train']}")
        
        return dataset
    
    def _compute_label(self, label_expr: str) -> pd.DataFrame:
        """Compute label using Qlib (label requires look-ahead)."""
        from qlib.data import D
        
        data_config = self.config['data']
        
        logger.debug(f"  Label expr: {label_expr}")
        
        stock_list = D.instruments(data_config['market'])
        
        label_df = D.features(
            stock_list,
            [label_expr],
            start_time=data_config['start_time'],
            end_time=data_config['end_time'],
            freq='day'
        )
        
        label_df.columns = ['LABEL0']
        
        logger.debug(f"  Label rows: {len(label_df)}")
        
        return label_df
    
    def _load_qlib_factors(self, factor_expressions: Dict[str, str]) -> Optional[pd.DataFrame]:
        """Load Qlib-compatible factors."""
        from qlib.data import D
        
        data_config = self.config['data']
        
        try:
            stock_list = D.instruments(data_config['market'])
            
            expressions = list(factor_expressions.values())
            names = list(factor_expressions.keys())
            
            df = D.features(
                stock_list,
                expressions,
                start_time=data_config['start_time'],
                end_time=data_config['end_time'],
                freq='day'
            )
            
            df.columns = names
            return df
        except Exception as e:
            logger.warning(f"Failed to load Qlib factors: {e}")
            return None

    @staticmethod
    def _normalize_signal_index(data, data_name: str):
        """Return Qlib signal data indexed by sorted (datetime, instrument)."""
        if not isinstance(data, (pd.Series, pd.DataFrame)):
            return data
        if not isinstance(data.index, pd.MultiIndex) or data.index.nlevels != 2:
            return data

        names = list(data.index.names)
        normalized_names = [str(name).lower() if name is not None else None for name in names]

        if 'datetime' in normalized_names:
            datetime_pos = normalized_names.index('datetime')
        elif 'date' in normalized_names:
            datetime_pos = normalized_names.index('date')
        elif 'instrument' in normalized_names:
            datetime_pos = 1 - normalized_names.index('instrument')
        else:
            # Fall back to the level whose complete contents can be parsed as
            # datetimes. This handles Qlib outputs whose first level is unnamed.
            datetime_pos = None
            for pos in range(2):
                parsed = pd.to_datetime(
                    data.index.get_level_values(pos), errors='coerce'
                )
                if not parsed.isna().any():
                    datetime_pos = pos
                    break
            if datetime_pos is None:
                raise ValueError(
                    f"{data_name} has no parseable datetime index level: {names}"
                )

        instrument_pos = 1 - datetime_pos
        datetime_values = pd.to_datetime(
            data.index.get_level_values(datetime_pos), errors='coerce'
        )
        if datetime_values.isna().any():
            bad_values = data.index.get_level_values(datetime_pos)[datetime_values.isna()]
            raise ValueError(
                f"{data_name} datetime index contains invalid values: "
                f"{list(pd.unique(bad_values))[:5]}"
            )
        instrument_values = data.index.get_level_values(instrument_pos).astype(str)

        normalized = data.copy()
        normalized.index = pd.MultiIndex.from_arrays(
            [datetime_values, instrument_values],
            names=['datetime', 'instrument'],
        )
        normalized = normalized.sort_index()
        logger.debug(
            f"  {data_name} signal index normalized: "
            f"names={normalized.index.names}, "
            f"dtypes={[str(normalized.index.get_level_values(i).dtype) for i in range(2)]}"
        )
        return normalized
    
    def _calculate_long_short_analytics(self, pred: pd.Series) -> Dict[str, Dict]:
        """Calculate equal-weight long, short, long-short and score deciles.

        Turnover is gross traded notional: sum(abs(w_t - w_(t-1))). Costs are
        charged on that notional. The long-short leg uses 50% long and 50%
        short exposure, for 100% total gross exposure.
        """
        from qlib.data import D

        ls_config = self.config.get('backtest', {}).get('long_short', {})
        quantile = float(ls_config.get('quantile', 0.1))
        min_positions = int(ls_config.get('min_positions', 20))
        transaction_cost = float(ls_config.get('transaction_cost', 0.0005))
        short_borrow_rate = float(ls_config.get('short_borrow_rate', 0.0))
        if not 0 < quantile <= 0.5:
            raise ValueError(f"long_short.quantile must be in (0, 0.5], got {quantile}")

        bt_config = self.config['backtest']['backtest']
        instruments = D.instruments(self.config['data']['market'])
        label_expr = self.config['dataset']['label']
        realized = D.features(
            instruments,
            [label_expr],
            start_time=bt_config['start_time'],
            end_time=bt_config['end_time'],
            freq='day',
        )
        realized = self._normalize_signal_index(realized, 'realized return').iloc[:, 0]
        signal = pred if isinstance(pred, pd.Series) else pred.iloc[:, 0]
        joined = pd.concat(
            [signal.rename('score'), realized.rename('realized_return')], axis=1, join='inner'
        ).replace([np.inf, -np.inf], np.nan).dropna()

        start = pd.Timestamp(bt_config['start_time'])
        end = pd.Timestamp(bt_config['end_time'])
        dates = joined.index.get_level_values('datetime')
        joined = joined[(dates >= start) & (dates <= end)]
        if joined.empty:
            raise ValueError('No prediction/return overlap for long-short analytics')

        previous = {
            'long': pd.Series(dtype=float),
            'short': pd.Series(dtype=float),
            'long_short': pd.Series(dtype=float),
            **{f'group_{number}': pd.Series(dtype=float) for number in range(1, 11)},
        }
        records = {name: [] for name in previous}
        borrow_daily = short_borrow_rate / 252.0

        for date, group in joined.groupby(level='datetime', sort=True):
            group = group.droplevel('datetime').sort_values('score')
            count = min(max(min_positions, int(np.ceil(len(group) * quantile))), len(group) // 2)
            if count < 1:
                continue
            bottom = group.iloc[:count]
            top = group.iloc[-count:]
            long_weights = pd.Series(1.0 / count, index=top.index)
            short_weights = pd.Series(-1.0 / count, index=bottom.index)
            weights = {
                'long': long_weights,
                'short': short_weights,
                'long_short': pd.concat([long_weights * 0.5, short_weights * 0.5]),
            }
            for number, members in enumerate(np.array_split(group.index.to_numpy(), 10), start=1):
                if len(members) > 0:
                    weights[f'group_{number}'] = pd.Series(1.0 / len(members), index=members)
            returns = group['realized_return']

            for name, current in weights.items():
                delta = current.subtract(previous[name], fill_value=0.0)
                turnover = float(delta.abs().sum())
                cost = turnover * transaction_cost
                gross_return = float((current * returns.reindex(current.index)).sum())
                borrow_cost = borrow_daily * float(current[current < 0].abs().sum())
                net_return = gross_return - cost - borrow_cost
                records[name].append({
                    'date': pd.Timestamp(date),
                    'gross_return': gross_return,
                    'net_return': net_return,
                    'turnover': turnover,
                    'transaction_cost': cost,
                    'borrow_cost': borrow_cost,
                    'positions': int(len(current)),
                })
                previous[name] = current

        def summarize(rows: List[Dict]) -> Dict:
            frame = pd.DataFrame(rows).set_index('date').sort_index()
            net = frame['net_return'].clip(lower=-0.999999)
            gross = frame['gross_return'].clip(lower=-0.999999)
            net_equity = (1.0 + net).cumprod()
            gross_equity = (1.0 + gross).cumprod()
            periods = len(frame)

            def annualized(equity: pd.Series) -> float:
                return float(equity.iloc[-1] ** (252.0 / periods) - 1.0) if periods else 0.0

            volatility = float(net.std(ddof=1) * np.sqrt(252)) if periods > 1 else 0.0
            sharpe = float(net.mean() / net.std(ddof=1) * np.sqrt(252)) if periods > 1 and net.std(ddof=1) > 0 else 0.0
            drawdown = net_equity / net_equity.cummax() - 1.0
            return {
                'annualized_gross_return': annualized(gross_equity),
                'annualized_net_return': annualized(net_equity),
                'total_net_return': float(net_equity.iloc[-1] - 1.0),
                'annualized_volatility': volatility,
                'sharpe_ratio': sharpe,
                'max_drawdown': float(drawdown.min()),
                'average_daily_turnover': float(frame['turnover'].mean()),
                'annualized_turnover': float(frame['turnover'].mean() * 252),
                'total_transaction_cost': float(frame['transaction_cost'].sum()),
                'total_borrow_cost': float(frame['borrow_cost'].sum()),
                'average_positions': float(frame['positions'].mean()),
                'daily_net_returns': [
                    {'date': idx.strftime('%Y-%m-%d'), 'value': float(value)}
                    for idx, value in net.items()
                ],
                'curve': [
                    {'date': idx.strftime('%Y-%m-%d'), 'value': float(value - 1.0)}
                    for idx, value in net_equity.items()
                ],
            }

        return {name: summarize(rows) for name, rows in records.items() if rows}

    def _train_and_backtest(
        self,
        dataset,
        exp_name: str,
        rec_name: str,
        output_name: Optional[str] = None,
        portfolio_mode: str = 'long',
        retrain_months: int = 12,
        min_train_years: int = 10,
        portfolio_optimization: bool = False,
    ) -> Dict:
        """Train model and run backtest."""
        from qlib.contrib.model.gbdt import LGBModel
        from qlib.data import D
        from qlib.workflow import R
        from qlib.workflow.record_temp import SignalRecord
        from qlib.backtest import backtest as qlib_backtest
        from qlib.contrib.eva.alpha import calc_ic
        from qlib.contrib.evaluate import risk_analysis
        
        model_config = self.config['model']
        backtest_config = self.config['backtest']['backtest']
        strategy_config = self.config['backtest']['strategy']
        
        metrics = {}
        
        with R.start(experiment_name=exp_name, recorder_name=rec_name):
            # Train model
            train_start = time.time()
            
            model_type = str(model_config.get('type', 'lgb')).lower()
            model_name = 'lightgbm' if model_type in ('lgb', 'lightgbm') else model_type
            if model_name not in ('lightgbm', 'pls5', 'lasso'):
                raise ValueError(f"Unsupported model type: {model_type}")
            from quantaalpha.backtest.expanding_models import ExpandingQlibModel
            model = ExpandingQlibModel(
                model_type=model_name,
                retrain_months=retrain_months,
                min_train_years=min_train_years,
            )
            
            model.fit(dataset)
            training_seconds = time.time() - train_start
            print(f"[4/4] Train {model_name.upper()} done ({training_seconds:.1f}s)")
            metrics['model'] = model_name
            metrics['training_seconds'] = training_seconds
            metrics['train_period'] = self.config['dataset']['segments'].get('train')
            metrics['valid_period'] = self.config['dataset']['segments'].get('valid')
            metrics['test_period'] = self.config['dataset']['segments'].get('test')
            metrics['expanding_window'] = True
            metrics['retrain_months'] = int(retrain_months)
            metrics['min_train_years'] = int(min_train_years)
            
            # Generate prediction
            # Backtest analytics must only receive out-of-sample predictions.
            # Predicting the whole dataset hid stale factor caches: training
            # succeeded on pre-test rows and the failure surfaced much later as
            # an unexplained empty join against test-period returns.
            pred = model.predict(dataset, segment='test')
            metrics['model_details'] = getattr(model, 'details', {})
            pred = self._normalize_signal_index(pred, "prediction")
            logger.debug(f"  Pred shape: {pred.shape}")

            if pred.empty:
                test_start, test_end = self.config['dataset']['segments']['test']
                raise ValueError(
                    "No out-of-sample predictions were generated for the test "
                    f"period {test_start} to {test_end}. Check factor cache coverage."
                )

            raw_pred = pred.copy()
            test_start, test_end = self.config['dataset']['segments']['test']
            from quantaalpha.market.profile import (
                apply_market_eligibility, eligibility_fields, get_market_profile,
            )
            profile = get_market_profile()
            instruments = D.instruments(profile.instrument)
            market_fields = profile.qlib_classification_fields + eligibility_fields(profile)
            industry_frame = D.features(
                instruments, market_fields, start_time=test_start, end_time=test_end, freq='day',
            )
            industry_frame.columns = [field[1:] for field in market_fields]
            raw_pred = apply_market_eligibility(raw_pred, industry_frame)
            classifications = industry_frame[list(profile.classification_fields)]
            pred = industry_rank_signal(
                raw_pred, classifications, profile.primary_classification, profile.classification_fields
            )
            if pred.empty:
                raise ValueError(
                    f'No {profile.primary_classification} data overlaps the independent backtest prediction'
                )
            robust_pred = industry_rank_signal(
                raw_pred, classifications, profile.robustness_classification, profile.classification_fields
            )
            metrics['industry_method'] = f'{profile.primary_classification}_neutral_rank'
            metrics['industry_exposure'] = calculate_industry_diagnostics(
                raw_pred, classifications, profile.classification_fields
            )
            metrics[f'industry_{profile.robustness_classification}_robustness'] = (
                self._calculate_long_short_analytics(robust_pred) if not robust_pred.empty else {}
            )
            if profile.mode == 'crypto' and 'funding_rate' in industry_frame:
                from quantaalpha.data.binance_futures_adapter import funding_sensitivity
                metrics['crypto_funding'] = funding_sensitivity(
                    raw_pred, industry_frame['funding_rate'],
                    quantile=float(os.environ.get('LONG_SHORT_QUANTILE', '0.1')),
                )

            all_analytics = self._calculate_long_short_analytics(pred)
            portfolio_analytics = {
                name: all_analytics[name]
                for name in ('long', 'short', 'long_short')
                if name in all_analytics
            }
            decile_analytics = {
                f'group_{number}': all_analytics[f'group_{number}']
                for number in range(1, 11)
                if f'group_{number}' in all_analytics
            }
            if portfolio_optimization:
                if portfolio_mode != 'long_short':
                    raise ValueError('MAXSER-PR portfolio optimization requires Long-Short mode')
                from quantaalpha.backtest.portfolio_optimization import calculate_maxser_pr_analytics
                equal_weight = portfolio_analytics.get('long_short')
                optimized, optimization_details = calculate_maxser_pr_analytics(pred, self.config)
                portfolio_analytics['long_short_equal_weight'] = equal_weight
                portfolio_analytics['long_short'] = optimized
                metrics['portfolio_optimization'] = optimization_details
            else:
                metrics['portfolio_optimization'] = {'enabled': False, 'method': 'equal_weight'}
            selected = portfolio_analytics.get(portfolio_mode)
            if selected is None:
                raise ValueError(f"Unsupported portfolio mode: {portfolio_mode}")
            metrics['portfolio_mode'] = portfolio_mode
            metrics['portfolio_analytics'] = portfolio_analytics
            metrics['decile_analytics'] = decile_analytics
            metrics['annualized_return'] = selected['annualized_net_return']
            metrics['sharpe_ratio'] = selected['sharpe_ratio']
            metrics['max_drawdown'] = selected['max_drawdown']
            metrics['average_daily_turnover'] = selected['average_daily_turnover']
            metrics['annualized_turnover'] = selected['annualized_turnover']
            metrics['total_transaction_cost'] = selected['total_transaction_cost']
            metrics['cumulative_curve'] = selected['curve']

            long_short_daily = portfolio_analytics.get('long_short', {}).get('daily_net_returns', [])
            if long_short_daily:
                if profile.mode == 'cn':
                    from quantaalpha.backtest.china_evaluation import (
                        calculate_barra_style_exposures, regress_china_asset_pricing,
                    )
                    metrics['barra_style_exposure'] = calculate_barra_style_exposures(
                        raw_pred, instruments, test_start, test_end
                    )
                    metrics['asset_pricing'] = regress_china_asset_pricing(
                        long_short_daily, instruments, test_start, test_end
                    )
                    metrics['asset_pricing_source'] = 'local_point_in_time_cn_ff_proxies'
                elif profile.mode == 'us':
                    from quantaalpha.backtest.asset_pricing import regress_asset_pricing
                    wrds_root = os.environ.get('WRDS_ROOT', '')
                    if wrds_root:
                        metrics['asset_pricing'] = regress_asset_pricing(long_short_daily, wrds_root)
                        metrics['asset_pricing_source'] = 'wrds_fama_french' 
            
            # Save the already-normalized prediction rather than asking
            # SignalRecord to call model.predict() a second time and recreate
            # the mixed-type index. Save the matching label explicitly too so
            # SigAnaRecord evaluates the same normalized signal.
            recorder = R.get_recorder()
            pred_record = pred.to_frame("score") if isinstance(pred, pd.Series) else pred
            recorder.save_objects(**{"pred.pkl": pred_record})
            raw_label = SignalRecord.generate_label(dataset)
            raw_label = self._normalize_signal_index(raw_label, "label")
            recorder.save_objects(**{"label.pkl": raw_label})
            logger.info(
                f"Normalized signal record saved for Experiment {recorder.experiment_id}"
            )
            
            # Compute IC directly from the normalized signal and label. Qlib's
            # SigAnaRecord logs metric names such as "Rank IC"; MLflow 3.13
            # rejects those names asynchronously, which made valid IC values
            # disappear from otherwise successful combined backtests.
            try:
                ic_series, ric_series = calc_ic(
                    pred_record.iloc[:, 0], raw_label.iloc[:, 0]
                )
                recorder.save_objects(
                    artifact_path="sig_analysis",
                    **{"ic.pkl": ic_series, "ric.pkl": ric_series},
                )

                if isinstance(ic_series, pd.Series) and len(ic_series) > 0:
                    metrics['IC'] = float(ic_series.mean())
                    metrics['ICIR'] = (
                        float(ic_series.mean() / ic_series.std())
                        if ic_series.std() > 0 else 0.0
                    )

                if isinstance(ric_series, pd.Series) and len(ric_series) > 0:
                    metrics['Rank IC'] = float(ric_series.mean())
                    metrics['Rank ICIR'] = (
                        float(ric_series.mean() / ric_series.std())
                        if ric_series.std() > 0 else 0.0
                    )

                print(f"  IC={metrics.get('IC', 0):.6f}, ICIR={metrics.get('ICIR', 0):.6f}, "
                      f"Rank IC={metrics.get('Rank IC', 0):.6f}, Rank ICIR={metrics.get('Rank ICIR', 0):.6f}")
            except Exception as e:
                logger.warning(f"IC analysis failed: {e}")
            # Qlib's stock portfolio simulator supplies a CSI 300 benchmark
            # when benchmark=None.  Crypto analytics above are already computed
            # from the out-of-sample signal without a stock benchmark, so do not
            # run that stock-only simulation for Binance futures.
            if profile.mode == 'crypto':
                logger.info(
                    'Skipping Qlib stock portfolio simulation for Crypto; '
                    'using benchmark-free out-of-sample portfolio analytics.'
                )
                return metrics

            # Portfolio backtest
            try:
                bt_start = time.time()
                
                market = self.config['data']['market']
                instruments = D.instruments(market)
                stock_list = D.list_instruments(
                    instruments,
                    start_time=backtest_config['start_time'],
                    end_time=backtest_config['end_time'],
                    as_list=True
                )
                logger.debug(f"  Stock count: {len(stock_list)}")
                if len(stock_list) < 10:
                    logger.warning(f"Stock pool too small ({len(stock_list)}), results may be unreliable")
                # Filter invalid price signals
                try:
                    price_data = D.features(
                        stock_list,
                        ['$close'],
                        start_time=backtest_config['start_time'],
                        end_time=backtest_config['end_time'],
                        freq='day'
                    )
                    invalid_mask = (price_data['$close'] == 0) | (price_data['$close'].isna())
                    invalid_count = invalid_mask.sum()
                    
                    if invalid_count > 0:
                        logger.debug(f"  Found {invalid_count} zero/NaN price records")
                        if isinstance(pred, pd.Series):
                            invalid_indices = invalid_mask[invalid_mask].index
                            invalid_set = set()
                            for idx in invalid_indices:
                                instrument, datetime = idx
                                invalid_set.add((datetime, instrument))
                            
                            filtered_count = 0
                            for idx in pred.index:
                                if idx in invalid_set:
                                    pred.loc[idx] = np.nan
                                    filtered_count += 1
                            
                            if filtered_count > 0:
                                logger.debug(f"  Filtered {filtered_count} invalid price signals")
                except Exception as filter_err:
                    logger.warning(f"Price filter failed: {filter_err}")
                
                qlib_end_time = pd.Timestamp(backtest_config['end_time'])
                full_calendar = pd.DatetimeIndex(D.calendar(freq='day'))
                if len(full_calendar) > 1 and qlib_end_time >= full_calendar[-1]:
                    # Daily strategies need the next calendar point to close
                    # the final step. The latest stored session has no next
                    # point, so stop the executable simulation one session
                    # earlier while the manual long/short analytics continues
                    # to use every return that is actually available.
                    qlib_end_time = full_calendar[-2]
                    logger.info(
                        "Qlib portfolio end adjusted to %s because %s is the "
                        "last available calendar session",
                        qlib_end_time.strftime('%Y-%m-%d'),
                        backtest_config['end_time'],
                    )

                portfolio_metric_dict, indicator_dict = qlib_backtest(
                    executor={
                        "class": "SimulatorExecutor",
                        "module_path": "qlib.backtest.executor",
                        "kwargs": {
                            "time_per_step": "day",
                            "generate_portfolio_metrics": True,
                            "verbose": False,
                            "indicator_config": {"show_indicator": False}
                        }
                    },
                    strategy={
                        "class": strategy_config['class'],
                        "module_path": strategy_config['module_path'],
                        "kwargs": {
                            "signal": pred,
                            "topk": strategy_config['kwargs']['topk'],
                            "n_drop": strategy_config['kwargs']['n_drop']
                        }
                    },
                    start_time=backtest_config['start_time'],
                    end_time=qlib_end_time,
                    account=backtest_config['account'],
                    benchmark=backtest_config['benchmark'],
                    exchange_kwargs={
                        "codes": stock_list,
                        **backtest_config['exchange_kwargs']
                    }
                )
                
                print(f"  Portfolio backtest done ({time.time()-bt_start:.1f}s)")
                # Extract portfolio metrics
                if portfolio_metric_dict and "1day" in portfolio_metric_dict:
                    report_df, positions_df = portfolio_metric_dict["1day"]
                    
                    if isinstance(report_df, pd.DataFrame) and 'return' in report_df.columns:
                        portfolio_return = report_df['return'].replace([np.inf, -np.inf], np.nan).fillna(0)
                        bench_return = report_df['bench'].replace([np.inf, -np.inf], np.nan).fillna(0) if 'bench' in report_df.columns else 0
                        cost = report_df['cost'].replace([np.inf, -np.inf], np.nan).fillna(0) if 'cost' in report_df.columns else 0
                        
                        excess_return_with_cost = portfolio_return - bench_return - cost
                        excess_return_with_cost = excess_return_with_cost.dropna()
                        
                        if len(excess_return_with_cost) > 0:
                            try:
                                daily_df = report_df.copy()
                                daily_df['excess_return'] = excess_return_with_cost
                                
                                output_dir = Path(self.config['experiment'].get('output_dir', './backtest_v2_results'))
                                output_dir.mkdir(parents=True, exist_ok=True)
                                
                                file_prefix = output_name if output_name else exp_name
                                csv_path = output_dir / f"{file_prefix}_cumulative_excess.csv"
                                save_df = daily_df[['excess_return']].copy()
                                save_df.columns = ['daily_excess_return']
                                save_df['cumulative_excess_return'] = save_df['daily_excess_return'].cumsum()
                                
                                save_df.index.name = 'date'
                                save_df.to_csv(csv_path)
                                logger.debug(f"  Daily excess return saved: {csv_path}")
                            except Exception as csv_err:
                                logger.warning(f"Failed to save daily CSV: {csv_err}")

                            analysis = risk_analysis(excess_return_with_cost)
                            
                            if isinstance(analysis, pd.DataFrame):
                                analysis = analysis['risk'] if 'risk' in analysis.columns else analysis.iloc[:, 0]
                            
                            ann_ret = float(analysis.get('annualized_return', 0))
                            info_ratio = float(analysis.get('information_ratio', 0))
                            max_dd = float(analysis.get('max_drawdown', 0))
                            
                            if not np.isnan(ann_ret) and not np.isinf(ann_ret):
                                metrics['qlib_long_excess_annualized_return'] = ann_ret
                            if not np.isnan(info_ratio) and not np.isinf(info_ratio):
                                metrics['qlib_long_excess_information_ratio'] = info_ratio
                            if not np.isnan(max_dd) and not np.isinf(max_dd):
                                metrics['qlib_long_excess_max_drawdown'] = max_dd
                            
                            if max_dd != 0 and not np.isnan(ann_ret) and not np.isinf(ann_ret):
                                calmar = ann_ret / abs(max_dd)
                                if not np.isnan(calmar) and not np.isinf(calmar):
                                    metrics['qlib_long_excess_calmar_ratio'] = calmar
                            
            except Exception as e:
                logger.warning(f"Portfolio backtest failed: {e}")
                import traceback
                traceback.print_exc()
        
        return metrics
    
    def _print_results(self, metrics: Dict, total_time: float):
        """Print result summary."""
        def _f(val, fmt='.6f'):
            return format(val, fmt) if isinstance(val, (int, float)) else 'N/A'

        print(f"\n{'='*50}")
        print("Backtest Results")
        print(f"{'='*50}")
        print("[IC Metrics]")
        print(f"  IC: {_f(metrics.get('IC'))}  ICIR: {_f(metrics.get('ICIR'))}")
        print(f"  Rank IC: {_f(metrics.get('Rank IC'))}  Rank ICIR: {_f(metrics.get('Rank ICIR'))}")
        print("[Strategy Metrics]")
        print(f"  Ann. Return: {_f(metrics.get('annualized_return'), '.4f')}  Max DD: {_f(metrics.get('max_drawdown'), '.4f')}")
        print(f"  Sharpe: {_f(metrics.get('sharpe_ratio'), '.4f')}  "
              f"Avg Daily Turnover: {_f(metrics.get('average_daily_turnover'), '.4f')}")
        print(f"Total time: {total_time:.1f}s")
        print(f"{'='*50}")
    
    def _save_results(self, metrics: Dict, exp_name: str, 
                     factor_source: str, num_factors: int, elapsed: float,
                     output_name: Optional[str] = None):
        """Save results."""
        output_dir = Path(self.config['experiment'].get('output_dir', './backtest_v2_results'))
        output_dir.mkdir(parents=True, exist_ok=True)
        if output_name:
            output_file = f"{output_name}_backtest_metrics.json"
        else:
            output_file = self.config['experiment']['output_metrics_file']
        output_path = output_dir / output_file
        
        result_data = {
            "experiment_name": exp_name,
            "factor_source": factor_source,
            "num_factors": num_factors,
            "metrics": metrics,
            "config": {
                "data_range": f"{self.config['data']['start_time']} ~ {self.config['data']['end_time']}",
                "test_range": f"{self.config['dataset']['segments']['test'][0]} ~ {self.config['dataset']['segments']['test'][1]}",
                "backtest_range": f"{self.config['backtest']['backtest']['start_time']} ~ {self.config['backtest']['backtest']['end_time']}",
                "market": self.config['data']['market'],
                "benchmark": self.config['backtest']['backtest']['benchmark']
            },
            "elapsed_seconds": elapsed
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, separators=(',', ':'))
        
        print(f"Results saved: {output_path}")
        summary_file = output_dir / "batch_summary.json"
        summary_data = []
        if summary_file.exists():
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary_data = json.load(f)
            except:
                summary_data = []
        
        ann_ret = metrics.get('annualized_return')
        mdd = metrics.get('max_drawdown')
        calmar_ratio = None
        if ann_ret is not None and mdd is not None and mdd != 0:
            calmar_ratio = ann_ret / abs(mdd)
        
        summary_entry = {
            "name": output_name or exp_name,
            "num_factors": num_factors,
            "IC": metrics.get('IC'),
            "ICIR": metrics.get('ICIR'),
            "Rank_IC": metrics.get('Rank IC'),
            "Rank_ICIR": metrics.get('Rank ICIR'),
            "annualized_return": ann_ret,
            "information_ratio": metrics.get('information_ratio'),
            "max_drawdown": mdd,
            "calmar_ratio": calmar_ratio,
            "elapsed_seconds": elapsed
        }
        summary_data.append(summary_entry)
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"Appended to summary: {summary_file}")
        from quantaalpha.backtest.retention import enforce_backtest_retention
        keep = int(os.environ.get('BACKTEST_RESULT_RETENTION', '3'))
        metrics['storage_retention'] = enforce_backtest_retention(
            output_dir, project_root=project_root, keep=keep
        )
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, separators=(',', ':'))
