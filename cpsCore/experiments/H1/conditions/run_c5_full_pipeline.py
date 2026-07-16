"""
run_c5_full_pipeline.py — H1 Condition 5: Full pipeline (Static + Dynamic + Agent)
------------------------------------------------------------------------------------
v2 methodology (supersedes the original flat-union version):

The agent no longer receives a pre-merged, provenance-erased C4 union. Instead
it receives C2 (static call-graph edges) and C3 (dynamic trace rows, in their
REAL captured execution order, with caller/callee function names) as two
separately labeled evidence sources. This lets the agent reason about *why*
an edge is missing from one source — e.g. a static-only edge may be a
genuinely real call that is merely suppressed at runtime (LogLevel::NONE, as
in S4), which should usually be KEPT, not pruned as an "implementation
detail" — instead of collapsing that distinction the moment the two sources
are unioned.

The agent produces two things in one response:
  1. "elements"  — the final deduplicated {source,target,interaction} set.
                    Written to elements.json, UNCHANGED SCHEMA, so the
                    existing score.py F1 pipeline and H3's condition-B/B'
                    prompt-builder keep working without modification.
  2. "sequence"  — a complete, ORDERED call sequence for the scenario: the
                    real dynamic trace order is the backbone, and any
                    retained static-only edges are inserted at the position
                    implied by the scenario description / source semantics.
                    Rendered to sequence.mmd (Mermaid sequenceDiagram) and
                    also saved raw as sequence.json for auditability.

Requires AZURE_ENDPOINT / AZURE_OPENAI_API_KEY in cpsCore/.env.

Usage:
    python run_c5_full_pipeline.py --scenario S1
    python run_c5_full_pipeline.py --all

Output:
    experiments/H1/conditions/C5_full_pipeline/<scenario>/elements.json
    experiments/H1/conditions/C5_full_pipeline/<scenario>/sequence.json
    experiments/H1/conditions/C5_full_pipeline/<scenario>/sequence.mmd
    experiments/H1/conditions/C5_full_pipeline/<scenario>/model.sysml   (SysML v2: structure + sequence)
    experiments/H1/conditions/C5_full_pipeline/<scenario>/views.sysml  (SysML v2 views exposing model.sysml)
"""
import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (ROOT, SCENARIOS, SCENARIO_COMPONENTS, SCENARIO_PRIMARY,
                    Element, load_elements, save_elements, elements_path,
                    load_trace_slice)

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

try:
    from openai import AzureOpenAI
except ImportError:
    raise SystemExit("Run: pip install openai")

LABEL = "C5_full_pipeline"

SCENARIO_DESCRIPTIONS = {
    "S1": "Aggregator notification chain: Synchronization runners trigger aggregation "
          "updates and logging throughout.",
    "S2": "Configuration property mapping: PropertyMapper reads/validates properties "
          "and logs each step.",
    "S3": "Multi-component runner orchestration: SimpleRunner fans out to Aggregation "
          "(fetch runnable objects), Utilities (convert RunStage enum to string), "
          "and Logging (log progress).",
    "S4": "Stage Event Bridge pub-sub routing: a Synchronization-side "
          "StageEventBridge publishes RunStage events via a boost::signals2 signal; "
          "an Aggregation-side StageEventListener receives them via onStageEvent "
          "when connected. Publishing with no listener attached logs an error via "
          "Logging (fault path, suppressed at runtime by LogLevel::NONE in the test).",
}

