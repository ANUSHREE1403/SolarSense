# SolarSense

A simple, data-driven tool to estimate whether installing solar is financially worth it for a home.

Currently supports UK postcodes only; support for more countries is coming soon.

## What It Does

- Takes minimal inputs (postcode, house type, usage, optional roof area)
- Resolves location and fetches solar yield from `PVGIS`
- Converts roof assumptions into estimated system size
- Models 10-year financial outcomes including generation, savings, export income, and net return
- Generates conservative / expected / optimistic scenarios
- Exposes both CLI and Flask API for easy integration
- Validates model quality with unit tests and benchmark cases

## Why I Built It

Most solar calculators either focus only on technical sizing or provide basic savings estimates. They do not clearly answer whether solar is actually worth the investment.

I built SolarSense to solve this gap by combining location-based data, realistic assumptions, and financial modeling into a simple decision tool with minimal inputs and clear outputs.

## Example Output

```text
System size: 5.85 kWp
Annual generation: ~5,600 kWh
10-year net result: +GBP 2,300
Payback period: ~8 years
```

## Core Assumptions

- 10-year horizon with 0.5% annual panel degradation
- Usable roof factor + cap to avoid oversized domestic systems
- Size-based install cost curve
- Regional install-cost multiplier logic
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
