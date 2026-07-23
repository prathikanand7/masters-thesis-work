"""
run_agent_extra.py — H3 additional conditions for the holistic 5-condition design
-----------------------------------------------------------------------------------
The holistic H3 experiment (see experiments/H3/README.md) tests five conditions
across S1, S2, S3, S4:

  1. Source only              -> this script, output: C_source_only/
  2. Trace only                -> already collected as Aprime_traces_only/ (run_agent.py --all --no-source)
  3. Diagram only              -> this script, output: D_diagram_only/
  4. Source + Trace            -> already collected as A_no_diagrams/ (run_agent.py --all)
  5. Source + Trace + Diagram  -> already collected as B_with_diagrams/ (run_agent.py --all)

This script runs the two NEW conditions only (source-only, diagram-only), for real,
against the same live Azure OpenAI deployment used for the other three conditions.
No responses are fabricated or hand-written.

Usage:
    python run_agent_extra.py --all
    python run_agent_extra.py --condition source --scenario S1
    python run_agent_extra.py --condition diagram --scenario S4
"""
import argparse
import json
import os
import pathlib

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore

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
CONDITIONS = ["source", "diagram"]

TASK_PROMPT_SOURCE_ONLY = """\
You are analysing a scenario in the CPSCore C++ framework.

Given the context below, answer the following three questions:
1. List every **component** involved in this scenario (use the exact module names).
2. List every **interaction** between components in the format:
   `Source → Target : MethodName`
3. In 3–5 sentences, **explain the execution flow** of this scenario.

Be precise. Only include components and interactions directly evidenced by the
source code provided. No runtime trace or diagram is available for this
condition — reason only from the source. Do not hallucinate.
"""

TASK_PROMPT_DIAGRAM_ONLY = """\
You are analysing a scenario in the CPSCore C++ framework.

Given the context below, answer the following three questions:
1. List every **component** involved in this scenario (use the exact module names).
2. List every **interaction** between components in the format:
   `Source → Target : MethodName`
3. In 3–5 sentences, **explain the execution flow** of this scenario.

Be precise. You are given only a component interaction diagram (no source code,
no runtime trace). Base your answer strictly on the diagram provided. Do not
hallucinate interactions not present in it.
"""


def load_file_safe(path: pathlib.Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"[FILE NOT FOUND: {path}]"


def format_elements_json(path: pathlib.Path) -> str:
    if not path.exists():
        return f"[FILE NOT FOUND: {path}]"
    with open(path, encoding="utf-8") as f:
        elements = json.load(f)
    lines = ["Component interactions identified by full-pipeline analysis (C5):"]
    for e in elements:
        lines.append(f"  {e['source']} → {e['target']} : {e['interaction']}")
    return "\n".join(lines)


def build_context(scenario: str, condition: str) -> str:
    if condition == "source":
        snippet = load_file_safe(SCENARIOS_DIR / scenario / "source_snippet.txt")
        return f"## Relevant source code\n\n```cpp\n{snippet}\n```\n"
    elif condition == "diagram":
        elements_text = format_elements_json(H1_C5_DIR / scenario / "sequence.json")
        return f"## Component interaction diagram (C5 full-pipeline output)\n\n{elements_text}\n"
    raise ValueError(condition)


def run_condition(condition: str, scenario: str) -> str:
    context = build_context(scenario, condition)
    task_prompt = TASK_PROMPT_SOURCE_ONLY if condition == "source" else TASK_PROMPT_DIAGRAM_ONLY
    prompt = f"{task_prompt}\n\n## Context\n\n{context}"

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


def save_response(condition: str, scenario: str, response: str) -> None:
    subdir = "C_source_only" if condition == "source" else "D_diagram_only"
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
    args = parser.parse_args()

    if args.all:
        pairs = [(c, s) for c in CONDITIONS for s in SCENARIOS]
    elif args.condition and args.scenario:
        pairs = [(args.condition, args.scenario)]
    else:
        parser.error("Provide --all or both --condition and --scenario")

    for condition, scenario in pairs:
        print(f"Running condition {condition} x {scenario} ...")
        response = run_condition(condition, scenario)
        save_response(condition, scenario, response)


if __name__ == "__main__":
    main()
