#!/usr/bin/env python3
"""
Factor loader - multiple factor sources.

Supports:
1. Qlib built-in: alpha158, alpha158(20), alpha360
2. Custom factor library (JSON).
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


def _quality_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if value == value and value not in (float("inf"), float("-inf")) else None


def _quality_metric(metrics: Dict[str, Any], *keys: str,
                    suffixes: Tuple[str, ...] = ()) -> Optional[float]:
    for key in keys:
        value = _quality_number(metrics.get(key))
        if value is not None:
            return value
    for suffix in suffixes:
        for key, raw in metrics.items():
            if str(key).lower().endswith(suffix.lower()):
                value = _quality_number(raw)
                if value is not None:
                    return value
    return None


def assess_factor_quality(factor_info: Dict[str, Any]) -> Dict[str, Any]:
    """Score validation evidence without using held-out test results.

    Version 4 aligns predictive thresholds with the evaluated holding period,
    combines the two FF significance statistics into one evidence item, and
    normalizes over the evidence that is actually available.  A coverage
    confidence penalty and evidence-group gates prevent a sparse factor from
    receiving a misleading high score.
    """
    metrics = factor_info.get('backtest_results') or factor_info.get('backtestResults') or {}
    if not isinstance(metrics, dict):
        metrics = {}

    metadata = factor_info.get('metadata') or {}
    market_mode = str(
        factor_info.get('market_mode')
        or factor_info.get('marketMode')
        or (metadata.get('market_mode') if isinstance(metadata, dict) else '')
        or os.environ.get('MARKET_MODE', 'us')
    ).strip().lower()
    is_cn = market_mode == 'cn'
    is_crypto = market_mode == 'crypto'
    portfolio_leg = 'long' if is_cn else 'long_short'
    portfolio_label = 'Long-only' if is_cn else 'Long–Short'
    primary_industry = 'sw_l1' if is_cn else ('market_group' if is_crypto else 'gsector')
    robustness_industry = 'sw_l2' if is_cn else ('market_group' if is_crypto else 'ggroup')

    metric_keys = tuple(str(key).lower() for key in metrics)
    available_frequencies = [
        freq for freq in ('day', 'week', 'month')
        if any(key.startswith(f'{freq}.') for key in metric_keys)
    ]
    statistics_metadata = factor_info.get('statistics_metadata') or {}
    explicit_frequency = str(
        (statistics_metadata.get('evaluation_frequency')
         if isinstance(statistics_metadata, dict) else '') or ''
    ).strip().lower()
    primary_frequency = (
        explicit_frequency if explicit_frequency in available_frequencies
        else available_frequencies[0] if available_frequencies else 'day'
    )

    def frequency_metric(tail: str, *fallbacks: str) -> Optional[float]:
        return _quality_metric(metrics, f'{primary_frequency}.{tail}', *fallbacks)

    ic = _quality_metric(metrics, 'IC', 'ic', 'mean_ic',
                         '1day.excess_return_without_cost.ic', suffixes=('.ic',))
    rank_ic = _quality_metric(metrics, 'Rank IC', 'RankIC', 'rank_ic',
                              '1day.excess_return_without_cost.rank_ic', suffixes=('.rank_ic',))
    icir = _quality_metric(metrics, 'ICIR', 'icir', 'mean_ic_ir',
                           '1day.excess_return_without_cost.information_coefficient_ir')
    rank_icir = _quality_metric(metrics, 'Rank ICIR', 'RankICIR', 'rank_ic_ir',
                                '1day.excess_return_without_cost.rank_ic_ir')
    net_return = frequency_metric(
        f'{portfolio_leg}.annualized_net_return',
        '1day.excess_return_with_cost.annualized_return',
        '1day.excess_return_without_cost.annualized_return')
    gross_return = frequency_metric(f'{portfolio_leg}.annualized_gross_return')
    sharpe = frequency_metric(
        f'{portfolio_leg}.sharpe_ratio',
        '1day.excess_return_with_cost.information_ratio',
        '1day.excess_return_without_cost.information_ratio')
    max_drawdown = frequency_metric(
        f'{portfolio_leg}.max_drawdown',
        '1day.excess_return_with_cost.max_drawdown',
        '1day.excess_return_without_cost.max_drawdown')
    monotonicity = frequency_metric('decile_monotonicity')
    robust_rank_ic = _quality_metric(metrics, f'industry.{robustness_industry}.robustness.Rank IC')
    robust_net_return = _quality_metric(
        metrics,
        f'industry.{robustness_industry}.robustness.{primary_frequency}.{portfolio_leg}.annualized_net_return')
    industry_coverage = _quality_metric(metrics, f'industry.{primary_industry}.coverage')
    turnover = frequency_metric(f'{portfolio_leg}.average_turnover_per_rebalance')
    alpha_t = _quality_metric(
        metrics,
        f'{primary_frequency}.asset_pricing.ff5_mom.alpha_t_stat',
        f'{primary_frequency}.asset_pricing.ff5.alpha_t_stat',
        f'{primary_frequency}.asset_pricing.ff3_mom.alpha_t_stat',
        f'{primary_frequency}.asset_pricing.ff3.alpha_t_stat',
    )
    alpha_p = _quality_metric(
        metrics,
        f'{primary_frequency}.asset_pricing.ff5_mom.alpha_p_value',
        f'{primary_frequency}.asset_pricing.ff5.alpha_p_value',
        f'{primary_frequency}.asset_pricing.ff3_mom.alpha_p_value',
        f'{primary_frequency}.asset_pricing.ff3.alpha_p_value',
    )

    components: Dict[str, Dict[str, Any]] = {}
    groups = set()
    available_weight = 0.0
    earned = 0.0

    def add(name: str, label: str, value: Optional[float], weight: float,
            fraction: Any, group: str) -> None:
        nonlocal available_weight, earned
        if value is None:
            return
        part = max(0.0, min(1.0, float(fraction(value)))) * weight
        available_weight += weight
        earned += part
        groups.add(group)
        components[name] = {
            'label': label, 'value': round(value, 6),
            'score': round(part, 2), 'maxScore': weight,
        }

    ic_target = {'day': .03, 'week': .02, 'month': .01}[primary_frequency]
    if is_crypto:
        rank_ic_target = {'day': .04, 'week': .03, 'month': .02}[primary_frequency]
        # IC remains in the report for diagnosis but has no influence on
        # Crypto selection. Cross-sectional rank predictability is the target.
        add('rankIc', f'RankIC（{primary_frequency}，主目标）', rank_ic, 30,
            lambda x: max(x, 0) / rank_ic_target, 'predictive')
        add('rankIcStability', 'RankICIR 稳定性', rank_icir, 15,
            lambda x: abs(x) / .50, 'predictive')
    else:
        add('ic', f'|IC|（{primary_frequency}）', ic, 6,
            lambda x: abs(x) / ic_target, 'predictive')
        add('rankIc', f'|RankIC|（{primary_frequency}）', rank_ic, 6,
            lambda x: abs(x) / ic_target, 'predictive')
        stability = max(abs(v) for v in (icir, rank_icir) if v is not None) if any(
            v is not None for v in (icir, rank_icir)) else None
        add('icStability', 'IC/RankIC 稳定性', stability, 8, lambda x: x / .5, 'predictive')

    add('netReturn', f'{portfolio_label} 年化净收益', net_return, 8 if is_crypto else 7,
        lambda x: max(x, 0) / (.15 if is_cn else .12), 'economic')
    add('sharpe', f'{portfolio_label} Sharpe', sharpe, 12 if is_crypto else 10,
        lambda x: max(x, 0) / 1.5, 'economic')
    add('maxDrawdown', f'{portfolio_label} 最大回撤', max_drawdown, 8,
        lambda x: (0.50 - abs(x)) / .40, 'economic')

    add('monotonicity', '十分组单调性', monotonicity, 10,
        lambda x: abs(x) / .8, 'robustness')
    frequency_returns = [
        _quality_metric(metrics, f'{freq}.{portfolio_leg}.annualized_net_return')
        for freq in ('day', 'week', 'month')
    ]
    frequency_returns = [x for x in frequency_returns if x is not None]
    if len(frequency_returns) >= 2:
        consistency = sum(x > 0 for x in frequency_returns) / len(frequency_returns)
        add('frequencyConsistency', '日/周/月频一致性', consistency, 5 if is_crypto else 4,
            lambda x: x, 'robustness')

    if not is_crypto and rank_ic is not None and robust_rank_ic is not None:
        rank_match = 1.0 if rank_ic * robust_rank_ic > 0 else 0.0
        rank_ratio = min(abs(robust_rank_ic) / max(abs(rank_ic), 1e-12), 1.0)
        return_match = (
            1.0 if net_return is not None and robust_net_return is not None
            and net_return * robust_net_return > 0 else 0.0
        )
        industry_robustness = (rank_match + rank_ratio + return_match) / 3.0
        add('industryRobustness', f'{primary_industry}/{robustness_industry} 稳健性', industry_robustness, 7,
            lambda x: x, 'robustness')

    if not is_crypto and (alpha_t is not None or alpha_p is not None):
        alpha_parts = []
        if alpha_t is not None:
            alpha_parts.append(max(0.0, min(1.0, alpha_t / 3.0)))
        if alpha_p is not None:
            alpha_parts.append(max(0.0, min(1.0, (0.10 - alpha_p) / .10)))
        alpha_evidence = sum(alpha_parts) / len(alpha_parts)
        add('alphaSignificance',
            ('A股 Alpha 综合显著性' if is_cn else 'FF Alpha 综合显著性'),
            alpha_evidence, 10, lambda x: x, 'significance')

    add('turnover', '换手可交易性', turnover, 5,
        lambda x: (2.0 - x) / 1.75, 'tradability')
    if gross_return is not None and net_return is not None:
        cost_drag = max(gross_return - net_return, 0.0)
        add('costDrag', '年化成本损耗', cost_drag, 4 if is_crypto else 5,
            lambda x: (.10 - x) / .08, 'tradability')

    if is_crypto:
        funding_corr = _quality_metric(metrics, 'crypto.funding_signal_rank_corr')
        add('fundingIndependence', '资金费率暴露控制', funding_corr, 3,
            lambda x: (.50 - abs(x)) / .50, 'tradability')

    # Optional library-independence evidence. It is deliberately not invented
    # when a correlation heatmap has not persisted the statistic yet.
    correlation_sources = [factor_info, metadata, statistics_metadata, metrics]
    max_library_correlation = None
    for source in correlation_sources:
        if not isinstance(source, dict):
            continue
        max_library_correlation = _quality_metric(
            source, 'max_abs_factor_correlation', 'library_max_abs_correlation',
            'max_factor_correlation', 'redundancy_max_correlation')
        if max_library_correlation is not None:
            break
    add('independence', '因子库独立性', max_library_correlation, 0 if is_crypto else 10,
        lambda x: (.95 - abs(x)) / .45, 'independence')

    # Only train and validation are eligible for stability scoring.  The held-
    # out test split is never read here.
    split_results = factor_info.get('split_results') or factor_info.get('splitResults') or {}
    if isinstance(split_results, dict):
        def split_metrics(name: str) -> Dict[str, Any]:
            payload = split_results.get(name) or {}
            if not isinstance(payload, dict):
                return {}
            for key in ('metrics', 'backtest_results', 'backtestResults'):
                if isinstance(payload.get(key), dict):
                    return payload[key]
            return payload

        train_metrics, valid_metrics = split_metrics('train'), split_metrics('valid')
        train_return = _quality_metric(
            train_metrics, f'{primary_frequency}.{portfolio_leg}.annualized_net_return')
        valid_return = _quality_metric(
            valid_metrics, f'{primary_frequency}.{portfolio_leg}.annualized_net_return')
        if train_return is not None and valid_return is not None:
            same_sign = 1.0 if train_return * valid_return > 0 else 0.0
            magnitude = min(abs(valid_return) / max(abs(train_return), 1e-12), 1.0)
            add('trainValidationStability', '训练/验证稳定性',
                (same_sign + magnitude) / 2.0, 0 if is_crypto else 4, lambda x: x, 'robustness')

    coverage = min(1.0, available_weight / 100.0)
    normalized_score = earned / available_weight * 100.0 if available_weight else 0.0
    confidence_factor = min(1.0, coverage / .80)
    score = normalized_score * confidence_factor
    reasons = []
    if coverage < .65:
        reasons.append('评价指标覆盖不足，不能评为高质量')
    if len(groups) < 4:
        reasons.append('评价维度少于四类，不能评为高质量')
    if net_return is not None and net_return <= 0:
        reasons.append(f'{portfolio_label} 年化净收益不为正')
    if sharpe is not None and sharpe <= 0:
        reasons.append(f'{portfolio_label} Sharpe 不为正')
    if not is_crypto and industry_coverage is not None and industry_coverage < .90:
        reasons.append(f'{primary_industry} 覆盖率低于90%')
    crypto_rank_medium = not is_crypto or (rank_ic is not None and rank_ic >= .02)
    crypto_rank_high = not is_crypto or (
        rank_ic is not None and rank_ic >= .03
        and rank_icir is not None and abs(rank_icir) >= .25
    )
    if is_crypto and not crypto_rank_medium:
        reasons.append('验证集日频 RankIC 低于0.02')
    elif is_crypto and not crypto_rank_high:
        reasons.append('高质量要求 RankIC≥0.03 且 |RankICIR|≥0.25')

    if not components:
        explicit = str(factor_info.get('quality', '')).strip().lower()
        quality = {
            'high': 'high', 'high_quality': 'high',
            'medium': 'medium', 'medium_quality': 'medium',
            'low': 'low', 'low_quality': 'low',
        }.get(explicit, 'low')
    elif (score >= 70 and coverage >= .65 and len(groups) >= 4
          and (net_return is None or net_return > 0)
          and (sharpe is None or sharpe > 0)
          and crypto_rank_high):
        quality = 'high'
    elif (score >= 45 and coverage >= .40 and len(groups) >= 3
          and crypto_rank_medium):
        quality = 'medium'
    else:
        quality = 'low'

    return {
        'quality': quality,
        'score': round(score, 1),
        'coverage': round(coverage, 2),
        'evidenceGroups': sorted(groups),
        'components': components,
        'reasons': reasons,
        'portfolioLeg': portfolio_leg,
        'marketMode': market_mode,
        'primaryFrequency': primary_frequency,
        'methodVersion': ('crypto-rankic-only-v6-validation' if is_crypto
                          else 'multidimensional-v4-validation-balanced'),
    }


def classify_factor_quality(factor_info: Dict[str, Any]) -> str:
    """Return the quality bucket from the multi-dimensional assessment."""
    return assess_factor_quality(factor_info)['quality']


class FactorLoader:
    """Factor loader."""
    
    ALPHA158_20_FACTORS = {
        "ROC0": "($close-$open)/$open",
        "ROC1": "$close/Ref($close, 1)-1",
        "ROC5": "($close-Ref($close, 5))/Ref($close, 5)",
        "ROC10": "($close-Ref($close, 10))/Ref($close, 10)",
        "ROC20": "($close-Ref($close, 20))/Ref($close, 20)",
        "VRATIO5": "$volume/Mean($volume, 5)",
        "VRATIO10": "$volume/Mean($volume, 10)",
        "VSTD5_RATIO": "Std($volume, 5)/Mean($volume, 5)",
        "RANGE": "($high-$low)/$open",
        "VOLATILITY5": "Std($close, 5)/$close",
        "VOLATILITY10": "Std($close, 10)/$close",
        "RET_VOL5": "Std($close/Ref($close, 1)-1, 5)",
        "RSV5": "($close-Min($low, 5))/(Max($high, 5)-Min($low, 5)+1e-12)",
        "RSV10": "($close-Min($low, 10))/(Max($high, 10)-Min($low, 10)+1e-12)",
        "HIGH_RATIO5": "$close/Max($high, 5)-1",
        "LOW_RATIO5": "$close/Min($low, 5)-1",
        "SHADOW_RATIO": "($high-$close)/($close-$low+1e-12)",
        "BODY_RATIO": "($close-$open)/($high-$low+1e-12)",
        "MA_RATIO5_10": "Mean($close, 5)/Mean($close, 10)-1",
        "MA_RATIO10_20": "Mean($close, 10)/Mean($close, 20)-1",
    }
    
    ALPHA158_FACTORS = {
        "KMID": "($close-$open)/$open",
        "KLEN": "($high-$low)/$open",
        "KMID2": "($close-$open)/($high-$low+1e-12)",
        "KUP": "($high-Greater($open, $close))/$open",
        "KUP2": "($high-Greater($open, $close))/($high-$low+1e-12)",
        "KLOW": "(Less($open, $close)-$low)/$open",
        "KLOW2": "(Less($open, $close)-$low)/($high-$low+1e-12)",
        "KSFT": "(2*$close-$high-$low)/$open",
        "KSFT2": "(2*$close-$high-$low)/($high-$low+1e-12)",
        
        "OPEN0": "$open/$close",
        "HIGH0": "$high/$close",
        "LOW0": "$low/$close",
        "VWAP0": "$vwap/$close",
        
        "ROC5": "Ref($close, 5)/$close",
        "ROC10": "Ref($close, 10)/$close",
        "ROC20": "Ref($close, 20)/$close",
        "ROC30": "Ref($close, 30)/$close",
        "ROC60": "Ref($close, 60)/$close",
        
        "MA5": "Mean($close, 5)/$close",
        "MA10": "Mean($close, 10)/$close",
        "MA20": "Mean($close, 20)/$close",
        "MA30": "Mean($close, 30)/$close",
        "MA60": "Mean($close, 60)/$close",
        
        "STD5": "Std($close, 5)/$close",
        "STD10": "Std($close, 10)/$close",
        "STD20": "Std($close, 20)/$close",
        "STD30": "Std($close, 30)/$close",
        "STD60": "Std($close, 60)/$close",
        
        "BETA5": "Slope($close, 5)/$close",
        "BETA10": "Slope($close, 10)/$close",
        "BETA20": "Slope($close, 20)/$close",
        "BETA30": "Slope($close, 30)/$close",
        "BETA60": "Slope($close, 60)/$close",
        
        "RSQR5": "Rsquare($close, 5)",
        "RSQR10": "Rsquare($close, 10)",
        "RSQR20": "Rsquare($close, 20)",
        "RSQR30": "Rsquare($close, 30)",
        "RSQR60": "Rsquare($close, 60)",
        
        "RESI5": "Resi($close, 5)/$close",
        "RESI10": "Resi($close, 10)/$close",
        "RESI20": "Resi($close, 20)/$close",
        "RESI30": "Resi($close, 30)/$close",
        "RESI60": "Resi($close, 60)/$close",
        
        "MAX5": "Max($high, 5)/$close",
        "MAX10": "Max($high, 10)/$close",
        "MAX20": "Max($high, 20)/$close",
        "MAX30": "Max($high, 30)/$close",
        "MAX60": "Max($high, 60)/$close",
        
        "MIN5": "Min($low, 5)/$close",
        "MIN10": "Min($low, 10)/$close",
        "MIN20": "Min($low, 20)/$close",
        "MIN30": "Min($low, 30)/$close",
        "MIN60": "Min($low, 60)/$close",
        
        # QTLU
        "QTLU5": "Quantile($close, 5, 0.8)/$close",
        "QTLU10": "Quantile($close, 10, 0.8)/$close",
        "QTLU20": "Quantile($close, 20, 0.8)/$close",
        "QTLU30": "Quantile($close, 30, 0.8)/$close",
        "QTLU60": "Quantile($close, 60, 0.8)/$close",
        
        # QTLD
        "QTLD5": "Quantile($close, 5, 0.2)/$close",
        "QTLD10": "Quantile($close, 10, 0.2)/$close",
        "QTLD20": "Quantile($close, 20, 0.2)/$close",
        "QTLD30": "Quantile($close, 30, 0.2)/$close",
        "QTLD60": "Quantile($close, 60, 0.2)/$close",
        
        # RANK
        "RANK5": "Rank($close, 5)",
        "RANK10": "Rank($close, 10)",
        "RANK20": "Rank($close, 20)",
        "RANK30": "Rank($close, 30)",
        "RANK60": "Rank($close, 60)",
        
        # RSV
        "RSV5": "($close-Min($low, 5))/(Max($high, 5)-Min($low, 5)+1e-12)",
        "RSV10": "($close-Min($low, 10))/(Max($high, 10)-Min($low, 10)+1e-12)",
        "RSV20": "($close-Min($low, 20))/(Max($high, 20)-Min($low, 20)+1e-12)",
        "RSV30": "($close-Min($low, 30))/(Max($high, 30)-Min($low, 30)+1e-12)",
        "RSV60": "($close-Min($low, 60))/(Max($high, 60)-Min($low, 60)+1e-12)",
        
        # IMAX
        "IMAX5": "IdxMax($high, 5)/5",
        "IMAX10": "IdxMax($high, 10)/10",
        "IMAX20": "IdxMax($high, 20)/20",
        "IMAX30": "IdxMax($high, 30)/30",
        "IMAX60": "IdxMax($high, 60)/60",
        
        # IMIN
        "IMIN5": "IdxMin($low, 5)/5",
        "IMIN10": "IdxMin($low, 10)/10",
        "IMIN20": "IdxMin($low, 20)/20",
        "IMIN30": "IdxMin($low, 30)/30",
        "IMIN60": "IdxMin($low, 60)/60",
        
        # IMXD
        "IMXD5": "(IdxMax($high, 5)-IdxMin($low, 5))/5",
        "IMXD10": "(IdxMax($high, 10)-IdxMin($low, 10))/10",
        "IMXD20": "(IdxMax($high, 20)-IdxMin($low, 20))/20",
        "IMXD30": "(IdxMax($high, 30)-IdxMin($low, 30))/30",
        "IMXD60": "(IdxMax($high, 60)-IdxMin($low, 60))/60",
        
        # CORR
        "CORR5": "Corr($close, Log($volume+1), 5)",
        "CORR10": "Corr($close, Log($volume+1), 10)",
        "CORR20": "Corr($close, Log($volume+1), 20)",
        "CORR30": "Corr($close, Log($volume+1), 30)",
        "CORR60": "Corr($close, Log($volume+1), 60)",
        
        # CORD
        "CORD5": "Corr($close/Ref($close,1), Log($volume/Ref($volume, 1)+1), 5)",
        "CORD10": "Corr($close/Ref($close,1), Log($volume/Ref($volume, 1)+1), 10)",
        "CORD20": "Corr($close/Ref($close,1), Log($volume/Ref($volume, 1)+1), 20)",
        "CORD30": "Corr($close/Ref($close,1), Log($volume/Ref($volume, 1)+1), 30)",
        "CORD60": "Corr($close/Ref($close,1), Log($volume/Ref($volume, 1)+1), 60)",
        
        # CNTP
        "CNTP5": "Mean($close>Ref($close, 1), 5)",
        "CNTP10": "Mean($close>Ref($close, 1), 10)",
        "CNTP20": "Mean($close>Ref($close, 1), 20)",
        "CNTP30": "Mean($close>Ref($close, 1), 30)",
        "CNTP60": "Mean($close>Ref($close, 1), 60)",
        
        # CNTN
        "CNTN5": "Mean($close<Ref($close, 1), 5)",
        "CNTN10": "Mean($close<Ref($close, 1), 10)",
        "CNTN20": "Mean($close<Ref($close, 1), 20)",
        "CNTN30": "Mean($close<Ref($close, 1), 30)",
        "CNTN60": "Mean($close<Ref($close, 1), 60)",
        
        # CNTD
        "CNTD5": "Mean($close>Ref($close, 1), 5)-Mean($close<Ref($close, 1), 5)",
        "CNTD10": "Mean($close>Ref($close, 1), 10)-Mean($close<Ref($close, 1), 10)",
        "CNTD20": "Mean($close>Ref($close, 1), 20)-Mean($close<Ref($close, 1), 20)",
        "CNTD30": "Mean($close>Ref($close, 1), 30)-Mean($close<Ref($close, 1), 30)",
        "CNTD60": "Mean($close>Ref($close, 1), 60)-Mean($close<Ref($close, 1), 60)",
        
        # SUMP
        "SUMP5": "Sum(Greater($close-Ref($close, 1), 0), 5)/(Sum(Abs($close-Ref($close, 1)), 5)+1e-12)",
        "SUMP10": "Sum(Greater($close-Ref($close, 1), 0), 10)/(Sum(Abs($close-Ref($close, 1)), 10)+1e-12)",
        "SUMP20": "Sum(Greater($close-Ref($close, 1), 0), 20)/(Sum(Abs($close-Ref($close, 1)), 20)+1e-12)",
        "SUMP30": "Sum(Greater($close-Ref($close, 1), 0), 30)/(Sum(Abs($close-Ref($close, 1)), 30)+1e-12)",
        "SUMP60": "Sum(Greater($close-Ref($close, 1), 0), 60)/(Sum(Abs($close-Ref($close, 1)), 60)+1e-12)",
        
        # SUMN
        "SUMN5": "Sum(Greater(Ref($close, 1)-$close, 0), 5)/(Sum(Abs($close-Ref($close, 1)), 5)+1e-12)",
        "SUMN10": "Sum(Greater(Ref($close, 1)-$close, 0), 10)/(Sum(Abs($close-Ref($close, 1)), 10)+1e-12)",
        "SUMN20": "Sum(Greater(Ref($close, 1)-$close, 0), 20)/(Sum(Abs($close-Ref($close, 1)), 20)+1e-12)",
        "SUMN30": "Sum(Greater(Ref($close, 1)-$close, 0), 30)/(Sum(Abs($close-Ref($close, 1)), 30)+1e-12)",
        "SUMN60": "Sum(Greater(Ref($close, 1)-$close, 0), 60)/(Sum(Abs($close-Ref($close, 1)), 60)+1e-12)",
        
        # SUMD
        "SUMD5": "(Sum(Greater($close-Ref($close, 1), 0), 5)-Sum(Greater(Ref($close, 1)-$close, 0), 5))/(Sum(Abs($close-Ref($close, 1)), 5)+1e-12)",
        "SUMD10": "(Sum(Greater($close-Ref($close, 1), 0), 10)-Sum(Greater(Ref($close, 1)-$close, 0), 10))/(Sum(Abs($close-Ref($close, 1)), 10)+1e-12)",
        "SUMD20": "(Sum(Greater($close-Ref($close, 1), 0), 20)-Sum(Greater(Ref($close, 1)-$close, 0), 20))/(Sum(Abs($close-Ref($close, 1)), 20)+1e-12)",
        "SUMD30": "(Sum(Greater($close-Ref($close, 1), 0), 30)-Sum(Greater(Ref($close, 1)-$close, 0), 30))/(Sum(Abs($close-Ref($close, 1)), 30)+1e-12)",
        "SUMD60": "(Sum(Greater($close-Ref($close, 1), 0), 60)-Sum(Greater(Ref($close, 1)-$close, 0), 60))/(Sum(Abs($close-Ref($close, 1)), 60)+1e-12)",
        
        # VMA
        "VMA5": "Mean($volume, 5)/($volume+1e-12)",
        "VMA10": "Mean($volume, 10)/($volume+1e-12)",
        "VMA20": "Mean($volume, 20)/($volume+1e-12)",
        "VMA30": "Mean($volume, 30)/($volume+1e-12)",
        "VMA60": "Mean($volume, 60)/($volume+1e-12)",
        
        # VSTD
        "VSTD5": "Std($volume, 5)/($volume+1e-12)",
        "VSTD10": "Std($volume, 10)/($volume+1e-12)",
        "VSTD20": "Std($volume, 20)/($volume+1e-12)",
        "VSTD30": "Std($volume, 30)/($volume+1e-12)",
        "VSTD60": "Std($volume, 60)/($volume+1e-12)",
        
        # WVMA
        "WVMA5": "Std(Abs($close/Ref($close, 1)-1)*$volume, 5)/(Mean(Abs($close/Ref($close, 1)-1)*$volume, 5)+1e-12)",
        "WVMA10": "Std(Abs($close/Ref($close, 1)-1)*$volume, 10)/(Mean(Abs($close/Ref($close, 1)-1)*$volume, 10)+1e-12)",
        "WVMA20": "Std(Abs($close/Ref($close, 1)-1)*$volume, 20)/(Mean(Abs($close/Ref($close, 1)-1)*$volume, 20)+1e-12)",
        "WVMA30": "Std(Abs($close/Ref($close, 1)-1)*$volume, 30)/(Mean(Abs($close/Ref($close, 1)-1)*$volume, 30)+1e-12)",
        "WVMA60": "Std(Abs($close/Ref($close, 1)-1)*$volume, 60)/(Mean(Abs($close/Ref($close, 1)-1)*$volume, 60)+1e-12)",
        
        # VSUMP
        "VSUMP5": "Sum(Greater($volume-Ref($volume, 1), 0), 5)/(Sum(Abs($volume-Ref($volume, 1)), 5)+1e-12)",
        "VSUMP10": "Sum(Greater($volume-Ref($volume, 1), 0), 10)/(Sum(Abs($volume-Ref($volume, 1)), 10)+1e-12)",
        "VSUMP20": "Sum(Greater($volume-Ref($volume, 1), 0), 20)/(Sum(Abs($volume-Ref($volume, 1)), 20)+1e-12)",
        "VSUMP30": "Sum(Greater($volume-Ref($volume, 1), 0), 30)/(Sum(Abs($volume-Ref($volume, 1)), 30)+1e-12)",
        "VSUMP60": "Sum(Greater($volume-Ref($volume, 1), 0), 60)/(Sum(Abs($volume-Ref($volume, 1)), 60)+1e-12)",
        
        # VSUMN
        "VSUMN5": "Sum(Greater(Ref($volume, 1)-$volume, 0), 5)/(Sum(Abs($volume-Ref($volume, 1)), 5)+1e-12)",
        "VSUMN10": "Sum(Greater(Ref($volume, 1)-$volume, 0), 10)/(Sum(Abs($volume-Ref($volume, 1)), 10)+1e-12)",
        "VSUMN20": "Sum(Greater(Ref($volume, 1)-$volume, 0), 20)/(Sum(Abs($volume-Ref($volume, 1)), 20)+1e-12)",
        "VSUMN30": "Sum(Greater(Ref($volume, 1)-$volume, 0), 30)/(Sum(Abs($volume-Ref($volume, 1)), 30)+1e-12)",
        "VSUMN60": "Sum(Greater(Ref($volume, 1)-$volume, 0), 60)/(Sum(Abs($volume-Ref($volume, 1)), 60)+1e-12)",
        
        # VSUMD
        "VSUMD5": "(Sum(Greater($volume-Ref($volume, 1), 0), 5)-Sum(Greater(Ref($volume, 1)-$volume, 0), 5))/(Sum(Abs($volume-Ref($volume, 1)), 5)+1e-12)",
        "VSUMD10": "(Sum(Greater($volume-Ref($volume, 1), 0), 10)-Sum(Greater(Ref($volume, 1)-$volume, 0), 10))/(Sum(Abs($volume-Ref($volume, 1)), 10)+1e-12)",
        "VSUMD20": "(Sum(Greater($volume-Ref($volume, 1), 0), 20)-Sum(Greater(Ref($volume, 1)-$volume, 0), 20))/(Sum(Abs($volume-Ref($volume, 1)), 20)+1e-12)",
        "VSUMD30": "(Sum(Greater($volume-Ref($volume, 1), 0), 30)-Sum(Greater(Ref($volume, 1)-$volume, 0), 30))/(Sum(Abs($volume-Ref($volume, 1)), 30)+1e-12)",
        "VSUMD60": "(Sum(Greater($volume-Ref($volume, 1), 0), 60)-Sum(Greater(Ref($volume, 1)-$volume, 0), 60))/(Sum(Abs($volume-Ref($volume, 1)), 60)+1e-12)",
    }
    
    def __init__(self, config: Dict):
        """Args: config: config dict."""
        self.config = config
        self.factor_source_config = config.get('factor_source', {})
        
    def load_factors(self) -> Tuple[Dict[str, str], List[Dict]]:
        """
        Returns: (qlib_compatible_factors {name: expression}, custom_factors list).
        """
        source_type = self.factor_source_config.get('type', 'alpha158_20')
        
        logger.debug(f"Loading factor source: {source_type}")
        
        if source_type == 'alpha158':
            return self._load_alpha158(), []
        elif source_type == 'alpha158_20':
            return self._load_alpha158_20(), []
        elif source_type == 'alpha360':
            return self._load_alpha360(), []
        elif source_type == 'custom':
            return self._load_custom_factors()
        elif source_type == 'combined':
            return self._load_combined_factors()
        else:
            raise ValueError(f"Unsupported factor source type: {source_type}")
    
    def _load_alpha158_20(self) -> Dict[str, str]:
        """Load Alpha158(20) factors."""
        logger.debug(f"  Load Alpha158(20): {len(self.ALPHA158_20_FACTORS)} factors")
        return self.ALPHA158_20_FACTORS.copy()
    
    def _load_alpha158(self) -> Dict[str, str]:
        """Load Alpha158 factors."""
        logger.debug(f"  Load Alpha158: {len(self.ALPHA158_FACTORS)} factors")
        return self.ALPHA158_FACTORS.copy()
    
    def _load_alpha360(self) -> Dict[str, str]:
        """Load Alpha360 factors (multi-window price/volume)."""
        alpha360_factors = {}
        
        windows = [5, 10, 20, 30, 60]
        for w in windows:
            alpha360_factors[f"ROC{w}"] = f"Ref($close, {w})/$close"
            alpha360_factors[f"MA{w}"] = f"Mean($close, {w})/$close"
            alpha360_factors[f"STD{w}"] = f"Std($close, {w})/$close"
            alpha360_factors[f"MAX{w}"] = f"Max($high, {w})/$close"
            alpha360_factors[f"MIN{w}"] = f"Min($low, {w})/$close"
            alpha360_factors[f"RSV{w}"] = f"($close-Min($low, {w}))/(Max($high, {w})-Min($low, {w})+1e-12)"
            alpha360_factors[f"VMA{w}"] = f"Mean($volume, {w})/($volume+1e-12)"
            alpha360_factors[f"VSTD{w}"] = f"Std($volume, {w})/($volume+1e-12)"
            alpha360_factors[f"CORR{w}"] = f"Corr($close, Log($volume+1), {w})"
        
        extended_windows = [3, 7, 15, 40, 120]
        for w in extended_windows:
            alpha360_factors[f"ROC{w}"] = f"Ref($close, {w})/$close"
            alpha360_factors[f"MA{w}"] = f"Mean($close, {w})/$close"
            alpha360_factors[f"STD{w}"] = f"Std($close, {w})/$close"
        
        alpha360_factors.update({
            "KMID": "($close-$open)/$open",
            "KLEN": "($high-$low)/$open",
            "KMID2": "($close-$open)/($high-$low+1e-12)",
            "KUP": "($high-Greater($open, $close))/$open",
            "KLOW": "(Less($open, $close)-$low)/$open",
            "KSFT": "(2*$close-$high-$low)/$open",
        })
        
        logger.debug(f"  Load Alpha360: {len(alpha360_factors)} factors")
        return alpha360_factors
    
    def _load_custom_factors(self) -> Tuple[Dict[str, str], List[Dict]]:
        """Load custom factor library; all factors use custom calculator (expr_parser + function_lib). Returns ({}, custom_factors)."""
        custom_config = self.factor_source_config.get('custom', {})
        json_files = custom_config.get('json_files', [])
        quality_filter = custom_config.get('quality_filter')
        max_factors = custom_config.get('max_factors')
        
        custom_factors = []
        
        for json_file in json_files:
            file_path = Path(json_file)
            if not file_path.exists():
                logger.warning(f"  Factor library file not found: {json_file}")
                continue
            
            factors = self._parse_all_factors_from_json(file_path, quality_filter)
            custom_factors.extend(factors)
        
        if max_factors and len(custom_factors) > max_factors:
            custom_factors = custom_factors[:max_factors]
        
        logger.debug(f"  Load custom factors: {len(custom_factors)} (custom calculator)")
        
        return {}, custom_factors
    
    def _parse_all_factors_from_json(self, file_path: Path, 
                                     quality_filter: Optional[str] = None) -> List[Dict]:
        """Parse all factors from JSON; returns list of dicts with cache_location if present."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        factors = data.get('factors', {})
        result = []
        
        for factor_id, factor_info in factors.items():
            if quality_filter and quality_filter != 'all':
                if classify_factor_quality(factor_info) != quality_filter:
                    continue
            
            factor_name = factor_info.get('factor_name', factor_id)
            factor_expr = factor_info.get('factor_expression', '')
            
            if not factor_expr:
                continue
            
            factor_dict = {
                'factor_id': factor_id,
                'factor_name': factor_name,
                'factor_expression': factor_expr,
                'factor_description': factor_info.get('factor_description', ''),
            }
            
            cache_location = factor_info.get('cache_location')
            if cache_location:
                factor_dict['cache_location'] = cache_location
            
            result.append(factor_dict)
        
        return result
    
    def _load_combined_factors(self) -> Tuple[Dict[str, str], List[Dict]]:
        """Load combined factors (official + custom)."""
        combined_config = self.factor_source_config.get('combined', {})
        official_source = combined_config.get('official_source', 'alpha158_20')
        include_custom = combined_config.get('include_custom', True)
        
        if official_source == 'alpha158':
            qlib_compatible = self._load_alpha158()
        elif official_source == 'alpha158_20':
            qlib_compatible = self._load_alpha158_20()
        elif official_source == 'alpha360':
            qlib_compatible = self._load_alpha360()
        else:
            qlib_compatible = {}
        
        needs_llm = []
        
        if include_custom:
            custom_compatible, custom_llm = self._load_custom_factors()
            qlib_compatible.update(custom_compatible)
            needs_llm.extend(custom_llm)
        
        logger.debug(f"  Combined: {len(qlib_compatible)} Qlib-compatible, {len(needs_llm)} need LLM")
        return qlib_compatible, needs_llm
    
    def _parse_factor_json(self, file_path: Path, 
                          quality_filter: Optional[str] = None) -> Tuple[Dict[str, str], List[Dict]]:
        """Parse factor JSON; returns (qlib_compatible, needs_llm)."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        factors = data.get('factors', {})
        qlib_compatible = {}
        needs_llm = []
        
        for factor_id, factor_info in factors.items():
            if quality_filter and quality_filter != 'all':
                if classify_factor_quality(factor_info) != quality_filter:
                    continue
            
            factor_name = factor_info.get('factor_name', factor_id)
            factor_expr = factor_info.get('factor_expression', '')
            
            if not factor_expr:
                continue
            
            if self._is_qlib_compatible(factor_expr):
                converted = self._convert_to_qlib_expression(factor_expr)
                if converted:
                    qlib_compatible[factor_name] = converted
                else:
                    needs_llm.append({
                        'factor_id': factor_id,
                        'factor_name': factor_name,
                        'factor_expression': factor_expr,
                        'factor_description': factor_info.get('factor_description', ''),
                        'variables': factor_info.get('variables', {})
                    })
            else:
                needs_llm.append({
                    'factor_id': factor_id,
                    'factor_name': factor_name,
                    'factor_expression': factor_expr,
                    'factor_description': factor_info.get('factor_description', ''),
                    'variables': factor_info.get('variables', {})
                })
        
        return qlib_compatible, needs_llm
    
    def _is_qlib_compatible(self, expr: str) -> bool:
        """Check if expression is Qlib-compatible (unsupported operators list)."""
        unsupported_patterns = [
            'ZSCORE(', 'RANK(', 'TS_ZSCORE(', 'TS_RANK(',
            'DELAY(', 'DELTA(', 'DECAYLINEAR(',
            'REGBETA(', 'REGRESI(', 'SEQUENCE(',
            'SUMIF(', 'COUNTIF(', 'FILTER(',
            'POW(', 'SIGN(', 'INV(',
            'RSI(', 'MACD(', 'BB_',
            'EMA(', 'WMA(', 'SMA(',
            'TS_CORR(', 'TS_COVARIANCE(',
            'TS_MAD(', 'TS_QUANTILE(', 'TS_PCTCHANGE(',
            'HIGHDAY(', 'LOWDAY(', 'SUMAC(',
            'TS_ARGMAX(', 'TS_ARGMIN(',
            '?', ':'  # ternary
        ]
        
        expr_upper = expr.upper()
        for pattern in unsupported_patterns:
            if pattern.upper() in expr_upper:
                return False
        
        return True
    
    def _convert_to_qlib_expression(self, expr: str) -> Optional[str]:
        """Convert custom expression to Qlib-compatible; returns None if not possible."""
        conversions = {
            'TS_MEAN': 'Mean',
            'TS_STD': 'Std',
            'TS_VAR': 'Var',
            'TS_MAX': 'Max',
            'TS_MIN': 'Min',
            'TS_SUM': 'Sum',
            '$return': '($close/Ref($close,1)-1)',
        }
        
        result = expr
        for old, new in conversions.items():
            result = result.replace(old, new)
        
        if self._is_qlib_compatible(result):
            return result
        
        return None
    
    def get_factor_info(self) -> Dict[str, Any]:
        """Return factor source summary."""
        source_type = self.factor_source_config.get('type', 'alpha158_20')
        
        if source_type == 'alpha158':
            return {
                'type': 'alpha158',
                'count': len(self.ALPHA158_FACTORS),
                'description': 'Qlib Alpha158'
            }
        elif source_type == 'alpha158_20':
            return {
                'type': 'alpha158_20',
                'count': len(self.ALPHA158_20_FACTORS),
                'description': 'Qlib Alpha158(20) core'
            }
        elif source_type == 'alpha360':
            return {
                'type': 'alpha360',
                'count': 'dynamic',
                'description': 'Qlib Alpha360'
            }
        elif source_type == 'custom':
            return {
                'type': 'custom',
                'json_files': self.factor_source_config.get('custom', {}).get('json_files', []),
                'description': 'Custom factor library'
            }
        else:
            return {
                'type': source_type,
                'description': 'Unknown factor source'
            }
