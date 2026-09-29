# Method ledger: sentences about what was done, bound to where it was done

Status: implemented (author approved Q1–Q3 as recommended, 2026-09-29; unit tests and red check pass locally; CI not run; acceptance 3 not yet read by a person)

## Problem

The loop checks claims against a claims ledger, numbers against a number ledger, and citations against saved
sources. A sentence that says what was done carries no claim, no number and no citation, so no check reads it. This
covers methods, data, design, what a figure or table shows, and a result judged without a value. On one real
manuscript, every check was current, and still an outside review and the author found three such errors:

- a figure drew two independent controls as nested pools;
- the methods named the wrong scoring function for a retriever;
- a figure note predicted a trend the supplement reports the other way round.

That manuscript then built its own method ledger and checker. The ledger is a TSV with one row per such sentence,
over a thousand rows. Each row points at a file in a pinned experiment repository at a locked commit. The checker
fails on:

- a sentence changed in the draft;
- a missing pointer;
- a manuscript line number used as a pointer;
- a verdict still open;
- a sentence in a fully covered file with no row.

It found real errors, and in use it showed six gaps:

| | Gap | What happened |
|---|---|---|
| G1 | A pointer by line number drifts | After one round of edits, rows still pointed inside the file but at other sentences, and the check passed. Only a line past the end of the file was caught. |
| G2 | `file#key` checks the file, not the key | A sentence pointed at a JSON file that held only the pooled count, not the split the sentence stated, and the check passed. More than a hundred rows use `#key`. |
| G3 | A rebuild drops rows silently | Rows whose sentence was heavily rewritten no longer matched and fell out of the ledger. The check reported zero errors: a row that is gone does not exist for it. |
| G4 | No verdict for a deleted sentence | Deleting a sentence the ledger covers can only be reported as "sentence changed". The row is then removed by hand, and the fact that the sentence was once checked survives only in git history. |
| G5 | A run-in heading is part of the sentence | `\paragraph{…}\label{…}` was stored in front of the first sentence of the paragraph. Inserting a sentence after the heading broke both rows. |
| G6 | A note that names a problem does not count | A row's note said the sentence was a post-hoc analysis not marked as exploratory, while its verdict was `match`. The check passed it for days. |

The global rule this serves says the ledger must be able to fail: when a sentence changes or the file it points at
goes away, the check reports it. G1 and G3 are places where it did not.

## Goal

The loop gets a `method-ledger` check that reads a manuscript's method ledger in the format that manuscript already
uses, fails on G1–G6 as well as the five existing error kinds, and appears as a coverage row like the other checks. A
manuscript can then drop its local checker. Adopting the check needs no rewrite of the ledger beyond the rows it
reports.

## Non-goals

- **Writing the rows.** The first pass is someone reading the code, a person or an agent whose verdicts are drafts.
  The check keeps the ledger honest after that; it does not propose rows or verdicts.
- **Judging whether a sentence matches its code.** `verdict` is recorded. The check makes sure the record is still
  about this sentence and this pointer, not that the verdict is right.
- **Exploratory labels on numbers.** Exploratory labels are carried by the number ledger, which already binds each
  printed number to its scope. The method ledger's note is read for flag words (D6), nothing more.
- **Rendered-PDF checks** (doubled full stops a document class inserts, missing ToUnicode maps). These belong to the
  build check.

## Decisions

**D1 Format: the manuscript's TSV as it is.**
- Columns: `id  loc  sentence  claim_type  pointer  evidence  verdict  note  checked`.
- `claim_type`: `procedure | data | design | depiction | result | none`.
- `loc` is where the sentence was when the row was written. It is shown, and it is never used to decide anything.
- Unknown columns are kept and ignored.

**D2 A sentence is found by its text, with headings removed.**
- The row's `sentence` must occur in the draft file at the index commit.
- Both sides are normalised the same way: comments are dropped and whitespace is collapsed.
- Leading sectioning commands with their labels are removed from both. This includes `\section`, `\subsection` and
  `\paragraph` with its `{…}` and a following `\label{…}` (G5).
