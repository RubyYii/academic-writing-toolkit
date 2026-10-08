"""The manuscript ring (the conversation-layer spec W1-W4, plus the design stage the author approved):
seven stages of one revision round, what hangs on each, and which ones the engine only infers."""
import unittest

import isolation  # noqa: F401 -- a throwaway HOME before anything reads the real one

from loop import coverage as V
from loop import ring as R


def risk(kind, rid, gate, decided_on=None, uuid=None):
    x = {"kind": kind, "id": rid, "title": f"合成标题 {rid}", "gate": gate, "source": "合成", "status": "未决"}
    if decided_on:
        x.update(decided_on=decided_on, decision="合成决定", uuid=uuid or "0" * 36)
    return x


def summary(open_=(), decided=(), rows=()):
    return {"risks": {"open": list(open_), "decided": list(decided), "below": [], "problems": []}, "rows": list(rows)}


def row(cid, status, last_at=None, name=None):
    return {"id": cid, "name": name or cid, "status": status, "detail": "", "last_at": last_at}


def seg(r, key):
    return next(s for s in r["segments"] if s["key"] == key)


class RingTest(unittest.TestCase):
    def test_the_gate_text_hangs_an_open_item_on_its_stage(self):
        """The shapes a real register uses to name a gate (synthetic wording): the first part decides, and a gate
        that names both a review page and a rewrite belongs to the review."""
        s = summary(open_=[risk("风险", "A1", "改稿核对页；再跑一轮读者组"), risk("风险", "A2", "作者写完意图卡；核对页"),
                           risk("风险", "A3", "这一轮改稿结束"), risk("风险", "A4", "作者核完之后决定怎么改稿"),
                           risk("风险", "A5", "G2"), risk("风险", "A6", "D2")])
        r = R.ring(s)
        self.assertEqual([i["id"] for i in seg(r, "review")["items"]], ["A1", "A4"])
        self.assertEqual([i["id"] for i in seg(r, "design")["items"]], ["A2"])
        self.assertEqual([i["id"] for i in seg(r, "rewrite")["items"]], ["A3"])
        self.assertEqual([i["id"] for i in r["unhung"]], ["A5", "A6"], "a gate id is not a stage: listed apart, not guessed")
        self.assertEqual(r["waiting"], 6, "every open register item waits on the author")

    def test_a_round_starts_at_the_last_review_decision_and_says_its_precision(self):
        s = summary(decided=[risk("风险", "B1", "改稿核对页", "2026-09-23"), risk("风险", "B2", "对照经作者在核对页裁定", "2026-09-24"),
                             risk("门", "G4", "G4", "2026-09-25")])
        r = R.ring(s)
        self.assertEqual(r["since"], "2026-09-24", "only a review decision starts a round, not a later gate")
        self.assertIn("日", r["sinceNote"], "the register keeps dates, not times: the ring says so")
        self.assertIsNone(R.ring(summary())["since"], "no review decided yet: the round runs from the start")

    def test_the_current_stage_is_the_first_with_something_hanging(self):
        s = summary(open_=[risk("风险", "C1", "作者写完意图卡"), risk("风险", "C2", "改稿核对页")])
        r = R.ring(s, last_comment_at="2026-09-24T10:00:00Z")
        self.assertEqual(r["current"], "design")
        self.assertEqual(seg(r, "comment")["state"], "done")

    def test_with_nothing_hanging_the_current_stage_is_the_first_not_yet_reached(self):
        r = R.ring(summary(), last_comment_at="2026-09-24T10:00:00Z")
        self.assertEqual(r["current"], "rewrite", "the author spoke; nothing rewritten since")

    def test_the_latest_activity_is_said_beside_the_current_stage(self):
        """A real manuscript waited at 设计 (an item hung there) while the day's work was rewriting. Both are true, so
        both are said: where the round waits, and where it last moved."""
        s = summary(open_=[risk("风险", "C1", "作者写完意图卡")],
                    rows=[row("readers", V.OK, last_at="2026-09-24T09:00:00Z"), row("x", V.OK, last_at="2026-09-24T09:30:00Z")])
        r = R.ring(s, last_comment_at="2026-09-24T08:00:00Z", last_change_at="2026-09-24T11:00:00Z")
        self.assertEqual(r["current"], "design")
        self.assertEqual(r["latest"], "rewrite")
        self.assertIsNone(R.ring(summary())["latest"])

    def test_checks_that_are_not_current_hang_on_the_check_stage(self):
        s = summary(rows=[row("fingerprint", V.FAILED, name="文风"), row("claims", V.STALE, name="主张台账"), row("x", V.OK)])
        r = R.ring(s, last_comment_at="2026-09-24T10:00:00Z", last_change_at="2026-09-24T11:00:00Z")
        self.assertEqual([i["id"] for i in seg(r, "check")["items"]], ["fingerprint", "claims"])
        self.assertEqual(r["current"], "check")

    def test_an_accepted_stale_reader_panel_does_not_hang_and_counts_as_done(self):
        s = summary(rows=[row("readers", V.ACCEPTED, last_at="2026-09-24T09:00:00Z", name="读者组")])
        r = R.ring(s, last_change_at="2026-09-24T12:00:00Z")
        self.assertEqual(seg(r, "readers")["items"], [], "someone accepted this change; the ring does not ask for a re-run")
        stale = R.ring(summary(rows=[row("readers", V.STALE, last_at="2026-09-24T09:00:00Z", name="读者组")]),
                        last_change_at="2026-09-24T12:00:00Z")
        self.assertEqual(len(seg(stale, "readers")["items"]), 1)

    def test_a_stale_reader_panel_says_how_much_changed_and_whether_to_accept_or_reread(self):
        # 09-28 panel grill R5: "the draft changed, re-read" looked the same for one changed word and a restructure.
        def stale(changed, scope):
            r = dict(row("readers", V.STALE, last_at="2026-09-24T09:00:00Z", name="读者组"), changed=changed, detail="句子改 3")
            s = dict(summary(rows=[r]), readers_scope={"sections": ["A"], "sentences": scope, "of": scope})
            return seg(R.ring(s, last_change_at="2026-09-24T12:00:00Z"), "readers")["items"][0]["detail"]
        self.assertEqual(stale(3, 400), "句子改 3；改动小（改动 3 处 / 读的范围 400 句），可以接受这次过期、不重读：跟 Claude 说一声")
        self.assertIn("改动小", stale(8, 400), "2% of 400 is 8: still small")
        self.assertIn("改动大（改动 9 处 / 读的范围 400 句），要重读", stale(9, 400))
        self.assertIn("改动小", stale(5, 100), "never fewer than five")
        self.assertEqual(stale(0, 400), "句子改 3", "no count, no verdict")
        no_scope = dict(summary(rows=[dict(row("readers", V.STALE, last_at="2026-09-24T09:00:00Z"), changed=3, detail="句子改 3")]))
        self.assertEqual(seg(R.ring(no_scope, last_change_at="2026-09-24T12:00:00Z"), "readers")["items"][0]["detail"], "句子改 3")

    def test_an_open_item_says_what_closes_it_and_which_gate_decides_it(self):
        x = dict(risk("风险", "W1", "改稿结束"), detail="待 改稿结束",
                 evidence="改完后把合成模板装进工具（公开仓，不带原句）。另一句不上环")
        r = R.ring(summary(open_=[x]))
        item = seg(r, "rewrite")["items"][0]
        self.assertEqual(item["detail"], "要做：改完后把合成模板装进工具 · 由：改稿结束")
        bad = dict(risk("风险", "W2", "改稿结束"), detail="格式不全：缺 消除它的证据", evidence="")
        self.assertEqual(seg(R.ring(summary(open_=[bad])), "rewrite")["items"][0]["detail"], "格式不全：缺 消除它的证据")
        long_ = dict(risk("风险", "W3", "改稿结束"), evidence="合" * 100)
        self.assertEqual(len(seg(R.ring(summary(open_=[long_])), "rewrite")["items"][0]["detail"].split(" · ")[0]), 3 + 60)

    def test_a_reader_panel_older_than_the_last_rewrite_hangs_on_readers_as_stale(self):
        s = summary(rows=[row("readers", V.OK, last_at="2026-09-24T09:00:00Z", name="读者组")])
        r = R.ring(s, last_comment_at="2026-09-24T08:00:00Z", last_change_at="2026-09-24T11:00:00Z")
        items = seg(r, "readers")["items"]
        self.assertEqual(len(items), 1)
        self.assertIn("过期", items[0]["text"])
        fresh = R.ring(s, last_comment_at="2026-09-24T08:00:00Z", last_change_at="2026-09-24T08:30:00Z")
        self.assertEqual(seg(fresh, "readers")["items"], [])

    def test_times_in_different_offsets_are_compared_as_times(self):
        """The hooks write …Z, git writes …+01:00: as strings 12:30Z sorts before 13:20+01:00 (12:20Z)."""
        s = summary(rows=[row("readers", V.OK, last_at="2026-09-24T12:30:00Z")])
        r = R.ring(s, last_comment_at="2026-09-24T08:00:00Z", last_change_at="2026-09-24T13:20:00+01:00")
        self.assertEqual(seg(r, "readers")["items"], [], "the panel ran after the rewrite")
        self.assertEqual(r["latest"], "readers")

    def test_register_items_are_the_authors_to_decide_and_stale_checks_are_not(self):
        """The host paints what waits on the author apart from what is only out of date: each hung item says which."""
        s = summary(open_=[risk("风险", "C1", "作者写完意图卡")], rows=[row("fingerprint", V.STALE, name="文风")])
        r = R.ring(s, last_comment_at="2026-09-24T10:00:00Z", last_change_at="2026-09-24T11:00:00Z")
        self.assertEqual([i["you"] for i in seg(r, "design")["items"]], [True])
        self.assertEqual([i["you"] for i in seg(r, "check")["items"]], [False])

    def test_the_latest_activity_carries_its_time(self):
        s = summary(rows=[row("readers", V.OK, last_at="2026-09-24T12:30:00Z")])
        r = R.ring(s, last_comment_at="2026-09-24T08:00:00Z", last_change_at="2026-09-24T13:20:00+01:00")
        self.assertEqual(r["latest_at"], "2026-09-24T12:30:00Z")
        self.assertIsNone(R.ring(summary())["latest_at"])

    def test_what_the_engine_cannot_see_is_said_not_guessed(self):
        r = R.ring(summary())
        self.assertEqual([s["key"] for s in r["segments"]], ["comment", "design", "rewrite", "check", "readers", "review", "land"])
        self.assertEqual(seg(r, "review")["seen"], R.INFERRED)
        self.assertEqual(seg(r, "land")["seen"], R.COMMITS_ONLY)
        self.assertEqual(seg(r, "design")["seen"], R.INFERRED)
        self.assertEqual(seg(r, "check")["seen"], R.SEEN)

    def test_closed_gates_are_listed_by_date_with_the_authors_message(self):
        s = summary(decided=[risk("门", "G0", "G0", "2026-09-22", "aaaa1111" + "0" * 28),
                             risk("风险", "B1", "改稿核对页", "2026-09-23", "bbbb2222" + "0" * 28),
                             risk("风险", "B2", "改稿核对页", "2026-09-23", "bbbb2222" + "0" * 28)])
        closed = R.ring(s)["closed"]
        self.assertEqual([c["date"] for c in closed], ["2026-09-23", "2026-09-22"], "newest first")
        self.assertEqual(closed[0]["items"], ["B1、B2（bbbb2222）"], "one message closed both: said once")
        mixed = R.ring(summary(decided=[risk("风险", "B1", "改稿核对页", "2026-09-23", "bbbb2222" + "0" * 28),
                                        risk("门", "G3", "G3", "2026-09-23", "cccc3333" + "0" * 28),
                                        risk("风险", "B2", "改稿核对页", "2026-09-23", "bbbb2222" + "0" * 28),
                                        {k: v for k, v in risk("风险", "B3", "改稿核对页", "2026-09-23").items() if k != "uuid"}]))["closed"]
        self.assertEqual(mixed[0]["items"], ["B1、B2（bbbb2222）", "G3（cccc3333）", "B3"], "in the order first seen; no uuid, no bracket")

    def test_how_far_the_round_got_is_the_furthest_stage_that_moved_in_it(self):
        """Neither current (a stale open item pins it at 设计) nor latest (a comment restarts it) says how far the round
        got; reached does (the author 09-24: a draft ready to upload still read 设计)."""
        s = summary(open_=[risk("风险", "D1", "作者写完意图卡")], decided=[risk("风险", "B1", "改稿核对页", "2026-09-24")],
                    rows=[row("a", V.OK, "2026-09-24T12:00:00Z")])
        r = R.ring(s, last_comment_at="2026-09-24T20:00:00Z", last_change_at="2026-09-24T11:00:00Z")
        self.assertEqual(r["current"], "design")
        self.assertEqual(r["latest"], "comment")
        self.assertEqual(r["reached"], "check", "a check ran after the rewrite within the round")
        old = R.ring(s, last_comment_at="2026-09-24T20:00:00Z", last_change_at="2026-09-23T11:00:00Z")
        self.assertEqual(old["reached"], "check", "a rewrite before the round does not count, the check within it does")
        self.assertIsNone(R.ring(summary(decided=[risk("风险", "B1", "改稿核对页", "2026-09-25")]),
                                 last_comment_at="2026-09-24T20:00:00Z")["reached"], "nothing moved within the round")

    def test_an_open_item_carries_the_date_it_last_moved(self):
        x = dict(risk("风险", "E1", "改稿核对页"), moved="09-22")
        r = R.ring(summary(open_=[x, risk("风险", "E2", "改稿核对页")]))
        self.assertEqual([i.get("moved") for i in seg(r, "review")["items"]], ["09-22", None])


