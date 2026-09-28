"""The manuscript ring: one revision round as seven stages, what hangs on each, and which the engine only infers.

The conversation-layer spec (W1-W4), plus a design stage the author approved: the loop had no "design before
writing" step. The engine has no notion of a revision round,
only of a turn, so a round is read off the register: it starts at the last review gate the author decided (the
register keeps dates, not times, and the ring says so). Nothing here is guessed where the engine cannot see:

  - 你的意见, 改稿, 检查, 读者组 are seen (the author's comments, change sets, the coverage summary, reader results);
  - 设计 and 你核对 are inferred (the intent card is never read; a review is only known by the decision it closed);
  - 落稿 is only a commit (只有提交): whether it followed the review cannot be told.

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


def stages(analysis=False):
    return STAGES[:2] + [ANALYSIS] + STAGES[2:] if analysis else STAGES


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
    """Whether an ISO time falls in the round: on or after its start date (dates only in the register, which are the
    author's local dates, so the time's own date is compared)."""
    return bool(_utc(t)) and (since is None or str(t)[:10] >= since)


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


def ring(summary, *, last_comment_at=None, last_change_at=None, name=None, analysis=None):
    """analysis: the claims ledger's 分析 items ([{id, title, closed, status}]) when the workspace turns the stage on;
    None keeps the seven-stage ring. An open item hangs on 分析 as work to do, not as the author's to decide."""
    stage_list = stages(analysis is not None)
    risks = (summary or {}).get("risks") or {}
    open_, decided = risks.get("open") or [], risks.get("decided") or []
    reviews = [d.get("decided_on") for d in decided if stage_of(d.get("gate")) == "review" and d.get("decided_on")]
    since = max(reviews) if reviews else None

    items = {k: [] for k, _, _ in stage_list}
    unhung = []
    for x in open_:
        entry = {"id": x.get("id"), "text": f"{x.get('kind', '')} {x.get('id')} {x.get('title', '')}".strip(),
                 "detail": _open_detail(x), "you": True}
        if x.get("moved"):
            entry["moved"] = x["moved"]
        key = stage_of(x.get("gate"))
        (items[key] if key else unhung).append(entry)
    rows = (summary or {}).get("rows") or []
    for r in rows:
        if r.get("id") == "readers":
            continue
        if r.get("status") in NOT_CURRENT:
            items["check"].append({"id": r.get("id"), "text": f"{r.get('name', r.get('id'))} {r.get('status')}", "detail": r.get("detail") or "",
                                   "you": False})
    readers = next((r for r in rows if r.get("id") == "readers"), None)
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
    happened = {
        "analysis": any(since is None or d >= since for d in done_on) if analysis is not None else None,
        "comment": _after(last_comment_at, since),
        "design": None,
        "rewrite": _after(last_change_at, since),
        "check": _after(last_change_at, since) and not items["check"],
        "readers": bool(readers and _after(readers.get("last_at"), since)
                        and (not _before(readers.get("last_at"), last_change_at) or readers.get("status") == V.ACCEPTED)),
        "review": False,
        "land": None,
    }
    segments = []
    for key, label, seen in stage_list:
        if key == "analysis":
            # Work to do, not a decision waiting on the author: open while an analysis is open.
            state = "open" if items[key] else ("done" if happened[key] else "unseen")
        elif items[key]:
            state = "hanging"
        elif happened[key] is None:
            state = "unseen"
        else:
            state = "done" if happened[key] else "open"
        segments.append({"key": key, "name": label, "seen": seen, "state": state, "items": items[key]})
    current = next((s["key"] for s in segments if s["state"] == "hanging"), None) \
        or next((s["key"] for s in segments if s["state"] == "open"), None)

    # Where the round last moved, beside where it waits (a real manuscript waited at 设计 while the day's work was rewriting).
    check_at = max((r.get("last_at") for r in rows if r.get("id") != "readers" and _utc(r.get("last_at"))), key=_utc, default=None)
    moves = [(k, t) for k, t in (("comment", last_comment_at), ("rewrite", last_change_at), ("check", check_at),
                                 ("readers", readers.get("last_at") if readers else None)) if _utc(t)]
    last = max(moves, key=lambda kt: _utc(kt[1])) if moves else None
    latest, latest_at = (last[0], last[1]) if last else (None, None)
    # How far the round got: the furthest stage that moved within it. Neither `current` (the first stage something
    # waits on) nor `latest` (a comment restarts it) says this; the author asked 09-24 why a draft ready to upload
    # still read 设计. A stage reached and then left behind by a later rewrite still counts: the round did get there.
    order = [k for k, _, _ in stage_list]
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
    return {"title": name, "since": since,
            "sinceNote": f"这一轮从 {since} 算起（台账只记日期，精确到日）" if since else "还没有核对页关过门：从头算起",
            "current": current, "latest": latest, "latest_at": latest_at, "reached": reached, "segments": segments, "unhung": unhung,
            "waiting": len(open_), "closed": closed}
