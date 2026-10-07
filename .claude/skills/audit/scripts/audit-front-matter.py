#!/usr/bin/env python3
"""What the title and the abstract leave a reader to guess.

    python3 audit-front-matter.py [--root DIR] [--venue-corpus DIR] [--json] FILE...

Reads each FILE and every file it pulls in with \\input, \\include or \\subfile (relative to --root, ".tex" added when
missing), finds \\title (the full title, not the short form in [...]) and the abstract (\\begin{abstract} ...
\\end{abstract}), and reports two things that no sentence-level check sees:

- title-word-missing-from-abstract: a content word of the title that no word of the abstract shares. On one
  manuscript the abstract was rewritten three times and lost every word of the title's main clause, and nothing
  reported it. A word counts as present when the abstract has it, its plural, or a word that starts with its first
  max(6, n-3) letters (retrieval: retrieved); a synonym does not count, so a word the abstract says differently is
  still listed, and is the author's to keep or change.
- coined-name-undefined-in-abstract: a name the draft coins, used in the abstract before the abstract says what it
  is. A name is coined when it has a capital after its first letter (GaugeBench, Flood-Log) and the draft says we
  made it ("we build/introduce/present/release/... NAME", "we call it NAME") or calls it ours ("our <noun>, NAME",
  "NAME, our ...", "NAME is our ..."). Where it first appears in the abstract, that sentence must say we made it,
  describe it ("NAME, a ...", "NAME (a ...", "NAME is a ...", "a <noun phrase>, NAME", or the same with "our" and
  at least two words: "NAME is our river record", "our record of tidal gauges, NAME"), open a
  relative clause on it ("NAME, whose ..."), or follow a sentence that says we made something. "our record,
  NAME" does not: "our" and one noun tell the reader whose the name is, not what it is. On one manuscript the
  abstract's first use of the benchmark's name was of that form, inside a sentence about its first evaluation, and
  the definition had been cut to fit the word limit.

It also counts the abstract's words (abstract_words). With --venue-corpus, the abstracts of the venue's papers are read
from that directory (.pdf through pdftotext, .txt and .md as they are, .tex from its abstract environment): the text
between a line that starts with "Abstract" and the first numbered section heading ("1 Introduction", "1. INTRODUCTION",
"I. INTRODUCTION", or a "1" on its own line before "Introduction"), cut short at a Keywords, Index Terms, CCS Concepts
or ACM Reference Format line. A file with no such heading, no numbered section after it, or a stretch outside
30-600 words is skipped and listed with the reason. With at least 5 abstracts read, the report gives the draft's
percentile among them (the share of venue abstracts shorter, ties counted half), and above the 75th percentile adds:

- abstract-longer-than-venue (low): a hint that the abstract is longer than most of the venue's, worth a look.

A draft with no \\title or no abstract is not an issue: the report says which it did not find (abstract_found,
title_found) and checks nothing that needs it.

Exit: 0 no issue; 1 at least one; 2 nothing read (no FILE could be read).
"""
import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
import unicodedata
from pathlib import Path

INPUT = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")
COMMENT = re.compile(r"(?<!\\)%.*")
TITLE = re.compile(r"\\title\s*(?:\[[^\]]*\])?\s*\{")
ABSTRACT = re.compile(r"\\begin\s*\{abstract\}(.*?)\\end\s*\{abstract\}", re.S)
DROP = re.compile(r"\\(?:[A-Za-z]*[Cc]ite[A-Za-z]*|ref|cref|Cref|autoref|eqref|pageref|label|nameref|url|"
                  r"footnote|thanks|Description)\*?(?:\s*\[[^\]]*\]){0,2}\s*\{[^{}]*\}")
ACCENT = re.compile(r"\\['\"`^~=.uvHckb]\s*\{?([A-Za-z])\}?")
COMMAND = re.compile(r"\\[A-Za-z]+\*?|\\.")
MATH = re.compile(r"\$[^$]*\$|\\\(.*?\\\)")
STOPWORDS = set("""a an the and or nor but of in on at to for from by with without into onto over under between among
across through during before after above below about against within beyond toward towards via per than as is are was
were be been being am do does did has have had can could may might must shall should will would not no yes this that
these those it its their our we us you your they them he she his her i my me what when where which who whom whose why
how whether if then so such both either neither each every any all some more most less least other another same own
very only also just even still yet again further once here there up down out off new novel using use case study
studies approach approaches method methods toward towards versus vs""".split())
WORD = re.compile(r"[A-Za-z][A-Za-z']*")
# a name with a capital after its first letter, as a word of its own: GaugeBench, Flood-Log
NAME = re.compile(r"(?<![\w-])([A-Za-z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*|[A-Z][a-z0-9]+(?:-[A-Za-z0-9]+)*-"
                  r"[A-Z][A-Za-z0-9]*)(?![\w-])")
