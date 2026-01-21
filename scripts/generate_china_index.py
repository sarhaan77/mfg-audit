"""
Generate China trade deficit index.
Extracts trade deficit with China for each HS6 code,
sorted in descending order (largest deficits first).
Only includes codes with positive deficits (US imports more from China).
"""

import json
from pathlib import Path

from rich import print


def load_json(path: Path) -> dict:
    """Load JSON file."""
    return json.loads(path.read_text())


def save_json(path: Path, data: dict):
    """Save dict to JSON file."""
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def generate_china_index(trade_data: dict) -> dict:
    """Extract China trade deficits and sort by size."""
    china_deficits = {}

    for hs6, data in trade_data.items():
        deficit_data = data.get("deficit", {})
        china_deficit = deficit_data.get("CHINA", 0)

        # Only include positive deficits (US imports more from China)
        if china_deficit > 0:
            china_deficits[hs6] = china_deficit

    # Sort by deficit in descending order
    sorted_deficits = dict(
        sorted(china_deficits.items(), key=lambda x: x[1], reverse=True)
    )

    return sorted_deficits


def main():
    """Main entry point."""
    trade_file = Path("data/trade_deficit.json")
    output_file = Path("data/china_index.json")

    print("[cyan]Loading trade data...[/cyan]")
    trade_data = load_json(trade_file)

    print("[cyan]Extracting China trade deficits...[/cyan]")
    china_index = generate_china_index(trade_data)

    print(f"[cyan]Saving {len(china_index)} HS6 codes with China trade deficit...[/cyan]")
    save_json(output_file, china_index)

    # Show top 10
    print("\n[green]✓ Done![/green] Top 10 China trade deficits:")
    for i, (hs6, deficit) in enumerate(list(china_index.items())[:10], 1):
        print(f"  {i}. HS6 {hs6}: ${deficit:,}")


if __name__ == "__main__":
    main()
