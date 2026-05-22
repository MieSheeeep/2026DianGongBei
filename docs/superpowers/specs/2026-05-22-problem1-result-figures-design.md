# Problem One Result Figures Design

## Goal

Replace the indicator and cost-result tables in problem one with concise
publication-style result figures while keeping precise energy totals available
in the existing table.

## Scope

- Keep the problem-one power curve and energy table.
- Replace the indicator table with a threshold-aware bar chart that labels the
  computed values, compliance direction, and pass/fail outcome.
- Replace the cost table with a compact cost-composition figure. Positive cost
  contributors define the composition; grid sell revenue is shown as an
  explicit offset rather than a negative pie slice.
- Generate vector PDF figures for the paper from the local problem-one script.
- Keep the problem-one prose aligned with the new figures and final numerical
  results.

## Figure Style

Use a restrained conference-paper style: vector export, direct value labels,
light axes, no decorative gradients, typography sized for single-column A4
reading, and redundant cues beyond color for compliance and thresholds.

## Verification

- Re-run the problem-one script to regenerate figure PDFs.
- Compile the paper with XeLaTeX.
- Render the problem-one result pages and inspect label fit, figure ordering,
  and the final numerical result text.
