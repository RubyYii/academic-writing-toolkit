# Growing the probe set from defects the checks missed, one confirmed batch at a time

Status: draft (2026-10-05). The author approved the idea ("grow the red-check set by target band, with the author
confirming each defect"); this spec has not been read. Nothing is built yet. Batch 1 is chosen and measured, and it
waits on the author's confirmation (gate 1).

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

The three missed ones go to the author for gate 1.

## Open for the author

- Q1 Should a covered candidate still get a probe, to pin the rule that catches it? Default: no, following
  EnvHarness's rule against non-challenging tasks. The test already lists checks with no probe.
- Q2 Batch size. Default: three, because the author's attention is the scarce part.
