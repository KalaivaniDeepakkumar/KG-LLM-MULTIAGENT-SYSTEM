#!/usr/bin/env python3
"""
create_graph.py

Idempotent Neo4j import script for:
- crop_data.csv
- soil_data.csv
- policy_data.csv
- TN_Biogas_Production_Limit.csv

Requirements:
  pip install neo4j pandas python-dotenv tqdm

Usage:
  export NEO4J_URI="neo4j+s://<host>"
  export NEO4J_USER="<user>"
  export NEO4J_PASSWORD="<password>"
  python create_graph.py
"""

import os
import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Data Directory (CSV files are in the same directory as this script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CROP_CSV = os.path.join(SCRIPT_DIR, "crop_data.csv")
SOIL_CSV = os.path.join(SCRIPT_DIR, "soil_data.csv")
POLICY_CSV = os.path.join(SCRIPT_DIR, "policy_data.csv")
BIOGAS_CSV = os.path.join(SCRIPT_DIR, "TN_Biogas_Production_Limit.csv")

BATCH = 200  # batch size for driver stability

if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
    raise RuntimeError("Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in environment")

driver = GraphDatabase.driver(
    NEO4J_URI, 
    auth=(NEO4J_USER, NEO4J_PASSWORD), 
    max_connection_lifetime=600
)


# -------------------------------------------------
#   Create Constraints
# -------------------------------------------------
def create_constraints():
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Crop) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Residue) REQUIRE r.type IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Soil) REQUIRE s.type IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (reg:Region) REQUIRE reg.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Policy) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (b:BiogasLimit) REQUIRE b.id IS UNIQUE"
    ]
    with driver.session() as session:
        for c in constraints:
            print("Executing:", c)
            session.run(c)


# Utility for batching
def chunked(df, size):
    for i in range(0, len(df), size):
        yield df.iloc[i:i+size]


# -------------------------------------------------
#   Import Crop Data
# -------------------------------------------------
def import_crops(path):
    if not os.path.exists(path):
        print("[ERROR] crop_data.csv not found:", path)
        return

    # Try different encodings to handle various CSV formats
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc).fillna("")
            break
        except UnicodeDecodeError:
            continue
    if df is None:
        raise RuntimeError(f"Could not read {path} with any encoding")
    print(f"[INFO] Importing {len(df)} crop rows...")

    with driver.session() as session:
        for batch in chunked(df, BATCH):
            tx = session.begin_transaction()

            for _, row in batch.iterrows():
                crop = str(row["Crop"]).strip()
                residue_type = str(row["Residue_Type"]).strip()

                def clean_float(value):
                    try:
                        return float(value)
                    except:
                        return None

                cypher = """
                MERGE (c:Crop {name:$crop})
                MERGE (r:Residue {type:$residue})
                SET r.residue_ratio = $ratio,
                    r.nutrient_N = $n,
                    r.nutrient_P = $p,
                    r.nutrient_K = $k,
                    r.common_use = $common_use
                MERGE (c)-[:HAS_RESIDUE]->(r)
                """

                tx.run(
                    cypher,
                    crop=crop,
                    residue=residue_type,
                    ratio=clean_float(row.get("Residue_Factor")),
                    n=clean_float(row.get("N_pct")),
                    p=clean_float(row.get("P_pct")),
                    k=clean_float(row.get("K_pct")),
                    common_use=str(row.get("Common_Use", ""))
                )

            tx.commit()

    print("[SUCCESS] crop_data import complete.")


# -------------------------------------------------
#   Import Soil Data
# -------------------------------------------------
def import_soils(path):
    if not os.path.exists(path):
        print("[ERROR] soil_data.csv not found:", path)
        return

    # Try different encodings to handle various CSV formats
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc).fillna("")
            break
        except UnicodeDecodeError:
            continue
    if df is None:
        raise RuntimeError(f"Could not read {path} with any encoding")
    print(f"[INFO] Importing {len(df)} soil rows...")

    with driver.session() as session:
        for batch in chunked(df, BATCH):
            tx = session.begin_transaction()

            for _, row in batch.iterrows():
                soil = str(row["Soil_Type"]).strip()

                cypher = """
                MERGE (s:Soil {type:$soil})
                SET s.retention_capacity = $retention
                """

                tx.run(
                    cypher,
                    soil=soil,
                    retention=str(row.get("Retention_Capacity", ""))
                )

            tx.commit()

    print("[SUCCESS] soil_data import complete.")


