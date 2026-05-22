# Math Typography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the LaTeX paper Times-like math typography and tighter display formula spacing.

**Architecture:** Keep the change global and narrow in `main.tex` so existing formula markup in the paper sections inherits the new math presentation. Extend the existing PowerShell source check to guard the package and display spacing directives, then compile and inspect the current formula-heavy pages.

**Tech Stack:** XeLaTeX, CTeX, AMS math, `newtxmath`, PowerShell

---

### Task 1: Guard Math Typography Configuration

**Files:**
- Modify: `tests/check-paper-format.ps1`
- Test: `tests/check-paper-format.ps1`

- [ ] **Step 1: Add source checks**

Add checks that require:

```powershell
@{ Name = 'Times-like math font'; Pass = $main.Contains('\usepackage{newtxmath}') }
@{ Name = 'display math spacing'; Pass = $main.Contains('\setlength{\abovedisplayskip}') }
```

- [ ] **Step 2: Run the source check before the preamble edit**

Run: `powershell -ExecutionPolicy Bypass -File tests/check-paper-format.ps1`

Expected: exit code `1` for the missing math package and display spacing.

### Task 2: Tune the Math Preamble

**Files:**
- Modify: `main.tex`
- Test: `tests/check-paper-format.ps1`

- [ ] **Step 1: Load the Times-like math package**

Keep the existing `amsmath`, `amssymb`, and `amsfonts` imports and load:

```tex
\usepackage{newtxmath}
```

- [ ] **Step 2: Set display-math spacing**

Add compact display spacing after the paragraph spacing setup:

```tex
\setlength{\abovedisplayskip}{0.6em plus 0.2em minus 0.1em}
\setlength{\belowdisplayskip}{0.6em plus 0.2em minus 0.1em}
\setlength{\abovedisplayshortskip}{0.35em plus 0.15em minus 0.1em}
\setlength{\belowdisplayshortskip}{0.35em plus 0.15em minus 0.1em}
```

- [ ] **Step 3: Run the source check**

Run: `powershell -ExecutionPolicy Bypass -File tests/check-paper-format.ps1`

Expected: exit code `0`.

### Task 3: Compile and Inspect

**Files:**
- Verify: `main.tex`
- Verify: current formula-heavy section pages

- [ ] **Step 1: Compile**

Run: `xelatex -interaction=nonstopmode -halt-on-error main.tex`

Expected: exit code `0`.

- [ ] **Step 2: Render formula-heavy pages**

Render the pages that contain the current problem-one formulas and inspect math
weight, equation spacing, aligned blocks, and page breaks.
