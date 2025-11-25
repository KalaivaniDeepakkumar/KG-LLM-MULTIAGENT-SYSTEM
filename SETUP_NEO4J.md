# Neo4j Knowledge Graph Setup Guide

This guide will help you set up a Neo4j Aura knowledge graph and integrate it with the LLM API to reduce hallucinations.

## Prerequisites

1. A Neo4j Aura account (free tier available at https://neo4j.com/cloud/aura/)
2. Python 3.8+ installed
3. All required dependencies installed

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Set Up Neo4j Aura

1. Go to https://neo4j.com/cloud/aura/ and create a free account
2. Create a new Aura instance (choose the free tier)
3. Once created, you'll receive:
   - **NEO4J_URI**: Something like `neo4j+s://xxxxx.databases.neo4j.io`
   - **NEO4J_USER**: Usually `neo4j`
   - **NEO4J_PASSWORD**: The password you set during instance creation

## Step 3: Configure Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Neo4j credentials:
   ```
   NEO4J_URI=neo4j+s://your-instance-id.databases.neo4j.io
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password_here
   ```

   Also add your OpenRouter API key:
   ```
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```

## Step 4: Import Data into Neo4j

Run the graph creation script to import all CSV data into Neo4j:

```bash
cd graph
python create_graph.py
```

This will:
- Create constraints for data integrity
- Import crop and residue data from `crop_data.csv`
- Import soil data from `soil_data.csv`
- Import policy data from `policy_data.csv`
- Import biogas/biochar limits from `TN_Biogas_Production_Limit.csv`

You should see output like:
```
=== Creating Constraints ===
=== Importing Crop Data ===
📥 Importing 270 crop rows...
✔ crop_data import complete.
...
🎉 ALL DATA IMPORTED SUCCESSFULLY!
```

## Step 5: Verify the Import

You can verify the data was imported correctly by:

1. Opening the Neo4j Browser in your Aura dashboard
2. Running these queries:

```cypher
// Check crop data
MATCH (c:Crop)-[:HAS_RESIDUE]->(r:Residue)
RETURN c.name, r.type, r.residue_ratio LIMIT 10;

// Check soil data
MATCH (s:Soil)
RETURN s.type, s.retention_capacity LIMIT 10;

// Check policy data
MATCH (p:Policy)-[:APPLIES_TO]->(r:Region)
RETURN p.name, r.name, p.compost_subsidy LIMIT 10;

// Check biogas limits
MATCH (r:Region)-[:HAS_LIMIT]->(b:BiogasLimit)
RETURN r.name, b.compost_capacity, b.biochar_limit_pct LIMIT 10;
```

## Step 6: Run the Application

Now you can run the Flask application:

```bash
python llm_api.py
```

The application will automatically:
- Connect to Neo4j when processing requests
- Retrieve relevant context from the knowledge graph
- Include this context in LLM prompts to reduce hallucinations
- Fall back gracefully if Neo4j is unavailable

## How It Works

1. **User submits form** with crop type, location, soil type, etc.
2. **System queries Neo4j** to retrieve:
   - Crop-specific residue data (ratios, nutrients, common uses)
   - Soil characteristics (retention capacity)
   - Regional policies (subsidies, CO2 limits, burning bans)
   - Regional capacities (compost capacity, biogas limits, biochar limits)
3. **Context is formatted** and included in the LLM prompt
4. **LLM generates response** using factual data from the knowledge graph
5. **Hallucinations are reduced** because the LLM has access to real data

## Troubleshooting

### Connection Issues

If you see "Error connecting to Neo4j":
- Verify your `.env` file has correct credentials
- Check that your Neo4j Aura instance is running
- Ensure your IP is whitelisted (Aura allows all IPs by default)

### Import Errors

If the import fails:
- Check that all CSV files are in the `graph/` directory
- Verify CSV column names match what the script expects
- Check Neo4j Aura instance has enough storage (free tier: 0.5 GB)

### Context Not Appearing

If context isn't being retrieved:
- Check the application logs for Neo4j query errors
- Verify data was imported correctly using the verification queries
- Ensure crop/soil/location names match exactly (case-sensitive)

## Graph Schema

The knowledge graph has the following structure:

```
(Crop)-[:HAS_RESIDUE]->(Residue)
(Soil)
(Region)-[:HAS_LIMIT]->(BiogasLimit)
(Policy)-[:APPLIES_TO]->(Region)
```

This allows efficient queries to retrieve all relevant context for a given crop, location, and soil type combination.

