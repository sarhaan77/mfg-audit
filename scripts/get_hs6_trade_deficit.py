"""
Fetch export/import data for HS6 codes from Census API.
Extracts HS6 codes from naics_products.json and fetches trade data.
Processes 40 requests concurrently and stores in a single JSON file.

Output format:
{
  "230910": {
    "export_value": {"MEXICO": 237959262, "CANADA": 93878539, ...},
    "import_value": {"JAPAN": 503848134, "GERMANY": 401047381, ...}
  }
}
"""

import asyncio
import json
import os
from pathlib import Path

import aiohttp
from dotenv import load_dotenv
from rich import print
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

load_dotenv()

# Config
MAX_CONCURRENT = 40
CENSUS_API_KEY = os.getenv("CENSUS_API_KEY")
EXPORTS_URL = "https://api.census.gov/data/timeseries/intltrade/exports/hs"
IMPORTS_URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
RESULTS_FILE = Path("data/trade_deficit.json")
ERRORS_FILE = Path("tmp/trade_deficit_errors.json")


def load_json(path: Path) -> dict:
    """Load JSON file or return empty dict."""
    return json.loads(path.read_text()) if path.exists() else {}


def save_json(path: Path, data: dict):
    """Save dict to JSON file."""
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def load_hs6_from_naics() -> list[str]:
    """Extract unique HS6 codes from naics_products.json."""
    naics_products = load_json(Path("data/naics_products.json"))
    hs6_codes = set()

    for naics_data in naics_products.values():
        # Extract from exports
        for product in naics_data.get("exports", []):
            hs6_codes.add(product["hs6"])
        # Extract from imports
        for product in naics_data.get("imports", []):
            hs6_codes.add(product["hs6"])

    return sorted(list(hs6_codes))


async def fetch_hs6_data(
    hs6: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore
):
    """Fetch export and import data for a single HS6 code."""
    async with semaphore:
        try:
            # Fetch exports
            params_exp = {
                "get": "CTY_CODE,CTY_NAME,ALL_VAL_YR",
                "E_COMMODITY": hs6,
                "COMM_LVL": "HS6",
                "YEAR": "2024",
                "MONTH": "12",
                "key": CENSUS_API_KEY,
                "SUMMARY_LVL": "DET",
            }
            async with session.get(EXPORTS_URL, params=params_exp) as resp:
                resp.raise_for_status()
                exp_data = await resp.json()
                export_dict = {}
                if exp_data and len(exp_data) > 1:
                    for row in exp_data[1:]:  # Skip header
                        country, value = row[1], row[2]
                        if country and value and country != "TOTAL FOR ALL COUNTRIES":
                            export_dict[country] = int(value) if value != "null" else 0

            # Fetch imports
            params_imp = {
                "get": "CTY_CODE,CTY_NAME,GEN_VAL_YR",
                "I_COMMODITY": hs6,
                "COMM_LVL": "HS6",
                "YEAR": "2024",
                "MONTH": "12",
                "key": CENSUS_API_KEY,
                "SUMMARY_LVL": "DET",
            }
            async with session.get(IMPORTS_URL, params=params_imp) as resp:
                resp.raise_for_status()
                imp_data = await resp.json()
                import_dict = {}
                if imp_data and len(imp_data) > 1:
                    for row in imp_data[1:]:  # Skip header
                        country, value = row[1], row[2]
                        if country and value and country != "TOTAL FOR ALL COUNTRIES":
                            import_dict[country] = int(value) if value != "null" else 0

            return (
                hs6,
                {"export_value": export_dict, "import_value": import_dict},
                None,
            )

        except Exception as e:
            return (hs6, None, f"{type(e).__name__}: {str(e)}")


async def main(retry_errors: bool = False):
    """Main entry point."""
    # Load existing data
    results = load_json(RESULTS_FILE)
    errors = load_json(ERRORS_FILE)

    # Get HS codes to process
    if retry_errors:
        hs_codes = [e["hscode"] for e in errors.values()]
        print(f"[yellow]Retrying {len(hs_codes)} failed codes...[/yellow]")
    else:
        all_codes = load_hs6_from_naics()
        hs_codes = [hc for hc in all_codes if hc not in results]
        print(
            f"[cyan]Processing {len(hs_codes)} HS6 codes (skipping {len(results)} already done)[/cyan]"
        )

    if not hs_codes:
        print("[green]✓ All done![/green]")
        return

    # Process with progress bar
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_hs6_data(hc, session, semaphore) for hc in hs_codes]

        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task("Fetching trade data...", total=len(tasks))

            for coro in asyncio.as_completed(tasks):
                hs6, result, error = await coro

                if result:
                    results[hs6] = result
                    errors.pop(hs6, None)
                else:
                    errors[hs6] = {"hscode": hs6, "error": error}

                progress.advance(task)

                # Save every 50
                if progress.tasks[0].completed % 50 == 0:
                    save_json(RESULTS_FILE, results)
                    save_json(ERRORS_FILE, errors)

    # Final save
    save_json(RESULTS_FILE, results)
    save_json(ERRORS_FILE, errors)

    print(f"\n[green]✓ Done![/green] Success: {len(results)} | Errors: {len(errors)}")
    if errors:
        print(f"[yellow]Run with --retry to retry errors[/yellow]")


if __name__ == "__main__":
    import sys

    retry_mode = "--retry" in sys.argv
    asyncio.run(main(retry_mode))
