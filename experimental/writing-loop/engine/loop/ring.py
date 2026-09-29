"""The manuscript ring: one revision round as seven stages, what hangs on each, and which the engine only infers.

The conversation-layer spec (W1-W4), plus a design stage the author approved: the loop had no "design before
writing" step. The engine has no notion of a revision round,
only of a turn, so a round is read off the register: it starts at the last review gate the author decided (the
register keeps dates, not times, and the ring says so). Nothing here is guessed where the engine cannot see:

  - 你的意见, 改稿, 检查, 读者组 are seen (the author's comments, change sets, the coverage summary, reader results);
  - 设计 and 你核对 are inferred (the intent card is never read; a review is only known by the decision it closed);
  - 落稿 is only a commit (只有提交): whether it followed the review cannot be told.

Since 2026-09-29 (spec 2026-09-29-ring-rounds-and-stages), when the caller passes what it can see (ringinputs): 落稿
is seen from a build report ready to upload, 你核对 from any register decision after the last change, 设计 from the
intent card (and leaves the ring when there is none), a round ends at the later landing or decision, and a frozen
manuscript gets four stages with a stale reader panel said, not hung. Without those inputs the ring is as above.

Open register items hang on the stage their gate names (the first part of 由哪个门决定, by word); a gate id or a
gate no word matches is listed apart. Each hung item says whether it is the author's to decide (a register item) or only
out of date (a check, the reader panel). Checks that are not current hang on 检查; a reader panel older than the last
rewrite hangs on 读者组. This module only reads a summary and two times; the caller supplies both.
"""
import datetime as dt
import re

from . import coverage as V

SEEN = "看得见"
INFERRED = "推出来"
# 「只有提交」：刘海上一格 56pt 宽，六个字放不下又不许缩字（HIG 最小 10pt；09-24 grill 实拍被截成「只看得到…」）。
COMMITS_ONLY = "只有提交"

STAGES = [("comment", "你的意见", SEEN), ("design", "设计", INFERRED), ("rewrite", "改稿", SEEN), ("check", "检查", SEEN),
          ("readers", "读者组", SEEN), ("review", "你核对", INFERRED), ("land", "落稿", COMMITS_ONLY)]

# 分析, between 设计 and 改稿, only when the workspace turns it on (ring.analysis; spec 2026-09-25 §4.5): the analyses a
# round needed ran outside the ring, which could then only offer rewording. It is seen through the claims ledger.
ANALYSIS = ("analysis", "分析", SEEN)


# A frozen manuscript takes correctness fixes only (global rule: once the author calls it uploadable): no design, no
# reader panel, no review round (spec 2026-09-29-ring-rounds-and-stages R5).
FROZEN = ("comment", "rewrite", "check", "land")


def stages(analysis=False, freeze=False, design=True):
    if freeze:
        return [s for s in STAGES if s[0] in FROZEN]
    out = STAGES[:2] + [ANALYSIS] + STAGES[2:] if analysis else list(STAGES)
    return out if design else [s for s in out if s[0] != "design"]


# The first part of a gate, by word. Order matters: 「改稿核对页」 names the review, not the rewrite.
GATE_WORDS = [("design", ("意图卡", "设计")), ("readers", ("读者组",)), ("review", ("核对", "核完")), ("rewrite", ("改稿",))]
NOT_CURRENT = (V.STALE, V.FAILED, V.NEVER, V.MISSING)


def stage_of(gate):
    """The stage a gate names, or None (a gate id such as G2, or words no rule knows)."""
    first = (gate or "").replace(";", "；").split("；")[0]
    for key, words in GATE_WORDS:
        if any(w in first for w in words):
            return key
    return None


def _utc(t):
    """An ISO time as an aware UTC datetime, or None. Times come as …Z (the hooks) and …+01:00 (git): compared as
    strings they order wrongly across offsets."""
    if not t:
        return None
    try:
        d = dt.datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)


def _before(a, b):
    ua, ub = _utc(a), _utc(b)
    return bool(ua and ub and ua < ub)


def _after(t, since):
    """Whether an ISO time falls in the round. A start that is a date (the register's review gates, the author's local
    dates) is compared by the time's own date; a start that is a time (a landing, a decision resolved to its message)
    by the time itself."""
    if not _utc(t):
        return False
    if since is None:
        return True
    if len(str(since)) <= 10:
        return str(t)[:10] >= str(since)
    return not _before(t, since)


