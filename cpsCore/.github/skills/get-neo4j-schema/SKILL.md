---
name: get-neo4j-schema
description: Retrieve the Neo4j database schema by executing a read-only Python script and display it in a tabular format.
user-invocable: true
---

# get_neo4j_schema

## Overview

This agent skill retrieves the **Neo4j database schema of a code graph** (node labels, relationship types, and their properties) by executing a Python script and returning the output of the script in a tabular format.

The skill is read-only and does not modify the database.

## When to use

- User asks for the schema or structure of the code graph
- User asks which node labels or relationship types exist
- Schema information is needed to translate user queries into Cypher queries
- The agent needs an authoritative view of the graph model

## Execution

1. The skill executes the following script to retrieve the Neo4j database schema of the code graph:

```bash
uv run .github/skills/get-neo4j-schema/scripts/get_neo4j_schema.py | Out-File -FilePath graph_schema.txt -Encoding utf8
```

2. Always display the output of the script executed in the previous step in a tabular format showing node labels, relationship types, and their properties.

3. Write the output to a file named, `graph_schema.txt`.