"""Point-in-time IBES analyst fields for the WRDS S&P 500 Qlib store.

Reads the parquet tables pulled from WRDS IBES (``IBES_ROOT``):

* ``recdsum``  monthly recommendation consensus (statpers)
* ``ptgsumu``  monthly price-target consensus, unadjusted (statpers)
* ``surpsumu`` quarterly EPS surprise against the consensus (anndats)
* ``idsum``    IBES ticker -> 8-digit CUSIP history (sdates)

IBES tickers are linked to CRSP PERMNOs through the CUSIP: the IBES CUSIP
history (each CUSIP valid from its ``sdates`` until the ticker's next CUSIP)
is joined to the CRSP historical CUSIP ranges, and a row links only when its
date falls inside both ranges. This is the CUSIP leg of WRDS ``iclink``.

Timing: a consensus is dated on its IBES statistics date and a surprise on the
announcement date, which is often after the close. Every value is therefore
first usable on the next trading session (a strict backward as-of merge), and
is dropped once it is older than the next update could be.

``statsum_epsus`` (consensus EPS forecasts) and ``det_epsus`` are not used:
they are not in the local pull, so EPS forecast revisions cannot be built.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

CRSP_NAMES_REL = Path("CRSP/Stock - Version 2/CRSP Stock Events - Historical Descriptive Information.zip")

REQUIRED_TABLES = ("idsum", "recdsum", "ptgsumu", "surpsumu")
# Tables that would add EPS consensus and revisions if pulled from WRDS.
MISSING_FOR_EPS_REVISIONS = ("statsum_epsus", "det_epsus")

REC_FIELDS = [
    "ibes_rec_mean", "ibes_rec_count", "ibes_rec_net_up", "ibes_rec_buy_pct",
    "ibes_rec_sell_pct", "ibes_rec_dispersion",
]
PTG_FIELDS = ["ibes_ptg_upside", "ibes_ptg_count", "ibes_ptg_net_revision", "ibes_ptg_dispersion"]
SURPRISE_FIELDS = ["ibes_sue", "ibes_eps_surprise", "ibes_surprise_age_days"]
IBES_FIELDS = REC_FIELDS + PTG_FIELDS + SURPRISE_FIELDS

FIELD_DESCRIPTIONS = {
    "ibes_rec_mean": "IBES mean analyst recommendation (1 = strong buy ... 5 = strong sell)",
    "ibes_rec_count": "number of analysts with a recommendation",
    "ibes_rec_net_up": "(upgrades - downgrades) / analysts over the prior month",
    "ibes_rec_buy_pct": "share of analysts rating buy or strong buy",
    "ibes_rec_sell_pct": "share of analysts rating sell or strong sell",
    "ibes_rec_dispersion": "standard deviation of analyst recommendations",
    "ibes_ptg_upside": "mean 12-month analyst price target / price on the consensus date - 1",
    "ibes_ptg_count": "number of analysts with a price target",
    "ibes_ptg_net_revision": "(price targets raised - lowered) / analysts over the prior month",
    "ibes_ptg_dispersion": "standard deviation / mean of analyst price targets",
    "ibes_sue": "latest quarterly EPS surprise in analyst standard deviations (IBES SUE)",
    "ibes_eps_surprise": "latest quarterly EPS minus consensus, divided by the pre-announcement price",
    "ibes_surprise_age_days": "calendar days since that earnings announcement",
}

# A monthly consensus is replaced within about 5 weeks; a quarterly surprise
# within about 4 months. Older values mean coverage stopped.
MONTHLY_MAX_AGE_DAYS = 45
QUARTERLY_MAX_AGE_DAYS = 120


def default_ibes_root(wrds_root: str | Path | None, configured: str | None = None) -> Path | None:
    if configured:
        return Path(configured)
    if wrds_root and (Path(wrds_root) / "IBES").is_dir():
        return Path(wrds_root) / "IBES"
    return None


def inspect_ibes(ibes_root: str | Path | None) -> dict:
    """Report which IBES tables are present and readable."""
    if not ibes_root:
        return {"root": None, "ready": False, "tables": {}, "missing": list(REQUIRED_TABLES)}
    root = Path(ibes_root)
    tables = {}
    for path in sorted(root.glob("*.parquet")):
        if path.name.startswith("."):
            continue
        try:
            import pyarrow.parquet as pq

            rows = pq.ParquetFile(path).metadata.num_rows
            tables[path.stem] = {"rows": rows, "readable": True}
        except Exception as error:  # truncated pulls have no parquet footer
            tables[path.stem] = {"rows": None, "readable": False, "error": str(error)[:120]}
    missing = [name for name in REQUIRED_TABLES if not tables.get(name, {}).get("readable")]
    return {
        "root": str(root),
        "ready": not missing,
        "tables": tables,
        "missing": missing,
        "unreadable": [name for name, info in tables.items() if not info["readable"]],
        "epsRevisionsAvailable": all(tables.get(n, {}).get("readable") for n in MISSING_FOR_EPS_REVISIONS),
        "fields": IBES_FIELDS,
    }


def _crsp_cusip_ranges(wrds_root: Path, permnos: set[int]) -> pd.DataFrame:
    source = wrds_root / CRSP_NAMES_REL
    with zipfile.ZipFile(source) as archive:
        member = next(info for info in archive.infolist() if not info.is_dir())
        with archive.open(member) as stream:
            names = pd.read_csv(
                stream, usecols=["PERMNO", "CUSIP", "SecInfoStartDt", "SecInfoEndDt"],
                dtype={"CUSIP": str}, low_memory=False,
            )
    names = names[pd.to_numeric(names["PERMNO"], errors="coerce").isin(permnos)].dropna(subset=["CUSIP"])
    names["permno"] = names["PERMNO"].astype(int)
    names["cusip"] = names["CUSIP"].str.strip().str.upper().str[:8]
    names["crsp_start"] = pd.to_datetime(names["SecInfoStartDt"], errors="coerce")
    names["crsp_end"] = pd.to_datetime(names["SecInfoEndDt"], errors="coerce")
    return (
        names.groupby(["cusip", "permno"], as_index=False)
        .agg(crsp_start=("crsp_start", "min"), crsp_end=("crsp_end", "max"))
    )


def build_links(idsum: pd.DataFrame, crsp_ranges: pd.DataFrame) -> pd.DataFrame:
    """IBES ticker -> PERMNO with the date window in which the link holds."""
    ids = idsum[["ticker", "cusip", "sdates"]].dropna().copy()
    ids["cusip"] = ids["cusip"].astype(str).str.strip().str.upper().str[:8]
    ids["sdates"] = pd.to_datetime(ids["sdates"], errors="coerce")
    ids = ids.dropna().sort_values(["ticker", "sdates"])
    # Collapse repeated rows of the same CUSIP; a CUSIP holds until the
    # ticker's next different CUSIP appears.
    changed = ids["cusip"].ne(ids.groupby("ticker")["cusip"].shift())
    spells = ids[changed].copy()
    spells["ibes_end"] = spells.groupby("ticker")["sdates"].shift(-1) - pd.Timedelta(days=1)
    spells["ibes_end"] = spells["ibes_end"].fillna(pd.Timestamp("2262-01-01"))
    links = spells.merge(crsp_ranges, on="cusip", how="inner")
    # A ticker's first CUSIP is valid from listing, not only from the first
    # IBES snapshot, so only the CRSP range bounds the start of a first spell.
    first = links.groupby("ticker")["sdates"].transform("min") == links["sdates"]
    start = links["sdates"].where(~first, links["crsp_start"])
    links["start"] = np.maximum(start.values, links["crsp_start"].values)
    links["end"] = np.minimum(links["ibes_end"].values, links["crsp_end"].values)
    links = links[links["start"] <= links["end"]]
    return links[["ticker", "permno", "cusip", "start", "end"]].reset_index(drop=True)


def link_rows(frame: pd.DataFrame, links: pd.DataFrame, date_column: str) -> pd.DataFrame:
    """Attach a PERMNO to each IBES row whose date is inside a link window."""
    merged = frame.merge(links[["ticker", "permno", "start", "end"]], on="ticker", how="inner")
    merged = merged[(merged[date_column] >= merged["start"]) & (merged[date_column] <= merged["end"])]
    merged = merged.sort_values(["permno", date_column, "ticker"])
    # Two IBES tickers on one PERMNO and date: keep one, deterministically.
    merged = merged.drop_duplicates(["permno", date_column], keep="first")
    return merged.drop(columns=["start", "end"])


def _ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = pd.to_numeric(denominator, errors="coerce")
    return pd.to_numeric(numerator, errors="coerce") / denominator.where(denominator > 0)


def load_ibes(ibes_root: str | Path, wrds_root: str | Path, permnos: set[int],
              start_date: str, end_date: str) -> tuple[dict[int, dict[str, pd.DataFrame]], dict]:
    """Return per-PERMNO event tables and a summary for the build manifest."""
    import duckdb

    root = Path(ibes_root)
    crsp_ranges = _crsp_cusip_ranges(Path(wrds_root), permnos)
    con = duckdb.connect()
    idsum = con.execute(f"select ticker, cusip, sdates from read_parquet('{root / 'idsum.parquet'}')").df()
    links = build_links(idsum, crsp_ranges)
    tickers = pd.DataFrame({"ticker": links["ticker"].unique()})
    con.register("linked_tickers", tickers)
    lo, hi = pd.Timestamp(start_date) - pd.Timedelta(days=150), pd.Timestamp(end_date)

    rec = con.execute(f"""
        select r.ticker, cast(r.statpers as date) as event_date, r.meanrec, r.numrec, r.numup, r.numdown,
               r.buypct, r.sellpct, r.stdev
        from read_parquet('{root / 'recdsum.parquet'}') r join linked_tickers t using (ticker)
        where r.statpers between ? and ?""", [lo, hi]).df()
    ptg = con.execute(f"""
        select p.ticker, cast(p.statpers as date) as event_date, p.meanptg, p.numest,
               p.numup1m, p.numdown1m, p.stdev
        from read_parquet('{root / 'ptgsumu.parquet'}') p join linked_tickers t using (ticker)
        where p.measure = 'PTG' and p.curr = 'USD' and p.statpers between ? and ?""", [lo, hi]).df()
    surprise = con.execute(f"""
        select s.ticker, cast(s.anndats as date) as event_date, s.actual, s.surpmean, s.suescore
        from read_parquet('{root / 'surpsumu.parquet'}') s join linked_tickers t using (ticker)
        where s.measure = 'EPS' and s.fiscalp = 'QTR' and s.anndats between ? and ?""", [lo, hi]).df()

    tables: dict[int, dict[str, pd.DataFrame]] = {}
    counts = {}
    for name, frame in (("rec", rec), ("ptg", ptg), ("surprise", surprise)):
        frame["event_date"] = pd.to_datetime(frame["event_date"]).astype("datetime64[ns]")
        linked = link_rows(frame, links, "event_date")
        if name == "rec":
            linked["ibes_rec_mean"] = linked["meanrec"]
            linked["ibes_rec_count"] = linked["numrec"]
            linked["ibes_rec_net_up"] = _ratio(linked["numup"].fillna(0) - linked["numdown"].fillna(0), linked["numrec"])
            linked["ibes_rec_buy_pct"] = linked["buypct"] / 100.0
            linked["ibes_rec_sell_pct"] = linked["sellpct"] / 100.0
            linked["ibes_rec_dispersion"] = linked["stdev"]
            keep = REC_FIELDS
        elif name == "ptg":
            linked["ibes_ptg_count"] = linked["numest"]
            linked["ibes_ptg_net_revision"] = _ratio(
                linked["numup1m"].fillna(0) - linked["numdown1m"].fillna(0), linked["numest"])
            linked["ibes_ptg_dispersion"] = _ratio(linked["stdev"], linked["meanptg"])
            keep = ["meanptg", "ibes_ptg_count", "ibes_ptg_net_revision", "ibes_ptg_dispersion"]
        else:
            linked["ibes_sue"] = linked["suescore"]
            linked["eps_gap"] = linked["actual"] - linked["surpmean"]
            keep = ["ibes_sue", "eps_gap"]
        counts[name] = {"rows": int(len(linked)), "permnos": int(linked["permno"].nunique())}
        for permno, group in linked.groupby("permno", sort=False):
            tables.setdefault(int(permno), {})[name] = (
                group[["event_date", *keep]].sort_values("event_date").reset_index(drop=True)
            )
    summary = {
        "root": str(root),
        "linked_tickers": int(links["ticker"].nunique()),
        "linked_permnos": int(links["permno"].nunique()),
        "requested_permnos": len(permnos),
        "rows": counts,
        "timing": "statpers / anndats; usable from the next session; monthly values dropped after "
                  f"{MONTHLY_MAX_AGE_DAYS} days, surprises after {QUARTERLY_MAX_AGE_DAYS} days",
        "link": "IBES idsum CUSIP spells x CRSP historical CUSIP ranges",
        "fields": IBES_FIELDS,
    }
    return tables, summary


def _asof(daily: pd.DataFrame, events: pd.DataFrame, max_age_days: int) -> pd.DataFrame:
    """Values known strictly before each session, dropped once stale."""
    merged = pd.merge_asof(
        daily[["date"]], events.sort_values("event_date"),
        left_on="date", right_on="event_date", direction="backward", allow_exact_matches=False,
    )
    age = (merged["date"] - merged["event_date"]).dt.days
    stale = age > max_age_days
    values = merged.drop(columns=["date"])
    values.loc[stale, :] = np.nan
    values["age_days"] = age.where(~stale)
    return values


def attach_ibes(daily: pd.DataFrame, tables: dict[str, pd.DataFrame] | None) -> pd.DataFrame:
    """Add IBES_FIELDS to one PERMNO's daily frame (needs ``date`` and ``raw_close``).

    Prices used for scaling are unadjusted, like the IBES unadjusted values.
    """
    out = daily.sort_values("date").reset_index(drop=True)
    # DuckDB yields microsecond timestamps and CSVs nanosecond ones;
    # merge_asof refuses to mix them.
    out["date"] = out["date"].astype("datetime64[ns]")
    tables = {
        name: frame.assign(event_date=frame["event_date"].astype("datetime64[ns]"))
        for name, frame in (tables or {}).items()
    }
    prices = out[["date", "raw_close"]].dropna().sort_values("date")

    rec = tables.get("rec")
    if rec is not None and not rec.empty:
        values = _asof(out, rec, MONTHLY_MAX_AGE_DAYS)
        for field in REC_FIELDS:
            out[field] = values[field].to_numpy()

    ptg = tables.get("ptg")
    if ptg is not None and not ptg.empty:
        # Upside uses the price on the consensus date itself.
        priced = pd.merge_asof(ptg.sort_values("event_date"), prices, left_on="event_date",
                               right_on="date", direction="backward").drop(columns=["date"])
        priced["ibes_ptg_upside"] = _ratio(priced["meanptg"], priced["raw_close"]) - 1.0
        values = _asof(out, priced, MONTHLY_MAX_AGE_DAYS)
        for field in PTG_FIELDS:
            out[field] = values[field].to_numpy()

    surprise = tables.get("surprise")
    if surprise is not None and not surprise.empty:
        # Scale by the last close before the announcement.
        priced = pd.merge_asof(surprise.sort_values("event_date"), prices, left_on="event_date",
                               right_on="date", direction="backward",
                               allow_exact_matches=False).drop(columns=["date"])
        priced["ibes_eps_surprise"] = _ratio(priced["eps_gap"], priced["raw_close"])
        values = _asof(out, priced, QUARTERLY_MAX_AGE_DAYS)
        out["ibes_sue"] = values["ibes_sue"].to_numpy()
        out["ibes_eps_surprise"] = values["ibes_eps_surprise"].to_numpy()
        out["ibes_surprise_age_days"] = values["age_days"].to_numpy()

    for field in IBES_FIELDS:
        if field not in out.columns:
            out[field] = np.nan
    return out
