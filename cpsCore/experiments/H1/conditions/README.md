# H1 Conditions — How to Run Each

All 5 conditions produce a structural diagram and a sequence diagram for each scenario.
Output goes into the corresponding `CX_<label>/SX/` subfolder as:
- `structural.sysml` (or `.json`)
- `sequence.sysml` (or `.json`)

---

## C1 — LLM-only (baseline floor)

Script: `run_c1_llm_only.py`

What it does: sends a plain-English scenario description to an LLM (no graph, no traces).
No existing skills are invoked.

```bash
python run_c1_llm_only.py --scenario S1
```

---

## C2 — Static-only

Invoke the pipeline with **only** the Neo4j static call-graph skills, skip trace ingestion.

Skills used:
- `get-interface-dependency-table`
- `draw-structural-mermaid` / `draw-sysml-structural-model`

Trace-ingestion skills (`get-runtime-traces`, `get-sequence-dependency-table`) are **skipped**.

Script: `run_c2_static_only.py`

---

## C3 — Dynamic-only

Invoke the pipeline with **only** the trace-ingestion skills, skip Neo4j graph.

Skills used:
- `get-runtime-traces`
- `get-sequence-dependency-table`
- `draw-sequential-mermaid-general` / `draw-sysml-sequence-model`

Neo4j skills (`get-interface-dependency-table`) are **skipped**.

Script: `run_c3_dynamic_only.py`

---

## C4 — Static + Dynamic (no agent synthesis)

Run both static and dynamic ingestion, but do **not** invoke the agent synthesis layer.
Output is the raw merged diagram from the ingestion skills.

Script: `run_c4_static_dynamic.py`

---

## C5 — Full pipeline (existing)

This is your current working pipeline. Run it as-is via the existing skills.

Script: `run_c5_full_pipeline.py` (thin wrapper over existing skill invocations)

---

## Flag convention

Each `run_cX_*.py` script accepts `--scenario [S1|S2|S3|all]` and writes outputs to
`conditions/CX_<label>/<scenario>/`.
