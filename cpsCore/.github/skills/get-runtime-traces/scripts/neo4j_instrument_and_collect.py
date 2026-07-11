from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Neo4j-driven instrumentation and trace collection")
    parser.add_argument("--workspace-root", type=Path, default=ROOT)
    parser.add_argument("--mapping-path", type=Path, default=SKILL_DIR / "instrumentation_mapping.csv")
    parser.add_argument("--query-log-path", type=Path, default=SKILL_DIR / "cypher_query.txt")
    parser.add_argument("--trace-output", type=Path, default=ROOT / "runtime_traces_hybrid.txt")
    parser.add_argument("--trace-command", type=str, default="")
    parser.add_argument("--fail-on-trace-command-error", action="store_true")
    parser.add_argument("--skip-neo4j-traces", action="store_true")
    return parser.parse_args()


def run_python(script: Path, *args: str) -> None:
    command = [sys.executable, str(script), *args]
    subprocess.run(command, check=True)


def run_trace_command(command: str, workspace_root: Path, trace_output: Path, fail_on_error: bool) -> None:
    trace_output.parent.mkdir(parents=True, exist_ok=True)
    with trace_output.open("w", encoding="utf-8") as handle:
        completed = subprocess.run(
            command,
            cwd=workspace_root,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if completed.stdout:
            handle.write(completed.stdout)
            if not completed.stdout.endswith("\n"):
                handle.write("\n")
        if completed.stderr:
            handle.write(completed.stderr)
            if not completed.stderr.endswith("\n"):
                handle.write("\n")
    if completed.returncode != 0:
        message = f"Trace command failed with code {completed.returncode}: {command}"
        if fail_on_error:
            raise SystemExit(message)
        print(message)
        print(f"Continuing because --fail-on-trace-command-error was not set. Captured stderr remains in {trace_output}")


def main() -> int:
    args = parse_args()
    workspace_root = args.workspace_root.resolve()

    gen_script = SKILL_DIR / "scripts" / "generate_instrumentation_mapping.py"
    apply_script = SKILL_DIR / "scripts" / "apply_instrumentation_from_mapping.py"
    neo4j_traces_script = SKILL_DIR / "scripts" / "get_runtime_traces.py"

    run_python(
        gen_script,
        "--workspace-root",
        str(workspace_root),
        "--mapping-path",
        str(args.mapping_path),
        "--query-log-path",
        str(args.query_log_path),
    )

    run_python(
        apply_script,
        "--workspace-root",
        str(workspace_root),
        "--mapping-path",
        str(args.mapping_path),
    )

    if not args.skip_neo4j_traces:
        run_python(neo4j_traces_script)

    if args.trace_command:
        run_trace_command(
            args.trace_command,
            workspace_root,
            args.trace_output,
            args.fail_on_trace_command_error,
        )
        print(f"Runtime trace output: {args.trace_output}")

    print("Neo4j-driven instrumentation workflow completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
