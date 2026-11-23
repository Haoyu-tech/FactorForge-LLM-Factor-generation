"""Where to get data that the local Qlib stores do not hold.

Every entry names a kind of data a research direction may need, which stored
fields would satisfy it, and where it can be obtained. The direction check
attaches these entries to the data it reports as missing, so the sources shown
to the user come from this file and never from the LLM.

Every URL was opened and every DOI was matched to its title on Crossref on
2026-11-21. Bai, Bali and Wen (2019, JFE) is deliberately absent: it was
retracted. When adding an entry, check the link and the DOI the same way.
"""
from __future__ import annotations

ALL_MARKETS = ("us", "cn", "crypto")


def _paper(citation: str, doi: str, markets: tuple[str, ...] = ()) -> dict:
    paper = {"citation": citation, "url": f"https://doi.org/{doi}"}
    if markets:
        paper["markets"] = markets
    return paper


WRDS = "https://wrds-www.wharton.upenn.edu/pages/about/data-vendors"
TUSHARE = {
    "name": "Tushare Pro data API",
    "url": "https://tushare.pro/document/2",
    "kind": "api",
    "access": "Free tier plus points-based access; China A shares",
    "markets": ("cn",),
}
AKSHARE = {
    "name": "AKShare (open-source China market data library)",
    "url": "https://github.com/akfamily/akshare",
    "kind": "github",
    "access": "Free; scrapes public sites, history depth varies by table",
    "markets": ("cn",),
}
BINANCE_ARCHIVE = {
    "name": "Binance public data archive (data.binance.vision)",
    "url": "https://data.binance.vision/",
    "kind": "dataset",
    "access": "Free; daily and monthly files for spot and USD-M futures",
    "markets": ("crypto",),
}
BINANCE_ARCHIVE_GITHUB = {
    "name": "binance/binance-public-data (download scripts and file layout)",
    "url": "https://github.com/binance/binance-public-data",
    "kind": "github",
    "access": "Free",
    "markets": ("crypto",),
}


