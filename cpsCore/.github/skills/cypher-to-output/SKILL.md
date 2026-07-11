---
name: cypher-to-output
description: Runs a cypher query obtained as output from the "text-to-cypher" skill based on the schema which is the output of the "get-neo4j-schema" skill and converts the results into human-understandable language.
user-invocable: true
---

# cypher-to-output

## Overview

This agent skill runs a cypher query obtained as output from the "text-to-cypher" skill based on the schema which is the output of the "get-neo4j-schema" skill and converts the results into human-understandable language.

The skill is read-only and does not modify the database.

## When to use

- User asks a question that can be answered by running a Cypher query against the graph database and wants the results to be presented in a human-understandable format.
- User needs information from the graph database that requires running a Cypher query and prefers to have the results translated into natural language for easier comprehension.
- User has a Cypher query that they want to run against the graph database and wants the results to be presented in a human-understandable format.


## Execution

i. The skill needs to first execute the skill "get-neo4j-schema" (if not executed already) to retrieve the graph schema, which includes node labels, relationship types, and their properties. This information is crucial for constructing an accurate Cypher query that aligns with the structure of the graph database.

ii. The skill needs to first execute the skill "text-to-cypher" (if not executed already) to retrieve the Cypher query based on the user's natural language query and the graph schema. This information is crucial for constructing an accurate Cypher query that aligns with the structure of the graph database.

iii. The skill executes the following script to run the Cypher query obtained in Step ii against the graph database:

```bash
uv run .github/skills/cypher-to-output/scripts/cypher_to_output.py
```

iv. Combine the schema of the graph database obtained in Step i (from `graph_schema.txt`) and the output of the Cypher query executed in Step iii to generate a human-understandable response.

v. Structure the response in a tabular format if the output contains multiple records or a list of items, ensuring that the information is presented clearly and concisely for easy comprehension by the user.