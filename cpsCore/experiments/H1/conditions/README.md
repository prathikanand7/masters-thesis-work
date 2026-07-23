# H1 Conditions — How to Run Each

All conditions produce an interactions set and a sequence diagram for each scenario.
Output goes into the corresponding `CX_<label>/SX/` subfolder as:
- `interactions.json` — set of (source, target, interaction) triples
- `sequence.json`     — ordered event list

Scenarios: **S1a, S1b, S2, S3**.


---

## C1 — LLM-only (baseline floor)

Script: `run_c1_llm_only.py`

What it does: sends a plain-English scenario description plus the source snippet to an
LLM (no static graph, no traces). Two chained calls: call 1 identifies unique
cross-component interactions; call 2 produces the ordered sequence.

```bash
python run_c1_llm_only.py --scenario S1a
python run_c1_llm_only.py --all
```

---

## C2 — Static-only

Uses the Neo4j static call-graph only; trace ingestion is skipped.

Input: Neo4j bolt connection (see `.env`).
Output: interaction set derived from graph traversal; sequence depth-ordered
(shorter call-graph path = earlier).

Script: `run_c2_static_only.py`

---

## C3 — Dynamic-only

Uses the runtime trace only; Neo4j graph is skipped.

Input: `experiments/scenarios/SX/trace_slice.txt`.
Output: interaction set = deduped trace events; sequence = all trace events in order.

Script: `run_c3_dynamic_only.py`

---

## C4 — Static + Dynamic union (no agent synthesis)

Computes C2 ∪ C3: union of the static and dynamic interaction sets.
Sequence backbone is copied from C3 (trace order).

Script: `run_c4_static_dynamic.py`

---

## C5 — Intersection (set-algebra baseline)

Computes C2 ∩ C3: only interactions confirmed by **both** the static graph and the
dynamic trace are retained. Sequence is C3 filtered to C2-confirmed events.


Script: `run_c5_intersection.py`

---


## gen_sysml.py — SysML v2 Visualisation (spec42 / SysML v2 Editor)

Reads the C5 intersection results (`interactions.json`, `sequence.json`) for each
scenario and writes **three self-contained SysML v2 files per scenario** into
`experiments/H1/conditions/sysml_diagrams/<scenario>/`:

| File | SysML pattern | spec42 view type |
|---|---|---|
| `interactions.sysml` | Structural architecture: `port def` per interface, `part def` per component with caller/callee ports, `connection` declarations | `InterconnectionView` |
| `sequence.sysml` | Interaction scenario: `part def :> InteractionScenario`, `Lifeline` per component, `SynchronousCall` per execution step | `SequenceView` |
| `views.sysml` | Imports both packages; declares `<Scenario>StructView` and `<Scenario>SeqView` | — |

`interactions.sysml` structure:
```sysml
port def <Interface>;                         // one per unique interaction name
part def <Component> {
    port calls<X>    : <X>;                   // caller side
    port provides<X> : <X>;                   // callee side
}
part <scenario>System {                       // top-level system instance
    part <name> : <Component>;
    connection : <X> connect <src>::calls<X> to <tgt>::provides<X>;
}
```

Notes from the LLM (in `sequence.json`) are rendered as SysML line comments.

```bash
python gen_sysml.py                  # all scenarios → H1/conditions/sysml_diagrams/
```

To visualise: open a `views.sysml` file in VS Code with the spec42 SysML v2 Editor
plugin active, then open the **View** tab to render `<Scenario>StructView`
(structural architecture) and `<Scenario>SeqView` (execution sequence).

---

## Flag convention

Each `run_cX_*.py` script accepts `--scenario [S1a|S1b|S2|S3]` or `--all` and writes
outputs to `conditions/CX_<label>/<scenario>/`.

The architectural edge map used for GT validation and instrumentation guidance is at
`architectural_diagrams/cpsCore_packages_annotated.puml` (cpscore root).
