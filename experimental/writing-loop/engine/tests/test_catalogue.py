"""The wiring invariant: a check the toolkit has, and the loop does not run, must be a decision, not an accident.

Twice a working capability sat beside a manuscript without being run on it: an audit that only ran when someone
remembered to call it, and a reader-panel prototype that worked and was never promoted. These tests make the
first kind impossible to add silently: every check registered in scripts/check-fails-closed.py is either in the
loop's catalogue or in its UNWIRED list with a reason, and every skill is either installed or declared.
"""
import importlib.util
import unittest

import isolation  # noqa: F401  (a throwaway HOME; see isolation.py)

from loop import catalogue as K

ROOT = K.ENGINE_ROOT


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def registered_checks():
    return set(_load(ROOT / "scripts" / "check-fails-closed.py", "fails_closed").CHECKS)


def not_checks():
    return set(_load(ROOT / "scripts" / "check-fails-closed.py", "fails_closed").NOT_CHECKS)


def installer_names():
    return set(_load(ROOT / "scripts" / "install-codex-skills.py", "install_codex").NAMES)


def documented_skills():
    import re
    text = (ROOT / "docs" / "skills" / "README.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\| `/([\w-]+)` \|", text, re.M))


def skill_dirs():
    return {p.parent.name for p in (ROOT / ".claude" / "skills").glob("*/SKILL.md")}


class WiringTest(unittest.TestCase):
    def test_every_registered_check_is_wired_or_declared_unwired(self):
        problems = K.wiring_problems(registered_checks(), skill_dirs(), installer_names(), documented_skills(),
                                     not_checks())
        self.assertEqual(problems, [], "\n".join(problems))

    def test_a_skill_that_checks_nothing_and_says_nothing_is_seen(self):
        saved = dict(K.SKILL_ROLES)
        try:
            K.SKILL_ROLES.pop("export")
            problems = K.wiring_problems(registered_checks(), skill_dirs(), installer_names())
            self.assertTrue(any("技能 export" in p for p in problems), problems)
        finally:
            K.SKILL_ROLES.clear()
            K.SKILL_ROLES.update(saved)

    def test_moving_a_check_into_not_checks_alone_is_seen(self):
        problems = K.wiring_problems(registered_checks() - {"audit/audit-claim-positioning.py"}, skill_dirs(),
                                     installer_names(), None, not_checks() | {"audit/audit-claim-positioning.py"})
        self.assertTrue(any("NOT_CHECKS" in p and "audit-claim-positioning" in p for p in problems), problems)

    def test_the_invariant_sees_a_skill_nobody_can_find(self):
        problems = K.wiring_problems(registered_checks(), skill_dirs(), installer_names(),
                                     documented_skills() - {"readers"})
        self.assertTrue(any("readers" in p and "docs/skills" in p for p in problems), problems)

    def test_the_invariant_sees_an_unwired_check(self):
        # The invariant itself must go red: a registry entry the catalogue has never heard of.
        fake = registered_checks() | {"audit/audit-zz-new-capability.py"}
        problems = K.wiring_problems(fake, skill_dirs(), installer_names())
        self.assertTrue(any("audit-zz-new-capability" in p for p in problems), problems)

    def test_the_invariant_sees_a_skill_that_is_not_installed(self):
        problems = K.wiring_problems(registered_checks(), skill_dirs() | {"zz-new-skill"}, installer_names())
        self.assertTrue(any("zz-new-skill" in p and "Codex 安装器" in p for p in problems), problems)

    def test_the_invariant_sees_a_catalogued_script_that_is_not_registered(self):
        problems = K.wiring_problems(registered_checks() - {"audit/audit-claim-positioning.py"},
                                     skill_dirs(), installer_names())
        self.assertTrue(any("audit-claim-positioning" in p for p in problems), problems)

    def test_an_unwired_reason_must_say_something(self):
        saved = dict(K.UNWIRED)
        try:
            key = next(iter(K.UNWIRED))
            K.UNWIRED[key] = "n/a"
            problems = K.wiring_problems(registered_checks(), skill_dirs(), installer_names())
            self.assertTrue(any(key in p and "理由" in p for p in problems), problems)
        finally:
            K.UNWIRED.clear()
            K.UNWIRED.update(saved)

    def test_catalogued_scripts_exist(self):
        for c in K.CHECKS:
            for s in c["scripts"]:
                self.assertTrue(K.script_path(s).is_file(), f"{c['id']}: {s}")

    def test_ids_are_unique_and_kinds_known(self):
        ids = [c["id"] for c in K.CHECKS]
        self.assertEqual(len(ids), len(set(ids)))
        for c in K.CHECKS:
            self.assertIn(c["kind"], K.KINDS, c["id"])
            self.assertIn(c["scope"]["kind"], K.SCOPES, c["id"])
            self.assertTrue(set(c["formats"]) <= {"latex", "markdown"}, c["id"])


if __name__ == "__main__":
    unittest.main()


class ClaimLedgerWiringTest(unittest.TestCase):
    """spec 2026-09-30-claim-ledger-reading: the ledger audit reads the bibliography's names (Q2), and the
    changed-sentence check reads the claim ledgers to name the rows an edit unbinds (Q6)."""

    def cfg(self):
        return {"repo": "/tmp/fake-repo", "_ws": "/tmp/fake-ws",
                "inputs": {"bib": "references.bib"},
                "overview": {"ledger": {"path": "audit/ledger.tsv", "base_dir": "sections",
                                        "also": ["audit/ledger-supplement.tsv"], "names": "audit/names.tsv"}}}

    def test_the_ledger_audit_gets_the_bibliography_and_the_names_table(self):
        cfg = self.cfg()
        check = K.by_id("claim-ledger")
        inputs = check["inputs"](cfg)
        self.assertEqual((inputs.get("bib"), inputs.get("names")), ("references.bib", "audit/names.tsv"))
        argv = check["argv"]({"cfg": cfg, "ws": "/tmp/fake-ws", "tmp": "", "inputs": inputs, "also": []})
        self.assertEqual(argv[argv.index("--bib") + 1], "references.bib")
        self.assertEqual(argv[argv.index("--names") + 1], "audit/names.tsv")

    def test_the_changed_sentence_check_gets_every_claim_ledger_as_an_absolute_path(self):
        cfg = self.cfg()
        check = K.by_id("sentence-changes")
        argv = check["argv"]({"cfg": cfg, "ws": "", "tmp": "", "inputs": {}})
        got = [argv[i + 1] for i, x in enumerate(argv) if x == "--ledger"]
        self.assertEqual(got, ["/tmp/fake-repo/audit/ledger.tsv", "/tmp/fake-repo/audit/ledger-supplement.tsv"])
        self.assertTrue(set(got) <= set(check["outside"](cfg)), "editing a ledger makes the last run stale")
