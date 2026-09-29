"""loop precheck: every script check on the working tree before a commit, recording nothing. A round that deleted
repeated statements passed the checks its author ran by hand and turned two others red at the commit. Synthetic
fixtures: the bridge survey of test_coverage."""
import argparse
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

from loop import catalogue as K
from loop import cli
from loop import config as C
from loop import coverage as V

from fixtures import TempDir, git
from test_coverage import Probe, commit, reindex, setup

DRAFT_PROBE = r"""
import json, pathlib, sys
n = pathlib.Path("sections/01_intro.tex").read_text(encoding="utf-8").count("BROKEN")
print(json.dumps({"issues": ["BROKEN"] * n}))
sys.exit(1 if n else 0)
"""


def draft_check(root, seen=None, needs=()):
    """A check whose finding is read from the draft: one issue per BROKEN in the introduction."""
    script = Path(root) / "draftprobe.py"
    script.write_text(DRAFT_PROBE, encoding="utf-8")

    def argv(ctx):
        if seen is not None:
            seen.append(ctx.get("precheck"))
        return [sys.executable, str(script)]
    return {"id": "draftprobe", "name": "读稿探针", "kind": "script", "scripts": [str(script)], "formats": ["latex"],
            "instead": {}, "scope": {"kind": "cite"}, "needs": list(needs), "inputs": lambda cfg: {},
            "outside": lambda cfg: [], "argv": argv}


def tree_state(ws):
    """Every file under the workspace, by content and modification time: what a precheck must leave as it found it."""
    out = {}
    for p in sorted(Path(ws).rglob("*")):
        if p.is_file():
            out[str(p.relative_to(ws))] = (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
    return out


def probe_rows(res):
    return [c for c in res["checks"] if c["id"] != "_scan"]


def edit_intro(repo, extra):
    intro = Path(repo) / "sections/01_intro.tex"
    intro.write_text(intro.read_text(encoding="utf-8") + extra, encoding="utf-8")


class PrecheckTest(unittest.TestCase):
    def test_an_uncommitted_edit_that_turns_a_check_red_is_said_and_nothing_is_written(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            seen = []
            with Probe(draft_check(root, seen)):
                V.compute(cfg, ws, do_run=True)
                before = tree_state(ws)
                edit_intro(repo, "\nThe gauges were BROKEN.\n")
                res = V.precheck(cfg, ws)
                self.assertTrue(res["worktree"], "the working tree, not HEAD")
                [c] = probe_rows(res)
                self.assertEqual((c["group"], c["last_verdict"], c["summary"]), (V.PRE_RED, "ok", "1 条"))
                self.assertEqual(tree_state(ws), before, "no run record, summary or state file is written")
                self.assertEqual(seen[-1], True, "a check that keeps state is told it is a precheck")
            self.assertEqual(git(repo, "stash", "list"), "", "the stash list is untouched")
            self.assertIn("sections/01_intro.tex", git(repo, "status", "--porcelain"), "the edit is still uncommitted")

    def test_a_clean_tree_is_checked_at_head_and_a_check_not_configured_is_left_out(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(draft_check(root, needs=["inputs.nothing_here"])):
                V.compute(cfg, ws, do_run=True)
                self.assertEqual(probe_rows(V.precheck(cfg, ws)), [], "a check the workspace does not configure")
            with Probe(draft_check(root)):
                V.compute(cfg, ws, do_run=True)
                res = V.precheck(cfg, ws)
                self.assertFalse(res["worktree"])
                self.assertEqual(res["head"], res["base_head"])
                self.assertEqual([c["group"] for c in res["checks"]], [V.PRE_OK, V.PRE_OK], "the probe and scan coverage")
                self.assertEqual([c["id"] for c in V.precheck(cfg, ws, only={"draftprobe"})["checks"]], ["draftprobe"],
                                 "--only names what runs; scan coverage is _scan")

    def test_a_finding_that_reads_differently_has_changed_and_one_that_does_not_is_still(self):
        with TempDir() as root:
            repo, ws = setup(root, [({"sections/01_intro.tex": "\\section{Introduction}\nOne gauge was BROKEN.\n"},
                                     "v2", 1_700_000_100)])
            cfg = C.load(ws)
            with Probe(draft_check(root)):
                V.compute(cfg, ws, do_run=True)
                edit_intro(repo, "Another was BROKEN too.\n")
                [c] = probe_rows(V.precheck(cfg, ws))
                self.assertEqual((c["group"], c["last_summary"], c["summary"]), (V.PRE_CHANGED, "1 条", "2 条"))
                git(repo, "checkout", "--", "sections/01_intro.tex")
                (Path(repo) / "main.tex").write_text((Path(repo) / "main.tex").read_text() + "%\n", encoding="utf-8")
                [c] = probe_rows(V.precheck(cfg, ws))
                self.assertEqual(c["group"], V.PRE_SAME)

    def test_the_command_exits_1_when_a_check_would_turn_red(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            args = argparse.Namespace(workspace=ws, only=None, json=False)
            with Probe(draft_check(root)):
                V.compute(cfg, ws, do_run=True)
                self.assertEqual(cli.cmd_precheck(args), 0)
                edit_intro(repo, "\nThe gauges were BROKEN.\n")
                self.assertEqual(cli.cmd_precheck(args), 1)

    def test_a_new_heading_without_a_rule_is_said_before_the_commit(self):
        # 09-29: three headings added in one round went unscanned by every check until after the commit
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(draft_check(root)):
                V.compute(cfg, ws, do_run=True)
                edit_intro(repo, "\\subsection{Gauges Nobody Reads}\n" + " ".join(["Each gauge was read by hand."] * 12) + "\n")
                [scan] = [c for c in V.precheck(cfg, ws)["checks"] if c["id"] == "_scan"]
                self.assertEqual((scan["group"], scan["last_verdict"]), (V.PRE_RED, "ok"))
                self.assertIn("Gauges Nobody Reads", scan["summary"])

    def test_the_method_ledger_works_on_a_copy_of_its_state(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            cfg.setdefault("inputs", {})["method_ledger"] = "ledger.tsv"
            state = Path(ws) / "cache" / "coverage" / "method-ledger-ids.json"
            state.parent.mkdir(parents=True, exist_ok=True)
            state.write_text('{"ids": ["M-1"]}', encoding="utf-8")
            with tempfile.TemporaryDirectory() as tmp:
                argv = K.by_id("method-ledger")["argv"]({"cfg": cfg, "ws": ws, "tmp": tmp, "precheck": True})
                used = Path(argv[argv.index("--state") + 1])
                self.assertEqual(used.parent, Path(tmp), "the state the check may write is a copy")
                self.assertEqual(used.read_text(encoding="utf-8"), state.read_text(encoding="utf-8"))
                argv = K.by_id("method-ledger")["argv"]({"cfg": cfg, "ws": ws, "tmp": tmp})
                self.assertEqual(Path(argv[argv.index("--state") + 1]), state, "a recorded run keeps its state")


if __name__ == "__main__":
    unittest.main()
