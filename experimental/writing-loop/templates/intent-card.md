# Intent card

Copy this file into the workspace and name it in `config.json` as `target.intent_card`. Kept under the workspace's
`human/` folder it is the author's own; anywhere else it is a draft, and the loop says so.

The engine reads three things from this file: whether it exists, its approval line, and its hash. It does not read the
sections below. They are for the author and for whoever revises the paper. What keeps a section from being dropped
when the card is revised is the risk register: see "Writing decisions go in the register" in the README.

Mark each part the author has approved with the uuid of that message. Mark each part the author has not approved
with ◌ (a default that anyone may overturn).

## 读者 · Reader

Who reads the paper, what they already know, and what they do not.

## 读者读完要带走的 · What the reader carries away

- **M1** …
- **M2** …

Two to four points. The readers skill measures whether readers carry these away.

## 不属于意图的 · Not part of the intent

Things a reader might take away that the author does not claim. A rewrite that adds one of these is what the scan
below looks for.

## 优势句 · Advantage sentence

What this paper gives its reader that the nearest work does not. Give the uuid of the message in which the author
approved it, or mark it ◌.

Where it goes follows the story page below, not a fixed slot. An earlier version of this template put it first in
the abstract. In the round that changed this, the same-genre papers of the target venue opened with who relies on the
work and what is at stake, stated the problem, and only then said what the paper does; the author also asked for the
problem before the method. Check the venue's exemplars before placing it.

The first paragraph of the introduction makes the same claim in its own words and goes further. It does not restate
the abstract sentence by sentence. In the round this template comes from, the abstract and the introduction were
both made to open with this sentence, and in the next reader panel most readers said the introduction's first
paragraph repeated the abstract. Those readers were AI readers, so treat this as a warning, not a measurement.

## 讲法页 · Story page (the narrative order in plain words)

Settle this page with the author before any sentence of the abstract or the introduction is rewritten. It is the
outline the sentence work follows. In the round this section comes from, a month of sentence-level revision kept
failing the author's reading of the PDF, while every check, each of which reads sentences, passed each version: the
story had never been written down in plain words and agreed first.

One block per step, in the author's own language. A common order is problem → gap → approach → strongest result →
significance; adjust it to how papers of the same genre in the target venue are told (next subsection), and give the
uuid of the author's approval for each step, or mark it ◌.

For each step:
- **Plain words**: one or two sentences that a reader outside the subfield can follow. No figures here.
- **Evidence**: the numbers, sources or sections behind it. Figures go here, not in the plain words.
- **The reader can say**: what a reader who took the step in could say in their own words. A reader panel scores
  against this line, so the author approves it before any panel uses it; a line written by the model and used
  unapproved scores the model's own reading of the paper.
- **Lands in**: the sentences or paragraphs of the abstract, the introduction, the results and the conclusion that
  carry it.

Four questions to read a draft against the page:
1. Does the first sentence say who relies on this and what is at stake, or does it open on a figure or a method?
2. Does the problem land on a judgement people would get wrong, not only on a measure being imprecise?
3. Are the findings first said in words, with few figures, after the approach?
4. Does the end say who the work is for and what it did not test?

### Same-genre exemplars

Pick two or three papers of the same genre in the target venue (an evaluation, a measurement, a re-examination of an
existing practice, and so on) and lay each abstract out sentence by sentence against the steps. Archive the originals,
register every quoted fragment, and verify the fragments against the archived text with a check that fails on an
injected fake fragment. An exemplar shows what the venue accepts; it is not a template to copy.

Read in the originals when this section was written (2026-09-28):
- Mensh and Kording, "Ten simple rules for structuring papers", PLOS Computational Biology 13(9): e1005619 (2017),
  doi:10.1371/journal.pcbi.1005619. Context, content, conclusion at every scale; in the abstract, do not give results
  before the reader is ready for them; one informal sentence per planned paragraph before the prose.
