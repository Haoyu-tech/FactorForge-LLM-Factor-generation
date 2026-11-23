"""JKP/Kelly 153 S&P 500 panel build and path resolution."""
import json

import numpy as np
import pandas as pd
import pytest

from quantaalpha.data import kelly_adapter as K


def _source(tmp_path):
    factors = ["prc"] + [f"f{i:03d}" for i in range(K.EXPECTED_FACTOR_COUNT - 1)]
    rows = [
        # permno, eom
        (1.0, "1986-12-31"),   # member, but before the start month
        (1.0, "2000-06-30"),   # member, kept
        (1.0, "2001-06-30"),   # after membership ended
        (2.0, "2000-06-30"),   # never a member
        (np.nan, "2000-06-30"),  # non-US row without a PERMNO
    ]
    frame = pd.DataFrame(rows, columns=["permno", "eom"])
    frame["eom"] = pd.to_datetime(frame["eom"]).dt.date
    frame["excntry"] = "USA"
    frame["ret_exc_lead1m"] = 0.01
    frame["ret_exc"] = 0.02
    frame["me"] = 100.0
    values = pd.DataFrame({name: float(i) for i, name in enumerate(factors)}, index=frame.index)
    frame = pd.concat([frame, values], axis=1)
    path = tmp_path / "kelly_factor_153.parquet"
    frame.to_parquet(path, index=False)
    membership = tmp_path / "sp500.txt"
    membership.write_text("P1\t1980-01-01\t2000-12-31\n", encoding="utf-8")
    return path, membership


def test_build_filters_membership_and_start_month(tmp_path):
    source, membership = _source(tmp_path)
    out = tmp_path / "cache" / "panel.parquet"
    report_json = tmp_path / "report" / "r.json"
    summary = K.build_sp500_panel(
        source, membership, out, tmp_path / "report" / "r.csv", report_json,
        start_month="1987-01-01",
    )
    panel = pd.read_parquet(out)
    assert panel["permno"].tolist() == [1]
    assert pd.Timestamp(panel["eom"].iloc[0]) == pd.Timestamp("2000-06-30")
    assert summary["start_month"] == "2000-06-30"
    assert summary["sp500_member_months"] == 1
    assert json.loads(report_json.read_text())["summary"]["factor_count"] == 153


def test_build_without_start_month_keeps_full_history(tmp_path):
    source, membership = _source(tmp_path)
    out = tmp_path / "panel.parquet"
    K.build_sp500_panel(source, membership, out, tmp_path / "r.csv", tmp_path / "r.json")
    assert len(pd.read_parquet(out)) == 2


def test_resolve_paths_defaults(tmp_path):
    paths = K.resolve_kelly_paths({"WRDS_ROOT": str(tmp_path)}, project_root=tmp_path / "proj")
    assert paths["panel"] == tmp_path / "_quantaalpha_cache" / "kelly_153_sp500.parquet"
    assert paths["report_json"] == tmp_path / "proj" / "data" / "kelly" / "jkp_sp500_missingness_1987.json"
    assert paths["membership"] == tmp_path / "proj" / "data" / "qlib" / "wrds_sp500" / "instruments" / "sp500.txt"


def test_resolve_paths_finds_unzipped_source_and_honours_overrides(tmp_path):
    (tmp_path / "kelley_factors").mkdir()
    source = tmp_path / "kelley_factors" / "kelly_factor_153.parquet"
    source.write_bytes(b"")
    paths = K.resolve_kelly_paths(
        {
            "WRDS_ROOT": str(tmp_path),
            "KELLY_PANEL_PATH": str(tmp_path / "local" / "p.parquet"),
            "WRDS_QLIB_DATA_DIR": str(tmp_path / "qlib"),
        },
        project_root=tmp_path,
    )
    assert paths["source"] == source
    assert paths["panel"] == tmp_path / "local" / "p.parquet"
    assert paths["membership"] == tmp_path / "qlib" / "instruments" / "sp500.txt"

    explicit = K.resolve_kelly_paths(
        {"WRDS_ROOT": str(tmp_path), "KELLY_SOURCE_PATH": str(tmp_path / "x.parquet")},
        project_root=tmp_path,
    )
    assert explicit["source"] == tmp_path / "x.parquet"
