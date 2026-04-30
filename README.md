# SolarSense

UK-first solar feasibility calculator focused on one question: **is solar worth it for this home?**

## What It Does

- Resolves postcode to coordinates (`Postcodes.io`) with NI fallback (`Nominatim`)
- Pulls location-specific yield from `PVGIS`
- Estimates rooftop system size from roof area/house type
- Models 10-year outcomes: generation, bill savings, export income, net result
- Supports conservative/expected/optimistic scenarios
- Exposes both CLI and Flask API
- Includes unit tests and benchmark suite

## Why I Built It

Most calculators either stop at technical sizing or show very basic savings. I built SolarSense as a practical, data-backed decision tool with minimal inputs and clear output.

## Core Assumptions

- 10-year horizon with 0.5% annual panel degradation
- Usable roof factor + cap to avoid oversized domestic systems
- Size-based install cost curve
- Regional cost premium logic for London/SE
- Optional electricity price inflation

## Quickstart

```bash
pip install -r requirements.txt
python solar_calculator.py --postcode "CF10 1EP" --house-type semi --scenario-mode
```

## API

```bash
python api_server.py
```

POST `http://127.0.0.1:8080/solar/calculate`

```json
{
  "postcode": "CF10 1EP",
  "house_type": "semi",
  "annual_usage_kwh": 3500,
  "scenario_mode": true
}
```

## Validation

```bash
python tests/test_core.py
python benchmarks/run_benchmark_suite.py
```

Benchmark outputs:
- `benchmarks/benchmark_report.json`
- `benchmarks/benchmark_report.md`
