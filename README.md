# US Manufacturing Trade Analysis

analyzing the health of american manufacturing by looking at trade deficits, china dependency, and defense criticality.

## quick start

```bash
uv sync
uv run uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

then open http://localhost:8000

## data pipeline

1. **naics → products**: map manufacturing industries (NAICS 31-33) to their import/export products using census concordance files
2. **trade data**: fetch country-level trade data from census API for each HS6 product code
3. **china index**: calculate trade deficit with china for each product
4. **defense index**: score defense criticality (0-10) using openai

## metrics

| metric | description | status |
|--------|-------------|--------|
| china index | trade deficit with china per HS6 | done |
| defense index | defense criticality score (0-10) | done |
| labor index | labor requirements (BLS data) | planned |
| cost ratio | USA vs china production cost | planned |

## classification systems

- **NAICS**: classifies industries (e.g., 311111 = "Dog and Cat Food Manufacturing")
- **HS6**: 6-digit global product code
- **HTS**: 10-digit US import code (HS6 + 4 digits)
- **Schedule B**: 10-digit US export code (usually same as HTS)

## env vars

```
CENSUS_API_KEY=...
OPENAI_API_KEY=...
```
