# H3 Agent Conditions

Two conditions, same agent (Claude API), different context.

## Condition A — source + traces only

The agent receives:
- Raw CPSCore source snippets for the scenario's components
- The scenario's `trace_slice.txt` from `experiments/scenarios/SX/`

**Does NOT receive:** any diagram.

## Condition B — source + traces + diagrams

The agent receives everything in condition A, plus:
- The full-pipeline generated structural diagram (`H1/conditions/C5_full_pipeline/SX/structural.sysml`)
- The full-pipeline generated sequence diagram (`H1/conditions/C5_full_pipeline/SX/sequence.sysml`)

## Running

```bash
# Both conditions, all scenarios
python run_agent.py --all

# One condition, one scenario
python run_agent.py --condition A --scenario S1
```

Responses are saved to `responses/<condition>/<scenario>_response.txt`.

## Agent prompt task

The agent is asked three things for each scenario:
1. List the components involved (by name).
2. List the interactions between components (source → target : method).
3. Explain the execution flow in 3-5 sentences.