SYNTHESIS_PROMPT = """\
You are a software architect reconstructing the interaction model for the \
following scenario in the CPSCore C++ framework.

Scenario: {description}

You have TWO INDEPENDENT, separately-collected evidence sources. They have \
NOT been pre-merged — you must reason about them together yourself.

## STATIC EVIDENCE (call-graph analysis; NO execution order available)
Found by analysing source-code call sites. A static edge can be missing from \
the dynamic trace for two very different reasons:
  (a) it is a genuinely real call that happened to be SUPPRESSED under the \
      tested runtime conditions (e.g. a log call gated behind a disabled log \
      level such as LogLevel::NONE) — this is still architecturally real and \
      should normally be KEPT even though only one source has it; or
  (b) static analysis over-approximated and the edge is incidental (e.g. a \
      redundant singleton-accessor call sitting alongside another call to the \
      same target that IS corroborated by the trace) — this is safe to drop.
Each edge below is tagged with whether the dynamic trace also observed it.
{static_list}

## DYNAMIC EVIDENCE (real runtime trace, IN ACTUAL EXECUTION ORDER)
Observed executing, listed in the real order they occurred, with the calling \
function that triggered each one. A dynamic-only edge (no matching static \
edge) usually means static analysis could not resolve an indirect dispatch \
(e.g. a boost::signals2 signal/slot connection established at runtime) — this \
is confirmed by actual execution and should almost always be KEPT.
{dynamic_list}

## Your task
1. Decide the final set of architecturally significant interactions. An edge \
   corroborated by BOTH sources is strong evidence to keep. An edge found by \
   only ONE source is NOT automatically weaker evidence — reason about *why* \
   it is missing from the other source (suppression vs. indirect dispatch vs. \
   genuine over-approximation) using the guidance above, rather than treating \
   single-source edges as uniformly lower priority.
2. Produce a complete, precise, ORDERED call sequence for the scenario: use \
   the real dynamic execution order as the backbone, and insert any retained \
   static-only edges at the position implied by the scenario description \
   (e.g. "this error log fires inside function X, in place of the normal \
   continuation, when the fault condition holds"). Add a short "note" to any \
   step that came from only one evidence source, explaining why (e.g. \
   "suppressed at runtime, LogLevel::NONE" or "indirect dispatch, no static \
   call site").

Return ONLY a JSON object in this exact format, no other text:
{{
  "elements": [
    {{"source": "ComponentA", "target": "ComponentB", "interaction": "MethodName"}}
  ],
  "sequence": [
    {{"step": 1, "source": "ComponentA", "target": "ComponentB", "interaction": "MethodName", "note": ""}}
  ]
}}

Every entry in "elements" must appear at least once in "sequence", and vice versa.
Valid component names: Aggregation, Configuration, Framework, Logging, \
Synchronization, Utilities.
"""


def _normalize_static(elements: set) -> set:
    """Normalize interaction names to bare function name, matching scorer convention."""
    return {Element(e.source, e.target, e.interaction.split(".")[-1]) for e in elements}


def _load_dynamic_ordered(scenario: str, primary: str, allowed: set) -> list[dict]:
    """Filtered, order-preserving dynamic evidence with caller-function context.

    trace_slice.txt rows are already in real captured chronological order
    (by EventTimestamp) — no re-sorting is performed, to keep the sequence
    backbone genuine rather than reconstructed.
    """
    rows = load_trace_slice(scenario)
    ordered = []
    for row in rows:
        src  = row.get("ClientComponent", "").strip()
        tgt  = row.get("ServerComponent",  "").strip()
        intr = row.get("EventName",        "").strip()
        fn   = row.get("ClientFunction",   "").strip()
        ts   = row.get("EventTimestamp",   "").strip()
        if src and tgt and intr and src == primary and tgt in allowed and src != tgt:
            ordered.append({
                "source": src, "target": tgt,
                "interaction": intr.split(".")[-1],
                "caller_function": fn, "timestamp": ts,
            })
    return ordered


def _render_mermaid(sequence: list[dict], scenario: str, path: pathlib.Path) -> None:
    lines = ["sequenceDiagram", f"  %% C5 full-pipeline reconstruction — {scenario}"]
    participants: list[str] = []
    for step in sequence:
        for p in (step.get("source"), step.get("target")):
            if p and p not in participants:
                participants.append(p)
    for p in participants:
        lines.append(f"  participant {p}")
    if not sequence:
        lines.append("  %% (no steps — agent kept no elements for this scenario)")
    for step in sequence:
        lines.append(f"  {step['source']}->>{step['target']}: {step['interaction']}")
        note = (step.get("note") or "").strip()
        if note:
            lines.append(f"  Note right of {step['target']}: {note}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Saved sequence diagram → {path.relative_to(ROOT)}")


def _sysml_id(name: str) -> str:
    """Sanitize a name into a valid SysML v2 identifier fragment."""
    safe = re.sub(r"[^0-9A-Za-z_]", "_", name)
    if safe and safe[0].isdigit():
        safe = f"_{safe}"
    return safe


def _port_type_name(interaction: str) -> str:
    """Derive a port-def (interface) type name from an interaction, e.g. 'getAll' -> 'GetAll'."""
    ident = _sysml_id(interaction)
    return ident[:1].upper() + ident[1:]


