# Paper Format Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the LaTeX paper template so its cover and drafting guidance follow the supplied competition format rules.

**Architecture:** Keep page setup and section ordering in `main.tex`, because the existing template already owns geometry, typography, cover pagination, and document assembly there. Add a small PowerShell source check for the narrow format guarantees that can regress without changing LaTeX compilation, then compile and inspect the generated PDF after edits.

**Tech Stack:** XeLaTeX, CTeX, PowerShell

---

### Task 1: Add Format Regression Check

**Files:**
- Create: `tests/check-paper-format.ps1`
- Test: `tests/check-paper-format.ps1`

- [ ] **Step 1: Write the source check**

```powershell
$main = Get-Content -Raw -Encoding UTF8 'main.tex'
$references = Get-Content -Raw -Encoding UTF8 'sections/references.tex'

$checks = @(
  @{ Name = 'registration number'; Pass = $main.Contains('\newcommand{\registrationNumber}{009842}') },
  @{ Name = 'cover label'; Pass = $main.Contains('参赛编号：') },
  @{ Name = 'old cover banner removed'; Pass = -not $main.Contains('参赛论文') },
  @{ Name = 'references no toc entry'; Pass = -not $references.Contains('\addcontentsline{toc}{section}{参考文献}') },
  @{ Name = 'citation marker guidance'; Pass = $references.Contains('[1][3]') }
)

$failed = $checks | Where-Object { -not $_.Pass }
if ($failed) {
  $failed | ForEach-Object { Write-Error "Missing paper format rule: $($_.Name)" }
  exit 1
}

Write-Output 'Paper format source checks passed.'
```

- [ ] **Step 2: Run the source check and verify it fails before template edits**

Run: `powershell -ExecutionPolicy Bypass -File tests/check-paper-format.ps1`

Expected: exit code `1` with failures for the registration number, cover label,
old cover banner, table-of-contents reference entry, and citation marker
guidance.

### Task 2: Revise Template Formatting

**Files:**
- Modify: `main.tex`
- Modify: `sections/references.tex`
- Modify: `README.md`
- Test: `tests/check-paper-format.ps1`

- [ ] **Step 1: Replace the cover in `main.tex`**

Keep the existing A4, margin, page numbering, and section-order setup. Set:

```tex
\newcommand{\registrationNumber}{009842}
```

Replace the current banner cover content with two centered lines:

```tex
{\heiti\zihao{2} 参赛编号：\registrationNumber\par}
\vspace{3cm}
{\heiti\zihao{2} 论文题目：\paperTitle\par}
```

- [ ] **Step 2: Revise reference guidance**

Remove the reference table-of-contents insertion and add a short note that
body citations use bracketed numbering such as `[1][3]`. Keep the three
supplied examples for books, journal articles, and online resources.

- [ ] **Step 3: Expand README writing constraints**

Document the supplied page count, abstract-length, anonymity, and citation
constraints near the existing format notes.

- [ ] **Step 4: Run the source check and verify it passes**

Run: `powershell -ExecutionPolicy Bypass -File tests/check-paper-format.ps1`

Expected: exit code `0` and `Paper format source checks passed.`

### Task 3: Compile and Inspect

**Files:**
- Verify: `main.tex`

- [ ] **Step 1: Compile the template**

Run: `xelatex -interaction=nonstopmode -halt-on-error main.tex`

Expected: exit code `0` and an updated `main.pdf`.

- [ ] **Step 2: Inspect the first PDF page**

Render or screenshot the first PDF page and confirm it contains only the
registration-number line and paper-title line with no footer page number.

- [ ] **Step 3: Inspect the second PDF page**

Confirm the abstract page contains the title, abstract, keywords, and footer
page number `1`.
