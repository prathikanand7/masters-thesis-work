"""
derive_gt.py — Authoritative GT derivation from Renaissance DB + trace
=======================================================================
For each scenario derives two ground-truth files:

  gt_interactions.json  – unordered set of {source, target, interaction};
                          union of static (Neo4j) and dynamic (trace) edges,
                          both validated against cpsCore_packages_annotated.puml.

  gt_sequence.json      – ordered list with an evidence field;
                          dynamic edges in first-occurrence trace order,
                          followed by static-only edges (not seen at runtime).

Evidence values
  "dynamic"  — seen in trace_slice.txt at runtime
  "static"   — found by Neo4j static traversal; NOT seen at runtime
  "both"     — confirmed by both sources

Sources
  1. Renaissance Neo4j graph  (bolt, same CYPHER + entry points as C2)
  2. experiments/scenarios/<S>/full_trace.txt
Validation
  3. diagrams/cpsCore_packages_annotated.puml  (clang-uml architectural edges)
Manual check printed
  4. experiments/scenarios/<S>/source_snippet.txt  (first 20 lines, for reference)

Usage
  python derive_gt.py                   # all scenarios
  python derive_gt.py --scenario S1a   # single scenario
  python derive_gt.py --dry-run        # print report only, do not write files
"""

import argparse
import csv
import json
import pathlib
import re
import sys

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT     = pathlib.Path(__file__).parent.parent.parent  # cpsCore/
SCEN_DIR = pathlib.Path(__file__).parent                # experiments/scenarios/
PUML     = ROOT / "architectural_diagrams" / "cpsCore_packages_annotated.puml"

# ── Scenario configuration (mirrored from H1 C2 condition) ─────────────────
SCENARIOS = ["S1a", "S1b", "S2", "S3", "S4"]

SCENARIO_COMPONENTS: dict[str, set[str]] = {
    "S1a": {"Synchronization", "Aggregation", "Logging"},
    "S1b": {"Synchronization", "Aggregation", "Logging"},
    "S2":  {"Configuration",   "Logging"},
    "S3":  {"Synchronization", "Aggregation", "Utilities", "Logging"},
    "S4":  {"Synchronization", "Aggregation", "Logging"},
}

# Entry-point functions for Neo4j traversal (same as C2 run_c2_static_only.py)
SCENARIO_ENTRY: dict[str, list[tuple[str, str]]] = {
    "S1a": [("SynchronizedRunner",      "runSynchronized"),
            ("SynchronizedRunnerMaster", "runStage")],
    "S1b": [("SynchronizedRunner",      "runSynchronized"),
            ("SynchronizedRunnerMaster", "runStage")],
    "S2":  [("PropertyMapper",          "addOptional"),
            ("PropertyMapper",          "add")],
    "S3":  [("AggregatableRunner",      "runAllStages"),
            ("AggregatableRunner",      "notifyAggregationOnUpdate"),
            ("MultiThreadingScheduler", "schedule"),
            ("MultiThreadingScheduler", "run"),
            # runSchedule/stop are called internally via std::function/thread — Neo4j
            # misses them due to indirect dispatch, so seed them explicitly.
            ("MultiThreadingScheduler", "runSchedule"),
            ("MultiThreadingScheduler", "stop"),
            # ObjectHandleContainer called during aggregation update cycle
            ("ObjectHandleContainer",   "setFromAggregationIfNotSet"),
           ],
    "S4":  [("StageEventBridge",        "publishStage"),
            ("StageEventListener",      "attachTo")],
}

# Implementation-detail calls to drop even if found by Neo4j
SCENARIO_EXCLUDE: dict[str, set[str]] = {
    "S4": {"getLogLevel"},
}

# Bare method names excluded globally from all scenarios.
# These are implementation-detail calls that are statically reachable but not
# meaningful cross-component interactions (e.g. singleton accessor patterns).
GLOBAL_EXCLUDE_BARE: set[str] = {"instance"}

