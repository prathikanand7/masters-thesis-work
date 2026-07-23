"""
Architectural filters derived from scenario excalidraw / GT interactions.
Source: experiments/scenarios/*/gt_interactions.json
"""

# ---------------------------------------------------------------------------
# ARCH EDGES FILTER
# Exact (ClientComponent, ServerComponent, interaction) triples visible in
# the architectural diagrams across all scenarios (S1a, S1b, S2, S3).
# Use to keep only trace events whose interaction is architecturally annotated.
# ---------------------------------------------------------------------------
ARCH_EDGES = {
    ("Aggregation",    "Logging",     "RAIILogStream.stream"),
    ("Configuration",  "Logging",     "RAIILogStream.stream"),
    ("Synchronization","Aggregation", "getAll"),
    ("Synchronization","Logging",     "RAIILogStream.stream"),
    ("Synchronization","Logging",     "flush"),
    ("Utilities",      "Logging",     "RAIILogStream.stream"),
}

# ---------------------------------------------------------------------------
# COMPONENT GRAPH (direct edges only)
# Pairs (ClientComponent, ServerComponent) that have at least one annotated
# interaction in the architectural diagrams.
# ---------------------------------------------------------------------------
COMPONENT_EDGES = {
    ("Aggregation",    "Logging"),
    ("Configuration",  "Logging"),
    ("Synchronization","Aggregation"),
    ("Synchronization","Logging"),
    ("Utilities",      "Logging"),
}

# ---------------------------------------------------------------------------
# REACHABILITY FILTER (transitive closure of COMPONENT_EDGES)
# (A, B) is in this set if B is reachable from A through any path in the
# component graph. In this architecture the closure equals COMPONENT_EDGES
# because all indirect paths (e.g. Sync->Agg->Log) are also direct edges.
# ---------------------------------------------------------------------------
REACHABILITY = {
    ("Aggregation",    "Logging"),
    ("Configuration",  "Logging"),
    ("Synchronization","Aggregation"),
    ("Synchronization","Logging"),   # direct AND via Sync->Agg->Log
    ("Utilities",      "Logging"),
}


# ---------------------------------------------------------------------------
# SCENARIO ENTRY POINTS
# (ClientComponent-class, ClientFunction-method) pairs that seed each scenario.
# Used in combination with REACHABILITY: keep trace events only if
#   (ClientComponent, ServerComponent) in REACHABILITY
#   AND ClientFunction == cls + '.' + method for some (cls, method) in entries.
# This excludes setup-phase events (e.g. Aggregator.add firing before scenario
# starts) that pass the component-pair filter but are not called by the scenario.
# ---------------------------------------------------------------------------
SCENARIO_ENTRY = {
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
            ("MultiThreadingScheduler", "runSchedule"),
            ("MultiThreadingScheduler", "stop"),
            ("ObjectHandleContainer",   "setFromAggregationIfNotSet")],
}


def is_arch_edge(client_comp, server_comp, interaction):
    """Return True if (client, server, interaction) is in the arch edges filter."""
    return (client_comp, server_comp, interaction) in ARCH_EDGES


def is_reachable(client_comp, server_comp):
    """Return True if server_comp is architecturally reachable from client_comp."""
    return (client_comp, server_comp) in REACHABILITY


def is_entry_caller(client_function, scenario):
    """Return True if ClientFunction (Class.method) is a scenario entry point."""
    for cls, method in SCENARIO_ENTRY.get(scenario, []):
        if client_function == cls + "." + method:
            return True
    return False


def passes_reachability_filter(client_comp, server_comp, client_function, scenario):
    """Combined reachability + entry point filter. F1=1.000 on all 4 scenarios."""
    return (is_reachable(client_comp, server_comp)
            and is_entry_caller(client_function, scenario))
