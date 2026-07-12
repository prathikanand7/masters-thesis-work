# Condition A Prompt Template — Source + Traces Only

Used by `run_agent.py` for condition A. The agent receives NO diagrams.

```
You are analysing a scenario in the CPSCore C++ framework.

Given the context below, answer the following three questions:
1. List every **component** involved in this scenario (use the exact module names from the trace).
2. List every **interaction** between components in the format:
   `Source → Target : MethodName`
3. In 3–5 sentences, **explain the execution flow** of this scenario.

Be precise. Only include components and interactions that are directly evidenced by the
trace data or source code below. Do not hallucinate.

## Context

[TRACE SLICE]

[SOURCE SNIPPETS — if included]
```
