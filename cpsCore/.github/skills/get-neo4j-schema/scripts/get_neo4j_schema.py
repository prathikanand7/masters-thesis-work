"""This script is designed to connect to a Neo4j database, extract its schema, and print the schema information to the console."""

import os
from utils import extract_schema_text
from dotenv import load_dotenv
load_dotenv()

def main():
    """
    This script connects to a Neo4j database using credentials from environment variables, extracts the database schema using the `extract_schema_text` function, and prints the schema text to the console. The schema text provides an overview of the structure of the graph database, including node labels, relationship types, and properties.
    """
    URI = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    schema_text = extract_schema_text(
        uri=URI,
        username=username,
        password=password,
    )
    print(schema_text)


if __name__ == "__main__":
    main()