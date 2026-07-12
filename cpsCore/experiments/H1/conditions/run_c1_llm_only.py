"""
run_c1_llm_only.py — H1 Condition 1: LLM-only baseline
--------------------------------------------------------
Sends only the scenario's plain-English description to Claude.
NO graph data, NO trace data, NO source code.
This is the floor baseline — the LLM must reconstruct the diagram
from world knowledge of C++ frameworks and the scenario description alone.

Usage:
    python run_c1_llm_only.py --scenario S1
    python run_c1_llm_only.py --all

Output: experiments/H1/conditions/C1_llm_only/<scenario>/elements.json
"""
import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (SCENARIOS, SCENARIO_COMPONENTS, SCENARIO_PRIMARY, Element,
                    save_elements, elements_path)

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

SCENARIO_DESCRIPTIONS = {
    "S1": (
        "Scenario S1 — Aggregator notification chain in CPSCore.\n"
        "A Synchronization runner triggers an aggregation update across CPSCore's "
        "Aggregation module. The SynchronizedRunner and AggregatableRunner "
        "(in the Synchronization component) interact with the Aggregator "
        "(in the Aggregation component) to fetch runnable objects. "
        "Logging activity occurs throughout via the Logging component."
    ),
    "S2": (
        "Scenario S2 — Configuration property mapping in CPSCore.\n"
        "The Configuration module's PropertyMapper reads and validates configuration "
        "properties (strings, vectors, enums, Eigen types). Each property read "
        "emits a trace log via the Logging module."
    ),
    "S3": (
        "Scenario S3 — Multi-component runner orchestration in CPSCore.\n"
        "SimpleRunner and SynchronizedRunnerMaster (Synchronization component) "
        "orchestrate a run cycle that fans out to: the Aggregation component "
        "(to retrieve runnable objects), the Utilities component (to convert "
        "RunStage enum values to strings), and the Logging component "
        "(to log stage progress and errors)."
    ),
    "S4": (
        "Scenario S4 — Stage Event Bridge pub-sub routing in CPSCore.\n"
        "A Synchronization-side StageEventBridge publishes RunStage completion "
        "events through a boost::signals2 signal. An Aggregation-side "
        "StageEventListener subscribes to the bridge and receives stage events "
        "via its onStageEvent callback when the signal fires. If the bridge "
        "publishes a stage with no listener attached, it logs an error through "
        "the Logging component."
    ),
}

PROMPT_TEMPLATE = """\
You are a software architect analysing the CPSCore C++ framework.

Based ONLY on the scenario description below (no source code or traces are provided),
produce a list of inter-component interactions in this exact JSON format:

[
  {{"source": "ComponentA", "target": "ComponentB", "interaction": "MethodName"}},
  ...
]

Rules:
- Use only the CPSCore module names: Aggregation, Configuration, Framework,
  Logging, Synchronization, Utilities.
- Each entry must have a distinct (source, target, interaction) triple.
- Do not include self-loops (source == target).
- Output ONLY the JSON array, no other text.

Scenario:
{description}
"""


def run_scenario(scenario: str) -> None:
    description = SCENARIO_DESCRIPTIONS[scenario]
    prompt = PROMPT_TEMPLATE.format(description=description)

    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_ENDPOINT"],
        api_version="2025-01-01-preview",
    )
    resp = client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.choices[0].message.content.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[:-3]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  [WARN] Could not parse LLM response for {scenario}: {e}")
        print(f"  Raw response:\n{raw}")
        data = []

    allowed = SCENARIO_COMPONENTS[scenario]
    primary = SCENARIO_PRIMARY[scenario]
    elements = {
        Element(d["source"], d["target"], d["interaction"])
        for d in data
        if d.get("source") == primary and d.get("target") in allowed
           and d["source"] != d["target"] and d.get("interaction")
    }
    save_elements(elements, elements_path(LABEL, scenario))


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