MADE = r"(?:build|built|builds|introduce[sd]?|present(?:s|ed)?|release[sd]?|construct(?:s|ed)?|create[sd]?|" \
       r"propose[sd]?|curate[sd]?|develop(?:s|ed)?|design(?:s|ed)?|assemble[sd]?|collect(?:s|ed)?|compile[sd]?|" \
       r"call(?:s|ed)?|name[sd]?|term(?:s|ed)?|dub(?:s|bed)?)"
# words that, between the verb and the name, say the verb is about something else: we build on X, we present results
# on X, we present an evaluation of X
ABOUT = {"on", "upon", "in", "to", "from", "with", "by", "at", "against", "using", "via", "over", "under", "into"}
# a definite or possessive word inside "a ... , NAME" makes NAME the apposition of that later noun, not of the
# indefinite one: "a first run of our record, NAME" does not say what NAME is
DEFINITE = {"our", "the", "its", "their", "this", "these", "those", "that", "his", "her", "my", "your"}
# after the name, what may follow when the name is the thing made rather than a word describing another noun
# (we collected NAME scores)
AFTER_MADE = r"(?=\s*(?:[,.;:()]|$|(?:and|or|to|which|that|for|with|in|on|as|of|from|by|at|is|was|are|were)\b))"
ABBREV = re.compile(r"\b(e\.g|i\.e|et al|cf|vs|Fig|Figs|Eq|Eqs|Sec|Secs|No|approx|resp|ca)\.", re.I)
SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'`])")


# a venue paper's abstract: from a line that starts with "Abstract" to the first numbered section heading
ABSTRACT_HEAD = re.compile(r"(?im)^[ \t#]*abstract\b[ \t]*[.:\u2014\u2013-]?[ \t]*")
SECTION_ONE = re.compile(r"(?m)^[ \t#]*(?:1\.?|I\.)(?:[ \t]+[A-Z][A-Za-z]|[ \t]*\n[ \t#]*(?i:introduction)\b)")
ABSTRACT_STOP = re.compile(r"(?im)^[ \t#]*(?:keywords|key words|index terms|ccs concepts|acm reference format)\b")
VENUE_SUFFIXES = {".pdf", ".txt", ".md", ".tex"}
ABSTRACT_WORDS = (30, 600)  # a stretch outside this is not an abstract that was read right
MIN_VENUE = 5  # fewer abstracts than this give no percentile
LONG_AT = 75  # above this percentile the abstract is longer than most of the venue's


def word_count(text):
    """Words of plain text: whitespace-separated tokens holding a letter or a digit. The draft's abstract and the
    venue's are counted by this one rule."""
    return sum(1 for w in text.split() if re.search(r"[A-Za-z0-9]", w))


