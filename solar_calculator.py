import argparse
import json
from dataclasses import dataclass
from typing import Any

import requests


POSTCODES_API = "https://api.postcodes.io/postcodes/{postcode}"
PVGIS_API = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"
NOMINATIM_API = "https://nominatim.openstreetmap.org/search"

DEFAULT_IMPORT_RATE_GBP_PER_KWH = 0.245
DEFAULT_SEG_RATE_GBP_PER_KWH = 0.055
DEFAULT_PANEL_POWER_KWP_PER_M2 = 0.2
DEFAULT_ROOF_USABLE_FACTOR = 0.65
DEFAULT_MAX_USABLE_ROOF_M2 = 35.0
DEFAULT_PERFORMANCE_RATIO = 0.8
DEFAULT_ANNUAL_DEGRADATION = 0.005
DEFAULT_ANNUAL_PRICE_INFLATION = 0.0

HOUSE_TYPE_DEFAULT_ROOF_M2 = {
    "flat": 18.0,
    "terrace": 35.0,
    "semi": 45.0,
    "detached": 52.0,
}

SCENARIOS = {
    "conservative": {"import_rate": 0.22, "seg_rate": 0.04, "self_consumption": 0.3},
    "expected": {"import_rate": DEFAULT_IMPORT_RATE_GBP_PER_KWH, "seg_rate": DEFAULT_SEG_RATE_GBP_PER_KWH, "self_consumption": 0.4},
    "optimistic": {"import_rate": 0.28, "seg_rate": 0.12, "self_consumption": 0.55},
}


@dataclass
class SolarInputs:
    postcode: str
    annual_usage_kwh: float
    roof_area_m2: float
    house_type: str
    roof_area_explicit: bool
    import_rate: float
    seg_rate: float
    self_consumption: float
    annual_price_inflation: float
    regional_cost_multiplier: float
    battery: bool


def get_location_from_postcode(postcode: str) -> dict[str, Any]:
    compact = postcode.replace(" ", "")
    try:
        response = requests.get(POSTCODES_API.format(postcode=compact), timeout=15)
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == 200 and payload.get("result"):
            return payload["result"]
    except Exception:
        pass

    query = f"{postcode}, Northern Ireland, UK"
    fallback = requests.get(
        NOMINATIM_API,
        params={"q": query, "format": "jsonv2", "limit": 1},
        headers={"User-Agent": "SolarSense/1.0"},
        timeout=20,
    )
    fallback.raise_for_status()
    rows = fallback.json()
    if not rows:
        raise ValueError("Invalid postcode or no location data found.")
    top = rows[0]
    address = top.get("address", {})
    return {
        "postcode": postcode,
        "latitude": float(top["lat"]),
        "longitude": float(top["lon"]),
        "country": "Northern Ireland",
        "region": address.get("state") or "Northern Ireland",
        "admin_district": address.get("county") or address.get("city_district"),
        "source": "nominatim_fallback",
    }


