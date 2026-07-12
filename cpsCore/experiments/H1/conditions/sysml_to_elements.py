"""
sysml_to_elements.py — parse SysML v2 text files into Element sets
-------------------------------------------------------------------
Parses the structural and sequence SysML files produced by the full pipeline
(sysml_structural_model.sysml, sysml_sequence_model.sysml) and extracts
inter-component interactions as Element(source, target, interaction) triples.

Parsing approach:
- Structural: looks for 'connection' blocks or 'connect X to Y' lines,
  extracts component-level source/target using the component map.
- Sequence: looks for 'message' lines with 'from X to Y : Z' patterns,
  extracts component-level source/target using the component map.
- Falls back to interaction name extraction from the SysML text.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import Element, path_to_component, SCENARIO_COMPONENTS

# Known CPSCore top-level component names (used for direct text matching)
COMPONENT_NAMES = {
    "Aggregation", "Configuration", "Framework",
    "Logging", "Synchronization", "Utilities"
}

# ── Pattern: connect <A>::<part> to <B>::<part>  ───────────────────────────
_CONNECT_RE = re.compile(
    r"connect\s+([\w:]+)\s+to\s+([\w:]+)",
    re.IGNORECASE
)
# ── Pattern: message mX from <A> to <B> : '<interaction>'  ────────────────
_MSG_RE = re.compile(
    r"message\s+\w+\s+from\s+([\w.]+)\s+to\s+([\w.]+)\s*:\s*['\"]?([\w.]+)['\"]?",
    re.IGNORECASE
)
# ── Pattern: connection : <Interface> ─────────────────────────────────────
_IFACE_RE = re.compile(r"connection\s*:\s*(\w+)", re.IGNORECASE)


def _extract_component(token: str) -> str | None:
    """Extract component name from a token like 'sync.simpleRunner' or
    'Synchronization::simpleRunner'. Returns None if not recognisable."""
    # Strip qualifier suffix (::part or .part)
    base = re.split(r"[:.]", token)[0]
    if base in COMPONENT_NAMES:
        return base
    return None


def parse_sysml_structural(path: pathlib.Path) -> set[Element]:
    """Parse a SysML structural model file → Element set."""
    elements: set[Element] = set()
    if not path.exists():
        print(f"  [SKIP] {path} not found")
        return elements

    text = path.read_text()
    lines = text.splitlines()

    current_iface = None
    for line in lines:
        stripped = line.strip()

        # Track current interface name for the next connect line
        m_iface = _IFACE_RE.search(stripped)
        if m_iface:
            current_iface = m_iface.group(1)

        m_conn = _CONNECT_RE.search(stripped)
        if m_conn:
            src = _extract_component(m_conn.group(1))
            tgt = _extract_component(m_conn.group(2))
            if src and tgt and src != tgt:
                interaction = current_iface or "connection"
                elements.add(Element(src, tgt, interaction))

    return elements


def parse_sysml_sequence(path: pathlib.Path) -> set[Element]:
    """Parse a SysML sequence model file → Element set."""
    elements: set[Element] = set()
    if not path.exists():
        print(f"  [SKIP] {path} not found")
        return elements

    text = path.read_text()
    for m in _MSG_RE.finditer(text):
        src  = _extract_component(m.group(1))
        tgt  = _extract_component(m.group(2))
        intr = m.group(3).strip("'\"").strip()
        if src and tgt and src != tgt and intr:
            elements.add(Element(src, tgt, intr))

    return elements