def venue_abstract(path):
    """(word count, None) for a venue paper's abstract, or (None, why it was skipped)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        if not shutil.which("pdftotext"):
            return None, "pdftotext not on PATH"
        try:
            text = subprocess.run(["pdftotext", "-q", str(path), "-"], capture_output=True, text=True,
                                  timeout=120).stdout
        except (OSError, subprocess.SubprocessError) as e:
            return None, f"pdftotext failed: {type(e).__name__}"
        text = re.sub(r"-\n", "", text or "")
    else:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return None, f"unreadable: {e.strerror or e}"
    if suffix == ".tex":
        m = ABSTRACT.search(COMMENT.sub("", text))
        if not m:
            return None, "no abstract environment"
        body = plain(m.group(1))
    else:
        head = ABSTRACT_HEAD.search(text)
        if not head:
            return None, "no Abstract heading"
        end = SECTION_ONE.search(text, head.end())
        if not end:
            return None, "no numbered section heading after Abstract"
        stop = ABSTRACT_STOP.search(text, head.end(), end.start())
        body = text[head.end():stop.start() if stop else end.start()]
    n = word_count(body)
    if not ABSTRACT_WORDS[0] <= n <= ABSTRACT_WORDS[1]:
        return None, f"{n} words between the headings, not read as an abstract"
    return n, None


def venue_abstracts(corpus, draft_words):
    """What the venue corpus says about the draft abstract's length."""
    d = Path(corpus).expanduser()
    files = sorted(p for p in d.rglob("*") if p.is_file() and p.suffix.lower() in VENUE_SUFFIXES) if d.is_dir() else []
    parsed, skipped = {}, []
    for p in files:
        n, why = venue_abstract(p)
        if n is None:
            skipped.append({"file": str(p.relative_to(d)), "reason": why})
        else:
            parsed[str(p.relative_to(d))] = n
    counts = sorted(parsed.values())
    out = {"dir": str(d), "found": d.is_dir(), "files": len(files), "parsed": len(counts), "parsed_files": parsed,
           "skipped": skipped, "median": None, "p75": None, "percentile": None}
    if len(counts) >= MIN_VENUE:
        below = sum(1 for c in counts if c < draft_words)
        equal = sum(1 for c in counts if c == draft_words)
        out["median"] = statistics.median(counts)
        out["p75"] = statistics.quantiles(counts, n=4, method="inclusive")[2]
        out["percentile"] = int(round(100 * (below + 0.5 * equal) / len(counts)))
    return out


def read_tree(files, root):
    """[(path, text without comments)] for the files given and everything they input, each file once."""
    out, seen, unresolved = [], set(), []
    stack = [Path(f) for f in reversed(files)]
    while stack:
        p = stack.pop()
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        try:
            text = COMMENT.sub("", p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            unresolved.append(str(p))
            continue
        out.append((p, text))
        for m in reversed(list(INPUT.finditer(text))):
            q = Path(root) / m.group(1).strip()
            if not q.suffix:
                q = q.with_suffix(".tex")
            if q.exists():
                stack.append(q)
            else:
                unresolved.append(m.group(1).strip())
    return out, unresolved


def closing(text, start):
    """Index of the brace closing the group that opens just before start."""
    depth = 1
    for i in range(start, len(text)):
        c = text[i]
        if c == "{" and text[i - 1] != "\\":
            depth += 1
        elif c == "}" and text[i - 1] != "\\":
            depth -= 1
            if depth == 0:
                return i
    return len(text)


def plain(tex):
    """The words of a LaTeX fragment: citations, references and math out, commands dropped, their arguments kept."""
    t = MATH.sub(" ", DROP.sub(" ", tex))
    t = ACCENT.sub(r"\1", t)
    t = t.replace("~", " ").replace("\\\\", " ")
    t = re.sub(r"\\[,;:! ]", " ", t)
    t = COMMAND.sub(lambda m: "" if m.group(0)[1:2].isalpha() else m.group(0)[1:], t)
    t = t.replace("{", "").replace("}", "")
    t = re.sub(r"-{2,}", " ", t)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.split())


def sentences(text):
    t = ABBREV.sub(lambda m: m.group(1).replace(".", "\u2024") + "\u2024", text)
    return [s.replace("\u2024", ".") for s in SPLIT.split(t) if s.strip()]


def stem(w):
    w = w.lower().replace("'", "")
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("ches", "shes", "sses", "xes", "zes")):
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is")) and len(w) > 3:
        return w[:-1]
    return w


def present(word, abstract_stems):
    s = stem(word)
    need = s if len(s) <= 6 else s[:max(6, len(s) - 3)]
    return any(a.startswith(need) for a in abstract_stems)


def title_words(title):
    out, seen = [], set()
    for w in WORD.findall(title.replace("-", " ")):
        if w.lower() in STOPWORDS or len(w) < 3 or stem(w) in seen:
            continue
        seen.add(stem(w))
        out.append(w)
    return out


def _between_ok(words, also=()):
    return not any(w.lower() in ABOUT or w.lower() in also for w in words)


