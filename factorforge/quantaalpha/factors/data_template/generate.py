"""Generate price/volume files for the configured market."""
import os
import qlib
from qlib.config import REG_CN, REG_US
from qlib.data import D
from quantaalpha.data.wrds_adapter import EXPORTED_FUNDAMENTAL_FIELDS


def env_value(name, default=None):
    """Read values passed by either python-dotenv or the frontend parser."""
    value = os.environ.get(name, default)
    if isinstance(value, str):
        return value.strip().strip("'\"")
    return value


provider = env_value("QLIB_DATA_DIR", env_value("QLIB_PROVIDER_URI", "~/.qlib/qlib_data/cn_data"))
region_name = env_value("QLIB_REGION", "cn").lower()
region = REG_US if region_name == "us" else REG_CN
qlib.init(provider_uri=provider, region=region)
market = env_value("QLIB_MARKET", "sp500" if region_name == "us" else "all")
fields = ["$open", "$close", "$high", "$low", "$volume", "$factor", "$close/Ref($close, 1)-1"]
column_names = ["$open", "$close", "$high", "$low", "$volume", "$factor", "$return"]
source = env_value("DATA_SOURCE", "qlib").lower()
if source == "wrds":
    fundamental_fields = [f"${name}" for name in EXPORTED_FUNDAMENTAL_FIELDS]
    fields.extend(fundamental_fields)
    column_names.extend(fundamental_fields)
elif source == "cn_duckdb":
    from quantaalpha.data.cn_duckdb_adapter import FINANCIAL_FIELDS, SW_FIELDS
    china_fields = [
        "$amount", "$turnover_rate", "$turnover_rate_f", "$volume_ratio",
        "$pe", "$pe_ttm", "$pb", "$ps_ttm", "$total_mv", "$circ_mv",
        "$is_st", "$listing_age_days", "$fundamental_age_days",
        *[f"${name}" for name in FINANCIAL_FIELDS],
        *[f"${name}" for name in SW_FIELDS],
    ]
    fields.extend(china_fields)
    column_names.extend(china_fields)
elif source == "binance_futures":
    from quantaalpha.data.binance_futures_adapter import EXPORTED_FIELDS
    crypto_fields = [
        f"${name}" for name in EXPORTED_FIELDS
        if name not in {"open", "close", "high", "low", "volume", "factor", "return"}
    ]
    fields.extend(crypto_fields)
    column_names.extend(crypto_fields)
data = D.features(
    D.instruments(market),
    fields,
    start_time=env_value("QLIB_DATA_START", "2015-01-01"),
    end_time=env_value("QLIB_DATA_END") or None,
)
data.columns = column_names
data = data.reorder_levels(["datetime", "instrument"]).sort_index()
data.to_hdf("daily_pv_all.h5", key="data", mode="w")
names = sorted(data.index.get_level_values("instrument").unique())[:30]
data.loc[data.index.get_level_values("instrument").isin(names)].to_hdf("daily_pv_debug.h5", key="data", mode="w")
