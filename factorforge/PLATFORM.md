# FactorForge · 因子智研

An interactive factor-research platform with Chinese/English UI, built on the QuantaAlpha codebase. The original package name remains `quantaalpha` for import compatibility. Original author metadata is preserved in `pyproject.toml`.

## Features

- Separate US, China A-share and Binance USDT perpetual market configurations and factor libraries.
- LLM hypothesis generation, factor evaluation, evolution and incremental library saving.
- Validation-based selection, independent split evaluation and saved charts/statistics.
- Expanding-window model backtests with LightGBM, PLS and Lasso; correlation pruning.
- Market-specific exposure diagnostics and configurable portfolio analytics.
- FactorForge interface, language switching, factor library, backtest and settings pages.

## Run locally

Python 3.10 and Node.js 18+ are recommended. In WSL/Linux:

```bash
cd factorforge
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r frontend-v2/backend/requirements.txt
cp .env.template .env
# Edit .env: configure provider credentials and local data paths.
cd frontend-v2
npm ci
python backend/app.py
```

In a second terminal, run `npm run dev` from `factorforge/frontend-v2`. Open http://localhost:3000/ (backend port 8000).

Existing Conda installations may use `bash frontend-v2/start.sh`; this expects a `quantaalpha` Conda environment. The supplied Windows launcher is for the existing WSL installation and its `quantaalpha.service`; it is not a fresh-install script.

## Data and credentials

Configure your own data and date splits in Settings or `.env`. Source financial databases, market data, generated factor libraries, experiment outputs, model caches, installed dependencies and actual credentials are intentionally excluded. Local path defaults are examples and must be adapted on another machine. Data providers and LLM access must be supplied separately.

## Validation and limits

Frontend build: `cd frontend-v2 && npm ci && npm run build`.
Python tests: `python -m pytest tests` from this directory.

This publication captures the working research platform; it is not a certification of trading performance. Some legacy UI text still uses the translation fallback. Existing statistical/portfolio assumptions should be reviewed for each market before relying on reported results. Tests and build checks do not require launching new mining jobs.

See [README.md](README.md) and [README_EN.md](README_EN.md) for the inherited framework documentation. The repository's root research pipeline and historical results remain separate from this web platform.