def _bounds(landing, decisions, last_comment_at, last_change_at):
    """(the round's start, the event that closed the round shown, if it has not been left yet). A round ends at a
    landing or a decision (R4); the round shown is the one after the latest end once anything moved after it, else
    the one that end closed, so a landing just made is still seen as the round's last stage."""
    ends = [(d.get("at"), "decision") for d in decisions or [] if _utc(d.get("at"))]
    if landing and _utc(landing.get("at")):
        ends.append((landing["at"], "land"))
    ends.sort(key=lambda e: _utc(e[0]))
    if not ends:
        return None, None
    last = ends[-1]
    moved = _before(last[0], last_change_at) or _before(last[0], last_comment_at)
    if moved:
        return last[0], None
    return (ends[-2][0] if len(ends) > 1 else None), last


def _done_on(status):
    """The date an item closed as done (已做 YYYY-MM-DD ...), or None."""
    parts = str(status or "").split()
    return parts[1] if len(parts) > 1 and parts[0] == "已做" else None


def _first_clause(text, limit=60):
    """The first sentence of a register field, without its trailing parenthetical, cut to fit a line."""
    t = re.split(r"[。；;]", str(text or "").strip(), maxsplit=1)[0]
    t = re.sub(r"\s*[（(][^（）()]*[）)]\s*$", "", t).strip()
    return t if len(t) <= limit else t[: limit - 1] + "…"


def _open_detail(x):
    """An open register item's second line on the ring: what closes it and which gate decides it. The title alone
    cannot be read away from the register (panel grill 14, 09-27). Items the register could
    not read keep the reader's own words (格式不全 …)."""
    what, gate = _first_clause(x.get("evidence")), (x.get("gate") or "").strip()
    if not what or str(x.get("detail") or "").startswith("格式不全"):
        return x.get("detail") or ""
    return f"要做：{what}" + (f" · 由：{gate}" if gate else "")


# A stale reader panel says how much changed and whether that is small enough to accept instead of re-reading
# (09-28 panel grill R5: the notch said only "the draft changed, re-read", so a one-word change and a restructure
# looked the same). Small is at most this share of the sentences the panel reads, and never fewer than SMALL_MIN.
# A default, not a rule: anyone can still accept or re-run (coverage.accept); this line only says which is plausible.
SMALL_SHARE, SMALL_MIN = 0.02, 5


def _readers_detail(r, scope):
    base = r.get("detail") or ""
    n, total = r.get("changed") or 0, (scope or {}).get("sentences") or 0
    if n <= 0 or total <= 0:
        return base
    size = f"改动 {n} 处 / 读的范围 {total} 句"
    verdict = (f"改动小（{size}），可以接受这次过期、不重读：跟 Claude 说一声" if n <= max(SMALL_MIN, round(total * SMALL_SHARE))
               else f"改动大（{size}），要重读")
    return f"{base}；{verdict}" if base else verdict


# While a rewrite goes one part at a time (spec 2026-09-29-part-by-part-revision), the ring is the current part's steps.
PART_STAGES = [("story", "讲法", SEEN), ("candidates", "候选", SEEN), ("decide", "你裁", SEEN), ("land", "落稿", SEEN),
               ("check", "检查", SEEN), ("build", "构建", SEEN)]


