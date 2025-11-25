"""
Optimizer Agent (Gemini 2.5 Flash – Correct SDK Version)

Refines allocation plans created by the Planner Agent.
Ensures capacity limits, policies, soil constraints, and sustainability rules are respected.
"""

import json
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini SDK once
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class OptimizerAgent:
    """Agent responsible for optimizing residue allocation plans."""

    def __init__(self, model="gemini-2.5-flash"):
        self.model = model
        self.client = genai.GenerativeModel(model)

    def optimize_plan(self, initial_plan, crop_type, residue_amount, location, soil_type, kg_context=None):
        """
        Optimizes the initial allocation plan.
        Returns: Parsed JSON dictionary
        """

        prompt = f"""
You are the Optimizer Agent in a multi-agent agricultural residue utilization system.

Your task: Refine and optimize the Planner Agent's initial allocation plan, strictly using
the Knowledge Graph context (KG Context). Never hallucinate missing information.

=========================================================
USER INPUT
=========================================================
Crop Type      : {crop_type}
Residue Amount : {residue_amount}
Soil Type      : {soil_type}
District       : {location}

=========================================================
INITIAL PLAN (from Planner Agent)
=========================================================
{json.dumps(initial_plan, indent=2)}

=========================================================
KNOWLEDGE GRAPH CONTEXT (STRICT SOURCE OF TRUTH)
=========================================================
{kg_context}

Use ONLY the above KG facts for:
- Policy constraints
- Biochar/biogas/compost capacity
- Soil limitations
- Compost suitability
- District-level restrictions (bans, subsidies)
- Residue chemistry (if provided)

=========================================================
OPTIMIZATION RULES
=========================================================

1. Percentages MUST sum to EXACTLY 100.
2. Tons MUST = (percentage / 100) × {residue_amount}.
3. Respect all capacity limits present in the KG.
4. Avoid pathways not present in the Planner's output.
5. For missing KG values → clearly list under "missing_data".
6. Final plan must improve:
   - environmental sustainability
   - CO₂ reduction
   - soil carbon
   - regional alignment
   - feasibility

=========================================================
OUTPUT FORMAT (STRICT JSON ONLY)
=========================================================

{{
  "allocation": [
    {{"pathway": "Composting", "percentage": 0.0, "tons": 0.0}},
    {{"pathway": "Biochar", "percentage": 0.0, "tons": 0.0}},
    {{"pathway": "Biogas", "percentage": 0.0, "tons": 0.0}},
    {{"pathway": "Feed_or_Storage", "percentage": 0.0, "tons": 0.0}}
  ],
  "justification": {{
    "sustainability": "",
    "local_demand": "",
    "co2": ""
  }},
  "benefits": [],
  "risks": [],
  "notes": "",
  "detailed_explanation": "",
  "missing_data": ""
}}

Return ONLY valid JSON. No markdown.
"""

        try:
            # Call Gemini SDK
            response = self.client.generate_content(prompt)
            raw_text = response.text.strip()

            parsed = self._extract_json(raw_text)
            validated = self._validate_and_fix(parsed, residue_amount)
            return validated

        except Exception as e:
            print(f"[OPTIMIZER ERROR] {e}")
            return None

    def _extract_json(self, text):
        """Extract JSON safely from Gemini output."""
        try:
            return json.loads(text)
        except:
            start = text.find("{")
            end = text.rfind("}") + 1
            return json.loads(text[start:end])

    def _validate_and_fix(self, plan, total_residue):
        """Normalize percentages and recompute tons."""

        if not plan or "allocation" not in plan:
            return plan

        allocations = plan["allocation"]
        if not allocations:
            return plan

        total_pct = sum(a.get("percentage", 0) for a in allocations)

        # Normalize to exactly 100%
        if total_pct > 0:
            for a in allocations:
                a["percentage"] = round((a["percentage"] / total_pct) * 100, 2)
        else:
            equal = round(100 / len(allocations), 2)
            for a in allocations:
                a["percentage"] = equal

        # Recompute tons
        for a in allocations:
            a["tons"] = round((a["percentage"] / 100) * total_residue, 2)

        # Fix rounding drift
        final_sum = sum(a["percentage"] for a in allocations)
        if abs(final_sum - 100) > 0.1:
            diff = round(100 - final_sum, 2)
            allocations[-1]["percentage"] += diff
            allocations[-1]["tons"] = round((allocations[-1]["percentage"] / 100) * total_residue, 2)

        return plan
