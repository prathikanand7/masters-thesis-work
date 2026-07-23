"""
ingest_s4_to_neo4j.py — Add S4 code (StageEventBridge / StageEventListener) to Neo4j

Directly inserts the function nodes and CppCalls relationships for the two
constructed S4 source files using the same node schema as the existing graph.

After running, C2's Neo4j traversal from StageEventBridge::publishStage
will find:
  Synchronization → Logging    : stream    (via CPSLOG_ERROR in publishStage)
  Synchronization → Logging    : instance  (via CPSLogger::instance() in publishStage)
  Synchronization → Utilities  : convert   (via EnumMap in publishStage)

Usage:
    python3 ingest_s4_to_neo4j.py [--dry-run]
"""

import argparse
import os
import pathlib
from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT = pathlib.Path(__file__).parent
load_dotenv(ROOT / ".env")

# ── Node definitions ──────────────────────────────────────────────────────────
# Each entry: (node_name, symbol, type, source_file)

SRC_SYNC = "/src/Synchronization/StageEventBridge.cpp"
HDR_SYNC = "/include/cpsCore/Synchronization/StageEventBridge.h"
SRC_AGG  = "/src/Aggregation/StageEventListener.cpp"
HDR_AGG  = "/include/cpsCore/Aggregation/StageEventListener.h"

NODES = [
    # StageEventBridge declarations (header)
    (f"cpp_funcdec/{HDR_SYNC}/StageEventBridge.publishStage",  "publishStage",  "CppFunctionDeclaration", HDR_SYNC),
    (f"cpp_funcdec/{HDR_SYNC}/StageEventBridge.subscribeStage","subscribeStage","CppFunctionDeclaration", HDR_SYNC),
    # StageEventBridge definitions (source)
    (f"cpp_funcdef/{SRC_SYNC}/StageEventBridge.publishStage",  "publishStage",  "CppFunctionDefinition",  SRC_SYNC),
    (f"cpp_funcdef/{SRC_SYNC}/StageEventBridge.subscribeStage","subscribeStage","CppFunctionDefinition",  SRC_SYNC),
    # StageEventListener declarations (header)
    (f"cpp_funcdec/{HDR_AGG}/StageEventListener.attachTo",     "attachTo",      "CppFunctionDeclaration", HDR_AGG),
    (f"cpp_funcdec/{HDR_AGG}/StageEventListener.onStageEvent", "onStageEvent",  "CppFunctionDeclaration", HDR_AGG),
    # StageEventListener definitions (source)
    (f"cpp_funcdef/{SRC_AGG}/StageEventListener.attachTo",     "attachTo",      "CppFunctionDefinition",  SRC_AGG),
    (f"cpp_funcdef/{SRC_AGG}/StageEventListener.onStageEvent", "onStageEvent",  "CppFunctionDefinition",  SRC_AGG),
]

IMPLEMENTS = [
    (f"cpp_funcdef/{SRC_SYNC}/StageEventBridge.publishStage",
     f"cpp_funcdec/{HDR_SYNC}/StageEventBridge.publishStage"),
    (f"cpp_funcdef/{SRC_SYNC}/StageEventBridge.subscribeStage",
     f"cpp_funcdec/{HDR_SYNC}/StageEventBridge.subscribeStage"),
    (f"cpp_funcdef/{SRC_AGG}/StageEventListener.attachTo",
     f"cpp_funcdec/{HDR_AGG}/StageEventListener.attachTo"),
    (f"cpp_funcdef/{SRC_AGG}/StageEventListener.onStageEvent",
     f"cpp_funcdec/{HDR_AGG}/StageEventListener.onStageEvent"),
]

# CppCalls: (caller_def_name, callee_symbol, callee_component_hint)
# callee_component_hint helps us pick the right existing node
CALLS = [
    # publishStage calls: instance(), stream (via CPSLOG_ERROR), convert (via EnumMap)
    (f"cpp_funcdef/{SRC_SYNC}/StageEventBridge.publishStage", "instance", "Logging"),
    (f"cpp_funcdef/{SRC_SYNC}/StageEventBridge.publishStage", "getLogLevel", "Logging"),
    (f"cpp_funcdef/{SRC_SYNC}/StageEventBridge.publishStage", "stream",    "Logging"),
    (f"cpp_funcdef/{SRC_SYNC}/StageEventBridge.publishStage", "convert",   "Utilities"),
    # subscribeStage: no cross-component calls
    # attachTo calls subscribeStage (intra-Sync), bind → no cross-component
    # onStageEvent calls: stream (via CPSLOG_DEBUG), convert (via EnumMap)
    (f"cpp_funcdef/{SRC_AGG}/StageEventListener.onStageEvent", "stream",   "Logging"),
    (f"cpp_funcdef/{SRC_AGG}/StageEventListener.onStageEvent", "convert",  "Utilities"),
]


def run(dry_run: bool):
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
    )
    with driver.session() as s:

        # ── 1. Insert file nodes ──────────────────────────────────────────
        for fp in {n[3] for n in NODES}:
            label = "HeaderFile" if fp.endswith(".h") else "SourceFile"
            print(f"  FILE: {fp}")
            if not dry_run:
                s.run(f"MERGE (f:{label} {{name: $fp}}) SET f.type = $label",
                      fp=fp, label=label)

        # ── 2. Insert function nodes ──────────────────────────────────────
        for name, symbol, ntype, src_fp in NODES:
            print(f"  NODE [{ntype[:10]}]: {name.split('/')[-1]}")
            if not dry_run:
                s.run("""
                    MERGE (n {name: $name})
                    SET n.symbol = $symbol, n.type = $ntype, n.labelV = $ntype
                """, name=name, symbol=symbol, ntype=ntype)
                s.run("""
                    MATCH (n {name: $name}), (f {name: $fp})
                    MERGE (n)-[:Source]->(f)
                """, name=name, fp=src_fp)

        # ── 3. CppImplements (def → decl) ────────────────────────────────
        for def_name, decl_name in IMPLEMENTS:
            print(f"  IMPL: {def_name.split('/')[-1]} → {decl_name.split('/')[-1]}")
            if not dry_run:
                s.run("""
                    MATCH (d {name: $def_name}), (dc {name: $decl_name})
                    MERGE (d)-[:CppImplements]->(dc)
                """, def_name=def_name, decl_name=decl_name)

        # ── 4. CppCalls → existing nodes ─────────────────────────────────
        for caller_name, callee_sym, comp_hint in CALLS:
            if dry_run:
                print(f"  CALL: {caller_name.split('/')[-1]} → {callee_sym} ({comp_hint})")
                continue
            # Find callee in the existing graph
            result = s.run("""
                MATCH (callee)
                WHERE callee.symbol = $sym
                  AND (callee.name CONTAINS $hint OR callee.name CONTAINS $hint2)
                RETURN callee.name AS cname LIMIT 1
            """, sym=callee_sym, hint=f"/{comp_hint}/", hint2=comp_hint)
            row = result.single()
            if row:
                s.run("""
                    MATCH (caller {name: $cname}), (callee {name: $ccname})
                    MERGE (caller)-[:CppCalls]->(callee)
                """, cname=caller_name, ccname=row["cname"])
                print(f"  LINK: {caller_name.split('/')[-1]} → {callee_sym} ({comp_hint}) ✓")
            else:
                print(f"  [SKIP] callee not found: {callee_sym} in {comp_hint}")

    driver.close()
    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.dry_run)


