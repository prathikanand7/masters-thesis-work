#!/usr/bin/env python3
"""
Generate a SysML v2 plaintext sequence diagram from processed_traces.csv.

Applies the same grouping / numbering rules as the HTML diagram:
  Rule 1 -- consecutive events with same event_name+event_type but different
            event_parameter -> collapsed message + /* note: ... */ comment listing
            each sub-item with its own global sequence number.
  Rule 2 -- same event_name+event_type+event_parameter but different
            sub_parameter_name_values -> individual messages each with inline
            attribute declarations showing extracted key-value pairs.
  Rule 3 -- identical run (same param AND same sp) -> single message.
  Rule 4 -- single event with sp values -> message + inline attribute declarations.

Output style follows the typed-message SysML v2 sample:
  - Typed message hierarchy (SynchronousCall, ReturnMessage, AsynchronousMessage)
  - Message parts with ref from/to Lifelines and attribute :>> label
  - Participant part defs with auto-generated ports
  - System assembly part def with deduplicated connect statements
  - InteractionScenario-based Scenario part def

Usage:
    python gen_sysml_sequence.py <csv_path> [-o <output.sysml>] [--package NAME]

Example:
    python gen_sysml_sequence.py processed_traces.csv -o general_sequence_diagram.sysml
"""

import argparse
import csv
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sp_values(sp: str) -> str:
    """Extract list values from a Python-style dict string, joined with ', '."""
    if not sp or sp in ("{}", ""):
        return ""
    vals = []
    for m in re.finditer(r"\[([^\]]+)\]", sp):
        for item in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
            vals.append(item)
    return ", ".join(vals)


def parse_sp_dict(sp: str) -> list:
    """
    Parse a Python-style sp dict string into (key, joined_values) tuples.

    Example input : {'Size': ['1900', '1160'], 'Mode': ['UNCOUPLED']}
    Example output: [('Size', '1900, 1160'), ('Mode', 'UNCOUPLED')]
    """
    if not sp or sp in ("{}", ""):
        return []
    result = []
    for m in re.finditer(r"'([^']+)':\s*\[([^\]]*)\]", sp):
        key = m.group(1)
        values = re.findall(r"['\"]([^'\"]+)['\"]", m.group(2))
        joined = ", ".join(values) if values else ""
        if joined:
            result.append((key, joined))
    return result


def arrow_base_label(row: dict) -> str:
    """Return 'EventName (Param)' or 'EventName' -- no truncation."""
    label = row["en"]
    if row["ep"]:
        label += f" ({row['ep']})"
    return label


def arrow_detail_label(row: dict) -> str:
    """Base label plus sp values -- used in hover-group note lines."""
    label = arrow_base_label(row)
    v = sp_values(row["sp"])
    if v:
        label += f": {v}"
    return label


def label_to_part_name(label: str, et: str, seq: int) -> str:
    """
    Convert a display label and event type to a valid SysML part name.
    """
    m = re.match(r"^([\w]+)(?:\s*\(([^)]+)\))?", label.strip())
    if m:
        en = m.group(1)
        ep = m.group(2) or ""
    else:
        en = re.sub(r"[^a-zA-Z0-9]", "", label) or f"m{seq}"
        ep = ""

    en_lc = en[0].lower() + en[1:] if en else f"m{seq}"
    suffix = {"Command": "cmd", "Reply": "rpl"}.get(et, "ntf")

    if ep:
        ep_clean = re.sub(r"[^a-zA-Z0-9]", "_", ep).strip("_")
        return f"{en_lc}_{ep_clean}_{suffix}_{seq}"
    return f"{en_lc}_{suffix}_{seq}"


# ---------------------------------------------------------------------------
# Row processing  (same logic as processRows() in the HTML)
# ---------------------------------------------------------------------------