- Nature, "How to construct a Nature summary paragraph", https://www.nature.com/documents/nature-summary-paragraph.pdf
- Plaxco, "The art of writing science", Protein Science 19(12):2261–2266 (2010), doi:10.1002/pro.514
- Koopman, "How to Write an Abstract" (1997), https://users.ece.cmu.edu/~koopman/essays/abstract.html. It asks for
  results in numbers, and warns against numbers that are easily misread; the guides disagree on figures in the
  abstract, and none of them opens an abstract with one.
- USC Libraries, "The C.A.R.S. Model", https://libguides.usc.edu/writingguide/CARS (after Swales 1990)
- Lingard, "Writing for the reader: Using reader expectation principles to maximize clarity", Perspectives on Medical
  Education 11(4):228–231 (2022), doi:10.1007/s40037-022-00708-w

## 实验角色 · Experiment roles

Each experiment or section has one role:
- **core**: it holds up a point M;
- **credibility**: it makes a core result believable;
- **scope**: it says how far the results reach;
- **process history**: it tells how the work got here.

Content that serves no point leaves the main text. A pre-registered result is never deleted: it moves to the
supplement or the limitations, and it is reported as it came out.

| # | Experiment or section | Role | Serves | Where it goes | 现状 (checked against the draft on YYYY-MM-DD) |
|---|---|---|---|---|---|
| 1 | … | core | M1 | main text | 未核 |

现状 says where the item stands in the draft, as checked on the date in the header. 未核 means it was not checked
this time.

## 「稿子替你加的」扫描 · What the rewrite added

Done by hand before each round of rewrites goes to the author. It is not an automatic check.

- **What to scan**: every new or rewritten sentence in the sentence-pairs TSV. Once per paper, also scan the whole
  paper as it stands, section by section, including the appendix; this is the baseline. A scan of the abstract and
  introduction alone says nothing about the body. In the first round this was used on, the baseline found more to
  change than the new sentences did.
- **Types**: a concession; a hedge that carries no information; process narration; the paper arguing against
  itself; content with no role in the argument; framing changed after seeing the results; an undefined term.
- **Output**: `defensive-scan.tsv`, next to the pairs TSV, with one row for every new or rewritten sentence. Columns:
  - `id`, `sentence`, `type` (or `none`), `why`;
  - `fix`: what to do with the sentence, one of keep / cut / move / rewrite;
  - `judged_by`: always "machine draft";
  - `verdict`, `reason`: filled in by the author.
- **What `verdict` means**: whether the author takes the fix (`take` / `leave`), not whether the sentence stays. A
  sentence whose fix is "cut" and whose verdict is `take` is gone. Do not feed this table to
  `audit-sentence-changes.py --pairs`: there, `accepted` means the sentence stays, and for every row whose fix is not
  "keep" the two meanings are opposite.
- **Not counted**:
  - the one concrete statement of a weakness in the limitations section;
  - pre-registered results reported as they came out;
  - negations with a stated search scope ("the sources searched this time do not …").
- **Tally, once the author has given verdicts**: for each type, the rows flagged and how many fixes the author took.
  Keep the tally round by round. Whether this scan is worth automating can then be decided on more than one round.

## 验收 · Acceptance

Before a round of rewrites goes to the author, run each check and write the result on the page the author reviews,
including whether it found something that was then changed.

| # | What | How | Judged by |
|---|---|---|---|
| V1 | The paper follows the advantage sentence and the narrative order | Label each paragraph of the abstract and the introduction with its step, and check that the introduction's first paragraph does not restate the abstract sentence by sentence. For every section of the body, each results subsection and the conclusion, write which point M it serves. List what fits nowhere | Draft by the model, the author judges |
| V2 | The experiment roles have landed | "Where it goes" in the roles table matches the draft, and a search for the process-history passages finds nothing in the main text. Write the search command under the roles table | Mechanical |
| V3 | The conclusion does not argue against itself | Run the conclusion through the scan: no concession, and nowhere does the paper argue against itself | Draft by the model, the author judges |
| V4 | Paragraphs open on the point, not on figures | Read the loop's paragraph-openers check (段首). For each flagged paragraph write keep (its content is the data) or rewrite (lead with the point in plain words, figures after); the first paragraph of each chapter comes first | Draft by the model, the author judges |
