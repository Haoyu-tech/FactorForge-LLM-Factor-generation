"""A-share DuckDB catalogue and point-in-time Qlib builder.

The source database is treated as immutable.  Only daily stock observations are
read; fund/ETF and minute tables are deliberately outside this adapter.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


UNIVERSES = {
    "csi300": "000300.SH",
    "csi500": "000905.SH",
    "sme_composite": "399101.SZ",
}
FINANCIAL_FIELDS = [
    "roe", "roa", "grossprofit_margin", "netprofit_margin", "debt_to_assets",
    "assets_turn", "current_ratio", "q_sales_yoy", "basic_eps_yoy",
    "q_ocf_to_sales", "roic", "assets_yoy",
]
SW_FIELDS = ["sw_l1", "sw_l2", "sw_l3"]


def _connect(path: str | Path):
    import duckdb
    return duckdb.connect(str(path), read_only=True)


def _date(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return str(pd.Timestamp(value).date())


def _qlib_symbol(ts_code: str) -> str:
    code, exchange = str(ts_code).split(".")
    return f"{exchange.upper()}{code}"


def inspect_cn_duckdb(db_path: str | Path) -> dict:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(path)
    con = _connect(path)
    try:
        required = [
            "ts_daily", "ts_daily_basic", "ts_adj_factor", "ts_stock_basic",
            "ts_stock_st", "ts_namechange", "ts_index_weight",
            "ts_index_member_all", "ts_fina_indicator", "ts_trade_cal",
        ]
        existing = {row[0] for row in con.execute("show tables").fetchall()}
        tables = {name: name in existing for name in required}
        price = con.execute(
            "select count(*), count(distinct ts_code), min(trade_date), max(trade_date) from ts_daily"
        ).fetchone()
        coverage = {}
        for universe, index_code in UNIVERSES.items():
            row = con.execute(
                "select count(*), count(distinct con_code), min(trade_date), max(trade_date) "
                "from ts_index_weight where index_code=?", [index_code]
            ).fetchone()
            coverage[universe] = {
                "indexCode": index_code, "rows": int(row[0]), "stocks": int(row[1]),
                "start": _date(row[2]), "end": _date(row[3]),
                "preCoveragePolicy": (
                    "按历史流动性与自由流通市值半年重建（近似）"
                    if universe != "sme_composite" else "按原中小板002股票及上市日期重建"
                ),
            }
        st = con.execute(
            "select count(*), count(distinct ts_code), min(trade_date), max(trade_date) from ts_stock_st"
        ).fetchone()
        sw = con.execute(
            "select count(*), count(distinct ts_code), min(in_date), max(coalesce(out_date,in_date)) "
            "from ts_index_member_all"
        ).fetchone()
        return {
            "path": str(path), "sizeGb": round(path.stat().st_size / 1024**3, 2),
            "ready": all(tables.values()), "tables": tables,
            "daily": {"rows": int(price[0]), "stocks": int(price[1]),
                      "start": _date(price[2]), "end": _date(price[3])},
            "universes": coverage,
            "stHistory": {"rows": int(st[0]), "stocks": int(st[1]),
                          "start": _date(st[2]), "end": _date(st[3]),
                          "nameChangeFallback": True},
            "shenwan": {"rows": int(sw[0]), "stocks": int(sw[1]),
                        "start": _date(sw[2]), "end": _date(sw[3]),
                        "levels": ["sw_l1", "sw_l2", "sw_l3"]},
            "financialTiming": "严格按 ann_date 公告日向后可用；不按报告期提前填充",
            "notes": [
                "分钟、ETF、基金表不会被读取",
                "CSI 300/500 官方权重快照覆盖前采用可复现的半年近似重建，并在清单中标记 approximate",
                "ST 先用 ts_stock_st，早期历史用名称变更区间补充",
            ],
        }
    finally:
        con.close()


def _load_fundamentals(con, start: str, end: str) -> dict[str, pd.DataFrame]:
    columns = ",".join(FINANCIAL_FIELDS)
    frame = con.execute(
        f"select ts_code, ann_date, end_date, {columns} from ts_fina_indicator "
        "where ann_date is not null and ann_date <= ?", [end.replace("-", "")]
    ).df()
    if frame.empty:
        return {}
    frame["available_date"] = pd.to_datetime(frame["ann_date"].astype(str), errors="coerce")
    frame["report_date"] = pd.to_datetime(frame["end_date"].astype(str), errors="coerce")
    frame = frame.dropna(subset=["available_date"]).sort_values(["ts_code", "available_date", "report_date"])
    frame = frame.drop_duplicates(["ts_code", "available_date"], keep="last")
    frame[FINANCIAL_FIELDS] = frame[FINANCIAL_FIELDS].apply(pd.to_numeric, errors="coerce")
    frame["book_to_price"] = np.nan
    return {str(code): group for code, group in frame.groupby("ts_code", sort=False)}


def _load_sw_memberships(con) -> dict[str, pd.DataFrame]:
    frame = con.execute(
        "select ts_code,l1_code,l2_code,l3_code,in_date,out_date from ts_index_member_all"
    ).df()
    if frame.empty:
        return {}
    frame["in_date"] = pd.to_datetime(frame["in_date"].astype(str), errors="coerce")
    frame["out_date"] = pd.to_datetime(frame["out_date"].astype(str), errors="coerce")
    for source, target in (("l1_code", "sw_l1"), ("l2_code", "sw_l2"), ("l3_code", "sw_l3")):
        frame[target] = pd.to_numeric(frame[source].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
    frame = frame.dropna(subset=["in_date"]).sort_values(["ts_code", "in_date"])
    return {str(code): group for code, group in frame.groupby("ts_code", sort=False)}


def _load_st_intervals(con) -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    """Load compact ST ranges; daily status rows are collapsed for fast builds."""
    direct = con.execute("select ts_code,trade_date from ts_stock_st order by ts_code,trade_date").df()
    direct["date"] = pd.to_datetime(direct["trade_date"].astype(str), errors="coerce")
    names = con.execute(
        "select ts_code,start_date,end_date from ts_namechange where upper(name) like '%ST%'"
    ).df()
    names["start"] = pd.to_datetime(names["start_date"].astype(str), errors="coerce")
    names["end"] = pd.to_datetime(names["end_date"].astype(str), errors="coerce").fillna(pd.Timestamp("2099-12-31"))
    output: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    for code, group in direct.dropna(subset=["date"]).groupby("ts_code", sort=False):
        dates = sorted(pd.unique(group["date"]))
        ranges = []
        if dates:
            range_start = previous = pd.Timestamp(dates[0])
            for value in dates[1:]:
                value = pd.Timestamp(value)
                if (value - previous).days > 7:
                    ranges.append((range_start, previous))
                    range_start = value
                previous = value
            ranges.append((range_start, previous))
        output[str(code)] = ranges
    for row in names.dropna(subset=["start"]).itertuples(index=False):
        output.setdefault(str(row.ts_code), []).append((row.start, row.end))
    return output

def _mark_intervals(dates: pd.Series, intervals) -> np.ndarray:
    values = pd.to_datetime(dates).to_numpy(dtype="datetime64[ns]")
    mask = np.zeros(len(values), dtype=bool)
    for start, end in intervals or []:
        mask |= (values >= np.datetime64(start)) & (values <= np.datetime64(end))
    return mask


def _compact_membership(rows: pd.DataFrame, end_date: str) -> list[tuple[str, str, str]]:
    """Turn dated snapshots into non-overlapping Qlib membership intervals."""
    if rows.empty:
        return []
    rows = rows.copy()
    rows["date"] = pd.to_datetime(rows["date"])
    snapshots = sorted(rows["date"].unique())
    result: list[tuple[str, str, str]] = []
    open_since: dict[str, pd.Timestamp] = {}
    previous: set[str] = set()
    for date in snapshots:
        current = set(rows.loc[rows["date"] == date, "symbol"].astype(str))
        for symbol in current - previous:
            open_since[symbol] = pd.Timestamp(date)
        for symbol in previous - current:
            result.append((symbol, str(open_since.pop(symbol).date()), str((pd.Timestamp(date) - pd.Timedelta(days=1)).date())))
        previous = current
    for symbol in previous:
        result.append((symbol, str(open_since[symbol].date()), end_date))
    return result


def _build_universes(con, start_date: str, end_date: str, stock_basic: pd.DataFrame) -> tuple[dict[str, list], dict]:
    output: dict[str, list] = {}
    metadata: dict[str, dict] = {}
    for name, code in (("csi300", "000300.SH"), ("csi500", "000905.SH")):
        exact = con.execute(
            "select trade_date as date, con_code from ts_index_weight "
            "where index_code=? and trade_date between ? and ? order by trade_date",
            [code, start_date.replace("-", ""), end_date.replace("-", "")],
        ).df()
        exact_start = _date(exact["date"].min()) if not exact.empty else None
        approximate = []
        cutoff = pd.Timestamp(exact_start) if exact_start else pd.Timestamp(end_date) + pd.Timedelta(days=1)
        # Reconstruct on January/July boundaries. With source prices beginning
        # in January 2010, July 2010 is the first leakage-free ranking. Its first
        # window contains roughly 115 A-share sessions; later windows use more.
        boundaries = [
            pd.Timestamp(year=year, month=month, day=1)
            for year in range(pd.Timestamp(start_date).year, cutoff.year + 1)
            for month in (1, 7)
        ]
        for rebalance in (date for date in boundaries if pd.Timestamp(start_date) <= date < cutoff):
            lookback_end = (rebalance - pd.Timedelta(days=1)).strftime("%Y%m%d")
            lookback_start = (rebalance - pd.Timedelta(days=400)).strftime("%Y%m%d")
            ranks = con.execute(
                "select d.ts_code, avg(d.amount) as liquidity, avg(b.total_mv) as total_mv "
                "from ts_daily d join ts_daily_basic b using(ts_code,trade_date) "
                "join ts_stock_basic s using(ts_code) "
                "where d.trade_date between ? and ? and s.list_date < ? "
                "and (d.ts_code like '%.SH' or d.ts_code like '%.SZ') "
                "group by d.ts_code having count(*) >= 100 order by total_mv desc",
                [lookback_start, lookback_end, (rebalance - pd.Timedelta(days=375)).strftime("%Y%m%d")],
            ).df()
            if ranks.empty:
                continue
            liquid = ranks[ranks["liquidity"] >= ranks["liquidity"].quantile(0.2)].sort_values("total_mv", ascending=False)
            chosen = liquid.head(300) if name == "csi300" else liquid.iloc[300:800]
            approximate.extend({"date": rebalance, "con_code": item} for item in chosen["ts_code"])
        combined = pd.concat([pd.DataFrame(approximate), exact], ignore_index=True)
        if not combined.empty:
            combined["symbol"] = combined["con_code"].map(_qlib_symbol)
            output[name] = _compact_membership(combined[["date", "symbol"]], end_date)
        else:
            output[name] = []
        metadata[name] = {"officialSnapshotStart": exact_start, "preSnapshot": "semiannual_liquidity_market_cap_reconstruction_min_100_sessions", "exactRows": len(exact)}

    small = stock_basic[stock_basic["ts_code"].astype(str).str.startswith("002")].copy()
    small["list_date"] = pd.to_datetime(small["list_date"].astype(str), errors="coerce")
    output["sme_composite"] = [
        (_qlib_symbol(row.ts_code), str(max(pd.Timestamp(start_date), row.list_date + pd.Timedelta(days=14)).date()), end_date)
        for row in small.itertuples(index=False) if pd.notna(row.list_date)
    ]
    metadata["sme_composite"] = {"officialRule": "all former SME-board 002 shares; entry approximated at tenth trading day", "officialSnapshotStart": None}
    return output, metadata


def build_cn_qlib(
    db_path: str | Path,
    output_dir: str | Path,
    project_root: str | Path,
    start_date: str = "2010-01-04",
    end_date: str = "2025-12-31",
    chunk_size: int = 250_000,
) -> dict:
    """Build one reusable A-share Qlib store for all supported universes."""
    database, output = Path(db_path), Path(output_dir)
    if not database.exists():
        raise FileNotFoundError(database)
    staging = output.parent / f"{output.name}_staging"
    binary = output.parent / f"{output.name}_binary_staging"
    for temporary in (staging, binary):
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir(parents=True)
    con = _connect(database)
    try:
        stock_basic = con.execute(
            "select ts_code,list_date,market from ts_stock_basic "
            "where ts_code like '%.SH' or ts_code like '%.SZ'"
        ).df()
        listing = {str(r.ts_code): pd.to_datetime(str(r.list_date), errors="coerce") for r in stock_basic.itertuples(index=False)}
        financials = _load_fundamentals(con, start_date, end_date)
        industries = _load_sw_memberships(con)
        st_intervals = _load_st_intervals(con)
        cursor = con.execute(
            "select d.ts_code,d.trade_date,d.open,d.high,d.low,d.close,d.vol as volume,d.amount,"
            "a.adj_factor,b.turnover_rate,b.turnover_rate_f,b.volume_ratio,b.pe,b.pe_ttm,b.pb,b.ps_ttm,"
            "b.total_share,b.float_share,b.free_share,b.total_mv,b.circ_mv "
            "from ts_daily d left join ts_adj_factor a using(ts_code,trade_date) "
            "left join ts_daily_basic b using(ts_code,trade_date) "
            "where d.trade_date between ? and ? and (d.ts_code like '%.SH' or d.ts_code like '%.SZ') "
            "order by d.ts_code,d.trade_date",
            [start_date.replace("-", ""), end_date.replace("-", "")],
        )
        while True:
            chunk = cursor.fetch_df_chunk(max(1, chunk_size // 2048))
            if chunk.empty:
                break
            chunk["date"] = pd.to_datetime(chunk["trade_date"].astype(str), errors="coerce")
            for ts_code, group in chunk.groupby("ts_code", sort=False):
                group = group.copy().sort_values("date")
                adj = pd.to_numeric(group["adj_factor"], errors="coerce").replace(0, np.nan).ffill().fillna(1.0)
                for col in ("open", "high", "low", "close"):
                    group[col] = pd.to_numeric(group[col], errors="coerce") * adj
                group["volume"] = pd.to_numeric(group["volume"], errors="coerce").fillna(0) / adj
                group["factor"] = 1.0
                group["change"] = group["close"].pct_change()
                list_date = listing.get(str(ts_code))
                group["listing_age_days"] = ((group["date"] - list_date).dt.days * 252 / 365) if pd.notna(list_date) else np.nan
                group["is_st"] = _mark_intervals(group["date"], st_intervals.get(str(ts_code))).astype(float)
                fin = financials.get(str(ts_code))
                if fin is not None and not fin.empty:
                    group = pd.merge_asof(group, fin, left_on="date", right_on="available_date", direction="backward")
                    group["fundamental_age_days"] = (group["date"] - group["available_date"]).dt.days
                industry = industries.get(str(ts_code))
                if industry is not None and not industry.empty:
                    group = pd.merge_asof(group, industry, left_on="date", right_on="in_date", direction="backward")
                    valid = group["out_date"].isna() | (group["date"] <= group["out_date"])
                    group.loc[~valid, SW_FIELDS] = np.nan
                group["symbol"] = _qlib_symbol(str(ts_code))
                for field in FINANCIAL_FIELDS + ["fundamental_age_days"] + SW_FIELDS:
                    if field not in group:
                        group[field] = np.nan
                keep = ["date", "symbol", "open", "high", "low", "close", "volume", "factor", "change",
                        "amount", "turnover_rate", "turnover_rate_f", "volume_ratio", "pe", "pe_ttm", "pb", "ps_ttm",
                        "total_share", "float_share", "free_share", "total_mv", "circ_mv", "is_st", "listing_age_days",
                        *FINANCIAL_FIELDS, "fundamental_age_days", *SW_FIELDS]
                path = staging / f"{_qlib_symbol(str(ts_code)).lower()}.csv"
                group[keep].to_csv(path, mode="a", header=not path.exists(), index=False)

        universes, universe_metadata = _build_universes(con, start_date, end_date, stock_basic)
        # Benchmarks are stored as ordinary Qlib instruments but never enter a stock universe.
        for index_code in UNIVERSES.values():
            benchmark = con.execute(
                "select trade_date,open,high,low,close,vol as volume from ts_index_daily "
                "where ts_code=? and trade_date between ? and ? order by trade_date",
                [index_code, start_date.replace("-", ""), end_date.replace("-", "")],
            ).df()
            if benchmark.empty:
                continue
            benchmark["date"] = pd.to_datetime(benchmark["trade_date"].astype(str), errors="coerce")
            benchmark["symbol"] = _qlib_symbol(index_code)
            benchmark["factor"] = 1.0
            benchmark["change"] = pd.to_numeric(benchmark["close"], errors="coerce").pct_change()
            base = ["date", "symbol", "open", "high", "low", "close", "volume", "factor", "change"]
            extra = ["amount", "turnover_rate", "turnover_rate_f", "volume_ratio", "pe", "pe_ttm", "pb", "ps_ttm",
                     "total_share", "float_share", "free_share", "total_mv", "circ_mv", "is_st", "listing_age_days",
                     *FINANCIAL_FIELDS, "fundamental_age_days", *SW_FIELDS]
            for field in extra:
                benchmark[field] = np.nan
            benchmark[base + extra].to_csv(staging / f"{_qlib_symbol(index_code).lower()}.csv", index=False)
    finally:
        con.close()

    include = ["open", "high", "low", "close", "volume", "factor", "change", "amount",
               "turnover_rate", "turnover_rate_f", "volume_ratio", "pe", "pe_ttm", "pb", "ps_ttm",
               "total_share", "float_share", "free_share", "total_mv", "circ_mv", "is_st", "listing_age_days",
               *FINANCIAL_FIELDS, "fundamental_age_days", *SW_FIELDS]
    dump_script = Path(project_root) / "tools" / "qlib-source" / "scripts" / "dump_bin.py"
    subprocess.run([
        sys.executable, str(dump_script), "dump_all", "--data_path", str(staging),
        "--qlib_dir", str(binary), "--freq", "day", "--date_field_name", "date",
        "--file_suffix", ".csv", "--symbol_field_name", "symbol",
        "--include_fields", ",".join(include),
    ], check=True)
    instrument_dir = binary / "instruments"
    instrument_dir.mkdir(parents=True, exist_ok=True)
    for name, intervals in universes.items():
        (instrument_dir / f"{name}.txt").write_text(
            "\n".join(f"{symbol}\t{start}\t{end}" for symbol, start, end in intervals) + "\n",
            encoding="utf-8",
        )
    metadata = {
        "source": str(database), "builtAtUtc": pd.Timestamp.utcnow().isoformat(),
        "startDate": start_date, "endDate": end_date, "region": "cn",
        "universes": universe_metadata, "fields": include,
        "filters": {"stField": "is_st", "newStockAgeField": "listing_age_days", "defaultMinTradingDays": 375},
        "industry": {"primary": "sw_l1", "robustness": "sw_l2", "detail": "sw_l3"},
        "financialTiming": "ann_date backward as-of only",
    }
    (binary / "cn_market_manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    backup = output.parent / f"{output.name}_previous"
    if backup.exists():
        shutil.rmtree(backup)
    if output.exists():
        output.rename(backup)
    binary.rename(output)
    if backup.exists():
        shutil.rmtree(backup)
    shutil.rmtree(staging)
    return metadata
