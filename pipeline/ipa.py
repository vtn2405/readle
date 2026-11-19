"""
IPA bằng code (không LLM) từ CMU Pronouncing Dictionary — giọng Mỹ, ký hiệu kiểu Mỹ
không có dấu dài `ː` (/tɛnd/, /ˈvaɪtəl/, /ˈrɑkət/, /ˈimjuz/; người dùng chốt run #38).
Dùng cho `Token.ipa` và `LexiconEntry.ipa` (contract 1.1, ADR-010).
Trong cụm nhiều từ, từ chức năng đọc nhẹ (`of` → /əv/, `a` → /ə/, `the` → /ðə/).

Từ không có trong từ điển (vd "carotenoids", số) → None; app ẩn dòng IPA.
Giới hạn đã biết: từ đồng tự khác âm ("read", "live") lấy cách đọc đầu tiên của CMUdict.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

_VOWELS = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ",
    "EH": "ɛ", "ER": "ɝ", "EY": "eɪ", "IH": "ɪ", "IY": "i", "OW": "oʊ",
    "OY": "ɔɪ", "UH": "ʊ", "UW": "u",
}
# Dạng yếu của từ chức năng khi đứng trong cụm (CMUdict chỉ cho dạng nhấn, vd "of" /ʌv/).
_WEAK_IN_PHRASE = {"of": "əv", "a": "ə", "an": "ən", "the": "ðə"}
# Nguyên âm không nhấn (stress 0) đọc nhẹ hơn.
_UNSTRESSED = {"AH": "ə", "ER": "ɚ", "IY": "i", "UW": "u"}
_CONSONANTS = {
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h",
    "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ", "P": "p",
    "R": "r", "S": "s", "SH": "ʃ", "T": "t", "TH": "θ", "V": "v", "W": "w",
    "Y": "j", "Z": "z", "ZH": "ʒ",
}
# Phụ âm đầu âm tiết hợp lệ trong tiếng Anh (luật maximal onset để đặt dấu nhấn).
_ONSETS = {tuple(o.split()) for o in [
    "P R", "P L", "B R", "B L", "T R", "D R", "K R", "K L", "G R", "G L",
    "F R", "F L", "TH R", "SH R", "S P", "S T", "S K", "S M", "S N", "S L",
    "S W", "S F", "T W", "D W", "K W", "G W", "TH W", "P Y", "B Y", "F Y",
    "M Y", "K Y", "V Y", "HH Y", "G Y", "S P R", "S P L", "S T R", "S K R",
    "S K W", "S P Y", "S K Y",
]} | {(c,) for c in _CONSONANTS if c != "NG"}

_WORD = re.compile(r"[a-z]+(?:'[a-z]+)?")


_MANUAL_PATH = Path(__file__).parent / "data" / "ipa.json"


@lru_cache(maxsize=1)
def _manual() -> dict[str, str]:
    """IPA viết tay dùng chung (pipeline/data/ipa.json): khóa viết thường → thân IPA không có '/'."""
    if not _MANUAL_PATH.exists():
        return {}
    raw = json.loads(_MANUAL_PATH.read_text("utf-8-sig"))["entries"]
    return {k.lower(): v.strip("/") for k, v in raw.items()}


@lru_cache(maxsize=1)
def _dict() -> dict[str, list[list[str]]]:
    import cmudict
    return cmudict.dict()


def _split(phone: str) -> tuple[str, Optional[int]]:
    if phone[-1].isdigit():
        return phone[:-1], int(phone[-1])
    return phone, None


def arpabet_to_ipa(phones: list[str]) -> str:
    """ARPAbet (có số nhấn) → IPA, đặt ˈ/ˌ ở đầu âm tiết khi từ có ≥ 2 âm tiết."""
    parsed: list[tuple[str, Optional[int]]] = []
    for k, p in enumerate(phones):
        base, stress = _split(p)
        nxt = _split(phones[k + 1]) if k + 1 < len(phones) else None
        if base == "ER" and stress == 0 and nxt and nxt[1] is not None:
            # "moderation" M AA2 D ER0 EY1 …: /r/ thuộc âm tiết sau → ˌmɑdəˈreɪʃən
            parsed += [("AH", 0), ("R", None)]
        else:
            parsed.append((base, stress))
    vowel_idx = [k for k, (_, s) in enumerate(parsed) if s is not None]
    marks: dict[int, str] = {}
    if len(vowel_idx) > 1:
        prev = -1
        for v in vowel_idx:
            cluster = [parsed[k][0] for k in range(prev + 1, v)]
            onset = 0
            if prev >= 0:
                for n in range(len(cluster), 0, -1):
                    if tuple(cluster[-n:]) in _ONSETS:
                        onset = n
                        break
            start = v - onset if prev >= 0 else 0
            stress = parsed[v][1]
            if stress == 1:
                marks[start] = "ˈ"
            elif stress == 2:
                marks[start] = "ˌ"
            prev = v
    out = []
    for k, (base, stress) in enumerate(parsed):
        out.append(marks.get(k, ""))
        if stress is None:
            out.append(_CONSONANTS[base])
        elif stress == 0 and base in _UNSTRESSED:
            out.append(_UNSTRESSED[base])
        else:
            out.append(_VOWELS[base])
    return "".join(out)


def _word_body(word: str) -> Optional[str]:
    """IPA không kèm dấu / cho 1 từ (có thể có gạch nối). None nếu không tra được."""
    w = word.lower().replace("’", "'").strip()
    if not w:
        return None
    if w in _manual():
        return _manual()[w]
    prons = _dict().get(w)
    if prons:
        return arpabet_to_ipa(prons[0])
    parts = w.split("-")
    if len(parts) > 1 and all(_WORD.fullmatch(p) for p in parts):
        return _hyphen_compound(parts)
    return None


# Từ chức năng trong từ ghép gạch nối: không nhấn ("hole-in-the-wall", "up-to-date").
_UNSTRESSED_IN_COMPOUND = {"in", "on", "of", "to", "the", "a", "an", "and", "at", "by", "for", "or"}


def _hyphen_compound(parts: list[str]) -> Optional[str]:
    """Từ ghép gạch nối không có trong CMUdict (run #68). Kiểu giống ipa.json đã duyệt
    ("heavy-lift" → ˈhɛviˌlɪft): nối liền, phần nội dung đầu nhấn chính ˈ, các phần sau nhấn phụ ˌ,
    từ chức năng đọc nhẹ không nhấn ("hole-in-the-wall" → ˈhoʊlɪnðəˌwɔl, "pop-up" → ˈpɑpˌʌp).
    Trước đây nối liền và mất hết dấu nhấn của phần một âm tiết (/pɑpʌp/)."""
    out, first = [], True
    for p in parts:
        if p in _UNSTRESSED_IN_COMPOUND:
            body = _WEAK_IN_PHRASE.get(p) or _word_body(p)
            if not body:
                return None
            out.append(body.replace("ˈ", "").replace("ˌ", ""))
            continue
        body = _word_body(p)
        if not body:
            return None
        if "ˈ" not in body and "ˌ" not in body:   # một âm tiết: tự thêm dấu nhấn
            body = "ˈ" + body
        if not first:                              # phần sau: nhấn chính → nhấn phụ
            body = body.replace("ˈ", "ˌ")
        out.append(body)
        first = False
    return "".join(out)


def word_ipa(word: str) -> Optional[str]:
    """IPA của một từ, dạng "/ˈvaɪtəl/"; None nếu không có trong từ điển."""
    body = _word_body(word)
    return f"/{body}/" if body else None


def phrase_ipa(phrase: str) -> Optional[str]:
    """IPA của cả cụm, các từ cách nhau 1 dấu cách; None nếu có từ không tra được."""
    manual = _manual().get(" ".join(phrase.lower().split()))
    if manual:
        return f"/{manual}/"
    words = phrase.split()
    if len(words) > 1:
        bodies = [_WEAK_IN_PHRASE.get(w.lower()) or _word_body(w) for w in words]
    else:
        bodies = [_word_body(w) for w in words]
    if not words or not all(bodies):
        return None
    return "/" + " ".join(bodies) + "/"


def add_token_ipa(tokens: list[dict]) -> list[dict]:
    """Trả list token mới có trường `ipa` = IPA của **lemma** (khớp chữ hiển thị ở dòng
    từ đơn, tooltip và thẻ đã lưu — đều dùng lemma). Lemma không tra được (spaCy đôi khi
    cho lemma lạ, vd "cookies" → "cooky") thì dùng `text`. None cho dấu câu / từ không tra được."""
    return [{**t, "ipa": (word_ipa(t["lemma"]) or word_ipa(t["text"])) if t["is_word"] else None}
            for t in tokens]
