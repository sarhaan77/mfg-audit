# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project analyzes the health of the American manufacturing sector using various metrics including China dependency, labor requirements, and trade data. The analysis works with standardized classification systems:

- **NAICS** (North American Industry Classification System): Classifies businesses/industries (e.g., 311111 = "Dog and Cat Food Manufacturing")
- **HS** (Harmonized System): 6-digit global product classification code
- **HTS** (Harmonized Tariff Schedule): 10-digit US import classification (HS6 + 4 additional digits)
- **Schedule B**: 10-digit US export classification (typically same as HTS)

Manufacturing NAICS codes of interest are 31-33.

## Development Commands

### Package Management

**This project uses `uv` for package management and script execution (requires Python 3.13+).**

**Environment setup:**
```bash
uv sync
```

**Adding dependencies:**
```bash
uv add <package-name>
```
**IMPORTANT:** Never edit `pyproject.toml` directly. Always use `uv add` to add dependencies.

### Running Scripts

**ALWAYS use `uv run` to execute Python scripts.**

**Build NAICS to products mapping from Census concordance:**
```bash
uv run scripts/mfg_concordance.py
```

**Fetch trade data from Census API:**
```bash
uv run scripts/get_hs6_trade_deficit.py
uv run scripts/get_hs6_trade_deficit.py --retry  # Retry failed requests
```

**Calculate trade deficits per country:**
```bash
uv run scripts/calculate_trade_deficit.py
```

**Generate China dependency index:**
```bash
uv run scripts/generate_china_index.py
```

**Generate defense criticality scores:**
```bash
uv run scripts/defense_index.py
uv run scripts/defense_index.py --retry  # Retry failed requests
```

### Dashboard

**Run the intelligence dashboard:**
```bash
uv run uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```
Then open browser to http://localhost:8000

### Linting
```bash
uv run ruff check .
uv run ruff format .
```

## Architecture

### Data Processing Pipeline

The project uses a multi-stage processing pipeline to analyze US manufacturing trade data:

1. **NAICS-Product Mapping** (`scripts/mfg_concordance.py`):
   - Reads manufacturing NAICS codes from `data/mfg_naics.csv`
   - Maps each NAICS code to export/import products using Census concordance files
   - Output: `data/naics_products.json` with structure: `{naics: {exports: [...], imports: [...]}}`
   - Each product includes HS10, HS6, long description (ld), and short description (sd)

2. **Trade Data Fetching** (`scripts/get_hs6_trade_deficit.py`):
   - Extracts unique HS6 codes from `naics_products.json`
   - Fetches country-level export/import values from Census API for each HS6
   - Processes 40 concurrent requests with aiohttp
   - Incremental processing: saves every 50 requests, skips completed codes
   - Output: `data/trade_deficit.json` with structure: `{hs6: {export_value: {country: value}, import_value: {country: value}}}`

3. **Trade Deficit Calculation** (`scripts/calculate_trade_deficit.py`):
   - Calculates per-country trade deficit (import - export) for each HS6
   - Adds `deficit` field to `trade_deficit.json`
   - Positive = trade deficit, negative = trade surplus

4. **China Dependency Index** (`scripts/generate_china_index.py`):
   - Extracts China-specific trade deficits for all HS6 codes
   - Filters to only positive deficits (US imports more from China than exports)
   - Sorts by deficit size (largest first)
   - Output: `data/china_index.json`

5. **Defense Criticality Scoring** (`scripts/defense_index.py`):
   - Uses OpenAI API (gpt-5-mini) with structured output to score defense criticality (0-10)
   - Scores based on: direct military use, supply chain criticality, dual-use tech, strategic materials
   - Processes 40 concurrent requests with semaphore-based rate limiting
   - Incremental processing with retry support
   - Output: `data/defense_index.json` with scores and reasoning for each HS6

### Key Design Patterns

**Async Batch Processing:**
- All data fetching scripts use `asyncio.Semaphore` for concurrency control
- `asyncio.as_completed()` for processing results as they arrive
- Progress tracking with `rich.progress` for user feedback

**Incremental Processing:**
- Load existing results at startup
- Skip already-processed codes
- Save progress periodically (every 50 requests)
- Final save at completion to ensure no data loss

**Error Handling:**
- Separate error storage for retryable failures
- `--retry` flag to reprocess only failed requests
- Results are mutually exclusive across success/no-match/error categories

## Data Files

### Input Data
- `data/mfg_naics.csv`: Cleaned manufacturing NAICS codes (31-33)
- `tmp/expconcord24.csv`: Census 2024 export concordance (NAICS → Schedule B)
- `tmp/impconcord24.csv`: Census 2024 import concordance (NAICS → HTS)

### Output Data
- `data/naics_products.json`: NAICS → products mapping with HS codes
- `data/trade_deficit.json`: HS6 country-level trade data (exports, imports, deficits)
- `data/china_index.json`: China trade deficits sorted by size
- `data/defense_index.json`: Defense criticality scores (0-10) with reasoning
- `tmp/trade_deficit_errors.json`: Failed trade data API requests
- `tmp/defense_index_errors.json`: Failed defense scoring API requests

## Environment Variables

Required in `.env` file:
- `OPENAI_API_KEY`: For defense criticality scoring (uses gpt-5-mini model)
- `CENSUS_API_KEY`: For fetching US trade statistics from Census API

## Metrics

### Completed Metrics
1. **China Index** (`data/china_index.json`): Trade deficit with China for each HS6 code, sorted by magnitude
2. **Defense Index** (`data/defense_index.json`): Defense criticality scores (0-10) with AI-generated reasoning

### Planned Metrics
1. **Labor Index**: Labor requirements for production (BLS data)
2. **Cost Ratio**: USA production cost / China production cost
