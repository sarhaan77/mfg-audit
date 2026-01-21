"""
Map manufacturing NAICS codes to their export/import products from Census concordance files.

This script reads:
- Manufacturing NAICS codes from data/mfg_naics.csv
- Export concordance from tmp/expconcord24.csv
- Import concordance from tmp/impconcord24.csv

And produces a JSON file mapping each NAICS code to its associated commodity codes.
"""

import json
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.progress import track

console = Console()


def load_naics_codes(filepath: str) -> list[str]:
    """Load manufacturing NAICS codes from CSV."""
    df = pd.read_csv(filepath)
    return df["code"].astype(str).tolist()


def load_concordance(filepath: str) -> pd.DataFrame:
    """Load concordance file and ensure NAICS column is string type."""
    df = pd.read_csv(
        filepath, dtype={"naics": str, "commodity": str, "descriptn": str}
    )
    return df


def transform_product(product: dict) -> dict:
    """Transform a product record to the desired format."""
    return {
        "hs10": product["commodity"],
        "hs6": product["commodity"][:6],
        "ld": product["descriptn"],
        "sd": product["abbreviatn"],
    }


def build_naics_products_map(
    naics_codes: list[str],
    export_concordance: pd.DataFrame,
    import_concordance: pd.DataFrame,
) -> dict:
    """
    Build a dictionary mapping each NAICS code to its export/import products.

    Args:
        naics_codes: List of NAICS codes to process
        export_concordance: Export concordance DataFrame
        import_concordance: Import concordance DataFrame

    Returns:
        Dictionary with structure:
        {
            "311111": {
                "exports": [{"hs10": "...", "hs6": "...", "ld": "...", "sd": "..."}, ...],
                "imports": [{"hs10": "...", "hs6": "...", "ld": "...", "sd": "..."}, ...]
            },
            ...
        }
    """
    result = {}

    for naics in track(naics_codes, description="Processing NAICS codes"):
        # Filter concordance files for matching NAICS code
        export_matches = export_concordance[export_concordance["naics"] == naics]
        import_matches = import_concordance[import_concordance["naics"] == naics]

        # Extract and transform products
        exports = [
            transform_product(p)
            for p in export_matches[
                ["commodity", "descriptn", "abbreviatn"]
            ].to_dict("records")
        ]
        imports = [
            transform_product(p)
            for p in import_matches[
                ["commodity", "descriptn", "abbreviatn"]
            ].to_dict("records")
        ]

        result[naics] = {"exports": exports, "imports": imports}

    return result


def main():
    console.print("[bold cyan]NAICS to Products Mapping[/bold cyan]")
    console.print()

    # Define file paths
    naics_file = Path("data/mfg_naics.csv")
    export_file = Path("tmp/expconcord24.csv")
    import_file = Path("tmp/impconcord24.csv")
    output_file = Path("data/naics_products.json")

    # Load data
    console.print("[yellow]Loading data...[/yellow]")
    naics_codes = load_naics_codes(naics_file)
    console.print(f"   Loaded {len(naics_codes)} NAICS codes")

    export_concordance = load_concordance(export_file)
    console.print(f"   Loaded {len(export_concordance)} export concordance rows")

    import_concordance = load_concordance(import_file)
    console.print(f"   Loaded {len(import_concordance)} import concordance rows")
    console.print()

    # Build mapping
    console.print("[yellow]Building NAICS to products mapping...[/yellow]")
    naics_products = build_naics_products_map(
        naics_codes, export_concordance, import_concordance
    )
    console.print()

    # Save results
    console.print(f"[yellow]Saving results to {output_file}...[/yellow]")
    with open(output_file, "w") as f:
        json.dump(naics_products, f, indent=2)

    # Print summary statistics
    console.print()
    console.print("[bold green] Complete![/bold green]")
    console.print()
    console.print("[cyan]Summary:[/cyan]")

    total_exports = sum(len(v["exports"]) for v in naics_products.values())
    total_imports = sum(len(v["imports"]) for v in naics_products.values())
    naics_with_exports = sum(1 for v in naics_products.values() if v["exports"])
    naics_with_imports = sum(1 for v in naics_products.values() if v["imports"])

    console.print(f"  Total NAICS codes processed: {len(naics_products)}")
    console.print(f"  NAICS codes with exports: {naics_with_exports}")
    console.print(f"  NAICS codes with imports: {naics_with_imports}")
    console.print(f"  Total export products: {total_exports}")
    console.print(f"  Total import products: {total_imports}")
    console.print(f"  Output saved to: {output_file}")


if __name__ == "__main__":
    main()
