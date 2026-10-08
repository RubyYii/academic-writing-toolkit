"""Part-by-part revision (spec 2026-09-29-part-by-part-revision): the current part's steps, progress over the plan, the
plan held against the draft, agreement between landed parts. Synthetic wording throughout."""
import datetime as dt
import json
import unittest
from pathlib import Path

from loop import config as C
from loop import coverage as V
from loop import history as H
from loop import parts as P
from loop import ring as R
from loop import state as S

from fixtures import TempDir, git, make_repo, workspace


def noon(day):
    return int(dt.datetime(2026, 1, day, 12, tzinfo=dt.timezone.utc).timestamp())


MAIN = r"""\documentclass{article}
\begin{document}
\input{sections/01_intro}
\input{sections/02_related}
\input{sections/03_results}
\input{sections/04_discussion}
\end{document}
"""


def section(title, sentences):
    return f"\\section{{{title}}}\n" + " ".join(sentences) + "\n"


INTRO = section("Introduction", [f"Gauge {i} reads the bridge at noon." for i in range(1, 9)])
INTRO2 = section("Introduction", [f"Gauge {i} reads the north bridge at dawn." for i in range(1, 9)])
RELATED = section("Related Work", [f"Survey {i} measured a bridge." for i in range(1, 9)])
RELATED2 = section("Related Work", [f"Survey {i} measured a bridge." for i in range(1, 7)]
                   + ["A newer survey measured two bridges.", "Survey 8 measured a bridge."])
RESULTS = section("Results", [f"Result {i} holds for the gauges." for i in range(1, 9)])
DISC = section("Discussion", [f"Point {i} is discussed here." for i in range(1, 9)])
DISC2 = section("Discussion", [f"Point {i} is argued again here." for i in range(1, 9)])
RULES = [{"match": r"^Introduction$", "prefix": "I", "kind": "prose"},
         {"match": r"^Related Work$", "prefix": "W", "kind": "prose"},
         {"match": r"^Results$", "prefix": "R", "kind": "prose"},
         {"match": r"^Discussion$", "prefix": "D", "kind": "prose"}]

LEDGER = """阶段：冻结，只收正确性

## 主张 C1 桥的读数可信
- 证据：表 1
- 强度：强
- 允许的说法：读数可信

## 待做 N1 引言重写
- 类型：写作
- 节：I
- 状态：已做 2026-01-02 合成提交

## 待做 N2 相关工作重写
- 类型：写作
- 节：W
- 状态：在做

## 待做 N3 结果重写
- 类型：写作
- 节：R
- 状态：未做
"""

ACCEPT = ("# key\treason\twho\tsentence\n"
          "aaaaaaaaaaaaaaaa\t部分 N2 候选，未入稿\t合成\tAn unwritten survey measured nine bridges.\n"
          "bbbbbbbbbbbbbbbb\t部分 N2 候选，已入稿\t合成\tA newer survey measured two bridges.\n"
          "cccccccccccccccc\t部分 N3 候选\t合成\tResult nine holds nowhere.\n"
          "dddddddddddddddd\t方法台账 N2-104 那一行的改写\t合成\tA sentence of another ledger.\n"
          "eeeeeeeeeeeeeeee\t修订案 5 N2 的检验，不是改稿计划的一部分\t合成\tAnother unwritten sentence.\n")


def build(root, extra=(), ledger=LEDGER):
    files = {"main.tex": MAIN, "sections/01_intro.tex": INTRO, "sections/02_related.tex": RELATED,
             "sections/03_results.tex": RESULTS, "sections/04_discussion.tex": DISC, "accepted.tsv": ACCEPT}
    commits = [(files, "v1", noon(1)), ({"sections/01_intro.tex": INTRO2}, "land intro", noon(2)),
               ({"sections/02_related.tex": RELATED2}, "related in progress", noon(3))] + list(extra)
    repo = make_repo(root, commits)
    ws = workspace(root, repo, "main", glob=["main.tex", "sections/01_intro.tex", "sections/02_related.tex", "sections/03_results.tex", "sections/04_discussion.tex"])
    cfg = C.load(ws)
    cfg["draft"]["format"] = "latex"
    cfg["draft"]["sections"] = RULES
    cfg["draft"]["accepted_rewrites"] = "accepted.tsv"
    led = Path(root) / "claims.md"
    led.write_text(ledger, encoding="utf-8")
    cfg["claims"] = str(led)
    C.save(ws, cfg)
    cfg = C.load(ws)
    vs = H.load_versions(cfg)
    H.assign_ids(vs)
    head = git(repo, "rev-parse", "HEAD")
    (Path(ws) / "index" / "sentences.json").write_text(json.dumps({"head": head, "versions": vs}), encoding="utf-8")
    return repo, ws, C.load(ws)


def compute(root, **kw):
    repo, ws, cfg = build(root, **kw)
    report = kw.get("report")
    return P.compute(cfg, ws, S.compute(cfg, ws), report), repo


