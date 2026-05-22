# Paper Format Design

## Goal

Bring the LaTeX competition paper template into line with the supplied paper
format rules while keeping the document structure ready for team writing.

## Scope

- Keep the paper on A4 pages with 2.5 cm margins.
- Keep the body text at Song-style Chinese small-four size through the existing
  `ctexart` setup.
- Replace the current decorative cover with a minimal first page matching the
  provided reference: a registration-number line and a paper-title line only.
- Set the registration number to `009842`.
- Keep the paper title in the shared `\paperTitle` macro until the actual A/B
  problem title is supplied, so the cover and abstract page stay consistent.
- Keep page numbering hidden on the cover and start Arabic page number `1` on
  the abstract page footer.
- Keep the main text beginning after the abstract page, omit a table of
  contents, and place appendices after references.
- Make the citation guidance match the supplied reference formats and mention
  the contest anonymity rule in repository guidance.

## Files

- `main.tex` controls document geometry, typography, cover layout, pagination,
  and section ordering.
- `sections/references.tex` provides reference-list examples and citation
  guidance for book, journal, and online sources.
- `README.md` records the writing and submission constraints that are easy to
  violate while drafting.

## Approach

Use a minimal template edit. The existing LaTeX project already has the right
paper size, margins, abstract page position, footer page numbering, main-text/appendix
ordering, and modular section layout. The cover block, references guidance,
and README reminders are the narrow places that need revision.

## Verification

- Add a small source-level format check before the template edits so the cover
  and reference rules have a repeatable regression check.
- Compile `main.tex` with XeLaTeX after the edits to confirm the template still
  builds.
- Inspect the generated first page during verification to confirm that it only
  carries the two requested cover lines and no page number.
