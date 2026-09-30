#!/usr/bin/env python3
"""Claim ledger audit for LaTeX manuscripts.

    python3 audit-claim-ledger.py --base-dir <manuscript> --ledger <ledger.tsv> [--ledger <more.tsv> ...]
                                  [--also-file <supplement.tex> ...] [--json] [--pairs] [--allow-empty]

The gap this closes: the citation fidelity audit reads `chapters/**/*.md`
against reading notes. A LaTeX manuscript's claims about its sources were
checked by nothing at all.

A ledger row binds one manuscript sentence to one verbatim snippet in one
archived source, and the audit checks that binding in both directions:

  snippet-not-in-source          the snippet is not verbatim in the archived source
  claim-not-in-manuscript        the sentence was edited; the binding is stale
  key-not-in-claim-sentence      the row names a key the sentence does not cite
  source-file-missing            the archived source is not on disk
  negative-claim-without-fulltext  "X did not do Y" recorded against an abstract
  unledgered-assertion           a citing sentence that asserts something about
                                 its source and has no ledger row
  qualifier-dropped              PROMPT: a hedge in the snippet that the claim
                                 does not carry ("expected", "some", "may")
  unread-high-risk               a negative, scope or numeric claim that no
                                 author has read against its snippets
  unledgered-negative-claim      "X did not do Y" about a cited work, with no row
  uncited-literature-claim       PROMPT (hard in gate mode for a new sentence):
                                 "cited here", "prior work"... with no \\cite
  named-work-without-cite        PROMPT (the same): a registered work named with
                                 no \\cite
  recheck-same-key               PROMPT: a row the author read as wrong; the other
                                 sentences citing that key, to read again

Found is not read (spec docs/specs/2026-09-30-claim-ledger-reading.md). A snippet
that is verbatim in its source can still be about something else; on one real
manuscript two such rows stayed green until a person read the source. So a row
may carry a `read` column, `author: <what the snippet says, what the sentence
adds>` or `draft: <the same, written by an agent>`, and the report counts found,
draft-read and author-read rows. Only high-risk claims that no author has read
are findings: a negative claim, a scope claim ("only", "first", "outside"), or a
number the claim's snippets do not contain. Every snippet of a claim is read
together (`--pairs` groups rows by claim across all ledgers): one claim judged
against one of its three rows was once "corrected" wrongly. An optional `version`
column records where the evidence came from (an arXiv version, say, while the
bibliography cites the proceedings version).

Claims with no \\cite are still claims. A sentence that points at the literature
("the benchmarks cited here", "prior work") or names a work the bibliography
registers (by --names, or by its shorttitle in --bib) with no \\cite is listed.
Works with no name are not checked, and the report says how many.

What it does NOT do: judge whether a claim says more than its snippet in
words the snippet never used. Machine judgement of that was measured on a
small red-check set: with the claim and its passage paired it caught 7 of 8,
and it missed a dropped "expected" every time. So the audit binds and prompts;
a reader still decides. `--pairs` prints claim/snippet pairs for that reading.

Commit gate (--gate-since GITREF, --credits FILE)
------------------------------------------------
Run over a whole manuscript the audit produces a long coverage list that nobody
reads at the moment a citation is written. `--gate-since` narrows it to the
citing sentences this change added, and makes those hard findings, so the check
can sit on the commit instead of on the submission.

  new-assertion-unledgered     a new sentence asserts something about its source
  new-citation-unaccounted     a new sentence cites a source with no account
  credit-outside-its-procedure a credited key used for a procedure it was not
                               credited for

`--credits` holds the method credits the author accepts, one per line, as
`key = the procedure it may be cited for`. The procedure matters: run against
the six commits that introduced the wrong citations in a real manuscript, a
key-only allowlist let an equivalence-testing paper through as the source of a
permutation test, because the key was listed and the sentence read like a
credit. A bare key (no `=`) restores that hole. A key may be listed on
several lines, one procedure each; any procedure the sentence names covers it.

The full scan reads the same file: a citing sentence with no ledger row whose
every key is covered is reported as `credited` and leaves the
unledgered-assertion count, so a sentence the author has already accepted as a
method credit stops reading as missing evidence.

Historical check, 2026-09-20: over the four commits that introduced them, the
gate flags all six wrong citations plus the dropped qualifier, as part of 34,
14, 6 and 4 flagged sentences respectively. It demands an account; it does not
judge whether the account is right.

Exit: 1 on a hard finding, 2 when no ledger row was checked at all (an empty
ledger verifies nothing, whatever the coverage list says) unless --allow-empty,
0 otherwise. In gate mode a change that added no citation is a pass.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

COLUMNS = ["claim", "cite_key", "snippet", "source_file", "level"]
OPTIONAL = ["read", "version"]
LEVELS = {"fulltext", "abstract-only", "metadata"}
# Verbs that make a citing sentence a claim about its source rather than a
# credit line ("we use X~\cite{y}").
REPORTING = re.compile(
    r"\b(show|shows|showed|shown|find|finds|found|report|reports|reported|document|documents|documented"
    r"|demonstrate\w*|establish\w*|catalogu\w*|argue\w*|observe[sd]?|note[sd]?|propose[sd]?|examine[sd]?"
    r"|conclude[sd]?|reveal\w*|suggest\w*|claim[sd]?|describe[sd]?|warn[sd]?)\b", re.I)
NEGATIVE = re.compile(
    r"\b(did not|does not|do not|never|no prior|nobody|none of|neither|is not|are not|was not|were not"
    r"|first to|the only)\b", re.I)
# A claim that a cited work lacks something ("did not evaluate", "no prior"). The copular negations of NEGATIVE are
# left out: "an absolute score is not meaningful in isolation" reports a view, it does not say the work left anything
# out, and an existing fixture carries exactly that sentence.
NEGATIVE_WORK = re.compile(
    r"\b(did not|does not|do not|never|no prior|nobody|none of|neither|first to|the only)\b", re.I)
# "first" only as a claim of priority ("the first", "first to"): "X first masks the text, then ..." is a sequence.
# "only" inside a compound ("hypothesis-only") names a thing, it does not limit a claim.
SCOPE = re.compile(r"(?<!-)\b(only|solely|exclusively|outside|beyond (?:the|their|its) scope|the first|first to|no prior|none)\b",
                   re.I)
# A number standing alone: digits inside a name (ColQwen2.5-v0.2) are not a count, and "one" is mostly a determiner or
# a pronoun ("one framework", "the one"). Measured on one real ledger, those two made six of ten hits noise.
NUMBER = re.compile(
    r"(?<![\w.-])(\d[\d.,]*\d|\d)(?![\w-])|\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty"
    r"|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|half|twice|double|triple)\b", re.I)
POINTING = re.compile(
    r"\b(cited (?:here|above|below|earlier)|(?:prior|previous|earlier) (?:work|works|studies|benchmarks|methods)"
    r"|the literature|existing (?:work|works|benchmarks|methods|datasets|studies)"
    r"|these (?:benchmarks|studies|works))\b", re.I)
HEDGE = ["expected", "may", "might", "can", "could", "some", "many", "often", "typically", "likely",
         "possibly", "approximately", "about", "partly", "partially", "only", "largely", "mostly"]
CITE = re.compile(r"\\[a-zA-Z]*cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}")


def clean_tex(text):
    text = re.sub(r"(?m)(?<!\\)%.*$", "", text)
    text = re.sub(r"\\(?:label|ref|eqref|input|include)\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:section|subsection|subsubsection|paragraph)\*?\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:emph|textbf|textit|texttt|text)\{([^}]*)\}", r"\1", text)
    text = text.replace("~", " ").replace("--", "-").replace("\\%", "%")
    return re.sub(r"\s+", " ", text)


def norm(text):
    """Whitespace, hyphenated line breaks and quotation marks normalised for matching."""
    text = re.sub(r"-\s*\n\s*", "", text)
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("--", "-").replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def tex_files(base):
    return [p for p in sorted(base.rglob("*.tex"))
            if not any(part.startswith(".") or part in {"node_modules", "build"} for part in p.relative_to(base).parts)]


def split_cited(text):
    """[(sentence, keys)] for every sentence of `text` that carries a \\cite."""
    out = []
    for sentence in re.split(r"(?<=[.])\s+(?=[A-Z\\])", clean_tex(text)):
        keys = [k.strip() for group in CITE.findall(sentence) for k in group.split(",") if k.strip()]
        if keys:
            out.append((sentence.strip(), keys))
    return out


def split_all(text):
    """Every sentence of `text`, with its keys (empty when it cites nothing)."""
    out = []
    for sentence in re.split(r"(?<=[.])\s+(?=[A-Z\\])", clean_tex(text)):
        keys = [k.strip() for group in CITE.findall(sentence) for k in group.split(",") if k.strip()]
        if sentence.strip():
            out.append((sentence.strip(), keys))
    return out


def manuscript_files(base, also=()):
    """[(path, label)]: every .tex under base, then each --also-file (a supplement outside base, say), each once.
    09-27: moving text into a supplement at the repository root took it out of the base directory, and 13 ledger
    rows read as edited away while the sentences were only elsewhere."""
    out = [(p, str(p.relative_to(base))) for p in tex_files(base)]
    seen = {p.resolve() for p, _ in out}
    for x in also:
        p = Path(x).expanduser().resolve()
        if p not in seen:
            seen.add(p)
            out.append((p, str(x)))
    return out


def citing_sentences(base, also=()):
    """[(file, sentence, keys)] for every sentence that carries a \\cite."""
    out = []
    for path, label in manuscript_files(base, also):
        for sentence, keys in split_cited(path.read_text(encoding="utf-8", errors="replace")):
            out.append((label, sentence, keys))
    return out


def sentences_at_ref(base, ref, also=(), every=False):
    """Normalised citing sentences (every sentence, with every=True) as they stood at `ref`.

    Files that did not exist there contribute nothing, so every sentence of a
    newly added file counts as new.
    """
    top = subprocess.run(["git", "-C", str(base), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if top.returncode:
        sys.exit(f"GATE_NOT_A_REPO: {base} is not inside a git repository")
    root = Path(top.stdout.strip())
    if subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                      capture_output=True).returncode:
        sys.exit(f"GATE_BAD_REF: {ref} is not a commit in {root}")
    before = set()
    for path, _ in manuscript_files(base, also):
        rel = path.resolve().relative_to(root)
        shown = subprocess.run(["git", "-C", str(root), "show", f"{ref}:{rel}"],
                               capture_output=True, text=True)
        if shown.returncode:
            continue
        before.update(norm(s) for s, _ in (split_all if every else split_cited)(shown.stdout))
    return before


def read_credits(path):
    """key -> [procedure, ...] as the author accepted them; an empty procedure accepts any use."""
    credits = {}
    for line in Path(path).expanduser().read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        key, _, procedure = line.partition("=")
        credits.setdefault(key.strip(), []).append(norm(procedure))
    return credits


def uncovered(keys, sentence, credits):
    """The keys of `sentence` that no accepted credit covers.

    Match the procedure against the prose only. Key names carry the procedure's
    own words (lakens2017equivalence), so leaving the \\cite in would let a key
    vouch for itself."""
    prose = norm(CITE.sub(" ", sentence))
    return [k for k in keys if not any(p == "" or p in prose for p in credits.get(k, []))]


def read_names(names_files, bib_files):
    """name -> key, from name<TAB>key tables and from `shorttitle` in bibliographies."""
    names = {}
    for f in bib_files:
        text = Path(f).expanduser().read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,(.*?)(?=\n@|\Z)", text, re.S):
            t = re.search(r"shorttitle\s*=\s*(?:\{([^{}]*)\}|\"([^\"]*)\")", m.group(2), re.I)
            name = t and (t.group(1) if t.group(1) is not None else t.group(2)).strip()
            if name:
                names[name] = m.group(1)
    for f in names_files:
        for line in Path(f).expanduser().read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].rstrip()
            if "\t" in line:
                name, key = line.split("\t", 1)
                if name.strip() and key.strip():
                    names[name.strip()] = key.strip()
    return names


def reading(row):
    """author / draft / "" (found only)."""
    r = row.get("read", "").strip().lower()
    return "author" if r.startswith("author:") else ("draft" if r.startswith("draft:") else "")


def risks(claim, snippets):
    """Why a claim is high-risk: negative, scope, numbers none of its snippets contain."""
    out = []
    if NEGATIVE_WORK.search(claim):
        out.append("negative")
    if SCOPE.search(claim):
        out.append("scope")
    text = norm(" ".join(snippets))
    found = {(m.group(1) or m.group(2)).lower() for m in NUMBER.finditer(claim)}
    missing = sorted(x for x in found if not re.search(rf"(?<![\w.]){re.escape(x)}(?![\w])", text))
    if missing:
        out.append("numbers not in its snippets: " + ", ".join(missing))
    return out


def read_ledger(path):
    rows = []
    lines = [l.rstrip("\n") for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return rows
    header = lines[0].split("\t")
    if header[:len(COLUMNS)] != COLUMNS:
        sys.exit(f"LEDGER_COLUMNS: expected {COLUMNS}, found {header}")
    for n, line in enumerate(lines[1:], 2):
        parts = line.split("\t")
        if len(parts) < len(COLUMNS):
            sys.exit(f"LEDGER_COLUMNS: line {n} has {len(parts)} columns, expected {len(COLUMNS)}")
        row = dict(zip(COLUMNS, parts))
        for col in OPTIONAL:
            row[col] = parts[header.index(col)].strip() if col in header and header.index(col) < len(parts) else ""
        row["line"] = n
        if row["level"] not in LEVELS:
            sys.exit(f"LEDGER_LEVEL: line {n} has level {row['level']!r}, expected one of {sorted(LEVELS)}")
        rows.append(row)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--ledger", required=True, action="append",
                    help="a ledger; give it more than once (the text's ledger, a supplement's), and the rows are read together")
    ap.add_argument("--also-file", action="append", default=[], metavar="FILE",
                    help="a manuscript file outside --base-dir to read too (a supplement at the repository root)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--pairs", action="store_true", help="print claim/snippet pairs for reading")
    ap.add_argument("--allow-empty", action="store_true")
    ap.add_argument("--gate-since", metavar="GITREF",
                    help="only citing sentences that are new since GITREF are hard findings")
    ap.add_argument("--credits", metavar="FILE",
                    help="method credits the author has accepted, one per line, as "
                         "'key = the procedure it may be cited for'; a bare key accepts any use. "
                         "Read by the full scan and by the commit gate")
    ap.add_argument("--bib", action="append", default=[], metavar="FILE",
                    help="a bibliography whose shorttitle fields name works (checked for mentions with no \\cite)")
    ap.add_argument("--names", action="append", default=[], metavar="FILE",
                    help="name<TAB>key lines: works whose mentions with no \\cite are listed")
    a = ap.parse_args(argv)
    base = Path(a.base_dir).expanduser().resolve()
    ledger_paths = [Path(x).expanduser().resolve() for x in a.ledger]
    ledger_path = ledger_paths[0]
    if not base.is_dir():
        sys.exit(f"BASE_MISSING: {base}")
    for lp in ledger_paths:
        if not lp.is_file():
            sys.exit(f"LEDGER_MISSING: {lp}")
    for x in a.also_file:
        if not Path(x).expanduser().is_file():
            sys.exit(f"ALSO_FILE_MISSING: {x}")

    sentences = citing_sentences(base, a.also_file)
    rows = []
    for lp in ledger_paths:
        for row in read_ledger(lp):
            row["_ledger"] = lp
            rows.append(row)
    credits = read_credits(a.credits) if a.credits else {}
    findings, pairs = [], []
    before = sentences_at_ref(base, a.gate_since, a.also_file) if a.gate_since else None
    before_all = sentences_at_ref(base, a.gate_since, a.also_file, every=True) if a.gate_since else None

    for row in rows:
        loc = f"{row['_ledger'].name}:{row['line']}"
        claim_n = norm(row["claim"])
        bound = [(f, s, k) for f, s, k in sentences if claim_n and claim_n in norm(s)]
        if not bound:
            findings.append({"kind": "claim-not-in-manuscript", "location": loc, "cite_key": row["cite_key"],
                             "detail": f"the ledger's claim is not a sentence in the manuscript: {row['claim'][:90]}"})
        elif row["cite_key"] not in {k for _, _, keys in bound for k in keys}:
            findings.append({"kind": "key-not-in-claim-sentence", "location": loc, "cite_key": row["cite_key"],
                             "detail": f"the bound sentence does not cite {row['cite_key']}"})
        source = (base / row["source_file"]) if not Path(row["source_file"]).is_absolute() else Path(row["source_file"])
        if not source.is_file():
            source = row["_ledger"].parent / row["source_file"]
        if not source.is_file():
            findings.append({"kind": "source-file-missing", "location": loc, "cite_key": row["cite_key"],
                             "detail": f"archived source not found: {row['source_file']}"})
        else:
            text = norm(source.read_text(encoding="utf-8", errors="replace"))
            if norm(row["snippet"]) not in text:
                findings.append({"kind": "snippet-not-in-source", "location": loc, "cite_key": row["cite_key"],
                                 "detail": f'"{row["snippet"][:90]}" is not verbatim in {row["source_file"]}'})
        if NEGATIVE.search(row["claim"]) and row["level"] != "fulltext":
            findings.append({"kind": "negative-claim-without-fulltext", "location": loc, "cite_key": row["cite_key"],
                             "detail": f"a negative claim recorded against level={row['level']}; read the full text or scope the sentence to what was read"})
        dropped = [h for h in HEDGE
                   if re.search(rf"\b{re.escape(h)}\b", row["snippet"], re.I)
                   and not re.search(rf"\b{re.escape(h)}\b", row["claim"], re.I)]
        if dropped:
            findings.append({"kind": "qualifier-dropped", "prompt": True, "location": loc, "cite_key": row["cite_key"],
                             "detail": f"the snippet hedges with {dropped}; the claim does not — read the pair before trusting it"})
        pairs.append({"cite_key": row["cite_key"], "claim": row["claim"], "snippet": row["snippet"],
                      "source_file": row["source_file"], "level": row["level"], "version": row["version"],
                      "read": row["read"], "location": loc})

    # Found is not read: one finding per claim, judged with every row the claim has (in every ledger).
    groups = {}
    for row in rows:
        groups.setdefault(norm(row["claim"]), []).append(row)
    for claim_n, group in groups.items():
        why = risks(group[0]["claim"], [r["snippet"] for r in group])
        if not why or any(reading(r) == "author" for r in group):
            continue
        loc = f"{group[0]['_ledger'].name}:{group[0]['line']}"
        new = before is None or not any(claim_n in norm(s) and norm(s) not in before for _, s, _ in sentences)
        findings.append({"kind": "unread-high-risk", "prompt": before is not None and new is False, "location": loc,
                         "cite_key": ",".join(sorted({r["cite_key"] for r in group})),
                         "detail": f"{'; '.join(why)} — no author has read it against its {len(group)} snippet(s); "
                                   f"write read: author: <what they say, what the sentence adds>: {group[0]['claim'][:80]}"})
    # A row the author read as wrong: the other sentences citing that key are read again.
    for row in rows:
        if re.match(r"\s*author:\s*wrong\b", row["read"], re.I):
            others = [(f, s) for f, s, k in sentences if row["cite_key"] in k and norm(row["claim"]) not in norm(s)]
            for f, s in others:
                findings.append({"kind": "recheck-same-key", "prompt": True, "location": f, "cite_key": row["cite_key"],
                                 "sentence": s, "detail": f"{row['_ledger'].name}:{row['line']} was read as wrong; "
                                                          f"this sentence cites {row['cite_key']} too: {s[:90]}"})

    ledgered = {norm(r["claim"]) for r in rows if norm(r["claim"])}
    for f, s, keys in sentences:
        if any(c and c in norm(s) for c in ledgered):
            continue
        if NEGATIVE_WORK.search(CITE.sub(" ", s)):
            old = before is not None and norm(s) in before
            findings.append({"kind": "unledgered-negative-claim", "prompt": old, "location": f,
                             "cite_key": ",".join(keys), "sentence": s,
                             "detail": f"says a cited work lacks something, with no ledger row: {s[:90]}"})
            continue
        if credits and not uncovered(keys, s, credits):
            findings.append({"kind": "credited", "prompt": False, "location": f, "cite_key": ",".join(keys),
                             "sentence": s, "detail": f"accepted as a method credit for {','.join(keys)}: {s[:90]}"})
            continue
        kind = "unledgered-assertion" if REPORTING.search(s) else "unledgered-credit"
        findings.append({"kind": kind, "prompt": kind == "unledgered-credit", "location": f,
                         "cite_key": ",".join(keys), "sentence": s,
                         "detail": f"{'asserts something about' if kind == 'unledgered-assertion' else 'credits'} {','.join(keys)} with no ledger row: {s[:90]}"})

    # Claims with no \cite: pointing phrases, and works named without a citation.
    names = read_names(a.names, a.bib)
    cited_keys = {k for _, _, keys in sentences for k in keys}
    unnamed = sorted(cited_keys - set(names.values()))
    for path, label in manuscript_files(base, a.also_file):
        for s, keys in split_all(path.read_text(encoding="utf-8", errors="replace")):
            if keys:
                continue
            new = before_all is not None and norm(s) not in before_all
            m = POINTING.search(s)
            if m:
                findings.append({"kind": "uncited-literature-claim", "prompt": not new, "location": label,
                                 "sentence": s, "cite_key": "",
                                 "detail": f"points at the literature (\"{m.group(1)}\") with no \\cite: {s[:90]}"})
            named = [n for n in names if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", s)]
            if named:
                findings.append({"kind": "named-work-without-cite", "prompt": not new, "location": label,
                                 "sentence": s, "cite_key": ",".join(names[n] for n in named),
                                 "detail": f"names {', '.join(named)} with no \\cite: {s[:90]}"})

    gate = None
    if a.gate_since:
        # A credit is accepted for a named procedure, not for a key outright.
        # Run against the commit that introduced them, a key-only allowlist let
        # an equivalence-testing paper through as the source of a permutation
        # test: the key was listed, and the sentence read like a credit.
        added = [(f, s, k) for f, s, k in sentences if norm(s) not in before]
        for f, s, keys in added:
            if any(c and c in norm(s) for c in ledgered):
                continue
            off = uncovered(keys, s, credits)
            if not off:
                continue
            miscredited = [k for k in off if k in credits]
            if miscredited:
                kind, why = "credit-outside-its-procedure", (
                    "; ".join(f"{k} is accepted for \"{' / '.join(credits[k])}\", which this sentence does not mention"
                              for k in miscredited))
            else:
                kind = "new-assertion-unledgered" if REPORTING.search(s) else "new-citation-unaccounted"
                why = "no ledger row and no credit entry"
            findings.append({"kind": kind, "location": f, "cite_key": ",".join(off),
                             "detail": f"new since {a.gate_since}, {why}: {s[:90]}"})
        gate = {"since": a.gate_since, "new_citing_sentences": len(added),
                "credits_file": a.credits, "credits": {k: v for k, v in sorted(credits.items())}}

    hard_kinds = {"snippet-not-in-source", "claim-not-in-manuscript", "key-not-in-claim-sentence",
                  "source-file-missing", "negative-claim-without-fulltext",
                  "new-assertion-unledgered", "new-citation-unaccounted",
                  "credit-outside-its-procedure", "unread-high-risk", "unledgered-negative-claim",
                  "uncited-literature-claim", "named-work-without-cite"}
    hard = [f for f in findings if f["kind"] in hard_kinds and not f.get("prompt")]
    counts = {"found": len(rows), "author": sum(1 for r in rows if reading(r) == "author"),
              "draft": sum(1 for r in rows if reading(r) == "draft")}
    counts["unread"] = counts["found"] - counts["author"] - counts["draft"]
    # Nothing verified is not a pass: an empty ledger over a citing manuscript
    # produces a coverage list and no verification at all.
    # In gate mode the question is what this change added, so a change that
    # added no citation is a legitimate pass even with an empty ledger.
    nothing = not rows and not a.gate_since
    payload = {
        "schema_version": 1,
        "base": str(base),
        "ledger": str(ledger_path),
        "ledgers": [str(p) for p in ledger_paths],
        "also_files": list(a.also_file),
        "citing_sentences": len(sentences),
        "ledger_rows": len(rows),
        "gate": gate,
        "credits_file": a.credits,
        "credited_sentences": sum(1 for f in findings if f["kind"] == "credited"),
        "reading": counts,
        "names": {"named_works": len(names), "cited_keys_without_name": len(unnamed)},
        "findings": findings,
        "hard_finding_count": len(hard),
        "nothing_checked": nothing,
        "limits": {
            "semantic_overreach": "NOT decided here: a claim that says more than its snippet in words the snippet never used passes every check. Measured on a small red-check set, a paired machine judge caught 7 of 8 and missed a dropped 'expected' every time; read the pairs.",
            "coverage": "unledgered-assertion uses a reporting-verb heuristic, so it both misses claims phrased without one and flags some credit lines",
        },
    }
    if a.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        unledgered = sum(1 for f in findings if f["kind"] == "unledgered-assertion")
        print(f"claim ledger: {len(rows)} row(s) against {len(sentences)} citing sentence(s) under {base}")
        print(f"coverage: {unledgered} asserting sentence(s) carry no row, and nothing here checks them")
        print(f"rows: {counts['found']} found, {counts['author']} read by the author, {counts['draft']} read in draft, "
              f"{counts['unread']} not read (found is not read)")
        print(f"names: {len(names)} work(s) named; {len(unnamed)} cited key(s) have no name, so mentions of them "
              f"with no \\cite are not checked")
        if gate:
            print(f"gate: {gate['new_citing_sentences']} citing sentence(s) new since {gate['since']}"
                  f"; {len(gate['credits'])} key(s) accepted as credits")
        for kind in ["new-assertion-unledgered", "new-citation-unaccounted", "credit-outside-its-procedure",
                     "unread-high-risk", "unledgered-negative-claim", "uncited-literature-claim",
                     "named-work-without-cite", "recheck-same-key", "snippet-not-in-source", "claim-not-in-manuscript", "key-not-in-claim-sentence",
                     "source-file-missing", "negative-claim-without-fulltext", "unledgered-assertion",
                     "qualifier-dropped", "unledgered-credit", "credited"]:
            group = [f for f in findings if f["kind"] == kind]
            if not group:
                continue
            prompts = sum(1 for f in group if f.get("prompt"))
            tag = " (prompt, not a finding)" if prompts == len(group) else (f" ({prompts} of them prompts)" if prompts else "")
            print(f"\n{kind}{tag} ({len(group)})")
            for f in group:
                print(f"  {f['location']}\n    {f['detail']}")
        if nothing:
            print("\nNOTHING CHECKED: no citing sentence and no ledger row. This is not a pass.")
        print(f"\nNot decided here: {payload['limits']['semantic_overreach']}")
    if a.pairs:
        # One claim, every snippet it has, in every ledger: judge the claim against all of them.
        grouped = {}
        for p in pairs:
            grouped.setdefault(norm(p["claim"]), []).append(p)
        for group in grouped.values():
            print(f"\nclaim: {group[0]['claim']}  ({len(group)} snippet{'s' * (len(group) > 1)})")
            for p in group:
                meta = " · ".join(x for x in [p["cite_key"], p["level"], p["version"]] if x)
                print(f"  [{meta}] {p['location']}\n    snippet: {p['snippet']}\n    source:  {p['source_file']}"
                      + (f"\n    read:    {p['read']}" if p["read"] else "\n    read:    (not read)"))
    return 1 if hard else (2 if nothing and not a.allow_empty else 0)


if __name__ == "__main__":
    sys.exit(main())
