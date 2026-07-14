# Prathik Anand Krishnan: MSc Software Engineering Thesis
## Hybrid Static–Trace Analysis for Interaction Model Synthesis in Event-Driven Systems

---

## Project Structure

```
prathik-thesis/
├── main.tex            ← Entry point; thesis metadata is set here
├── acronyms.tex        ← Acronym definitions (add new ones here)
├── references.bib      ← Bibliography (use Zotero + Overleaf for best workflow)
├── cpp-macro.tex       ← \Cpp command definition
│
├── cover.tex           ← Half-title cover page
├── title.tex           ← Formal title page (calls \makeformaltitlepage)
├── abstract.tex        ← ~250-word abstract
├── acknowledgement.tex ← Acknowledgements
│
├── introduction.tex    ← Ch 1: Context, Problem, RQs, Approach, Outline
├── background.tex      ← Ch 2: SysML v2, PGs, Static/Trace Analysis, Scenario Scoping, SSEF
├── related_work.tex    ← Ch 3: Literature survey + positioning table
├── methods.tex         ← Ch 4: Pipeline, PG schema, extraction, evidence combination, scenario scoping
├── experiments.tex     ← Ch 5: Case study, implementation, results tables
├── evaluation.tex      ← Ch 6: RQ answers, validation, threats to validity
├── conclusion.tex      ← Ch 7: Summary, contributions, future work
└── appendix.tex        ← Appendix A: Cypher constraints, macro patterns, diagrams
```

---

## Compilation

### Via Overleaf (recommended)
Upload the entire folder as a zip to Overleaf.
Overleaf has `--shell-escape` and `biber` enabled by default.
Set the main document to `main.tex`.

### Locally (requires TeX Live 2023+ or MikTeX)

```bash
latexmk -pdf -shell-escape main.tex
```

Or manually:
```bash
pdflatex --shell-escape main.tex
biber main
pdflatex --shell-escape main.tex
pdflatex --shell-escape main.tex
```

> **Note:** `minted` requires `--shell-escape` and Python's `Pygments` library.
> Install with: `pip install Pygments`

---

## Using the Official UvA MSc SE Template

This project uses the standard `report` class for portability.
To switch to the official UvA class file:

1. Download `uvamscse.cls` from the UvA/Overleaf template gallery
2. Replace `\documentclass[11pt, a4paper, twoside]{report}` in `main.tex`
   with `\documentclass{uvamscse}` (and adjust key-value options as needed)
3. Some custom commands defined in `main.tex` (like `\makeformaltitlepage`)
   may already be provided by the official class; remove duplicates

---

## Key TODOs

Search for `\todo` in any chapter file to find placeholders that need filling in.
A summary list is generated automatically in the compiled PDF under "Open TODO Items".

Highest priority:
- [x] Fix double-backslash typos in `experiments.tex` and `methods.tex` (rendered as literal `\texttt{...}` in the PDF)
- [x] Fix undefined `\cref{sec:static-extraction-method}` in `methods.tex` → now points to `sec:static-impl`
- [x] Remove dead `\ssef` macro from `main.tex` (SSEF dropped from thesis)
- [x] Replace incorrect `franks:roscallgraph` bib entry (was an unrelated queueing-networks paper) with the correct citation: Santos, Cunha \& Macedo, "Static-Time Extraction and Analysis of the ROS Computation Graph," IRC 2019, now `santos:roscompgraph`
- [x] Fix stray blank line mid-sentence in `conclusion.tex` Future Work
- [x] Remove uncited bib entries (`Beck2000a`, `du:softcite`, `friedenthal:sysml`)
- [x] Add pipeline architecture figure (`fig:pipeline-overview` in `methods.tex`, TikZ, no external image needed)
- [x] Explain why the H2 quantitative table is scoped to S1–S3 only (added paragraph in `evaluation.tex`)
- [x] Rewrite `abstract.tex` and `acknowledgement.tex` — Capgemini/fluoroscopy/SSEF content replaced with the real CPSCore/H1–H3 narrative
- [x] Add practitioner validation section (`sec:practitioner` in `evaluation.tex`) from the Renaissance MCP hands-on session + 4 interviews on a second, large industrial codebase, cross-referenced from `introduction.tex`, `conclusion.tex`, `acknowledgement.tex`, `abstract.tex`, and the External Validity threats subsection
- [x] Standardised on **Renaissance MCP** as the tool name throughout (dropped the "Azurion Atlas" naming, confirmed by Prathik as a separate/uncertain term, not to be used)
- [x] Further genericised the practitioner section: removed all product names and domain-identifying specifics (system name, subsystem names, defect-specific class/component names); the defect is now described only at the generic "service / proxy / client / downstream component" level; participant roles no longer name the domain they work in
- [x] H2 blinded expert rating: both raters' completed forms received; results and discussion added to \cref{sec:h2-qual}, and the H2 confirmation language updated in `evaluation.tex` and `conclusion.tex`
- [ ] Fill in UvA thesis committee (chair, second reviewer) in `main.tex`
- [ ] Include reference diagrams (S1–S5) in appendix from `experiments/H1/reference_diagrams/`
- [ ] Include generated C5 diagrams in appendix from `experiments/H1/conditions/C5_full_pipeline/`
- [ ] Add repository URL in `conclusion.tex`
- [ ] Consider trimming `abstract.tex` closer to ~250 words if the department enforces a hard limit (currently ~370 words, reporting H1–H3 plus the practitioner session)


---

## Contacts

| Role                   | Name                             |
|------------------------|-----------------------------------|
| Author                 | Prathik Anand Krishnan            |
| UvA academic supervisor| Dr. L. Thomas van Binsbergen (CCI, UvA) |
| External supervisor    | Rosilde Corvino (TNO-ESI)         |
| GDI teammates          | Joe, Navoneel (Novo)           |
| External expert raters (H2) | Joe, Navoneel (TNO-ESI engineers) |
| Practitioner session participants (`sec:practitioner`) | Anonymised in-thesis as P1–P4 (software designer, software product owner, senior software architect, algorithm engineer) |

