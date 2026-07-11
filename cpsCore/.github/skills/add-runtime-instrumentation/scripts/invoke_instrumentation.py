#!/usr/bin/env python3
"""
Wrapper script for the add-runtime-instrumentation skill.
Enables invocation from agent or command line.

Usage:
    python invoke_instrumentation.py apply [--exclude-tests] [--renaissance-root PATH] [--cpscore-root PATH]
    python invoke_instrumentation.py remove [--renaissance-root PATH] [--cpscore-root PATH]
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

def run_powershell_script(script_path, args):
    """Run a PowerShell script with given arguments."""
    cmd = ["powershell", "-NoProfile", "-File", str(script_path)] + args
    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode

def main():
    parser = argparse.ArgumentParser(
        description="Apply or remove runtime instrumentation to cpsCore"
    )
    parser.add_argument(
        "action",
        choices=["apply", "remove"],
        help="Action to perform: apply or remove instrumentation"
    )
    parser.add_argument(
        "--exclude-tests",
        action="store_true",
        help="Exclude test files during instrumentation (faster iteration)"
    )
    parser.add_argument(
        "--renaissance-root",
        default="C:\\Code\\clang-exp",
        help="Path to renaissance_clang repository root"
    )
    parser.add_argument(
        "--cpscore-root",
        default="C:\\Code\\CSP\\cpsCore",
        help="Path to cpsCore repository root"
    )
    
    args = parser.parse_args()
    
    # Get the scripts directory (relative to this file)
    scripts_dir = Path(__file__).parent / "scripts"
    
    if args.action == "apply":
        script = scripts_dir / "apply_tracing.ps1"
        ps_args = [
            f"-RenaissanceRoot '{args.renaissance_root}'",
            f"-CpsCoreRoot '{args.cpscore_root}'"
        ]
        if args.exclude_tests:
            ps_args.append("-ExcludeTests")
    else:  # remove
        script = scripts_dir / "remove_tracing.ps1"
        ps_args = [
            f"-RenaissanceRoot '{args.renaissance_root}'",
            f"-CpsCoreRoot '{args.cpscore_root}'"
        ]
    
    if not script.exists():
        print(f"Error: Script not found at {script}", file=sys.stderr)
        return 1
    
    print(f"Running: {script}")
    print(f"Action: {args.action}")
    if args.action == "apply" and args.exclude_tests:
        print("(Excluding test files)")
    
    return run_powershell_script(script, ps_args)

if __name__ == "__main__":
    sys.exit(main())