class PartsTest(unittest.TestCase):
    def test_the_current_part_its_candidates_and_progress(self):
        with TempDir() as root:
            p, _ = compute(root)
            self.assertEqual((p["total"], p["closed"]), (3, 1))
            self.assertEqual(p["current"]["id"], "N2", "the open part whose sections changed last")
            self.assertEqual(p["current"]["candidates"], 2)
            self.assertEqual([c["key"] for c in p["current"]["waiting"]], ["aaaaaaaaaaaaaaaa"],
                             "a candidate that entered the draft no longer waits, whatever its note says")
            n1 = next(x for x in p["parts"] if x["id"] == "N1")
            self.assertTrue(n1["landing"])
            self.assertEqual(n1["changed_after"], 0)

    def test_a_freeze_with_open_parts_is_said(self):
        with TempDir() as root:
            p, _ = compute(root)
            [f] = [c for c in p["contradictions"] if c["id"] == "冻结"]
            self.assertIn("还有 2 部分没落稿", f["text"])

    def test_a_landed_part_rewritten_again_is_said(self):
        with TempDir() as root:
            again = section("Introduction", [f"Gauge {i} is read twice a day." for i in range(1, 9)])
            p, _ = compute(root, extra=[({"sections/01_intro.tex": again}, "intro again", noon(4))])
            [c] = [c for c in p["contradictions"] if c["id"] == "N1"]
            self.assertIn("标了落稿，之后又改了", c["text"])

    def test_a_part_marked_landed_without_a_commit_that_day_is_said(self):
        with TempDir() as root:
            p, _ = compute(root, ledger=LEDGER.replace("已做 2026-01-02", "已做 2026-01-05"))
            [c] = [c for c in p["contradictions"] if c["id"] == "N1"]
            self.assertIn("那一天那几节没有提交", c["text"])

    def test_change_outside_the_plan_is_said(self):
        with TempDir() as root:
            p, _ = compute(root, extra=[({"sections/04_discussion.tex": DISC2}, "discussion", noon(4))])
            [c] = [c for c in p["contradictions"] if c["id"] == "计划外"]
            self.assertIn("改了计划外的", c["text"])
        with TempDir() as root:
            p, _ = compute(root)
            self.assertFalse(any(c["id"] == "计划外" for c in p["contradictions"]))

    def test_built_when_the_report_contains_the_parts_last_commit(self):
        with TempDir() as root:
            repo, ws, cfg = build(root)
            head = git(repo, "rev-parse", "HEAD")
            p = P.compute(cfg, ws, S.compute(cfg, ws), {"ready_to_upload": True, "source_commit": head})
            self.assertTrue(p["current"]["built"])
            first = git(repo, "rev-list", "--max-parents=0", "HEAD")
            p = P.compute(cfg, ws, S.compute(cfg, ws), {"ready_to_upload": True, "source_commit": first})
            self.assertFalse(p["current"]["built"])

    def test_with_every_part_closed_the_mode_is_off(self):
        with TempDir() as root:
            led = LEDGER.replace("- 状态：在做", "- 状态：不做 2026-01-03 合成").replace("- 状态：未做", "- 状态：不做 2026-01-03 合成")
            p, _ = compute(root, ledger=led)
            self.assertIsNone(p)

    def test_the_card_carries_the_progress(self):
        from loop import lintel as LN
        with TempDir() as root:
            p, _ = compute(root)
            out = LN._ring({"rows": []}, name="t", last_comment_at=None, last_change_at=None, ring_inputs={"parts": p})
            self.assertEqual(out["progress"], "第 2/3 部分：相关工作重写（已落 1）")
            self.assertEqual([s["key"] for s in out["segments"]][:3], ["story", "candidates", "decide"])

    def test_the_ring_inputs_carry_the_parts(self):
        from loop import ringinputs as RI
        with TempDir() as root:
            repo, ws, cfg = build(root)
            got = RI.parts(cfg, ws)
            self.assertEqual(got["current"]["id"], "N2")
            self.assertIsNone(RI.parts({**cfg, "claims": None}, ws), "no ledger, no parts")

    def test_the_ring_is_the_current_parts_steps(self):
        with TempDir() as root:
            p, _ = compute(root)
            rows = [dict(id="readers", name="读者组", status=V.STALE, detail="", last_at="2026-01-01T00:00:00+00:00", changed=40),
                    dict(id="fingerprint", name="文风", status=V.STALE, detail="", last_at=None)]
            r = R.ring({"rows": rows}, parts=p, name="t")
            self.assertEqual([s["key"] for s in r["segments"]], ["story", "candidates", "decide", "land", "check", "build"])
            decide = next(s for s in r["segments"] if s["key"] == "decide")
            self.assertEqual((decide["state"], len(decide["items"])), ("hanging", 1))
            self.assertFalse(any(i["id"] == "readers" for s in r["segments"] for i in s["items"]),
                             "the reader panel waits until every part has landed")
            self.assertTrue(any(i["id"] == "fingerprint" for s in r["segments"] for i in s["items"]), "checks stay")
            self.assertEqual(r["progress"], "第 2/3 部分：相关工作重写（已落 1）")
            self.assertEqual(r["reached"], "candidates", "how far this part got, not the draft's latest build")
            self.assertEqual(next(s for s in r["segments"] if s["key"] == "build")["state"], "open")
            self.assertEqual(r["waiting"], 2, "one candidate and the freeze contradiction")
            self.assertIn("对不上", r["frozenNote"])


if __name__ == "__main__":
    unittest.main()
