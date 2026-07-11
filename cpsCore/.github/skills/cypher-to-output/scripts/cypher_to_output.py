"""This script connects to a Neo4j database, executes a Cypher query, and uses an LLM to convert the output back into human-understandable language."""

from utils import extract_schema_text
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from neo4j import GraphDatabase
from neo4j_graphrag.llm import AzureOpenAILLM
from neo4j_graphrag.retrievers import Text2CypherRetriever
from neo4j_graphrag.generation import GraphRAG
import json
from openai import AzureOpenAI
import re
from dotenv import load_dotenv
import sys
import argparse
import os
load_dotenv()

# Load Neo4j connection details from environment variables
URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")
AUTH = (USERNAME, PASSWORD)

def execute_cypher_query(cypher_query: str):
    """Executes a Cypher query against the Neo4j database.
    Args:
        cypher_query (str): The Cypher query to execute.
    Returns:
        list: The records returned by the query.
    """
    # Connect to Neo4j database
    DRIVER = GraphDatabase.driver(URI, auth=AUTH)
    records, _, _ = DRIVER.execute_query(cypher_query)
    DRIVER.close()
    return records


def main():
    """
    Main function to read user query, extract Neo4j schema, execute the Cypher query, and convert the output back to human-understandable language.
    """
    # read the user query from the file, "cypher_query.txt"
    with open("cypher_query.txt", "r") as f:
        cypher_query = f.read()
    # execute the Cypher query against the Neo4j database
    query_output = execute_cypher_query(cypher_query)
    print(query_output)


if __name__ == "__main__":
    main()
