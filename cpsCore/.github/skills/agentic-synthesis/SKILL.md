---
name: agentic-synthesis
description: Combines a scenario-scoped static dependency table and a scenario-scoped runtime trace into the final, judgement-adjudicated interaction set (elements.json / sequence.json) consumed by draw-sysml-sequence-model and draw-sysml-structural-model.
user-invocable: true
---

# agentic-synthesis

## Overview

This agent skill is Stage 5 of the reconstruction pipeline, between trace
collection (Stage 4: "add-runtime-instrumentation") and diagram
generation (Stage 6: "draw-sysml-sequence-model" /
"draw-sysml-structural-model"). It takes the static evidence
("get-interface-dependency-table" / "get-sequence-dependency-table")
and the dynamic evidence (the runtime trace from
"add-runtime-instrumentation"), both already scoped to the same
scenario, and decides the final interaction set.

It is the only stage in the pipeline that is **not** a fixed,
deterministic skill: the other ten skills follow a strict rule set given
their inputs, but this one has to judge, per interaction, whether a
single-source edge is real evidence the other source missed, or noise
the other source correctly left out. That judgement is not reducible to
a lookup table, which is why this skill's instructions below are
guidance for reasoning, not a strict rule set, unlike every other skill
in this repository.

## When to use

- You have both a static dependency table and a runtime trace for the
  same scenario (same primary component, same target components) and
  want the final, adjudicated interaction set before generating a SysML
  diagram.
- You want to understand or reproduce the reasoning behind an existing
  "elements.json"/"sequence.json" pair: which interactions were
  corroborated trivially, and which required a judgement call.
- Do **not** use this skill if you only want the raw, unexamined union of
  both sources (that is condition C4 in this thesis's terminology, or
  just tag-and-merge without adjudication) -- Stage 5 output is
  specifically the *pruned* set, condition C5.

## Inputs

Two evidence sources, each accepted in either format:

**Static evidence** (one of):
- "sequence_dependency_table.csv" / "interface_dependency_table.csv"
  (columns as documented in the "get-sequence-dependency-table" /
  "get-interface-dependency-table" skills), or
- an already-JSON static element list: an array of
  "{"source", "target", "interaction"}" objects.

**Dynamic evidence** (one of):
- the runtime trace CSV, schema
  "EventTimestamp|EventName|ClientComponent|ClientFunction|ServerComponent|ServerFunction|RelationshipType|InterfaceNames"
  (as produced by "add-runtime-instrumentation" / "collect_traces.py"), or
- an already-JSON dynamic element list, same shape as the static one,
  optionally with a "step"/timestamp field preserving execution order.

Both sources must already be scoped to the same scenario (scoping
happens upstream, at Stage 2 -- "text-to-cypher" / "cypher-to-output" --
and is applied identically to both sources before this skill runs; this
skill does not re-scope).

## Outputs

- **"elements.json"** (primary, canonical output): a deduplicated array
  of the final "{"source", "target", "interaction"}" triples, the
  structural element set consumed by "draw-sysml-structural-model".
- **"sequence.json"** (primary, canonical output): the same interactions
  in execution order, each step as
  "{"step", "source", "target", "interaction", "note"}", consumed by
  "draw-sysml-sequence-model".
- Optionally, a CSV rendering of the same final set (same columns as
  "sequence_dependency_table.csv") as a secondary, human-readable
  convenience output -- never the primary output, and never a
  substitute for the two JSON files, regardless of which format the
  inputs arrived in.

## MECHANISM

### Phase 1 -- Mechanical union (STRICT)

i. Normalise every row/object from both sources into the same
   "(source, target, interaction)" triple shape. Do not invent a triple
   that is not literally present in one of the two sources.

ii. Tag every triple with its provenance: "static-only", "dynamic-only",
    or "corroborated" (present in both, matched on the normalised
    triple).

iii. Preserve the dynamic evidence's execution order for "sequence.json"
     where available; place static-only triples at the position implied
     by the scenario's declared call structure (\eg immediately before
     or after the step that would trigger them), not at the end by
     default.

iv. Do not deduplicate across genuinely distinct call sites: if the
    static evidence lists the same "(source, target, interaction)"
    triple from two different call sites, that is a modelling decision
    for Stage 6, not something this skill collapses.

### Phase 2 -- Judgement (GUIDANCE, not a rule set)

For every triple tagged "corroborated": keep it, "note" stays empty.
Corroboration is the trivial case -- most interactions in most scenarios
will fall here, and no further reasoning is needed for them.

For every triple tagged "static-only" or "dynamic-only", reason about
which of the following it is, using whatever scenario context, source
comments, and test-case information is available -- this is a judgement
call, not a lookup:

- **Suppression** (static-only edge): is this a real interaction the
  scenario's runtime coverage simply did not exercise (\eg gated behind
  an error path, a log-level check, or a branch this test run does not
  take)? If so, **keep**, and write a "note" explaining why it is
  plausibly real despite the absence of trace corroboration. If instead
  it looks like an ordinary static over-approximation (a call site that
  belongs to a different function or a different scenario's primary
  component), **drop** it.

- **Indirect dispatch** (dynamic-only edge): does this reflect a real
  call path the static graph could not resolve (\eg a
  "boost::signals2" connection, a callback registered by identifier
  rather than call site, or another indirection the static extractor is
  known not to follow)? If so, **keep**, with a "note" explaining the
  dispatch mechanism. If it looks like an unrelated event that happened
  to fire during the same test run, **drop** it.

- When genuinely uncertain between keep and drop, prefer **keep** with a
  "note" flagging the uncertainty explicitly, rather than silently
  dropping a possibly-real interaction: the downstream use of this
  output includes human and agent comprehension (not only precision
  scoring), so an over-cautious keep with a visible caveat is a smaller
  failure than a silent, unrecoverable drop.

Every kept single-source triple must carry a non-empty, specific "note"
(not a generic "kept" placeholder) -- \eg "static-only, retained: gated
behind CPSLOG_ERROR under LogLevel::NONE, not exercised by this test run"
or "dynamic-only, retained: boost::signals2 dispatch, no static call
edge to the connected slot". An empty "note" is only ever valid on a
corroborated triple.

## Relationship to other skills

- Upstream: "get-interface-dependency-table" / "get-sequence-dependency-table"
  (static evidence), "add-runtime-instrumentation" (dynamic evidence).
- Downstream: "draw-sysml-structural-model" (reads "elements.json"),
  "draw-sysml-sequence-model" (reads "sequence.json").
- Not upstream of "draw-sequential-mermaid-general" /
  "draw-structural-mermaid": those two skills read the Stage 3 CSV
  tables directly and intentionally bypass this skill, for a
  whole-codebase visualisation rather than an adjudicated,
  scenario-specific one.
