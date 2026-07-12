# Experiments

All three hypotheses share the **same scenario set, the same Neo4j graph, and the same
CPSCore trace files** already present in this workspace.  
Do NOT create separate clones or workspaces — every new artifact (reference diagrams,
scores, agent transcripts) lives here so ground truth is never duplicated.

```
experiments/
├── scenarios/          ← shared scenario definitions (used by H1 + H2 + H3)
├── H1/                 ← Static+Dynamic evidence improves reconstruction
│   ├── reference_diagrams/   ground-truth SysML/JSON per scenario
│   ├── conditions/           outputs of 5 pipeline conditions per scenario
│   └── scoring/              precision/recall/F1 scripts + results
├── H2/                 ← Guided instrumentation improves signal-to-noise
│   ├── instrumentation/      full vs. guided trace files per scenario
│   ├── metrics/              diagram size + coverage scripts + results
│   └── expert_rating/        rating form + collected responses
└── H3/                 ← Reconstructed models improve agent task performance
    ├── agent_conditions/     prompt harness + raw responses (2 conditions)
    └── scoring/              component/interaction scoring scripts + results
```

## Dependency flow

```
scenarios/  ──►  H1/reference_diagrams/  ──►  H2/metrics/ (coverage)
                                          ──►  H3/scoring/ (ground truth)
```

H1 **must** be completed (reference diagrams validated) before H2 coverage
metrics and H3 ground truth are finalised.

## Quick-start per hypothesis

| Hypothesis | First action | Blocking? |
|---|---|---|
| H1 | Write scenario definitions in `scenarios/`, then manually build reference diagrams | Yes — gates H2 coverage and H3 ground truth |
| H2 expert ratings | Send `H2/expert_rating/rating_form.md` today | Calendar-bound, not effort-bound |
| H3 | Derive ground truth from H1 reference diagrams once H1 is done | Depends on H1 |

## Scenarios selected

See `scenarios/scenarios.md` for the full rationale.  
Short list (update once finalised):

| ID | Name | Pattern exercised |
|---|---|---|
| S1 | TBD | Client → server request (IDC API) |
| S2 | TBD | Multi-hop pub-sub chain (boost::signals2) |
| S3 | TBD | Fault / retry path (INetworkLayer) |
