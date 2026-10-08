#!/usr/bin/env python3
"""Paragraph openers: which paragraphs open on figures rather than on plain words.

A reader meets each paragraph through its first sentence. This check lists the paragraphs whose first sentence
carries a number or a formula, or opens on a table or a figure, so that a person can decide whether each should
lead with the phenomenon, the problem or the point in plain words and bring the numbers after it.

Where it comes from: in one journal revision the author rejected an abstract and an introduction that led with
figures, and in the target venue most papers of the same genre stated their findings in words (the evidence stays
with the private workspace). Every sentence-level check had passed that draft.

It does not judge. A paragraph whose content is numbers (dataset statistics, a task definition, a formula, a list of
models) rightly opens with them. The count is a pointer for reading, not a score, and the loop reports it as
findings, not as a failure.

Reads chapters/*.md as prose-view.py writes them: inline math is shown as MATH, and a reference leaves only its word
("Table", "Figure"). Headings, tables, list items and code blocks are skipped.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional

# A period after one of these does not end the sentence.
ABBREV = re.compile(r"(?:\b(?:e\.g|i\.e|et al|cf|vs|approx|Fig|Tab|Eq|Sec|No|Nos)|\b[A-Z])\.$")
SENTENCE_END = re.compile(r"[.!?](?=\s+[A-Z\"'(\[]|\s*$)")
MATH = re.compile(r"\bMATH\b")
# A figure: 7, 2,340, 12.5, 12.5%, 3.2 times. Not part of a name (Recall@10, COVID-19, Llama-3-8B, GPT-4o).
NUMBER = re.compile(r"(?<![\w@./-])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s*(?:%|percent\b|per cent\b|times\b))?(?![\w/-])")
YEAR = re.compile(r"^(?:1[5-9]|20)\d\d$")
# A number after one of these points somewhere; it is not data.
POINTER = re.compile(r"\b(?:Section|Sections|Sec\.|Chapter|Chapters|Appendix|Step|Steps|Rule|Rules|RQ|Part|Phase|Stage|"
                     r"Table|Tables|Figure|Figures|Fig\.|Eq\.|Equation|Line|Lines|Page|Pages|p\.|pp\.)\s*$")
FLOAT = re.compile(r"^\W*(?:(?:As\s+)?(?:shown|seen|reported|listed|given|summarised|summarized)\s+in\s+|In\s+|See\s+)?"
                   r"(?:the\s+)?(?:supplementary\s+)?(?:Table|Figure|Fig\.|Tab\.|Equation|Eq\.)(?=\W|$)")
SKIP_BLOCK = re.compile(r"^(?:#|\||```|[-*+]\s|\d+[.)]\s|>)")


def chapter_files(base_dir: Path) -> Iterable[Path]:
    root = base_dir / "chapters"
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*.md") if p.is_file())


def paragraphs(text: str) -> List[dict]:
    out: List[dict] = []
    pos = 0
    for block in re.split(r"(\n\s*\n)", text):
        line = text.count("\n", 0, pos) + 1
        pos += len(block)
        raw = block.strip()
        if not raw or SKIP_BLOCK.match(raw):
            continue
        out.append({"line": line, "text": " ".join(raw.split())})
    return out


def first_sentence(text: str) -> str:
    for m in SENTENCE_END.finditer(text):
        head = text[:m.end()]
        if ABBREV.search(head):
            continue
        return head
    return text


def figures(sentence: str) -> List[str]:
    # Recall@$K$ is shown as "Recall@ MATH": a metric's name, not a figure.
    found = ["MATH" for m in MATH.finditer(sentence) if not re.search(r"@\s*$", sentence[:m.start()])]
    for m in NUMBER.finditer(sentence):
        token = m.group(0).strip()
        bare = token.rstrip("%").replace(",", "").split()[0]
        if YEAR.match(bare):
            continue
        before = sentence[:m.start()]
        if POINTER.search(before):
            continue
        if before.endswith("(") and sentence[m.end():m.end() + 1] == ")":
            continue  # a list marker such as (1)
        if re.fullmatch(r"\d{1,2}", token) and re.search(r"\b[A-Z][A-Za-z]*[A-Z][A-Za-z]*\s$", before):
            continue  # a version in a model's name, as in "BLIP 2"
        found.append(token)
    return found


def audit_file(path: Path, base_dir: Path) -> dict:
    paras = paragraphs(path.read_text(encoding="utf-8"))
    issues: List[dict] = []
    for i, para in enumerate(paras, 1):
        sent = first_sentence(para["text"])
        loc = "{}:{}".format(path.relative_to(base_dir), para["line"])
        kind: Optional[str] = None
        detail = ""
        if FLOAT.match(sent):
            kind, detail = "float-opener", "opens on a table, figure or equation"
        else:
            figs = figures(sent)
            if figs:
                kind, detail = "number-opener", "first sentence carries " + ", ".join(figs[:4])
        if kind:
            issues.append({
                "kind": kind,
                "severity": "low",
                "location": loc,
                "paragraph": i,
                "chapter_first_paragraph": i == 1,
                "sentence": sent[:240],
                "message": detail + "; consider leading with the point in plain words and bringing the numbers after.",
            })
    return {"file": str(path.relative_to(base_dir)), "paragraphs": len(paras), "issues": issues}


def summary_zh(total: int, per_file: List[dict], issues: List[dict]) -> str:
    nums = sum(1 for x in issues if x["kind"] == "number-opener")
    floats = sum(1 for x in issues if x["kind"] == "float-opener")
    text = "{} 段里，首句带数字或公式 {} 段、以图表开头 {} 段（只作提示：数据本身就是内容的段落不算问题）".format(total, nums, floats)
    firsts = [x["location"] for x in issues if x["chapter_first_paragraph"]]
    if firsts:
        text += "；章首段 {} 处：{}".format(len(firsts), "、".join(firsts[:4]))
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="List paragraphs whose first sentence leads with figures.")
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--json", action="store_true", dest="emit_json")
    args = parser.parse_args()
    base_dir = Path(args.base_dir)
    if not base_dir.is_dir():
        sys.stderr.write("error: --base-dir is not a directory\n")
        return 2
    files = list(chapter_files(base_dir))
    per_file = [audit_file(p, base_dir) for p in files]
    issues = [x for f in per_file for x in f["issues"]]
    total = sum(f["paragraphs"] for f in per_file)
    payload = {
        "schema_version": 1,
        "files_scanned": len(files),
        "chapters_dir_present": (base_dir / "chapters").is_dir(),
        "nothing_checked": not files or total == 0,
        "paragraphs": total,
        "files": [{"file": f["file"], "paragraphs": f["paragraphs"], "flagged": len(f["issues"])} for f in per_file],
        "issues": issues,
        "issue_count": len(issues),
        "summary_zh": summary_zh(total, per_file, issues),
    }
    if args.emit_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for issue in issues:
            print("{location}: {kind}: {sentence}".format(**issue))
        print(payload["summary_zh"])
    if not files or total == 0:
        sys.stderr.write("nothing checked: no paragraphs in chapters/*.md under {}\n".format(base_dir))
        return 2
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
