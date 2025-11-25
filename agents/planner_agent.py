"""
Planner Agent (Gemini 2.5 Flash – Correct SDK Version)

Uses Gemini API for grounded allocation planning.
Avoids REST endpoints (deprecated for Gemini 2.x models).
"""

import json
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini once → SDK handles the rest
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class PlannerAgent:
    """Agent responsible for creating initial KG-grounded allocation plans."""

    def __init__(self, model="gemini-2.5-flash"):
        self.model = model
        self.client = genai.GenerativeModel(model)

    def create_plan(self, crop_type, crop_yield, residue_amount, location, soil_type, kg_context=None):
        """
        Creates an initial allocation plan using Gemini.
        Returns: Python dictionary (parsed JSON)
        """

        prompt = f"""
You are the Planner Agent in an agricultural residue management system.

Your job:
Generate a scientifically accurate, policy-aware, region-specific allocation
plan for agricultural residue. Your reasoning MUST strictly follow the
Knowledge Graph Context (KG Context). NEVER hallucinate.

=========================================================
USER INPUT
=========================================================
Crop Type      : {crop_type}
Crop Yield     : {crop_yield}
Total Residue  : {residue_amount}
Soil Type      : {soil_type}
District       : {location}

=========================================================
KNOWLEDGE GRAPH CONTEXT (STRICT TRUTH SOURCE)
=========================================================
{kg_context}

ONLY use the facts above for:
- Residue ratios, nutrient values
- Soil retention capacity
- Biochar/biogas/compost limits
- Regional subsidies or bans
- Sustainability constraints
- Local facility capacity

=========================================================
TASK REQUIREMENTS
=========================================================

1. Determine feasible pathways based on KG:
   - Composting
   - Biochar
   - Biogas
   - Animal Feed / Storage

2. Use KG facts + environmental logic to justify allocations.

3. Avoid assumptions. If data missing → explicitly state it under "missing_data".

4. Output MUST be STRICT JSON in this exact structure:

{{
  "allocation": [
    {{"pathway": "Composting", "percentage": 0.0, "tons": 0.0, "reasoning": ""}},
    {{"pathway": "Biochar", "percentage": 0.0, "tons": 0.0, "reasoning": ""}},
    {{"pathway": "Biogas", "percentage": 0.0, "tons": 0.0, "reasoning": ""}},
    {{"pathway": "Feed_or_Storage", "percentage": 0.0, "tons": 0.0, "reasoning": ""}}
  ],
  "initial_notes": "",
  "missing_data": "",
  "confidence": 0.0
}}

RULES:
- Percentages MUST sum to 100.
- Tons = (percentage / 100) × {residue_amount}
- No markdown, no explanations, only JSON.
"""

        try:
            # Call Gemini SDK
            response = self.client.generate_content(prompt)

            raw_text = response.text.strip()
            return self._extract_json(raw_text)

        except Exception as e:
            print(f"[PLANNER ERROR] {e}")
            return None

    def _extract_json(self, text):
        """Extract JSON body from Gemini output safely."""

        try:
            return json.loads(text)
        except:
            # recover JSON inside surrounding text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end != -1:
                return json.loads(text[start:end])
            raise
