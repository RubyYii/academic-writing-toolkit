# The manuscript ring: stages that can be seen, rounds that end, and a freeze mode

Status: implemented on the loop side (author approved Q1–Q3 as recommended, 2026-09-29; unit tests and red check pass locally; CI not run). R6's two labels in lintel itself are not done.

Takes over two items that `2026-09-25-review-gap-closure.md` §4.6 left as design only:
- a way for 落稿 to be seen;
- labels that tell how far the round got from where it waits.

The third item there, a status for work deferred past submission, belongs to the claims ledger and stays apart.

## Problem

The author looked at the notch on a frozen manuscript and asked two things: why the ring always stands at 读者组, and
whether its stages make sense. Read against the code and that manuscript's data, the answer is that the ring cannot
stand anywhere else, and for reasons that have nothing to do with the paper.

1. **Three of the seven stages can never light up.**
   - The ring marks the furthest stage that moved within the round (`reached`). It only records movement in four:
     你的意见, 改稿, 检查, 读者组.
   - 设计 is always "not seen": the intent card is never read.
   - 你核对 is always "not yet": a closed review gate starts a new round, so within a round it never shows done.
   - 落稿 is always "not seen": only commits are known, and nothing says which one landed.
   - So once a reader panel runs in a round, the marker sits at 读者组 until the round ends.
2. **A round ends only when a review gate closes in the risk register.**
   - The author's way of working moved on: story pages, a freeze, the conversation's list. No review gate closed
     after that.
   - One "round" has now run four days and more than a hundred commits.
3. **The freeze is not known.**
   - The global rules say that once the author calls a manuscript uploadable, it takes correctness fixes only.
   - The ring still hangs 读者组 · 过期 as a rerun after each fix. That pushes toward an expensive panel nobody meant
     to run in a freeze.
4. **One marker answers two questions.** "How far did this round get" and "where does it wait" are drawn as one
   square labelled 做到这里. The waiting stage is only a coloured dot.

Meanwhile the signals that do say where the paper stands are already on the notch, and they are right:
- the paper state (待作者终审);
- the submission build's cell (可上传, from a build report with `ready_to_upload` at a named source commit).

The ring contradicts them.

## Goal

Every stage on the ring can be seen from data the loop already has, or it is not on the ring. A round ends at a
landing or a review, whichever came later. A frozen manuscript gets a shorter ring that does not ask for a reader panel.
"Reached" and "waiting at" are two labels.

## Non-goals

- New sources of truth. Every signal below is already read by the loop:
  - the build report;
  - the risk register with its message uuids;
  - the conversation transcripts;
  - the claims ledger's stage;
  - the intent card path.
- Deciding when a paper is ready. That stays the paper state's and the author's.
- A new notch layout. lintel keeps its segments; only their states and labels change.

## Decisions

**R1 落稿 is seen from the build report.**
- A round has landed when the configured build report (`overview.build_report`) says `ready_to_upload`.
- Its `source_commit` must be the draft's current commit, or an ancestor whose later commits touch no draft file.
- The stage shows the source commit.
- If the draft moved on after the landing, the stage shows "改过了" (changed since), not "done".
- Without a build report, 落稿 stays 只有提交, as now.

**R2 你核对 is seen from the author's decision after the last change.**
- It is done when a register decision, of any gate, is dated after the round's last rewrite.
- The decision's author-message uuid is resolved to a time through the transcripts, so a same-day decision is
  ordered correctly.
- A decision with no uuid falls back to its date, and the ring says it is date-only.
- It no longer requires the gate's wording to contain 核对.

**R3 设计 is seen, or it leaves the ring.**
- It is done when the configured intent card (`target.intent_card`) changed within the round.
- Without an intent card configured, the stage is removed from the ring, instead of standing there "not seen".
- The table still lists it.

**R4 A round starts at the later of the last landing and the last review decision.**
- A landing (R1) ends a round. A decision after it (R2) also ends one.
- The register's review gates keep working as before; they are one kind of decision.

