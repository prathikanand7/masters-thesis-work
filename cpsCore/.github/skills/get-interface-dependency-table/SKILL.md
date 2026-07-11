````skill
---
name: get-interface-dependency-table
description: Retrieve an interface dependency table from the Neo4j code graph by executing read-only Cypher queries and write the result to a CSV file.
user-invocable: true
---

# get-interface-dependency-table

## Overview

This agent skill inspects the connected Neo4j code graph and generates an **interface dependency table** in CSV format.

The table is intended to be consumed by `draw-sysml-structural-model` and similar structural-model generators.

The skill is read-only and does not modify the database.

## When to use

- User wants a component/interface dependency table derived from the code graph.
- User wants static structural modeling input from the connected Neo4j database.
- User wants Neo4j relationships aggregated into a CSV with the columns `InterfaceName`, `Server`, and `Client`.

## Output files

- `interface_dependency_table.csv` at the repository root
- `.github/skills/get-interface-dependency-table/cypher_query.txt` containing the Cypher queries executed by this skill

## CSV format

The CSV file uses these columns:

- `InterfaceName` — the relationship type or dependency interface name
- `Server` — the provider side of the interface
- `Client` — the consumer side of the interface

If an interface has multiple servers or clients, the values are written as a semicolon-separated list in the corresponding cell.

## Semantics

- Each row represents one interface name.
- The interface name is derived from the relationship type in the graph.
- The server side is derived from the relationship target.
- The client side is derived from the relationship source.
- Duplicate component names are removed.
- Empty values are ignored.

## Execution

1. Load Neo4j connection settings from the repository `.env` file.
2. Run read-only Cypher queries against the connected Neo4j database.
3. Aggregate each relationship type into a single interface row.
4. Write the resulting table to `interface_dependency_table.csv`.
5. Write the Cypher queries used by this skill to `.github/skills/get-interface-dependency-table/cypher_query.txt`.

## Example

A row such as:

- `InterfaceName = Include`
- `Server = HeaderFile; OtherFile`
- `Client = SourceFile; HeaderFile`

means that the listed clients depend on the listed servers through the `Include` interface.
````