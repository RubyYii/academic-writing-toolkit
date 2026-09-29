"""What the ring reads besides the coverage summary (spec 2026-09-29-ring-rounds-and-stages): a landing from the build
report, decisions timed by their author message, the intent card, a freeze. Synthetic throughout."""
import json
import unittest
from pathlib import Path

from loop import config as C
from loop import ringinputs as RI

from fixtures import TempDir, git, make_repo, workspace

REPORT = {"ready_to_upload": True, "source_commit": None, "failures": []}


def setup(root, ready=True):
    repo = make_repo(root, [({"main.tex": "\\section{Intro}\nTwo gauges.\n"}, "v1", 1_700_000_000)])
    src = git(repo, "rev-parse", "HEAD")
    (repo / "build").mkdir()
    (repo / "build" / "report.json").write_text(json.dumps(dict(REPORT, ready_to_upload=ready, source_commit=src)),
                                                encoding="utf-8")
    git(repo, "add", "build/report.json")
    git(repo, "commit", "-qm", "build report")
    ws = workspace(root, repo, "main", glob=["main.tex"])
    cfg = C.load(ws)
    cfg.setdefault("overview", {})["build_report"] = "build/report.json"
    C.save(ws, cfg)
    return repo, ws, C.load(ws), src


class RingInputsTest(unittest.TestCase):
    def test_a_ready_build_is_a_landing_and_a_later_draft_change_is_said(self):
        with TempDir() as root:
            repo, ws, cfg, src = setup(root)
            got = RI.landing(cfg)
            self.assertEqual((got["commit"], got["changed"]), (src[:7], False), "a commit that only adds the report")
            (repo / "main.tex").write_text("\\section{Intro}\nThree gauges.\n", encoding="utf-8")
            git(repo, "commit", "-qam", "edit")
            self.assertTrue(RI.landing(cfg)["changed"])
        with TempDir() as root:
            repo, ws, cfg, src = setup(root, ready=False)
            self.assertIsNone(RI.landing(cfg), "not ready to upload is no landing")

    def test_a_decision_is_timed_by_its_message_and_a_miss_is_not_rescanned(self):
        with TempDir() as root:
            t = Path(root) / "session.jsonl"
            # written compact, as the transcripts are
            t.write_text(json.dumps({"type": "user", "uuid": "u-1", "timestamp": "2026-01-02T11:30:00Z"},
                                    separators=(",", ":")) + "\n", encoding="utf-8")
            orig = RI._transcript_files
            RI._transcript_files = lambda cfg: [str(t)]
            try:
                cache = Path(root) / "times.json"
                self.assertEqual(RI.uuid_times({}, ["u-1", "u-2"], cache), {"u-1": "2026-01-02T11:30:00Z"})
                calls = []
                RI._transcript_files = lambda cfg: calls.append(1) or [str(t)]
                RI.uuid_times({}, ["u-1"], cache)
                self.assertEqual(calls, [], "a found time is read from the cache")
                cov = {"risks": {"decided": [{"id": "D1", "uuid": "u-1", "decided_on": "2026-01-02"},
                                             {"id": "D2", "uuid": "u-2", "decided_on": "2026-01-03"}]}}
                ws = Path(root) / "ws"
                RI._transcript_files = lambda cfg: [str(t)]
                self.assertEqual(RI.decisions({}, ws, cov), [{"id": "D1", "at": "2026-01-02T11:30:00Z"},
                                                             {"id": "D2", "at": "2026-01-03"}],
                                 "a message not found falls back to the date")
            finally:
                RI._transcript_files = orig

    def test_a_freeze_is_read_from_the_ledger_stage_or_forced(self):
        with TempDir() as root:
            led = Path(root) / "claims.md"
            cfg = {"claims": str(led)}
            for stage, frozen in (("冻结，只收正确性", True), ("终检", True), ("分析", False)):
                led.write_text(f"阶段：{stage}\n\n## 主张 C1 x\n- 证据：t\n- 强度：强\n- 允许的说法：x\n", encoding="utf-8")
                self.assertEqual(RI.freeze(cfg, root), frozen, stage)
            self.assertTrue(RI.freeze({"ring": {"freeze": True}}, root))

    def test_the_intent_card_is_configured_or_not(self):
        self.assertEqual(RI.design({}), {"configured": False, "at": None})
        with TempDir() as root:
            card = Path(root) / "card.md"
            card.write_text("x", encoding="utf-8")
            got = RI.design({"target": {"intent_card": str(card)}})
            self.assertTrue(got["configured"] and got["at"])


if __name__ == "__main__":
    unittest.main()