# Static-only edges to INCLUDE in GT despite having no runtime trace event.
# Default: static-only edges are NOT included (they may be on unexercised code paths).
# Add here ONLY when confirmed as a genuinely exercised-but-suppressed interaction.
# Format: scenario → set of bare method names to include from static-only edges.
STATIC_ONLY_INCLUDE: dict[str, set[str]] = {
    # S4: stream (Sync→Log via CPSLOG_ERROR in publishStage) is confirmed by both
    # static (Neo4j traverses publishStage→RAIILogStream.stream) and dynamic
    # (trace_slice.txt records it). This entry is therefore redundant — stream would
    # appear in GT via the dynamic trace regardless — but is kept as an explicit
    # whitelist guard. Note: LogLevelScope(NONE) in the test suppresses log OUTPUT
    # but does NOT prevent RAIILogStream.stream from firing; the constructor is
    # evaluated as a C++ temporary in the CPSLOG_ERROR argument expression.
    "S4": {"stream"},
}

# Qualified interaction name for static-only edges (Neo4j returns bare method names).
# Use this to restore the Class.method form when it's known from source reading.
# Format: scenario → {bare_name: qualified_name}
STATIC_ONLY_QUALIFIED: dict[str, dict[str, str]] = {
    "S4": {"stream": "RAIILogStream.stream"},
}

# Cypher — same as C2
CYPHER = """
MATCH (entry {type:'CppFunctionDefinition'})
WHERE entry.symbol = $method AND entry.name CONTAINS $cls
WITH entry LIMIT 1
MATCH (entry)-[:Source]->(ef)
WITH entry, ef
CALL {
  WITH entry, ef
  MATCH (entry)-[:CppCalls]->(decl)<-[:CppImplements]-(step_def)-[:CppCalls]->(callee)
  MATCH (callee)-[:Source]->(cf)
  WHERE ef.name <> cf.name
  RETURN callee.symbol AS sym, cf.name AS callee_file
  UNION
  WITH entry, ef
  MATCH (entry)-[:CppCalls]->(callee)
  MATCH (callee)-[:Source]->(cf)
  WHERE ef.name <> cf.name
  RETURN callee.symbol AS sym, cf.name AS callee_file
}
RETURN DISTINCT sym, callee_file, ef.name AS entry_file
"""

# Cypher — all functions reachable from an entry point via CppCalls (any depth up to 8).
# Used to filter trace events: only keep events whose ClientFunction is reachable from
# SCENARIO_ENTRY, excluding test-setup boilerplate that fires before/after the scenario.
CYPHER_REACHABLE = """
MATCH (entry {type:'CppFunctionDefinition'})
WHERE entry.symbol = $method AND entry.name CONTAINS $cls
WITH entry LIMIT 1
MATCH (entry)-[:CppCalls*0..8]->(callee)
RETURN DISTINCT callee.symbol AS sym, callee.name AS callee_path
"""

# ── Component path detection ────────────────────────────────────────────────
_PATH_COMPONENT_MAP = [
    (re.compile(r"/(src|include/cpsCore)/Aggregation/",    re.I), "Aggregation"),
    (re.compile(r"/(src|include/cpsCore)/Configuration/",  re.I), "Configuration"),
    (re.compile(r"/(src|include/cpsCore)/Framework/",      re.I), "Framework"),
    (re.compile(r"/(src|include/cpsCore)/Logging/",        re.I), "Logging"),
    (re.compile(r"/(src|include/cpsCore)/Synchronization/",re.I), "Synchronization"),
    (re.compile(r"/(src|include/cpsCore)/Utilities/",      re.I), "Utilities"),
]

def path_to_component(path: str) -> str | None:
    for pattern, name in _PATH_COMPONENT_MAP:
        if pattern.search(path):
            return name
    return None

# ── 1. Load valid architectural edges from annotated puml ───────────────────
def load_puml_edges(puml_path: pathlib.Path) -> set[tuple[str, str]]:
    """Return set of (src_lower, tgt_lower) confirmed by clang-uml."""
    edges: set[tuple[str, str]] = set()
    if not puml_path.exists():
        print(f"  [WARN] Annotated puml not found: {puml_path}")
        return edges
    arrow_re = re.compile(
        r"^\s*(\w+)\s+\.\.>\s+(\w+)",
        re.MULTILINE
    )
    for src, tgt in arrow_re.findall(puml_path.read_text()):
        edges.add((src.lower(), tgt.lower()))
    return edges

