# How to read files.
For example, if you want to read `filename.h5`
```Python
import pandas as pd
df = pd.read_hdf("filename.h5", key="data")
```
NOTE: **key is always "data" for all hdf5 files **.

# Here is a short description about the data

| Filename       | Description                                                      |
| -------------- | -----------------------------------------------------------------|
| "daily_pv.h5"  | Adjusted daily price and volume data.                            |


# For different data, We have some basic knowledge for them

## Daily data variables
$open: open price of the stock on that day.
$close: close price of the stock on that day.
$high: high price of the stock on that day.
$low: low price of the stock on that day.
$volume: volume of the stock on that day.
$return: daily return of the stock on that day.
## Optional WRDS point-in-time fundamental variables

When DATA_SOURCE=wrds, daily_pv.h5 also contains quarterly Compustat values aligned by
the public release date (rdq; datadate + 90 days fallback) and forward-filled only after
release. Available groups include selected low-missing raw balance-sheet and income-statement
values; growth, profitability and margins; inventory, receivables and net fixed-asset changes;
liability and retained-earnings ratios; report lag and fundamental age; and all four GICS levels. The
authoritative field list is `EXPORTED_FUNDAMENTAL_FIELDS` in `quantaalpha.data.wrds_adapter`.
Security identity is CRSP PERMNO and the universe follows historical S&P 500
MbrStartDt/MbrEndDt intervals. Missing accounting values remain missing rather than being
silently replaced with zero.
