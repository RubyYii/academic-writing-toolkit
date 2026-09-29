# Part-by-part revision: what the notch answers while a manuscript is rewritten one part at a time

Status: draft (written 2026-09-29; the author decided the four answers, the plan's place and the reader-panel rule; the
rest of this document is not approved; nothing implemented)

## Problem

A manuscript declared frozen for correctness went on to be rewritten, one part at a time, over a day. The parts went
abstract, research questions, introduction, related work. Each part ran the same steps:

1. a plain-language story of the part, approved by the author;
2. candidate English sentences, registered with the changed-sentence gate as not yet in the draft and not yet decided;
3. the author's decision in the conversation;
4. a commit that lands the part;
5. a build that is ready to upload, and an updated response letter.

The notch showed a revision ring built for rounds over the whole paper. It read the ledger's 冻结 and a ready build as
"landed", and asked for nothing. A build is ready to upload within minutes of every landing, so it says nothing about
whether the rewriting is over. `2026-09-29-ring-rounds-and-stages` (with the fix that a freeze must be earned) now
shows the contradiction, but it still cannot say where the work is.

## Decided by the author (2026-09-29)

- **A1** While parts are being rewritten, the notch answers four things:
  - how far the current part has got (story → candidates → your decision → landed → built), and how many candidates
    wait on a decision;
  - progress over the whole plan (parts landed of parts planned, and which remain);
  - whether the landed parts agree with one another;
  - the checks and the reader panel, which stay on the notch.
- **A2** The plan (which parts, in which order) is written as the claims ledger's 待做 items of type 写作, one per part,
  each naming the sections it covers. The loop holds the plan against what the draft actually does.
- **A3** The reader panel is asked for once, after every part of the plan has landed, not after each part.

## Goal

The notch says where the rewriting is, from signals the loop can check. The plan is declared, but a contradiction
between the plan and the draft is shown, never smoothed over.

## Non-goals

- Writing the plan. The author or an agent writes the 写作 items. The loop reads them and checks them.
- Judging whether a part is good. That stays with the gate, the ledgers and the readers.
- Paragraph-level tracking. A part is one or more sections, because a section is what the index and the checks already
  name. See Q1.
- The story page itself. It is not on main yet (the story-layer branch). This mode shows the story step only when a part
  names its page.

## Decisions

**P1 A part is a 写作 item with sections.**
- The item is `## 待做 N7 <what>` with `类型：写作`, a new field `节：<section prefixes or files>` (for example `节：W` or
  `节：sections/02_related_work.tex`), and optionally `讲法：<story page path>`.
- Part-by-part mode is on while at least one such item is open. It is not switched on or off by the stage name.

**P2 Each step is read from something the loop can see.**

| Step | Seen when |
|---|---|
| 讲法 story | the item names a story page and the page carries an approval uuid found in the transcripts; otherwise "not seen" |
| 候选 candidates | acceptance-ledger rows that name the item's id and whose sentence is **not** in the current draft |
| 等你裁 your decision | there are such candidates |
| 落稿 landed | the item is `已做 <date> <evidence>`, and a commit on or after that date changed the part's sections |
| 构建 built | the build report's source commit contains the landing commit |

- Whether a candidate is in the draft is measured, not read from its note. A candidate that entered the draft stops
  waiting on its own. One that never did stays counted.

**P3 The plan is checked against the draft.** Each contradiction is listed, and counts as waiting on the author:
- a part marked landed whose sections changed afterwards by more than a correctness-sized amount (the same threshold
  as the freeze rule);
- sections changed that no open or landed part covers ("changed outside the plan");
- the stage saying 冻结 while parts are open. This replaces the freeze-broken question in this mode: the rewriting is
  expected, the stage line is what is stale.

**P4 Progress over the plan** is the count of 写作 items closed (已做 or 不做) of all 写作 items, and the open ones in the
ledger's order. The current part is the first open item, or the one whose sections changed last.

**P5 Agreement between landed parts, first version.** The count of whole-draft findings that fall in landed parts'
sections:
- paper-state findings: over-reach, a required wording missing in a place, an unscoped quantifier;
- changed-sentence flags not yet accepted.

Terminology drift across parts (a term renamed in one part and not the others) is not measured in this version; see Q2.

**P6 The notch.** In this mode the ring shows the current part's five steps. Above the route it says
`第 4/7 部分：<title>`. Under the route it gives the agreement count. The three columns are:
- 等你裁: candidates waiting, plus contradictions, plus register items;
- 要重跑: checks out of date, but not the reader panel until every part has landed (A3);
- 投稿: as now.
- This needs one optional field in lintel (`progress`), added to lintel before the loop exports it.

**P7 After the last part lands**, the mode ends. The ring returns to rounds, and the stale reader panel is asked for once.

## Acceptance

1. **Fixtures.** A synthetic draft, ledger and acceptance ledger per rule, each tested on the old code first:
   - each step seen and not seen;
   - a candidate that enters the draft stops waiting;
   - a landed part changed afterwards;
   - a change outside the plan;
   - 冻结 with open parts;
   - progress and the current part;
   - the agreement count;
   - the reader panel held until the last part lands, then asked for once.
2. **Mutations.** Each rule has a redcheck mutation that turns its test red.
3. **Replay on one real workspace, read only.** The plan is drafted from its commit history and shown to the author
   before it is written into any ledger. The replay shows:
   - the current part;
   - progress;
   - the candidates waiting;
   - the contradictions.
   Each count is checked by reading the rows behind it.
4. **Screenshots** of lintel's own window for a part in progress and for the last part landed. Only the current
   appearance is taken; the system appearance is not changed.

## Open questions for the author

- **Q1 How big is a part?** Recommended: one or more sections. The index and every check already name sections, and the
  real day's parts were sections (the research questions sit inside the introduction and can be named by its label
  prefix). The alternative is paragraphs, which the index can also name but which move with every insertion.
- **Q2 Terminology across parts.** Recommended: leave it out of the first version and add it once a term list exists
  (the title-word coverage item). A count without a list would be a guess.
- **Q3 The real plan.** Recommended: I draft the 写作 items for the manuscript in progress from its commit history
  (parts already landed marked 已做 with their commit). The author and that manuscript's session check the draft before
  it goes into their ledger. The loop does not write their ledger.
