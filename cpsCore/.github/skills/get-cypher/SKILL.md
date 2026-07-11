---
name: get-cypher
description: Translate the user-input into a Cypher query.
user-invocable: true
---

# get-cypher

## Overview

This agent skill translates **user-input into a Cypher query**.

The skill is read-only and does not modify the database.

## When to use

- User explicitly wants to see the Cypher query generated from their natural language input and does not require an interpretation of the results into human-readable output.
- User is not familiar with Cypher query language but wants to get the Cypher query that corresponds to their natural language query, perhaps to use it later in a different context or tool.
- User wants to quickly retrieve the Cypher query without executing it against the graph database, for example, to understand how their natural language query is being translated into Cypher.

## Inputs:

- **User Query**: A natural language question or request that the user wants to ask about the graph database. For example, "What are the header files present in the codegraph?" or "What are the C/C++ function definitions in Header File of name /include/json/allocator.h?"

## Outputs:

- **Cypher Query**: A Cypher query generated from the user input that can be executed against the Neo4j database to retrieve the desired information.

## Execution

The skill executes:

```bash
uv run .github/skills/get-cypher/scripts/get_cypher.py --user_query "Your query here"
```