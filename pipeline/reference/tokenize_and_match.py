"""
Tham chiếu (đã chạy thử) cho bước B3 (tokenize) và B5 (định vị mục từ).

Ý tưởng mượn có ghi nguồn (chỉ ý tưởng, không chép mã):
- Lute v3 (MIT): nối token bằng zero-width space rồi tìm chuỗi có chồng lấn,
  để cụm chỉ khớp đúng ranh giới token (lute/read/render/calculate_textitems.py).
- read-frog (GPL-3, chỉ học ý tưởng): khóa so khớp chuẩn hóa NFC, bỏ ký tự vô hình,
  hạ chữ thường (src/utils/glossary/match-key.ts).
- LinguaCafe (GPL-3, chỉ học ý tưởng): token kèm lemma + POS + chỉ số câu (tools/tokenizer.py).

Vì sao không dùng PhraseMatcher(attr="LEMMA"): lemma của spaCy giữ chữ hoa
("Broccoli" -> "Broccoli") nên khớp theo lemma bị lệch hoa/thường. Ở đây ta tự
chuẩn hóa lemma rồi khớp 2 lượt: theo lemma, nếu trượt thì theo chữ (lowercase).
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import spacy

ZWS = "\u200b"
FN_POS = {"DET", "ADP", "AUX", "CCONJ", "SCONJ", "PART", "PRON"}
_INVISIBLE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")


@lru_cache(maxsize=1)
def get_nlp():
    # Chỉ cần tagger + lemmatizer; tắt NER cho nhanh.
    return spacy.load("en_core_web_sm", disable=["ner"])


def norm(s: str) -> str:
    """Khóa chuẩn hóa: NFC, bỏ ký tự vô hình, gộp khoảng trắng, chữ thường."""
    s = _INVISIBLE.sub("", unicodedata.normalize("NFC", s))
    return re.sub(r"\s+", " ", s).strip().lower()


def tokenize(text: str, with_tags: bool = False) -> list[dict]:
    """Trả về tokens theo contract (chưa có vi). Token khoảng trắng của spaCy được gộp vào ws.
    `with_tags=True` thêm `tag`/`dep` của spaCy (ngoài contract, chỉ dùng trong enrich cho glossary
    bị động, BE-06i); bundle đi qua `ArticleBundle` nên 2 trường này bị bỏ khi ghi file."""
    doc = get_nlp()(text)
    out: list[dict] = []
    for t in doc:
        if t.is_space:
            if out:
                out[-1]["ws"] += t.text + t.whitespace_
            continue
        is_word = not t.is_punct
        tok = {
            "i": len(out),
            "text": t.text,
            "ws": t.whitespace_,
            "lemma": t.lemma_,
            "pos": t.pos_,
            "is_word": is_word,
            "is_fn": is_word and t.pos_ in FN_POS,
            "vi": None,
        }
        if with_tags:
            tok["tag"], tok["dep"] = t.tag_, t.dep_
        out.append(tok)
    return out


def lemma_key(canonical_form: str) -> str:
    """Khóa nhận diện lặp lại qua các bài (cột UNIQUE lexicon_entries.lemma_key)."""
    return " ".join(norm(t.lemma_) for t in get_nlp()(canonical_form) if not t.is_space)


# Chỗ trống sở hữu trong dạng chuẩn ("trace one's roots to", "speak one's mind") khớp đúng
# 1 token tính từ sở hữu trong bài ("its", "their"…). spaCy tách "one's" thành "one" + "'s".
POSSESSIVES = ("my", "your", "his", "her", "its", "our", "their")
_ONES = object()


def _find_all(seq: list[str], pattern: list) -> list[int]:
    """Mọi vị trí bắt đầu (kể cả chồng lấn) của pattern trong seq, đúng ranh giới token.
    Phần tử `_ONES` của pattern khớp một token sở hữu bất kỳ."""
    content = ZWS + ZWS.join(seq) + ZWS
    zws_pos = [k for k, ch in enumerate(content) if ch == ZWS]
    poss = "(?:" + "|".join(POSSESSIVES) + ")"
    needle = re.escape(ZWS) + re.escape(ZWS).join(
        poss if p is _ONES else re.escape(p) for p in pattern) + re.escape(ZWS)
    return [zws_pos.index(m.start()) for m in re.finditer(rf"(?=({needle}))", content)]


def _with_ones(words: list[str]) -> list:
    """["trace", "one", "'s", "root"] → ["trace", _ONES, "root"]."""
    out, k = [], 0
    while k < len(words):
        if words[k] == "one" and k + 1 < len(words) and words[k + 1] in ("'s", "’s"):
            out.append(_ONES)
            k += 2
            continue
        out.append(words[k])
        k += 1
    return out


def locate(tokens: list[dict], canonical_form: str) -> list[tuple[int, int]]:
    """
    Trả về [(token_start, token_end_inclusive), ...]. Rỗng = không định vị được
    -> đưa vào báo cáo lỗi B5 cho người duyệt, KHÔNG đoán.
    """
    pat_doc = [t for t in get_nlp()(canonical_form) if not t.is_space]
    lemma_pat = _with_ones([norm(t.lemma_) for t in pat_doc])
    text_pat = _with_ones([norm(t.text) for t in pat_doc])
    n = len(lemma_pat)
    by_lemma = _find_all([norm(t["lemma"]) for t in tokens], lemma_pat)
    starts = by_lemma or _find_all([norm(t["text"]) for t in tokens], text_pat)
    return [(s, s + n - 1) for s in starts]


def surface(tokens: list[dict], start: int, end: int) -> str:
    """Chuỗi hiển thị của khoảng token (không kèm khoảng trắng cuối)."""
    return "".join(t["text"] + t["ws"] for t in tokens[start:end + 1]).rstrip()


_SENT_END = {".", "!", "?"}
_CLOSERS = {"”", "’", '"', "'", ")", "]", "»"}


def sentence_bounds(tokens: list[dict], start: int, end: int) -> tuple[int, int]:
    """Khoảng token [s, e] của câu chứa [start, end]. Ranh giới = . ! ?; dấu đóng ngoặc/nháy
    ngay sau dấu kết câu (`away.”`) thuộc về câu TRƯỚC, nên câu sau không bắt đầu bằng `”`."""
    s = start
    while s > 0 and tokens[s - 1]["text"] not in _SENT_END:
        if tokens[s - 1]["text"] in _CLOSERS and s - 2 >= 0 and tokens[s - 2]["text"] in _SENT_END:
            break
        s -= 1
    e = end
    while e < len(tokens) - 1 and tokens[e]["text"] not in _SENT_END:
        e += 1
    while e < len(tokens) - 1 and tokens[e]["text"] in _SENT_END | _CLOSERS \
            and tokens[e + 1]["text"] in _CLOSERS and not tokens[e]["ws"]:
        e += 1
    return s, e


def merge_code_tokens(tokens: list[dict]) -> tuple[list[dict], dict[int, int]]:
    """Gộp mã/tên viết liền bằng gạch nối mà spaCy tách ra: `R2` `-` `D2` → `R2-D2`, `3` `-` `D` → `3-D`.
    Chỉ gộp khi mỗi phần là 1-3 ký tự HOA/số và không có khoảng trắng giữa (không đụng `low-fat`,
    `90-minute`). Trả (tokens mới đánh lại `i`, map chỉ số cũ → mới)."""
    def code(t):
        return t["is_word"] and 1 <= len(t["text"]) <= 3 and all(c.isupper() or c.isdigit() for c in t["text"])

    out: list[dict] = []
    remap: dict[int, int] = {}
    k = 0
    while k < len(tokens):
        t = tokens[k]
        j = k
        while (j + 2 < len(tokens) and code(tokens[j]) and not tokens[j]["ws"]
               and tokens[j + 1]["text"] == "-" and not tokens[j + 1]["ws"] and code(tokens[j + 2])):
            j += 2
        if j > k:
            text = "".join(x["text"] for x in tokens[k:j + 1])
            merged = {**t, "text": text, "lemma": text, "pos": "PROPN", "is_fn": False,
                      "ws": tokens[j]["ws"], "i": len(out)}
            for m in range(k, j + 1):
                remap[m] = len(out)
            out.append(merged)
            k = j + 1
            continue
        remap[k] = len(out)
        out.append({**t, "i": len(out)})
        k += 1
    return out, remap


def sentence_cloze(tokens: list[dict], start: int, end: int) -> dict:
    """Cắt câu chứa khoảng token (sentence_bounds) và tách 3 phần cho flashcard."""
    s, e = sentence_bounds(tokens, start, end)
    before = "".join(t["text"] + t["ws"] for t in tokens[s:start])
    after = "".join(t["text"] + t["ws"] for t in tokens[end + 1:e + 1]).rstrip()
    answer = surface(tokens, start, end)
    sep_after = tokens[end]["ws"]
    return {"text_before": before, "answer": answer, "text_after": sep_after + after if after else ""}


EXCERPT_MAX_CHARS = 160


def clip_excerpt(text: str, max_chars: int = EXCERPT_MAX_CHARS) -> str:
    """Gộp khoảng trắng; dài quá `max_chars` thì cắt ở ranh giới từ + "…" (tính cả "…")."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars - 1]
    if " " in cut:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip(" ,;:-–—") + "…"


def article_excerpt(tokens: list[dict], max_chars: int = EXCERPT_MAX_CHARS) -> str | None:
    """Đoạn trích (ADR-024 điểm 2): câu đầu của card đầu, chép nguyên văn từ tokens, không gọi LLM."""
    words = [t["i"] for t in tokens if t["is_word"]]
    if not words:
        return None
    s, e = sentence_bounds(tokens, words[0], words[0])
    return clip_excerpt(surface(tokens, s, e), max_chars) or None


if __name__ == "__main__":
    toks = tokenize("Restaurant meals tend to have more added salt, so eat out in moderation.")
    for form in ["tend to", "in moderation", "play a vital role in"]:
        print(form, "->", locate(toks, form), "| key:", lemma_key(form))
