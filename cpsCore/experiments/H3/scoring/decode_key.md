# H3 Completeness Scoring — Decode Key

**DO NOT READ until all 10 completeness scores are filled in.**

Mapping from blinded file names back to conditions:

| Scenario | resp1 | resp2 |
|----------|-------|-------|
| S1 | A (no diagrams) | B (with diagrams) |
| S2 | B (with diagrams) | A (no diagrams) |
| S3 | A (no diagrams) | B (with diagrams) |
| S4 | B (with diagrams) | A (no diagrams) |

**Pattern:** odd-indexed scenarios (S1, S3): resp1=A, resp2=B.  
Even-indexed scenarios (S2, S4): resp1=B, resp2=A.

## Blind files location

`experiments/H3/scoring/blind_responses/`

## How to use

1. Read `S1_resp1.txt` and `S1_resp2.txt` (in the blind_responses/ folder).
2. Score each against the `reference_explanation` in `ground_truth/S1_ground_truth.json` using `rubric.md`.
3. Record the score (1–5) for each resp1/resp2 pair.
4. Repeat for all 4 scenarios (8 files total).
5. **Then** look at this decode key and translate:
   - S1 resp1 score → Condition A score; S1 resp2 score → Condition B score
   - S2 resp1 score → Condition B score; S2 resp2 score → Condition A score
   - etc.
6. Fill in the `completeness` column in `results.csv`.

## Reference explanations

Condition A = source + traces only (blind_responses/{S}_resp1.txt for S1/S3, resp2.txt for S2/S4)  
Condition B = source + traces + C5 element list (blind_responses/{S}_resp2.txt for S1/S3, resp1.txt for S2/S4)

Each scenario's reference prose is in `ground_truth/{S}_ground_truth.json` → `reference_explanation` field.
