#!/usr/bin/env python3
"""
Generate a valid SysML v2 sequence model from sequence_dependency_table.csv.
Maps file paths to meaningful component names and organizes by scenario.
Compatible with Views.sysml and CPScoreInteractionModels pattern.

This script is CODEBASE-AGNOSTIC: component names are derived algorithmically
from file paths found in the CSV. No hardcoded mapping is required.
"""
import csv
import re
from pathlib import Path
from collections import OrderedDict


# ---------------------------------------------------------------------------
# Path-to-Component Mapping (algorithmic — no hardcoded table)
# ---------------------------------------------------------------------------

# Cache so the same path always resolves to the same component name
_component_cache: dict[str, str] = {}


def _stem_to_component_name(stem: str) -> str:
    """
    Convert a file stem into a CamelCase component name.

    Examples:
        'hamming74'              -> 'Hamming74'
        'BasicSerialization'     -> 'BasicSerialization'
        'tcp_client'             -> 'TcpClient'
        'MessageQueuePublisherImpl' -> 'MessageQueuePublisher' (strip Impl)
    """
    # If already CamelCase (starts upper, has mixed case), use as-is
    if re.match(r'^[A-Z][a-zA-Z0-9]+$', stem):
        name = stem
    else:
        # Split on underscores/hyphens/dots and CamelCase
        parts = re.split(r'[_\-.]', stem)
        name = ''.join(p.capitalize() for p in parts if p)

    # Strip trailing "Impl" — treat implementation as same component
    if name.endswith("Impl") and len(name) > 4:
        name = name[:-4]

    return name or "Unknown"


def _detect_extern_library(path: str) -> str | None:
    """
    For paths under /extern/, return a short library name.
    Returns None if not an extern path.
    """
    if not path.startswith("/extern/"):
        return None

    # Extract the first directory after /extern/
    parts = path.split("/")
    # parts = ['', 'extern', 'LibName', ...]
    if len(parts) < 3:
        return "External"

    lib_dir = parts[2]  # e.g. 'Catch2', 'cpp_redis'

    # Check for sub-libraries (e.g. cpp_redis/tacopie)
    if lib_dir == "cpp_redis" and len(parts) > 3 and parts[3] == "tacopie":
        return "Tacopie"

    # Normalize common patterns
    return _stem_to_component_name(lib_dir)


def map_component(path: str) -> str:
    """
    Derive a meaningful component name from a file path.

    Strategy:
      1. /extern/... → library name (e.g. Catch2, CppRedis, Tacopie)
      2. /tests/...  → file stem + "Test" suffix if not already present
      3. /src/... or /include/... → file stem as CamelCase class name

    The same stem appearing under /src/ and /include/ maps to the same
    component, since header+implementation represent one logical unit.
    """
    if path in _component_cache:
        return _component_cache[path]

    # --- Extern libraries ---
    lib = _detect_extern_library(path)
    if lib is not None:
        _component_cache[path] = lib
        return lib

    stem = Path(path).stem  # e.g. 'BasicSerialization', 'hamming74'

    # --- Test files ---
    if "/tests/" in path or path.startswith("/tests/"):
        name = _stem_to_component_name(stem)
        # Append "Test" if not already a test-named file
        if not name.endswith("Test"):
            name += "Test"
        _component_cache[path] = name
        return name

    # --- Source / Include files ---
    name = _stem_to_component_name(stem)
    _component_cache[path] = name
    return name


# ---------------------------------------------------------------------------
# Scenario classification (algorithmic — derived from file path structure)
# ---------------------------------------------------------------------------

# Directories that are too generic to serve as a subsystem name
_GENERIC_DIRS = frozenset({
    "detail", "api", "impl", "internal", "include", "src", "core",
    "sources", "includes", "single_include", "misc", "utils", "network",
    "builders", "cpsCore",
})