def _part_ring(summary, parts, name):
    """The ring while parts are open: the current part's steps, the plan's contradictions to decide, progress above
    the route, agreement under it. The reader panel waits until every part has landed (the author, 09-29)."""
    risks = (summary or {}).get("risks") or {}
    open_ = risks.get("open") or []
    cur = parts["current"]
    rows = (summary or {}).get("rows") or []
    checks = [{"id": r.get("id"), "text": f"{r.get('name', r.get('id'))} {r.get('status')}", "detail": r.get("detail") or "",
               "you": False} for r in rows if r.get("id") != "readers" and r.get("status") in NOT_CURRENT]
    waiting = [{"id": c["key"][:8], "text": "候选没入稿：" + _first_clause(c["sentence"], 40), "detail": c["reason"][:200],
                "you": True} for c in cur["waiting"]]
    story = cur["story"]
    states = {
        "story": ("unseen", None) if story is None else (("done", None) if story else ("open", "没认可")),
        "candidates": ("done", None) if cur["candidates"] else ("open", None),
        "decide": ("hanging", None) if waiting else (("done", None) if cur["candidates"] else ("open", None)),
        # The current part has not landed: the whole draft's checks and build say nothing about how far this part got
        # (09-29 shot: a part with no candidates yet read 走到 构建, because the draft's latest build held its file).
        "land": ("open", None),
        "check": ("hanging", None) if checks else ("open", None),
        "build": ("open", None),
    }
    items = {"decide": waiting, "check": checks}
    segments = []
    for key, label, seen in PART_STAGES:
        st, note = states[key]
        seg = {"key": key, "name": label, "seen": seen, "state": st, "items": items.get(key, [])}
        if note:
            seg["note"] = note
        segments.append(seg)
    order = [k for k, _, _ in PART_STAGES]
    done = [k for k in order if states[k][0] == "done"]
    unhung = [{"id": c["id"], "text": c["text"], "detail": c["detail"], "you": True} for c in parts["contradictions"]]
    unhung += [{"id": x.get("id"), "text": f"{x.get('kind', '')} {x.get('id')} {x.get('title', '')}".strip(),
                "detail": _open_detail(x), "you": True} for x in open_]
    landed = [p for p in parts["parts"] if p.get("landing")]
    n = len(parts["agreement"])
    note = (f"落了的部分里 {n} 处对不上" if n else "落了的部分里没查出对不上（只查主张清单的越界、量词与限定词）") \
        if landed else None
    return {"title": name, "since": None, "sinceNote": f"逐段改稿：第 {cur['index']}/{parts['total']} 部分",
            "frozen": False, "frozenNote": note,
            "progress": f"第 {cur['index']}/{parts['total']} 部分：{cur['title']}（已落 {parts['closed']}）",
            "current": next((s["key"] for s in segments if s["state"] == "hanging"), None)
            or next((s["key"] for s in segments if s["state"] == "open"), None),
            "latest": None, "latest_at": None, "reached": done[-1] if done else None, "segments": segments,
            "unhung": unhung, "waiting": len(waiting) + len(unhung), "closed": []}