DATA_CATEGORIES: list[dict] = [
    {
        "id": "market_equity",
        "label": "Market capitalization and valuation ratios (size, book-to-market, earnings yield)",
        "label_zh": "市值与估值比率（规模、账面市值比、盈利收益率）",
        "markets": ALL_MARKETS,
        "satisfied_by": ("total_mv", "circ_mv", "market_cap", "shrout", "me", "pb", "pe"),
        "keywords": (
            "market cap", "market capitalization", "market value", "size effect", "size factor",
            "small cap", "small-cap", "firm size", "book-to-market", "book to market", "price-to-book",
            "price to book", "earnings yield", "value premium", "value factor", "valuation",
            "市值", "市净率", "市盈率", "估值", "小市值", "规模因子",
        ),
        "sources": [
            {"name": "CRSP daily stock file on WRDS (SHROUT x PRC gives market equity)",
             "url": f"{WRDS}/center-for-research-in-security-prices-crsp/",
             "kind": "dataset", "access": "WRDS subscription; rebuild the local WRDS store with SHROUT",
             "markets": ("us",)},
            {"name": "Kenneth French data library (size and value portfolios, breakpoints)",
             "url": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html",
             "kind": "dataset", "access": "Free", "markets": ("us",)},
            {"name": "CoinGecko API (circulating supply and market cap per coin)",
             "url": "https://docs.coingecko.com/",
             "kind": "api", "access": "Free tier with rate limits", "markets": ("crypto",)},
            {"name": "Coin Metrics community data (supply and market cap history)",
             "url": "https://github.com/coinmetrics/data",
             "kind": "github", "access": "Free community data", "markets": ("crypto",)},
            TUSHARE,
        ],
        "papers": [
            _paper("Banz (1981), The relationship between return and market value of common stocks, JFE",
                   "10.1016/0304-405X(81)90018-0", ("us", "cn")),
            _paper("Fama and French (1992), The cross-section of expected stock returns, JF",
                   "10.1111/j.1540-6261.1992.tb04398.x", ("us", "cn")),
            _paper("Liu, Stambaugh and Yuan (2019), Size and value in China, JFE",
                   "10.1016/j.jfineco.2019.03.008", ("cn",)),
            _paper("Liu, Tsyvinski and Wu (2022), Common risk factors in cryptocurrency, JF",
                   "10.1111/jofi.13119", ("crypto",)),
        ],
    },
    {
        "id": "analyst_forecasts",
        "label": "Analyst recommendations, price targets and earnings surprises against consensus",
        "label_zh": "分析师评级、目标价与相对一致预期的盈利意外",
        "markets": ("us", "cn"),
        "satisfied_by": ("ibes_rec_mean", "ibes_ptg_upside", "ibes_sue", "rec_mean", "target_price"),
        "keywords": (
            "analyst", "consensus", "recommendation", "upgrade", "downgrade", "target price", "price target",
            "earnings surprise", "sue", "ibes", "i/b/e/s",
            "分析师", "一致预期", "评级", "目标价", "研报", "盈利意外",
        ),
        "sources": [
            {"name": "LSEG I/B/E/S on WRDS (estimates, revisions, recommendations)",
             "url": f"{WRDS}/lseg/", "kind": "dataset", "access": "WRDS subscription", "markets": ("us",)},
            {"name": "Tushare Pro report_rc (sell-side earnings forecasts)",
             "url": "https://tushare.pro/document/2", "kind": "api",
             "access": "Points-based access; China A shares", "markets": ("cn",)},
        ],
        "papers": [
            _paper("Chan, Jegadeesh and Lakonishok (1996), Momentum strategies, JF",
                   "10.1111/j.1540-6261.1996.tb05222.x"),
            _paper("Womack (1996), Do brokerage analysts' recommendations have investment value?, JF",
                   "10.1111/j.1540-6261.1996.tb05205.x"),
            _paper("Barber, Lehavy, McNichols and Trueman (2001), Can investors profit from the prophets?, JF",
                   "10.1111/0022-1082.00336"),
        ],
    },
    {
        "id": "analyst_eps_revisions",
        "label": "Consensus EPS forecasts and their revisions",
        "label_zh": "一致预期 EPS 及其调整",
        "markets": ("us", "cn"),
        "satisfied_by": ("ibes_eps_fy1", "ibes_eps_revision", "eps_forecast", "eps_revision"),
        "keywords": (
            "eps forecast", "earnings forecast", "forecast revision", "estimate revision", "earnings revision",
            "eps revision", "consensus eps", "forecast dispersion", "fy1", "long-term growth forecast",
            "盈利预测", "预测调整", "盈利预测调整", "一致预期调整", "预期上调", "预期下调",
        ),
        "sources": [
            {"name": "IBES statsum_epsus (summary EPS consensus) and det_epsus (analyst-level estimates) on WRDS; "
                     "the local IBES pull stopped before these tables",
             "url": f"{WRDS}/lseg/", "kind": "dataset", "access": "WRDS subscription", "markets": ("us",)},
            {"name": "Tushare Pro report_rc (sell-side earnings forecasts)",
             "url": "https://tushare.pro/document/2", "kind": "api",
             "access": "Points-based access; China A shares", "markets": ("cn",)},
        ],
        "papers": [
            _paper("Chan, Jegadeesh and Lakonishok (1996), Momentum strategies, JF",
                   "10.1111/j.1540-6261.1996.tb05222.x"),
        ],
    },
    {
        "id": "options",
        "label": "Options data (implied volatility, skew, put-call parity, option volume)",
        "label_zh": "期权数据（隐含波动率、偏度、平价偏离、期权成交量）",
        "markets": ALL_MARKETS,
        "satisfied_by": ("implied_vol", "iv", "iv_skew", "put_call_ratio", "option_volume"),
        "keywords": (
            "option", "options", "implied volatility", "implied vol", "volatility smirk", "volatility skew",
            "put-call", "put call", "iv spread", "variance risk premium", "deribit",
            "期权", "隐含波动率", "波动率偏度", "认沽", "认购",
        ),
        "sources": [
            {"name": "OptionMetrics IvyDB US on WRDS", "url": f"{WRDS}/optionmetrics/",
             "kind": "dataset", "access": "WRDS subscription", "markets": ("us",)},
            {"name": "Cboe DataShop (option quotes, open-close volume)", "url": "https://datashop.cboe.com/",
             "kind": "dataset", "access": "Paid", "markets": ("us",)},
            {"name": "Tardis.dev (historical Deribit and exchange option data)", "url": "https://tardis.dev/",
             "kind": "dataset", "access": "Paid; free first-day-of-month samples", "markets": ("crypto",)},
            {"name": "Deribit API (live option chain and implied volatility)", "url": "https://docs.deribit.com/",
             "kind": "api", "access": "Free", "markets": ("crypto",)},
            AKSHARE,
        ],
        "papers": [
            _paper("Cremers and Weinbaum (2010), Deviations from put-call parity and stock return predictability, JFQA",
                   "10.1017/S002210901000013X"),
            _paper("Xing, Zhang and Zhao (2010), What does the individual option volatility smirk tell us about future equity returns?, JFQA",
                   "10.1017/S0022109010000220"),
            _paper("An, Ang, Bali and Cakici (2014), The joint cross section of stocks and options, JF",
                   "10.1111/jofi.12181"),
        ],
    },
    {
        "id": "short_interest",
        "label": "Short interest, short selling and margin trading",
        "label_zh": "做空、卖空余额与融资融券",
        "markets": ("us", "cn"),
        "satisfied_by": ("short_interest", "shortint", "days_to_cover", "rzye", "rqye", "margin_balance"),
        "keywords": (
            "short interest", "short selling", "short sale", "short-selling", "days to cover",
            "securities lending", "borrow fee", "margin trading", "margin balance",
            "融资融券", "融券", "融资余额", "卖空", "做空",
        ),
        "sources": [
            {"name": "FINRA equity short interest", "url": "https://www.finra.org/finra-data/browse-catalog/equity-short-interest",
             "kind": "dataset", "access": "Free", "markets": ("us",)},
            {"name": "Compustat Supplemental Short Interest on WRDS (S&P Global Market Intelligence)",
             "url": f"{WRDS}/sp-global-market-intelligence/", "kind": "dataset",
             "access": "WRDS subscription", "markets": ("us",)},
            {"name": "Tushare Pro margin_detail (per-stock margin and securities lending balances)",
             "url": "https://tushare.pro/document/2", "kind": "api", "access": "Points-based access",
             "markets": ("cn",)},
        ],
        "papers": [
            _paper("Asquith, Pathak and Ritter (2005), Short interest, institutional ownership, and stock returns, JFE",
                   "10.1016/j.jfineco.2005.01.001"),
            _paper("Boehmer, Jones and Zhang (2008), Which shorts are informed?, JF",
                   "10.1111/j.1540-6261.2008.01324.x"),
            _paper("Rapach, Ringgenberg and Zhou (2016), Short interest and aggregate stock returns, JFE",
                   "10.1016/j.jfineco.2016.03.004"),
        ],
    },
    {
        "id": "institutional_holdings",
        "label": "Institutional and foreign holdings (13F, northbound flows)",
        "label_zh": "机构与外资持股（13F、北向资金）",
        "markets": ("us", "cn"),
        "satisfied_by": ("inst_own", "io_ratio", "hk_hold", "northbound_ratio"),
        "keywords": (
            "institutional ownership", "institutional holding", "13f", "fund holding", "herding",
            "northbound", "foreign ownership", "北向", "沪深港通", "陆股通", "机构持股", "基金持仓", "外资持股",
        ),
        "sources": [
            {"name": "SEC Form 13F data sets", "url": "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets",
             "kind": "dataset", "access": "Free", "markets": ("us",)},
            {"name": "LSEG (Thomson) 13F institutional holdings on WRDS", "url": f"{WRDS}/lseg/",
             "kind": "dataset", "access": "WRDS subscription", "markets": ("us",)},
            {"name": "Tushare Pro hk_hold (northbound holdings per stock)", "url": "https://tushare.pro/document/2",
             "kind": "api", "access": "Points-based access", "markets": ("cn",)},
        ],
        "papers": [
            _paper("Gompers and Metrick (2001), Institutional investors and equity prices, QJE",
                   "10.1162/003355301556392"),
            _paper("Nofsinger and Sias (1999), Herding and feedback trading by institutional and individual investors, JF",
                   "10.1111/0022-1082.00188"),
        ],
    },
    {
        "id": "insider_trading",
        "label": "Insider trades (Form 4) and major-shareholder transactions",
        "label_zh": "内部人交易与大股东增减持",
        "markets": ("us", "cn"),
        "satisfied_by": ("insider_net_buy", "insider_trades"),
        "keywords": ("insider", "form 4", "director dealing", "增减持", "高管增持", "高管减持", "大股东减持", "内部人"),
        "sources": [
            {"name": "SEC insider transactions data sets (Forms 3, 4, 5)",
             "url": "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets",
             "kind": "dataset", "access": "Free", "markets": ("us",)},
            {"name": "LSEG insider filings on WRDS", "url": f"{WRDS}/lseg/", "kind": "dataset",
             "access": "WRDS subscription", "markets": ("us",)},
            {"name": "Tushare Pro stk_holdertrade (shareholder increases and decreases)",
             "url": "https://tushare.pro/document/2", "kind": "api", "access": "Points-based access",
             "markets": ("cn",)},
        ],
        "papers": [
            _paper("Lakonishok and Lee (2001), Are insider trades informative?, RFS", "10.1093/rfs/14.1.79"),
            _paper("Cohen, Malloy and Pomorski (2012), Decoding inside information, JF",
                   "10.1111/j.1540-6261.2012.01740.x"),
        ],
    },
    {
        "id": "text_news",
        "label": "Text: news, filings, earnings-call transcripts and their sentiment",
        "label_zh": "文本：新闻、公告、业绩会文字稿及情绪",
        "markets": ALL_MARKETS,
        "satisfied_by": ("news_sentiment", "news_count", "text_tone"),
        "keywords": (
            "news", "sentiment", "media", "10-k", "10k", "filing text", "textual", "text-based",
            "earnings call", "conference call", "transcript", "tone", "nlp", "llm embedding",
            "新闻", "舆情", "情绪", "公告文本", "文本", "年报文本", "业绩说明会",
        ),
        "sources": [
            {"name": "SEC EDGAR full-text search and filings", "url": "https://www.sec.gov/edgar/search/",
             "kind": "website", "access": "Free", "markets": ("us",)},
            {"name": "Loughran-McDonald master dictionary and 10-K files (Notre Dame SRAF)",
             "url": "https://sraf.nd.edu/", "kind": "dataset", "access": "Free", "markets": ("us",)},
            {"name": "RavenPack news analytics on WRDS", "url": f"{WRDS}/ravenpack/", "kind": "dataset",
             "access": "WRDS subscription", "markets": ("us", "cn")},
            {"name": "GDELT global news event database", "url": "https://www.gdeltproject.org/",
             "kind": "dataset", "access": "Free", "markets": ALL_MARKETS},
            {"name": "Santiment (crypto social and news sentiment)", "url": "https://santiment.net/",
             "kind": "api", "access": "Free tier; paid history", "markets": ("crypto",)},
            AKSHARE,
        ],
        "papers": [
            _paper("Tetlock (2007), Giving content to investor sentiment: The role of media in the stock market, JF",
                   "10.1111/j.1540-6261.2007.01232.x"),
            _paper("Loughran and McDonald (2011), When is a liability not a liability? Textual analysis, dictionaries, and 10-Ks, JF",
                   "10.1111/j.1540-6261.2010.01625.x"),
            _paper("Mayew and Venkatachalam (2012), The power of voice: Managerial affective states and future firm performance, JF",
                   "10.1111/j.1540-6261.2011.01705.x"),
            {"citation": "Ke, Kelly and Xiu (2019), Predicting returns with text data, NBER working paper 26186",
             "url": "https://www.nber.org/papers/w26186"},
        ],
    },
    {
        "id": "attention_social",
        "label": "Investor attention and social media (search volume, page views, posts)",
        "label_zh": "投资者关注度与社交媒体（搜索量、浏览量、帖子）",
        "markets": ALL_MARKETS,
        "satisfied_by": ("search_volume", "page_views", "social_volume"),
        "keywords": (
            "attention", "google search", "search volume", "google trends", "wikipedia", "page view",
            "social media", "twitter", "reddit", "stocktwits", "retail investor attention",
            "关注度", "搜索指数", "百度指数", "股吧", "社交媒体", "散户关注",
        ),
        "sources": [
            {"name": "Google Trends", "url": "https://trends.google.com/", "kind": "website",
             "access": "Free; weekly or daily relative search volume", "markets": ALL_MARKETS},
            {"name": "Wikimedia page-view analytics API",
             "url": "https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/",
             "kind": "api", "access": "Free", "markets": ALL_MARKETS},
            {"name": "LunarCrush (crypto social activity)", "url": "https://lunarcrush.com/",
             "kind": "api", "access": "Paid API", "markets": ("crypto",)},
            {"name": "Santiment (crypto social volume)", "url": "https://santiment.net/",
             "kind": "api", "access": "Free tier; paid history", "markets": ("crypto",)},
            AKSHARE,
        ],
        "papers": [
            _paper("Da, Engelberg and Gao (2011), In search of attention, JF", "10.1111/j.1540-6261.2011.01679.x"),
            _paper("Chen, De, Hu and Hwang (2014), Wisdom of crowds: The value of stock opinions transmitted through social media, RFS",
                   "10.1093/rfs/hhu001"),
        ],
    },
    {
        "id": "intraday",
        "label": "Intraday and order-book data (minute bars, trades, quotes, depth)",
        "label_zh": "日内与盘口数据（分钟线、逐笔成交、报价、深度）",
        "markets": ALL_MARKETS,
        "satisfied_by": ("minute_close", "intraday_return", "bid", "ask", "spread", "depth"),
        "keywords": (
            "intraday", "minute", "high-frequency", "high frequency", "tick", "order book", "limit order",
            "bid-ask", "bid ask", "quoted spread", "market depth", "first half hour", "last half hour",
            "日内", "分钟", "高频", "逐笔", "盘口", "挂单", "买卖价差", "集合竞价",
        ),
        "sources": [
            {"name": "NYSE Trade and Quote (TAQ) on WRDS", "url": f"{WRDS}/nyse-trade-and-quote-taq/",
             "kind": "dataset", "access": "WRDS subscription", "markets": ("us",)},
            {"name": "LOBSTER (Nasdaq limit order book reconstruction)", "url": "https://lobsterdata.com/",
             "kind": "dataset", "access": "Paid; academic pricing", "markets": ("us",)},
            BINANCE_ARCHIVE, BINANCE_ARCHIVE_GITHUB,
            {"name": "Tardis.dev (tick-level order books and trades)", "url": "https://tardis.dev/",
             "kind": "dataset", "access": "Paid; free monthly samples", "markets": ("crypto",)},
            AKSHARE,
        ],
        "papers": [
            _paper("Chordia and Subrahmanyam (2004), Order imbalance and individual stock returns: Theory and evidence, JFE",
                   "10.1016/S0304-405X(03)00175-2"),
            _paper("Easley, Lopez de Prado and O'Hara (2012), Flow toxicity and liquidity in a high-frequency world, RFS",
                   "10.1093/rfs/hhs053"),
            _paper("Gao, Han, Li and Zhou (2018), Market intraday momentum, JFE", "10.1016/j.jfineco.2018.05.009"),
        ],
    },
    {
        "id": "crypto_onchain",
        "label": "On-chain data (active addresses, transfers, exchange flows, holder concentration)",
        "label_zh": "链上数据（活跃地址、转账、交易所净流入、持币集中度）",
        "markets": ("crypto",),
        "satisfied_by": ("active_addresses", "tx_count", "exchange_netflow", "nvt"),
        "keywords": (
            "on-chain", "onchain", "active address", "wallet", "whale", "exchange inflow", "exchange outflow",
            "netflow", "nvt", "mvrv", "hash rate", "tvl", "stablecoin supply", "token unlock",
            "链上", "活跃地址", "巨鲸", "交易所流入", "交易所流出", "解锁",
        ),
        "sources": [
            {"name": "Coin Metrics community data", "url": "https://github.com/coinmetrics/data",
             "kind": "github", "access": "Free community metrics", "markets": ("crypto",)},
            {"name": "Glassnode", "url": "https://glassnode.com/", "kind": "api",
             "access": "Free tier; paid API", "markets": ("crypto",)},
            {"name": "CryptoQuant (exchange flows)", "url": "https://www.cryptoquant.com/", "kind": "api",
             "access": "Free tier; paid API", "markets": ("crypto",)},
            {"name": "Dune (SQL over decoded chain data)", "url": "https://dune.com/", "kind": "website",
             "access": "Free tier", "markets": ("crypto",)},
        ],
        "papers": [
            _paper("Cong, Li and Wang (2021), Tokenomics: Dynamic adoption and valuation, RFS", "10.1093/rfs/hhaa089"),
            _paper("Liu and Tsyvinski (2021), Risks and returns of cryptocurrency, RFS", "10.1093/rfs/hhaa113"),
        ],
    },
    {
        "id": "crypto_positioning",
        "label": "Futures positioning (open interest, long/short ratios, liquidations, basis)",
        "label_zh": "合约持仓（持仓量、多空比、爆仓、基差）",
        "markets": ("crypto",),
        "satisfied_by": ("open_interest", "sum_open_interest", "long_short_ratio", "liquidations", "basis"),
        "keywords": (
            "open interest", "long/short ratio", "long-short ratio", "long short ratio", "liquidation",
            "basis", "top trader", "持仓量", "多空比", "爆仓", "基差", "大户持仓",
        ),
        "sources": [
            {"name": "Binance USD-M futures open-interest statistics API",
             "url": "https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics",
             "kind": "api", "access": "Free; recent window only", "markets": ("crypto",)},
            {"name": "Binance archive futures/um/daily/metrics (open interest and long/short ratios history)",
             "url": "https://data.binance.vision/", "kind": "dataset", "access": "Free", "markets": ("crypto",)},
            BINANCE_ARCHIVE_GITHUB,
            {"name": "CoinGlass (open interest and liquidations across exchanges)", "url": "https://www.coinglass.com/",
             "kind": "api", "access": "Paid API", "markets": ("crypto",)},
        ],
        "papers": [
            {"citation": "Schmeling, Schrimpf and Todorov (2023), Crypto carry, BIS working paper 1087",
             "url": "https://www.bis.org/publ/work1087.htm"},
            {"citation": "He, Manela, Ross and von Wachter (2022), Fundamentals of perpetual futures, arXiv 2212.06888",
             "url": "https://arxiv.org/abs/2212.06888"},
        ],
    },
    {
        "id": "macro",
        "label": "Macro and rates series (yields, inflation, VIX, credit spreads)",
        "label_zh": "宏观与利率序列（收益率、通胀、VIX、信用利差）",
        "markets": ALL_MARKETS,
        "satisfied_by": ("vix", "term_spread", "default_spread", "cpi"),
        "keywords": (
            "macro", "interest rate", "yield curve", "term spread", "inflation", "cpi", "vix",
            "credit spread", "gdp", "monetary policy", "fomc", "宏观", "利率", "通胀", "社融", "货币政策",
        ),
        "sources": [
            {"name": "FRED (Federal Reserve Bank of St. Louis)", "url": "https://fred.stlouisfed.org/",
             "kind": "dataset", "access": "Free", "markets": ALL_MARKETS},
            {"name": "Amit Goyal's predictor data (Welch-Goyal series)", "url": "https://sites.google.com/view/agoyal145",
             "kind": "dataset", "access": "Free", "markets": ("us",)},
            AKSHARE,
        ],
        "papers": [
            _paper("Welch and Goyal (2008), A comprehensive look at the empirical performance of equity premium prediction, RFS",
                   "10.1093/rfs/hhm014"),
        ],
        "note": "Macro series are one number per date. A cross-sectional factor needs them interacted with a "
                "stock characteristic, such as a rolling beta to the series.",
    },
    {
        "id": "esg",
        "label": "ESG ratings and carbon emissions",
        "label_zh": "ESG 评级与碳排放",
        "markets": ("us", "cn"),
        "satisfied_by": ("esg_score", "carbon_intensity"),
        "keywords": ("esg", "carbon", "emission", "climate", "green", "sustainability", "sustainable", "环境", "碳排放", "绿色"),
        "sources": [
            {"name": "MSCI ESG ratings", "url": "https://www.msci.com/data-and-analytics/sustainability-solutions/esg-ratings",
             "kind": "dataset", "access": "Paid; MSCI ESG KLD history on WRDS", "markets": ("us", "cn")},
            {"name": "LSEG ESG scores on WRDS", "url": f"{WRDS}/lseg/", "kind": "dataset",
             "access": "WRDS subscription", "markets": ("us", "cn")},
        ],
        "papers": [
            _paper("Pastor, Stambaugh and Taylor (2022), Dissecting green returns, JFE", "10.1016/j.jfineco.2022.07.007"),
            _paper("Berg, Kolbel and Rigobon (2022), Aggregate confusion: The divergence of ESG ratings, Review of Finance",
                   "10.1093/rof/rfac033"),
        ],
    },
    {
        "id": "economic_links",
        "label": "Customer-supplier and other economic links between firms",
        "label_zh": "供应链与公司间经济关联",
        "markets": ("us", "cn"),
        "satisfied_by": ("customer_return", "supplier_return"),
        "keywords": ("supply chain", "supplier", "customer", "customers", "economic link", "peer firm", "供应链", "客户", "供应商", "产业链"),
        "sources": [
            {"name": "FactSet Revere supply chain relationships on WRDS", "url": f"{WRDS}/factset/",
             "kind": "dataset", "access": "WRDS subscription", "markets": ("us", "cn")},
            {"name": "Compustat customer segments on WRDS (S&P Global Market Intelligence)",
             "url": f"{WRDS}/sp-global-market-intelligence/", "kind": "dataset",
             "access": "WRDS subscription", "markets": ("us",)},
        ],
        "papers": [
            _paper("Cohen and Frazzini (2008), Economic links and predictable returns, JF",
                   "10.1111/j.1540-6261.2008.01379.x"),
            _paper("Menzly and Ozbas (2010), Market segmentation and cross-predictability of returns, JF",
                   "10.1111/j.1540-6261.2010.01578.x"),
        ],
    },
    {
        "id": "innovation",
        "label": "Patents and innovation",
        "label_zh": "专利与创新",
        "markets": ("us", "cn"),
        "satisfied_by": ("patent_count", "patent_value"),
        "keywords": ("patent", "patents", "innovation", "r&d", "research and development", "专利", "研发", "创新"),
        "sources": [
            {"name": "Kogan-Papanikolaou-Seru-Stoffman patent data (extended)",
             "url": "https://github.com/KPSS2017/Technological-Innovation-Resource-Allocation-and-Growth-Extended-Data",
             "kind": "github", "access": "Free", "markets": ("us",)},
            {"name": "USPTO PatentsView", "url": "https://data.uspto.gov/support/transition-guide/patentsview",
             "kind": "dataset", "access": "Free", "markets": ("us",)},
        ],
        "papers": [
            _paper("Kogan, Papanikolaou, Seru and Stoffman (2017), Technological innovation, resource allocation, and growth, QJE",
                   "10.1093/qje/qjw040"),
            _paper("Hirshleifer, Hsu and Li (2013), Innovative efficiency and stock returns, JFE",
                   "10.1016/j.jfineco.2012.09.011"),
        ],
    },
    {
        "id": "fund_flows",
        "label": "Mutual fund and ETF flows",
        "label_zh": "基金与 ETF 资金流",
        "markets": ("us", "cn"),
        "satisfied_by": ("fund_flow", "etf_flow"),
        "keywords": ("fund flow", "mutual fund", "etf flow", "fire sale", "redemption", "基金申赎", "资金流入", "ETF 资金"),
        "sources": [
            {"name": "CRSP Survivor-Bias-Free Mutual Fund database on WRDS",
             "url": f"{WRDS}/center-for-research-in-security-prices-crsp/", "kind": "dataset",
             "access": "WRDS subscription", "markets": ("us",)},
            TUSHARE,
        ],
        "papers": [
            _paper("Coval and Stafford (2007), Asset fire sales (and purchases) in equity markets, JFE",
                   "10.1016/j.jfineco.2006.09.007"),
            _paper("Lou (2012), A flow-based explanation for return predictability, RFS", "10.1093/rfs/hhs103"),
        ],
    },
    {
        "id": "corporate_bonds",
        "label": "Corporate bond prices, credit spreads and CDS",
        "label_zh": "公司债价格、信用利差与 CDS",
        "markets": ("us",),
        "satisfied_by": ("bond_spread", "cds_spread"),
        "keywords": ("corporate bond", "credit default swap", "cds", "bond return", "trace", "公司债", "信用债"),
        "sources": [
            {"name": "FINRA TRACE", "url": "https://www.finra.org/filing-reporting/trace", "kind": "dataset",
             "access": "Free recent data; history via WRDS", "markets": ("us",)},
            {"name": "Open Bond Asset Pricing (cleaned TRACE bond returns and factors)",
             "url": "https://openbondassetpricing.com/", "kind": "dataset", "access": "Free", "markets": ("us",)},
        ],
        "papers": [
            _paper("Gebhardt, Hvidkjaer and Swaminathan (2005), The cross-section of expected corporate bond returns: Betas or characteristics?, JFE",
                   "10.1016/j.jfineco.2004.04.002"),
            _paper("Dickerson, Mueller and Robotti (2023), Priced risk in corporate bonds, JFE",
                   "10.1016/j.jfineco.2023.103707"),
        ],
    },
    {
        "id": "cn_trading_disclosures",
        "label": "China exchange trading disclosures (Dragon-Tiger list, money flow, block trades, holder counts)",
        "label_zh": "A股交易披露（龙虎榜、资金流向、大宗交易、股东户数）",
        "markets": ("cn",),
        "satisfied_by": ("net_mf_amount", "buy_elg_amount", "holder_num", "top_list_net"),
        "keywords": (
            "dragon tiger", "money flow", "block trade", "holder count", "shareholder count",
            "龙虎榜", "资金流向", "主力资金", "大单", "大宗交易", "股东户数", "游资",
        ),
        "sources": [
            {"name": "Tushare Pro top_list, moneyflow, block_trade, stk_holdernumber",
             "url": "https://tushare.pro/document/2", "kind": "api", "access": "Points-based access",
             "markets": ("cn",)},
            AKSHARE,
        ],
        "papers": [],
    },
]

