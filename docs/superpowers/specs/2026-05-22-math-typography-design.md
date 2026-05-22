# Math Typography Design

## Goal

Make the paper formulas read closer to compact CVPR/IEEE-style technical
papers while preserving the Chinese body typography and the current paper
content.

## Scope

- Keep XeLaTeX, `ctexart`, Chinese body fonts, page geometry, and section
  content intact.
- Use a Times-like math font package in the preamble so variables, Greek
  letters, and math symbols look more like engineering conference papers.
- Keep the existing equation markup such as `\mathrm{ALK}`,
  `\Pi_{\mathrm{green}}`, and display math environments valid.
- Normalize display-math spacing so equations sit cleanly between Chinese
  paragraphs without large vertical gaps.
- Verify against the current formula-heavy problem section instead of rewriting
  equations by hand.

## Approach

Use `newtxmath` as the math font layer. It is a narrow preamble change that
keeps the current AMS math workflow and avoids migrating the document to
`unicode-math`. Pair it with explicit display skip lengths so displayed
equations and aligned blocks have consistent vertical breathing room in the
paper.

## Files

- `main.tex` owns the global math package choice and display math spacing.
- `tests/check-paper-format.ps1` can assert that the chosen math typography
  package and spacing configuration remain present.

## Verification

- Run the source-level format check before and after the preamble edit.
- Compile the current paper with XeLaTeX after the edit.
- Render a formula-heavy page and inspect formula weight, spacing, and line
  breaks without changing the user's current section content.