# -------------------------------------------------
#   Import Policy Data
# -------------------------------------------------
def import_policies(path):
    if not os.path.exists(path):
        print("[ERROR] policy_data.csv not found:", path)
        return

    # Try different encodings to handle various CSV formats
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc).fillna("")
            break
        except UnicodeDecodeError:
            continue
    if df is None:
        raise RuntimeError(f"Could not read {path} with any encoding")
    print(f"[INFO] Importing {len(df)} policy rows...")

    with driver.session() as session:
        for batch in chunked(df, BATCH):
            tx = session.begin_transaction()

            for _, row in batch.iterrows():
                region = str(row["Region"]).strip()
                burning_ban = str(row.get("Burning_Ban", "")).strip()

                def clean_float(value):
                    try:
                        return float(value)
                    except:
                        return None

                # Create policy node for each region's policy
                policy_name = f"Policy_{region}"
                
                cypher = """
                MERGE (r:Region {name:$region})
                MERGE (p:Policy {name:$policy})
                SET p.burning_ban = $burning_ban,
                    p.compost_subsidy = $compost_subsidy,
                    p.biogas_subsidy = $biogas_subsidy,
                    p.co2_limit = $co2_limit
                MERGE (p)-[:APPLIES_TO]->(r)
                """

                tx.run(
                    cypher,
                    region=region,
                    policy=policy_name,
                    burning_ban=burning_ban,
                    compost_subsidy=clean_float(row.get("Compost_Subsidy_INR_per_t")),
                    biogas_subsidy=clean_float(row.get("Biogas_Subsidy_pct")),
                    co2_limit=clean_float(row.get("CO2_Limit_t_per_ha"))
                )

            tx.commit()

    print("[SUCCESS] policy_data import complete.")


# -------------------------------------------------
#   Import Biogas Limit CSV
# -------------------------------------------------
def import_biogas_limits(path):
    if not os.path.exists(path):
        print("[ERROR] TN_Biogas_Production_Limit.csv not found:", path)
        return

    # Try different encodings to handle various CSV formats
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc).fillna("")
            break
        except UnicodeDecodeError:
            continue
    if df is None:
        raise RuntimeError(f"Could not read {path} with any encoding")

    print(f"[INFO] Importing biogas limits from {len(df)} rows...")

    with driver.session() as session:
        for batch in chunked(df, BATCH):
            tx = session.begin_transaction()

            for _, row in batch.iterrows():
                district = str(row.get("District", "")).strip()
                if district == "" or district == "nan":
                    continue

                def clean_float(value):
                    try:
                        return float(value)
                    except:
                        return None

                # unique ID for node
                import hashlib
                bid = hashlib.sha1(district.encode()).hexdigest()[:12]

                cypher = """
                MERGE (r:Region {name:$district})
                MERGE (b:BiogasLimit {id:$bid})
                SET b.biogas_production_score = $score,
                    b.biogas_limit_level = $level,
                    b.compost_capacity = $compost_capacity,
                    b.biochar_max_pct = $biochar_max,
                    b.biochar_potential_score = $biochar_score,
                    b.biochar_limit_pct = $biochar_limit,
                    b.biochar_level = $biochar_level
                MERGE (r)-[:HAS_LIMIT]->(b)
                """

                tx.run(
                    cypher, 
                    district=district, 
                    bid=bid,
                    score=clean_float(row.get("Biogas_Production_Score")),
                    level=str(row.get("Biogas_Limit_Level", "")),
                    compost_capacity=clean_float(row.get("Compost_Capacity_t_per_day")),
                    biochar_max=clean_float(row.get("Biochar_Max_pct_reported")),
                    biochar_score=clean_float(row.get("Biochar_Potential_Score_0_10")),
                    biochar_limit=clean_float(row.get("Biochar_Limit_pct")),
                    biochar_level=str(row.get("Biochar_Level", ""))
                )

            tx.commit()

    print("[SUCCESS] biogas limit import complete.")


# -------------------------------------------------
#   MAIN RUNNER
# -------------------------------------------------
def run_all():
    print("\n=== Creating Constraints ===")
    create_constraints()

    print("\n=== Importing Crop Data ===")
    import_crops(CROP_CSV)

    print("\n=== Importing Soil Data ===")
    import_soils(SOIL_CSV)

    print("\n=== Importing Policy Data ===")
    import_policies(POLICY_CSV)

    print("\n=== Importing Biogas Limits ===")
    import_biogas_limits(BIOGAS_CSV)

    print("\n[SUCCESS] ALL DATA IMPORTED SUCCESSFULLY!\n")

    print("Here are some verification queries you can run in Neo4j Browser:\n")
    print("""
MATCH (c:Crop)-[:HAS_RESIDUE]->(r:Residue)
RETURN c.name, r.type, r.residue_ratio LIMIT 20;

MATCH (s:Soil) RETURN s LIMIT 20;

MATCH (p:Policy)-[:APPLIES_TO]->(r:Region)
RETURN p.name, r.name LIMIT 20;

MATCH (reg:Region)-[:HAS_LIMIT]->(b:BiogasLimit)
RETURN reg.name, b.value LIMIT 20;
""")


if __name__ == "__main__":
    run_all()
