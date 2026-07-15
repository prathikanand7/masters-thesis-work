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
| This diagram accurately reflects the scenario's *relevant* interactions | 1 | 1 |
| This diagram is easy to read and understand | 4 | 3 |
| This diagram would be useful to me in practice (e.g., onboarding, debugging, review) | 3 | 2 |

**Any comments on S1 (optional):**

> I miss events - e.g. when are the runnable objects retrieves (and available at the synchronization runner)?
 

---

## Scenario S2

**Context:** The Configuration component reads and validates configuration properties (strings, vectors, enums). Each property read emits a log entry via the Logging component.

### Ratings

| Question | Diagram A (1–5) | Diagram B (1–5) |
|---|---|---|
| This diagram accurately reflects the scenario's *relevant* interactions | 1 | 2 |
| This diagram is easy to read and understand | 2 | 4 |
| This diagram would be useful to me in practice (e.g., onboarding, debugging, review) | 2 | 3 |

**Any comments on S2 (optional):**

> Unclear what is read (from where) and then logged.
Unclear what is repeated - or is first every read and then every logged (what could be a poor implementation) 

---

## Scenario S3

**Context:** A Synchronization runner orchestrates a run cycle that fans out to multiple components: fetching runnable objects (Aggregation), converting stage enum values to strings (Utilities), and logging progress (Logging).

### Ratings

| Question | Diagram A (1–5) | Diagram B (1–5) |
|---|---|---|
| This diagram accurately reflects the scenario's *relevant* interactions | 4 | 3 |
| This diagram is easy to read and understand | 4 | 3 |
| This diagram would be useful to me in practice (e.g., onboarding, debugging, review) | 4 | 4 |

**Any comments on S3 (optional):**

> Diagram A is maybe too simple.
Diagram B leaves too much to the user - Do I really correctly interpret that Configuration and Framework are not relevant in this scenario (when focusing on Synchronization).

---

## Overall (after reviewing all scenarios)

1. Overall, which diagram style (A or B, considering the pattern across scenarios) did you find more useful, and why?

> I like minimal number of objects / swimming lanes.
I like that the object of interest is the first one. 

I have problems with the stream data type - a stream is never one message, but a sequence there of.
So having a stream as a data type is strange for a sequence diagram.

2. Any features you'd want added to either style (e.g., annotations, grouping, filtering)?

> I miss responses - when is the answer to e.g., getAll obtained?
I miss activity - when are objects/tasks just waiting and when are they processing?
I miss time stamps - how much time has elapsed between the different events / communications?


**Thank you** — please return this completed form to Prathik / Rosilde. Your responses will be kept anonymized in the thesis write-up.
