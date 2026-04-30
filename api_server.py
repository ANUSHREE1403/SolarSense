from flask import Flask, jsonify, request
from flask_cors import CORS

from solar_calculator import (
    SolarInputs,
    build_output,
    get_location_from_postcode,
    get_pvgis_yield_kwh_per_kwp,
    regional_cost_multiplier,
    resolve_roof_area,
)

app = Flask(__name__)
CORS(app)


@app.post("/solar/calculate")
def calculate():
    payload = request.get_json(silent=True) or {}
    postcode = payload.get("postcode", "")
    if not postcode:
        return jsonify({"error": "postcode is required"}), 400

    annual_usage_kwh = float(payload.get("annual_usage_kwh", 3500))
    roof_area_m2 = payload.get("roof_area_m2")
    house_type = payload.get("house_type", "semi")
    battery = bool(payload.get("battery", False))
    scenario_mode = bool(payload.get("scenario_mode", True))
    import_rate = float(payload.get("import_rate", 0.245))
    seg_rate = float(payload.get("seg_rate", 0.055))
    self_consumption = float(payload.get("self_consumption", 0.4))
    annual_price_inflation = float(payload.get("annual_price_inflation", 0.0))
    roof_area_explicit = roof_area_m2 is not None and float(roof_area_m2) > 0

    try:
        loc = get_location_from_postcode(postcode)
        lat, lon = float(loc["latitude"]), float(loc["longitude"])
        resolved_roof = resolve_roof_area(roof_area_m2, house_type)
        annual_yield = get_pvgis_yield_kwh_per_kwp(lat, lon)
        inputs = SolarInputs(
            postcode=postcode,
            annual_usage_kwh=annual_usage_kwh,
            roof_area_m2=resolved_roof,
            house_type=house_type,
            roof_area_explicit=roof_area_explicit,
            import_rate=import_rate,
            seg_rate=seg_rate,
            self_consumption=self_consumption,
            annual_price_inflation=annual_price_inflation,
            regional_cost_multiplier=regional_cost_multiplier(loc, postcode),
            battery=battery,
        )
        core = build_output(inputs, loc, annual_yield, scenario_mode=scenario_mode)
        return (
            jsonify(
                {
                    "postcode": postcode,
                    "location": {
                        "latitude": lat,
                        "longitude": lon,
                        "country": loc.get("country"),
                        "admin_district": loc.get("admin_district"),
                        "source": loc.get("source", "postcodes.io"),
                    },
                    "resolved_roof_area_m2": resolved_roof,
                    **core,
                }
            ),
            200,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True, load_dotenv=False)