# ── 2. Query Neo4j for static edges ────────────────────────────────────────
def load_static_edges(scenario: str) -> set[tuple[str, str, str]]:
    """Return set of (src, tgt, interaction) from Renaissance Neo4j graph."""
    try:
        from neo4j import GraphDatabase
        from dotenv import load_dotenv
        import os
    except ImportError as e:
        print(f"  [SKIP Neo4j] Missing dependency: {e}")
        return set()

    load_dotenv(ROOT / ".env")
    uri      = os.environ.get("NEO4J_URI",     "bolt://localhost:7687")
    user     = os.environ.get("NEO4J_USER",    "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")

    allowed  = SCENARIO_COMPONENTS[scenario]
    exclude  = SCENARIO_EXCLUDE.get(scenario, set())
    entries  = SCENARIO_ENTRY.get(scenario, [])
    elements: set[tuple[str, str, str]] = set()

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            for cls, method in entries:
                for rec in session.run(CYPHER, cls=cls, method=method):
                    src = path_to_component(rec["entry_file"] or "")
                    tgt = path_to_component(rec["callee_file"] or "")
                    if not src or not tgt or src == tgt:
                        continue
                    if src not in allowed or tgt not in allowed:
                        continue
                    intr = (rec["sym"] or "").strip()
                    b = bare_method(intr)
                    if intr and intr not in exclude and b not in GLOBAL_EXCLUDE_BARE:
                        elements.add((src, tgt, intr))
    finally:
        driver.close()
    return elements

