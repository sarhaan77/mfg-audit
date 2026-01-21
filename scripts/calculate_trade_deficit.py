"""
Calculate trade deficit per country for each HS6 code.
Adds a 'deficit' key with per-country calculations (import - export).

Positive deficit = trade deficit (import more than export)
Negative deficit = trade surplus (export more than import)
"""

import json
from pathlib import Path

from rich import print


def load_json(path: Path) -> dict:
    """Load JSON file."""
    return json.loads(path.read_text())


def save_json(path: Path, data: dict):
    """Save dict to JSON file."""
    path.write_text(json.dumps(data, indent=2))


def calculate_deficits(trade_data: dict) -> dict:
    """Calculate per-country trade deficit for each HS6 code."""
    for hs6, data in trade_data.items():
        exports = data.get("export_value", {})
        imports = data.get("import_value", {})

        # Get all unique countries
        all_countries = set(exports.keys()) | set(imports.keys())

        # Calculate deficit for each country (import - export)
        deficit = {}
        for country in all_countries:
            export_val = exports.get(country, 0)
            import_val = imports.get(country, 0)
            deficit[country] = import_val - export_val

        data["deficit"] = deficit

    return trade_data


def main():
    """Main entry point."""
    trade_file = Path("data/trade_deficit.json")

    print("[cyan]Loading trade data...[/cyan]")
    trade_data = load_json(trade_file)

    print(f"[cyan]Calculating deficits for {len(trade_data)} HS6 codes...[/cyan]")
    updated_data = calculate_deficits(trade_data)

    print("[cyan]Saving updated data...[/cyan]")
    save_json(trade_file, updated_data)

    print("[green]✓ Done! Added deficit calculations to all HS6 codes[/green]")


if __name__ == "__main__":
    main()
