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
   gate flagged the new sentence, but only for a comma. A reason was given for the comma, and the count went through.
   An outside reader caught it.
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
- Look for `the|this|these|that|those` followed by up to two words and then one of those content words. A possessive
  counts as its noun (`audit's` is `audit`). Ordinals and their kin (`first`, `second`, `third`, `other`, `former`,
  `latter`, `same`, `following`, `last`) are not nouns here.
- It is a hit only if the word appears in no target sentence of the same file before the referring sentence. A noun
  still introduced elsewhere is not lost.
- A hit flags the removal as `took_antecedent`, and names the referring sentence and the phrase. The reason goes on
  the removal, as for any flagged removal. The referring sentence is not rewritten or flagged itself.

**D2 A share beside the draft's other shares of the same total.**
- A share phrase is `K of (the) N`, then up to two words, then a plural noun: "one of three later sensors", "two of the
  three sensors". K and N are digits or number words up to twelve.
- When a changed or added sentence has a share phrase that its base did not have, take its noun and its total N.
- List every other target sentence with a share of the same noun and the same total, and a different K.
- If there is at least one, the sentence is flagged `count_elsewhere`, with those sentences listed. If there is none,
  nothing is said. Flag or note is Q1.
- Why so narrow: a first version that listed every count of the same noun set about twenty sentences beside the real
  incident, most of them about something else (how many were run, on what machine). Keeping the total fixed and the
  share different left the sentences that actually disagreed.

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
   - The three real incidents (1–3 above), and the one the prototype found, must each be flagged.
   - On the manuscript's recent commits, every new flag is read and counted as real or noise.
   - Stop rule: if more than half are noise, narrow the rule before merging, and write the leftover gap here.
4. **Loop.** The gate row reports the new flags like the others. No other row changes.

## Evidence for the open questions (prototype, read only)

A prototype of D1 and D2, built on the gate's own sentence reader and pairing, was run over the 43 commits of one real
manuscript's last two days, plus the two incidents that never reached a commit (rebuilt from the commits around them).
The per-sentence readings are kept in the private workspace, not here.

- **Where incidents 1–3 sit in the gate.** Incidents 1 and 2 are removals, not revisions. Incident 1's reference is ten
  sentences after the removed one, in the same paragraph (an abstract). Incident 2's is the next sentence. Incident 3's
  candidate was flagged for a comma only.
- **D1 windows.**
  - Next five sentences: 4 hits. Misses incident 1.
  - Rest of the paragraph: 8 hits. Catches incidents 1 and 2, and one more that nobody had noticed and that is still in
    the draft. Of the other five, one is borderline and four are noise. Two of the four go once possessives and
    ordinals are handled, leaving 6 hits: 3 real, 1 borderline, 2 noise.
  - Rest of the file: 30 hits, nearly all across paragraphs and nearly all noise.
- **Q3, revisions.** Extended to nouns dropped from a revised sentence: 5 more hits in 4 places, none real on reading.
  They were the paper's central object (which every reader knows), a noun with its own relative clause, and a
  phenomenon the whole section is about.
- **D2.**
  - Incident 3's candidate: the narrowed rule lists 6 sentences, and the first three all state the other share.
  - Over the 43 commits: 10 new share phrases; 5 would be flagged. 4 of the 5 are the very pair of shares that readers
    confused in incident 3.

## Open questions for the author

- **Q1 Is a share that disagrees a flag, or a note?**
  - Recommended: a flag, needing a reason, and only when D2 finds another share.
  - In incident 3 the gate already flagged the sentence, for a comma. The reason written answered the comma, and the
    count went through. A note would sit on the same line and not be answered, like any other line that is not
    counted.
  - The cost is small: 5 flags in 43 commits.
- **Q2 How far after a removal to look?**
  - Recommended: the rest of the paragraph, with no cap.
  - A five-sentence cap misses incident 1. The whole file triples the hits, with nothing more caught.
  - The gate currently reads a file as one list of sentences. Knowing where a paragraph ends needs one small change to
    how it reads the text: it already breaks units at blank lines, and the change keeps that boundary.
- **Q3 Removed sentences only, or also words dropped from a revised sentence?**
  - Recommended: removed sentences only.
  - All three real cases were removals. The revision hits were all noise.
  - Add revisions if a real case turns up.
