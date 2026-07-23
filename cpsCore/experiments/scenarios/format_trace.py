"""
format_trace.py — Convert clang-exp trace formats to standard pipe-delimited format
-------------------------------------------------------------------------------------
Handles two input formats:

  1. Pipe-separated (clang-exp tool output pasted with | separators):
       HH:MM:SS.mmm | clientFn | clientComp | serverEvent | serverComp | clientClass | sourceFile

  2. Comma-separated [TRACE] format (raw clang-exp output):
       [TRACE] HH:MM:SS.mmm, clientFn, clientComp, serverEvent, serverComp, clientClass, sourceFile

Output (standard 8-column pipe-delimited format):
  EventTimestamp|EventName|ClientComponent|ClientFunction|ServerComponent|ServerFunction|RelationshipType|InterfaceNames

Usage:
    python format_trace.py full_trace.txt              # convert in place
    python format_trace.py full_trace.txt --out out.txt
    python format_trace.py trace.txt --compare trace_slice.txt  # compare after conversion
"""
import argparse
import pathlib

HEADER = "EventTimestamp|EventName|ClientComponent|ClientFunction|ServerComponent|ServerFunction|RelationshipType|InterfaceNames"
DATE = "2026-07-18"


def parse_row(line: str) -> tuple | None:
    """Parse a row from either format. Returns 7-tuple or None."""
    line = line.strip()
    if not line or line.startswith("EventTimestamp") or line.startswith("===") or line.startswith("All tests") or line.startswith("Filters"):
        return None

    # [TRACE] comma format
    if line.startswith("[TRACE]"):
        line = line[len("[TRACE]"):].strip()
        parts = [p.strip() for p in line.split(",", 6)]
    else:
        parts = [p.strip() for p in line.split("|")]

    if len(parts) != 7:
        return None
    return tuple(parts)


def to_row(parts: tuple) -> str:
    time_str, client_fn, client_comp, server_event, server_comp, client_class, _ = parts
    ts = f"{DATE}T{time_str}000Z"
    client_fn_full = f"{client_class.split('<')[0]}.{client_fn}" if client_class else client_fn
    iface = server_event.split(".")[0] if "." in server_event else server_event
    return f"{ts}|{server_event}|{client_comp}|{client_fn_full}|{server_comp}|{server_event}|Command|{iface}"


def convert_text(text: str) -> list[str]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("EventTimestamp") or line.startswith("===") or line.startswith("All tests") or line.startswith("Filters"):
            continue
        # [S4TRACE] lines are already in pipe-delimited format — pass through
        if line.startswith("[S4TRACE]"):
            rows.append(line[len("[S4TRACE]"):].strip())
            continue
        parts = parse_row(line)
        if parts:
            rows.append(to_row(parts))
    return rows


def convert_file(input_path: pathlib.Path, output_path: pathlib.Path) -> list[str]:
    rows = convert_text(input_path.read_text(encoding="utf-8"))
    output_path.write_text(HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=pathlib.Path)
    parser.add_argument("--out", "-o", type=pathlib.Path, default=None)
    parser.add_argument("--compare", "-c", type=pathlib.Path, default=None,
                        help="Compare converted output against this file (line by line)")
    args = parser.parse_args()

    output = args.out or args.input
    rows = convert_file(args.input, output)
    print(f"Converted {len(rows)} events → {output}")

    if args.compare:
        ref_lines = [l for l in args.compare.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("EventTimestamp")]
        if rows == ref_lines:
            print(f"✓ IDENTICAL to {args.compare}")
        else:
            print(f"✗ DIFFERS from {args.compare} ({len(rows)} vs {len(ref_lines)} events)")
            for i, (a, b) in enumerate(zip(rows, ref_lines), 1):
                if a != b:
                    print(f"  Line {i+1}:")
                    print(f"    converted: {a}")
                    print(f"    reference: {b}")
            if len(rows) != len(ref_lines):
                print(f"  Extra rows in {'converted' if len(rows) > len(ref_lines) else 'reference'}:")
                for r in (rows if len(rows) > len(ref_lines) else ref_lines)[min(len(rows), len(ref_lines)):]:
                    print(f"    {r}")


if __name__ == "__main__":
    main()