# ── 2b. Query Neo4j for reachable functions (scenario-scope filter) ────────
def load_reachable_functions(scenario: str) -> set[tuple[str, str]]:
    """Return set of (symbol, class_hint_or_path) for all functions reachable from entry points.

    The set is seeded with the entry points themselves (always reachable), then extended
    by Neo4j forward CppCalls traversal (up to 8 hops). The class_hint_or_path value is
    either the class name string (for directly seeded entry points) or the file path
    (for Neo4j-discovered callees).

    Returns empty set only if Neo4j is unavailable AND no entry points defined.
    Falls back to keeping all events if Neo4j is unavailable.
    """
    entries = SCENARIO_ENTRY.get(scenario, [])
    # Seed: entry points are always reachable (cls as the hint)
    reachable: set[tuple[str, str]] = {(method, cls) for cls, method in entries}

    try:
        from neo4j import GraphDatabase
        from dotenv import load_dotenv
        import os
    except ImportError:
        return reachable  # return at least the entry points

    load_dotenv(ROOT / ".env")
    uri      = os.environ.get("NEO4J_URI",     "bolt://localhost:7687")
    user     = os.environ.get("NEO4J_USER",    "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            for cls, method in entries:
                for rec in session.run(CYPHER_REACHABLE, cls=cls, method=method):
                    sym  = (rec["sym"]         or "").strip()
                    path = (rec["callee_path"] or "").strip()
                    if sym:
                        reachable.add((sym, path))
    finally:
        driver.close()
    return reachable


def is_client_reachable(client_fn: str, reachable: set[tuple[str, str]]) -> bool:
    """Return True if ClientFunction (ClassName.methodName) is reachable from entry points.

    Matches by: symbol == method AND (class_name in path OR class_name == hint).
    Falls back to True if reachable set is empty.
    """
    if not reachable:
        return True  # no filter — keep all events
    if not client_fn or "." not in client_fn:
        return True  # unparseable — keep
    parts = client_fn.rsplit(".", 1)
    cls, method = parts[0], parts[1]
    return any(sym == method and (cls in (hint or "") or cls == hint)
               for sym, hint in reachable)


# ── 3. Parse trace_slice.txt for dynamic edges (in execution order) ─────────
def load_dynamic_edges_ordered(scenario: str,
                                reachable: set[tuple[str, str]] | None = None
                                ) -> list[tuple[str, str, str]]:
    """Return ALL (src, tgt, interaction) rows from trace in execution order (no dedup).

    If reachable is provided, only keeps events whose ClientFunction is reachable from
    SCENARIO_ENTRY — i.e., triggered by scenario logic, not test-setup boilerplate.
    """
    path = SCEN_DIR / scenario / "full_trace.txt"
    if not path.exists():
        return []
    allowed  = SCENARIO_COMPONENTS[scenario]
    ordered: list[tuple[str, str, str]] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            src       = (row.get("ClientComponent") or "").strip()
            tgt       = (row.get("ServerComponent")  or "").strip()
            intr      = (row.get("EventName")        or "").strip()
            client_fn = (row.get("ClientFunction")   or "").strip()
            if not src or not tgt or not intr or src == tgt:
                continue
            if src not in allowed or tgt not in allowed:
                continue
            if reachable is not None and not is_client_reachable(client_fn, reachable):
                print(f"      [SETUP] excluded {src}→{tgt}:{intr} (caller={client_fn})")
                continue
            ordered.append((src, tgt, intr))
    return ordered

# ── 4. Validate edges against puml ─────────────────────────────────────────
def is_valid(src: str, tgt: str, puml_edges: set[tuple[str, str]]) -> bool:
    return (src.lower(), tgt.lower()) in puml_edges


def bare_method(interaction: str) -> str:
    """Normalise to bare method name: 'Aggregator.getAll' → 'getall', 'flush' → 'flush'."""
    return interaction.split(".")[-1].lower()

# ── 5. Print source snippet header for manual reference ────────────────────
def print_snippet_header(scenario: str) -> None:
    path = SCEN_DIR / scenario / "source_snippet.txt"
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    print(f"\n  [Source snippet — first 20 lines of {scenario}/source_snippet.txt]")
    for line in lines[:20]:
        print(f"    {line}")

# ── 6. Derive and write GT for one scenario ─────────────────────────────────
def process_scenario(scenario: str, puml_edges: set[tuple[str, str]],
                     dry_run: bool) -> None:
    print(f"\n{'='*60}")
    print(f"  Scenario: {scenario}")
    print(f"{'='*60}")

    # --- Static edges from Neo4j ---
    print(f"\n  → Querying Renaissance Neo4j ...")
    static_raw = load_static_edges(scenario)
    static_valid = {e for e in static_raw if is_valid(e[0], e[1], puml_edges)}
    static_invalid = static_raw - static_valid
    print(f"    Neo4j found {len(static_raw)} edges, {len(static_valid)} valid (puml), "
          f"{len(static_invalid)} rejected")
    if static_invalid:
        for e in sorted(static_invalid):
            print(f"      [REJECTED static]  {e[0]} → {e[1]} : {e[2]}")

    # --- Reachable function set (for setup-event filtering) ---
    print(f"\n  → Querying Neo4j for reachable functions (scenario-scope filter) ...")
    reachable = load_reachable_functions(scenario)
    print(f"    {len(reachable)} functions reachable from entry points")

    # --- Dynamic edges from trace (scenario-scoped: exclude setup boilerplate) ---
    print(f"\n  → Parsing trace_slice.txt (filtering to scenario-logic callers) ...")
    dynamic_ordered = load_dynamic_edges_ordered(scenario, reachable)
    dynamic_valid   = [e for e in dynamic_ordered if is_valid(e[0], e[1], puml_edges)]
    dynamic_keys    = {(s, t, bare_method(i)) for s, t, i in dynamic_valid}  # unique types
    rejected_dyn    = [e for e in dynamic_ordered if not is_valid(e[0], e[1], puml_edges)]
    print(f"    Trace: {len(dynamic_ordered)} events, {len(dynamic_valid)} valid, "
          f"{len(rejected_dyn)} rejected ({len(dynamic_keys)} unique types)")
    if rejected_dyn:
        for e in rejected_dyn:
            print(f"      [REJECTED dynamic] {e[0]} → {e[1]} : {e[2]}")

    # --- Cross-check (normalise by bare method name for comparison) ---
    # Neo4j returns bare names ('getAll'); trace returns qualified names ('Aggregator.getAll').
    # We match on (src, tgt, bare_method) and prefer the trace's qualified form as canonical.

    # Build lookup: (src, tgt, bare) → canonical interaction string
    # Trace takes precedence (qualified form is more informative).
    # Static-only edges fall back to bare Neo4j name unless overridden by STATIC_ONLY_QUALIFIED.
    qualified_overrides = STATIC_ONLY_QUALIFIED.get(scenario, {})
    canonical: dict[tuple[str, str, str], str] = {}
    for s, t, i in static_valid:
        key = (s, t, bare_method(i))
        canonical.setdefault(key, qualified_overrides.get(key[2], i))
    for s, t, i in dynamic_valid:
        key = (s, t, bare_method(i))
        canonical[key] = i  # overwrite with trace's qualified form

    # Normalised key sets
    static_keys  = {(s, t, bare_method(i)) for s, t, i in static_valid}

    in_both_keys     = static_keys & dynamic_keys
    static_only_keys = static_keys - dynamic_keys
    dynamic_only_keys= dynamic_keys - static_keys

    print(f"\n  Cross-check (normalised to bare method name):")
    print(f"    Both (static ∩ dynamic):")
    for key in sorted(in_both_keys):
        print(f"      {key[0]} → {key[1]} : {canonical[key]}  [bare={key[2]}]")
    print(f"    Static only (in Neo4j, NOT in trace — suppressed at runtime):")
    for key in sorted(static_only_keys):
        print(f"      {key[0]} → {key[1]} : {canonical[key]}  [bare={key[2]}]")
    print(f"    Dynamic only (in trace, NOT in Neo4j — runtime-only e.g. signals):")
    for key in sorted(dynamic_only_keys):
        print(f"      {key[0]} → {key[1]} : {canonical[key]}  [bare={key[2]}]")

    # --- Snippet header for manual verification ---
    print_snippet_header(scenario)

    # gt_interactions.json: union of dynamic + whitelisted static-only edges
    allowed_static_bare = STATIC_ONLY_INCLUDE.get(scenario, set())
    included_static_keys = {k for k in static_only_keys if k[2] in allowed_static_bare}
    excluded_static_keys = static_only_keys - included_static_keys

    if excluded_static_keys:
        print(f"\n  Static-only edges EXCLUDED (unexercised code paths or not whitelisted):")
        for key in sorted(excluded_static_keys):
            print(f"    {key[0]} → {key[1]} : {canonical[key]}  [bare={key[2]}]")
    if included_static_keys:
        print(f"\n  Static-only edges INCLUDED (whitelisted in STATIC_ONLY_INCLUDE):")
        for key in sorted(included_static_keys):
            print(f"    {key[0]} → {key[1]} : {canonical[key]}  [bare={key[2]}]")

    all_keys = dynamic_keys | in_both_keys | included_static_keys
    gt_interactions = sorted(
        [{"source": k[0], "target": k[1], "interaction": canonical[k]} for k in all_keys],
        key=lambda d: (d["source"], d["target"], d["interaction"])
    )

    # gt_sequence.json: ALL trace events in execution order, with position index.
    # No deduplication — if a call fires 6 times, it appears 6 times.
    def ev_label(key: tuple[str, str, str]) -> str:
        in_s = key in static_keys
        in_d = key in dynamic_keys
        if in_s and in_d:
            return "both"
        return "static" if in_s else "dynamic"

    gt_sequence: list[dict] = []
    for pos, (s, t, i) in enumerate(dynamic_valid):
        key = (s, t, bare_method(i))
        gt_sequence.append({
            "order": pos,
            "source": s, "target": t, "interaction": i,
            "evidence": ev_label(key)
        })
    # Static-only edges are NOT in gt_sequence — they were not observed at runtime.

    # --- Print summary ---
    print(f"\n  GT interactions ({len(gt_interactions)} elements):")
    for d in gt_interactions:
        print(f"    {d['source']} → {d['target']} : {d['interaction']}")
    print(f"\n  GT sequence ({len(gt_sequence)} elements, ordered):")
    for i, d in enumerate(gt_sequence):
        print(f"    [{i}] {d['source']} → {d['target']} : {d['interaction']}  [{d['evidence']}]")

    # --- Write files ---
    if not dry_run:
        out_intr = SCEN_DIR / scenario / "gt_interactions.json"
        out_seq  = SCEN_DIR / scenario / "gt_sequence.json"
        out_intr.write_text(json.dumps(gt_interactions, indent=2))
        out_seq.write_text(json.dumps(gt_sequence, indent=2))
        print(f"\n  Written: {out_intr.relative_to(ROOT)}")
        print(f"  Written: {out_seq.relative_to(ROOT)}")
    else:
        print("\n  [dry-run] Files not written.")

# ── Main ────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS,
                        help="Process a single scenario (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print report only; do not write GT files")
    args = parser.parse_args()

    print(f"\nLoading architectural edges from {PUML.name} ...")
    puml_edges = load_puml_edges(PUML)
    print(f"  Found {len(puml_edges)} directed component edges in annotated puml")

    targets = [args.scenario] if args.scenario else SCENARIOS
    for scenario in targets:
        process_scenario(scenario, puml_edges, args.dry_run)

    print(f"\n{'='*60}")
    print("Done." if not args.dry_run else "Dry run complete — no files written.")


if __name__ == "__main__":
    main()
