"""
Từ điển CEFR từ đơn dùng chung (BE-15a, ADR-022).

Nguồn (chép nguyên 2 CSV, ghim commit, xem `pipeline/data/vendor/olp-en-cefrj/SOURCE.md`):
- CEFR-J Vocabulary Profile 1.5 (A1-B2). "The CEFR-J Wordlist Version 1.5. Compiled by
  Yukio Tono, Tokyo University of Foreign Studies."
- Octanove Vocabulary Profile C1/C2 1.0 (CC BY-SA 4.0 — áp cho danh sách suy ra
  `pipeline/data/cefr_lexicon.json`).

Lệnh:
  py -m pipeline.cefr_lexicon build    → pipeline/data/cefr_lexicon.json
  py -m pipeline.cefr_lexicon report   → pipeline/out/cefr_lexicon_report.md

Tra (`lookup_cefr`), ADR-022 điểm 3-5:
  cefr.json (người duyệt, nguồn "human") → (lemma, UPOS) → lemma mọi từ loại (cấp thấp nhất)
  → dạng gốc của token (`form`, chữa lỗi lemma spaCy `according→accord`, `data→datum`) → None.
  Cụm (có dấu cách): chỉ khớp nguyên văn trong cefr.json hoặc mục nhiều từ của CEFR-J/Octanove.
Không dùng trong `enrich.py` lúc này (BE-06g, prompt v3) → 8 bài đã seed không đổi.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import sys
from collections import Counter
from functools import lru_cache
from typing import Optional

from pipeline.reference.tokenize_and_match import norm

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"
VENDOR = DATA / "vendor" / "olp-en-cefrj"
LEXICON_PATH = DATA / "cefr_lexicon.json"
CEFR_DICT_PATH = DATA / "cefr.json"
OUT = ROOT / "out"
REPORT_PATH = OUT / "cefr_lexicon_report.md"

SOURCE_COMMIT = "d4e45b75b38f27b30dfc5c44d8c571aec7e7092f"
# Thứ tự = độ ưu tiên: CEFR-J thắng Octanove ở cùng khóa ("first band wins").
SOURCES = (
    ("cefrj", "cefrj-vocabulary-profile-1.5.csv"),
    ("octanove", "octanove-vocabulary-profile-c1c2-1.0.csv"),
)
CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
_FN_TAIL = {"to", "of"}

# POS của CSV → UPOS của spaCy. Một POS có thể ra nhiều UPOS (spaCy gắn AUX hoặc VERB tùy câu).
POS_TO_UPOS: dict[str, tuple[str, ...]] = {
    "noun": ("NOUN",),
    "verb": ("VERB",),
    "be-verb": ("AUX", "VERB"),
    "do-verb": ("AUX", "VERB"),
    "have-verb": ("AUX", "VERB"),
    "modal auxiliary": ("AUX", "VERB"),
    "adjective": ("ADJ",),
    "adverb": ("ADV",),
    "preposition": ("ADP",),
    "determiner": ("DET",),
    "pronoun": ("PRON",),
    "conjunction": ("CCONJ", "SCONJ"),
    "number": ("NUM",),
    "interjection": ("INTJ",),
    "infinitive-to": ("PART",),
}

# POS tự do của LexiconEntry.pos (bundle) → UPOS, chỉ để tra bảng chênh lệch trong báo cáo.
ENTRY_POS_TO_UPOS = {
    "noun": "NOUN", "verb": "VERB", "adjective": "ADJ", "adverb": "ADV",
    "preposition": "ADP", "determiner": "DET", "pronoun": "PRON", "conjunction": "CCONJ",
    "number": "NUM", "interjection": "INTJ",
}

_NOTE = (
    "Sinh tự động bằng `py -m pipeline.cefr_lexicon build` (BE-15a, ADR-022), không sửa tay. "
    "Nguồn: CEFR-J Vocabulary Profile 1.5 (The CEFR-J Wordlist Version 1.5. Compiled by Yukio Tono, "
    "Tokyo University of Foreign Studies) + Octanove Vocabulary Profile C1/C2 1.0 (CC BY-SA 4.0; "
    "danh sách suy ra này theo cùng giấy phép cho phần từ nguồn octanove). Xem "
    "pipeline/data/vendor/olp-en-cefrj/NOTICE. Muốn đổi cấp một từ: sửa pipeline/data/cefr.json "
    "(người duyệt thắng), không sửa file này."
)


def _lower_level(a: str, b: str) -> str:
    return a if CEFR_ORDER.index(a) <= CEFR_ORDER.index(b) else b


def split_variants(headword: str) -> list[str]:
    """`a.m./A.M./am/AM` → ['a.m.', 'am'] (chuẩn hóa, bỏ trùng, giữ thứ tự)."""
    out: list[str] = []
    for part in headword.split("/"):
        key = norm(part)
        if key and key not in out:
            out.append(key)
    return out


def read_rows(path: pathlib.Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_lexicon(sources: tuple[tuple[str, pathlib.Path], ...]) -> tuple[dict, dict]:
    """Trả (lexicon, log). lexicon đúng định dạng `cefr_lexicon.json`.
    log: {"dropped": [...], "duplicates": [...], "shadowed": [...], "rows": {src: n}}."""
    entries: dict[str, dict] = {}
    multiword: dict[str, dict] = {}
    log = {"dropped": [], "duplicates": [], "shadowed": [], "rows": {}}
    for src, path in sources:
        rows = read_rows(path)
        log["rows"][src] = len(rows)
        mine_e: dict[str, str] = {}
        mine_m: dict[str, str] = {}
        for n, row in enumerate(rows, start=2):  # dòng 1 là tiêu đề
            head = row.get("headword") or ""
            pos = norm(row.get("pos") or "")
            cefr = (row.get("CEFR") or "").strip().upper()
            where = f"{src}:{n} `{head}` pos=`{row.get('pos') or ''}` {cefr}"
            if cefr not in CEFR_ORDER:
                log["dropped"].append((where, "cấp CEFR lạ"))
                continue
            if pos not in POS_TO_UPOS:
                log["dropped"].append((where, "POS lạ/rỗng → không nạp"))
                continue
            for form in split_variants(head):
                if " " in form:
                    targets = [(mine_m, form)]
                else:
                    targets = [(mine_e, f"{form}|{u}") for u in POS_TO_UPOS[pos]]
                for table, key in targets:
                    if key in table:
                        if table[key] != cefr:
                            log["duplicates"].append(
                                (src, key, table[key], cefr, _lower_level(table[key], cefr)))
                        table[key] = _lower_level(table[key], cefr)
                    else:
                        table[key] = cefr
        for mine, out in ((mine_e, entries), (mine_m, multiword)):
            for key, cefr in mine.items():
                if key in out:  # nguồn trước thắng
                    if out[key]["cefr"] != cefr:
                        log["shadowed"].append((key, out[key]["source"], out[key]["cefr"], src, cefr))
                    continue
                out[key] = {"cefr": cefr, "source": src}
    lexicon = {
        "_note": _NOTE,
        "source_commit": SOURCE_COMMIT,
        "entries": dict(sorted(entries.items())),
        "multiword": dict(sorted(multiword.items())),
    }
    return lexicon, log


def default_sources() -> tuple[tuple[str, pathlib.Path], ...]:
    return tuple((src, VENDOR / name) for src, name in SOURCES)


def dump_lexicon(lexicon: dict) -> str:
    """Mỗi mục 1 dòng, khóa sắp xếp → sinh lại giống hệt, diff dễ đọc."""
    lines = ["{",
             f'  "_note": {json.dumps(lexicon["_note"], ensure_ascii=False)},',
             f'  "source_commit": {json.dumps(lexicon["source_commit"])},']
    for i, name in enumerate(("entries", "multiword")):
        items = sorted(lexicon[name].items())
        lines.append(f'  "{name}": {{')
        for j, (k, v) in enumerate(items):
            comma = "," if j < len(items) - 1 else ""
            lines.append(f"    {json.dumps(k, ensure_ascii=False)}: "
                         f"{json.dumps(v, ensure_ascii=False, sort_keys=True)}{comma}")
        lines.append("  }" + ("," if i == 0 else ""))
    lines.append("}")
    return "\n".join(lines) + "\n"


def build(path: pathlib.Path = LEXICON_PATH) -> dict:
    lexicon, log = build_lexicon(default_sources())
    path.write_text(dump_lexicon(lexicon), encoding="utf-8", newline="\n")
    return log


# ── Tra cứu ──

class CefrLookup:
    """Tra CEFR theo ADR-022. `human` = dict lemma_key → {"cefr", ...} (định dạng
    `enrich.load_cefr_dict`), `lexicon` = nội dung `cefr_lexicon.json`."""

    def __init__(self, lexicon: dict, human: Optional[dict] = None):
        self.human = {norm(k): v["cefr"] for k, v in (human or {}).items()}
        # cũng khớp theo dạng viết trong cefr.json (lemma_key của "hands-off" là "hand - off")
        for v in (human or {}).values():
            if v.get("form"):
                self.human.setdefault(norm(v["form"]), v["cefr"])
        self.entries = lexicon["entries"]
        self.multiword = lexicon["multiword"]
        self.by_lemma: dict[str, tuple[str, str]] = {}
        for key, v in self.entries.items():
            lemma = key.rsplit("|", 1)[0]
            cur = self.by_lemma.get(lemma)
            if cur is None or CEFR_ORDER.index(v["cefr"]) < CEFR_ORDER.index(cur[0]):
                self.by_lemma[lemma] = (v["cefr"], v["source"])
        # "according to" chỉ có dạng cụm trong CEFR-J, còn spaCy gắn "according" lemma "accord":
        # dạng gốc là từ đầu của cụm "<từ> to/of" → lấy cấp của cụm (bước cuối, chỉ qua `form`).
        self.fn_heads: dict[str, tuple[str, str]] = {}
        for phrase, v in sorted(self.multiword.items()):
            head, *rest = phrase.split()
            cur = self.fn_heads.get(head)
            if rest and set(rest) <= _FN_TAIL and (
                    cur is None or CEFR_ORDER.index(v["cefr"]) < CEFR_ORDER.index(cur[0])):
                self.fn_heads[head] = (v["cefr"], v["source"])

    def _dict(self, key: str, upos: Optional[str]) -> Optional[tuple[str, str]]:
        if upos:
            hit = self.entries.get(f"{key}|{upos.upper()}")
            if hit:
                return hit["cefr"], hit["source"]
        return self.by_lemma.get(key)

    def __call__(self, lemma: str, upos: Optional[str] = None,
                 form: Optional[str] = None, use_human: bool = True) -> Optional[tuple[str, str]]:
        keys = [k for k in dict.fromkeys([norm(lemma), norm(form or "")]) if k]
        if use_human:
            for k in keys:
                if k in self.human:
                    return self.human[k], "human"
        for k in keys:
            if " " in k:
                hit = self.multiword.get(k)
                if hit:
                    return hit["cefr"], hit["source"]
                continue
            hit = self._dict(k, upos)
            if hit:
                return hit
        f = norm(form or "")
        return self.fn_heads.get(f) if f and " " not in f else None


@lru_cache(maxsize=1)
def default_lookup() -> CefrLookup:
    from pipeline.enrich import load_cefr_dict  # dùng đúng hàm nạp cefr.json của enrich
    lexicon = json.loads(LEXICON_PATH.read_text("utf-8"))
    return CefrLookup(lexicon, load_cefr_dict(CEFR_DICT_PATH))


def lookup_cefr(lemma: str, upos: Optional[str] = None,
                form: Optional[str] = None) -> Optional[tuple[str, str]]:
    """(cefr, source) với source ∈ {"human", "cefrj", "octanove"}; không có → None.
    Không áp `overrides.json` của từng bài (việc của enrich)."""
    return default_lookup()(lemma, upos, form)


# ── Báo cáo ──

def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundles(out_dir: pathlib.Path) -> list[tuple[str, dict, dict]]:
    order = json.loads((out_dir / "processing_order.json").read_text("utf-8"))
    res = []
    for slug in order:
        p = out_dir / slug / "bundle.json"
        if not p.exists():
            continue
        ov_path = out_dir / slug / "overrides.json"
        ov = json.loads(ov_path.read_text("utf-8-sig")) if ov_path.exists() else {}
        res.append((slug, json.loads(p.read_text("utf-8")), ov.get("lexicon") or {}))
    return res


def coverage(bundle: dict, look: CefrLookup) -> tuple[int, int, Counter]:
    """(số token từ tra được, tổng token từ, Counter các lemma trượt)."""
    hit = total = 0
    miss: Counter = Counter()
    for sec in bundle["sections"]:
        for t in sec["tokens"]:
            if not t["is_word"]:
                continue
            total += 1
            if look(t["lemma"], t.get("pos"), t["text"]):
                hit += 1
            else:
                miss[norm(t["lemma"])] += 1
    return hit, total, miss


def discrepancies(bundles, look: CefrLookup) -> tuple[list, list]:
    """Mục từ đơn có cefr_level khác kết quả tra; cụm khớp từ điển mà khác cấp."""
    singles, phrases = [], []
    for slug, b, ov in bundles:
        for e in b["lexicon"]:
            form = e["canonical_form"]
            ov_level = (ov.get(form) or {}).get("cefr_level")
            note = "overrides bài" if ov_level else ""
            if " " in norm(form):
                got = look(e["lemma_key"], form=form)
                if got and got[0] != e["cefr_level"]:
                    phrases.append((slug, form, e["cefr_level"], got[0], got[1], note))
                continue
            upos = ENTRY_POS_TO_UPOS.get(norm(e.get("pos") or ""))
            lemma = e["lemma_key"] if " " not in norm(e["lemma_key"]) else form  # "hand - off"
            got = look(lemma, upos, form)
            if got is None or got[0] != e["cefr_level"]:
                singles.append((slug, form, e.get("pos") or "", e["cefr_level"],
                                got[0] if got else "—", got[1] if got else "không có", note))
    return singles, phrases


def report(out_dir: pathlib.Path = OUT, path: pathlib.Path = REPORT_PATH) -> str:
    from pipeline.enrich import load_cefr_dict
    lexicon, log = build_lexicon(default_sources())
    on_disk = (LEXICON_PATH.read_bytes().decode("utf-8").replace("\r\n", "\n")
               if LEXICON_PATH.exists() else "")
    stale = on_disk != dump_lexicon(lexicon)
    human = load_cefr_dict(CEFR_DICT_PATH)
    look = CefrLookup(lexicon, human)
    L: list[str] = ["# Báo cáo từ điển CEFR (BE-15a, ADR-022)", "",
                    "> Sinh bằng `py -m pipeline.cefr_lexicon report`. Không sửa tay.", ""]
    if stale:
        L += ["**CẢNH BÁO:** `cefr_lexicon.json` trên đĩa khác bản sinh từ CSV → chạy `build`.", ""]

    L += ["## 1. Nguồn", "", "| Nguồn | File | sha256 | Số dòng |", "|---|---|---|---|"]
    for src, p in default_sources():
        L.append(f"| {src} | `{p.name}` | `{sha256(p)[:16]}…` | {log['rows'][src]} |")
    L += ["", f"Commit: `{SOURCE_COMMIT}`.", ""]

    L += ["## 2. Số mục theo nguồn và cấp", "",
          "| Bảng | Nguồn | " + " | ".join(CEFR_ORDER) + " | Tổng |",
          "|---|---|" + "---|" * (len(CEFR_ORDER) + 1)]
    for name in ("entries", "multiword"):
        for src, _ in SOURCES:
            c = Counter(v["cefr"] for v in lexicon[name].values() if v["source"] == src)
            L.append(f"| {name} | {src} | " + " | ".join(str(c.get(x, 0)) for x in CEFR_ORDER)
                     + f" | {sum(c.values())} |")
    lemmas = {k.rsplit('|', 1)[0] for k in lexicon["entries"]}
    L += ["", f"Khóa `lemma|UPOS`: {len(lexicon['entries'])} · lemma khác nhau: {len(lemmas)} · "
          f"mục nhiều từ: {len(lexicon['multiword'])}.", ""]

    L += ["## 3. Dòng bị bỏ", ""]
    L += [f"- {w} — {why}" for w, why in log["dropped"]] or ["- (không có)"]
    L += ["", "## 4. Trùng khóa cùng nguồn (giữ cấp thấp nhất)", ""]
    L += [f"- {src} `{key}`: {a} / {b} → {keep}" for src, key, a, b, keep in log["duplicates"]] \
        or ["- (không có)"]
    L += ["", "## 5. Octanove bị CEFR-J che (cùng khóa, khác cấp; CEFR-J thắng)", "",
          f"{len(log['shadowed'])} khóa.", ""]
    L += [f"- `{key}`: {s1} {c1} ← {s2} {c2}" for key, s1, c1, s2, c2 in log["shadowed"]]

    L += ["", "## 6. Xung đột với `cefr.json` (giữ bản duyệt)", "",
          "| Mục | cefr.json | Từ điển | Nguồn |", "|---|---|---|---|"]
    n_conf = 0
    for v in human.values():
        got = look(v["form"], form=v["form"], use_human=False)
        if got and got[0] != v["cefr"]:
            n_conf += 1
            L.append(f"| {v['form']} | {v['cefr']} ({v['source']}) | {got[0]} | {got[1]} |")
    if not n_conf:
        L.append("| (không có) | | | |")
    in_dict = sum(1 for v in human.values() if look(v["form"], form=v["form"], use_human=False))
    L += ["", f"`cefr.json`: {len(human)} mục, {in_dict} mục có trong từ điển.", ""]

    bundles = _bundles(out_dir)
    L += ["## 7. Độ phủ token theo bài", "",
          "Token từ (`is_word`) tra ra cấp bằng `lookup_cefr(lemma, pos, text)` (gồm cefr.json).", "",
          "| Bài | Tra được | Tổng | % | Lemma trượt nhiều nhất |", "|---|---|---|---|---|"]
    H = T = 0
    for slug, b, _ in bundles:
        h, t, miss = coverage(b, look)
        H, T = H + h, T + t
        top = ", ".join(f"{k} ({n})" for k, n in miss.most_common(8))
        L.append(f"| {slug} | {h} | {t} | {100 * h / t:.1f} | {top} |")
    if T:
        L.append(f"| **Tổng {len(bundles)} bài** | {H} | {T} | {100 * H / T:.1f} | |")

    singles, phrases = discrepancies(bundles, look)
    L += ["", "## 8. Chênh lệch CEFR của mục từ đơn (cần người duyệt)", "",
          "Mục `single_word`/từ đơn trong `bundle.json` có `cefr_level` khác kết quả tra "
          "(hoặc từ điển không có). **Không tự sửa.** Muốn đổi: ghi vào `cefr.json` rồi seed lại "
          "bài (sau BE-06g để không lỡ cache).", "",
          "| Bài | Mục | pos | Hiện tại | Tra được | Nguồn | Ghi chú |", "|---|---|---|---|---|---|---|"]
    L += [f"| {' | '.join(r)} |" for r in singles] or ["| (không có) | | | | | | |"]
    L += ["", "## 9. Cụm khớp nguyên văn từ điển nhưng khác cấp", "",
          "| Bài | Cụm | Hiện tại | Tra được | Nguồn | Ghi chú |", "|---|---|---|---|---|---|"]
    L += [f"| {' | '.join(r)} |" for r in phrases] or ["| (không có) | | | | | |"]
    text = "\n".join(L) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return text


def main() -> None:
    ap = argparse.ArgumentParser(prog="pipeline.cefr_lexicon", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="CSV → pipeline/data/cefr_lexicon.json")
    sub.add_parser("report", help="→ pipeline/out/cefr_lexicon_report.md")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.cmd == "build":
        log = build()
        print(f"OK {LEXICON_PATH.relative_to(ROOT.parent)} · bỏ {len(log['dropped'])} dòng · "
              f"trùng {len(log['duplicates'])} · Octanove bị che {len(log['shadowed'])}")
    else:
        report()
        print(f"OK {REPORT_PATH.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
