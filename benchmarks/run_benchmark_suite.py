import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from solar_calculator import (
    SolarInputs,
    calculate_10y,
    get_location_from_postcode,
    get_pvgis_yield_kwh_per_kwp,
    regional_cost_multiplier,
    resolve_roof_area,
)


ROOT = Path(__file__).resolve().parent
CASE_FILE = ROOT / "uk_benchmark_cases.json"
REPORT_JSON = ROOT / "benchmark_report.json"
REPORT_MD = ROOT / "benchmark_report.md"


def in_range(value: float, lo: float | None, hi: float | None) -> bool:
    if lo is not None and value < lo:
        return False
    if hi is not None and value > hi:
        return False
    return True


def status_from_checks(checks: list[bool]) -> str:
    if checks and all(checks):
        return "PASS"
    if checks and any(checks):
        return "PARTIAL"
    return "FAIL"


def run_case(case: dict) -> dict:
    expect = case.get("expect", {})
    postcode = case["postcode"]
    house_type = case.get("house_type", "semi")
    roof_m2 = resolve_roof_area(case.get("roof_area_m2"), house_type)
    usage = float(case.get("annual_usage_kwh", 3500))
    details = {"id": case["id"], "label": case["label"], "postcode": postcode}
    checks = []

    try:
        loc = get_location_from_postcode(postcode)
        lat = float(loc["latitude"])
        lon = float(loc["longitude"])
        annual_yield = get_pvgis_yield_kwh_per_kwp(lat, lon)
        inputs = SolarInputs(
            postcode=postcode,
            annual_usage_kwh=usage,
            roof_area_m2=roof_m2,
            house_type=house_type,
            roof_area_explicit=bool(case.get("roof_area_m2")),
            import_rate=0.245,
            seg_rate=0.055,
            self_consumption=0.4,
            annual_price_inflation=0.0,
            regional_cost_multiplier=regional_cost_multiplier(loc, postcode),
            battery=False,
        )
        out = calculate_10y(inputs, annual_yield)
        c1 = in_range(annual_yield, expect.get("yield_kwh_per_kwp_min"), expect.get("yield_kwh_per_kwp_max"))
        c2 = in_range(out["system_size_kwp"], expect.get("system_kwp_min"), expect.get("system_kwp_max")) if (
            "system_kwp_min" in expect or "system_kwp_max" in expect
        ) else True
        c3 = in_range(out["total_investment_gbp"], expect.get("install_cost_min"), expect.get("install_cost_max")) if (
            "install_cost_min" in expect or "install_cost_max" in expect
        ) else True
        checks.extend([c1, c2, c3])
        details.update(
            {
                "yield_kwh_per_kwp": round(annual_yield, 1),
                "system_size_kwp": out["system_size_kwp"],
                "install_cost_gbp": out["total_investment_gbp"],
                "ten_year_net_profit_gbp": out["ten_year_net_profit_gbp"],
                "checks": {"irradiance": c1, "system_size": c2, "install_cost": c3},
                "status": status_from_checks(checks),
            }
        )
    except Exception as exc:
        details["status"] = "FAIL"
        details["error"] = str(exc)

    return details


def main() -> None:
    cases = json.loads(CASE_FILE.read_text(encoding="utf-8")).get("cases", [])
    results = [run_case(c) for c in cases]
    summary = {
        "total": len(results),
        "pass": sum(1 for r in results if r["status"] == "PASS"),
        "partial": sum(1 for r in results if r["status"] == "PARTIAL"),
        "fail": sum(1 for r in results if r["status"] == "FAIL"),
    }
    payload = {"summary": summary, "results": results}
    REPORT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Solar Benchmark Report",
        "",
        f"- Total: {summary['total']}",
        f"- PASS: {summary['pass']}",
        f"- PARTIAL: {summary['partial']}",
        f"- FAIL: {summary['fail']}",
        "",
        "## Case Results",
        "",
    ]
    for r in results:
        lines.append(f"### {r['label']} ({r['postcode']}) - {r['status']}")
        if "error" in r:
            lines.append(f"- Error: `{r['error']}`")
        else:
            lines.append(f"- Irradiance: `{r['yield_kwh_per_kwp']} kWh/kWp`")
            lines.append(f"- System size: `{r['system_size_kwp']} kWp`")
            lines.append(f"- Install cost: `GBP {r['install_cost_gbp']}`")
            lines.append(f"- 10y net profit: `GBP {r['ten_year_net_profit_gbp']}`")
            lines.append(f"- Checks: `{r['checks']}`")
        lines.append("")

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Saved: {REPORT_JSON}")
    print(f"Saved: {REPORT_MD}")


if __name__ == "__main__":
    main()
