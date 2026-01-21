"""
Defense criticality scoring using OpenAI API.
Processes HS6 codes and assigns defense criticality scores (0-10).
- 0: Not defense critical
- 10: Mission critical for defense industrial base

Processes 40 concurrent requests and stores results.
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from rich import print
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Config
MAX_CONCURRENT = 40
RESULTS_FILE = Path("data/defense_index.json")
ERRORS_FILE = Path("tmp/defense_index_errors.json")


class DefenseScore(BaseModel):
    score: int = Field(ge=0, le=10, description="Defense criticality score 0-10")
    reasoning: str = Field(description="Explanation for the score")


def load_json(path: Path) -> dict:
    """Load JSON file or return empty dict."""
    return json.loads(path.read_text()) if path.exists() else {}


def save_json(path: Path, data: dict):
    """Save dict to JSON file."""
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def load_hs_codes() -> dict[str, str]:
    """Extract unique HS6 codes with descriptions from naics_products.json."""
    naics_products = load_json(Path("data/naics_products.json"))
    hs_codes = {}

    for naics_data in naics_products.values():
        # Extract from exports
        for product in naics_data.get("exports", []):
            hs6 = product["hs6"]
            ld = product["ld"]
            # Keep first description we encounter for each HS6
            if hs6 not in hs_codes:
                hs_codes[hs6] = ld

        # Extract from imports
        for product in naics_data.get("imports", []):
            hs6 = product["hs6"]
            ld = product["ld"]
            if hs6 not in hs_codes:
                hs_codes[hs6] = ld

    return hs_codes


async def score_defense_criticality(
    hs6: str, description: str, semaphore: asyncio.Semaphore
):
    """Score defense criticality for a single HS6 code."""
    async with semaphore:
        try:
            response = await client.responses.parse(
                model="gpt-5-mini",
                input=[
                    {
                        "role": "system",
                        "content": """You are a defense industrial base expert. Score how critical each product is for US defense/military capabilities on a scale of 0-10.

Scoring criteria:
- 10: Mission critical - Direct weapons systems (missiles, ammunition, combat vehicles) OR critical supply chain items without which defense production stops (fasteners, basic materials, essential components)
- 7-9: High importance - Dual-use critical technology (semiconductors, batteries, rare earth elements), defense manufacturing equipment, key materials
- 4-6: Moderate importance - General industrial goods used in defense, commercial dual-use items
- 1-3: Low importance - Consumer goods with minimal defense applications
- 0: No defense relevance - Pure consumer/civilian products

Consider:
1. Direct military use
2. Supply chain criticality (if this stops, defense production stops)
3. Dual-use technology importance
4. Manufacturing capability dependence
5. Strategic material importance

Be realistic - fasteners are 10 because nothing can be built without them, but luxury consumer goods are 0.""",
                    },
                    {
                        "role": "user",
                        "content": f"Score defense criticality for HS6: {hs6} - {description}",
                    },
                ],
                text_format=DefenseScore,
            )
            return (
                hs6,
                {
                    "hs6": hs6,
                    "description": description,
                    "score": response.output_parsed.score,
                    "reasoning": response.output_parsed.reasoning,
                },
                None,
            )
        except Exception as e:
            return (hs6, None, f"{type(e).__name__}: {str(e)}")


async def main(retry_errors: bool = False):
    """Main entry point."""
    # Load existing results
    results = load_json(RESULTS_FILE)
    errors = load_json(ERRORS_FILE)

    # Get HS codes to process
    if retry_errors:
        hs_codes = {e["hs6"]: e["description"] for e in errors.values()}
        print(f"[yellow]Retrying {len(hs_codes)} failed codes...[/yellow]")
    else:
        all_codes = load_hs_codes()
        hs_codes = {k: v for k, v in all_codes.items() if k not in results}
        print(
            f"[cyan]Processing {len(hs_codes)} HS6 codes (skipping {len(results)} already done)[/cyan]"
        )

    if not hs_codes:
        print("[green]✓ All done![/green]")
        return

    # Process with progress bar
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [
        score_defense_criticality(hs6, desc, semaphore)
        for hs6, desc in hs_codes.items()
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("Scoring defense criticality...", total=len(tasks))

        for coro in asyncio.as_completed(tasks):
            hs6, result, error = await coro

            if result:
                results[hs6] = result
                errors.pop(hs6, None)
            else:
                errors[hs6] = {
                    "hs6": hs6,
                    "description": hs_codes[hs6],
                    "error": error,
                }

            progress.advance(task)

            # Save every 50
            if progress.tasks[0].completed % 50 == 0:
                save_json(RESULTS_FILE, results)
                save_json(ERRORS_FILE, errors)

    # Final save
    save_json(RESULTS_FILE, results)
    save_json(ERRORS_FILE, errors)

    # Show distribution
    score_dist = {}
    for item in results.values():
        score = item["score"]
        score_dist[score] = score_dist.get(score, 0) + 1

    print(f"\n[green]✓ Done![/green] Scored: {len(results)} | Errors: {len(errors)}")
    print("\n[cyan]Score distribution:[/cyan]")
    for score in sorted(score_dist.keys(), reverse=True):
        print(f"  Score {score}: {score_dist[score]} codes")

    if errors:
        print(f"\n[yellow]Run with --retry to retry errors[/yellow]")


if __name__ == "__main__":
    import sys

    retry_mode = "--retry" in sys.argv
    asyncio.run(main(retry_mode))