def _extract_subsystem(path: str) -> str:
    """
    Derive a subsystem/domain name from a file path.

    The subsystem is determined by traversing the directory hierarchy from
    the most specific (deepest) directory upward, selecting the first
    non-generic directory name. This groups files that share a common
    functional area into the same scenario.

    Examples:
        /src/Utilities/IDC/NetworkLayer/Redis/RedisPublisher.cpp → Redis
        /src/Synchronization/AggregatableRunner.cpp              → Synchronization
        /src/Aggregation/Aggregator.cpp                          → Aggregation
        /include/cpsCore/Utilities/IPC/detail/MsgQueueImpl.h     → IPC
        /tests/Utilities/FilterTest.cpp                          → TestExecution
        /extern/Catch2/...                                       → Catch2
        /extern/cpp_redis/tacopie/...                            → Tacopie
    """
    # Extern libraries → use library name
    if path.startswith("/extern/"):
        parts = path.split("/")
        if len(parts) >= 3:
            lib = parts[2]
            if lib == "cpp_redis" and len(parts) > 3 and parts[3] == "tacopie":
                return "Tacopie"
            return _stem_to_component_name(lib)
        return "External"

    # Test files → single "TestExecution" subsystem
    if "/tests/" in path or path.startswith("/tests/"):
        return "TestExecution"

    # Source/Include files → find the most specific non-generic directory
    # Strip common prefixes to get the meaningful part
    clean = path
    for prefix in ("/src/", "/include/cpsCore/", "/include/"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
            break

    # Get parent directories (without the filename)
    parent = str(Path(clean).parent)
    dirs = [d for d in parent.replace("\\", "/").split("/") if d and d != "."]

    # Walk from deepest to shallowest, pick the first meaningful directory
    for d in reversed(dirs):
        if d.lower() not in _GENERIC_DIRS:
            return _stem_to_component_name(d)

    # Fallback: use the file stem itself as the subsystem
    return _stem_to_component_name(Path(path).stem)


def build_scenarios(rows: list) -> OrderedDict:
    """
    Group rows into scenarios based on the client component's subsystem.

    Returns an OrderedDict mapping scenario names to lists of messages,
    ordered by first appearance in the sequence.
    """
    from collections import defaultdict

    subsystem_groups: dict[str, list] = defaultdict(list)

    for row in rows:
        subsystem = _extract_subsystem(row["client_path"])
        subsystem_groups[subsystem].append(row)

    # Build ordered scenarios, sorted by earliest sequence number in each group
    sorted_subsystems = sorted(
        subsystem_groups.items(),
        key=lambda item: item[1][0]["seq"]
    )

    scenarios = OrderedDict()
    for subsystem, msgs in sorted_subsystems:
        scenario_name = f"{subsystem}Scenario"
        # Deduplicate: keep only unique (client, server, event) tuples
        seen = set()
        deduped = []
        for m in msgs:
            key = (m["client"], m["server"], m["event"])
            if key not in seen:
                seen.add(key)
                deduped.append(m)
        if deduped:
            scenarios[scenario_name] = deduped

    # Merge tiny scenarios (< 3 messages) into a "MiscellaneousScenario"
    final = OrderedDict()
    misc_msgs = []
    for name, msgs in scenarios.items():
        if len(msgs) >= 3:
            final[name] = msgs
        else:
            misc_msgs.extend(msgs)
    if misc_msgs:
        final["MiscellaneousScenario"] = misc_msgs

    return final


# ---------------------------------------------------------------------------
# SysML v2 Generation
# ---------------------------------------------------------------------------

MSG_TYPE_MAP = {
    "Command": "SynchronousCall",
    "Reply": "ReturnMessage",
    "Notification": "AsynchronousMessage",
}


def generate_sysml(scenarios: dict, package_name: str = "CPScoreInteractionModels") -> str:
    """Generate SysML v2 textual notation from classified scenarios."""
    lines = []
    lines.append(f"package {package_name} {{")
    lines.append("    private import ScalarValues::String;")
    lines.append("")
    lines.append("    // =========================================================")
    lines.append("    // Interaction stereotypes")
    lines.append("    // =========================================================")
    lines.append("")
    lines.append("    part def InteractionScenario;")
    lines.append("    part def Lifeline;")
    lines.append("")
    lines.append("    part def Message {")
    lines.append("        attribute label : String;")
    lines.append("        ref from : Lifeline;")
    lines.append("        ref to   : Lifeline;")
    lines.append("    }")
    lines.append("")
    lines.append("    part def SynchronousCall     :> Message;")
    lines.append("    part def ReturnMessage       :> Message;")
    lines.append("    part def AsynchronousMessage :> Message;")
    lines.append("")

    scenario_num = 0
    for scenario_name, messages in scenarios.items():
        if not messages:
            continue
        scenario_num += 1

        # Derive description from scenario name (strip "Scenario" suffix)
        desc = scenario_name.replace("Scenario", "")
        lines.append("    // =========================================================")
        lines.append(f"    // SCENARIO {scenario_num}: {desc}")
        lines.append("    // =========================================================")
        lines.append("")
        lines.append(f"    part def {scenario_name} :> InteractionScenario {{")
        lines.append("")

        # Collect participants (use simple lowercase names for lifelines)
        participants = OrderedDict()
        capped_msgs = messages[:12]
        for msg in capped_msgs:
            if msg["client"] not in participants:
                # Convert CamelCase to simple lowercase identifier
                name = msg["client"]
                pname = name[0].lower() + name[1:] if name else "unknown"
                # Simplify problematic prefixes (e.g. cPSLogger -> logger)
                if pname.startswith("cPS"):
                    pname = pname[3].lower() + pname[4:]
                elif pname.startswith("iDC") or pname.startswith("iPC"):
                    pname = pname[:3].lower() + pname[3:]
                participants[msg["client"]] = pname
            if msg["server"] not in participants:
                name = msg["server"]
                pname = name[0].lower() + name[1:] if name else "unknown"
                if pname.startswith("cPS"):
                    pname = pname[3].lower() + pname[4:]
                elif pname.startswith("iDC") or pname.startswith("iPC"):
                    pname = pname[:3].lower() + pname[3:]
                participants[msg["server"]] = pname

        # Deduplicate part names (ensure they're valid SysML identifiers)
        used_names = set()
        for comp, pname in list(participants.items()):
            orig = pname
            counter = 2
            while pname in used_names:
                pname = f"{orig}{counter}"
                counter += 1
            participants[comp] = pname
            used_names.add(pname)

        # Emit lifeline declarations
        for comp, pname in participants.items():
            lines.append(f"        part {pname} : Lifeline;")
        lines.append("")

        # Emit messages (cap at 12 to keep diagrams readable)
        capped = messages[:12]
        for idx, msg in enumerate(capped, 1):
            src_part = participants[msg["client"]]
            tgt_part = participants[msg["server"]]
            msg_type = MSG_TYPE_MAP.get(msg["rel_type"], "SynchronousCall")
            event = msg["event"]

            # Clean label: "N. eventName" — no brackets or special chars
            label = f"{idx}. {event}"

            lines.append(f"        part m{idx} : {msg_type} {{")
            lines.append(f'            ref from : Lifeline = {src_part};')
            lines.append(f'            ref to   : Lifeline = {tgt_part};')
            lines.append(f'            attribute :>> label = "{label}";')
            lines.append(f"        }}")
            lines.append("")

        lines.append("    }")
        lines.append("")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a SysML v2 sequence model from sequence_dependency_table.csv"
    )
    parser.add_argument(
        "csv", nargs="?", type=Path,
        default=Path(r"c:\Users\prathikak\Documents\cpsCore\sequence_dependency_table.csv"),
        help="Path to the sequence_dependency_table.csv (default: workspace CSV)",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output .sysml file (default: sysml_sequence_model.sysml in same folder)",
    )
    parser.add_argument(
        "--package", default="CPScoreInteractionModels",
        help='SysML package name (default: "CPScoreInteractionModels")',
    )
    args = parser.parse_args()

    csv_path = args.csv
    output_path = args.output or csv_path.parent / "sysml_sequence_model.sysml"

    # Read and process CSV
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            client = map_component(row["ClientComponent"])
            server = map_component(row["ServerComponent"])
            processed = {
                "seq": int(row["Sequence"]),
                "event": row["EventName"],
                "client": client,
                "client_path": row["ClientComponent"],
                "client_fn": row["ClientFunction"],
                "server": server,
                "server_path": row["ServerComponent"],
                "server_fn": row["ServerFunction"],
                "rel_type": row["RelationshipType"],
                "timestamp": row["EventTimestamp"],
            }
            rows.append(processed)

    # Sort by sequence
    rows.sort(key=lambda r: r["seq"])

    # Filter: exclude purely external library-internal calls and self-calls
    # (self-calls where client == server add no interaction value)
    EXTERNAL_COMPONENTS = set()
    for r in rows:
        if r["client_path"].startswith("/extern/"):
            EXTERNAL_COMPONENTS.add(r["client"])
        if r["server_path"].startswith("/extern/"):
            EXTERNAL_COMPONENTS.add(r["server"])

    filtered_rows = [
        r for r in rows
        if not (r["client"] in EXTERNAL_COMPONENTS and r["server"] in EXTERNAL_COMPONENTS)
        and r["client"] != r["server"]
    ]

    # Build scenarios algorithmically from subsystem grouping
    scenarios = build_scenarios(filtered_rows)

    # Print stats
    total_msgs = sum(len(v) for v in scenarios.values())
    print(f"Total rows: {len(rows)}")
    print(f"Filtered rows: {len(filtered_rows)}")
    print(f"Scenarios (deduped messages): {len(scenarios)} scenarios, {total_msgs} messages")
    for name, msgs in scenarios.items():
        print(f"  {name}: {len(msgs)} messages")

    # Generate SysML
    sysml = generate_sysml(scenarios, package_name=args.package)
    output_path.write_text(sysml, encoding="utf-8", newline="\n")
    print(f"\nWritten to: {output_path}")
    print(f"Total lines: {sysml.count(chr(10)) + 1}")


if __name__ == "__main__":
    main()