if __name__ == "__main__":
    unittest.main()


class AnalysisStageTest(unittest.TestCase):
    """A stage for analysis (spec 2026-09-25 §4.5): the analyses a round needed ran outside the ring, so the ring could
    only offer rewording. It is off unless the workspace turns it on; the claims ledger's 分析 items hang on it."""

    def test_without_the_stage_the_ring_keeps_its_seven_stages(self):
        r = R.ring(summary())
        self.assertEqual([s["key"] for s in r["segments"]], [k for k, _, _ in R.STAGES])
        self.assertNotIn("analysis", [s["key"] for s in r["segments"]])

    def test_an_open_analysis_hangs_on_the_stage_between_design_and_rewrite(self):
        items = [{"id": "N1", "title": "五个模型跑遮字", "closed": False, "status": "未做"},
                 {"id": "N2", "title": "换掉查询文字", "closed": True, "status": "已做 2026-01-01 run-2"}]
        r = R.ring(summary(), analysis=items)
        keys = [s["key"] for s in r["segments"]]
        self.assertEqual(keys[:4], ["comment", "design", "analysis", "rewrite"])
        a = seg(r, "analysis")
        self.assertEqual(a["state"], "open")
        self.assertEqual([i["id"] for i in a["items"]], ["N1"])

    def test_an_analysis_closed_within_the_round_marks_the_stage_done(self):
        decided = [risk("门", "G1", "核对页", decided_on="2026-02-01")]
        done = [{"id": "N1", "title": "五个模型跑遮字", "closed": True, "status": "已做 2026-02-03 run-5"}]
        r = R.ring(summary(decided=decided), analysis=done)
        self.assertEqual(seg(r, "analysis")["state"], "done")
        before = [{"id": "N1", "title": "五个模型跑遮字", "closed": True, "status": "已做 2026-01-20 run-5"}]
        self.assertEqual(seg(R.ring(summary(decided=decided), analysis=before), "analysis")["state"], "unseen",
                         "an analysis done before the round began is not this round's")


