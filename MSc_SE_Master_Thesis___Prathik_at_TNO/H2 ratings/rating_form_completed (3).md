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
| This diagram is easy to read and understand | 5 | 2 |
| This diagram would be useful to me in practice (e.g., onboarding, debugging, review) | 5 | 3 |

**Any comments on S1 (optional):**

> Diagram B appears to be more 'complete'. However I think this completeness is unhelpful to a developer given the task Context only mentions the components synchronisation, aggregation and logging. All the extra events are just streaming, I do not think these are particularly valuable - except for the synchronization - convert -> utilities edge. I do not know the codebase so can't comment if this is important but I assume not!
Diagram A is a lot simpler and manageable for understanding the flow. It also appears to start at the 'right point' in the sequence. The getAll event rather than a stream.

---

## Scenario S2

**Context:** The Configuration component reads and validates configuration properties (strings, vectors, enums). Each property read emits a log entry via the Logging component.

### Ratings

| Question | Diagram A (1–5) | Diagram B (1–5) |
|---|---|---|
| This diagram accurately reflects the scenario's *relevant* interactions | 2 | 5 |
| This diagram is easy to read and understand | 2 | 5 |
| This diagram would be useful to me in practice (e.g., onboarding, debugging, review) | 3 | 3 |

**Any comments on S2 (optional):**

> Diagram B appears to correctly reflect the context (only the configuration and logging components are mentioned). It is easy to read and understand however I would question its usefulness. Perhaps a diagram is unnecessary here and simply a textual answer "configuration streams to logging" is much simpler and as informative.
Diagram A appears to show all the interactions in the system. However this is a slight information overload for what we want to do.
I would however mark it as the amount of usefulness as diagram A as it is possible that a user might want to know at want point in the sequence this action occurs. In which case it would be useful.

---

## Scenario S3

**Context:** A Synchronization runner orchestrates a run cycle that fans out to multiple components: fetching runnable objects (Aggregation), converting stage enum values to strings (Utilities), and logging progress (Logging).

### Ratings

| Question | Diagram A (1–5) | Diagram B (1–5) |
|---|---|---|
| This diagram accurately reflects the scenario's *relevant* interactions | 5 | 2 |
| This diagram is easy to read and understand | 5 | 2 |
| This diagram would be useful to me in practice (e.g., onboarding, debugging, review) | 5 | 3 |

**Any comments on S3 (optional):**

> Diagram A is a good diagram for this context and I think would be very useful. It is clear and features a manageable number of components and events to quickly understand what is happening.
Diagram B is again too much information for the use case but may be helpful in understanding when our specific events happen in the overall flow.

---

## Overall (after reviewing all scenarios)

1. Overall, which diagram style (A or B, considering the pattern across scenarios) did you find more useful, and why?

> I generally find the simpler more focused diagrams more useful. It is quicker and easier to read and understand therefore I can imagine myself happily referring to them when working on a coding problem.
I do think the larger diagrams are still helpful. Sometimes you want to know where an event occurs in the overall flow although I can see myself referring to this less. 

A workflow I imagine is looking at the large diagram to get a full overview of the workflow and then using the focused diagram to understand more concisely what is happening in our point of interest.

2. Any features you'd want added to either style (e.g., annotations, grouping, filtering)?

> Maybe an option to turn the stream events on or off/make them a specific colour. They can clutter the larger diagram slightly.

**Thank you** — please return this completed form to Prathik / Rosilde. Your responses will be kept anonymized in the thesis write-up.