def ring(summary, *, last_comment_at=None, last_change_at=None, name=None, analysis=None, landing=None,
         decisions=None, design=None, freeze=False, parts=None):
    """analysis: the claims ledger's 分析 items ([{id, title, closed, status}]) when the workspace turns the stage on;
    None keeps the seven-stage ring. An open item hangs on 分析 as work to do, not as the author's to decide.

    The rest (spec 2026-09-29-ring-rounds-and-stages) each keep the old behaviour when not given:
      landing    {"commit", "at", "changed"}: a build report ready to upload, its source commit's time, and whether a
                 draft file changed since (R1). 落稿 is then seen.
      decisions  [{"id", "at"}]: every decided register item, `at` its author message's time, or its date when the
                 message could not be found (R2). 你核对 is then seen, and a round ends at a decision or a landing (R4).
      design     {"configured": bool, "at"}: the intent card and when it last changed (R3). Not configured: 设计 leaves
                 the ring.
      freeze     the manuscript is frozen (R5): four stages, and a stale reader panel is said, not hung as a rerun.
      parts      parts.compute's result while a part-by-part rewrite is open: the ring is the current part's steps."""
    if parts:
        return _part_ring(summary, parts, name)
    # A freeze is earned by a quiet draft, not by the word in the ledger (09-29: the stage said 冻结 while the author
    # rewrote paragraph by paragraph, 541 changes since the reader panel, and the ring read as four stages done, landed,
    # nothing to re-run). More change since the panel than a correctness fix makes (the size the ring already calls
    # small enough to accept without re-reading) and the ring is shown as a rewrite, with the contradiction to decide.
    freeze_broken = None
    if freeze:
        rrow = next((r for r in (summary or {}).get("rows") or [] if r.get("id") == "readers"), None)
        n = (rrow or {}).get("changed") or 0
        total = ((summary or {}).get("readers_scope") or {}).get("sentences") or 0
        if rrow is not None and rrow.get("status") != V.ACCEPTED and n > max(SMALL_MIN, round(total * SMALL_SHARE)):
            freeze_broken, freeze = n, False
    stage_list = stages(analysis is not None and not freeze, freeze, design is None or bool(design.get("configured")))
    keys = {k for k, _, _ in stage_list}
    risks = (summary or {}).get("risks") or {}
    open_, decided = risks.get("open") or [], risks.get("decided") or []

    if landing is None and decisions is None:
        reviews = [d.get("decided_on") for d in decided if stage_of(d.get("gate")) == "review" and d.get("decided_on")]
        since = max(reviews) if reviews else None
    else:
        since, _closed_by = _bounds(landing, decisions, last_comment_at, last_change_at)

    items = {k: [] for k, _, _ in stage_list}
    unhung = []
    for x in open_:
        entry = {"id": x.get("id"), "text": f"{x.get('kind', '')} {x.get('id')} {x.get('title', '')}".strip(),
                 "detail": _open_detail(x), "you": True}
        if x.get("moved"):
            entry["moved"] = x["moved"]
        key = stage_of(x.get("gate"))
        (items[key] if key in items else unhung).append(entry)
    rows = (summary or {}).get("rows") or []
    for r in rows:
        if r.get("id") == "readers":
            continue
        if r.get("status") in NOT_CURRENT:
            items["check"].append({"id": r.get("id"), "text": f"{r.get('name', r.get('id'))} {r.get('status')}", "detail": r.get("detail") or "",
                                   "you": False})
    readers = next((r for r in rows if r.get("id") == "readers"), None)
    frozen_note = None
    if freeze_broken:
        frozen_note = f"阶段写着冻结，读者组之后改了 {freeze_broken} 处：按改稿显示"
        unhung.append({"id": "冻结", "text": f"阶段写着冻结，读者组之后改了 {freeze_broken} 处",
                       "detail": "改回改稿阶段（主张清单的阶段行），或确认这些都是正确性修补、接受这次过期", "you": True})
    if readers is not None and "readers" not in keys:
        # Frozen: a stale panel is said, with how much changed, and never asked for (R5).
        if readers.get("status") in NOT_CURRENT or _before(readers.get("last_at"), last_change_at):
            frozen_note = "冻结期不重读" + (f"（改动 {readers['changed']} 处）" if readers.get("changed") else "")
        readers = None
    if readers is not None:
        at = readers.get("last_at")
        # 接受过期：有人说过这次改动不用重读（coverage.accept），这一环不挂「要重跑」。
        if readers.get("status") in NOT_CURRENT or (_before(at, last_change_at) and readers.get("status") != V.ACCEPTED):
            items["readers"].append({"id": "readers", "text": "读者组 · 过期：稿子改过了，要重读" if at else "读者组 · 还没跑",
                                     "detail": _readers_detail(readers, (summary or {}).get("readers_scope")) if at
                                     else readers.get("detail") or "", "you": False})

    done_on = [d for d in (_done_on(x.get("status")) for x in analysis or [] if x.get("closed")) if d]
    for x in analysis or []:
        if not x.get("closed"):
            items["analysis"].append({"id": x.get("id"), "text": f"分析 {x.get('id')} {x.get('title', '')}".strip(),
                                      "detail": x.get("status") or "", "you": False})
    # 你核对 (R2): a decision of any gate made in the round and not before its last rewrite.
    review_at = None
    if decisions is not None:
        mine = [d["at"] for d in decisions if _after(d.get("at"), since) and not _before(d.get("at"), last_change_at)]
        review_at = max(mine, key=_utc) if mine else None
    # 落稿 (R1): the build is ready and nothing the draft is made of changed since its commit.
    land_at = landing.get("at") if landing and not landing.get("changed") and _after(landing.get("at"), since) \
        and not freeze_broken else None
    design_at = design.get("at") if design and design.get("configured") and _after(design.get("at"), since) else None
    happened = {
        "analysis": any(since is None or d >= str(since)[:10] for d in done_on) if analysis is not None else None,
        "comment": _after(last_comment_at, since),
        "design": (bool(design_at) or None) if design is not None else None,
        "rewrite": _after(last_change_at, since),
        "check": _after(last_change_at, since) and not items["check"],
        "readers": bool(readers and _after(readers.get("last_at"), since)
                        and (not _before(readers.get("last_at"), last_change_at) or readers.get("status") == V.ACCEPTED)),
        "review": bool(review_at),
        "land": (bool(land_at) or ("changed" if landing.get("changed") else False)) if landing is not None else None,
    }
    notes = {}
    if design is not None and design.get("configured") and not design_at:
        notes["design"] = "这一轮没动"  # 意图卡这一轮没改：不是没做，也不是卡在这里
    if happened["land"] == "changed":
        notes["land"] = "改过了"  # 构建之后稿子又改了
    elif freeze_broken and landing is not None:
        notes["land"] = "还在改"  # 构建可上传，但稿子还在改：可上传不等于落稿
    segments = []
    for key, label, seen in stage_list:
        sight = seen
        if key == "land" and landing is not None:
            sight = SEEN
        if key == "review" and decisions is not None:
            sight = SEEN
        if key == "design" and design is not None:
            sight = SEEN
        if key == "analysis":
            # Work to do, not a decision waiting on the author: open while an analysis is open.
            state = "open" if items[key] else ("done" if happened[key] else "unseen")
        elif items[key]:
            state = "hanging"
        elif happened[key] is None:
            state = "unseen"
        elif happened[key] == "changed":
            state = "open"
        else:
            state = "done" if happened[key] else "open"
        seg = {"key": key, "name": label, "seen": sight, "state": state, "items": items[key]}
        if key in notes:
            seg["note"] = notes[key]
        segments.append(seg)
    current = next((s["key"] for s in segments if s["state"] == "hanging"), None) \
        or next((s["key"] for s in segments if s["state"] == "open"), None)

    # Where the round last moved, beside where it waits (a real manuscript waited at 设计 while the day's work was rewriting).
    check_at = max((r.get("last_at") for r in rows if r.get("id") != "readers" and _utc(r.get("last_at"))), key=_utc, default=None)
    moves = [(k, t) for k, t in (("comment", last_comment_at), ("design", design_at), ("rewrite", last_change_at),
                                 ("check", check_at), ("readers", readers.get("last_at") if readers else None),
                                 ("review", review_at), ("land", land_at)) if _utc(t) and k in keys]
    last = max(moves, key=lambda kt: _utc(kt[1])) if moves else None
    latest, latest_at = (last[0], last[1]) if last else (None, None)
    # How far the round got: the furthest stage that moved within it. Neither `current` (the first stage something
    # waits on) nor `latest` (a comment restarts it) says this; the author asked 09-24 why a draft ready to upload
    # still read 设计. A stage reached and then left behind by a later rewrite still counts: the round did get there.
    order = [k for k, _, _ in stage_list]
    moves = [(k, t) for k, t in moves if k in order]
    within = [k for k, t in moves if _after(t, since)]
    reached = max(within, key=order.index) if within else None

    # Gates one message closed are said once: 「W1、W2、W3、W4（288498c5）」, not the same uuid four times (a real
    # register closed four in one message, and the panel line ran out of width).
    by_date = {}
    for d in decided:
        if d.get("decided_on"):
            by_date.setdefault(d["decided_on"], {}).setdefault((d.get("uuid") or "")[:8], []).append(str(d.get("id")))
    closed = [{"date": k, "items": [f"{'、'.join(ids)}（{u}）" if u else "、".join(ids) for u, ids in v.items()]}
              for k, v in sorted(by_date.items(), reverse=True)]
    if landing is None and decisions is None:
        since_note = f"这一轮从 {since} 算起（台账只记日期，精确到日）" if since else "还没有核对页关过门：从头算起"
    elif since:
        exact = len(str(since)) > 10
        since_note = f"这一轮从 {str(since)[:16].replace('T', ' ')} 算起（上一次落稿或裁定）" + ("" if exact else "（只知道日期）")
    else:
        since_note = "还没有落稿或裁定：从头算起"
    return {"title": name, "since": since, "sinceNote": since_note, "frozen": bool(freeze), "frozenNote": frozen_note,
            "current": current, "latest": latest, "latest_at": latest_at, "reached": reached, "segments": segments, "unhung": unhung,
            "waiting": len(open_) + (1 if freeze_broken else 0), "closed": closed}
