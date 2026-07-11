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
| This diagram accurately reflects the scenario's *relevant* interactions | 5 | 4 |
| This diagram is easy to read and understand | 5 | 3 |
| This diagram would be useful to me in practice (e.g., onboarding, debugging, review) | 4 | 4 |

**Any comments on S1 (optional):**

> 

---

## Scenario S2

**Context:** The Configuration component reads and validates configuration properties (strings, vectors, enums). Each property read emits a log entry via the Logging component.

### Ratings

| Question | Diagram A (1–5) | Diagram B (1–5) |
|---|---|---|
| This diagram accurately reflects the scenario's *relevant* interactions | 4 | 4 |
| This diagram is easy to read and understand | 3 | 4 |
| This diagram would be useful to me in practice (e.g., onboarding, debugging, review) | 4 | 3 |

**Any comments on S2 (optional):**

> It is not clear what triggers a logging event

---

## Scenario S3

**Context:** A Synchronization runner orchestrates a run cycle that fans out to multiple components: fetching runnable objects (Aggregation), converting stage enum values to strings (Utilities), and logging progress (Logging).

### Ratings

| Question | Diagram A (1–5) | Diagram B (1–5) |
|---|---|---|
| This diagram accurately reflects the scenario's *relevant* interactions | 5 | 5 |
| This diagram is easy to read and understand | 5 | 4 |
| This diagram would be useful to me in practice (e.g., onboarding, debugging, review) | 4 | 3 |

**Any comments on S3 (optional):**

> 

---

## Overall (after reviewing all scenarios)

1. Overall, which diagram style (A or B, considering the pattern across scenarios) did you find more useful, and why?

> It seems that for S2 B is the simplified diagram, while for S1 and S3 A is the simplified one. It depends a bit on the usecase, but showing all the logging is not that relevant most of the time. For onboarding the simplified diagrams suit me better as you can easily see the important interactions quickly. If you want to debug something it is probably most useful to look at the full data

2. Any features you'd want added to either style (e.g., annotations, grouping, filtering)?

> Adding return lines could be useful. That makes all interactions a bit more clear without understanding the context

**Thank you** — please return this completed form to Prathik / Rosilde. Your responses will be kept anonymized in the thesis write-up.
