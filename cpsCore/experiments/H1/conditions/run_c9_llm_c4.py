"""
run_c9_llm_c4.py — H1 Condition 9: LLM refined from guided trace (C4 candidates)
----------------------------------------------------------------------------------
Two-call LLM chain per scenario:

  Call 1 — INTERACTIONS: given the C4 guided-instrumentation candidates and the
            source code, remove any setup-phase events that slipped into the guided
            window, keep the scenario-logic interactions, and add any that were missed.

  Call 2 — SEQUENCE: given the confirmed interaction set and source code, produce
            the full ordered execution sequence with repetitions.

The C4 candidate list is already well-targeted (trace_slice.txt covers the test
execution window) but may contain a small number of setup-phase calls (e.g.,
Aggregator.add or Aggregation→Logging events from object registration that fire
before the scenario logic begins). The LLM's task is to make that final precision cut.

Usage:
    python run_c9_llm_c4.py --scenario S1a
    python run_c9_llm_c4.py --all

Input:  conditions/C4_guided_only/<scenario>/interactions.json   (guided trace candidates)
        scenarios/<scenario>/source_snippet.txt
Output: conditions/C9_llm_c4/<scenario>/interactions.json
        conditions/C9_llm_c4/<scenario>/sequence.json
"""
import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (SCENARIOS, SCENARIO_COMPONENTS, Element,
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

LABEL = "C9_llm_c4"
C4_LABEL = "C4_guided_only"

# ── Prompt 1: interactions ─────────────────────────────────────────────────
PROMPT_INTERACTIONS = """\
You are a software architect analysing the CPSCore C++ framework.

The following events were captured by GUIDED RUNTIME INSTRUMENTATION of this test
scenario. The instrumentation targeted the test execution window (from the moment
the scenario starts to when it ends), but may still include setup-phase calls that
fire in the test fixture just before the scenario logic begins — for example, calls
that register objects with an aggregator or configure the logger before any runner starts.

Guided instrumentation candidates:
{guided_candidates}

Using the C++ source code below, produce the CORRECT set of cross-component
architectural interactions for this test scenario. You MUST:
  1. Remove setup-phase interactions fired in the test fixture before the
     scenario logic starts (e.g. aggregator.add(), logger setup).
  2. Keep all genuine cross-component interactions that are part of the
     scenario execution logic.
  3. Add any cross-component interactions you see in the source code that
     the guided instrumentation missed.

A "cross-component call" crosses a CPSCore module boundary — the caller class
belongs to one module and the callee belongs to a DIFFERENT module.
CPSCore modules: Aggregation, Configuration, Framework, Logging, Synchronization, Utilities.

IMPORTANT — CPSLOG macros:
Every CPSLOG_* call (CPSLOG_TRACE, CPSLOG_DEBUG, CPSLOG_WARN, CPSLOG_ERROR, ...)
creates a RAIILogStream object and calls .stream on it — this IS a cross-component
call to Logging regardless of log level. Represent each as:
  {{"source": "<CallerComponent>", "target": "Logging", "interaction": "RAIILogStream.stream"}}

IMPORTANT — CPSLogger.flush():
Calls to CPSLogger::instance()->flush() are a cross-component interaction:
  {{"source": "<CallerComponent>", "target": "Logging", "interaction": "CPSLogger.flush"}}

IMPORTANT — failure / timeout scenarios:
If this is a failure or timeout variant, the test executes the normal happy-path
calls FIRST before the failure path fires. Include ALL interactions from both paths.

EXCLUDE:
- CPSLogger::instance() — singleton accessor, not an interaction.
- setLogLevel(), setSink() — logging configuration.
- Test-fixture setup calls executed before the scenario logic runs.

Return ONLY a JSON array, no other text:
[
  {{"source": "ComponentA", "target": "ComponentB", "interaction": "ClassName.methodName"}}
]

Rules:
- No self-loops (source != target).
- One entry per unique (source, target, interaction) triple.
- "interaction" is "ClassName.methodName" (e.g. "Aggregator.getAll").
- Output ONLY the JSON array.

Source code:
{source_code}
"""

# ── Prompt 2: sequence (chained) ────────────────────────────────────────────
PROMPT_SEQUENCE = """\
You are a software architect analysing the CPSCore C++ framework.

The following cross-component interactions have been confirmed for this scenario:
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
- For failure/timeout scenarios: list happy-path calls first, then failure-path
  calls in the order they fire after the timeout occurs.
- Output ONLY the JSON array.

Source code:
{source_code}
"""


def _llm_call(client: "AzureOpenAI", prompt: str) -> str:
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
    c4_path = interactions_path(C4_LABEL, scenario)
    if not snippet_path.exists():
        print(f"  [SKIP] {snippet_path} not found")
        return
    if not c4_path.exists():
        print(f"  [SKIP] C4 output not found: {c4_path} — run run_c4_guided_only.py first")
        return

    source_code = snippet_path.read_text(encoding="utf-8")
    c4_data = json.loads(c4_path.read_text(encoding="utf-8"))

    # Format C4 candidates for the prompt
    guided_candidates = "\n".join(
        f"  - {d['source']} → {d['target']} : {d['interaction']}"
        for d in c4_data
        if d.get("source") and d.get("target") and d.get("interaction")
    ) or "  (none)"

    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_ENDPOINT"],
        api_version="2025-01-01-preview",
    )
    allowed = SCENARIO_COMPONENTS[scenario]
    out_dir = COND_DIR / LABEL / scenario
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Call 1: interactions ────────────────────────────────────────────────
    print(f"  [Call 1] Refining guided trace candidates ...")
    raw1 = _llm_call(client, PROMPT_INTERACTIONS.format(
        guided_candidates=guided_candidates, source_code=source_code))
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

    # ── Call 2: sequence ────────────────────────────────────────────────────
    print(f"  [Call 2] Ordering sequence ...")
    intr_list = "\n".join(
        f"  - {e.source} → {e.target} : {e.interaction}"
        for e in sorted(interaction_elements)
    ) or "  (none identified)"
    raw2 = _llm_call(client, PROMPT_SEQUENCE.format(
        source_code=source_code, interactions_list=intr_list))
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
    print(f"  C9 → {len(interaction_elements)} interactions, {len(seq_steps)} sequence steps")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    targets = SCENARIOS if args.all else [args.scenario]
    for s in targets:
        print(f"C9 LLM+C4: {s}")
        run_scenario(s)


if __name__ == "__main__":
    main()