def process_rows(rows: list, no_collapse: bool = False) -> list:
    """
    Apply Rules 1-4 and return a list of display items.

    Each item is a dict with:
      type    : 'arrow' | 'hover'
      et      : event_type string
      src     : source participant name
      tgt     : target participant name
      label   : message label (no sequence number yet)
      spval   : joined sp-values string  (type='arrow' only, may be '')
      sp_raw  : raw sp string for attribute generation (type='arrow' only)
      details : list of raw detail strings (type='hover' only)

    If no_collapse is True, Rules 1-3 are skipped and every row is emitted
    as an individual arrow (one message per trace entry).
    """
    items = []
    i = 0

    while i < len(rows):
        r = rows[i]

        # ------------------------------------------------------------------ #
        # Command block -- collect consecutive Command(+Reply) pairs          #
        # ------------------------------------------------------------------ #
        if r["et"] == "Command":
            cmd_pairs = []
            j = i
            while (
                j < len(rows)
                and rows[j]["et"] == "Command"
                and rows[j]["en"] == r["en"]
            ):
                cmd = rows[j]
                has_reply = (
                    j + 1 < len(rows)
                    and rows[j + 1]["et"] == "Reply"
                    and rows[j + 1]["en"] == r["en"]
                )
                cmd_pairs.append({"cmd": cmd, "has_reply": has_reply})
                j = j + 2 if has_reply else j + 1

            if len(cmd_pairs) == 1:
                cmd = cmd_pairs[0]["cmd"]
                base = arrow_base_label(cmd)
                spv  = sp_values(cmd["sp"])
                items.append({
                    "type": "arrow", "et": "Command",
                    "src": cmd["cmd_src"], "tgt": cmd["cmd_tgt"],
                    "label": base, "spval": spv, "sp_raw": cmd["sp"],
                })
                if cmd_pairs[0]["has_reply"]:
                    items.append({
                        "type": "arrow", "et": "Reply",
                        "src": cmd["cmd_tgt"], "tgt": cmd["cmd_src"],
                        "label": cmd["en"], "spval": "", "sp_raw": "",
                    })
            else:
                all_eps = list(dict.fromkeys(c["cmd"]["ep"] for c in cmd_pairs))
                if len(all_eps) > 1:
                    # Rule 1 -- hover group (different event_parameter)
                    details = [arrow_detail_label(c["cmd"]) for c in cmd_pairs]
                    summary = f"{r['en']} ({len(cmd_pairs)})"
                    items.append({
                        "type": "hover", "et": "Command",
                        "src": cmd_pairs[0]["cmd"]["cmd_src"],
                        "tgt": cmd_pairs[0]["cmd"]["cmd_tgt"],
                        "label": summary, "details": details,
                    })
                else:
                    # Same param -- emit individually
                    for c in cmd_pairs:
                        cmd = c["cmd"]
                        base = arrow_base_label(cmd)
                        spv  = sp_values(cmd["sp"])
                        items.append({
                            "type": "arrow", "et": "Command",
                            "src": cmd["cmd_src"], "tgt": cmd["cmd_tgt"],
                            "label": base, "spval": spv, "sp_raw": cmd["sp"],
                        })
                        if c["has_reply"]:
                            items.append({
                                "type": "arrow", "et": "Reply",
                                "src": cmd["cmd_tgt"], "tgt": cmd["cmd_src"],
                                "label": cmd["en"], "spval": "", "sp_raw": "",
                            })
            i = j
            continue

        # ------------------------------------------------------------------ #
        # Reply not consumed above                                            #
        # ------------------------------------------------------------------ #
        if r["et"] == "Reply":
            items.append({
                "type": "arrow", "et": "Reply",
                "src": r["source_id"], "tgt": r["target_id"],
                "label": r["en"], "spval": "", "sp_raw": "",
            })
            i += 1
            continue

        # ------------------------------------------------------------------ #
        # Notification run                                                     #
        # ------------------------------------------------------------------ #
        notif_src = r["source_id"]
        notif_tgt = r["target_id"]

        if no_collapse:
            # Emit every row as its own individual arrow
            base = arrow_base_label(r)
            spv  = sp_values(r["sp"])
            items.append({
                "type": "arrow", "et": "Notification",
                "src": notif_src, "tgt": notif_tgt,
                "label": base, "spval": spv, "sp_raw": r["sp"],
            })
            i += 1
            continue

        run = [r]
        j = i + 1
        while j < len(rows) and rows[j]["et"] == r["et"] and rows[j]["en"] == r["en"]:
            run.append(rows[j])
            j += 1

        if len(run) == 1:
            base = arrow_base_label(r)
            spv  = sp_values(r["sp"])
            items.append({
                "type": "arrow", "et": "Notification",
                "src": notif_src, "tgt": notif_tgt,
                "label": base, "spval": spv, "sp_raw": r["sp"],
            })
            i = j
            continue

        all_eps = list(dict.fromkeys(n["ep"] for n in run))
        if len(all_eps) > 1:
            # Rule 1 -- hover group (different event_parameter)
            details = [arrow_detail_label(n) for n in run]
            summary = f"{r['en']} ({len(run)})"
            items.append({
                "type": "hover", "et": "Notification",
                "src": notif_src, "tgt": notif_tgt,
                "label": summary, "details": details,
            })
        else:
            all_sps = list(dict.fromkeys(n["sp"] for n in run))
            if len(all_sps) > 1:
                # Rule 2 -- different sub_parameter_name_values -> individual arrows
                for n in run:
                    base = arrow_base_label(n)
                    spv  = sp_values(n["sp"])
                    items.append({
                        "type": "arrow", "et": "Notification",
                        "src": notif_src, "tgt": notif_tgt,
                        "label": base, "spval": spv, "sp_raw": n["sp"],
                    })
            else:
                # Rule 3 -- identical run -> single arrow
                base = arrow_base_label(run[0])
                spv  = sp_values(run[0]["sp"])
                items.append({
                    "type": "arrow", "et": "Notification",
                    "src": notif_src, "tgt": notif_tgt,
                    "label": base, "spval": spv, "sp_raw": run[0]["sp"],
                })

        i = j

    return items


