# H3 Completeness Rubric

Apply this rubric to each agent response when scoring completeness (column in
`results.csv`). One score per condition × scenario.

| Score | Criteria |
|-------|----------|
| **1** | Response is missing most components and interactions; explanation is vague or wrong |
| **2** | Identifies a minority of components/interactions; explanation has significant gaps |
| **3** | Identifies roughly half the relevant components and interactions; explanation covers the main flow but misses important details |
| **4** | Identifies most components and interactions; explanation is largely correct with only minor omissions |
| **5** | Identifies all or nearly all correct components and interactions; explanation is accurate, complete, and clearly describes the execution flow |

## Application instructions

1. Read the agent response in `agent_conditions/responses/<condition>/<scenario>_response.txt`.
2. Compare against `ground_truth/<scenario>_ground_truth.json`.
3. Assign a 1–5 score based on overall explanation quality (not just raw counts —
   the counts are handled by the `comp_correct` and `intr_correct` columns).
4. Enter the score in the `completeness` column of `results.csv`.

## Inter-rater reliability

If a second rater is available, have them score the same responses independently.
Compute Cohen's kappa or simple % agreement. Report this in the thesis.
