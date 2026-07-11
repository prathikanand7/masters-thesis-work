# Structural & Sequence Diagram Feedback — Rating Form

**Purpose:** You're being asked to compare two versions of reconstructed interaction diagrams for the same scenarios in a C++ pub-sub codebase ([CPSCore](https://github.com/theilem/cpsCore)). For each scenario, you'll see two diagram variants, labeled **A** and **B**. You are not told which generation method produced which — please rate them purely on how they read to you as a developer/architect.

**Rating scale:**

| Score | Meaning |
|---|---|
| 1 | Strongly disagree |
| 2 | Disagree |
| 3 | Neutral |
| 4 | Agree |
| 5 | Strongly agree |

---

## Scenario S1

**Context:** A Synchronization runner triggers an aggregation update. The runner retrieves runnable objects from the Aggregation component and flushes the logger (Logging component) on completion.

### Ratings

| Question | Diagram A (1–5) | Diagram B (1–5) |
|---|---|---|
| This diagram accurately reflects the scenario's *relevant* interactions | 5 | 2 |
| This diagram is easy to read and understand | 5 | 3 |
| This diagram would be useful to me in practice (e.g., onboarding, debugging, review) | 5 | 4 |

**Any comments on S1 (optional):**

> Diagram A seems to be accurately representing the events in the scenario, S1. Diagram B seems to represent many more events that might be from other scenarios on top of scenario, S1.

---

## Scenario S2

**Context:** The Configuration component reads and validates configuration properties (strings, vectors, enums). Each property read emits a log entry via the Logging component.

### Ratings

| Question | Diagram A (1–5) | Diagram B (1–5) |
|---|---|---|
| This diagram accurately reflects the scenario's *relevant* interactions | 2 | 3 |
| This diagram is easy to read and understand | 2 | 5 |
| This diagram would be useful to me in practice (e.g., onboarding, debugging, review) | 2 | 2 |

**Any comments on S2 (optional):**

> Diagram B is a relatively better representation of Scenario S2 than Diagram 1. However, the single stream event does not tell us the number of property reads by the Configuration component which might be necessary to know in this scenario and is a very useful information for debugging.

---

## Scenario S3

**Context:** A Synchronization runner orchestrates a run cycle that fans out to multiple components: fetching runnable objects (Aggregation), converting stage enum values to strings (Utilities), and logging progress (Logging).

### Ratings

| Question | Diagram A (1–5) | Diagram B (1–5) |
|---|---|---|
| This diagram accurately reflects the scenario's *relevant* interactions | 5 | 2 |
| This diagram is easy to read and understand | 5 | 3 |
| This diagram would be useful to me in practice (e.g., onboarding, debugging, review) | 5 | 4 |

**Any comments on S3 (optional):**

> Diagram A seems to be accurately representing the events in the scenario, S3. Diagram B seems to represent many more events that might be from other scenarios on top of scenario, S3.

---

## Overall (after reviewing all scenarios)

1. Overall, which diagram style (A or B, considering the pattern across scenarios) did you find more useful, and why?

> I think it depends on the scenario. For scenarios, S1 and S3, diagram style A is more useful than that of B. However, for scenario, S2, diagram style B is more useful than A.

2. Any features you'd want added to either style (e.g., annotations, grouping, filtering)?

> I would like to add the event parameters in addition to the event names. For example, in scenario, S2, I see there is a stream event. I would like to add the exact property-read that was emitted as a stream event to make it more descriptive and helpful in debugging.

**Thank you** — please return this completed form to Prathik / Rosilde. Your responses will be kept anonymized in the thesis write-up.
