# Changed-sentence gate: what a deletion takes with it, and a count that disagrees

Status: draft (written 2026-09-29; the author approved starting on this line of work; nothing in this document is
approved yet; nothing implemented)

## Problem

A manuscript rewritten one part at a time is mostly deletions and moves. The changed-sentence gate
(`.claude/skills/audit/scripts/audit-sentence-changes.py`) judges each changed sentence and each removed sentence on
its own. Four things happened on one real manuscript, and every check passed each time:

1. A sentence was deleted. A later sentence in the same paragraph still said "the X", and X had been introduced only in
   the deleted sentence. A reader panel caught it.
2. The same again, with the following sentence. The author caught it by reading.
3. A denominator was added for clarity ("one of N later Ys"). Elsewhere the draft said two of those N do the thing. The
   gate flagged the new sentence, but only for length, a comma and prepositions. The author gave reasons for those, and
   the count went through. An outside reader caught it.
4. A deleted result sentence was paired with an unrelated new sentence, so it was never judged as a removal. The
   method-ledger check caught it, because the sentence had a ledger row.

Probes on the current code, with synthetic text, run before writing this:

| Probe | What the gate reports now |
|---|---|
| Delete the sentence that introduces "brass gauges"; a later kept sentence says "trust the gauges" | 1 removed, 0 flagged |
| Move one sentence, word for word, from one file to another | 0 changed, 0 flagged (already right) |
| Change "One sensor reads …" to "For one of three later sensors, …" while another sentence says "Two of the three later sensors …" | flagged for `longer`, `comma`, `prepositions`; nothing about the count |

## Goal

- When a sentence is removed, the gate names any later sentence whose "the X" may have lost what X referred to.
- When a changed or new sentence states a count of something, the gate puts the draft's other counts of the same thing
  beside it.

## Non-goals

- General coreference resolution: no parser, no model. The rules are string rules, and a person reads what they flag.
- Deciding that a reference is broken. The gate says where to look.
- Incident 4. It is covered by turning on the method-ledger check in the workspace where it happened (done, locally).
  A deleted sentence with a ledger row is reported by that check, not by the gate's pairing.
- Moving a sentence between files. The gate already handles a word-for-word move. Keeping five ledgers in step when a
  sentence moves is a separate problem.
- Saying where a deleted status sentence went ("exploratory", "preregistered"). A flagged removal already needs a
  reason, and the reason can say it.

## Decisions

**D1 A removal that took an antecedent.**
- For each removed sentence, take its content words (the gate's `content()`: three letters or more, not a stopword),
  and fold a plural onto its singular.
- Look at the sentences that followed it in the base and are still in the target, unchanged or revised. The window is
  Q2.
- Look for `the|this|these|that|those` followed by up to two words and then one of those content words.
- It is a hit only if the word appears in no target sentence of the same file before the referring sentence. A noun
  still introduced elsewhere is not lost.
- A hit flags the removal as `took_antecedent`, and names the referring sentence and the phrase. The reason goes on
  the removal, as for any flagged removal. The referring sentence is not rewritten or flagged itself.

**D2 A count beside the draft's other counts.**
- A count phrase is:
  - `one of N`;
  - `N of (the) M`;
  - `both`;
  - `all N`;
  - a number or number word up to twenty, followed within three words by a plural noun.
- When a changed or added sentence has a count phrase that its base did not have, take the plural noun it counts.
- List every other target sentence that states a count of the same noun.
- If there is at least one, the sentence is flagged `count_elsewhere`, with the other sentences listed. If there is
  none, nothing is said. Flag or note is Q1.

**D3 Nothing else changes.**
- Pairing, the existing flags, the exit codes and the loop's reading of the report stay as they are.
- The report counts the two new flags apart, so their volume on a real draft can be read.

## Acceptance

1. **Fixtures.** Synthetic text only. Each is run on the old code first and must be red:
   - D1: an antecedent lost, singular and plural;
   - D1: the noun still introduced earlier, so no flag;
   - D1: the reference outside the window, so no flag;
   - D2: a conflicting count, flagged;
   - D2: no other count, so nothing;
   - D2: an unchanged count, not flagged again.
2. **Mutations.** Each rule has a redcheck mutation that turns its test red.
3. **Replay, read only, in the private workspace.**
   - The three real incidents (1–3 above) must each be flagged.
   - On the manuscript's recent commits, every new flag is read and counted as real or noise.
   - Stop rule: if more than half are noise, narrow the rule before merging, and write the leftover gap here.
4. **Loop.** The gate row reports the new flags like the others. No other row changes.

## Open questions for the author

- **Q1 Is a count that disagrees a flag, or a note?**
  - Recommended: a flag, needing a reason, and only when another count of the same noun exists.
  - In incident 3, a note would have sat beside flags the author was already answering.
- **Q2 How far after a removal to look?**
  - Recommended: the rest of the paragraph, capped at five sentences. In incident 1 the reference was several sentences
    later, in the paragraph's last sentence.
  - The gate currently reads a file as one list of sentences. Knowing where a paragraph ends needs one small change to
    how it reads the text.
- **Q3 Removed sentences only, or also words dropped from a revised sentence?**
  - Recommended: removed sentences only, in this version. A revision that drops the noun is possible but noisier. Add
    it if the replay shows it happening.
