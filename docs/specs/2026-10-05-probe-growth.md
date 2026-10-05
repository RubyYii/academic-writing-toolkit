# Growing the probe set from defects the checks missed, one confirmed batch at a time

Status: batch 1 implemented locally (2026-10-05). The author approved the idea ("grow the red-check set by target
band, with the author confirming each defect") and confirmed all three defects of batch 1 (gate 1, "三条都算"). The
spec itself has not been read by the author.

What was run for batch 1:
- Each probe's bad draft failed on the old code; each new unit test that asserts a flag failed there too.
- 20 red-check mutants (`probegrowth`) each turned their test red.
- A new cross-check: no probe's corrected twin raises any probe's flag. Loosening the near-repeat threshold to 0.5
  turns it red.
- Read-only runs on one real draft, below.

Python 3.8 was checked by grammar only. CI has not run.

## Problem

The probe set (`experimental/writing-loop/engine/tests/probes/`, spec 2026-09-25 §4.1) holds six synthetic drafts. All
six are for the changed-sentence gate, and each was added after an incident. Meanwhile the private gap notes from one
manuscript record about sixty defects in the text that the checks of the time let through. Nothing decides which of
them should become probes, so the set grows only when someone remembers to add one.

Two things found while picking the first batch:

- A note's "no check catches this" goes stale. One candidate, a rewrite that copies another section's sentence word
  for word, is caught today by `duplicates_elsewhere`. Gate 2 has to be measured, not read from the note.
- About 25 of the 58 candidates need reading to see: the meaning, the code, a figure, or a cited source. No string
  rule will catch those, and they belong with the reader panels and the grill.

## Goal

A defect becomes a probe only after three gates (EnvHarness's write–verify loop, with the author as the benchmark's
own verdict):

1. **Real**: the author confirms it was a defect.
2. **Challenging**: today's checks miss it, measured on its synthetic bad draft.
3. **Solvable**: a rule can be written that flags the bad draft and not its corrected twin.

## Non-goals

- Defects a model makes up with no incident behind them (R-Zero-style self-play). Version 1 draws only on recorded
  incidents.
- Defects that need reading. They are closed as "needs reading" and stay in the gap notes.
- Adding a probe automatically. Every probe lands with its rule in a reviewed change.
- Loosening an existing check so that a probe passes.

## Decisions

**D1 Where things live.** The candidate list names a real manuscript, so it stays in the private workspace
repository. A probe in this tree is synthetic, with no manuscript wording, names or results, as now.

**D2 Gate 1.** The author confirms a batch of at most three. The confirmation (message uuid) goes in the private
candidate list. Unconfirmed candidates are not built.

**D3 Gate 2.**
- The synthetic bad draft is run through the checks that read that kind of text.
- If one of them already flags the defect by name, the candidate is closed as covered, with the flag recorded.
- A style flag on the same sentence (`longer`, `adverb`) does not count as catching it.

**D4 Gate 3.**
- The new rule flags the bad draft.
- It flags neither the twin nor the twins of the existing probes.
- A read-only run on one real draft counts its other hits. The count is reported with the rule; no threshold is fixed
  in advance.
- At most two revisions. After that the candidate is closed as "needs reading", with a gap note saying why.

**D5 The test.**
- `test_probes.py` gains a `CHECKS` entry when a probe names a check other than the sentence gate.
- `expect_flag` names the new rule's flag, so a probe caught by a different rule does not count.

## Batch 1 (measured 2026-10-05, gate 2 run on synthetic drafts)

| Defect | Today | Gate 2 |
|---|---|---|
| A sentence rewritten to copy another section's sentence word for word | `duplicates_elsewhere` | covered |
| An introduction sentence that repeats the abstract except for one word | nothing | missed |
| "N times more often than chance" with no hit count or denominator beside it | `longer`, `adverb` only | missed |
| `\label` after a run-in `\paragraph`, so `\ref` prints the enclosing section's number | no script reads it | missed (by search, not by running every check) |

The three missed ones went to the author, who confirmed all three (gate 1).

## Batch 1 results (gate 3)

| Defect | Rule | Bad / twin | Other hits on one real draft |
|---|---|---|---|
| A sentence that repeats another but for a word | sentence gate, `repeats_elsewhere`: a changed sentence of 8 words or more whose word sequence matches another sentence of the draft at difflib ratio 0.8 or more, and is not the same (that stays `duplicates_elsewhere`) | flagged / not | All pairs in the draft: 3 at 0.8 or more, 12 at 0.7. Each of the 3 restates an abstract or conclusion sentence in the body; most of the 12 are paraphrases, which is why the threshold is 0.8. The latest real round flags 2 more sentences, one such pair |
| A multiple of chance with no count beside it | sentence gate, `multiple_without_count`: "N times … chance/random" or a math multiple followed by "chance" ("the MATH chance level" excluded), with no "K of N", "K hits in N" or "K/N" in the sentence or the one either side | flagged / not | The draft states a multiple of chance in 14 sentences: 5 with a count in the sentence, 3 with one in a neighbour, 6 with none. The latest real round flags 1 more sentence |
| A `\label` on a heading with no number | new check `audit-cross-refs.py` (loop id `cross-refs`), LaTeX, follows `\input`: a label inside or right after a starred heading or one deeper than secnumdepth (last `\setcounter`, else the class default), reported only when a `\ref`, `\cref` or `\autoref` prints it | flagged / not | 7 labels, each on a run-in paragraph. The compiled draft's `.aux` gives all 7 the number of the section around them, so 7 of 7 are true; two pairs of them share a number |

Three remarks:
- The real draft's counts for the two sentence-gate rules are not an out-of-sample test: the 0.8 threshold and the
  two exclusions of the second rule (a random draw of sub-pools, "the MATH chance level") were set after reading that
  draft's hits. The third check was not changed after the run, and the `.aux` comparison is independent of it.
- The sentence-gate rules flag only changed sentences, so the counts above are what a round could raise, not what
  the next round will. The cross-reference check reads the whole draft, so a workspace that turns it on sees all of
  its hits in the first run.
- The cross-reference check does not see a label placed further down the paragraph, or references made from another
  document (an `xr` prefix). Both stay with the reader.

## Open for the author

- Q1 Should a covered candidate still get a probe, to pin the rule that catches it? Default: no, following
  EnvHarness's rule against non-challenging tasks. The test already lists checks with no probe.
- Q2 Batch size. Default: three, because the author's attention is the scarce part.
- Q3 The cross-reference check is on for every LaTeX workspace, needing no configuration. On the measured manuscript it
  would show its 7 hits in the first run after the toolkit is updated. Default: on, because all 7 are true and the
  check is cheap. Making it opt-in is one line in the catalogue.