**R5 Freeze mode.**
- A manuscript is frozen when:
  - the claims ledger's stage name begins with a word from `ring.freeze_stages` (default: 冻结, 终检); or
  - `ring.freeze` is true.
- Frozen, the ring is 你的意见 → 改稿 → 检查 → 落稿:
  - 设计, 读者组 and 你核对 are not on it;
  - a stale reader panel is said in the table as 冻结期不重读（改动 N 处）, not hung as a rerun;
  - the rerun count on the notch does not include it.
- The paper state line is unchanged.

**R6 Two labels.**
- The export already carries `reached` and `current`. lintel draws:
  - 走到 at `reached`;
  - 卡在 at `current` when a stage waits;
  - nothing extra when they are the same stage.
- The legend's 做到这里 becomes 走到.

## Acceptance

1. **Fixtures.** A synthetic workspace per decision, each tested on the old code first:
   - R1: a ready build report at the head. The old code does not light 落稿; the new code does.
   - R1: one commit after the report. The new code shows 改过了.
   - R2: a register decision after the last change, with and without a uuid.
   - R3: no intent card. The stage is gone from the ring.
   - R4: a landing mid-round. The round restarts.
   - R5: a ledger stage 冻结. Reader staleness is not a rerun, and the ring has four stages.
   - R6: `reached` and `current` differ, and both are exported.
2. **Mutations.** Each rule has a redcheck mutation that turns its test red.
3. **Replay on one real workspace, read-only.**
   - Before: the ring stands at 读者组, with a rerun for the panel.
   - After:
     - four stages;
     - reached 落稿 at the build's source commit, or 改过了 if the draft moved;
     - no panel rerun;
     - the round's start date moved from the last review gate to the later landing or decision.
4. **Screenshots** of the notch, light and dark, for the frozen ring and the full ring. They are taken on lintel's own
   windows only.

## Open questions for the author

- **Q1 How a freeze is known.** Recommended: the ledger's stage name, since the author already writes 冻结 there, with
  `ring.freeze` as the override. The alternative is config only, which is one more place to remember.
- **Q2 A stale reader panel in a freeze.** Recommended: said in the table with the change size, never hung as a rerun.
  The author asks for a panel when a correctness fix changes meaning. The alternative is a rerun only past a size
  threshold, which risks the same nagging.
- **Q3 设计 without an intent card.** Recommended: drop it from the ring. The alternative, "not seen", is what the ring
  shows now, and it reads as a stage never done.

## Decided (2026-09-29, the author: as recommended)

- **Q1** A freeze is read from the claims ledger's stage name (冻结, 终检), with `ring.freeze` to force it.
- **Q2** In a freeze a stale reader panel is said with its change size and never hung as a rerun.
- **Q3** Without an intent card, 设计 leaves the ring.

## As built

- `loop/ringinputs.py` gathers the four inputs. Each is read on its own; one that fails is reported and leaves the
  ring's old behaviour for that part. `ring.ring` takes them as optional arguments; without them it is unchanged, and
  every earlier ring test passes unmodified except one that asserted 设计 on a workspace with no intent card.
- Decision times come from the author message's uuid in the transcripts. Found times are cached; a uuid not found is
  looked for again only when the transcripts have grown.
- An intent card not changed within the round is drawn "not seen" with the note 这一轮没动, so the round never waits
  on it. A landing followed by a draft change is "not yet" with the note 改过了.
- The frozen panel note (`frozenNote`) is not exported to lintel yet: lintel rejects unknown fields, so it waits for
  the lintel side. The per-turn coverage line still lists the stale panel, as the spec asked.
- R6 on the loop side is the existing `reached` and `current` fields. lintel still draws one square; the 走到 / 卡在
  labels are the next step, with screenshots.

## Acceptance on one real workspace (2026-09-29, read only)

- Before: seven stages, the marker at 读者组, the panel hung as a rerun.
- After: frozen (the ledger's stage), four stages, reached 落稿 at the build's source commit, and the panel said as
  not re-read in a freeze. Every decided register item was timed by its message.
- Minutes later the manuscript committed a text change after that build; 落稿 then read 改过了.
- A card carrying the new ring passes lintel's own validator.