def _render_sysml_model(scenario: str, elements: set, sequence: list, path: pathlib.Path) -> None:
    """Render a combined SysML v2 model (structural + sequence) for one scenario.

    Follows the SAME textual conventions as the confirmed-working, visualizer-
    rendering root files ``sysml_structural_model.sysml`` / ``sysml_sequence_model.sysml``
    / ``Views.sysml`` (port-typed structural model + Message/Lifeline sequence
    model), scoped per-scenario via distinct package names:
    - Structural package (``ComponentModel_<scenario>``): one ``port def`` per
      unique interaction, one ``part def`` per component with ``server<Type>``
      ports for interactions it provides (is the call target of) and
      ``client<Type>`` ports for interactions it requires (is the call source
      of), and a ``part def System`` instantiating each component and
      connecting provider→requirer ports (``connect target.serverX to
      source.clientX;``). Derived from the final ``elements`` set.
    - Sequence package (``CPScoreInteractionModels_<scenario>``): the standard
      ``InteractionScenario`` / ``Lifeline`` / ``Message`` / ``SynchronousCall``
      scaffolding, with one ``part def <Scenario>Scenario`` containing a
      ``Lifeline`` part per participant and ordered ``SynchronousCall`` parts
      labeled ``"<step>. <interaction>"`` (with the agent's provenance note
      appended, if any). Derived from the ordered ``sequence`` list.
    """
    comp_pkg = f"ComponentModel_{scenario}"
    seq_pkg  = f"CPScoreInteractionModels_{scenario}"
    scenario_part = f"{scenario}Scenario"

    components   = sorted({e.source for e in elements} | {e.target for e in elements})
    interactions = sorted({e.interaction for e in elements})

    lines: list[str] = []

    # ---- structural package ----
    lines.append(f"package {comp_pkg} {{")
    lines.append("")
    for intr in interactions:
        lines.append(f"    port def {_port_type_name(intr)};")
    lines.append("")
    for comp in components:
        provided = sorted({e.interaction for e in elements if e.target == comp})
        required = sorted({e.interaction for e in elements if e.source == comp})
        lines.append(f"    part def {_sysml_id(comp)} {{")
        for intr in provided:
            lines.append(f"        port server{_port_type_name(intr)} : {_port_type_name(intr)};")
        for intr in required:
            lines.append(f"        port client{_port_type_name(intr)} : {_port_type_name(intr)};")
        lines.append("    }")
        lines.append("")
    lines.append("    part def System {")
    for comp in components:
        lines.append(f"        part {_sysml_id(comp).lower()} : {_sysml_id(comp)};")
    if elements:
        lines.append("")
    for e in sorted(elements):
        s = _sysml_id(e.source).lower()
        t = _sysml_id(e.target).lower()
        p = _port_type_name(e.interaction)
        # provider (target, has serverX) → requirer (source, has clientX)
        lines.append(f"        connect {t}.server{p} to {s}.client{p};")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # ---- sequence package ----
    lines.append(f"package {seq_pkg} {{")
    lines.append("    private import ScalarValues::String;")
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
    lines.append("    part def SynchronousCall :> Message;")
    lines.append("")
    lines.append(f"    part def {scenario_part} :> InteractionScenario {{")
    lines.append("")

    lifelines: list[str] = []
    for step in sequence:
        for p in (step.get("source"), step.get("target")):
            if p and p not in lifelines:
                lifelines.append(p)
    for p in lifelines:
        lines.append(f"        part {_sysml_id(p).lower()} : Lifeline;")
    lines.append("")

    for step in sequence:
        note = (step.get("note") or "").strip()
        label = f"{step['step']}. {step['interaction']}"
        if note:
            label += f" ({note})"
        label = label.replace('"', "'")
        src = _sysml_id(step["source"]).lower()
        tgt = _sysml_id(step["target"]).lower()
        lines.append(f"        part m{step['step']} : SynchronousCall {{")
        lines.append(f"            ref from : Lifeline = {src};")
        lines.append(f"            ref to   : Lifeline = {tgt};")
        lines.append(f'            attribute :>> label = "{label}";')
        lines.append("        }")
        lines.append("")

    lines.append("    }")
    lines.append("}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Saved SysML model → {path.relative_to(ROOT)}")


def _render_sysml_views(scenario: str, path: pathlib.Path) -> None:
    """Render a views.sysml exposing the structural and sequence views for one scenario,
    following the same convention as the confirmed-working root Views.sysml."""
    comp_pkg = f"ComponentModel_{scenario}"
    seq_pkg  = f"CPScoreInteractionModels_{scenario}"
    scenario_part = f"{scenario}Scenario"
    flow_view = f"{scenario.lower()}Flow"
    lines = [
        "package Views {",
        f"    import {comp_pkg}::*;",
        f"    import {seq_pkg}::*;",
        "",
        "    view structure : GeneralView {",
        f"        expose {comp_pkg}::System;",
        "    }",
        "",
        "    view connections : InterconnectionView {",
        f"        expose {comp_pkg}::System;",
        "    }",
        "",
        f"    view {flow_view} : SequenceView {{",
        f"        expose {seq_pkg}::{scenario_part};",
        "    }",
        "}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Saved SysML views → {path.relative_to(ROOT)}")