- A row whose sentence is only a heading has `claim_type none` and is matched as it is.

**D3 Pointers say where, and the check reads them.** One cell holds `;`-separated pointers. Each has a repository
prefix: `e0:` names a pinned repository from config, and no prefix means the manuscript. Each has one of these forms:

| Form | Checked |
|---|---|
| `path` | exists at the pinned commit (or at the manuscript's index commit) |
| `path:12` or `path:12-20` | only into a pinned repository, where a commit does not move; the lines must exist. Into the manuscript's own sources: error `pointer-by-line` (G1). |
| `path#a.b[0].c` | the file parses as JSON and the key path resolves (G2); YAML when the file ends `.yaml` or `.yml` |
| `path@"verbatim fragment"` | the fragment occurs in the file |
| `\label{x}` | the label exists in the manuscript |

A pointer that does not parse is `pointer-missing` with the reason, never skipped.

**D4 Verdicts, with a way to retire a row.**
- The verdicts are `match | partial | mismatch | unlocated | author | none | retired <commit>`.
- `partial` needs `checked`, and it is counted apart as *pending*: it neither passes nor fails.
- `mismatch` and `unlocated` are open (`open-verdict`).
- `retired <commit>` records a sentence deleted in that commit (G4). The commit must exist in the manuscript
  repository, and the sentence must be absent. If the sentence is back, the error is `retired-but-present`.

**D5 Rows cannot vanish.**
- The check keeps the row ids of its last run in the workspace cache.
- An id that is gone from the ledger without having become `retired` is `row-dropped` (G3).
- The first run only records. A deliberate removal is written as `retired`, not deleted.

**D6 A note that contradicts its verdict is said.**
- Config `method_ledger.note_flags` is a regex. Its default covers the ways the real ledger's notes said so:
  `未标|没标|说过头|not marked|unlabelled|overclaim|post[- ]hoc`.
- A row with verdict `match` whose note matches is `note-contradicts-verdict` (G6).
- The person either changes the verdict or rewrites the note.

**D7 Full coverage where it is declared.**
- Config `method_ledger.full` lists draft files in which every sentence needs a row, for example the data and
  protocol sections.
- A sentence there without a row is `unledgered`.
- Sentences are those of the loop's index, so the split is the one every other check uses.

**D8 Fail closed.**
- Exit 0 when nothing is reported and 1 when anything is.
- Exit 2 for a ledger that cannot be read, is empty, or has no row with a pointer. Also exit 2 when the pinned
  repository or commit is not there.
- The coverage row is never green on 2.

**D9 Where it lives.**
- The script is `.claude/skills/audit/scripts/audit-method-ledger.py`, beside the number ledger's.
- The catalogue check is `method-ledger`, named 文字对代码.
- Config:

      "inputs": {"method_ledger": {"path": "audit/method-ledger.tsv",
                                   "repos": {"e0": {"path": "~/dev/experiments", "commit": "<sha>"}},
                                   "full": ["sections/03_data.tex"],
                                   "note_flags": "…"}}

- The check is stale when the ledger, a full-coverage file, the pinned commit or the draft changes.

**D10 Paper state.**
- Open verdicts and errors count in coverage, like any failing check.
- They do not hold the paper-state verdict unless the author adds a required gate for them. Whether they should hold
  it by default is open question Q2.

## Acceptance

1. **Each error kind has a fixture pair.**
   - The error kinds are:
     - `sentence-changed`
     - `pointer-missing`, with one fixture for each pointer form
     - `pointer-by-line`
     - `no-pointer`
     - `open-verdict`
     - `unledgered`
     - `retired-but-present`
     - `row-dropped`
     - `note-contradicts-verdict`
   - For each kind, a synthetic draft and ledger fail, and a twin that differs only in the fix passes.
   - Each kind also has a redcheck mutation that turns its test red.
2. **Same answers as the local checker.**
   - Run on a copy of the real ledger, read-only in the manuscript repository.
   - The new check and the manuscript's own checker give the same count for each of the five kinds they share.
   - Every difference is explained in the evidence notes.
3. **The new kinds are read, not trusted.**
   - On the same copy, the check lists the `#key` pointers that do not resolve, the `match` rows with flag words
     (the manuscript currently has more than ten), and the heading-prefixed rows that D2 now matches.
   - Each listed row is read by a person before any count is reported as a finding.
4. **Injected faults turn red on the real ledger copy.**
   - The faults are a fake key, a fake label, a line number into a manuscript file, a dropped row, and a retired row
     whose sentence is still present.
   - Each must go red after the loop's own processing of the ledger, not only on the raw file. (On the manuscript, a
     brace-expansion step in its ledger builder once hid every label from the check.)