class SeenStagesTest(unittest.TestCase):
    """Spec 2026-09-29-ring-rounds-and-stages: every stage on the ring is seen or is not on it; a round ends at a
    landing or a decision; a frozen manuscript gets four stages. Synthetic times throughout."""
    CHANGE, CHECK, READ = "2026-01-02T10:00:00+00:00", "2026-01-02T10:05:00+00:00", "2026-01-02T11:00:00+00:00"

    def base(self, **kw):
        rows = [row("fingerprint", V.OK, self.CHECK), dict(row("readers", V.OK, self.READ), changed=0)]
        return R.ring(summary(rows=rows), last_comment_at="2026-01-02T09:00:00+00:00", last_change_at=self.CHANGE, **kw)

    def test_without_the_new_inputs_the_ring_stands_at_the_reader_panel(self):
        # The failure the author asked about: nothing past 读者组 can light up.
        r = self.base()
        self.assertEqual(r["reached"], "readers")
        self.assertEqual((seg(r, "review")["state"], seg(r, "land")["state"]), ("open", "unseen"))

    def test_a_ready_build_at_the_current_draft_lights_the_landing(self):
        r = self.base(landing={"commit": "abc1234", "at": "2026-01-02T12:00:00+00:00", "changed": False})
        self.assertEqual((seg(r, "land")["state"], seg(r, "land")["seen"]), ("done", R.SEEN))
        self.assertEqual(r["reached"], "land")

    def test_a_draft_changed_after_the_build_says_so(self):
        r = self.base(landing={"commit": "abc1234", "at": "2026-01-02T08:00:00+00:00", "changed": True})
        self.assertEqual((seg(r, "land")["state"], seg(r, "land").get("note")), ("open", "改过了"))
        self.assertNotEqual(r["reached"], "land")

    def test_a_decision_after_the_last_change_is_the_review(self):
        r = self.base(decisions=[{"id": "D1", "at": "2026-01-02T11:30:00+00:00"}])
        self.assertEqual(seg(r, "review")["state"], "done")
        self.assertEqual(r["reached"], "review")
        r = self.base(decisions=[{"id": "D1", "at": "2026-01-02T09:30:00+00:00"}])
        self.assertEqual(seg(r, "review")["state"], "open", "decided before the last rewrite: not a review of it")

    def test_a_round_starts_after_the_latest_landing_or_decision_once_something_moves(self):
        land = {"commit": "abc1234", "at": "2026-01-01T12:00:00+00:00", "changed": True}
        r = self.base(landing=land, decisions=[{"id": "D0", "at": "2025-12-30T12:00:00+00:00"}])
        self.assertEqual(r["since"], land["at"], "the draft moved after the landing: a new round from it")
        self.assertIn("落稿或裁定", r["sinceNote"])
        r = self.base(landing={"commit": "abc1234", "at": "2026-01-02T12:00:00+00:00", "changed": False},
                      decisions=[{"id": "D0", "at": "2025-12-30T12:00:00+00:00"}])
        self.assertEqual(r["since"], "2025-12-30T12:00:00+00:00", "nothing moved since the landing: its round is shown")

    def test_without_an_intent_card_design_leaves_the_ring(self):
        r = self.base(design={"configured": False, "at": None})
        self.assertNotIn("design", [s["key"] for s in r["segments"]])
        r = self.base(design={"configured": True, "at": "2025-06-01T00:00:00+00:00"},
                      decisions=[{"id": "D0", "at": "2025-12-30T12:00:00+00:00"}])
        self.assertEqual((seg(r, "design")["state"], seg(r, "design").get("note")), ("unseen", "这一轮没动"))
        self.assertNotEqual(r["current"], "design", "an untouched intent card is not where the round waits")
        r = self.base(design={"configured": True, "at": "2026-01-02T08:00:00+00:00"})
        self.assertEqual(seg(r, "design")["state"], "done")

    def test_frozen_the_ring_has_four_stages_and_does_not_ask_for_a_panel(self):
        # a correctness-sized change: a larger one breaks the freeze (FreezeEarnedTest)
        rows = [row("fingerprint", V.OK, self.CHECK), dict(row("readers", V.STALE, "2026-01-01T00:00:00+00:00"), changed=3)]
        r = R.ring(summary(rows=rows), last_change_at=self.CHANGE, freeze=True,
                   landing={"commit": "abc1234", "at": "2026-01-02T12:00:00+00:00", "changed": False})
        self.assertEqual([s["key"] for s in r["segments"]], ["comment", "rewrite", "check", "land"])
        self.assertFalse(any(i["id"] == "readers" for s in r["segments"] for i in s["items"]), "no panel rerun")
        self.assertEqual(r["frozenNote"], "冻结期不重读（改动 3 处）")
        self.assertEqual(r["reached"], "land")

    def test_the_frozen_note_goes_out_on_the_card(self):
        from loop import lintel as LN
        rows = [dict(row("readers", V.STALE, "2026-01-01T00:00:00+00:00"), changed=3)]
        out = LN._ring(summary(rows=rows), name="t", last_comment_at=None, last_change_at=None,
                       ring_inputs={"freeze": True})
        self.assertEqual(out["frozenNote"], "冻结期不重读（改动 3 处）")
        self.assertNotIn("frozenNote", LN._ring(summary(rows=rows), name="t", last_comment_at=None, last_change_at=None))

    def test_reached_and_current_are_two_things(self):
        # R6: how far the round got, and where it waits, are both exported.
        s = summary(open_=[risk("风险", "E1", "改稿核对页")], rows=[row("fingerprint", V.OK, self.CHECK)])
        r = R.ring(s, last_change_at=self.CHANGE, landing={"commit": "abc1234", "at": "2026-01-02T12:00:00+00:00",
                                                            "changed": False})
        self.assertEqual((r["reached"], r["current"]), ("land", "review"))


