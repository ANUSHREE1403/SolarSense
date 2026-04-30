import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from solar_calculator import SolarInputs, calculate_10y, estimate_system_size_kwp, resolve_roof_area


class TestSolarCore(unittest.TestCase):
    def test_resolve_roof_area_defaults(self):
        self.assertEqual(resolve_roof_area(None, "flat"), 18.0)
        self.assertEqual(resolve_roof_area(None, "terrace"), 35.0)
        self.assertEqual(resolve_roof_area(None, "semi"), 45.0)
        self.assertEqual(resolve_roof_area(None, "detached"), 52.0)

    def test_resolve_roof_area_override(self):
        self.assertEqual(resolve_roof_area(52.5, "flat"), 52.5)

    def test_estimate_system_size_with_cap(self):
        self.assertAlmostEqual(estimate_system_size_kwp(50), 6.5, places=3)
        self.assertAlmostEqual(estimate_system_size_kwp(200), 7.0, places=3)

    def test_calculate_10y_generation(self):
        inputs = SolarInputs(
            postcode="CF10 1EP",
            annual_usage_kwh=3500,
            roof_area_m2=50,
            house_type="semi",
            roof_area_explicit=True,
            import_rate=0.245,
            seg_rate=0.055,
            self_consumption=0.4,
            annual_price_inflation=0.0,
            regional_cost_multiplier=1.0,
            battery=False,
        )
        out = calculate_10y(inputs, 969.0)
        self.assertGreater(out["year_1_generation_kwh"], 0)
        self.assertGreater(out["ten_year_generation_kwh"], out["year_1_generation_kwh"])


if __name__ == "__main__":
    unittest.main()