5. **Failures are not read as passes.** An empty ledger, an unreadable ledger and a missing pinned commit each exit 2,
   and the coverage row says why.

## Open questions for the author

- **Q1 Line numbers into pinned code.** D3 allows line numbers into a pinned repository, because a locked commit does
  not move. Recommended: allow them. The alternative is fragments everywhere, which is safer and costs a rewrite of
  several hundred pointers.
- **Q2 Should open verdicts hold the paper state?** Recommended: no by default. Offer a required gate instead, so a
  manuscript that is frozen for correctness can opt in without every workspace turning 未就绪.
- **Q3 A migration helper.** It would rewrite the heading-prefixed rows (G5), which are mechanical. Recommended: yes,
  as a one-shot script that prints a diff. The ledger in the manuscript repository is never written.

## Decided (2026-09-29, the author: as recommended)

- **Q1** Line numbers into a pinned repository are allowed; into the manuscript's own `.tex` they are an error.
- **Q2** Open verdicts do not hold the paper state by default. A manuscript opts in with a required gate.
- **Q3** `--migrate-headings` prints the diff for heading-prefixed sentence cells and writes nothing.

## As built: where it differs from the decisions above

- **Pointers are recognised in the cell's text (D3).** The real ledger writes prose around its pointers ("§2",
  "the function f"), separates them with `;` or `；`, and gives bare file names and paths from a subdirectory.
  Requiring every cell to parse whole would have reported hundreds of rows that point correctly. What is checked is
  every pointer found; a cell with none is `no-pointer`.
- **Lookup order.** Pinned repositories at their commit, the manuscript at the index commit, unpinned repositories'
  working copies, the manuscript's working copy, and last the pinned repositories' working copies. A file found only
  in that last place counts as found and is said ("only on disk, not in the locked commit"). A bare name matches a
  file of that name anywhere; a path matches as a suffix; a bare name is also looked for inside zip archives the same
  cell names. These follow the manuscript's own checker, so the two agree.
- **Keys.** `a,b` after `#`: each later part is tried as a sibling of the first key's last segment, then as a key of
  its own. `[k=v]` selects an element by a field; `[x..y]` needs both ends, where an end may be a whole word inside a
  key; in a JSON Schema a field is found by name among `properties` and `$defs`.
- **Sentences (D2, D7).** A row may hold a heading's own words, so a sentence is found with headings removed or as
  written. `--full` files are split by the script itself, not by the loop's index: the script runs outside the
  engine.

## Acceptance on the real ledger (2026-09-29, a read-only copy)

- 2: the manuscript's checker and this one agree on the five shared kinds (0 each). The first run disagreed on 57
  pointers; every one was a lookup or key-syntax difference in this script, fixed above, none a finding.
- 3: new findings are 17 `match` rows whose notes carry flag words, to be read by a person; every key pointer
  resolved; 3 pointers are only on disk outside the locked commit.
- 4: a fake key, a fake selector value, a fake label, a line number into the manuscript, a dropped row and a retired
  row whose sentence is present each turned red. The first fake key did not: a counter added to the key branch had
  bypassed the key check itself. Fixed, and the injection repeated.
