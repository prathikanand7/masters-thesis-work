"""
run_agent.py — H3 agent prompt harness
----------------------------------------
Sends prompts to Azure OpenAI for each condition × scenario.

Experiment 1 (default — source + traces):
  Condition A: traces + source snippets (no diagram)
  Condition B: traces + source snippets + C5 element list
  Output dirs: A_no_diagrams/, B_with_diagrams/

Experiment 2 (--no-source — traces only, stricter isolation):
  Condition A': traces only
  Condition B': traces + C5 element list
  Output dirs: Aprime_traces_only/, Bprime_traces_diagram/

Both conditions include:
  - trace_slice.txt      — filtered runtime trace events for the scenario
  - source_snippet.txt   — relevant C++ source functions (Experiment 1 only)

Condition B/B' additionally includes:
  - elements.json (C5)   — formatted as a readable component-interaction list
    (NOTE: C5 outputs elements.json, not .sysml files)

Requires: AZURE_ENDPOINT environment variable set (or in ../../.env).

Usage:
    python run_agent.py --condition A --scenario S1
    python run_agent.py --all
    python run_agent.py --all --no-source   # Experiment 2
"""
import argparse
import json
import os
import pathlib

# Load .env if present
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore

# resolve() makes __file__ absolute even when invoked with a relative path.
# run_agent.py lives at cpsCore/experiments/H3/agent_conditions/ → 4 parents up.
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent  # cpsCore/

if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

try:
    from openai import AzureOpenAI
except ImportError:
    raise SystemExit("Install openai: pip install openai")
SCENARIOS_DIR = ROOT / "experiments" / "scenarios"
H1_C5_DIR     = ROOT / "experiments" / "H1" / "conditions" / "C5_full_pipeline"
RESPONSES_DIR = pathlib.Path(__file__).parent / "responses"

SCENARIOS  = ["S1", "S2", "S3", "S4"]
CONDITIONS = ["A", "B"]

TASK_PROMPT_WITH_SOURCE = """\
You are analysing a scenario in the CPSCore C++ framework.

Given the context below, answer the following three questions:
1. List every **component** involved in this scenario (use the exact module names).
2. List every **interaction** between components in the format:
   `Source → Target : MethodName`
3. In 3–5 sentences, **explain the execution flow** of this scenario.

Be precise. Only include components and interactions directly evidenced by the
trace data or source code provided. Do not hallucinate.
"""

TASK_PROMPT_TRACES_ONLY = """\
You are analysing a scenario in the CPSCore C++ framework.

Given the context below, answer the following three questions:
1. List every **component** involved in this scenario (use the exact module names).
2. List every **interaction** between components in the format:
   `Source → Target : MethodName`
3. In 3–5 sentences, **explain the execution flow** of this scenario.

Be precise. Only include components and interactions directly evidenced by the
trace data provided. Do not hallucinate. If the trace is empty, state that no
runtime evidence is available and list only what you can confirm.
"""

TASK_PROMPT_TRACES_AND_DIAGRAM = """\
You are analysing a scenario in the CPSCore C++ framework.

Given the context below, answer the following three questions:
1. List every **component** involved in this scenario (use the exact module names).
2. List every **interaction** between components in the format:
   `Source → Target : MethodName`
3. In 3–5 sentences, **explain the execution flow** of this scenario.

Be precise. Include components and interactions evidenced by **either** the
runtime trace data **or** the component interaction diagram provided. The diagram
may capture fault-path or statically-visible interactions absent from the runtime
trace. Do not hallucinate interactions not present in either source.
"""


def load_file_safe(path: pathlib.Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"[FILE NOT FOUND: {path}]"


def format_elements_json(path: pathlib.Path) -> str:
    """Format C5 elements.json as a human-readable interaction list."""
    if not path.exists():
        return f"[FILE NOT FOUND: {path}]"
    with open(path, encoding="utf-8") as f:
        elements = json.load(f)
    lines = ["Component interactions identified by full-pipeline analysis (C5):"]
    for e in elements:
        lines.append(f"  {e['source']} → {e['target']} : {e['interaction']}")
    return "\n".join(lines)


def build_context(scenario: str, condition: str, include_source: bool) -> str:
    trace = load_file_safe(SCENARIOS_DIR / scenario / "trace_slice.txt")

    ctx = f"## Runtime trace slice\n\n```\n{trace}\n```\n"

    if include_source:
        snippet = load_file_safe(SCENARIOS_DIR / scenario / "source_snippet.txt")
        ctx += f"\n## Relevant source code\n\n```cpp\n{snippet}\n```\n"

    if condition == "B":
        elements_text = format_elements_json(H1_C5_DIR / scenario / "elements.json")
        ctx += f"\n## Component interaction diagram (C5 full-pipeline output)\n\n{elements_text}\n"

    return ctx


def run_condition(condition: str, scenario: str, include_source: bool) -> str:
    context = build_context(scenario, condition, include_source)
    if include_source:
        task_prompt = TASK_PROMPT_WITH_SOURCE
    elif condition == "B":
        task_prompt = TASK_PROMPT_TRACES_AND_DIAGRAM  # trace + C5 diagram both count
    else:
        task_prompt = TASK_PROMPT_TRACES_ONLY          # trace only, A'
    prompt = f"{task_prompt}\n\n## Context\n\n{context}"

    # NOTE: OPENAI_API_VERSION in .env may contain an invalid string ("2025-08-07").
    # Use the known-good preview version; update here if the endpoint is upgraded.
    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_ENDPOINT"],
        api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        api_version="2025-01-01-preview",
    )
    model = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-5")
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def save_response(condition: str, scenario: str, response: str, include_source: bool) -> None:
    if include_source:
        subdir = "A_no_diagrams" if condition == "A" else "B_with_diagrams"
    else:
        subdir = "Aprime_traces_only" if condition == "A" else "Bprime_traces_diagram"
    out_dir = RESPONSES_DIR / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scenario}_response.txt"
    out_path.write_text(response, encoding="utf-8")
    print(f"Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=CONDITIONS)
    parser.add_argument("--scenario",  choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--no-source", dest="no_source", action="store_true",
                        help="Experiment 2: omit source snippets from both conditions")
    args = parser.parse_args()
    include_source = not args.no_source

    if args.all:
        pairs = [(c, s) for c in CONDITIONS for s in SCENARIOS]
    elif args.condition and args.scenario:
        pairs = [(args.condition, args.scenario)]
    else:
        parser.error("Provide --all or both --condition and --scenario")

    exp = "1 (source+traces)" if include_source else "2 (traces only)"
    print(f"Running Experiment {exp}")
    for condition, scenario in pairs:
        label = condition if include_source else f"{condition}'"
        print(f"Running condition {label} × {scenario} ...")
        response = run_condition(condition, scenario, include_source)
        save_response(condition, scenario, response, include_source)


if __name__ == "__main__":
    main()