def get_pvgis_yield_kwh_per_kwp(lat: float, lon: float) -> float:
    params = {
        "lat": lat,
        "lon": lon,
        "peakpower": 1,
        "loss": int((1 - DEFAULT_PERFORMANCE_RATIO) * 100),
        "angle": 35,
        "aspect": 0,
        "outputformat": "json",
    }
    response = requests.get(PVGIS_API, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    return float(data["outputs"]["totals"]["fixed"]["E_y"])


def resolve_roof_area(roof_area_m2: float | None, house_type: str | None) -> float:
    if roof_area_m2 and roof_area_m2 > 0:
        return float(roof_area_m2)
    if house_type and house_type in HOUSE_TYPE_DEFAULT_ROOF_M2:
        return HOUSE_TYPE_DEFAULT_ROOF_M2[house_type]
    return 45.0


def estimate_system_size_kwp(roof_area_m2: float) -> float:
    usable_m2 = min(roof_area_m2 * DEFAULT_ROOF_USABLE_FACTOR, DEFAULT_MAX_USABLE_ROOF_M2)
    return usable_m2 * DEFAULT_PANEL_POWER_KWP_PER_M2


def cost_per_kwp_for_size(system_size_kwp: float) -> float:
    if system_size_kwp <= 5:
        return 1550.0
    if system_size_kwp <= 8:
        ratio = (system_size_kwp - 5.0) / 3.0
        return 1550.0 - (150.0 * ratio)
    return 1350.0


def regional_cost_multiplier(loc: dict[str, Any], postcode: str) -> float:
    admin = str(loc.get("admin_district") or "").lower()
    compact = postcode.replace(" ", "").upper()
    london_prefixes = (
        "SE", "SW", "W", "NW", "N", "E", "EC", "WC", "BR", "CR", "DA", "EN",
        "HA", "IG", "KT", "RM", "SM", "TN", "TW", "UB",
    )
    is_london = "london" in admin or any(compact.startswith(p) for p in london_prefixes)
    return 1.2 if is_london else 1.0


def calculate_10y(inputs: SolarInputs, annual_yield_per_kwp: float) -> dict[str, float]:
    system_size_kwp = estimate_system_size_kwp(inputs.roof_area_m2)
    year_1_gen = system_size_kwp * annual_yield_per_kwp
    install_cost = system_size_kwp * cost_per_kwp_for_size(system_size_kwp) * inputs.regional_cost_multiplier
    battery_cost = 3200 if inputs.battery else 0
    total_investment = install_cost + battery_cost

    total_generation = 0.0
    total_savings = 0.0
    total_export_income = 0.0
    annual_generation = year_1_gen
    year_import_rate = inputs.import_rate

    for _ in range(10):
        self_used = min(inputs.annual_usage_kwh, annual_generation * inputs.self_consumption)
        exported = max(0.0, annual_generation - self_used)
        total_generation += annual_generation
        total_savings += self_used * year_import_rate
        total_export_income += exported * inputs.seg_rate
        annual_generation *= 1 - DEFAULT_ANNUAL_DEGRADATION
        year_import_rate *= 1 + inputs.annual_price_inflation

    total_benefit = total_savings + total_export_income
    net_profit_10y = total_benefit - total_investment

    return {
        "system_size_kwp": round(system_size_kwp, 2),
        "year_1_generation_kwh": round(year_1_gen, 0),
        "ten_year_generation_kwh": round(total_generation, 0),
        "total_investment_gbp": round(total_investment, 0),
        "ten_year_bill_savings_gbp": round(total_savings, 0),
        "ten_year_export_income_gbp": round(total_export_income, 0),
        "ten_year_total_benefit_gbp": round(total_benefit, 0),
        "ten_year_net_profit_gbp": round(net_profit_10y, 0),
        "regional_cost_multiplier": round(inputs.regional_cost_multiplier, 2),
        "annual_price_inflation": round(inputs.annual_price_inflation, 4),
    }


def build_output(inputs: SolarInputs, loc: dict[str, Any], annual_yield: float, scenario_mode: bool) -> dict[str, Any]:
    warnings: list[str] = []
    if inputs.house_type == "flat":
        if inputs.roof_area_explicit:
            warnings.append(
                "Flat/apartment feasibility depends on roof ownership and freeholder consent. Check legal and planning constraints."
            )
        else:
            warnings.append(
                "Flat/apartment estimate uses conservative default roof area and may not be installable due to shared-roof constraints."
            )

    if scenario_mode:
        scenario_results: dict[str, dict[str, float]] = {}
        for name, cfg in SCENARIOS.items():
            s_inputs = SolarInputs(
                postcode=inputs.postcode,
                annual_usage_kwh=inputs.annual_usage_kwh,
                roof_area_m2=inputs.roof_area_m2,
                house_type=inputs.house_type,
                roof_area_explicit=inputs.roof_area_explicit,
                import_rate=cfg["import_rate"],
                seg_rate=cfg["seg_rate"],
                self_consumption=cfg["self_consumption"] if not inputs.battery else min(cfg["self_consumption"] + 0.25, 0.85),
                annual_price_inflation=inputs.annual_price_inflation,
                regional_cost_multiplier=inputs.regional_cost_multiplier,
                battery=inputs.battery,
            )
            scenario_results[name] = calculate_10y(s_inputs, annual_yield)

        expected = scenario_results["expected"]
        summary = (
            f"I checked your house in {loc.get('country', 'UK')} ({inputs.postcode}). With around "
            f"{inputs.roof_area_m2:.0f} m2 roof, estimated system size is {expected['system_size_kwp']} kWp. "
            f"Expected 10-year generation is {expected['ten_year_generation_kwh']} kWh and expected net 10-year "
            f"profit is GBP {expected['ten_year_net_profit_gbp']}."
        )
        return {
            "annual_yield_kwh_per_kwp": round(annual_yield, 1),
            "scenario_results": scenario_results,
            "warnings": warnings,
            "assumptions": {
                "roof_usable_factor": DEFAULT_ROOF_USABLE_FACTOR,
                "max_usable_roof_m2": DEFAULT_MAX_USABLE_ROOF_M2,
                "annual_degradation": DEFAULT_ANNUAL_DEGRADATION,
                "annual_price_inflation": inputs.annual_price_inflation,
                "regional_cost_multiplier": inputs.regional_cost_multiplier,
            },
            "summary": summary,
        }

    result = calculate_10y(inputs, annual_yield)
    summary = (
        f"I checked your house in {loc.get('country', 'UK')} ({inputs.postcode}). With around "
        f"{inputs.roof_area_m2:.0f} m2 roof, you can install about {result['system_size_kwp']} kWp solar. "
        f"Estimated year-1 generation is {result['year_1_generation_kwh']} kWh and 10-year generation is "
        f"{result['ten_year_generation_kwh']} kWh. If you invest about GBP {result['total_investment_gbp']}, "
        f"you could save GBP {result['ten_year_bill_savings_gbp']} on bills and earn GBP "
        f"{result['ten_year_export_income_gbp']} from export in 10 years. Net 10-year profit is about GBP "
        f"{result['ten_year_net_profit_gbp']}."
    )
    return {
        "annual_yield_kwh_per_kwp": round(annual_yield, 1),
        "results": result,
        "warnings": warnings,
        "assumptions": {
            "roof_usable_factor": DEFAULT_ROOF_USABLE_FACTOR,
            "max_usable_roof_m2": DEFAULT_MAX_USABLE_ROOF_M2,
            "annual_degradation": DEFAULT_ANNUAL_DEGRADATION,
            "annual_price_inflation": inputs.annual_price_inflation,
            "regional_cost_multiplier": inputs.regional_cost_multiplier,
        },
        "summary": summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UK Solar Calculator")
    parser.add_argument("--postcode", required=True, help="UK postcode, e.g. CF10 1EP")
    parser.add_argument("--annual-usage-kwh", type=float, default=3500)
    parser.add_argument("--roof-area-m2", type=float, default=0)
    parser.add_argument("--house-type", choices=["flat", "terrace", "semi", "detached"], default="semi")
    parser.add_argument("--import-rate", type=float, default=DEFAULT_IMPORT_RATE_GBP_PER_KWH)
    parser.add_argument("--seg-rate", type=float, default=DEFAULT_SEG_RATE_GBP_PER_KWH)
    parser.add_argument("--self-consumption", type=float, default=0.4)
    parser.add_argument("--annual-price-inflation", type=float, default=DEFAULT_ANNUAL_PRICE_INFLATION)
    parser.add_argument("--battery", action="store_true")
    parser.add_argument("--scenario-mode", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    loc = get_location_from_postcode(args.postcode)
    lat = float(loc["latitude"])
    lon = float(loc["longitude"])
    roof_area_m2 = resolve_roof_area(args.roof_area_m2, args.house_type)
    annual_yield = get_pvgis_yield_kwh_per_kwp(lat, lon)
    inputs = SolarInputs(
        postcode=args.postcode,
        annual_usage_kwh=args.annual_usage_kwh,
        roof_area_m2=roof_area_m2,
        house_type=args.house_type,
        roof_area_explicit=bool(args.roof_area_m2 and args.roof_area_m2 > 0),
        import_rate=args.import_rate,
        seg_rate=args.seg_rate,
        self_consumption=args.self_consumption,
        annual_price_inflation=args.annual_price_inflation,
        regional_cost_multiplier=regional_cost_multiplier(loc, args.postcode),
        battery=args.battery,
    )
    core = build_output(inputs, loc, annual_yield, scenario_mode=args.scenario_mode)
    output = {
        "inputs": vars(args),
        "location": {
            "latitude": lat,
            "longitude": lon,
            "country": loc.get("country"),
            "region": loc.get("region"),
            "admin_district": loc.get("admin_district"),
            "source": loc.get("source", "postcodes.io"),
        },
        "resolved_roof_area_m2": roof_area_m2,
        **core,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
