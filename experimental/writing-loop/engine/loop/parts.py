"""Part-by-part revision (spec 2026-09-29-part-by-part-revision): where a rewrite that goes one part at a time is.

A part is a claims-ledger 待做 item of type 写作 that names its sections (`节：W、I2` by label prefix, or a file). While
one is open the notch answers, for the current part, how far it has got (story, candidates, your decision, landed,
checks, built); over the plan, how many parts have landed; whether the landed parts agree; and what in the plan the
draft contradicts. The plan is declared by whoever writes the ledger; every step here is read from the draft, the
acceptance ledger, the index and git, and a contradiction is shown rather than smoothed over.

Only reads: the index on disk, the acceptance ledger, the build report, git log. Returns None when no part is open.
"""
import json
import re
import subprocess
from pathlib import Path

from . import state as S

UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
DATE = re.compile(r"^(?:已做|不做)\s+(\d{4}-\d{2}-\d{2})")
# The size of change the ring already calls small enough to accept without re-reading (ring.SMALL_*): past it, a part
# marked landed is being rewritten again, and change outside the plan is more than a correctness fix.
SMALL_SHARE, SMALL_MIN = 0.02, 5
FREEZE_WORDS = ("冻结", "终检")


def _git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def _index(ws):
    try:
        d = json.loads((Path(ws) / "index" / "sentences.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return d.get("versions") or []


def _flat(text):
    """A sentence reduced to its letters and digits, lower case: the acceptance ledger keeps the gate's plain text and
    the index its own, so the two are compared on what both keep."""
    return re.sub(r"[\W_]+", "", str(text or "").lower())


def _in_part(sentence, part):
    lab, path = sentence.get("label") or "", sentence.get("path") or ""
    for sec in part["sections"]:
        if "/" in sec or sec.endswith(".tex") or sec.endswith(".md"):
            if path == sec:
                return True
        elif S.in_place(lab, sec):
            return True
    return False


def _changed(before, after):
    """Sentences added, changed or removed between two sentence lists, by hash."""
    a, b = [s.get("hash") for s in before], [s.get("hash") for s in after]
    sa, sb = set(a), set(b)
    return sum(1 for h in b if h not in sa) + sum(1 for h in a if h not in sb)


def _small(n):
    return max(SMALL_MIN, round(n * SMALL_SHARE))


def _version_at(versions, sha):
    return next((v for v in versions if v.get("sha") and sha and (v["sha"].startswith(sha) or sha.startswith(v["sha"]))),
                None)


def _landing(cfg, part, files):
    """The last commit on the date the part was marked done that changed its files, or None."""
    m = DATE.match(part["status"] or "")
    if not m or not files:
        return None
    day = m.group(1)
    sha = _git(cfg["repo"], "log", "-1", "--format=%H", f"--since={day} 00:00", f"--until={day} 23:59:59",
               cfg.get("ref") or "HEAD", "--", *sorted(files))
    return sha or None


def _candidates(cfg, part, current_flat):
    """Acceptance-ledger rows that name the part and whose sentence is not in the draft: registered, not landed."""
    from . import coverage as V
    try:
        lines = V.accepted_path(cfg).read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], []
    # tagged 「部分 P6」 / 「part P6」: a bare id collides with the manuscript's own (09-29: 「修订案 5 P6」 is a
    # preregistered hypothesis, and 「P6-102」 another ledger's row), and a longer id (P60) is not this part
    mine = re.compile(r"(?:部分|part)\s*[:：]?\s*" + re.escape(part["id"]) + r"(?![A-Za-z0-9_-])", re.I)
    rows, waiting = [], []
    for ln in lines:
        cells = ln.split("\t")
        if ln.startswith("#") or len(cells) < 4 or not mine.search(cells[1]):
            continue
        row = {"key": cells[0].strip(), "reason": cells[1].strip(), "sentence": cells[3].strip()}
        rows.append(row)
        f = _flat(row["sentence"])
        if f and not any(f in s for s in current_flat):
            waiting.append(row)
    return rows, waiting


def _story(cfg, part):
    """True: the part's story page is there and carries an approval found in the transcripts; False: named but not
    approved (or not there); None: no story page named."""
    if not part["story"]:
        return None
    p = Path(part["story"]).expanduser()
    if not p.is_absolute():
        p = Path(cfg["repo"]) / p
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return False
    from . import targets as TG
    return any(TG._approval_in_transcripts(cfg, u) for u in UUID.findall(text))


def compute(cfg, ws, st, build=None):
    """The part-by-part state, or None when no part is open. st is state.compute's result; build the build report
    ({source_commit, ready_to_upload}) or None."""
    parts = [dict(t) for t in st.get("todo") or [] if t.get("kind") == "写作" and t.get("sections")]
    if not any(not t["closed"] for t in parts):
        return None
    versions = _index(ws)
    now = versions[-1]["sentences"] if versions else []
    current_flat = [_flat(s.get("text")) for s in now]
    for t in parts:
        t["now"] = [s for s in now if _in_part(s, t)]
        t["files"] = sorted({s.get("path") for s in t["now"] if s.get("path")}
                            | {x for x in t["sections"] if "/" in x or x.endswith((".tex", ".md"))})
    contradictions = []
    landings = []
    for t in parts:
        if not t["closed"] or not (t["status"] or "").startswith("已做"):
            continue
        sha = _landing(cfg, t, t["files"])
        t["landing"] = sha
        if not sha:
            contradictions.append({"id": t["id"], "text": f"{t['id']} 标了落稿，那一天那几节没有提交",
                                   "detail": "落稿要有一次改了这几节的提交；写错了日期，或这一部分其实没落"})
            continue
        landings.append(sha)
        v = _version_at(versions, sha)
        if v is None:
            continue
        n = _changed([s for s in v["sentences"] if _in_part(s, t)], t["now"])
        t["changed_after"] = n
        if n > _small(len(t["now"])):
            contradictions.append({"id": t["id"], "text": f"{t['id']} 标了落稿，之后又改了 {n} 处",
                                   "detail": "这一部分还在改：改回在做，或确认是正确性修补"})
    # Change outside the plan since the first landing: sentences no part covers.
    first = None
    for sha in landings:
        v = _version_at(versions, sha)
        if v is not None and (first is None or versions.index(v) < versions.index(first)):
            first = v
    outside = 0
    if first is not None:
        covered = lambda s: any(_in_part(s, t) for t in parts)
        before = [s for s in first["sentences"] if not covered(s)]
        after = [s for s in now if not covered(s)]
        outside = _changed(before, after)
        if outside > _small(len(after)):
            contradictions.append({"id": "计划外", "text": f"改了计划外的 {outside} 处",
                                   "detail": "有节在改却不在任何一部分里：加一部分，或确认是正确性修补"})
    open_ = [t for t in parts if not t["closed"]]
    if any(str(st.get("stage") or "").startswith(w) for w in FREEZE_WORDS):
        contradictions.append({"id": "冻结", "text": f"阶段写着冻结，计划里还有 {len(open_)} 部分没落稿",
                               "detail": "改阶段行（主张清单），或把没落的部分改成不做"})
    # The current part: the open one whose files changed last, else the first open one.
    def last_change(t):
        return _git(cfg["repo"], "log", "-1", "--format=%ct", cfg.get("ref") or "HEAD", "--", *t["files"]) or "0" \
            if t["files"] else "0"
    cur = max(open_, key=lambda t: (int(last_change(t)), -parts.index(t)))
    rows, waiting = _candidates(cfg, cur, current_flat)
    built = None
    if build and build.get("ready_to_upload") and build.get("source_commit"):
        tip = _git(cfg["repo"], "log", "-1", "--format=%H", cfg.get("ref") or "HEAD", "--", *cur["files"]) \
            if cur["files"] else None
        built = bool(tip) and subprocess.run(["git", "-C", str(cfg["repo"]), "merge-base", "--is-ancestor", tip,
                                              str(build["source_commit"])], capture_output=True).returncode == 0
    # Agreement between landed parts, first version: paper-state findings that fall in their sections.
    landed = [t for t in parts if t.get("landing")]
    in_landed = lambda lab: any(_in_part({"label": lab, "path": ""}, t) for t in landed)
    labels = set()
    for o in st.get("over") or []:
        labels |= {x for x in o.get("labels") or [] if in_landed(x)}
    for u in (st.get("unscoped") or []) + (st.get("early") or []):
        if in_landed(u.get("label")):
            labels.add(u["label"])
    for q in st.get("unqualified") or []:
        labels |= {x for x in q.get("labels") or [] if in_landed(x)}
    return {"parts": [{k: t.get(k) for k in ("id", "title", "closed", "sections", "files", "landing", "changed_after")}
                      for t in parts],
            "current": {"id": cur["id"], "title": cur["title"], "index": parts.index(cur) + 1,
                        "story": _story(cfg, cur), "candidates": len(rows), "waiting": waiting, "built": built},
            "total": len(parts), "closed": sum(1 for t in parts if t["closed"]),
            "contradictions": contradictions, "agreement": sorted(labels), "outside": outside}
