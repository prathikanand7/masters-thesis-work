# Candidate Scenarios for Future Expansion

Current scenarios (S1a, S1b, S2, S3) have design weaknesses: S1a/S1b are near-identical,
S2 has only one interaction type, and all scenarios use overlapping component sets.
The candidates below are drawn from the existing cpsCore test suite.

---

## How to read this table

| Column | Meaning |
|---|---|
| New component pairs | Pairs **not** already covered by S1a–S3 |
| Est. interactions | Estimated distinct cross-component interaction types |
| Discriminating aspect | Which conditions (C1–C6) would be meaningfully split |
| Difficulty to instrument | How many new instrumentation sites are needed in trace_slice.txt |

---

## Candidate A — "MultiThreaded Test 2" (`tests/Utilities/Scheduler/SchedulerTest.cpp`)

**Test**: `MicroSimulator.stopOnWait()` blocks the time provider; `sched.schedule()` queues
a periodic task; `tp.releaseWait()` advances simulated time and triggers the scheduled
callback multiple times.

| Property | Value |
|---|---|
| Components | Synchronization (AggregatableRunner), Utilities (MultiThreadingScheduler, MicroSimulator, SignalHandler) |
| New component pairs | None — same as S3 |
| Est. interactions | 3–4 (same types as S3 but with richer periodic repeat structure) |
| Discriminating aspect | **Sequence metric**: periodic scheduling fires `Util→Log` in a timed pattern; correct sequence requires recovering the inter-leave of `Sync→Util` and `Util→Log` across multiple scheduler ticks. C2 depth-ordering fails to capture the periodic repetition. C1 (no runtime knowledge) cannot predict event counts. |
| Difficulty to instrument | Low — same sites as S3, no new source files |

**Recommendation**: good replacement for S3 (or supplement), not for S2.

---

## Candidate B — "MultiThreaded Test 3" (`tests/Utilities/Scheduler/SchedulerTest.cpp`)

**Test**: Two concurrent scheduled tasks with offset periods (5 ms and 20 ms), time-provider
controlled. Checks interleaved execution order of two independent periodic callbacks.

| Property | Value |
|---|---|
| Components | Synchronization, Utilities |
| New component pairs | None |
| Est. interactions | 3–4 |
| Discriminating aspect | **Sequence metric**: interleaved periodic tasks require recovering relative order of two independent `Util→Log` channels. The most complex sequence-recovery case in the test suite. C1 and C2 have no mechanism to determine runtime interleave order. |
| Difficulty to instrument | Low |

**Recommendation**: best supplement for testing sequence recovery depth.

---

## Candidate C — "Aggregation Merge" (`tests/Framework/FrameworkAPITest.cpp`)

**Test**: `FrameworkAPI::lockAggregator()` / `getAggregator()` / `globalAgg->merge(agg)` /
`globalAgg->getOne<T>()` / `globalAgg->getAll<T>()`. Exercises the Framework↔Aggregation
boundary directly.

| Property | Value |
|---|---|
| Components | Framework, Aggregation |
| New component pairs | **Framework → Aggregation** (absent from all current scenarios) |
| Est. interactions | 3–4 (lockAggregator, getAggregator, merge, getOne/getAll) |
| Discriminating aspect | New component pair tests whether C1 (LLM) and C2 (Neo4j) recognise Framework API call sites; no Logging involvement simplifies the GT. C3/C4 are pure trace — whether they capture Framework→Aggregation depends on instrumentation. |
| Difficulty to instrument | Medium — requires new instrumentation sites in Framework/ |
| External deps | Requires NetworkFactory (Redis/Serial) config — may need mocking or a stripped config file |

**Recommendation**: highest structural value — adds a new component pair. Worth the
instrumentation effort if external deps can be resolved.

---

## Candidate D — "IPC Test 1" (`tests/Utilities/IPC/IPCTest.cpp`)

**Test**: `IPC::publish<T>()` creates a shared-memory publisher; `IPC::subscribe<T>()`
registers a callback; `SimpleRunner.runAllStages()` starts the scheduler; callbacks fire
when data is published. The publish→callback link exists only at runtime (boost::signals2
or shared memory dispatch) — invisible to Neo4j static analysis.

| Property | Value |
|---|---|
| Components | Synchronization (SimpleRunner), Utilities (IPC, MultiThreadingScheduler, TimeProvider, SignalHandler) |
| New component pairs | Sync → Util (SimpleRunner initialises IPC) — present in S3, not novel |
| Est. interactions | 2–3 cross-component (Sync→Util, Util→Log) |
| Discriminating aspect | The IPC publish→subscribe callback is dynamic-only (Utilities-internal). While this doesn't add a new cross-component pair, it introduces a **runtime-only intra-component edge** that C1/C2 cannot see. Useful for studying intra-Utilities indirect dispatch, but does not improve cross-component coverage. |
| Difficulty to instrument | Medium — IPC subscribe callback sites are implicit (registered lambdas) |

**Recommendation**: limited value for cross-component evaluation; more useful as a
stress test for intra-component static analysis blind spots.

---

## Candidate E — "Scheduler Period Change" (`tests/Utilities/Scheduler/SchedulerTest.cpp`)

**Test**: `Event::changePeriod()` modifies a running scheduled task mid-execution.
Uses `SystemTimeProvider` (real-time wall clock) rather than `MicroSimulator`.

| Property | Value |
|---|---|
| Components | Synchronization (SimpleRunner), Utilities (MultiThreadingScheduler, SystemTimeProvider, SignalHandler) |
| New component pairs | None |
| Est. interactions | 2–3 |
| Discriminating aspect | `changePeriod()` is a runtime-only state mutation — C2 sees only that `changePeriod` exists as a callable, not when it fires. Useful for testing whether sequence recovery handles mid-execution state changes. |
| Difficulty to instrument | Low |

**Recommendation**: minor supplement; does not address the main weaknesses.

---

## Priority Order for Implementation

| Priority | Candidate | Reason |
|---|---|---|
| 1 | **C — Aggregation Merge** | Only test adding a new component pair (Framework↔Aggregation) |
| 2 | **B — MultiThreaded Test 3** | Richest sequence-recovery challenge; same instrumentation cost as S3 |
| 3 | **A — MultiThreaded Test 2** | Good sequence supplement, very low cost |
| 4 | D — IPC Test 1 | Interesting but Utilities-internal; limited cross-component value |
| 5 | E — Scheduler Period Change | Marginal improvement over existing S3 |

---

## Existing Scenario Coverage (for reference)

| Scenario | Test | Component pairs covered |
|---|---|---|
| S1a | Synchronized Runner Test | Sync→Agg, Sync→Log |
| S1b | Synchronized Runner Timeout | Sync→Agg, Sync→Log (+ timeout path) |
| S2 | Optional test | Config→Log |
| S3 | MultiThreaded Test 1 | Sync→Agg, Agg→Log, Util→Log |
| S4 | Stage Event Bridge Pub-Sub | Sync→Agg (dynamic), Sync→Log (static-only) |

**Missing pairs**: Framework→Aggregation, Framework→Configuration, Framework→Utilities,
Aggregation→Configuration, Configuration→Aggregation, Configuration→Utilities,
Utilities→Aggregation, Utilities→Synchronization.
