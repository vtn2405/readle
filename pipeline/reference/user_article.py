"""
Bản tham chiếu cho bài người dùng tự tải (ADR-021, bản nháp Contract 1.5 — CHƯA ÁP DỤNG).

App Flutter sẽ chuyển các hàm thuần trong file này sang Dart (FE-16). Fixture
`fixtures/user_article_sample.json` được sinh bằng chính các hàm này, nên bản Dart đúng
khi tách cùng chữ ra cùng tokens / cards như fixture.

Không dùng spaCy ở đây: app không có spaCy. Lemma, IPA, is_fn đến từ bảng `dict_entries`
(BE-15), được điền vào token sau bước tách bằng `apply_dict`.

Các hằng số và luật được mô tả trong docs/CONTRACTS.md mục 6 (bản nháp 1.5).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Callable, Literal, Optional

from pydantic import BaseModel, Field, model_validator

DRAFT_CONTRACT_VERSION = "1.5"

# ── Chuẩn hóa + tách đoạn ──────────────────────────────────────
_INVISIBLE = re.compile(r"[​-‏⁠﻿]")
_PARA_SPLIT = re.compile(r"\n[ \t ]*\n")
_SPACES = re.compile(r"\s+")


def normalize_text(raw: str) -> str:
    """NFC, bỏ ký tự vô hình, NBSP → space, xuống dòng chuẩn `\\n`."""
    s = unicodedata.normalize("NFC", raw)
    s = _INVISIBLE.sub("", s).replace(" ", " ")
    return s.replace("\r\n", "\n").replace("\r", "\n")


def split_paragraphs(raw: str) -> list[str]:
    """Đoạn = phần cách nhau bởi ≥ 1 dòng trống. Trong đoạn, mọi khoảng trắng (kể cả
    xuống dòng đơn) gộp thành 1 dấu cách. Bỏ đoạn rỗng."""
    out = []
    for p in _PARA_SPLIT.split(normalize_text(raw)):
        p = _SPACES.sub(" ", p).strip()
        if p:
            out.append(p)
    return out


# ── Tách token ────────────────────────────────────────────────
# Dart tương đương (RegExp(..., unicode: true)):
#   L  = \p{L}            AN = [\p{L}\p{Nd}]          D = \p{Nd}
#   NUM  = D+(?:[.,]D+)+
#   WORD = AN+(?:['’]L+)*(?:-AN+(?:['’]L+)*)*
#   TOKEN = NUM | WORD | \S
_L = r"[^\W\d_]"
_AN = r"[^\W_]"
_NUM = r"\d+(?:[.,]\d+)+"
_WORD = rf"{_AN}+(?:['’]{_L}+)*(?:-{_AN}+(?:['’]{_L}+)*)*"
_TOKEN = re.compile(rf"{_NUM}|{_WORD}|\S")
_HAS_ALNUM = re.compile(_AN)
# Số thuần (Dart: ^\p{Nd}+(?:[.,]\p{Nd}+)*$): chạm được như bài đã duyệt, nhưng tooltip chỉ
# hiện con số + loa, không tra dict_entries / lookup, không có nút Lưu. "1990s", "90-minute"
# không phải số thuần → đi như từ thường.
_PURE_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def is_pure_number(text: str) -> bool:
    return bool(_PURE_NUMBER.fullmatch(text))


def tokenize_paragraph(paragraph: str) -> list[dict]:
    """Tách 1 đoạn (đã qua `split_paragraphs`). `ws` = khoảng trắng tới token kế tiếp;
    token cuối đoạn có `ws = ""` (người gọi tự nối đoạn)."""
    toks: list[dict] = []
    matches = list(_TOKEN.finditer(paragraph))
    for k, m in enumerate(matches):
        nxt = matches[k + 1].start() if k + 1 < len(matches) else m.end()
        text = m.group()
        is_word = bool(_HAS_ALNUM.search(text))  # có chữ cái hoặc chữ số; dấu câu → không chạm được
        toks.append({
            "i": 0,  # đánh lại khi ghép card
            "text": text,
            "ws": paragraph[m.end():nxt],
            "lemma": text.lower(),
            "pos": None,
            "is_word": is_word,
            "is_fn": False,
            "vi": None,
            "ipa": None,
        })
    return toks


def word_count(tokens: list[dict]) -> int:
    return sum(1 for t in tokens if t["is_word"])


# ── Chia card ─────────────────────────────────────────────────
CARD_MIN_WORDS = 80
CARD_MAX_WORDS = 150
TAIL_MIN_WORDS = 40
TAIL_MAX_WORDS = 200
_SENT_END = {".", "!", "?"}
_CLOSERS = {"”", "’", '"', "'", ")", "]", "»"}


def split_sentences(tokens: list[dict]) -> list[list[dict]]:
    """Câu kết thúc ở `. ! ?` (kèm dấu đóng ngoặc/nháy ngay sau) có `ws` khác rỗng."""
    out, cur = [], []
    for k, t in enumerate(tokens):
        cur.append(t)
        if t["text"] in _SENT_END or (t["text"] in _CLOSERS and k > 0 and tokens[k - 1]["text"] in _SENT_END):
            nxt = tokens[k + 1] if k + 1 < len(tokens) else None
            if t["ws"] and not (nxt and nxt["text"] in _CLOSERS):
                out.append(cur)
                cur = []
    if cur:
        out.append(cur)
    return out


def _units(paragraphs: list[list[dict]]) -> list[tuple[list[dict], bool]]:
    """Đoạn ≤ CARD_MAX_WORDS là 1 đơn vị. Đoạn dài hơn chia theo câu, gom tham lam sao cho
    mỗi phần ≤ CARD_MAX_WORDS (một câu dài hơn thì đứng riêng). Cờ = bắt đầu đoạn mới."""
    out = []
    for p in paragraphs:
        if word_count(p) <= CARD_MAX_WORDS:
            out.append((p, True))
            continue
        piece: list[dict] = []
        first = True
        for s in split_sentences(p):
            if piece and word_count(piece) + word_count(s) > CARD_MAX_WORDS:
                out.append((piece, first))
                piece, first = [], False
            piece = piece + s
        if piece:
            out.append((piece, first))
    return out


def split_cards(paragraphs: list[list[dict]]) -> list[list[dict]]:
    """Gom tham lam: thêm đơn vị vào card khi card còn < CARD_MIN_WORDS và tổng ≤ CARD_MAX_WORDS.
    Card cuối < TAIL_MIN_WORDS thì gộp vào card trước nếu tổng ≤ TAIL_MAX_WORDS.
    Nối giữa 2 đơn vị trong cùng card: `\\n\\n` nếu đơn vị sau là đoạn mới, ngược lại `" "`.
    Trả về token đã đánh lại `i` từ 0 trong mỗi card."""
    cards: list[list[tuple[list[dict], bool]]] = []
    for unit in _units(paragraphs):
        if cards and word_count(_flat(cards[-1])) < CARD_MIN_WORDS \
                and word_count(_flat(cards[-1])) + word_count(unit[0]) <= CARD_MAX_WORDS:
            cards[-1].append(unit)
        else:
            cards.append([unit])
    if len(cards) >= 2 and word_count(_flat(cards[-1])) < TAIL_MIN_WORDS \
            and word_count(_flat(cards[-2])) + word_count(_flat(cards[-1])) <= TAIL_MAX_WORDS:
        cards[-2].extend(cards.pop())
    return [_join(c) for c in cards]


def _flat(card: list[tuple[list[dict], bool]]) -> list[dict]:
    return [t for u, _ in card for t in u]


def _join(card: list[tuple[list[dict], bool]]) -> list[dict]:
    out: list[dict] = []
    for k, (unit, new_para) in enumerate(card):
        unit = [dict(t) for t in unit]
        if out:
            out[-1]["ws"] = "\n\n" if new_para else " "
        out.extend(unit)
    if out:
        out[-1]["ws"] = ""
    for i, t in enumerate(out):
        t["i"] = i
    return out


# ── Kiểm tra trước khi lưu ────────────────────────────────────
MIN_WORDS = 50
MAX_WORDS = 2000
MIN_ENGLISH_RATIO = 0.85
TITLE_MAX_CHARS = 120
_ENGLISH_WORD = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")

MSG_TOO_SHORT = "Bài hơi ngắn, thêm một đoạn nữa nhé."
MSG_TOO_LONG = "Bài hơi dài, bạn chia thành hai bài nhé."
MSG_NOT_ENGLISH = "Hình như chữ này chưa phải tiếng Anh, bạn xem lại giúp mình nhé."
MSG_NO_TITLE = "Bài cần một tiêu đề ngắn nhé."


def validate_text(title: str, paragraphs: list[list[dict]]) -> Optional[str]:
    """None = lưu được; ngược lại trả câu báo nhẹ (đúng thứ tự kiểm dưới)."""
    words = [t["text"] for p in paragraphs for t in p if t["is_word"]]
    if not title.strip() or len(title.strip()) > TITLE_MAX_CHARS:
        return MSG_NO_TITLE
    if len(words) < MIN_WORDS:
        return MSG_TOO_SHORT
    if len(words) > MAX_WORDS:
        return MSG_TOO_LONG
    english = sum(1 for w in words if _ENGLISH_WORD.fullmatch(w))
    if english / len(words) < MIN_ENGLISH_RATIO:
        return MSG_NOT_ENGLISH
    return None


def suggest_title(raw: str) -> str:
    """Gợi ý tiêu đề: dòng đầu tiên khác rỗng, cắt ở TITLE_MAX_CHARS."""
    for line in normalize_text(raw).split("\n"):
        line = _SPACES.sub(" ", line).strip()
        if line:
            return line[:TITLE_MAX_CHARS]
    return ""


# ── Tra dict_entries ──────────────────────────────────────────
def lookup_form(text: str) -> str:
    """Khóa tra `dict_entries.form`: NFC, chữ thường, ’ → '."""
    return unicodedata.normalize("NFC", text).lower().replace("’", "'")