def made_by_us(sentence, name):
    """The sentence says we made NAME: we <made-verb> [a/an/the] [up to six words] [,] [called|named] NAME."""
    for m in re.finditer(r"\b[Ww]e\s+(?:[a-z]+ly\s+)?" + MADE + r"\b(.{0,120}?)(?<![\w-])" + re.escape(name)
                         + r"(?![\w-])" + AFTER_MADE, sentence):
        gap = m.group(1)
        words = WORD.findall(gap)
        if len(words) <= 7 and _between_ok(words, {"of"}) and not re.search(r"[.;:]", gap):
            return True
    return False


def ours(sentence, name):
    """The sentence calls NAME ours: we made it, or "our <noun>, NAME", or "NAME (ours)"."""
    if made_by_us(sentence, name):
        return True
    n = re.escape(name)
    return bool(re.search(r"\b[Oo]ur\s+(?:[\w-]+\s+){0,3}?[\w-]+,?\s+" + n + r"(?![\w-])", sentence)
                or re.search(r"(?<![\w-])" + n + r"(?![\w-])\s*(?:,\s*|\s+(?:is|was)\s+)our\b", sentence)
                or re.search(n + r"\s*\(ours\)", sentence))


def described(sentence, name):
    """The sentence says what NAME is: we made it, an indefinite description beside it, or "NAME is a ..."."""
    if made_by_us(sentence, name):
        return True
    n = re.escape(name)
    # "our" says whose; it describes only with more than the noun after it: "our river record", "our record of
    # 14 gauges", not "our record,"
    if re.search(r"(?<![\w-])" + n + r"(?![\w-])\s*(?:,\s*|\(\s*|\s+(?:is|was)\s+|,\s*which\s+is\s+)"
                 r"(?:(?:a|an)\s|our\s+[\w-]+\s+[\w-]+)", sentence):
        return True
    if re.search(r"(?<![\w-])" + n + r"(?![\w-])\s*,?\s*(?:which|whose)\s", sentence):
        return True
    if re.search(r"\b[Oo]ur\s+(?:[\w-]+\s+){1,7}?[\w-]+,?\s+" + n + r"(?![\w-])", sentence):
        return True
    for m in re.finditer(r"\b(?:[Aa]|[Aa]n)\s+((?:[\w-]+\s+){0,7}?[\w-]+),?\s+(?:(?:called|named|dubbed)\s+)?"
                         + n + r"(?![\w-])", sentence):
        if _between_ok(WORD.findall(m.group(1)), DEFINITE):
            return True
    return False


def says_we_made_something(sentence):
    return bool(re.search(r"\b[Ww]e\s+(?:[a-z]+ly\s+)?" + MADE + r"\s+(?:a|an|the|our|one|two|three)\b", sentence))


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def _num(x):
    return f"{x:g}" if isinstance(x, float) else str(x)


def length_zh(words, venue):
    """The abstract-length part of the loop's line."""
    if words is None:
        return None
    out = f"摘要 {words} 词"
    if venue is None:
        return out
    if not venue["found"]:
        return out + f"，刊物语料目录不存在（{venue['dir']}）"
    if venue["percentile"] is None:
        return out + f"，刊物摘要只读出 {venue['parsed']} 篇（跳过 {len(venue['skipped'])}），不给百分位"
    return (out + f"，在刊物 {venue['parsed']} 篇摘要里第 {venue['percentile']} 百分位（中位 {_num(venue['median'])}"
            + (f"，跳过 {len(venue['skipped'])} 篇" if venue["skipped"] else "") + "）"
            + ("，偏长" if venue["percentile"] > LONG_AT else ""))


def summary_zh(title_found, abstract_found, issues, coined, length=None):
    """The loop's one line for this check."""
    if not abstract_found:
        return "没找到标题和摘要，没查" if not title_found else "没找到摘要，没查"
    lost = [i["word"] for i in issues if i["kind"] == "title-word-missing-from-abstract"]
    odd = [i["name"] for i in issues if i["kind"] == "coined-name-undefined-in-abstract"]
    if not title_found:
        parts = ["没找到标题，标题词没查"]
    else:
        parts = [f"标题词摘要里没有 {len(lost)}（{'、'.join(lost)}）" if lost else "标题词都在摘要里"]
    if odd:
        parts.append(f"自造名首现没说是什么 {len(odd)}（{'、'.join(odd)}）")
    else:
        parts.append(f"自造名 {len(coined)} 个首现都说了是什么" if coined else "摘要里没有自造名")
    if length:
        parts.append(length)
    return "；".join(parts)