class FreezeEarnedTest(unittest.TestCase):
    """A freeze is earned by a quiet draft (09-29: the stage said 冻结 while paragraphs were rewritten; the ring read
    four stages done and landed, the panel not to be re-read)."""
    LAND = {"commit": "abc1234", "at": "2026-01-02T12:00:00+00:00", "changed": False}

    def ring(self, changed):
        rows = [row("fingerprint", V.OK, "2026-01-02T10:05:00+00:00"),
                dict(row("readers", V.STALE, "2026-01-01T00:00:00+00:00"), changed=changed)]
        s = dict(summary(rows=rows), readers_scope={"sentences": 800})
        return R.ring(s, last_change_at="2026-01-02T10:00:00+00:00", freeze=True, landing=self.LAND)

    def test_a_large_change_since_the_panel_breaks_the_freeze_and_asks(self):
        r = self.ring(541)
        self.assertIn("readers", [s["key"] for s in r["segments"]], "shown as a rewrite: the full ring")
        self.assertTrue(any(i["id"] == "readers" for i in seg(r, "readers")["items"]), "the panel is a rerun again")
        [ask] = [i for i in r["unhung"] if i["id"] == "冻结"]
        self.assertTrue(ask["you"])
        self.assertIn("541", ask["text"])
        self.assertEqual(r["waiting"], 1)
        self.assertEqual((seg(r, "land")["state"], seg(r, "land").get("note")), ("open", "还在改"),
                         "ready to upload is not landed while the draft is being rewritten")
        self.assertIn("按改稿显示", r["frozenNote"])

    def test_a_correctness_sized_change_keeps_the_freeze(self):
        r = self.ring(3)
        self.assertEqual([s["key"] for s in r["segments"]], ["comment", "rewrite", "check", "land"])
        self.assertFalse(any(i["id"] == "冻结" for i in r["unhung"]))
        self.assertEqual(seg(r, "land")["state"], "done")
