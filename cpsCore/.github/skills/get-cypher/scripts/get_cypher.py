"""This script connects to a Neo4j database, extracts its schema, and uses an LLM to convert natural language queries into Cypher queries"""

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
import os
load_dotenv()

# Load Neo4j connection details from environment variables
URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")
AUTH = (USERNAME, PASSWORD)
# Connect to Neo4j database
DRIVER = GraphDatabase.driver(URI, auth=AUTH)
# Create LLM object
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
LLM = AzureOpenAILLM(model_name="gpt-5", # or gpt-5-codex
                     azure_endpoint = AZURE_ENDPOINT
                    )


def read_user_query():
    """ Reads the user query from command-line arguments. If no query is provided, raises a RuntimeError prompting the user to provide a query via standard input or as a command-line argument.
    Returns:
        str: The user query as a string.
    """
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:])
    
    raise RuntimeError("No user query provided. Please provide a query via standard input or as a command-line argument.")


def initialize_retriever(schema: str | None = None):
    """" Initializes the Text2CypherRetriever with the Neo4j driver, LLM, and optional schema information.
    Args:
        schema (str, optional): The schema information of the Neo4j database to provide context
            for the retriever. Defaults to None.
    Returns:
        Text2CypherRetriever: An initialized Text2CypherRetriever object.
    """
    # Initialize the retriever
    retriever = Text2CypherRetriever(
        driver=DRIVER,
        llm=LLM,  # type: ignore
        neo4j_schema=schema,
    )
    return retriever



def text_2_cypher_func(user_input: str, schema: str | None = None) -> str:
    """Converts a natural language user query into a Cypher query using the Text2CypherRetriever.
    Args:
        user_input (str): The natural language query input by the user.
        schema (str, optional): The schema information of the Neo4j database to provide context
            for the retriever. Defaults to None.
    Returns:
        str: The generated Cypher query as a string.
    """
    retriever = initialize_retriever(schema)
    result = retriever.search(user_input)
    cypher = result.metadata.get("cypher")
    clean_cypher_query = re.sub(r'[`]', '', cypher)
    return clean_cypher_query


def main():
    """
    Main function to read user query, extract Neo4j schema, convert the query to Cypher, and print the Cypher query.
    """
    user_query = read_user_query()
    user_query += "\n Please only return the Cypher query without any additional text or explanation."
    schema_text = extract_schema_text(
        uri=URI,
        username=USERNAME,
        password=PASSWORD,
    )
    cypher_query = text_2_cypher_func(user_query, schema_text)
    print(cypher_query)

if __name__ == "__main__":
    main()