def lookup_forms(tokens: list[dict]) -> list[str]:
    """Danh sách dạng cần tra (không trùng, theo thứ tự xuất hiện), gồm cả dạng bỏ 's."""
    seen: dict[str, None] = {}
    for t in tokens:
        if not t["is_word"] or is_pure_number(t["text"]):
            continue
        f = lookup_form(t["text"])
        seen.setdefault(f, None)
        if f.endswith("'s") and len(f) > 2:
            seen.setdefault(f[:-2], None)
    return list(seen)


def apply_dict(tokens: list[dict], dict_get: Callable[[str], Optional[dict]]) -> list[dict]:
    """Điền lemma / ipa / is_fn từ dict_entries. Không có dạng thì thử bỏ 's;
    vẫn không có thì giữ lemma = chữ thường, ipa = None, is_fn = False."""
    out = []
    for t in tokens:
        t = dict(t)
        if t["is_word"] and not is_pure_number(t["text"]):
            f = lookup_form(t["text"])
            e = dict_get(f) or (dict_get(f[:-2]) if f.endswith("'s") and len(f) > 2 else None)
            if e:
                t["lemma"], t["ipa"], t["is_fn"] = e["lemma"], e.get("ipa"), bool(e.get("is_fn"))
        out.append(t)
    return out


