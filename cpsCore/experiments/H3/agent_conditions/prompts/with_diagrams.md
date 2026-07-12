# Condition B Prompt Template — Source + Traces + Diagrams

Used by `run_agent.py` for condition B. The agent receives both the trace and the
generated structural + sequence diagrams from the full pipeline (H1 condition C5).

```
You are analysing a scenario in the CPSCore C++ framework.

Given the context below (trace data AND architectural diagrams), answer:
1. List every **component** involved in this scenario (use exact module names).
2. List every **interaction** between components in the format:
   `Source → Target : MethodName`
3. In 3–5 sentences, **explain the execution flow** of this scenario.

Use the diagrams to supplement your understanding of the trace data.
Be precise. Do not hallucinate components or interactions not present in the context.

## Context

[TRACE SLICE]

[STRUCTURAL DIAGRAM — SysML v2]

[SEQUENCE DIAGRAM — SysML v2]

[SOURCE SNIPPETS — if included]
```
