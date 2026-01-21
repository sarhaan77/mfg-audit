"""
Simple data explorer for US manufacturing trade analysis.
"""

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Data directory
DATA_DIR = Path("data")

# Global data store
data_store: dict[str, Any] = {}


def load_data():
    """Load all data files into memory."""
    print("Loading data files...")

    # Load NAICS products
    with open(DATA_DIR / "naics_products.json") as f:
        data_store["naics_products"] = json.load(f)

    # Load trade deficit
    with open(DATA_DIR / "trade_deficit.json") as f:
        data_store["trade_deficit"] = json.load(f)

    # Load China index
    with open(DATA_DIR / "china_index.json") as f:
        data_store["china_index"] = json.load(f)

    # Load defense index
    with open(DATA_DIR / "defense_index.json") as f:
        data_store["defense_index"] = json.load(f)

    # Load NAICS names
    naics_names = {}
    with open(DATA_DIR / "mfg_naics.csv") as f:
        next(f)  # Skip header
        for line in f:
            code, name = line.strip().split(",", 1)
            naics_names[code] = name
    data_store["naics_names"] = naics_names

    # Build HS6 to NAICS reverse mapping
    hs6_to_naics = {}
    for naics, products in data_store["naics_products"].items():
        for product in products.get("exports", []) + products.get("imports", []):
            hs6 = product["hs6"]
            if hs6 not in hs6_to_naics:
                hs6_to_naics[hs6] = set()
            hs6_to_naics[hs6].add(naics)
    # Convert sets to lists for JSON serialization
    data_store["hs6_to_naics"] = {k: list(v) for k, v in hs6_to_naics.items()}

    # Build HS6 description lookup from defense index
    hs6_descriptions = {}
    for hs6, info in data_store["defense_index"].items():
        hs6_descriptions[hs6] = info["description"]
    data_store["hs6_descriptions"] = hs6_descriptions

    print(f"Loaded {len(data_store['naics_products'])} NAICS codes")
    print(f"Loaded {len(data_store['trade_deficit'])} HS6 trade records")
    print(f"Loaded {len(data_store['china_index'])} China deficit records")
    print(f"Loaded {len(data_store['defense_index'])} defense scores")


# Create FastAPI app
app = FastAPI(title="Manufacturing Trade Explorer")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Load data on startup
load_data()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/stats")
async def get_stats():
    """Get overview statistics."""
    total_china_deficit = sum(data_store["china_index"].values())
    high_defense = sum(
        1
        for info in data_store["defense_index"].values()
        if info.get("score", 0) >= 7
    )
    return {
        "total_hs6": len(data_store["trade_deficit"]),
        "total_naics": len(data_store["naics_products"]),
        "total_china_deficit": total_china_deficit,
        "high_defense_count": high_defense,
    }


@app.get("/api/products")
async def get_products(search: str | None = None, limit: int = 1000):
    """Get all products with summary data."""
    products = []

    for hs6, trade in data_store["trade_deficit"].items():
        # Get description
        desc = data_store["hs6_descriptions"].get(hs6, "")

        # Apply search filter
        if search:
            search_lower = search.lower()
            if not (
                search_lower in hs6.lower() or search_lower in desc.lower()
            ):
                continue

        # Get China deficit
        china_deficit = data_store["china_index"].get(hs6, 0)

        # Get defense score
        defense_info = data_store["defense_index"].get(hs6, {})
        defense_score = defense_info.get("score", 0)

        # Calculate total trade balance
        export_values = trade.get("export_value", {})
        import_values = trade.get("import_value", {})

        total_exports = sum(export_values.values())
        total_imports = sum(import_values.values())
        china_imports = 0
        for country, value in import_values.items():
            if country.upper() == "CHINA":
                china_imports = value
                break

        china_import_share = (
            china_imports / total_imports if total_imports > 0 else 0
        )
        trade_balance = total_exports - total_imports

        products.append(
            {
                "hs6": hs6,
                "description": desc,
                "china_deficit": china_deficit,
                "china_import_share": china_import_share,
                "defense_score": defense_score,
                "trade_balance": trade_balance,
                "total_exports": total_exports,
                "total_imports": total_imports,
            }
        )

    # Sort by China deficit (descending)
    products.sort(key=lambda x: x["china_deficit"], reverse=True)

    return {"products": products[:limit], "total": len(products)}


