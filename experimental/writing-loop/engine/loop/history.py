"""Draft history from git, with stable sentence ids.

A version is the draft as of one commit that changed it. The draft file may be renamed per
version (DRAFT-…-v8.md → -v9.md); the current draft at a commit is the highest-numbered file
that exists there. Sentence ids (S0001…) are inherited through alignment, never through position.
"""
import fnmatch
import json
import os
import posixpath
import re
from pathlib import Path

from . import align as A
from . import config as C
from . import gitio
from .text import sentences_of, text_hash


def _draft_at(cfg, commit):
    """The draft's path(s) at commit. A glob names one file per version (the highest-numbered); a list names
    several files that together are the draft, joined in the listed order (a LaTeX main file and its sections)."""
    g = cfg["draft"]["glob"]
    if isinstance(g, list):
        present = [p for p in g if gitio.ls_tree(cfg["repo"], commit, p)]
        return present or None
    names = [n for n in gitio.ls_tree(cfg["repo"], commit, posixpath.dirname(g) or ".") if fnmatch.fnmatch(n, g)]
    return max(names, key=C.version_key) if names else None


def _pathspecs(cfg):
    g = cfg["draft"]["glob"]
    return list(g) if isinstance(g, list) else [f":(glob){g}"]


def load_versions(cfg, until=None, cache_file=None):
    """Versions oldest first: [{"sha", "time", "subject", "body", "path", "blob", "sentences"}].
    Commits that leave the current draft's bytes unchanged are skipped.

    cache_file (K11 power, 2026-10-01): what each commit gave — its draft path and blob, and its sentences when it
    was a version — kept on disk. A commit never changes, so a later update reads only the commits it has not seen;
    on a real manuscript re-reading them was the largest single cost of an update. The caller keys the file by the
    engine and the draft settings, so a change to either starts a fresh one."""
    repo = cfg["repo"]
    head = until or gitio.rev_parse(repo, cfg["ref"])
    commits = gitio.log_touching(repo, head, _pathspecs(cfg))
    seen = _read_cache(cache_file)
    fresh = {}
    versions, last_blob = [], None
    for c in commits:
        e = seen.get(c["sha"])
        if e is None:
            path = _draft_at(cfg, c["sha"])
            if path is None:
                fresh[c["sha"]] = {"absent": True}
                continue
            paths = path if isinstance(path, list) else [path]
            blobs = [gitio.blob_id(repo, c["sha"], p) for p in paths]
            e = {"paths": paths, "blob": blobs[0] if len(blobs) == 1 else "+".join(blobs)}
        elif e.get("absent"):
            fresh[c["sha"]] = e
            continue
        fresh[c["sha"]] = e
        if e["blob"] == last_blob:
            continue
        if "sentences" not in e:
            texts = [(p, gitio.show(repo, c["sha"], p)) for p in e["paths"]]
            md = "\n\n".join(t for _, t in texts)
            sents = sentences_of(md, cfg["draft"]["sections"], cfg["draft"].get("format", "markdown"))
            locate(sents, texts)
            for s in sents:
                s["hash"] = text_hash(s["text"])
            e["sentences"] = sents
        paths = e["paths"]
        path = paths[0] if len(paths) == 1 else "+".join(paths)
        # The cache is written below, before the caller touches the versions (assign_ids adds ids in place).
        versions.append({**c, "path": path, "blob": e["blob"], "sentences": e["sentences"]})
        last_blob = e["blob"]
    if cache_file is not None and fresh != seen:
        _write_cache(cache_file, fresh)
    return versions


def _read_cache(cache_file):
    if cache_file is None:
        return {}
    try:
        data = json.loads(Path(cache_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_cache(cache_file, data):
    p = Path(cache_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


_WORD = re.compile(r"\S+")
LOCATE_WORDS = 6


def locate(sents, files):
    """Give each sentence the file and 1-based line where its first six words start, matched across line breaks
    (候选 A：面板里点开改动集要能指到「文件:行」). A sentence whose words are not found as written — cut by a LaTeX
    command, a title line rewritten by the splitter — gets neither key; nothing is guessed."""
    for s in sents:
        words = _WORD.findall(s["text"])[:LOCATE_WORDS]
        if not words:
            continue
        pat = re.compile(r"\s+".join(re.escape(w) for w in words))
        for path, text in files:
            m = pat.search(text)
            if m:
                s["path"] = path
                s["line"] = text.count("\n", 0, m.start()) + 1
                break


def _group(s):
    return f"{s['section']}{s['par']}"


def assign_ids(versions, aligner=None):
    """Give every sentence a stable id and return one transition per consecutive version pair.

    transition = {"from": i, "to": i+1, "align": aligner result}
    Inheritance: pairs keep the id; a split gives the old id to the part most similar to the
    whole and fresh ids (with split_from) to the rest; a merge keeps the id of the most similar
    old part and records merged_into on the others.
    """
    aligner = aligner or A.align
    counter = 0

    def fresh():
        nonlocal counter
        counter += 1
        return f"S{counter:04d}"

    transitions = []
    for vi, v in enumerate(versions):
        S = v["sentences"]
        if vi == 0:
            for s in S:
                s["sid"] = fresh()
            continue
        P = versions[vi - 1]["sentences"]
        al = aligner([p["text"] for p in P], [s["text"] for s in S],
                     [_group(p) for p in P], [_group(s) for s in S])
        for i, j, _ in al["pairs"]:
            S[j]["sid"] = P[i]["sid"]
        for i, run, _, parts in al["splits"]:
            heir = run[max(range(len(run)), key=lambda k: (parts[k], -k))]
            for j in run:
                if j == heir:
                    S[j]["sid"] = P[i]["sid"]
                else:
                    S[j]["sid"] = fresh()
                    S[j]["split_from"] = P[i]["sid"]
        for run, j, _, parts in al["merges"]:
            heir = run[max(range(len(run)), key=lambda k: (parts[k], -k))]
            S[j]["sid"] = P[heir]["sid"]
            S[j]["merged_from"] = [P[i]["sid"] for i in run]
        for j in al["added"]:
            S[j]["sid"] = fresh()
        for j, i, _ in al.get("derived", []):
            S[j]["derived_from"] = P[i]["sid"]
        missing = [s["label"] for s in S if "sid" not in s]
        if missing:
            raise AssertionError(f"alignment left sentences without an id at {v['sha'][:7]}: {missing}")
        ids = [s["sid"] for s in S]
        if len(set(ids)) != len(ids):
            raise AssertionError(f"duplicate sentence ids at {v['sha'][:7]}")
        transitions.append({"from": vi - 1, "to": vi, "align": al})
    return transitions


def positional_aligner(old, new, old_groups=None, new_groups=None):
    """Deliberately wrong reference: pairs sentences by index. Used only to prove tests go red."""
    n = min(len(old), len(new))
    return {"pairs": [(k, k, 1.0) for k in range(n)], "splits": [], "merges": [],
            "added": list(range(n, len(new))), "removed": list(range(n, len(old))), "moved": [], "derived": [], "absorbed": []}
