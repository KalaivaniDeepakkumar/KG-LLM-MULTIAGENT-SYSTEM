"""
neo4j_context.py

Retrieves relevant context from Neo4j knowledge graph to provide factual data
to the LLM, reducing hallucinations.
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Global driver instance for connection pooling
_driver = None

def get_neo4j_driver():
    """Get Neo4j driver instance (singleton pattern)."""
    global _driver
    
    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        print("[NEO4J] Missing environment variables: NEO4J_URI, NEO4J_USER, or NEO4J_PASSWORD")
        return None
    
    if _driver is None:
        try:
            _driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD),
                max_connection_lifetime=600
            )
            # Test connection
            with _driver.session() as session:
                session.run("RETURN 1")
            print("[NEO4J] Successfully connected to Neo4j")
        except Exception as e:
            print(f"[NEO4J] Error connecting to Neo4j: {e}")
            _driver = None
            return None
    
    return _driver


def get_crop_context(crop_type):
    """Retrieve crop and residue information from the knowledge graph."""
    driver = get_neo4j_driver()
    if not driver:
        print(f"[NEO4J] No driver available for crop query: {crop_type}")
        return None
    
    try:
        with driver.session() as session:
            # Try exact match first, then case-insensitive partial match
            query = """
            MATCH (c:Crop)-[:HAS_RESIDUE]->(r:Residue)
            WHERE c.name = $crop_type 
               OR toLower(c.name) CONTAINS toLower($crop_type)
               OR toLower($crop_type) CONTAINS toLower(c.name)
            RETURN c.name as crop, 
                   r.type as residue_type,
                   r.residue_ratio as residue_ratio,
                   r.nutrient_N as n_pct,
                   r.nutrient_P as p_pct,
                   r.nutrient_K as k_pct,
                   r.common_use as common_use
            LIMIT 5
            """
            result = session.run(query, crop_type=crop_type)
            records = [record.data() for record in result]
            if records:
                print(f"[NEO4J] Found {len(records)} crop record(s) for: {crop_type}")
            else:
                print(f"[NEO4J] No crop records found for: {crop_type}")
            return records if records else None
    except Exception as e:
        print(f"[NEO4J] Error querying crop context for '{crop_type}': {e}")
        import traceback
        traceback.print_exc()
        return None


def get_soil_context(soil_type):
    """Retrieve soil information from the knowledge graph."""
    driver = get_neo4j_driver()
    if not driver:
        print(f"[NEO4J] No driver available for soil query: {soil_type}")
        return None
    
    try:
        with driver.session() as session:
            # Try exact match first, then case-insensitive partial match
            query = """
            MATCH (s:Soil)
            WHERE s.type = $soil_type 
               OR toLower(s.type) CONTAINS toLower($soil_type)
               OR toLower($soil_type) CONTAINS toLower(s.type)
            RETURN s.type as soil_type,
                   s.retention_capacity as retention_capacity
            LIMIT 1
            """
            result = session.run(query, soil_type=soil_type)
            record = result.single()
            if record:
                print(f"[NEO4J] Found soil record for: {soil_type}")
            else:
                print(f"[NEO4J] No soil record found for: {soil_type}")
            return record.data() if record else None
    except Exception as e:
        print(f"[NEO4J] Error querying soil context for '{soil_type}': {e}")
        import traceback
        traceback.print_exc()
        return None


def get_region_context(location):
    """Retrieve region-specific policy and limit information."""
    driver = get_neo4j_driver()
    if not driver:
        print(f"[NEO4J] No driver available for region query: {location}")
        return None
    
    try:
        with driver.session() as session:
            # Get policy information
            policy_query = """
            MATCH (p:Policy)-[:APPLIES_TO]->(r:Region {name: $location})
            RETURN p.burning_ban as burning_ban,
                   p.compost_subsidy as compost_subsidy,
                   p.biogas_subsidy as biogas_subsidy,
                   p.co2_limit as co2_limit
            LIMIT 1
            """
            policy_result = session.run(policy_query, location=location)
            policy_record = policy_result.single()
            
            # Get biogas/biochar limits
            limit_query = """
            MATCH (r:Region {name: $location})-[:HAS_LIMIT]->(b:BiogasLimit)
            RETURN b.biogas_production_score as biogas_score,
                   b.biogas_limit_level as biogas_level,
                   b.compost_capacity as compost_capacity,
                   b.biochar_max_pct as biochar_max_pct,
                   b.biochar_potential_score as biochar_score,
                   b.biochar_limit_pct as biochar_limit_pct,
                   b.biochar_level as biochar_level
            LIMIT 1
            """
            limit_result = session.run(limit_query, location=location)
            limit_record = limit_result.single()
            
            context = {}
            if policy_record:
                context.update(policy_record.data())
                print(f"[NEO4J] Found policy data for region: {location}")
            else:
                print(f"[NEO4J] No policy data found for region: {location}")
                
            if limit_record:
                context.update(limit_record.data())
                print(f"[NEO4J] Found limit data for region: {location}")
            else:
                print(f"[NEO4J] No limit data found for region: {location}")
            
            return context if context else None
    except Exception as e:
        print(f"[NEO4J] Error querying region context for '{location}': {e}")
        import traceback
        traceback.print_exc()
        return None


def get_comprehensive_context(crop_type, location, soil_type):
    """
    Retrieve comprehensive context from Neo4j for all provided parameters.
    Returns a formatted string that can be included in the LLM prompt.
    """
    print(f"[NEO4J] Retrieving comprehensive context for crop={crop_type}, location={location}, soil={soil_type}")
    context_parts = []
    
    # Get crop context
    crop_data = get_crop_context(crop_type)
    if crop_data:
        context_parts.append("## Crop and Residue Information:")
        for item in crop_data:
            context_parts.append(f"- Crop: {item.get('crop', 'N/A')}")
            context_parts.append(f"  - Residue Type: {item.get('residue_type', 'N/A')}")
            context_parts.append(f"  - Residue Ratio: {item.get('residue_ratio', 'N/A')}")
            context_parts.append(f"  - Nutrients (N-P-K %): {item.get('n_pct', 'N/A')}-{item.get('p_pct', 'N/A')}-{item.get('k_pct', 'N/A')}")
            context_parts.append(f"  - Common Uses: {item.get('common_use', 'N/A')}")
            context_parts.append("")
    else:
        print(f"[NEO4J] No crop data retrieved for: {crop_type}")
    
    # Get soil context
    soil_data = get_soil_context(soil_type)
    if soil_data:
        context_parts.append("## Soil Information:")
        context_parts.append(f"- Soil Type: {soil_data.get('soil_type', 'N/A')}")
        context_parts.append(f"  - Retention Capacity: {soil_data.get('retention_capacity', 'N/A')}")
        context_parts.append("")
    else:
        print(f"[NEO4J] No soil data retrieved for: {soil_type}")
    
    # Get region context
    region_data = get_region_context(location)
    if region_data:
        context_parts.append(f"## Regional Policy and Limits for {location}:")
        if region_data.get('burning_ban'):
            context_parts.append(f"- Burning Ban: {region_data.get('burning_ban', 'N/A')}")
        if region_data.get('compost_subsidy'):
            context_parts.append(f"- Compost Subsidy: {region_data.get('compost_subsidy', 'N/A')} INR per ton")
        # Only show biogas subsidy if there's actual biogas capacity/limit data
        has_biogas_capacity = (region_data.get('biogas_level') and region_data.get('biogas_level') != 'None') or \
                             (region_data.get('biogas_score') is not None and region_data.get('biogas_score') > 0)
        if region_data.get('biogas_subsidy') and has_biogas_capacity:
            context_parts.append(f"- Biogas Subsidy: {region_data.get('biogas_subsidy', 'N/A')}%")
        if region_data.get('co2_limit'):
            context_parts.append(f"- CO2 Limit: {region_data.get('co2_limit', 'N/A')} tons per hectare")
        if region_data.get('biochar_limit_pct'):
            context_parts.append(f"- Biochar Limit: {region_data.get('biochar_limit_pct', 'N/A')}%")
        if region_data.get('biogas_level') and region_data.get('biogas_level') != 'None':
            context_parts.append(f"- Biogas Production Level: {region_data.get('biogas_level', 'N/A')}")
        context_parts.append("")
        
        # Explicit section for local capacities and demand
        context_parts.append(f"## LOCAL CAPACITIES AND DEMAND FOR {location} (CRITICAL - USE THESE VALUES):")
        if region_data.get('compost_capacity'):
            capacity = region_data.get('compost_capacity')
            context_parts.append(f"- LOCAL COMPOSTING FACILITY CAPACITY: {capacity} tons per day")
            context_parts.append(f"  This means the district can process up to {capacity} tons of compostable material per day.")
            context_parts.append(f"  When allocating residue for composting, ensure the daily allocation does not exceed {capacity} tons/day.")
        else:
            context_parts.append("- LOCAL COMPOSTING FACILITY CAPACITY: Not specified in database")
        if region_data.get('biogas_level') and region_data.get('biogas_level') != 'None':
            context_parts.append(f"- LOCAL BIOGAS PRODUCTION CAPACITY: {region_data.get('biogas_level', 'N/A')} level")
        if region_data.get('biochar_limit_pct'):
            context_parts.append(f"- LOCAL BIOCHAR PRODUCTION LIMIT: Up to {region_data.get('biochar_limit_pct', 'N/A')}% of residue can be allocated to biochar")
        context_parts.append("")
    else:
        print(f"[NEO4J] No region data retrieved for: {location}")
    
    if not context_parts:
        print("[NEO4J] No context retrieved - returning None")
        return None
    
    result = "\n".join(context_parts)
    print(f"[NEO4J] Context retrieved successfully ({len(result)} characters)")
    return result