def run_scenario(scenario: str) -> None:
    primary = SCENARIO_PRIMARY[scenario]
    allowed = SCENARIO_COMPONENTS[scenario]

    static_norm     = _normalize_static(load_elements(elements_path("C2_static_only", scenario)))
    dynamic_ordered = _load_dynamic_ordered(scenario, primary, allowed)

    if not static_norm:
        print(f"  [WARN] C2 empty for {scenario} — run run_c2_static_only.py first")
    if not dynamic_ordered:
        print(f"  [INFO] No dynamic evidence for {scenario} (fully suppressed at runtime, or run run_c3_dynamic_only.py first)")

    if not static_norm and not dynamic_ordered:
        save_elements(set(), elements_path(LABEL, scenario))
        out_dir = elements_path(LABEL, scenario).parent
        _render_mermaid([], scenario, out_dir / "sequence.mmd")
        _render_sysml_model(scenario, set(), [], out_dir / "model.sysml")
        _render_sysml_views(scenario, out_dir / "views.sysml")
        return

    dynamic_keys = {(d["source"], d["target"], d["interaction"]) for d in dynamic_ordered}
    static_keys  = {(e.source, e.target, e.interaction) for e in static_norm}

    static_lines = []
    for e in sorted(static_norm):
        key = (e.source, e.target, e.interaction)
        tag = " [ALSO in dynamic trace]" if key in dynamic_keys else " [STATIC-ONLY]"
        static_lines.append(f"  {e.source} → {e.target} : {e.interaction}{tag}")
    static_list = "\n".join(static_lines) if static_lines else "  (none)"

    dynamic_lines = []
    for i, d in enumerate(dynamic_ordered, 1):
        key = (d["source"], d["target"], d["interaction"])
        tag = (" [ALSO in static graph]" if key in static_keys
               else " [DYNAMIC-ONLY: no static call site, likely indirect dispatch]")
        caller = f" (from {d['caller_function']})" if d["caller_function"] else ""
        dynamic_lines.append(f"  [{i}] {d['source']} → {d['target']} : {d['interaction']}{caller}{tag}")
    dynamic_list = "\n".join(dynamic_lines) if dynamic_lines else "  (none — entire dynamic path suppressed at runtime)"

    prompt = SYNTHESIS_PROMPT.format(
        description=SCENARIO_DESCRIPTIONS[scenario],
        static_list=static_list,
        dynamic_list=dynamic_list,
    )

    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_ENDPOINT"],
        api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        api_version="2025-01-01-preview",
    )
    model = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-5")
    msg = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.choices[0].message.content.strip()

    # Strip markdown fences
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = raw[:-3].strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  [WARN] Could not parse LLM response for {scenario}: {e}")
        print(f"  Raw:\n{raw}")
        data = {"elements": [], "sequence": []}

    raw_elements = data.get("elements", []) if isinstance(data, dict) else []
    raw_sequence = data.get("sequence", []) if isinstance(data, dict) else []

    allowed_primary_check = allowed
    elements = {
        Element(d["source"], d["target"], d["interaction"])
        for d in raw_elements
        if d.get("source") == primary and d.get("target") in allowed_primary_check
           and d["source"] != d["target"] and d.get("interaction")
    }
    save_elements(elements, elements_path(LABEL, scenario))

    valid_keys = {(e.source, e.target, e.interaction) for e in elements}
    sequence = [
        step for step in raw_sequence
        if (step.get("source"), step.get("target"), step.get("interaction")) in valid_keys
    ]
    out_dir = elements_path(LABEL, scenario).parent
    seq_json_path = out_dir / "sequence.json"
    with open(seq_json_path, "w") as f:
        json.dump(sequence, f, indent=2)

    _render_mermaid(sequence, scenario, out_dir / "sequence.mmd")
    _render_sysml_model(scenario, elements, sequence, out_dir / "model.sysml")
    _render_sysml_views(scenario, out_dir / "views.sysml")

    evidence_union = len(static_keys | dynamic_keys)
    print(f"  static={len(static_norm)} dynamic={len(dynamic_ordered)} "
          f"union={evidence_union} → agent kept {len(elements)} elements, "
          f"{len(sequence)} sequence steps")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    targets = SCENARIOS if args.all else [args.scenario]
    for s in targets:
        print(f"C5 full-pipeline: {s}")
        run_scenario(s)


if __name__ == "__main__":
    main()
