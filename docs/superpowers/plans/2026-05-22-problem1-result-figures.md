# Problem One Result Figures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert problem-one indicator and cost tables into publication-style result figures.

**Architecture:** Reuse the local problem-one computation output as the single source of numerical truth, then extend its plotting routine to export vector PDFs for the paper. Keep LaTeX changes local to `sections/problem1.tex` so the energy table remains precise while the figure references replace only the indicator and cost-result tables.

**Tech Stack:** Python, NumPy, pandas, Matplotlib PDF export, XeLaTeX

---

### Task 1: Add Problem-One Result Figures

**Files:**
- Modify: `support/code/p1_solve.py`
- Create via script: `figures/p1_indicator_thresholds.pdf`
- Create via script: `figures/p1_cost_breakdown.pdf`

- [ ] Extend the plotting routine with a threshold-aware indicator bar chart.
- [ ] Extend the plotting routine with a cost composition figure that annotates
      sell revenue, net daily cost, and ton-ammonia cost outside the cost shares.
- [ ] Run `python support/code/p1_solve.py` and confirm the new PDF figures are
      emitted under `figures/`.

### Task 2: Replace Result Tables in LaTeX

**Files:**
- Modify: `sections/problem1.tex`

- [ ] Keep the energy table for exact energy totals.
- [ ] Replace the indicator table with the threshold bar chart.
- [ ] Replace the cost table with the cost breakdown figure and final cost text.
- [ ] Update the final analysis prose to refer to figures rather than removed
      tables.

### Task 3: Verify Layout

**Files:**
- Verify: `main.tex`

- [ ] Run `xelatex -interaction=nonstopmode -halt-on-error main.tex` twice.
- [ ] Render the problem-one result pages and inspect figure labels, page
      breaks, and text references.