# ---------------------------------------------------------------------------
# SysML v2 emitter
# ---------------------------------------------------------------------------

MSG_TYPE = {
    "Command":      "SynchronousCall",
    "Reply":        "ReturnMessage",
    "Notification": "AsynchronousMessage",
}


def build_sysml(items: list, participants: list, package_name: str) -> str:
    """
    Emit SysML v2 textual notation following the typed-message sample style.

    Structure:
      package '...' {
          private import ScalarValues::String;

          // Base definitions
          part def ControlSystem { attribute componentName : String; }
          part def InteractionScenario;
          part def Lifeline;
          part def Message { attribute label; ref from/to : Lifeline; }
          part def SynchronousCall     :> Message;
          part def ReturnMessage       :> Message;
          part def AsynchronousMessage :> Message;

          // Participant definitions (auto-generated ports)
          part def A :> ControlSystem { port cmdOut; port ntfOut; ... }
          part def B :> ControlSystem { port cmdIn;  port ntfIn;  ... }

          // System assembly
          part def System {
              part a : A;  part b : B;
              connect a.cmdOut to b.cmdIn;
              ...
          }

          // Interaction scenario
          part def Scenario :> InteractionScenario {
              part a : Lifeline;
              part b : Lifeline;

              // [Command]
              part activateBeFe_cmd_1 : SynchronousCall {
                  ref from : Lifeline = a;
                  ref to   : Lifeline = b;
                  attribute :>> label = "1. ActivateBeFe";
              }
              ...
          }
      }
    """
    indent = "    "
    inner  = indent * 2
    inner3 = indent * 3

    lines: list[str] = [
        f"package '{package_name}' {{",
        f"{indent}private import ScalarValues::String;",
        "",
        f"{indent}// =========================================================================",
        f"{indent}// Minimal portable base definitions",
        f"{indent}// =========================================================================",
        "",
        f"{indent}part def ControlSystem {{",
        f"{inner}attribute componentName : String;",
        f"{indent}}}",
        "",
        f"{indent}part def InteractionScenario;",
        f"{indent}part def Lifeline;",
        "",
        f"{indent}part def Message {{",
        f"{inner}attribute label : String;",
        f"{inner}ref from : Lifeline;",
        f"{inner}ref to   : Lifeline;",
        f"{indent}}}",
        "",
        f"{indent}part def SynchronousCall     :> Message;"
        + "   // CMD -- synchronous request expecting a reply",
        f"{indent}part def ReturnMessage       :> Message;"
        + "   // RPL -- reply to a synchronous call",
        f"{indent}part def AsynchronousMessage :> Message;"
        + "   // NTF -- fire-and-forget notification",
        "",
    ]

    # Determine which ports each participant needs and build connect statements
    ports_needed: dict[str, set] = {p: set() for p in participants}
    seen_connects: set             = set()
    connect_stmts: list[str]       = []

    for it in items:
        et  = it["et"]
        src = it["src"]
        tgt = it["tgt"]
        if et == "Command":
            ports_needed[src].add("cmdOut")
            ports_needed[tgt].add("cmdIn")
            key = (src, "cmdOut", tgt, "cmdIn")
        elif et == "Reply":
            ports_needed[src].add("rplOut")
            ports_needed[tgt].add("rplIn")
            key = (src, "rplOut", tgt, "rplIn")
        else:
            ports_needed[src].add("ntfOut")
            ports_needed[tgt].add("ntfIn")
            key = (src, "ntfOut", tgt, "ntfIn")
        if key not in seen_connects:
            seen_connects.add(key)
            connect_stmts.append(
                f"{inner}connect {src.lower()}.{key[1]} to {tgt.lower()}.{key[3]};"
            )

    # Participant Definitions
    lines += [
        f"{indent}// =========================================================================",
        f"{indent}// Participant Definitions",
        f"{indent}// =========================================================================",
        "",
    ]
    for p in participants:
        lines.append(f"{indent}part def {p} :> ControlSystem {{")
        lines.append(f"{inner}attribute :>> componentName = \"{p}\";")
        for port_name in sorted(ports_needed[p]):
            lines.append(f"{inner}port {port_name};")
        lines.append(f"{indent}}}")
        lines.append("")

    # System Assembly
    lines += [
        f"{indent}// =========================================================================",
        f"{indent}// System Assembly",
        f"{indent}// =========================================================================",
        "",
        f"{indent}part def System {{",
    ]
    for p in participants:
        lines.append(f"{inner}part {p.lower()} : {p};")
    if connect_stmts:
        lines.append("")
        lines += connect_stmts
    lines.append(f"{indent}}}")
    lines.append("")

    # Interaction Scenario
    lines += [
        f"{indent}// =========================================================================",
        f"{indent}// Interaction Scenario",
        f"{indent}// =========================================================================",
        "",
        f"{indent}part def Scenario :> InteractionScenario {{",
    ]
    for p in participants:
        lines.append(f"{inner}part {p.lower()} : Lifeline;")
    lines.append("")

    seq = 1
    for it in items:
        src      = it["src"].lower()
        tgt      = it["tgt"].lower()
        et       = it["et"]
        msg_type = MSG_TYPE.get(et, "AsynchronousMessage")
        pname    = label_to_part_name(it["label"], et, seq)

        lines.append(f"{inner}// [{et}]")

        if it["type"] == "hover":
            numbered_label = f"{seq}. {it['label']}"
            lines.append(f"{inner}part {pname} : {msg_type} {{")
            lines.append(f"{inner3}ref from : Lifeline = {src};")
            lines.append(f"{inner3}ref to   : Lifeline = {tgt};")
            lines.append(f"{inner3}attribute :>> label = \"{numbered_label}\";")
            lines.append(f"{inner}}}")
            note_parts = []
            for d in it["details"]:
                seq += 1
                note_parts.append(f"{seq}. {d}")
            lines.append(f"{inner}/* note: {', '.join(note_parts)} */")

        else:
            numbered_label = f"{seq}. {it['label']}"
            lines.append(f"{inner}part {pname} : {msg_type} {{")
            lines.append(f"{inner3}ref from : Lifeline = {src};")
            lines.append(f"{inner3}ref to   : Lifeline = {tgt};")
            lines.append(f"{inner3}attribute :>> label = \"{numbered_label}\";")
            lines.append(f"{inner}}}")
            for key, val in parse_sp_dict(it.get("sp_raw", "")):
                lines.append(f"{inner}// {key}: {val}")

        seq += 1

    lines += [
        "",
        f"{indent}}}",
        "}",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV reader
# ---------------------------------------------------------------------------

def read_csv(path: Path) -> tuple:
    """
    Read processed_traces.csv.

    Returns (rows, participants) where:
      rows         -- list of dicts with keys: et, en, ep, sp, source_id, target_id
      participants -- ordered list of unique participant names (first-appearance order)
    """
    rows = []
    participants = []
    seen_parts = set()

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=",")
        for row in reader:
            src = row["source"]
            tgt = row["target"]
            for p in (src, tgt):
                if p not in seen_parts:
                    participants.append(p)
                    seen_parts.add(p)

            r = {
                "et": "Notification",
                "en": row["caller_func"],
                "ep": "",
                "sp": "",
                "source_id": src,
                "target_id": tgt,
                # Pre-cache command direction for use in process_rows
                "cmd_src": src,
                "cmd_tgt": tgt,
            }
            rows.append(r)

    return rows, participants


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a SysML v2 sequence diagram from processed_traces.csv"
    )
    parser.add_argument("csv", type=Path, help="Path to processed_traces.csv")
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output .sysml file (default: same folder as CSV, _sequence.sysml suffix)",
    )
    parser.add_argument(
        "--package", default="Sequence",
        help='SysML package name (default: "Sequence")',
    )
    parser.add_argument(
        "--no-collapse", action="store_true", default=False,
        help="Emit every trace row as its own individual message (skip Rules 1-3 collapsing)",
    )
    args = parser.parse_args()

    if not args.csv.is_file():
        print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.csv.with_name(args.csv.stem + "_sequence.sysml")

    rows, participants = read_csv(args.csv)
    items = process_rows(rows, no_collapse=args.no_collapse)
    sysml = build_sysml(items, participants, args.package)

    output.write_text(sysml, encoding="utf-8", newline="\n")
    print(f"Written {len(items)} messages -> {output}")


if __name__ == "__main__":
    main()