# ── edited_ratio (event user_article_added) ───────────────────
def _seq(raw: str) -> list[str]:
    return [m.group() for p in split_paragraphs(raw) for m in _TOKEN.finditer(p)]


def edited_ratio(ocr_text: str, final_text: str) -> float:
    """Khoảng cách chỉnh sửa theo token (từ + dấu câu, Levenshtein 2 hàng) giữa chữ OCR
    và chữ người dùng lưu, chia số token OCR; kẹp [0, 1], làm tròn 2 chữ số."""
    a, b = _seq(ocr_text), _seq(final_text)
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return round(min(1.0, prev[-1] / max(1, len(a))), 2)


# ── lookup_key (Edge Function lookup + cache) ─────────────────
SENTENCE_MAX_CHARS = 400
WINDOW_TOKENS = 30


def sentence_for(tokens: list[dict], i: int) -> tuple[str, int]:
    """Câu chứa token i (luật như cloze, CONTRACTS 3.3) và `occurrence` = số token đứng
    trước trong câu có cùng `lookup_form`. Câu dài hơn SENTENCE_MAX_CHARS → cửa sổ
    ±WINDOW_TOKENS token quanh i (trong câu)."""
    start = i
    while start > 0 and tokens[start - 1]["text"] not in _SENT_END:
        start -= 1
    end = i
    while end < len(tokens) - 1 and tokens[end]["text"] not in _SENT_END:
        end += 1
    while end < len(tokens) - 1 and tokens[end + 1]["text"] in _CLOSERS:
        end += 1
    span = tokens[start:end + 1]
    if len(_render(span)) > SENTENCE_MAX_CHARS:
        lo, hi = max(start, i - WINDOW_TOKENS), min(end, i + WINDOW_TOKENS)
        start, span = lo, tokens[lo:hi + 1]
    form = lookup_form(tokens[i]["text"])
    occ = sum(1 for t in tokens[start:i] if t["is_word"] and lookup_form(t["text"]) == form)
    return _render(span), occ


def _render(tokens: list[dict]) -> str:
    return "".join(t["text"] + t["ws"] for t in tokens).strip()


def normalize_sentence(s: str) -> str:
    return _SPACES.sub(" ", unicodedata.normalize("NFC", s)).strip()


def lookup_key(sentence: str, word: str, occurrence: int) -> str:
    """sha256 hex của `v1\\n<câu chuẩn hóa>\\n<lookup_form(word)>\\n<occurrence>` (UTF-8)."""
    payload = f"v1\n{normalize_sentence(sentence)}\n{lookup_form(word)}\n{occurrence}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── Model bản nháp 1.5 cho bài tự tải ─────────────────────────
