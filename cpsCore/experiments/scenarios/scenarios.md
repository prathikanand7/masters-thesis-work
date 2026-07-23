# Scenario Definitions

These scenarios are reused verbatim across H1, H2, and H3.  
Do not define separate scenario sets for each hypothesis.

---

## S1a — Synchronized Runner Test (happy path)

**Test:** `TEST_CASE("Synchronized Runner Test")` in `tests/Synchronization/RunnerTest.cpp`  
**Pattern:** Master drives two runners through INIT → NORMAL → FINAL; all succeed  
**CPSCore components involved:** `Synchronization`, `Aggregation`, `Logging`  
**Key interactions:**
- `SynchronizedRunner.runSynchronized` → `Aggregator.getAll` (Aggregation)
- `SynchronizedRunner.runSynchronized` → `CPSLogger.instance` / `CPSLogger.flush` (Logging)
- `SynchronizedRunnerMaster.runStage` → `RAIILogStream.stream` (Logging)

**Why this stresses the architecture:**  
Exercises the synchronization pattern: shared-memory coordination between master
and runner threads, and the runner's dependency on the Aggregation component to
retrieve runnable objects.

**Trace filter (runtime_traces.txt):**
```
ClientComponent in [Synchronization] AND ServerComponent in [Aggregation, Logging]
AND ClientFunction contains [SynchronizedRunner, SynchronizedRunnerMaster]
```

---

## S1b — Synchronized Runner Timeout (failure path)

**Test:** `TEST_CASE("Synchronized Runner Timeout")` in `tests/Synchronization/RunnerTest.cpp`  
**Pattern:** One runner object exceeds the master's 1-second timeout → failure signal  
**CPSCore components involved:** `Synchronization`, `Logging`  
**Key interactions:**
- `SynchronizedRunnerMaster.runStage` → `RAIILogStream.stream` (Logging) — CPSLOG_WARN on timeout

**Note — static-only-visible interaction:**  
The test calls `CPSLogger::instance()->setLogLevel(LogLevel::NONE)` before triggering
the timeout, suppressing all runtime log output. The `CPSLOG_WARN` edge is visible
in source (C2 static) but absent from `runtime_traces.txt` (C3 dynamic cannot recover it).  
This makes S1b a deliberate mirror of S4's dynamic-only gap: here the gap is static-only.

**Trace filter (runtime_traces.txt):**
```
No events captured — logging is suppressed during this test.
```

---

## S2 — Configuration property mapping

**Pattern:** Configuration loading → property validation → logging  
**CPSCore components involved:** `Configuration`, `Logging`  
**Key interactions:**
- `PropertyMapper.add` → `RAIILogStream.stream`
- `PropertyMapper.addVector` / `addEnum` / `addEigen` → `RAIILogStream.stream`
- `PropertyMapper.mandatoryCheck` → `RAIILogStream.stream`

**Why this stresses the architecture:**  
A mostly-static, linear chain — serves as the "easy case" baseline.  
Expected to be well-reconstructed even by static-only conditions (H1 condition 2).

**Trace filter:**
```
ClientComponent = Configuration AND ServerComponent = Logging
```

---

## S3 — Multi-component runner orchestration

**Pattern:** Runner dispatches across Aggregation + Utilities + Logging simultaneously  
**CPSCore components involved:** `Synchronization`, `Aggregation`, `Utilities`, `Logging`  
**Key interactions:**
- `SimpleRunner.runStage` → `Aggregator.getAll` + `EnumMap.convert` + `RAIILogStream.stream`
- `SimpleRunner.runStages` → `EnumMap.convert` + `RAIILogStream.stream`
- `SynchronizedRunnerMaster.runAllStages` → `RAIILogStream.stream`

**Why this stresses the architecture:**  
Fan-out from a single orchestrator to multiple independent subsystems —
the hardest case for static analysis because the call targets are resolved
at runtime via template/virtual dispatch.

**Trace filter:**
```
ClientComponent = Synchronization AND ServerComponent in [Aggregation, Utilities, Logging]
AND ClientFunction in [SimpleRunner.runStage, SimpleRunner.runStages,
                       SynchronizedRunnerMaster.runAllStages]
```

---

## How to extend this list

Copy `scenario_template.md` into this file as a new section.  
Add the scenario ID to the table in `experiments/README.md`.  
Re-run H1 reference diagram construction for the new scenario before
running H2/H3.

---

## Schema for scenario definition files

Each scenario should also have a standalone file `scenarios/SX/` with:

```
scenarios/SX/
├── definition.md          (this section, standalone)
├── trace_slice.txt        (rows from runtime_traces.txt matching the filter)
├── static_slice.json      (nodes/edges from Neo4j matching the scenario components)
└── reference/             (populated by H1 Task 2)
    ├── structural.sysml   (or .json)
    └── sequence.sysml     (or .json)
```
