"""The changed-sentence gate on what a deletion takes with it and on a share that disagrees (spec
2026-09-29-deletion-side-effects D1–D3). Synthetic text throughout: a bridge survey, no manuscript text."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from loop import catalogue as K
from loop import coverage as V

from fixtures import TempDir

# AWT_AUDIT_DIR: the mutated copy a red check is testing; otherwise the skill in this checkout.
AUDIT = Path(os.environ.get("AWT_AUDIT_DIR") or K.ENGINE_ROOT / ".claude" / "skills" / "audit" / "scripts")
GATE = AUDIT / "audit-sentence-changes.py"

INTRO = "The survey logged readings from brass gauges on the north bridge."
FILLER = ["Weather varied across the season.", "Crews worked in pairs on each span.",
          "Traffic was stopped for an hour each morning.", "Rain delayed two of the visits.",
          "Each visit lasted about three hours.", "A second crew checked the railings.",
          "Photographs were taken of every joint."]
LAST = "We do not test whether inspectors trust the gauge readings."


def para(*sentences):
    return " ".join(sentences)


def gate(root, base, target, *extra):
    b, t = Path(root) / "base", Path(root) / "target"
    for d, text in ((b, base), (t, target)):
        d.mkdir(parents=True, exist_ok=True)
        (d / "s.tex").write_text("\\section{Setup}\n" + text + "\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(GATE), "--base", str(b), "--target", str(t), "--json", *extra],
                       capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr[-400:]
    return json.loads(r.stdout)


def flags(data, name):
    return [s for s in data["sentences"] if name in s["flags"]]


class LostAntecedentTest(unittest.TestCase):
    def test_a_removal_that_took_an_antecedent_is_flagged_far_down_the_paragraph(self):
        with TempDir() as root:
            d = gate(root, para(INTRO, *FILLER, LAST), para(*FILLER, LAST))
            [s] = flags(d, "took_antecedent")
            self.assertEqual(s["old"], INTRO)
            self.assertEqual([(h["phrase"], h["sentence"]) for h in s["antecedent"]], [("the gauge", LAST)],
                             "eight sentences on, in the same paragraph; a plural folded onto its singular, one "
                             "entry for the noun phrase")
            self.assertEqual(d["compared"]["took_antecedent"], 1)

    def test_a_noun_still_named_earlier_is_not_lost(self):
        with TempDir() as root:
            named = "Brass gauges on the north bridge gave daily readings."
            d = gate(root, para(named, INTRO, *FILLER[:2], LAST), para(named, *FILLER[:2], LAST))
            self.assertEqual(flags(d, "took_antecedent"), [])

    def test_the_next_paragraph_is_not_read(self):
        with TempDir() as root:
            d = gate(root, para(INTRO, *FILLER[:2]) + "\n\n" + LAST, para(*FILLER[:2]) + "\n\n" + LAST)
            self.assertEqual(flags(d, "took_antecedent"), [])

    def test_ordinals_modals_and_verbs_are_not_nouns(self):
        with TempDir() as root:
            gone = "Inspectors could address the second span only at night."
            later = ["The second was closed in winter.", "Those readings could vary by an hour.",
                     "This report addresses a gap in the record."]
            d = gate(root, para(FILLER[0], gone, *later), para(FILLER[0], *later))
            self.assertEqual(flags(d, "took_antecedent"), [])

    def test_a_participle_after_a_noun_is_not_a_noun(self):
        # "the sensors added later" was taken to point back to a removed "was added afterwards"
        with TempDir() as root:
            gone = "The comparison was added afterwards."
            d = gate(root, para(FILLER[0], gone, "Only the sensors added later read the deck."),
                     para(FILLER[0], "Only the sensors added later read the deck."))
            self.assertEqual(flags(d, "took_antecedent"), [])

    def test_a_revised_later_sentence_is_read_too(self):
        with TempDir() as root:
            d = gate(root, para(INTRO, FILLER[0], LAST),
                     para(FILLER[0], "We do not test whether bridge inspectors trust the gauge readings."))
            [s] = flags(d, "took_antecedent")
            self.assertEqual(s["antecedent"][0]["phrase"], "the gauge")


OTHER = "Two of the three later sensors read the deck temperature directly."


class ShareElsewhereTest(unittest.TestCase):
    def test_a_share_that_disagrees_is_flagged_with_the_other_sentences(self):
        with TempDir() as root:
            d = gate(root, para("One sensor reads the deck temperature directly.", OTHER),
                     para("For one of three later sensors, the deck temperature is read directly.", OTHER))
            [s] = flags(d, "count_elsewhere")
            self.assertEqual(s["shares_elsewhere"], [{"share": "one of three later sensors", "sentences": [OTHER]}])
            self.assertEqual(d["compared"]["count_elsewhere"], 1)

    def test_no_other_share_of_that_total_says_nothing(self):
        with TempDir() as root:
            four = "Two of the four later sensors read the deck temperature directly."
            same = "One of the three later sensors failed in May."
            for other in ("", four, same):
                d = gate(root, para("One sensor reads the deck temperature directly.", other),
                         para("For one of three later sensors, the deck temperature is read directly.", other))
                self.assertEqual(flags(d, "count_elsewhere"), [], other or "no other sentence")

    def test_a_share_the_sentence_already_had_is_not_flagged_again(self):
        with TempDir() as root:
            d = gate(root, para("For one of three later sensors, the deck temperature is read.", OTHER),
                     para("For one of three later sensors, the deck temperature is read directly.", OTHER))
            self.assertEqual(flags(d, "count_elsewhere"), [])

    def test_a_pairs_file_has_no_draft_to_compare_with(self):
        with TempDir() as root:
            pairs = Path(root) / "pairs.tsv"
            pairs.write_text("id\told\tnew\nx1\tOne sensor reads the deck.\tFor one of three later sensors, the "
                             "deck is read.\n", encoding="utf-8")
            r = subprocess.run([sys.executable, str(GATE), "--pairs", str(pairs), "--json"], capture_output=True,
                               text=True)
            self.assertEqual(flags(json.loads(r.stdout), "count_elsewhere"), [])


def gate_files(root, base, target):
    b, t = Path(root) / "base", Path(root) / "target"
    for d, files in ((b, base), (t, target)):
        for name, text in files.items():
            (d / name).parent.mkdir(parents=True, exist_ok=True)
            (d / name).write_text("\\section{" + name[:-4] + "}\n" + text + "\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(GATE), "--base", str(b), "--target", str(t), "--json"],
                       capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr[-400:]
    return json.loads(r.stdout)


SAME = "Ten of the eighteen gauges differ from their drawings beyond rounding."


class DuplicateTest(unittest.TestCase):
    """FOR-AWT 46: a round that removed repeated statements wrote a sentence that matched another letter for letter."""

    def test_a_rewrite_that_matches_another_sentence_but_for_a_reference_is_flagged(self):
        with TempDir() as root:
            d = gate_files(root, {"a.tex": para(FILLER[0], SAME), "b.tex": para(FILLER[1], "Some gauges were replaced in May.")},
                           {"a.tex": para(FILLER[0], SAME),
                            "b.tex": para(FILLER[1], SAME[:-1] + " (Section~\\ref{sec:a}).")})
            [s] = flags(d, "duplicates_elsewhere")
            self.assertEqual(s["duplicates"], [{"where": "a.tex", "sentence": SAME}])
            self.assertEqual(d["compared"]["duplicates_elsewhere"], 1)

    def test_a_verbatim_copy_is_found_by_count(self):
        with TempDir() as root:
            d = gate_files(root, {"a.tex": para(FILLER[0], SAME), "b.tex": FILLER[1]},
                           {"a.tex": para(FILLER[0], SAME), "b.tex": para(FILLER[1], SAME)})
            [s] = flags(d, "duplicates_elsewhere")
            self.assertEqual((s["kind"], s["where"], s["duplicates"]), ("copied", "b.tex", [{"where": "a.tex", "sentence": SAME}]),
                             "reported where the copy landed, beside where it already stood")

    def test_a_move_is_not_a_copy(self):
        with TempDir() as root:
            d = gate_files(root, {"a.tex": para(FILLER[0], SAME), "b.tex": FILLER[1]},
                           {"a.tex": FILLER[0], "b.tex": para(FILLER[1], SAME)})
            self.assertEqual(flags(d, "duplicates_elsewhere"), [])

    def test_a_repeat_the_base_already_had_is_not_flagged(self):
        with TempDir() as root:
            both = {"a.tex": para(FILLER[0], SAME), "b.tex": para(FILLER[1], SAME)}
            d = gate_files(root, both, {**both, "a.tex": para(FILLER[2], SAME)})
            self.assertEqual(flags(d, "duplicates_elsewhere"), [])

    def test_a_short_sentence_is_not_compared(self):
        with TempDir() as root:
            short = "Results are shown below."
            d = gate_files(root, {"a.tex": para(FILLER[0], short), "b.tex": FILLER[1]},
                           {"a.tex": para(FILLER[0], short), "b.tex": para(FILLER[1], short)})
            self.assertEqual(flags(d, "duplicates_elsewhere"), [])


class LoopSummaryTest(unittest.TestCase):
    def test_the_loop_names_the_new_flags_apart(self):
        with TempDir() as root:
            d = gate(root, para(INTRO, FILLER[0], LAST), para(FILLER[0], LAST))
            _, summary = V.interpret("sentence-changes", 1, json.dumps(d), "")
            self.assertIn("删句后指代可能落空 1", summary)

    def test_the_loop_names_a_duplicate(self):
        with TempDir() as root:
            d = gate_files(root, {"a.tex": para(FILLER[0], SAME), "b.tex": FILLER[1]},
                           {"a.tex": para(FILLER[0], SAME), "b.tex": para(FILLER[1], SAME)})
            _, summary = V.interpret("sentence-changes", 1, json.dumps(d), "")
            self.assertIn("与别处一字不差 1", summary)


if __name__ == "__main__":
    unittest.main()