# Libraries of replicated published signals. Shown for any missing data,
# because a direction that needs unavailable data has often been built before.
REPLICATION_LIBRARIES: list[dict] = [
    {"name": "Open Source Asset Pricing (Chen and Zimmermann): code and data for 200+ predictors",
     "url": "https://github.com/OpenSourceAP/CrossSection", "kind": "github", "markets": ("us",)},
    {"name": "Global factor data (Jensen, Kelly and Pedersen): 153 characteristics in 93 countries",
     "url": "https://jkpfactors.com/", "kind": "dataset", "markets": ("us", "cn")},
    {"name": "JKP replication code", "url": "https://github.com/bkelly-lab/ReplicationCrisis",
     "kind": "github", "markets": ("us", "cn")},
]
REPLICATION_PAPERS: list[dict] = [
    _paper("Chen and Zimmermann (2022), Open source cross-sectional asset pricing, Critical Finance Review",
           "10.1561/104.00000112"),
    _paper("Hou, Xue and Zhang (2020), Replicating anomalies, RFS", "10.1093/rfs/hhy131"),
    _paper("Jensen, Kelly and Pedersen (2023), Is there a replication crisis in finance?, JF", "10.1111/jofi.13249"),
]

CATEGORIES_BY_ID = {entry["id"]: entry for entry in DATA_CATEGORIES}


def category_for_market(category_id: str, market_mode: str) -> dict | None:
    """Return a category with only the sources that serve ``market_mode``."""
    entry = CATEGORIES_BY_ID.get(category_id)
    if entry is None:
        return None
    sources = [
        {key: value for key, value in source.items() if key != "markets"}
        for source in entry["sources"]
        if market_mode in source.get("markets", ALL_MARKETS)
    ]
    return {
        "id": entry["id"],
        "label": entry["label"],
        "labelZh": entry["label_zh"],
        "appliesToMarket": market_mode in entry["markets"],
        "sources": sources,
        "papers": [
            {key: value for key, value in paper.items() if key != "markets"}
            for paper in entry["papers"]
            if market_mode in paper.get("markets", ALL_MARKETS)
        ],
        "note": entry.get("note"),
    }


def replication_resources(market_mode: str) -> dict:
    return {
        "sources": [
            {key: value for key, value in item.items() if key != "markets"}
            for item in REPLICATION_LIBRARIES
            if market_mode in item["markets"]
        ],
        "papers": list(REPLICATION_PAPERS) if market_mode != "crypto" else [],
    }
