import json
import os
import csv
from flask import Flask, render_template, request, jsonify
from google import genai

# Import your agents + KG context builder
from agents.planner_agent import PlannerAgent
from agents.optimizer_agent import OptimizerAgent
from graph.neo4j_context import get_comprehensive_context

# -------------------------------------------------------------
# INITIAL SETUP
# -------------------------------------------------------------
app = Flask(__name__)

# Initialize agents (Gemini-powered)
planner = PlannerAgent(model="gemini-2.5-flash")
optimizer = OptimizerAgent(model="gemini-2.5-flash")

# -------------------------------------------------------------
# CSV HELPERS (same as before)
# -------------------------------------------------------------
def load_csv_column(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            return [row[0] for row in reader if row]
    except:
        return []

def get_crop_options():
    return load_csv_column("graph/crop_data.csv")

def get_soil_options():
    return load_csv_column("graph/soil_data.csv")

def get_district_options():
    return load_csv_column("graph/TN_Biogas_Production_Limit.csv")


# -------------------------------------------------------------
# MAIN HOMEPAGE
# -------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    result_json = None
    error_message = None

    default_inputs = {
        "crop_type": "Rice Paddy",
        "crop_yield": 5000,
        "residue_amount": 7500,
        "location": "Thanjavur",
        "soil_type": "Alluvial",
    }

    inputs = default_inputs.copy()

    if request.method == "POST":
        inputs = {
            "crop_type": request.form.get("crop_type"),
            "crop_yield": float(request.form.get("crop_yield")),
            "residue_amount": float(request.form.get("residue_amount")),
            "location": request.form.get("location"),
            "soil_type": request.form.get("soil_type"),
        }

        result_json, error_message = generate_structured_result(inputs)

    return render_template(
        "index.html",
        result_json=result_json,
        error_message=error_message,
        inputs=inputs,
    )


# -------------------------------------------------------------
# MAIN PIPELINE (Planner → Optimizer)
# -------------------------------------------------------------
def generate_structured_result(inputs):
    try:
        crop = inputs["crop_type"]
        residue_amount = inputs["residue_amount"]
        crop_yield = inputs["crop_yield"]
        location = inputs["location"]
        soil = inputs["soil_type"]

        # ----------------------------------------
        # 1. FETCH KNOWLEDGE GRAPH CONTEXT
        # ----------------------------------------
        kg_context = get_comprehensive_context(
            crop_type=crop,
            location=location,
            soil_type=soil
        )

        # ----------------------------------------
        # 2. RUN PLANNER AGENT (Gemini)
        # ----------------------------------------
        initial_plan = planner.create_plan(
            crop_type=crop,
            crop_yield=crop_yield,
            residue_amount=residue_amount,
            location=location,
            soil_type=soil,
            kg_context=kg_context
        )

        if not initial_plan:
            return None, "Planner agent failed to generate plan."

        # ----------------------------------------
        # 3. RUN OPTIMIZER AGENT (Gemini)
        # ----------------------------------------
        optimized = optimizer.optimize_plan(
            initial_plan=initial_plan,
            crop_type=crop,
            residue_amount=residue_amount,
            location=location,
            soil_type=soil,
            kg_context=kg_context
        )

        if not optimized:
            return None, "Optimizer agent failed to refine the plan."

        # ----------------------------------------
        # 4. FINAL RESULT
        # ----------------------------------------
        return optimized, None

    except Exception as e:
        return None, f"Internal Error: {str(e)}"


# -------------------------------------------------------------
# APIs for dropdowns
# -------------------------------------------------------------
@app.route("/api/crops")
def api_crops():
    return jsonify({"crops": get_crop_options()})

@app.route("/api/soils")
def api_soils():
    return jsonify({"soils": get_soil_options()})

@app.route("/api/districts")
def api_districts():
    return jsonify({"districts": get_district_options()})


# -------------------------------------------------------------
# RUN FLASK APP
# -------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
