"""
run_c1_llm_only.py — H1 Condition 1: Source code only (two-prompt chain)
-------------------------------------------------------------------------
Makes TWO separate LLM calls per scenario, each focused on one task:

  Call 1 — INTERACTIONS: identify the complete set of distinct cross-component
            method calls that execute during this test. Focus: coverage, precision,
            no duplicates. Excludes implementation details (singleton accessors).

  Call 2 — SEQUENCE: given the interactions from call 1, produce the full ordered
            execution sequence with repetitions (once per thread/stage/iteration).
            Focus: ordering and multiplicity.

Separating the tasks prevents the LLM from conflating set-identification with
ordering, which caused over-generation and wrong multiplicities in the combined prompt.

Usage:
    python run_c1_llm_only.py --scenario S1a
    python run_c1_llm_only.py --all

Input:  scenarios/<scenario>/source_snippet.txt
Output: C1_llm_only/<scenario>/interactions.json  — dedup set
        C1_llm_only/<scenario>/sequence.json       — ordered full sequence
"""
import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (SCENARIOS, SCENARIO_COMPONENTS, SCENARIO_PRIMARY, Element,
                    save_elements, interactions_path, sequence_path, COND_DIR, SCEN_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(pathlib.Path(__file__).parents[3] / ".env")
except ImportError:
    pass

try:
    from openai import AzureOpenAI
except ImportError:
    raise SystemExit("Run: pip install openai")

LABEL = "C1_llm_only"

# ── Prompt 1: interactions (unique set) ────────────────────────────────────
PROMPT_INTERACTIONS = """\
You are a software architect analysing the CPSCore C++ framework.

Based ONLY on the C++ source code below (no runtime traces or graph data),
identify every distinct cross-component method call that executes during
this specific test scenario.

A "cross-component call" crosses a CPSCore module boundary — the caller class
belongs to one module and the callee belongs to a DIFFERENT module.
CPSCore modules: Aggregation, Configuration, Framework, Logging, Synchronization, Utilities.

IMPORTANT — CPSLOG macros and log level:
Every CPSLOG_* call (CPSLOG_TRACE, CPSLOG_DEBUG, CPSLOG_WARN, CPSLOG_ERROR, ...)
creates a RAIILogStream object and calls .stream on it — this IS a cross-component
call to Logging regardless of the current log level setting. The log level only
controls whether output is printed, NOT whether RAIILogStream.stream is invoked.
Represent each CPSLOG_* call as:
  {{"source": "<CallerComponent>", "target": "Logging", "interaction": "RAIILogStream.stream"}}

IMPORTANT — CPSLogger.flush():
Calls to CPSLogger::instance()->flush() ARE a cross-component interaction:
  {{"source": "<CallerComponent>", "target": "Logging", "interaction": "CPSLogger.flush"}}

IMPORTANT — failure / timeout scenarios:
If this is a failure or timeout variant, the test STILL executes the normal
happy-path calls first before the failure path fires. Include ALL interactions
from BOTH the normal path and the failure/timeout path.

Return ONLY a JSON array, no other text:
[
  {{"source": "ComponentA", "target": "ComponentB", "interaction": "ClassName.methodName"}}
]

EXCLUDE:
- CPSLogger::instance() — singleton accessor, not an interaction.
- setLogLevel(), setSink() — logging configuration, not scenario interactions.
- Test-fixture setup calls executed before the scenario logic runs
  (e.g. aggregator.add(obj) in the test body before any runner/scheduler starts).

INCLUDE:
- RAIILogStream.stream from any CPSLOG_* call (ALL log levels, as explained above).
- CPSLogger.flush() calls.
- ALL interactions from every code path the test exercises.
- "interaction" is "ClassName.methodName" (e.g. "Aggregator.getAll").
- No self-loops. One entry per unique (source, target, interaction) triple.
- Output ONLY the JSON array.

Source code:
{source_code}
"""

# ── Prompt 2: sequence (ordered, with repetitions) ─────────────────────────
PROMPT_SEQUENCE = """\
You are a software architect analysing the CPSCore C++ framework.

The following cross-component interactions have been identified for this scenario:
{interactions_list}

Based ONLY on the C++ source code below, produce the complete ORDERED execution
sequence of ALL firing instances of these calls during the test — including
repetitions (once per thread, once per stage, once per loop iteration, etc.).

Return ONLY a JSON array of all firing events in execution order, no other text:
[
  {{"order": 0, "source": "ComponentA", "target": "ComponentB",
    "interaction": "ClassName.methodName",
    "note": "brief reason: which function calls this and when"}}
]

Rules:
- "order" is the 0-based position in the full execution sequence.
- List ALL firing instances — not just unique types.
  Example: if getAll fires twice (once per runner thread), list it twice.
- Only use interactions from the provided list above.
- Estimate repetition counts from the code (thread count, stage count, loop bounds).
- For failure/timeout scenarios: list the happy-path calls first, then the
  failure-path calls in the order they fire after the timeout occurs.
- Output ONLY the JSON array.

Source code:
{source_code}
"""


def _llm_call(client: "AzureOpenAI", prompt: str, scenario: str, label: str) -> str:
    resp = client.chat.completions.create(
        model=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-5"),
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = raw[:-3].strip()
    return raw


def run_scenario(scenario: str) -> None:
    snippet_path = SCEN_DIR / scenario / "source_snippet.txt"
    if not snippet_path.exists():
        print(f"  [SKIP] {snippet_path} not found")
        return
    source_code = snippet_path.read_text(encoding="utf-8")

    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_ENDPOINT"],
        api_version="2025-01-01-preview",
    )
    allowed = SCENARIO_COMPONENTS[scenario]
    primary = SCENARIO_PRIMARY[scenario]
    out_dir = COND_DIR / LABEL / scenario
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Call 1: interactions ────────────────────────────────────────────────
    print(f"  [Call 1] Identifying interactions ...")
    raw1 = _llm_call(client, PROMPT_INTERACTIONS.format(source_code=source_code),
                     scenario, "interactions")
    try:
        intr_raw = json.loads(raw1)
    except json.JSONDecodeError as e:
        print(f"  [WARN] interactions parse error: {e}\n  Raw: {raw1[:200]}")
        intr_raw = []

    interaction_elements = {
        Element(d["source"], d["target"], d["interaction"])
        for d in intr_raw
        if isinstance(d, dict)
        and d.get("source") in allowed
        and d.get("target") in allowed
        and d.get("source") != d.get("target")
        and d.get("interaction")
    }
    save_elements(interaction_elements, interactions_path(LABEL, scenario))

    # ── Call 2: sequence (chained — gives LLM the confirmed interaction set) ─
    print(f"  [Call 2] Ordering sequence ...")
    intr_list = "\n".join(
        f"  - {e.source} → {e.target} : {e.interaction}"
        for e in sorted(interaction_elements)
    ) or "  (none identified)"
    raw2 = _llm_call(client,
                     PROMPT_SEQUENCE.format(source_code=source_code,
                                            interactions_list=intr_list),
                     scenario, "sequence")
    try:
        seq_raw = json.loads(raw2)
    except json.JSONDecodeError as e:
        print(f"  [WARN] sequence parse error: {e}\n  Raw: {raw2[:200]}")
        seq_raw = []

    valid_keys = {(e.source, e.target, e.interaction) for e in interaction_elements}
    seq_steps, order = [], 0
    for d in seq_raw:
        if not isinstance(d, dict):
            continue
        if (d.get("source"), d.get("target"), d.get("interaction")) in valid_keys:
            seq_steps.append({
                "order":       order,
                "source":      d["source"],
                "target":      d["target"],
                "interaction": d["interaction"],
                "note":        d.get("note", ""),
            })
            order += 1
    sequence_path(LABEL, scenario).write_text(json.dumps(seq_steps, indent=2))
    print(f"  C1 → {len(interaction_elements)} interactions, {len(seq_steps)} sequence steps")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    targets = SCENARIOS if args.all else [args.scenario]
    for s in targets:
        print(f"C1 LLM-only: {s}")
        run_scenario(s)


if __name__ == "__main__":
    main()