@app.get("/api/products/{hs6}")
async def get_product_detail(hs6: str):
    """Get detailed information for a specific HS6 code."""
    # Get trade data
    trade = data_store["trade_deficit"].get(hs6)
    if not trade:
        return {"error": "Product not found"}

    # Build country-level breakdown
    export_values = trade.get("export_value", {})
    import_values = trade.get("import_value", {})

    countries = {}
    for country, export_val in export_values.items():
        countries[country] = {
            "exports": export_val,
            "imports": 0,
            "balance": export_val,
        }

    china_imports = 0
    for country, import_val in import_values.items():
        if country in countries:
            countries[country]["imports"] = import_val
            countries[country]["balance"] = (
                countries[country]["exports"] - import_val
            )
        else:
            countries[country] = {
                "exports": 0,
                "imports": import_val,
                "balance": -import_val,
            }
        if country.upper() == "CHINA":
            china_imports = import_val

    # Sort by absolute trade volume
    country_list = [
        {"country": country, **values} for country, values in countries.items()
    ]
    country_list.sort(
        key=lambda x: x["exports"] + x["imports"], reverse=True
    )

    total_imports = sum(import_values.values())
    china_import_share = (
        china_imports / total_imports if total_imports > 0 else 0
    )

    # Get defense info
    defense_info = data_store["defense_index"].get(hs6, {})

    # Get related NAICS
    naics_codes = data_store["hs6_to_naics"].get(hs6, [])
    naics_list = [
        {"code": code, "name": data_store["naics_names"].get(code, "")}
        for code in naics_codes
    ]

    return {
        "hs6": hs6,
        "description": data_store["hs6_descriptions"].get(hs6, ""),
        "defense_score": defense_info.get("score", 0),
        "defense_reasoning": defense_info.get("reasoning", ""),
        "china_deficit": data_store["china_index"].get(hs6, 0),
        "china_import_share": china_import_share,
        "china_imports": china_imports,
        "total_imports": total_imports,
        "countries": country_list,
        "naics": naics_list,
    }


@app.get("/api/naics")
async def get_naics_list():
    """Get list of all NAICS codes with aggregate metrics."""
    naics_list = []

    for naics, name in data_store["naics_names"].items():
        products = data_store["naics_products"].get(naics, {})

        # Get unique HS6 codes for this NAICS
        hs6_codes = set()
        for product in products.get("exports", []) + products.get(
            "imports", []
        ):
            hs6_codes.add(product["hs6"])

        # Calculate aggregate metrics
        total_china_deficit = sum(
            data_store["china_index"].get(hs6, 0) for hs6 in hs6_codes
        )
        avg_defense = (
            sum(
                data_store["defense_index"].get(hs6, {}).get("score", 0)
                for hs6 in hs6_codes
            )
            / len(hs6_codes)
            if hs6_codes
            else 0
        )

        naics_list.append(
            {
                "code": naics,
                "name": name,
                "product_count": len(hs6_codes),
                "total_china_deficit": total_china_deficit,
                "avg_defense_score": round(avg_defense, 1),
            }
        )

    # Sort by China deficit
    naics_list.sort(key=lambda x: x["total_china_deficit"], reverse=True)

    return {"naics": naics_list}


@app.get("/api/naics/{code}")
async def get_naics_products(code: str):
    """Get all products for a specific NAICS code."""
    products = data_store["naics_products"].get(code, {})
    name = data_store["naics_names"].get(code, "")

    # Get unique HS6 codes
    hs6_codes = set()
    for product in products.get("exports", []) + products.get("imports", []):
        hs6_codes.add(product["hs6"])

    # Build product list with metrics
    product_list = []
    for hs6 in hs6_codes:
        product_list.append(
            {
                "hs6": hs6,
                "description": data_store["hs6_descriptions"].get(hs6, ""),
                "china_deficit": data_store["china_index"].get(hs6, 0),
                "defense_score": data_store["defense_index"]
                .get(hs6, {})
                .get("score", 0),
            }
        )

    # Sort by China deficit
    product_list.sort(key=lambda x: x["china_deficit"], reverse=True)

    return {"code": code, "name": name, "products": product_list}


@app.get("/api/critical")
async def get_critical_matrix(
    min_china_deficit: int = 0, min_defense_score: int = 0
):
    """Get products in the critical matrix (high China dependency + high defense score)."""
    critical = []

    for hs6 in data_store["china_index"].keys():
        china_deficit = data_store["china_index"].get(hs6, 0)
        defense_score = (
            data_store["defense_index"].get(hs6, {}).get("score", 0)
        )

        if (
            china_deficit >= min_china_deficit
            and defense_score >= min_defense_score
        ):
            critical.append(
                {
                    "hs6": hs6,
                    "description": data_store["hs6_descriptions"].get(hs6, ""),
                    "china_deficit": china_deficit,
                    "defense_score": defense_score,
                }
            )

    # Sort by combined criticality (normalized)
    max_deficit = max(data_store["china_index"].values()) or 1
    for item in critical:
        item["criticality"] = (
            item["china_deficit"] / max_deficit + item["defense_score"] / 10
        ) / 2

    critical.sort(key=lambda x: x["criticality"], reverse=True)

    return {"products": critical, "total": len(critical)}
