# Claim ledger: a found snippet is not a read one, and a claim without \cite is still a claim

Status: implemented (written 2026-09-30; Q1–Q6 decided as recommended the same day; implemented on docs/claim-ledger-reading; tests and red checks pass locally; CI not run; see "As built")

## Decided by the author (2026-09-30)

Q1–Q6 as recommended below (◌): a `read` column with author / draft readings, and only high-risk rows that no author
has read are findings; uncited pointing phrases and named works are reported; a cited negative claim with no row is a
finding; `--pairs` groups rows by claim; an optional `version` column; after a fix, sentences citing the same key are
listed and an edited bound sentence names its rows.

## Problem

The claim-ledger audit (`.claude/skills/audit/scripts/audit-claim-ledger.py`) binds one manuscript sentence to one
verbatim snippet in one archived source. Its docstring already says what it does not do: judge whether the claim says
more than the snippet. On one real manuscript that gap, and three next to it, let wrong sentences through while every
check passed:

1. A sentence said something the source never said. A ledger row paired it with a real snippet from that source about
   something else. The snippet was found, so the row stayed green until a person read the source. It happened twice.
2. A sentence stated what "the benchmarks cited here" do, with no `\cite`. It had no row, so nothing looked at it. It
   contradicted two works cited in the same section.
3. Three new sentences stated what a named prior work's authors did, by name, without `\cite`. Nothing checked them.
4. One claim was supported by three rows. The agent read one, judged the claim to overreach, and edited the manuscript.
   The edit was wrong and was reverted later.

Two smaller ones: the evidence for a claim came from the arXiv version while the bibliography cites the proceedings
version, and there was nowhere to record that; editing a bound sentence left the ledger and the reading notes to be
updated by hand, and the loop reported the mismatch one round later.

## Probes on the current audit (synthetic text)

A two-source manuscript, run before writing this:

| Probe | What the audit reports now |
|---|---|
| A cited sentence whose ledger row holds a real snippet about something else (the sentence also gives a number the source contradicts) | exit 0, no finding |
| "The tools cited here handle only printed text." with no `\cite` | nothing |
| "BarBench, whose authors fixed the lighting, is the closest benchmark." with no `\cite`; BarBench is cited elsewhere | nothing |
| "Earlier work did not test handwritten text~\cite{foo}." with no row | a prompt, `unledgered-credit`: it is read as a credit line |
| Two rows support one claim | `--pairs` prints two separate pairs; nothing puts them side by side |

The coverage line said "0 asserting sentence(s) carry no row" throughout.

## Goals

- A row whose snippet was only found never reads as checked. The report separates found from read.
- A sentence that asserts something about the literature without `\cite` is reported.
- A negative claim about a cited work, with no row, is a finding, not a credit.
- A claim is read with all of its rows at once.
- The version the evidence came from can be recorded.

## Non-goals

- No machine judgement of support. The docstring's measurement stands (a paired judge caught 7 of 8 and missed a dropped
  hedge every time).
- No "add a citation" command that syncs the bibliography, sources, rows and notes. That is a separate spec.
- No change to how sources are extracted. (Two-column PDFs extracted with `pdftotext -layout` interleave the columns and
  break verbatim matching; without `-layout` they match. Noted here, not fixed.)

## Decisions

- **Q1 What makes a row read.** ◌ An optional column `read`: `author: <one line>` or `draft: <one line>`, where the line
  says what the snippet says and what the sentence adds. Empty means found only. The report counts found, draft-read and
  author-read rows. A row is a finding only when it is high-risk and not author-read: a negative claim, a scope claim
  ("only", "outside", "first", "no prior"), or a sentence whose numbers do not appear in its snippets. Other rows that are
  not read are a count, not a finding.
  (Alternatives: every row must be author-read, which in practice is never green; or keep found-means-checked.)
- **Q2 Claims with no `\cite`.** ◌ Two findings. `uncited-literature-claim`: a sentence with a pointing phrase ("cited
  here", "cited above", "prior work", "the literature", "existing benchmarks", "earlier studies") and no `\cite`.
  `named-work-without-cite`: a sentence that names a registered work and has no `\cite`. Names come from a workspace
  table (`name<TAB>key`), seeded from `shorttitle` where the bibliography has one. Names not in the table are not
  checked, and the report says so. In gate mode (sentences this change added) both are hard findings; in the full scan
  they are a list.
- **Q3 Negative claims with `\cite` and no row.** ◌ A finding, `unledgered-negative-claim`, using the patterns that
  `negative-claim-without-fulltext` already uses. No longer a credit prompt.
- **Q4 All rows at once.** ◌ `--pairs` groups rows by claim sentence across every ledger it is given, and prints each
  snippet under its claim. A claim judged to overreach is judged against the whole group.
- **Q5 Version.** ◌ An optional `version` column, shown in `--pairs` and in the reading notes. No check.
- **Q6 After a fix.** ◌ When a row is read as wrong (`author: wrong …`), list the other sentences that cite the same key
  for re-reading. When the changed-sentence gate sees a bound sentence edited, it names the ledger rows and the notes to
  update in the same round.

## Acceptance criteria

- Each probe above becomes a test that fails on the current audit and passes after.
- On one real workspace, read only: the report gives found / draft-read / author-read counts and lists the uncited
  literature claims and named-work claims. The first 10 hits of each new category are read by hand and their precision
  is reported before anything is called done.
- Every existing claim-ledger test still passes. No existing finding disappears.

## Risks

- Pointing phrases produce false positives, for example "prior work has shown" in a sentence whose citation sits in the
  next sentence. Q2 looks at the sentence only, and the first-10 precision check decides whether the phrase list stays.
- A names table needs upkeep. Seeding from `shorttitle` covers some of it; the report says which cited works have no
  name, so the gap is visible.
- Q1 adds a column people must fill. Only high-risk rows turn red, so the work goes where wrong claims have come from.

## As built (2026-09-30)

- **Q1 high-risk, narrowed after measuring.** On one real ledger (120 rows, none read yet), the rules as first written
  flagged 20 claims; of the first 10, 4 were worth an author's reading. The noise came from "one" as a determiner or
  pronoun, digits inside a model name, "first ... then" as a sequence, and "only" inside a compound ("text-only"). A
  number now counts only standing alone and without "one"; "first" only as "the first" or "first to"; "only" not after
  a hyphen. The same ledger then gave 8 claims, 6 worth reading. The 2 left over are the manuscript's own counts (counts of the models the manuscript itself tests); telling whose number it is was not attempted. The author accepted the narrowing the same day.
  T267 holds each narrowing.
- **Q3 narrower than written.** "Using the patterns that negative-claim-without-fulltext already uses" would have made
  "an absolute score is not meaningful in isolation" (an existing fixture) a claim that the work left something out.
  The finding uses those patterns without the copular negations (is not, are not, was not, were not).
- **Q2 on a real bibliography.** A bibliography without `shorttitle` names no work; on the real ledger all 72 cited keys
  had no name, and the report says so. A names table (`overview.ledger.names` in the workspace) is the way in.
- **Gate mode.** High-risk rows, cited negative claims and claims with no `\cite` are hard findings only for sentences
  the change added; older ones are prompts, so a commit is not blocked by what it did not touch.
- **Q6.** The changed-sentence audit takes `--ledger` (the loop passes every claim ledger as an absolute path, and a
  ledger that is not there is said, not skipped) and flags `bound_in_ledger` with the rows to update.
- **Tests.** T259–T267 (shell) and two wiring tests in the engine; each new judgement, and each narrowing, was removed
  once and its test turned red. The chat-reply rewrite gate passes the ledgers on too; no test covers that path.