def main():
    ap = argparse.ArgumentParser(description="Title words the abstract lost; coined names it uses before saying what "
                                             "they are.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--venue-corpus", help="the venue's papers (.pdf, .txt, .md, .tex): the abstract's length is placed "
                                           "among theirs")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    files, unresolved = read_tree(a.files, a.root)
    if not files:
        sys.stderr.write("audit-front-matter: none of the files given could be read\n")
        return 2
    title = title_at = abstract = abstract_at = None
    for path, text in files:
        m = TITLE.search(text)
        if m and title is None:
            title, title_at = text[m.end():closing(text, m.end())], f"{path}:{line_of(text, m.start())}"
        m = ABSTRACT.search(text)
        if m and abstract is None:
            abstract, abstract_at = m.group(1), f"{path}:{line_of(text, m.start())}"
    issues = []
    words = []
    if title is not None and abstract is not None:
        abstract_stems = [stem(w) for w in WORD.findall(plain(abstract).replace("-", " "))]
        title_text = plain(title)
        words = title_words(title_text)
        for w in words:
            if not present(w, abstract_stems):
                issues.append({"kind": "title-word-missing-from-abstract", "severity": "medium", "word": w,
                               "title": title_text, "location": title_at, "abstract": abstract_at,
                               "message": f"\"{w}\" is in the title and no word of the abstract shares it (a synonym "
                                          "is not counted; keep it if the abstract says it another way)."})
    coined = []
    if abstract is not None:
        body = [s for _, text in files for s in sentences(plain(ABSTRACT.sub(" ", text)))]
        abs_sents = sentences(plain(abstract))
        names = []
        for s in abs_sents:
            for m in NAME.finditer(s):
                if m.group(1) not in names:
                    names.append(m.group(1))
        for name in names:
            # an all-capital acronym is left out: "we collected GDB scores" reads as making it far too often
            if not any(c.islower() for c in name) or not any(ours(s, name) for s in body + abs_sents):
                continue
            coined.append(name)
            i = next(i for i, s in enumerate(abs_sents) if re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", s))
            first = abs_sents[i]
            if described(first, name) or (i > 0 and says_we_made_something(abs_sents[i - 1])):
                continue
            issues.append({"kind": "coined-name-undefined-in-abstract", "severity": "medium", "name": name,
                           "sentence": first, "location": abstract_at,
                           "message": f"The abstract first uses {name} without saying what it is or that we made "
                                      "it; a reader meets the name before its meaning."})
    n_words = word_count(plain(abstract)) if abstract is not None else None
    venue = venue_abstracts(a.venue_corpus, n_words) if a.venue_corpus and n_words is not None else None
    if venue and venue["percentile"] is not None and venue["percentile"] > LONG_AT:
        issues.append({"kind": "abstract-longer-than-venue", "severity": "low", "words": n_words,
                       "percentile": venue["percentile"], "location": abstract_at,
                       "message": f"The abstract has {n_words} words, longer than about {venue['percentile']}% of the "
                                  f"{venue['parsed']} venue abstracts read (median {_num(venue['median'])}, 75th "
                                  f"percentile {_num(venue['p75'])}). Worth a look: does the reader need every "
                                  "sentence before the introduction?"})
    payload = {"schema_version": 1,
               "summary_zh": summary_zh(title is not None, abstract is not None, issues, coined,
                                        length_zh(n_words, venue)),
               "title_found": title is not None, "abstract_found": abstract is not None,
               "abstract_words": n_words, "venue_abstracts": venue,
               "title_words": words, "coined_names": coined, "files_read": [str(p) for p, _ in files],
               "unresolved_inputs": sorted(set(unresolved)), "issues": issues, "issue_count": len(issues)}
    if a.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for i in issues:
            print(f"{i['location']}: {i['kind']}: {i.get('word') or i.get('name')}")
        print(f"read {len(files)} file(s); title {'found' if title is not None else 'not found'}, abstract "
              f"{'found' if abstract is not None else 'not found'}"
              + (f" ({n_words} words)" if n_words is not None else "")
              + (f", venue percentile {venue['percentile']} of {venue['parsed']} read, {len(venue['skipped'])} skipped"
                 if venue else "") + f"; {len(issues)} issue(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