class UserToken(BaseModel):
    i: int = Field(ge=0)
    text: str = Field(min_length=1)
    ws: Literal["", " ", "\n\n"]
    lemma: str
    pos: None = None
    is_word: bool
    is_fn: bool
    vi: None = None
    ipa: Optional[str] = None


class UserSection(BaseModel):
    id: str
    order_index: int = Field(ge=0)
    title: Literal[""] = ""
    icon_hint: Literal[""] = ""
    tokens: list[UserToken] = Field(min_length=1)
    key_idea: None = None
    check: None = None


class UserSource(BaseModel):
    name: Literal["Bài của bạn"]
    is_graded: Literal[False]


class UserArticleMeta(BaseModel):
    id: str = Field(pattern=r"^local_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    origin: Literal["user"]
    title: str = Field(min_length=1, max_length=TITLE_MAX_CHARS)
    category: None = None
    cefr_level: None = None
    source: UserSource
    word_count: int = Field(ge=MIN_WORDS, le=MAX_WORDS)
    section_count: int = Field(ge=1)


class UserArticleBundle(BaseModel):
    contract_version: Literal["1.5"]
    article: UserArticleMeta
    sections: list[UserSection]
    lexicon: list = Field(max_length=0)
    occurrences: list = Field(max_length=0)
    quiz: list = Field(max_length=0)

    @model_validator(mode="after")
    def _invariants(self) -> "UserArticleBundle":
        errors = []
        if self.article.section_count != len(self.sections):
            errors.append("section_count khác số section")
        if self.article.word_count != sum(t.is_word for s in self.sections for t in s.tokens):
            errors.append("word_count khác số token is_word")
        for k, s in enumerate(self.sections):
            if s.order_index != k or s.id != f"{self.article.id}_s{k}":
                errors.append(f"section {k}: order_index/id sai (cần `<article_id>_s{k}`)")
            if any(t.i != j for j, t in enumerate(s.tokens)):
                errors.append(f"{s.id}: token index không liên tục")
            if s.tokens[-1].ws != "":
                errors.append(f"{s.id}: token cuối card phải có ws rỗng")
            if any(t.is_fn and not t.is_word for t in s.tokens):
                errors.append(f"{s.id}: is_fn chỉ được true khi is_word")
        if errors:
            raise ValueError("Bài tự tải vi phạm bản nháp 1.5:\n- " + "\n- ".join(errors))
        return self


class UserArticleRecord(BaseModel):
    """Giá trị trong Hive box `user_articles` (khóa = article.id)."""
    bundle: UserArticleBundle
    created_at: str
    input_source: Literal["camera", "gallery", "paste"]
    ocr_engine: Optional[Literal["mlkit", "ppocr"]] = None
    edited_ratio: Optional[float] = Field(default=None, ge=0, le=1)
    dict_filled: bool

    @model_validator(mode="after")
    def _ocr_fields(self) -> "UserArticleRecord":
        if (self.input_source == "paste") != (self.ocr_engine is None):
            raise ValueError("ocr_engine null khi và chỉ khi input_source = paste")
        if (self.input_source == "paste") != (self.edited_ratio is None):
            raise ValueError("edited_ratio null khi và chỉ khi input_source = paste")
        return self


def build_bundle(article_id: str, title: str, raw_text: str,
                 dict_get: Optional[Callable[[str], Optional[dict]]] = None) -> dict:
    """Từ chữ đã soát → bundle bài tự tải. Ném ValueError(câu báo nhẹ) khi không đạt kiểm tra."""
    paragraphs = [tokenize_paragraph(p) for p in split_paragraphs(raw_text)]
    msg = validate_text(title, paragraphs)
    if msg:
        raise ValueError(msg)
    cards = split_cards(paragraphs)
    if dict_get:
        cards = [apply_dict(c, dict_get) for c in cards]
    sections = [{"id": f"{article_id}_s{k}", "order_index": k, "title": "", "icon_hint": "",
                 "tokens": c, "key_idea": None, "check": None} for k, c in enumerate(cards)]
    bundle = {
        "contract_version": DRAFT_CONTRACT_VERSION,
        "article": {"id": article_id, "origin": "user", "title": title.strip(), "category": None,
                    "cefr_level": None, "source": {"name": "Bài của bạn", "is_graded": False},
                    "word_count": sum(word_count(c) for c in cards), "section_count": len(cards)},
        "sections": sections, "lexicon": [], "occurrences": [], "quiz": [],
    }
    UserArticleBundle.model_validate(bundle)
    return bundle
