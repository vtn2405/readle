"""
BE-03: Tokenize → LLM enrich → locate → bundle.json + review.md

Usage:
    py -m pipeline.enrich run --slug eating-well --level A2 \
        --category "Health & Nutrition" --source-name "World of Wonder"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import random
import re
import sys
import textwrap
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from pipeline.cover import CoverSpec
from pipeline.glossary import normalize_glossary
from pipeline.ipa import add_token_ipa, phrase_ipa
from pipeline.reference.contract_models import (
    CONTRACT_VERSION,
    DEFINITION_MAX_WORDS,
    EXCERPT_MAX_CHARS,
    ArticleBundle,
)
from pipeline.reference.tokenize_and_match import (
    article_excerpt,
    get_nlp,
    lemma_key,
    locate,
    norm,
    merge_code_tokens,
    sentence_bounds,
    sentence_cloze,
    surface,
    tokenize,
)

OUT = pathlib.Path("pipeline/out")
CACHE = pathlib.Path("pipeline/.cache")
PROMPT_VERSION = "enrich-v1"
# Version riêng cho bước chọn mục từ (BE-06e1): đổi prompt bước 3 không làm mất cache
# nghĩa token / Key idea / Quick Check đã duyệt của bước 1-2.
ITEMS_PROMPT_VERSION = "items-v4"   # bài mới (BE-06i); bài đã duyệt ghim version trong prompt_pin.json
ITEMS_PROMPT_V2 = "items-v2"
ITEMS_VERSION_V3 = "items-v3"       # BE-06g (pizza, paris)
ITEMS_VERSIONS = (ITEMS_PROMPT_V2, ITEMS_VERSION_V3, ITEMS_PROMPT_VERSION)
# Prompt bước 4b (thẻ mục từ). v1 = PROMPT_VERSION cũ (10 bài đã duyệt; pin thiếu trường = v1);
# v2 (BE-06i mục 6): ví dụ chỉ dùng từ ≤ cấp bài, có validator theo từ điển CEFR.
DETAILS_PROMPT_V1 = PROMPT_VERSION
DETAILS_PROMPT_VERSION = "details-v2"
# BE-06i mục 7 (ADR-017 bổ sung run #93): chỉ tự ép chọn lại mục bài trước khi cấp ≤ cấp bài + 2.
REUSE_MAX_STEPS_ABOVE = 2
# Prompt bước 1 (Key idea + nghĩa token). Bài đã duyệt ghim version trong prompt_pin.json
# (thiếu trường = section-v1); đổi chữ prompt v1 sẽ sinh lại Key idea + nghĩa của 9 bài đã duyệt.
SECTION_PROMPT_V1 = "section-v1"
SECTION_PROMPT_VERSION = "section-v2"   # BE-06h, Q-025
# Ghim đầu vào prompt bước 3 của bài đã duyệt (BE-06g): sửa CEFR/mục từ của bài trước không
# làm bài sau trượt cache. Tạo bằng `py -m pipeline.enrich pin --slug <slug>`.
PIN_FILE = "prompt_pin.json"
# True → lời gọi LLM trượt cache thì báo lỗi thay vì gọi API (kiểm "chạy lại vẫn toàn cache hit").
CACHE_ONLY = False
DATA = pathlib.Path(__file__).parent / "data"
CEFR_DICT_PATH = DATA / "cefr.json"
# Thứ tự xử lý bài (known_entries = mục từ của các bài đứng trước, mọi cấp độ).
ORDER_PATH = OUT / "processing_order.json"


# ── Response models for instructor ──────────────────────────────

class TokenMeaning(BaseModel):
    i: int
    vi: str = Field(min_length=1, max_length=60,
                    description="Vietnamese meaning of THIS token in THIS sentence, 1-6 words")


class QuickCheckResponse(BaseModel):
    question: str = Field(description="English question about a specific detail or small inference")
    options: list[str] = Field(min_length=2, max_length=3)
    answer_index: int = Field(ge=0)
    explanation: str = Field(description="Vietnamese explanation of the correct answer")

    @model_validator(mode="after")
    def _valid_index(self):
        if self.answer_index >= len(self.options):
            raise ValueError(f"answer_index {self.answer_index} >= {len(self.options)} options")
        return self


_META_KEY_IDEA = re.compile(
    r"^(this|the)\s+(section|part|text|paragraph|article|passage)\s+"
    r"(gives|explains|describes|tells|talks|shows|is about|lists|introduces|presents)\b",
    re.IGNORECASE)


class SectionEnrichment(BaseModel):
    key_idea: str = Field(
        description="One simple English sentence (A2-level vocabulary), max 15 words, "
                    "capturing the section's main point")
    meanings: list[TokenMeaning]
    check: Optional[QuickCheckResponse] = None

    @field_validator("key_idea")
    @classmethod
    def _states_content(cls, v: str, info: ValidationInfo) -> str:
        # Chỉ áp cho section-v2 (bài đã duyệt bằng v1 vẫn đọc cache được).
        if (info.context or {}).get("key_idea_v2") and _META_KEY_IDEA.match(v.strip()):
            raise ValueError("key_idea describes the section ('This section …'); "
                             "state the content itself, e.g. 'Paris has 2.34 million people.'")
        return v

    @field_validator("meanings")
    @classmethod
    def _covers_all_words(cls, v: list[TokenMeaning], info: ValidationInfo) -> list[TokenMeaning]:
        need = set(info.context["word_indexes"])
        got = {m.i for m in v}
        missing, extra = sorted(need - got), sorted(got - need)
        if missing or extra:
            raise ValueError(f"meanings coverage: missing={missing} extra={extra}")
        return v


class KeyIdeaTokenMeaning(BaseModel):
    section_order: int = Field(description="order_index of the section")
    i: int = Field(description="Token index within that key idea")
    vi: str = Field(min_length=1, max_length=60)


class AllKeyIdeaMeanings(BaseModel):
    meanings: list[KeyIdeaTokenMeaning]

    @field_validator("meanings")
    @classmethod
    def _covers_all(cls, v: list[KeyIdeaTokenMeaning], info: ValidationInfo) -> list[KeyIdeaTokenMeaning]:
        need = set(info.context["expected_pairs"])
        got = {(m.section_order, m.i) for m in v}
        missing, extra = sorted(need - got), sorted(got - need)
        if missing or extra:
            raise ValueError(f"key_idea meanings: missing={missing} extra={extra}")
        return v


class SelectedItem(BaseModel):
    canonical_form: str = Field(description="Base form, lowercase, verb in infinitive")
    type: Literal["single_word", "collocation"]
    pos: str
    cefr_level: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    vi: str = Field(description="Vietnamese meaning in this article's context")
    ipa: Optional[str] = None
    definition_en: str = Field(description="Clear 1-sentence English definition")
    extra_example: str = Field(
        description="A new simple sentence using the item, on a DIFFERENT topic")


CEFR = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
EXAMPLE_MAX_WORDS = 20


class EntryDetail(BaseModel):
    canonical_form: str
    cefr_level: CEFR = Field(
        description="English Vocabulary Profile level of THIS item as a whole "
                    "(for a phrase: the phrase's own level, not its hardest word)")
    definition_en: str = Field(description=f"Learner-dictionary definition, max {DEFINITION_MAX_WORDS} words")
    extra_example: str = Field(
        description=f"New natural sentence using the item, max {EXAMPLE_MAX_WORDS} words, different topic")

    @field_validator("definition_en")
    @classmethod
    def _short_definition(cls, v: str) -> str:
        n = len(v.split())
        if n > DEFINITION_MAX_WORDS:
            raise ValueError(f"definition_en has {n} words; max {DEFINITION_MAX_WORDS}")
        return v

    @model_validator(mode="after")
    def _example_uses_item(self, info: ValidationInfo):
        n = len(self.extra_example.split())
        if n > EXAMPLE_MAX_WORDS:
            raise ValueError(f"{self.canonical_form}: extra_example has {n} words; max {EXAMPLE_MAX_WORDS}")
        if not locate(tokenize(self.extra_example), self.canonical_form):
            raise ValueError(
                f"{self.canonical_form}: extra_example must contain the item itself "
                f"(any inflection), e.g. '{self.canonical_form}'")
        originals = (info.context or {}).get("originals", {})
        if norm_sentence(self.extra_example) == norm_sentence(originals.get(self.canonical_form, "")):
            raise ValueError(f"{self.canonical_form}: extra_example copies the article sentence")
        # details-v2 (BE-06i mục 6): từ nội dung trong ví dụ (trừ chính mục từ) không khó hơn cấp bài.
        ctx = info.context or {}
        if ctx.get("example_level") and ctx.get("example_look"):
            hard = example_words_above(self.extra_example, self.canonical_form,
                                       ctx["example_level"], ctx["example_look"])
            if hard:
                raise ValueError(
                    f"{self.canonical_form}: extra_example uses words above {ctx['example_level']}: "
                    f"{', '.join(f'{w} ({c})' for w, c in hard)}. Rewrite it with simpler words "
                    f"(only the item itself may be harder than {ctx['example_level']}).")
        return self


def example_words_above(sentence: str, form: str, level: str, look) -> list[tuple[str, str]]:
    """Từ nội dung của câu ví dụ có cấp từ điển (cefr.json > CEFR-J > Octanove) cao hơn `level`,
    bỏ qua các token thuộc chính mục từ; từ không có trong từ điển thì bỏ qua."""
    toks = tokenize(sentence)
    inside = {i for s, e in locate(toks, form) for i in range(s, e + 1)}
    out: list[tuple[str, str]] = []
    for t in toks:
        if not t["is_word"] or t["i"] in inside or t["pos"] not in CONTENT_UPOS:
            continue
        got = look(norm(t["lemma"]), t["pos"], t["text"])
        if got and CEFR_ORDER.index(got[0]) > CEFR_ORDER.index(level) and (t["text"], got[0]) not in out:
            out.append((t["text"], got[0]))
    return out


class EntryDetails(BaseModel):
    entries: list[EntryDetail]

    @field_validator("entries")
    @classmethod
    def _covers_all(cls, v: list[EntryDetail], info: ValidationInfo) -> list[EntryDetail]:
        need = set(info.context["forms"])
        got = {e.canonical_form for e in v}
        missing, extra = sorted(need - got), sorted(got - need)
        if missing or extra:
            raise ValueError(f"entries coverage: missing={missing} extra={extra}. "
                             "Use canonical_form exactly as given.")
        return v


def norm_sentence(s: str) -> str:
    return " ".join(s.lower().split()).rstrip(".!?")


TFNG_OPTIONS = ["True", "False", "Not Given"]
# Mệnh đề nói về chính bài viết ("The article gives…") luôn kiểm được bằng cách đọc bài → không bao giờ NG.
_ABOUT_ARTICLE = re.compile(r"^\s*(according to )?(the )?(article|text|writer|author|passage|story)\b", re.I)


class QuizItemResponse(BaseModel):
    type: Literal["true_false", "multiple_choice", "true_false_ng"]
    question: str
    options: list[str] = Field(min_length=2, max_length=4)
    answer_index: int = Field(ge=0)
    explanation: str = Field(description="Vietnamese explanation")

    @model_validator(mode="after")
    def _valid_index(self):
        if self.type == "true_false_ng":
            # LLM hay trả thiếu "Not Given" hoặc viết "Not given" → chuẩn hóa bằng code (run #68).
            norm = [o.strip().lower() for o in self.options]
            if not norm or any(o not in ("true", "false", "not given") for o in norm) \
                    or norm != [x.lower() for x in TFNG_OPTIONS[:len(norm)]]:
                raise ValueError(f"true_false_ng options must be {TFNG_OPTIONS}, got {self.options}")
            self.options = list(TFNG_OPTIONS)
            if _ABOUT_ARTICLE.match(self.question):
                raise ValueError(
                    "true_false_ng statement must be about the world, not about the article itself "
                    "('The article says/gives…' can always be checked by reading, so it is never Not Given). "
                    "True = the text says the same; False = a sentence in the text contradicts it; "
                    "Not Given = no sentence confirms or contradicts it.")
        if self.answer_index >= len(self.options):
            raise ValueError(f"answer_index {self.answer_index} >= {len(self.options)} options")
        return self


# Từ khái quát hóa: mệnh đề T/F không được dùng nếu bài không có (Q-022 run #72).
QUIZ_QUALIFIERS = {"often", "usually", "always", "most", "mostly", "never", "generally",
                   "typically", "commonly", "normally", "rarely", "seldom"}
_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


def norm_evidence(s: str) -> str:
    """So khớp evidence với chữ của bài: thường hóa ngoặc, khoảng trắng, chữ thường, bỏ dấu câu cuối."""
    s = " ".join(s.translate(_QUOTES).lower().split())
    return s.strip().strip("\"'").rstrip(".!?,;:").strip()


class QuizItemV3(QuizItemResponse):
    """items-v3 (BE-06g): thêm `evidence` (chỉ dùng trong pipeline + review.md, không vào contract)."""
    evidence: Optional[str] = Field(
        default=None,
        description="ONE sentence copied word for word from the text that proves the correct answer; "
                    "null when the answer is Not Given")

    @model_validator(mode="after")
    def _evidence(self, info: ValidationInfo):
        text = (info.context or {}).get("full_text")
        if text is None:
            return self
        is_ng = self.type == "true_false_ng" and self.options[self.answer_index] == "Not Given"
        ev = (self.evidence or "").strip()
        if is_ng and ev:
            raise ValueError(f"Question '{self.question}': the answer is Not Given, so evidence must be "
                             "null. If a sentence in the text decides it, the answer is True or False.")
        if not is_ng:
            if not ev:
                raise ValueError(f"Question '{self.question}': give evidence — one sentence copied "
                                 "exactly from the text that proves the answer.")
            if norm_evidence(ev) not in norm_evidence(text):
                raise ValueError(f"Question '{self.question}': evidence \"{ev}\" is not in the text. "
                                 "Copy the sentence word for word (or choose another question).")
        if self.type in ("true_false", "true_false_ng"):
            text_words = set(re.findall(r"[a-z]+", text.lower()))
            extra = sorted(w for w in set(re.findall(r"[a-z]+", self.question.lower()))
                           & QUIZ_QUALIFIERS if w not in text_words)
            if extra:
                raise ValueError(f"Statement '{self.question}' uses {extra}, which the text never uses: "
                                 "do not make the statement more general than the text.")
        return self


CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
# ADR-016: so muc tu theo cap do bai + do dai; CEFR muc tu theo i+1.
ITEM_COUNT_BOUNDS = {"A2": (6, 10), "B1": (8, 12), "B2": (10, 15)}
# Nguoi dung chot run #38: khoang 1 muc / 60-80 tu (100/80 = 1.25, 100/60 = 1.67), kep trong tran theo cap.
ITEMS_PER_100_WORDS = (1.25, 1.67)


def item_count_range(level: str, words: int) -> tuple[int, int]:
    lo_b, hi_b = ITEM_COUNT_BOUNDS[level]
    lo = min(max(round(words * ITEMS_PER_100_WORDS[0] / 100), lo_b), hi_b)
    hi = min(max(round(words * ITEMS_PER_100_WORDS[1] / 100), lo_b), hi_b)
    if lo == hi:  # luon de LLM mot khoang it nhat 2 gia tri
        lo, hi = (lo - 1, hi) if lo > lo_b else (lo, hi + 1)
    return lo, hi


def allowed_cefr(level: str) -> tuple[str, str]:
    """i+1: ngang cap bai hoac cao hon 1 bac."""
    k = CEFR_ORDER.index(level)
    return CEFR_ORDER[k], CEFR_ORDER[k + 1]


class ArticleItems(BaseModel):  # items-v2
    # Trần thật nằm ở count_range (validator); 20 chừa chỗ cho required_items nâng trần.
    items: list[SelectedItem] = Field(min_length=6, max_length=20)
    quiz: list[QuizItemResponse] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def _locatable_and_valid(self, info: ValidationInfo):
        ctx = info.context
        lo, hi = ctx.get("count_range", (6, 10))
        if not lo <= len(self.items) <= hi:
            raise ValueError(f"Select between {lo} and {hi} items (got {len(self.items)}).")
        allowed = ctx.get("allowed_cefr")
        req_keys = set((ctx.get("required_keys") or {}).keys())
        cefr_dict = ctx.get("cefr_dict") or {}
        if allowed:
            # Cap trong tu dien dung chung thang cap LLM tu cham.
            # v3 (ctx "dict_level"): từ đơn không có trong cefr.json lấy cấp từ cefr_lexicon;
            # mục cefr.json KHÓ hơn i+1 được miễn (người duyệt đã chốt cấp, vd `pest` C1 ở bài B1).
            dict_level = ctx.get("dict_level")
            off = []
            for it in self.items:
                key = lemma_key(it.canonical_form)
                src = "known" if key in cefr_dict else None
                lvl = cefr_dict.get(key)
                if lvl is None and dict_level and " " not in it.canonical_form.strip():
                    lvl = dict_level(it)
                    src = "dictionary" if lvl else None
                lvl = lvl or it.cefr_level
                if lvl in allowed or key in req_keys:
                    continue
                if (src == "known" and dict_level
                        and CEFR_ORDER.index(lvl) > CEFR_ORDER.index(allowed[1])
                        and not above_ceiling(lvl, ctx.get("exempt_ceiling"))):  # v4: tối đa cấp bài + 2
                    continue
                off.append(f"{it.canonical_form} ({lvl}{', dictionary' if src == 'dictionary' else ''})")
            if off:
                raise ValueError(
                    f"Items outside the allowed CEFR levels {'/'.join(allowed)}: {off}. Replace them with "
                    "items from the text at those levels (not easier, at most one level above the article).")
        loc = ctx["locate"]
        toks_list = ctx["section_tokens"]
        bad = [it.canonical_form for it in self.items
               if not any(loc(toks, it.canonical_form) for toks in toks_list)]
        if bad:
            raise ValueError(
                f"Items not found in text (match on lemma): {bad}. "
                "Use the exact words from the text in base form.")
        required = ctx.get("required_keys") or {}
        got = {lemma_key(it.canonical_form) for it in self.items}
        missing = [form for key, form in required.items() if key not in got]
        if missing:
            raise ValueError(
                f"Required items missing: {missing}. You MUST include each of them "
                "(exact canonical_form as given).")
        excluded = ctx.get("excluded_keys") or {}
        banned = [form for key, form in excluded.items() if key in got]
        if banned:
            raise ValueError(
                f"Excluded items selected: {banned}. Do NOT select them; pick other items.")
        if ctx["level"] == "A2":
            ng = [q.question for q in self.quiz if q.type == "true_false_ng"]
            if ng:
                raise ValueError("A2 articles must not use true_false_ng")
        return self


class ArticleItemsV3(ArticleItems):
    quiz: list[QuizItemV3] = Field(min_length=3, max_length=3)


MIN_COLLOCATION_SHARE = 0.4  # BE-06i mục 5 (Q-029): pizza v3 chọn 8/10 từ đơn


def quiz_has_negative(quiz, level: str) -> bool:
    """Có ≥ 1 câu đáp án False (true_false / true_false_ng); bài B1+ được thay bằng 1 câu Not Given."""
    for q in quiz:
        ans = q.options[q.answer_index]
        if q.type in ("true_false", "true_false_ng") and ans == "False":
            return True
        if level != "A2" and q.type == "true_false_ng" and ans == "Not Given":
            return True
    return False


class ArticleItemsV4(ArticleItemsV3):
    """items-v4 (BE-06i): ≥ 40% mục là cụm; quiz không được toàn đáp án True."""

    @model_validator(mode="after")
    def _v4_rules(self, info: ValidationInfo):
        ctx = info.context or {}
        n = len(self.items)
        coll = sum(1 for it in self.items if it.type == "collocation")
        need = -(-int(MIN_COLLOCATION_SHARE * 10 * n) // 10)  # ceil(0.4 × n) không lệch số thực
        if coll < need:
            raise ValueError(
                f"Only {coll} of {n} items are collocations; at least {need} must be fixed phrases "
                "(type \"collocation\"). Replace some single words with fixed phrases from the text — "
                "the REPEATED PHRASES list is a good place to look.")
        if not quiz_has_negative(self.quiz, ctx.get("level", "B1")):
            extra = " (or one true_false_ng question whose answer is \"Not Given\")" \
                if ctx.get("level", "A2") != "A2" else ""
            raise ValueError(
                "At least one true/false question must have the answer \"False\": a statement that a "
                f"sentence in the text directly contradicts{extra}. Do not make every statement true.")
        return self


# ── Human overrides (pipeline/out/<slug>/overrides.json) ────────

class MeaningOverride(BaseModel):
    section_order: int
    text: str = Field(description="Exact token text, e.g. 'Serve'")
    vi: str = Field(min_length=1, max_length=60)
    nth: int = Field(default=1, ge=1, description="Which occurrence of `text` in the section")
    in_key_idea: bool = Field(default=False, description="Target the section's Key idea, not its body")


class LexiconOverride(BaseModel):
    """Sửa tay một mục từ sau khi duyệt; trường nào None thì giữ bản sinh tự động."""
    cefr_level: Optional[CEFR] = None
    pos: Optional[str] = None
    ipa: Optional[str] = None
    definition_en: Optional[str] = None
    extra_example: Optional[str] = None
    vi: Optional[str] = Field(default=None, min_length=1, max_length=80,
                              description="Nghĩa Việt của mục từ; ghi đè occurrence.vi ở mọi vị trí. "
                                          "Áp sau bước 4b nên không đổi cache của prompt")
    original_contains: Optional[str] = Field(
        default=None, description="Chọn câu gốc của thẻ (đưa vào bước 4b): occurrence có câu chứa chuỗi này")


# Trường của LexiconOverride không phải trường của thẻ (không ghi vào lexicon).
_LEX_NON_ENTRY = {"vi", "original_contains"}


class QuizOverride(BaseModel):
    """Sửa một phần câu quiz/Quick Check; trường None giữ bản sinh tự động."""
    type: Optional[Literal["true_false", "multiple_choice", "true_false_ng"]] = None
    question: Optional[str] = None
    options: Optional[list[str]] = None
    answer_index: Optional[int] = None
    explanation: Optional[str] = None


class QuickCheckOverride(QuizOverride):
    remove: bool = Field(default=False, description="Bỏ Quick Check của section này")


class OccurrenceExclusion(BaseModel):
    item: str = Field(description="canonical_form của mục từ")
    sentence_contains: str = Field(description="Bỏ occurrence có câu chứa chuỗi này (vd thrust dùng như động từ)")


class Overrides(BaseModel):
    title: Optional[str] = Field(
        default=None, min_length=1, max_length=120,
        description="tiêu đề bài sau duyệt; thắng --title và tiêu đề trong normalized_sections.json")
    required_items: list[str] = Field(
        default_factory=list,
        description="canonical_forms the LLM must select (must appear in the text)")
    excluded_items: list[str] = Field(
        default_factory=list,
        description="canonical_forms the editor rejected; the LLM must not select them")
    meanings: list[MeaningOverride] = Field(default_factory=list)
    lexicon: dict[str, LexiconOverride] = Field(
        default_factory=dict, description="canonical_form → trường cần sửa")
    key_ideas: dict[int, str] = Field(
        default_factory=dict, description="section order → Key idea viết tay (≤ 15 từ)")
    quiz: dict[int, QuizOverride] = Field(default_factory=dict, description="số thứ tự câu (1-3) → trường sửa")
    quick_checks: dict[int, QuickCheckOverride] = Field(
        default_factory=dict, description="section order → trường sửa (hoặc remove)")
    exclude_occurrences: list[OccurrenceExclusion] = Field(default_factory=list)
    drop_items: list[str] = Field(
        default_factory=list,
        description="canonical_forms bỏ SAU các bước LLM (không đổi prompt → cache hit, nội dung đã duyệt "
                    "giữ nguyên). Dùng khi bài đã duyệt; bài mới dùng excluded_items")
    excerpt: Optional[str] = Field(
        default=None, min_length=1, max_length=EXCERPT_MAX_CHARS,
        description="đoạn trích sửa tay (ADR-024); mặc định câu đầu card đầu, chép nguyên văn")
    cover: Optional[CoverSpec] = Field(
        default=None, description="vùng cắt ảnh bìa (pipeline.cover); không có → bìa chủ đề")

    @field_validator("key_ideas")
    @classmethod
    def _short_key_ideas(cls, v: dict[int, str]) -> dict[int, str]:
        long = {k: len(t.split()) for k, t in v.items() if len(t.split()) > 15}
        if long:
            raise ValueError(f"key_ideas quá 15 từ: {long}")
        return v


def _patch(model_cls, base: dict, ov: QuizOverride, label: str) -> dict:
    """Áp sửa một phần rồi validate lại bằng model gốc (vd answer_index phải < số lựa chọn)."""
    patch = ov.model_dump(exclude_none=True, exclude={"remove"})
    try:
        return model_cls.model_validate({**base, **patch}).model_dump()
    except Exception as e:  # noqa: BLE001 — báo rõ override nào hỏng
        raise ValueError(f"override {label} không hợp lệ: {e}") from e


def apply_key_idea_overrides(sections_data: list[dict], overrides: "Overrides") -> list[str]:
    """Gọi TRƯỚC bước 2 (nghĩa token Key idea tính theo text mới)."""
    by_order = {sd["order"]: sd for sd in sections_data}
    applied = []
    for order, text in overrides.key_ideas.items():
        sd = by_order.get(order)
        if sd is None:
            raise ValueError(f"override key_ideas: section {order} không tồn tại")
        applied.append(f"sec {order}: \"{sd['key_idea_text']}\" → \"{text}\"")
        sd["key_idea_text"] = text
        sd["key_idea_tokens"] = tokenize(text, with_tags=True)
    return applied


MAX_QUICK_CHECKS = 3  # SPEC 1.1 / 2.1: Quick Check thưa, tối đa 2-3 câu mỗi bài


def cap_quick_checks(sections_data: list[dict], limit: int = MAX_QUICK_CHECKS) -> list[str]:
    """Giữ Quick Check ở `limit` section dài nhất (bằng nhau → section trước), bỏ phần còn lại.
    Chạy sau LLM, trước override của người duyệt (override vẫn thêm/sửa/bỏ được)."""
    with_check = [sd for sd in sections_data if sd.get("check")]
    if len(with_check) <= limit:
        return []
    ranked = sorted(with_check, key=lambda sd: (-count_words(sd["tokens"]), sd["order"]))
    dropped = sorted(ranked[limit:], key=lambda sd: sd["order"])
    for sd in dropped:
        sd["check"] = None
    return [f"sec {sd['order']}: bỏ Quick Check (trần {limit}/bài, giữ section dài nhất)" for sd in dropped]


def apply_quick_check_overrides(sections_data: list[dict], overrides: "Overrides") -> list[str]:
    by_order = {sd["order"]: sd for sd in sections_data}
    applied = []
    for order, ov in overrides.quick_checks.items():
        sd = by_order.get(order)
        if sd is None:
            raise ValueError(f"override quick_checks: section {order} không tồn tại")
        if ov.remove:
            sd["check"] = None
            applied.append(f"sec {order}: bỏ Quick Check")
            continue
        sd["check"] = _patch(QuickCheckResponse, sd.get("check") or {}, ov, f"quick_checks[{order}]")
        applied.append(f"sec {order}: {', '.join(ov.model_dump(exclude_none=True, exclude={'remove'}))}")
    return applied


def apply_quiz_overrides(quiz: list, overrides: "Overrides") -> tuple[list, list[str]]:
    out = [q.model_dump() if hasattr(q, "model_dump") else dict(q) for q in quiz]
    applied = []
    for n, ov in overrides.quiz.items():
        if not 1 <= n <= len(out):
            raise ValueError(f"override quiz: câu {n} không tồn tại (có {len(out)} câu)")
        out[n - 1] = _patch(QuizItemResponse, out[n - 1], ov, f"quiz[{n}]")
        applied.append(f"câu {n}: {', '.join(ov.model_dump(exclude_none=True))}")
    return [QuizItemResponse.model_validate(q) for q in out], applied


def apply_occurrence_exclusions(occurrences: list[dict], overrides: "Overrides") -> tuple[list[dict], list[str]]:
    out, applied = list(occurrences), []
    for ex in overrides.exclude_occurrences:
        lex = item_to_lex_id(ex.item)
        hit = [o for o in out if o["lexicon_entry_id"] == lex and ex.sentence_contains in o["example_sentence"]]
        if not hit:
            raise ValueError(f"exclude_occurrences: không có occurrence '{ex.item}' chứa \"{ex.sentence_contains}\"")
        out = [o for o in out if o not in hit]
        if not any(o["lexicon_entry_id"] == lex for o in out):
            raise ValueError(f"exclude_occurrences: '{ex.item}' không còn occurrence nào")
        applied.append(f"{ex.item}: bỏ {len(hit)} vị trí (\"{ex.sentence_contains}\")")
    return out, applied


def pick_originals(occurrences: list[dict], lex_to_form: dict[str, str],
                   overrides: "Overrides") -> dict[str, str]:
    """canonical_form → câu gốc của thẻ: mặc định occurrence đầu; `original_contains` chọn câu khác."""
    want = {lemma_key(f): o.original_contains for f, o in overrides.lexicon.items() if o.original_contains}
    originals: dict[str, str] = {}
    for occ in occurrences:
        form = lex_to_form[occ["lexicon_entry_id"]]
        sub = want.get(lemma_key(form))
        if sub:
            if sub in occ["example_sentence"]:
                originals[form] = occ["example_sentence"]
        else:
            originals.setdefault(form, occ["example_sentence"])
    missing = [f for f, o in overrides.lexicon.items()
               if o.original_contains and lemma_key(f) in {lemma_key(x) for x in lex_to_form.values()}
               and f not in originals and not any(lemma_key(f) == lemma_key(k) for k in originals)]
    if missing:
        raise ValueError(f"original_contains: không thấy câu phù hợp cho {missing}")
    return originals


def load_overrides(path: pathlib.Path) -> Overrides:
    if not path.exists():
        return Overrides()
    return Overrides.model_validate_json(path.read_text("utf-8-sig"))


# ── Từ điển CEFR dùng chung, known_entries, chuẩn hóa định nghĩa (BE-06e1) ──

def load_cefr_dict(path: pathlib.Path = CEFR_DICT_PATH) -> dict[str, dict]:
    """lemma_key → {"form", "cefr", "source"}. Thiếu file → rỗng."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text("utf-8-sig"))["entries"]
    out = {}
    for form, v in raw.items():
        if v["cefr"] not in CEFR_ORDER:
            raise ValueError(f"cefr.json: '{form}' có cấp lạ {v['cefr']}")
        out[lemma_key(form)] = {"form": form, "cefr": v["cefr"], "source": v.get("source", "")}
    return out


def collect_known_entries(slug: str, out_dir: pathlib.Path = OUT,
                          order_path: Optional[pathlib.Path] = None) -> list[dict]:
    """Mục từ (mọi cấp độ) của các bài đứng TRƯỚC `slug` trong processing_order.json.
    Slug không có trong danh sách → lấy của mọi bài trong danh sách. Trùng lemma_key → giữ bài đầu.
    Trả [{"form", "cefr", "slug"}]."""
    order_path = order_path or out_dir / "processing_order.json"
    if not order_path.exists():
        return []
    order: list[str] = json.loads(order_path.read_text("utf-8-sig"))
    before = order[: order.index(slug)] if slug in order else order
    seen: set[str] = set()
    out: list[dict] = []
    for s in before:
        f = out_dir / s / "bundle.json"
        if not f.exists():
            continue
        lexicon = {e["lemma_key"]: e for e in json.loads(f.read_text("utf-8"))["lexicon"]}
        # Danh sách mục TRƯỚC drop_items (giữ prompt bài sau như cũ); thiếu file → lexicon của bundle.
        sel = out_dir / s / SELECTED_ITEMS_FILE
        selected = (json.loads(sel.read_text("utf-8")) if sel.exists()
                    else [{"form": e["canonical_form"], "cefr": e["cefr_level"]} for e in lexicon.values()])
        for it in selected:
            key = lemma_key(it["form"])
            if key in seen:
                continue
            seen.add(key)
            e = lexicon.get(key)
            entry = {"form": it["form"], "cefr": it["cefr"], "slug": s}
            if e:
                entry["card"] = {k: e.get(k) for k in SHARED_CARD_FIELDS}
            else:
                entry["dropped"] = True   # bị drop_items ở bài đó: vẫn liệt kê trong prompt, không ép chọn lại
            out.append(entry)
    return out


SELECTED_ITEMS_FILE = "selected_items.json"


def load_pin(slug: str, out_dir: pathlib.Path = OUT) -> Optional[dict]:
    f = out_dir / slug / PIN_FILE
    return json.loads(f.read_text("utf-8")) if f.exists() else None


def pinned_section_version(pin: Optional[dict]) -> str:
    """Version prompt bước 1: bài có pin mà thiếu trường = section-v1 (ghim trước BE-06h)."""
    if pin is None:
        return SECTION_PROMPT_VERSION
    return pin.get("section_prompt_version", SECTION_PROMPT_V1)


def pinned_details_version(pin: Optional[dict]) -> str:
    """Version prompt bước 4b: bài có pin mà thiếu trường = v1 (ghim trước BE-06i)."""
    if pin is None:
        return DETAILS_PROMPT_VERSION
    return pin.get("details_prompt_version", DETAILS_PROMPT_V1)


def write_pin(slug: str, version: str, run_args: dict, known_entries: list[dict],
              known_levels: list[tuple[str, str]], out_dir: pathlib.Path = OUT,
              section_version: str = SECTION_PROMPT_VERSION,
              details_version: str = DETAILS_PROMPT_VERSION) -> pathlib.Path:
    pin = {
        "_note": "Ghim đầu vào prompt bước 3 (chọn mục từ + quiz) của bài đã duyệt (BE-06g) "
                 "và version prompt bước 1 (Key idea + nghĩa token, BE-06h). "
                 "Chạy lại enrich dùng đúng các danh sách này thay vì đọc lại bài trước / cefr.json, "
                 "nên sửa CEFR hay mục từ ở chỗ khác không làm bài này trượt cache. "
                 "CEFR cuối cùng trong bundle vẫn lấy cefr.json hiện tại. Không sửa tay.",
        "items_prompt_version": version,
        "section_prompt_version": section_version,
        "details_prompt_version": details_version,
        "run_args": run_args,
        "known_entries": [{k: e[k] for k in ("form", "cefr", "slug", "dropped") if k in e}
                          for e in known_entries],
        "known_cefr_levels": [list(x) for x in known_levels],
    }
    f = out_dir / slug / PIN_FILE
    f.write_text(json.dumps(pin, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f


def pinned_known_entries(pin: dict, live: list[dict]) -> list[dict]:
    """Danh sách ghim (form, cefr, dropped) + thẻ dùng chung lấy từ bài trước hiện tại
    (thẻ chỉ dùng sau LLM → không ảnh hưởng cache)."""
    cards = {lemma_key(e["form"]): e["card"] for e in live if e.get("card")}
    out = []
    for e in pin["known_entries"]:
        e = dict(e)
        card = cards.get(lemma_key(e["form"]))
        if card and not e.get("dropped"):
            e["card"] = card
        out.append(e)
    return out


def known_cefr_levels(cefr_dict: dict, sections_data: list[dict]) -> list[tuple[str, str]]:
    """Mục của cefr.json có trong bài → khối "KNOWN CEFR LEVELS" của prompt."""
    return sorted({(v["form"], v["cefr"]) for v in cefr_dict.values()
                   if found_in(sections_data, v["form"])})


def apply_drop_items(items, occurrences: list[dict], details: dict,
                     overrides: "Overrides") -> tuple[list, list[dict], list[str]]:
    """Bỏ mục SAU các bước LLM (overrides.drop_items). Trả (items, occurrences, báo cáo)."""
    drop = {lemma_key(f) for f in overrides.drop_items}
    if not drop:
        return items, occurrences, []
    found = {lemma_key(it.canonical_form) for it in items}
    missing = [f for f in overrides.drop_items if lemma_key(f) not in found]
    if missing:
        raise ValueError(f"drop_items: {missing} không phải mục từ đã chọn")
    kept = [it for it in items if lemma_key(it.canonical_form) not in drop]
    dropped_ids = {item_to_lex_id(it.canonical_form) for it in items
                   if lemma_key(it.canonical_form) in drop}
    occ = [o for o in occurrences if o["lexicon_entry_id"] not in dropped_ids]
    for it in items:
        if lemma_key(it.canonical_form) in drop:
            details.pop(it.canonical_form, None)
    return kept, occ, [f"Bỏ mục (drop_items): {f}" for f in overrides.drop_items]


# Trường thẻ mục từ dùng chung toàn hệ thống (lexicon_entries theo lemma_key, BE-06f).
SHARED_CARD_FIELDS = ("canonical_form", "type", "pos", "cefr_level", "ipa",
                      "definition_en", "extra_example")


def apply_shared_cards(items, details: dict, known_entries: list[dict],
                       overrides: "Overrides") -> list[str]:
    """BE-06f: mục đã có ở bài đứng trước → dùng lại nguyên thẻ của bài đó (DB giữ thẻ bài seed
    trước, seed không ghi đè). Sửa thẻ dùng chung phải sửa ở bài đầu tiên, không ở bài sau."""
    cards = {lemma_key(e["form"]): e for e in known_entries if e.get("card")}
    ov_keys = {lemma_key(f) for f, o in overrides.lexicon.items()
               if o.model_dump(exclude_none=True, exclude=_LEX_NON_ENTRY)}
    applied: list[str] = []
    for it in items:
        key = lemma_key(it.canonical_form)
        known = cards.get(key)
        if not known:
            continue
        if key in ov_keys:
            raise ValueError(f"override lexicon: '{it.canonical_form}' là thẻ dùng chung của bài "
                             f"'{known['slug']}' — sửa trong overrides.json của bài đó")
        d = details[it.canonical_form]
        changed = [k for k, v in known["card"].items()
                   if v is not None and d.get(k, getattr(it, k, None)) != v]
        d.update({k: v for k, v in known["card"].items() if v is not None})
        d["cefr_note"] = f"thẻ dùng chung ({known['slug']})"
        d["ipa_source"] = f"thẻ dùng chung ({known['slug']})"
        applied.append(f"{it.canonical_form}: dùng lại thẻ của {known['slug']}"
                       + (f" (đổi {', '.join(changed)})" if changed else ""))
    return applied


def normalize_definition(s: str) -> str:
    """Một kiểu viết cho mọi bài: chữ thường đầu câu (trừ từ viết hoa toàn bộ / tên riêng có
    chữ hoa thứ 2, vd "AI", "DNA"), không dấu chấm cuối. Giống kiểu fixture và Cambridge."""
    s = " ".join(s.split()).rstrip(" .")
    if not s:
        return s
    first = s.split()[0]
    if len(first) > 1 and first[1:].lower() != first[1:]:
        return s  # "AI", "DNA", "McDonald's"
    if first == "I" or first.startswith("I'"):
        return s
    return s[0].lower() + s[1:]


def apply_meaning_overrides(sections_data: list[dict], overrides: Overrides) -> list[str]:
    """Overwrite ``sd['meanings']`` in place. Keyed by token text (not index) so a
    small text fix does not silently shift the target. Raises if a target is missing."""
    applied = []
    by_order = {sd["order"]: sd for sd in sections_data}
    for ov in overrides.meanings:
        sd = by_order.get(ov.section_order)
        if sd is None:
            raise ValueError(f"override: section {ov.section_order} không tồn tại")
        toks, mean, where = ((sd["key_idea_tokens"], sd["key_idea_meanings"], "key idea ")
                             if ov.in_key_idea else (sd["tokens"], sd["meanings"], ""))
        hits = [t["i"] for t in toks if t["is_word"] and t["text"] == ov.text]
        if len(hits) < ov.nth:
            raise ValueError(
                f"override: không tìm thấy '{ov.text}' (lần {ov.nth}) ở {where}section {ov.section_order}")
        i = hits[ov.nth - 1]
        old = mean.get(i)
        mean[i] = ov.vi
        applied.append(f"sec {ov.section_order} · {where}{ov.text} (i={i}): \"{old}\" → \"{ov.vi}\"")
    return applied


# ── Helpers ─────────────────────────────────────────────────────

def get_text_client():
    """Return (instructor_client, deployment_name)."""
    load_dotenv()
    deployment = os.environ["AZURE_DEPLOYMENT_TEXT"]
    api_version = os.environ["AZURE_OPENAI_API_VERSION"]
    import instructor
    client = instructor.from_provider(
        f"azure_openai/{deployment}",
        api_version=api_version,
    )
    return client, deployment


class CacheMiss(RuntimeError):
    """--cache-only: bước LLM trượt cache (đầu vào prompt đã đổi)."""


def cached_create(client, deployment, response_model, messages, context=None, version=PROMPT_VERSION):
    """LLM call with file-based cache keyed on (deployment, prompt version, model, messages)."""
    raw = json.dumps(
        [deployment, version, response_model.__name__, messages],
        ensure_ascii=False, sort_keys=True, default=str,
    )
    h = hashlib.sha256(raw.encode()).hexdigest()
    f = CACHE / f"{h}.json"
    if f.exists():
        print("(cache hit)", end=" ", flush=True)
        return response_model.model_validate_json(f.read_text("utf-8"), context=context)
    if CACHE_ONLY:
        raise CacheMiss(f"{response_model.__name__} ({version}) không có trong cache: {h[:12]}")
    res = client.create(
        response_model=response_model,
        messages=messages,
        context=context,
        max_retries=2,
    )
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(res.model_dump_json(indent=2), encoding="utf-8")
    return res


def format_token_lines(tokens: list[dict]) -> str:
    """Format is_word tokens as ``i\\ttext`` lines for the LLM prompt."""
    return "\n".join(f"{t['i']}\t{t['text']}" for t in tokens if t["is_word"])


def count_words(tokens: list[dict]) -> int:
    return sum(1 for t in tokens if t["is_word"])


def normalize_title(t: str) -> str:
    """Title-case if ALL CAPS, otherwise leave alone."""
    return t.title() if t == t.upper() and len(t) > 1 else t


def resolve_title(norm_title: str, cli_title: Optional[str], overrides: "Overrides") -> str:
    """Thứ tự: overrides.json `title` > `--title` > tiêu đề trong normalized_sections.json."""
    return (overrides.title or "").strip() or cli_title or normalize_title(norm_title)


def extract_sentence(tokens: list[dict], start: int, end: int) -> str:
    """Full sentence containing the token range [start, end] (sentence_bounds)."""
    s, e = sentence_bounds(tokens, start, end)
    return "".join(t["text"] + t["ws"] for t in tokens[s : e + 1]).strip()


def item_to_lex_id(canonical: str) -> str:
    slug = canonical.lower().replace(" ", "_").replace("-", "_")
    return f"lex_{slug}"


def merge_codes_with_meanings(tokens: list[dict], meanings: dict[int, str]
                              ) -> tuple[list[dict], dict[int, str], list[str]]:
    """merge_code_tokens + chuyển nghĩa sang chỉ số mới. Token gộp: nếu mọi phần giữ nguyên chữ
    (tên riêng "R2" → "R2") thì nghĩa = chữ đã gộp; còn lại ghép nghĩa các phần bằng "-" và ghi chú."""
    new_tokens, remap = merge_code_tokens(tokens)
    groups: dict[int, list[int]] = {}
    for old, new in remap.items():
        groups.setdefault(new, []).append(old)
    new_meanings: dict[int, str] = {}
    notes: list[str] = []
    for new, olds in groups.items():
        if len(olds) == 1:
            if olds[0] in meanings:
                new_meanings[new] = meanings[olds[0]]
            continue
        parts = [tokens[o] for o in olds if tokens[o]["is_word"]]
        vis = [meanings.get(t["i"], t["text"]) for t in parts]
        if all(v.strip() == t["text"] for v, t in zip(vis, parts)):
            vi = new_tokens[new]["text"]
        else:
            vi = "-".join(vis)
        new_meanings[new] = vi
        notes.append(f"{new_tokens[new]['text']} (nghĩa: \"{vi}\")")
    return new_tokens, new_meanings, notes


def apply_meanings(tokens: list[dict], meanings: dict[int, str]) -> list[dict]:
    """Return new token list with ``vi`` filled from *meanings*. Does not mutate input."""
    out = []
    for t in tokens:
        d = dict(t)
        if t["is_word"] and t["i"] in meanings:
            d["vi"] = meanings[t["i"]]
        out.append(d)
    return out


# ── Step 1: section enrichment ──────────────────────────────────

SECTION_PROMPT = textwrap.dedent("""\
You are annotating an English article section for Vietnamese learners (level {level}).

SECTION: "{section_title}" (article: "{article_title}")

FULL TEXT:
{body}

WORD TOKENS (index — text; only content words, no punctuation):
{lines}

INSTRUCTIONS:
1. key_idea — ONE simple English sentence (A2-level vocabulary, max 15 words) \
that captures the section's main point. Do not simply copy the first sentence.
2. meanings — For EVERY token index listed above, give a SHORT Vietnamese meaning \
(1–6 words) for how that word is used in THIS context.
   • Content words: contextual meaning, e.g. "plays" → "đóng (vai trò)"
   • Function words (a, the, in, to, and, that …): very short, e.g. "(mạo từ xác định)"
   • Proper nouns / letters: keep as-is, e.g. "K" → "K"
3. check — {check_instruction}\
""")

# v2 (BE-06h, Q-025 bài paris): Key idea thêm "iron tower" không có trong bài và
# "This section gives…". Chỉ khác v1 ở mục 1.
_KEY_IDEA_V1 = ("1. key_idea — ONE simple English sentence (A2-level vocabulary, max 15 words) "
                "that captures the section's main point. Do not simply copy the first sentence.\n")
_KEY_IDEA_V2 = (
    "1. key_idea — ONE simple English sentence (A2-level vocabulary, max 15 words) "
    "that captures the section's main point. Do not simply copy the first sentence.\n"
    "   • Use only facts stated in the section; do not add details from general knowledge.\n"
    "   • State the content, not what the section does "
    "(write \"Paris has 2.34 million people.\", not \"This section gives facts about Paris.\").\n"
)
assert _KEY_IDEA_V1 in SECTION_PROMPT
SECTION_PROMPTS = {
    SECTION_PROMPT_V1: SECTION_PROMPT,
    SECTION_PROMPT_VERSION: SECTION_PROMPT.replace(_KEY_IDEA_V1, _KEY_IDEA_V2),
}


def enrich_section(client, deployment, tokens, section_title, article_title, level, body_text,
                   version: str = SECTION_PROMPT_VERSION):
    wc = count_words(tokens)
    if wc >= 120:
        check_instr = (
            "Write a Quick Check: one multiple-choice question (2–3 English options) "
            "about a SPECIFIC DETAIL or small inference. "
            "Do NOT ask about the main idea. Write the explanation in Vietnamese."
        )
    else:
        check_instr = "Set check to null (section too short for a Quick Check)."

    prompt = SECTION_PROMPTS[version].format(
        level=level,
        section_title=section_title,
        article_title=article_title,
        body=body_text,
        lines=format_token_lines(tokens),
        check_instruction=check_instr,
    )
    word_idxs = [t["i"] for t in tokens if t["is_word"]]
    return cached_create(
        client, deployment, SectionEnrichment,
        [{"role": "user", "content": prompt}],
        context={"word_indexes": word_idxs, "key_idea_v2": version != SECTION_PROMPT_V1},
    )


# ── Step 2: key-idea token meanings ─────────────────────────────

KEY_IDEA_PROMPT = textwrap.dedent("""\
Provide a SHORT Vietnamese meaning (1–6 words) for each numbered token below.
These are words from Key Idea sentences that summarize sections of "{article_title}".
Apply the same rules as body-text meanings: content words get contextual meaning, \
function words get a short label, proper nouns stay as-is.

{sections_block}

Return one meaning for every (section_order, i) pair listed.\
""")


def enrich_key_ideas(client, deployment, sections_data, article_title):
    blocks = []
    expected: set[tuple[int, int]] = set()
    for sd in sections_data:
        word_toks = [t for t in sd["key_idea_tokens"] if t["is_word"]]
        if not word_toks:
            continue
        lines = "\n".join(f"{sd['order']}:{t['i']}\t{t['text']}" for t in word_toks)
        blocks.append(
            f"--- Section {sd['order']} \"{sd['title']}\" ---\n"
            f"Key idea: \"{sd['key_idea_text']}\"\nTokens:\n{lines}"
        )
        for t in word_toks:
            expected.add((sd["order"], t["i"]))

    prompt = KEY_IDEA_PROMPT.format(
        article_title=article_title,
        sections_block="\n\n".join(blocks),
    )
    return cached_create(
        client, deployment, AllKeyIdeaMeanings,
        [{"role": "user", "content": prompt}],
        context={"expected_pairs": expected},
    )


# ── Step 3: vocabulary items + quiz ─────────────────────────────

ITEMS_PROMPT = textwrap.dedent("""\
You are selecting vocabulary for a Vietnamese ESL reading app.

ARTICLE: "{title}" (category: {category}, level: {level})

FULL TEXT (sections in reading order):
{combined}

{known_block}

VOCABULARY SELECTION RULES:
1. Select {count_lo}–{count_hi} items a {level} learner should study from this article. \
Each item's cefr_level must be {cefr_a} or {cefr_b} (the article level or one level above): \
skip items that are easier, and skip items that are more than one level harder. \
Required and reused items below are exempt from this level rule.
2. USEFULNESS FIRST: choose items the learner will meet again in other news articles and can \
use in their own speaking and writing (IELTS-style), e.g. "generate electricity", \
"environmental impact", "result in", "make decisions", "food supply", "play a major role in". \
AVOID narrow technical terms that only matter for this topic (e.g. "rotor", "shaft", "nozzle", \
"harvesting machine") — include one only if it is the article's central concept.
3. Prefer collocations / fixed phrases (verb + noun, adjective + noun, verb + preposition, \
noun + of …) whose words commonly go together (type "collocation") over single words.
4. Then add important, reusable single content words not inside any selected collocation \
(type "single_word").
5. NEVER select function words (the, a, in, to, and, but …).
6. No duplicate items within the article.
7. canonical_form must be the base / infinitive form, lowercase; keep a leading "a" only \
when it belongs to the fixed phrase (e.g. "a good source of"). \
The words MUST actually appear in the text above.
8. cefr_level: the level of the WHOLE item (for a phrase: the phrase, not its hardest word). \
If the item is in the KNOWN CEFR LEVELS list, use exactly that level.
9. vi: Vietnamese meaning as used in THIS article.
10. definition_en: clear 1-sentence English definition.
11. extra_example: a new simple sentence using the item, on a DIFFERENT topic.
12. ipa: IPA transcription (American English).

QUIZ — Write exactly 3 questions about the article:
- Allowed types: "true_false", "multiple_choice"{ng_note}.
- question: English. explanation: Vietnamese.
- 2–4 options per question. answer_index is 0-based.\
""")


# items-v3 (BE-06g): cụm cố định thay vì cụm ghép tự do (Q-021), CEFR từ đơn theo từ điển
# (ADR-022), quiz có `evidence` + luật T/F/NG (Q-022). Prompt v2 ở trên giữ nguyên cho bài đã ghim.
ITEMS_PROMPT_V3 = textwrap.dedent("""You are selecting vocabulary for a Vietnamese ESL reading app.

ARTICLE: "{title}" (category: {category}, level: {level})

FULL TEXT (sections in reading order):
{combined}

{known_block}

VOCABULARY SELECTION RULES:
1. Select {count_lo}–{count_hi} items a {level} learner should study from this article. Each item's cefr_level must be {cefr_a} or {cefr_b} (the article level or one level above): skip items that are easier, and skip items that are more than one level harder. Required and reused items below are exempt from this level rule.
2. USEFULNESS FIRST: choose items the learner will meet again in other news articles and can use in their own speaking and writing (IELTS-style). AVOID narrow technical terms that only matter for this topic (e.g. "rotor", "shaft", "nozzle") — include one only if it is the article's central concept.
3. COLLOCATIONS MUST BE FIXED: choose word combinations that learners have to learn as a unit because the words conventionally go together — strong collocations, phrasal verbs, verb + preposition patterns and idioms (e.g. "make a decision", "play a vital role in", "take into account", "result in", "heavy traffic", "keep an eye on"). NEVER select free combinations whose meaning is simply the sum of their words and which a learner could already build from the parts (e.g. "read documents", "search the internet", "cost of driving", "one-way flights", "nonstop flights", "skip flying"). If a free combination contains one useful word, select that word as a single_word instead.
4. Then add important, reusable single content words not inside any selected collocation (type "single_word"). A single word's level comes from the SINGLE-WORD CEFR LEVELS list when it is listed there; a single word that is in the dictionary but not listed is at another level and must not be selected. New or technical words not in the dictionary may be selected with your own estimate.
5. NEVER select function words (the, a, in, to, and, but …).
6. No duplicate items within the article.
7. canonical_form must be the base / infinitive form, lowercase; keep a leading "a" only when it belongs to the fixed phrase (e.g. "a good source of"). The words MUST actually appear in the text above.
8. cefr_level: the level of the WHOLE item (for a phrase: the phrase, not its hardest word). If the item is in the KNOWN CEFR LEVELS or SINGLE-WORD CEFR LEVELS list, use exactly that level.
9. vi: Vietnamese meaning as used in THIS article.
10. definition_en: clear 1-sentence English definition.
11. extra_example: a new simple sentence using the item, on a DIFFERENT topic.
12. ipa: IPA transcription (American English).

QUIZ — Write exactly 3 questions about the article:
- Allowed types: "true_false", "multiple_choice"{ng_note}.
- question: English. explanation: Vietnamese.
- 2–4 options per question. answer_index is 0-based.
- evidence: ONE sentence copied word for word from the text that proves the correct answer. When the answer of a true_false_ng question is "Not Given", evidence must be null.
- True/false statements are about the world, never about the article itself ("The article says…" is not allowed). True = a sentence in the text states the same thing; False = a sentence in the text directly contradicts it; Not Given = no sentence confirms or contradicts it.
- Do not make a statement more general than the text: do not add words like "often", "usually", "always", "most" or "never" unless the text itself says so.
- Do not ask anything whose answer can only be inferred from the writer's tone, a joke, or a legend / story that the text does not present as fact.""")

# items-v4 (BE-06i mục 5): v3 + ưu tiên cụm lặp trong bài, ≥ 40% cụm, quiz có câu False.
# Dựng bằng replace trên v3 để chữ của v3 (2 bài đã ghim) không đổi.
_V3_RULE3_END = "If a free combination contains one useful word, select that word as a single_word instead."
_V3_QUIZ_END = ("- Do not ask anything whose answer can only be inferred from the writer's tone, a joke, "
                "or a legend / story that the text does not present as fact.")
ITEMS_PROMPT_V4 = ITEMS_PROMPT_V3.replace(
    _V3_RULE3_END,
    _V3_RULE3_END + " PREFER fixed phrases that the text uses MORE THAN ONCE (see REPEATED PHRASES, "
    "counted in the text by code; it is only a list of candidates — still skip the free combinations "
    "in it). At least 40% of the items (so at least {coll_min}) must be collocations.",
).replace(
    _V3_QUIZ_END,
    _V3_QUIZ_END + "\n- At least one true/false statement must be FALSE (a sentence in the text directly "
    "contradicts it){ng_false_note}. Do not make all statements true.",
)

# UPOS của token có thể là mục từ đơn (danh/động/tính/trạng từ).
CONTENT_UPOS = {"NOUN", "VERB", "ADJ", "ADV"}
# Cụm lặp: biên trái/phải không được là các loại này (bỏ "of pizza", "in the city", "is often").
_REPEAT_START_BAD = {"ADP", "DET", "CCONJ", "SCONJ", "PRON", "NUM", "PROPN", "PART", "PUNCT", "SYM", "X"}
_REPEAT_END_BAD = {"DET", "CCONJ", "SCONJ", "PRON", "NUM", "PROPN", "AUX", "PART", "ADV", "PUNCT", "SYM", "X"}
_REPEAT_GLUE = {"ADP", "PART", "DET"}


def repeated_phrases(sections_data: list[dict], min_count: int = 2, limit: int = 12,
                     sizes: tuple[int, ...] = (2, 3, 4)) -> list[tuple[str, int]]:
    """Cụm 2-4 từ lặp ≥ `min_count` lần trong bài (khóa = lemma, "be" gộp is/was/are), không vắt qua
    dấu câu, có ≥ 1 từ nội dung. Bỏ cụm con chỉ xuất hiện bên trong cụm dài hơn (cùng số lần).
    Trả [(dạng hiển thị phổ biến nhất, số lần)] theo số lần giảm dần — chỉ là gợi ý cho prompt v4."""
    from collections import Counter, defaultdict
    counts: Counter = Counter()
    shown: dict[str, Counter] = defaultdict(Counter)
    for sd in sections_data:
        runs, cur = [], []
        for t in sd["tokens"]:
            if t["is_word"]:
                cur.append(t)
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        for run in runs:
            for n in sizes:
                for k in range(len(run) - n + 1):
                    g = run[k:k + n]
                    if g[0]["pos"] in _REPEAT_START_BAD or g[-1]["pos"] in _REPEAT_END_BAD:
                        continue
                    if g[0]["pos"] == "AUX" and norm(g[0]["lemma"]) != "be":
                        continue
                    if not any(t["pos"] in CONTENT_UPOS for t in g):
                        continue
                    # Cần ≥ 1 từ chức năng ("topped with", "make a decision"): cụm toàn từ nội dung
                    # ("baked flat bread", "extra cheese", "last year") thường là ghép tự do và kéo LLM
                    # chọn sai luật 3 (thử trên pizza run #98).
                    if not any(t["pos"] in _REPEAT_GLUE for t in g):
                        continue
                    key = " ".join(norm(t["lemma"]) for t in g)
                    counts[key] += 1
                    shown[key][" ".join("be" if norm(t["lemma"]) == "be" else norm(t["text"])
                                        for t in g)] += 1
    rep = {k: c for k, c in counts.items() if c >= min_count}
    keep = [(k, c) for k, c in rep.items()
            if not any(k2 != k and f" {k} " in f" {k2} " and c2 >= c for k2, c2 in rep.items())]
    keep.sort(key=lambda x: (-x[1], -len(x[0].split()), x[0]))
    return [(shown[k].most_common(1)[0][0], c) for k, c in keep[:limit]]


def single_word_levels(sections_data: list[dict], look, cefr_dict: dict,
                       allowed: tuple[str, str]) -> list[tuple[str, str]]:
    """Từ nội dung trong bài có cấp từ điển (cefr_lexicon, không tính cefr.json) nằm trong i+1
    → khối SINGLE-WORD CEFR LEVELS của prompt v3."""
    out: dict[str, str] = {}
    for sd in sections_data:
        for t in sd["tokens"]:
            if not t["is_word"] or t["pos"] not in CONTENT_UPOS:
                continue
            lemma = norm(t["lemma"])
            if not lemma.isalpha() or lemma in out or lemma_key(lemma) in cefr_dict:
                continue
            got = look(lemma, t["pos"], t["text"], use_human=False)
            if got and got[0] in allowed:
                out[lemma] = got[0]
    return sorted(out.items())


def item_dict_level(look):
    """Cấp từ điển của một mục từ đơn (theo `pos` của mục), dùng trong validator v3 + merge."""
    from pipeline.cefr_lexicon import ENTRY_POS_TO_UPOS

    def _level(it) -> Optional[str]:
        form = it.canonical_form.strip()
        upos = ENTRY_POS_TO_UPOS.get(norm(it.pos or ""))
        got = look(lemma_key(form) if " " not in lemma_key(form) else form, upos, form,
                   use_human=False)
        return got[0] if got else None
    return _level


def phrase_floor(look):
    """Quy luật sàn (Q-026): cấp của cụm không thấp hơn từ nội dung khó nhất trong cụm
    (cấp từ lấy từ cefr.json + cefr_lexicon; bỏ từ chức năng và chỗ trống "one's").
    Trả hàm form → (cấp sàn, từ quyết định) | None."""
    def _floor(form: str):
        best = None
        for t in get_nlp()(form):
            if t.pos_ not in CONTENT_UPOS or norm(t.text) in ("one", "'s"):
                continue
            got = look(norm(t.lemma_), t.pos_, t.text)
            if got and (best is None or CEFR_ORDER.index(got[0]) > CEFR_ORDER.index(best[0])):
                best = (got[0], norm(t.text))
        return best
    return _floor


def found_in(sections_data: list[dict], form: str) -> bool:
    return any(locate(sd["tokens"], form) for sd in sections_data)


def reuse_ceiling(level: str) -> str:
    """Cấp cao nhất được tự ép chọn lại: cấp bài + 2 bậc (A2 → B2, B1 → C1, B2 → C2 = không giới hạn)."""
    k = CEFR_ORDER.index(level)
    return CEFR_ORDER[min(k + REUSE_MAX_STEPS_ABOVE, len(CEFR_ORDER) - 1)]


def above_ceiling(cefr: Optional[str], ceiling: Optional[str]) -> bool:
    return bool(ceiling and cefr in CEFR_ORDER and CEFR_ORDER.index(cefr) > CEFR_ORDER.index(ceiling))


def plan_reuse(sections_data, known_entries: list[dict], excluded_items=(),
               required_items=(), cap: int = 4, level: Optional[str] = None,
               ceiling: Optional[str] = None) -> list[str]:
    """Mục từ của bài trước có mặt trong bài này → bắt buộc chọn lại (tối đa `cap`, theo thứ tự
    bài trước), trừ mục người duyệt loại bỏ, đã có trong required_items, DỄ HƠN cấp bài
    (chọn lại "learn" A1 ở bài B1 không giúp gì), hoặc KHÓ HƠN `ceiling` (items-v4: cấp bài + 2,
    vd không ép `in moderation` C1 ở bài A2). Mục khó hơn trong khoảng thì được miễn i+1."""
    skip = {lemma_key(e) for e in (*excluded_items, *required_items)}
    floor = CEFR_ORDER.index(level) if level else 0
    out = []
    for e in known_entries:
        if len(out) >= cap:
            break
        if e.get("dropped") or lemma_key(e["form"]) in skip:
            continue
        if e.get("cefr") in CEFR_ORDER and CEFR_ORDER.index(e["cefr"]) < floor:
            continue
        if above_ceiling(e.get("cefr"), ceiling):
            continue
        if found_in(sections_data, e["form"]):
            out.append(e["form"])
    return out


def select_items_and_quiz(client, deployment, sections_data,
                          article_title, category, level, known_entries: list[dict],
                          required_items=(), excluded_items=(), cefr_dict: Optional[dict] = None,
                          version: str = ITEMS_PROMPT_VERSION,
                          pinned_levels: Optional[list] = None, on_inputs=None):
    """known_entries: [{"form", "cefr"}] của các bài trước (mọi cấp). Trả (ArticleItems, reused_forms).
    pinned_levels: khối KNOWN CEFR LEVELS đã ghim (prompt_pin.json) thay cho cefr_dict hiện tại.
    on_inputs(levels): gọi trước lời gọi LLM (để ghi prompt_pin.json)."""
    cefr_dict = cefr_dict or {}
    combined = "\n\n".join(
        f"### {sd['title']}\n{sd['body']}" for sd in sections_data
    )
    words = sum(len(sd["body"].split()) for sd in sections_data)
    count_lo, count_hi = item_count_range(level, words)
    v4 = version == ITEMS_PROMPT_VERSION
    ceiling = reuse_ceiling(level) if v4 else None
    if v4:  # mục bài trước khó hơn cấp bài + 2 không gợi ý, không ép chọn (ADR-017 bổ sung run #93)
        known_entries = [e for e in known_entries if not above_ceiling(e.get("cefr"), ceiling)]
    reused = plan_reuse(sections_data, known_entries, excluded_items, required_items,
                        cap=max(1, count_hi // 3), level=level, ceiling=ceiling)
    must = list(required_items) + reused
    # Muc bat buoc + tai su dung luon duoc giu: nang tran neu can.
    count_hi = max(count_hi, len(must))
    count_lo = min(count_lo, count_hi)
    cefr_a, cefr_b = allowed_cefr(level)
    if known_entries:
        known_block = (
            "ITEMS FROM EARLIER ARTICLES (any level; re-selecting them helps learners meet "
            "them again — prefer them whenever they genuinely appear in this text):\n"
            + "\n".join(f"- {e['form']} ({e['cefr']})" for e in known_entries)
        )
    else:
        known_block = "(No known entries from earlier articles.)"
    if reused:
        known_block += (
            "\n\nREUSED ITEMS (from earlier articles and found in this text — you MUST include "
            "each one with exactly this canonical_form; exempt from the CEFR rule):\n"
            + "\n".join(f"- {e}" for e in reused)
        )
    if pinned_levels is not None:
        levels_here = [tuple(x) for x in pinned_levels]
        validator_levels = {lemma_key(f): c for f, c in levels_here}
    else:
        levels_here = known_cefr_levels(cefr_dict, sections_data)
        validator_levels = {k: v["cefr"] for k, v in cefr_dict.items()}
    if on_inputs:
        on_inputs(levels_here)
    v3 = version != ITEMS_PROMPT_V2
    extra_ctx: dict = {}
    if v3:
        from pipeline.cefr_lexicon import default_lookup
        look = default_lookup()
        sw = single_word_levels(sections_data, look, cefr_dict, (cefr_a, cefr_b))
        if sw:
            known_block += (
                "\n\nSINGLE-WORD CEFR LEVELS (dictionary: CEFR-J / Octanove) — content words in this "
                f"text at {cefr_a}/{cefr_b}:\n" + ", ".join(f"{w} ({c})" for w, c in sw))
        extra_ctx = {"dict_level": item_dict_level(look),
                     "full_text": "\n".join(sd["body"] for sd in sections_data)}
    if v4:
        extra_ctx["exempt_ceiling"] = ceiling
        rep = repeated_phrases(sections_data)
        if rep:
            known_block += (
                "\n\nREPEATED PHRASES (word sequences used more than once in this text, counted by code; "
                "candidates only):\n" + "\n".join(f"- {p} (×{c})" for p, c in rep))
    if levels_here:
        known_block += (
            "\n\nKNOWN CEFR LEVELS (shared dictionary — use exactly these levels):\n"
            + "\n".join(f"- {f}: {c}" for f, c in levels_here)
        )
    if required_items:
        # Appended only when present so prompts (and cache keys) without overrides stay unchanged.
        known_block += (
            "\n\nREQUIRED ITEMS (chosen by the editor — you MUST include each one, "
            f"with exactly this canonical_form; they count toward the {count_lo}–{count_hi} total "
            "and may be outside the CEFR rule):\n"
            + "\n".join(f"- {e}" for e in required_items)
        )
    if excluded_items:
        known_block += (
            "\n\nEXCLUDED ITEMS (rejected by the editor — do NOT select these):\n"
            + "\n".join(f"- {e}" for e in excluded_items)
        )

    ng_note = ', "true_false_ng"' if level != "A2" else ""
    v4_fmt = {}
    if v4:
        v4_fmt = {"coll_min": -(-4 * count_lo // 10),
                  "ng_false_note": (' (for a true_false_ng question, an answer of "Not Given" also counts)'
                                    if level != "A2" else "")}

    template = ITEMS_PROMPT_V4 if v4 else ITEMS_PROMPT_V3 if v3 else ITEMS_PROMPT
    prompt = template.format(
        title=article_title,
        category=category,
        level=level,
        combined=combined,
        known_block=known_block,
        ng_note=ng_note,
        count_lo=count_lo, count_hi=count_hi, cefr_a=cefr_a, cefr_b=cefr_b, **v4_fmt,
    )
    all_toks = [sd["tokens"] for sd in sections_data]
    res = cached_create(
        client, deployment, ArticleItemsV4 if v4 else ArticleItemsV3 if v3 else ArticleItems,
        [{"role": "user", "content": prompt}],
        context={"locate": locate, "section_tokens": all_toks, "level": level,
                 "count_range": (count_lo, count_hi), "allowed_cefr": (cefr_a, cefr_b),
                 "required_keys": {lemma_key(e): e for e in must},
                 "excluded_keys": {lemma_key(e): e for e in excluded_items},
                 "cefr_dict": validator_levels, **extra_ctx},
        version=version,
    )
    return res, reused


# ── Step 3b: card details (definition, new example, CEFR re-check) ──

DETAILS_PROMPT = textwrap.dedent("""\
You are writing vocabulary cards for Vietnamese learners (article level {level}).
Each card shows: the item, its CEFR level, a short English definition, \
the sentence from the article, and ONE new example sentence.

ITEMS (canonical_form — type — Vietnamese meaning in the article — article sentence):
{lines}

For EACH item return:
1. canonical_form — exactly as given.
2. cefr_level — the level at which learners typically meet THIS item, following the \
English Vocabulary Profile. For a collocation or phrase, judge the phrase as a unit \
(e.g. "tend to" is B1 even though "tend" and "to" are easy). Be conservative; \
do not raise the level just because the topic is technical.
3. definition_en — learner-dictionary style (Cambridge / Oxford Learner's), \
max {max_def} words, simpler words than the item itself, same sense as in the article.
4. extra_example — ONE new, natural sentence (max {max_ex} words) that contains the item \
itself (inflection allowed), shows typical usage, uses the SAME sense as in the article, \
is on a DIFFERENT topic, and is no harder than {level} level. Must not reuse the article sentence.\
""")
# details-v2 (BE-06i mục 6, Q-029: `crust` "soft interior" ở bài A2): nói rõ từng từ của ví dụ.
_DETAILS_V1_EX = "is no harder than {level} level."
DETAILS_PROMPT_V2 = DETAILS_PROMPT.replace(
    _DETAILS_V1_EX,
    "uses ONLY words at or below {level} level apart from the item itself (no harder synonyms, "
    "no technical or literary words).")
DETAILS_PROMPTS = {DETAILS_PROMPT_V1: DETAILS_PROMPT, DETAILS_PROMPT_VERSION: DETAILS_PROMPT_V2}


def describe_entries(client, deployment, items, originals: dict[str, str], level: str,
                     version: str = DETAILS_PROMPT_V1, look=None):
    """Bước 4b. v1 giữ đúng prompt + khóa cache cũ (10 bài đã duyệt); v2 thêm luật từ ≤ cấp bài +
    validator `example_words_above` (cần `look`, mặc định từ điển CEFR dùng chung)."""
    lines = "\n".join(
        f"- {it.canonical_form} — {it.type} — {it.vi} — \"{originals.get(it.canonical_form, '')}\""
        for it in items
    )
    prompt = DETAILS_PROMPTS[version].format(level=level, lines=lines,
                                             max_def=DEFINITION_MAX_WORDS, max_ex=EXAMPLE_MAX_WORDS)
    context = {"forms": [it.canonical_form for it in items], "originals": originals}
    if version != DETAILS_PROMPT_V1:
        if look is None:
            from pipeline.cefr_lexicon import default_lookup
            look = default_lookup()
        context.update(example_level=level, example_look=look)
    return cached_create(
        client, deployment, EntryDetails,
        [{"role": "user", "content": prompt}],
        context=context, version=version,
    )


def clean_llm_ipa(ipa: Optional[str]) -> Optional[str]:
    """IPA do LLM sinh theo cùng quy ước CMUdict (ADR-017, run #38): không dấu dài ː/ˑ, có /…/."""
    if not ipa:
        return ipa
    body = ipa.strip().strip("/[]").replace("ː", "").replace("ˑ", "").strip()
    return f"/{body}/" if body else None


def merge_entry_details(items, details: EntryDetails, overrides: "Overrides",
                        cefr_dict: Optional[dict] = None,
                        dict_level=None, floor=None) -> tuple[dict, list[str]]:
    """canonical_form → {cefr_level, ipa, definition_en, extra_example, cefr_note}.
    CEFR: overrides.lexicon > từ điển dùng chung (pipeline/data/cefr.json) > [v3: cefr_lexicon
    cho từ đơn (dict_level)] > bước 3b > bước 3.
    IPA: CMUdict > LLM. Định nghĩa: chuẩn hóa một kiểu viết (normalize_definition)."""
    cefr_dict = cefr_dict or {}
    by_form = {d.canonical_form: d for d in details.entries}
    ov_by_key = {lemma_key(f): o for f, o in overrides.lexicon.items()}
    out: dict[str, dict] = {}
    applied: list[str] = []
    for it in items:
        d = by_form[it.canonical_form]
        ipa = phrase_ipa(it.canonical_form)
        entry = {
            "cefr_level": d.cefr_level,
            "ipa": ipa or clean_llm_ipa(it.ipa),
            "ipa_source": "cmudict" if ipa else "llm",
            "definition_en": normalize_definition(d.definition_en),
            "extra_example": d.extra_example,
            "cefr_note": "" if d.cefr_level == it.cefr_level
            else f"lần 1: {it.cefr_level}, lần 2: {d.cefr_level}",
        }
        known = cefr_dict.get(lemma_key(it.canonical_form))
        if known:
            entry["cefr_level"] = known["cefr"]
            entry["cefr_note"] = f"từ điển ({known['source']})"
        elif dict_level and " " not in it.canonical_form.strip():
            lvl = dict_level(it)
            if lvl:
                entry["cefr_level"] = lvl
                entry["cefr_note"] = "từ điển (cefr_lexicon)"
        elif floor and " " in it.canonical_form.strip():
            got = floor(it.canonical_form)
            if got and CEFR_ORDER.index(entry["cefr_level"]) < CEFR_ORDER.index(got[0]):
                entry["cefr_note"] = (f"llm+floor: LLM {entry['cefr_level']}, "
                                      f"sàn {got[0]} theo '{got[1]}'")
                entry["cefr_level"] = got[0]
        ov = ov_by_key.get(lemma_key(it.canonical_form))
        if ov:
            for field, val in ov.model_dump(exclude_none=True, exclude=_LEX_NON_ENTRY).items():
                if field == "definition_en":
                    val = normalize_definition(val)
                old = entry.get(field, getattr(it, field, None))
                applied.append(f"{it.canonical_form}.{field}: \"{old}\" → \"{val}\"")
                entry[field] = val
                if field == "cefr_level":
                    entry["cefr_note"] = "sửa tay"
                if field == "ipa":
                    entry["ipa_source"] = "sửa tay"
        out[it.canonical_form] = entry
    known = {lemma_key(it.canonical_form) for it in items}
    for form in overrides.lexicon:
        if lemma_key(form) not in known:
            raise ValueError(f"override lexicon: '{form}' không phải mục từ đã chọn")
    return out, applied


def apply_vi_overrides(items, occurrences: list[dict], overrides: "Overrides") -> list[str]:
    """overrides.lexicon[*].vi → item.vi (cho review.md) và occurrence.vi (cho bundle).
    Gọi SAU bước 4b: prompt 4b có chứa item.vi, đổi trước sẽ làm lỡ cache."""
    ov_by_key = {lemma_key(f): o.vi for f, o in overrides.lexicon.items() if o.vi}
    applied: list[str] = []
    for it in items:
        vi = ov_by_key.get(lemma_key(it.canonical_form))
        if not vi:
            continue
        applied.append(f"{it.canonical_form}.vi: \"{it.vi}\" → \"{vi}\"")
        it.vi = vi
        lex_id = item_to_lex_id(it.canonical_form)
        for occ in occurrences:
            if occ["lexicon_entry_id"] == lex_id:
                occ["vi"] = vi
    return applied


# ── Step 4: locate items in tokens ──────────────────────────────

def locate_items(items: list[SelectedItem], sections_data: list[dict]):
    """Return (occurrences_list, unlocated_canonical_forms)."""
    occurrences: list[dict] = []
    unlocated: list[str] = []
    counter = 1

    for item in items:
        found = False
        lex_id = item_to_lex_id(item.canonical_form)
        for sd in sections_data:
            for start, end in locate(sd["tokens"], item.canonical_form):
                found = True
                sent = extract_sentence(sd["tokens"], start, end)
                cloze = sentence_cloze(sd["tokens"], start, end)
                occurrences.append({
                    "id": f"occ_{sd['slug_under']}_{counter}",
                    "lexicon_entry_id": lex_id,
                    "section_id": sd["section_id"],
                    "token_start": start,
                    "token_end": end,
                    "vi": item.vi,
                    "example_sentence": sent,
                    "cloze": cloze,
                })
                counter += 1
        if not found:
            unlocated.append(item.canonical_form)

    return occurrences, unlocated


# ── Step 5: assemble bundle ─────────────────────────────────────

def collocation_word_ipas(items, details: dict) -> dict[str, str]:
    """{từ viết thường: "/ipa/"} lấy từ thẻ cụm khi số từ của dạng chuẩn bằng số đoạn IPA.
    Bỏ chỗ trống sở hữu (`one's`) và cụm lệch số đoạn (không đoán)."""
    out: dict[str, str] = {}
    for it in items:
        d = details[it.canonical_form]
        ipa = (d.get("ipa") or "").strip().strip("/").strip()
        if d.get("type", it.type) != "collocation" or not ipa:
            continue
        words, parts = it.canonical_form.lower().split(), ipa.split()
        if len(words) != len(parts):
            continue
        for w, p in zip(words, parts):
            if w != "one's" and w.isalpha():
                out.setdefault(w, f"/{p}/")
    return out


def build_bundle(slug, title, category, level, source_name, source_graded,
                 sections_data, items, quiz_responses, occurrences, details: dict,
                 excerpt: Optional[str] = None):
    slug_under = slug.replace("-", "_")

    sections = []
    for sd in sections_data:
        tokens_out = add_token_ipa(apply_meanings(sd["tokens"], sd["meanings"]))
        ki_tokens_out = add_token_ipa(apply_meanings(sd["key_idea_tokens"], sd["key_idea_meanings"]))
        sections.append({
            "id": sd["section_id"],
            "order_index": sd["order"],
            "title": sd["title"],
            "icon_hint": sd["icon_hint"],
            "tokens": tokens_out,
            "key_idea": {"text": sd["key_idea_text"], "tokens": ki_tokens_out},
            "check": sd.get("check"),
        })

    # Token chưa có IPA (CMUdict không có, vd "chatbot") mà là từ đơn có thẻ → dùng IPA của thẻ.
    card_ipa = {lemma_key(it.canonical_form): details[it.canonical_form]["ipa"] for it in items
                if details[it.canonical_form].get("type", it.type) == "single_word"
                and details[it.canonical_form].get("ipa")}
    # Thẻ cụm (BE-06i, vd "preheat oven" /ˌpriˈhit ˈʌvən/): số từ khớp số đoạn IPA → IPA từng từ.
    for word, ipa in collocation_word_ipas(items, details).items():
        card_ipa.setdefault(word, ipa)
    for sec in sections:
        for t in sec["tokens"] + sec["key_idea"]["tokens"]:
            if t["is_word"] and not t.get("ipa"):
                t["ipa"] = card_ipa.get(t["lemma"].lower()) or card_ipa.get(t["text"].lower())

    seen_lex: set[str] = set()
    lexicon = []
    for item in items:
        lid = item_to_lex_id(item.canonical_form)
        if lid in seen_lex:
            continue
        seen_lex.add(lid)
        d = details[item.canonical_form]
        lexicon.append({
            "id": lid,
            "canonical_form": d.get("canonical_form", item.canonical_form),
            "lemma_key": lemma_key(item.canonical_form),
            "type": d.get("type", item.type),
            "pos": d.get("pos", item.pos),
            "cefr_level": d["cefr_level"],
            "ipa": d["ipa"],
            "definition_en": d["definition_en"],
            "extra_example": d["extra_example"],
            "audio_url": None,
        })

    quiz = []
    for n, q in enumerate(quiz_responses, 1):
        quiz.append({
            "id": f"q_{slug_under}_{n}",
            "type": q.type,
            "question": q.question,
            "options": q.options,
            "answer_index": q.answer_index,
            "explanation": q.explanation,
        })

    total_words = sum(count_words(sd["tokens"]) for sd in sections_data)

    return {
        "contract_version": CONTRACT_VERSION,
        "article": {
            "id": f"art_{slug_under}",
            "title": title,
            "category": category,
            "cefr_level": level,
            "source": {"name": source_name, "is_graded": source_graded},
            "word_count": total_words,
            "section_count": len(sections),
            # cover_url: bundle giữ null như audio_url; pipeline.seed điền URL của đúng nơi đang seed.
            "cover_url": None,
            "excerpt": excerpt if excerpt is not None else (
                article_excerpt(min(sections, key=lambda s: s["order_index"])["tokens"]) if sections else None),
        },
        "sections": sections,
        "lexicon": lexicon,
        "occurrences": occurrences,
        "quiz": quiz,
    }


# ── Step 6: review.md ──────────────────────────────────────────

def write_review(path: pathlib.Path, slug: str, bundle: ArticleBundle,
                 unlocated: list[str], known_keys: set[str],
                 overrides_applied: list[str] = (), required_items: list[str] = (),
                 excluded_items: list[str] = (), details: Optional[dict] = None,
                 lexicon_applied: list[str] = (), reused: list[str] = (),
                 glossary_report: Optional[dict] = None, extra_applied: list[str] = (),
                 items_version: str = ITEMS_PROMPT_VERSION,
                 quiz_evidence: Optional[list] = None, quiz_edited=frozenset(),
                 section_version: str = SECTION_PROMPT_VERSION,
                 details_version: str = DETAILS_PROMPT_V1):
    coll = sum(1 for e in bundle.lexicon if e.type == "collocation")
    lines = [
        f"# Duyệt: {slug} ({bundle.article.cefr_level}, {bundle.article.category})"
        f" — prompt {section_version} / {items_version}"
        + (f" / {details_version} · cụm {coll}/{len(bundle.lexicon)}"
           if details_version != DETAILS_PROMPT_V1 else ""),
        "",
        "## 1. CẦN XỬ LÝ TAY",
    ]
    if unlocated:
        for form in unlocated:
            lines.append(f"- KHÔNG ĐỊNH VỊ ĐƯỢC: \"{form}\" — sửa canonical_form hoặc xóa mục")
    glossary_report = glossary_report or {}
    missing = glossary_report.get("missing", [])
    for m in missing:
        lines.append(f"- GLOSSARY CHƯA CÓ NGHĨA (chỉ có nhãn): {m} — sửa bằng `overrides.json` → `meanings`")
    if not unlocated and not missing:
        lines.append("- Không có")
    if overrides_applied or required_items or excluded_items or lexicon_applied or extra_applied:
        lines += ["", "**Đã áp dụng từ `overrides.json` (và gộp token tự động):**"]
        lines += [f"- Mục từ bắt buộc: {form}" for form in required_items]
        lines += [f"- Mục từ loại bỏ: {form}" for form in excluded_items]
        lines += [f"- Nghĩa: {a}" for a in overrides_applied]
        lines += [f"- Thẻ: {a}" for a in lexicon_applied]
        lines += [f"- {a}" for a in extra_applied]

    lines += ["", "## 2. Key idea (kiểm kỹ)",
              "| Section | Key idea | OK? |", "|---|---|---|"]
    for s in bundle.sections:
        lines.append(f"| {s.order_index}. {s.title} | {s.key_idea.text} | |")

    n_reused = sum(1 for e in bundle.lexicon if e.lemma_key in known_keys)
    lines += [
        "",
        f"## 3. Mục từ (kiểm kỹ) — tái sử dụng: {n_reused}/{len(bundle.lexicon)}"
        + (f" (bắt buộc chọn lại: {', '.join(reused)})" if reused else ""),
        "| canonical_form | type | vi | câu gốc | tái sử dụng | OK? |",
        "|---|---|---|---|---|---|",
    ]
    lex_by_id = {e.id: e for e in bundle.lexicon}
    shown_lex: set[str] = set()
    for occ in bundle.occurrences:
        entry = lex_by_id.get(occ.lexicon_entry_id)
        if not entry or entry.id in shown_lex:
            continue
        shown_lex.add(entry.id)
        reuse_mark = "✓" if entry.lemma_key in known_keys else ""
        ex = occ.example_sentence
        if len(ex) > 60:
            ex = ex[:57] + "…"
        lines.append(
            f"| {entry.canonical_form} | {entry.type} | {occ.vi} "
            f"| {ex} | {reuse_mark} | |"
        )

    details = details or {}
    lines += [
        "",
        "## 3b. Thẻ mục từ (kiểm kỹ CEFR có ⚠, IPA nguồn llm, ví dụ mới)",
        "Sửa bằng `overrides.json` → `lexicon` → `{\"<canonical_form>\": {\"cefr_level\": \"B1\", ...}}`.",
        "",
    ]
    level = bundle.article.cefr_level
    ok_cefr = allowed_cefr(level)
    for e in bundle.lexicon:
        d = details.get(e.canonical_form, {})
        note = d.get("cefr_note", "")
        if note.startswith("từ điển"):
            cefr = f"{e.cefr_level} ({note})"
        elif note and note != "sửa tay":
            cefr = f"{e.cefr_level} ⚠ ({note})"
        else:
            cefr = e.cefr_level
        if e.cefr_level not in ok_cefr:
            cefr += f" ⚠ ngoài i+1 (bài {level}: {'/'.join(ok_cefr)})"
        lines += [
            f"**{e.canonical_form}** · {e.type} · {e.pos} · {cefr}",
            f"- IPA: {e.ipa or '(trống)'}" + (f" — nguồn {d['ipa_source']}" if d.get("ipa_source") else ""),
            f"- Định nghĩa: {e.definition_en}",
            f"- Ví dụ mới: {e.extra_example}",
            "",
        ]
    no_ipa = sorted({t.text.lower() for s in bundle.sections for t in s.tokens + s.key_idea.tokens
                     if t.is_word and not t.ipa})
    lines.append(f"**Token không có IPA ({len(no_ipa)}, app ẩn dòng IPA):** "
                 + (", ".join(no_ipa) if no_ipa else "không có"))

    lines += ["", "## 4. Quick Check + Quiz (kiểm kỹ)", ""]
    has_check = False
    for s in bundle.sections:
        if s.check:
            has_check = True
            lines.append(f"**Section {s.order_index} — Quick Check:**")
            lines.append(f"- Q: {s.check.question}")
            for k, opt in enumerate(s.check.options):
                mark = " ✓" if k == s.check.answer_index else ""
                lines.append(f"  - [{k}] {opt}{mark}")
            lines.append(f"- Giải thích: {s.check.explanation}")
            lines.append("")
    if not has_check:
        lines.append("*(Không có Quick Check — các section đều < 120 từ)*")
        lines.append("")

    lines.append("**Quiz:**")
    for qi, q in enumerate(bundle.quiz, start=1):
        lines.append(f"- [{q.type}] {q.question}")
        for k, opt in enumerate(q.options):
            mark = " ✓" if k == q.answer_index else ""
            lines.append(f"  - [{k}] {opt}{mark}")
        lines.append(f"  Giải thích: {q.explanation}")
        if quiz_evidence is not None:
            if qi in quiz_edited:
                lines.append("  Bằng chứng: (câu đã sửa tay — tự kiểm lại với bài)")
            else:
                ev = quiz_evidence[qi - 1] if qi - 1 < len(quiz_evidence) else None
                lines.append(f"  Bằng chứng: {ev or '(không có — Not Given)'}")

    rng = random.Random(slug)
    all_word_tokens = []
    for s in bundle.sections:
        for t in s.tokens:
            if t.is_word:
                all_word_tokens.append((s.id, t))
    sample = rng.sample(all_word_tokens, min(15, len(all_word_tokens)))
    sample.sort(key=lambda x: (x[0], x[1].i))

    lines += [
        "",
        "## 5. Glossary (kiểm ngẫu nhiên 15 token)",
        "| section | i | token | vi |",
        "|---|---|---|---|",
    ]
    for sid, t in sample:
        lines.append(f"| {sid} | {t.i} | {t.text} | {t.vi} |")

    defaults = glossary_report.get("default", [])
    cleaned = glossary_report.get("cleaned", [])
    lines += ["", f"**Từ chức năng đã chuẩn hóa:** {len(cleaned)} bỏ ngoặc/nhãn, "
              f"{len(defaults)} dùng nghĩa mặc định, {len(missing)} chưa có nghĩa (mục 1)."]
    if defaults:
        lines.append("Nghĩa mặc định (xem lướt): " + "; ".join(sorted(set(defaults))))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── CLI ─────────────────────────────────────────────────────────

RUN_ARG_KEYS = ("level", "category", "source_name", "source_graded", "title")


def cmd_run(args):
    global CACHE_ONLY
    CACHE_ONLY = bool(args.cache_only)
    slug = args.slug
    old_pin = load_pin(slug)
    pin = None if args.write_pin else old_pin
    # Ghim lại bài cũ (--write-pin) giữ version bước 1 của pin cũ; bài mới dùng bản hiện tại.
    section_version = pinned_section_version(old_pin)
    details_version = pinned_details_version(old_pin)
    # Bài đã ghim: tham số chạy lấy từ pin khi không truyền trên dòng lệnh.
    for k in RUN_ARG_KEYS:
        if getattr(args, k) is None and pin:
            setattr(args, k, pin["run_args"].get(k))
    missing = [k for k in ("level", "category", "source_name") if not getattr(args, k)]
    if missing:
        print(f"ERROR: thiếu --{', --'.join(m.replace('_', '-') for m in missing)} "
              f"(bài chưa có {PIN_FILE})", file=sys.stderr)
        sys.exit(1)
    level = args.level
    category = args.category
    source_name = args.source_name
    source_graded = bool(args.source_graded)
    items_version = (pin["items_prompt_version"] if pin
                     else args.write_pin if args.write_pin else ITEMS_PROMPT_VERSION)

    norm_path = OUT / slug / "normalized_sections.json"
    if not norm_path.exists():
        print(f"ERROR: {norm_path} khong tim thay. Chay extract truoc.", file=sys.stderr)
        sys.exit(1)

    norm = json.loads(norm_path.read_text("utf-8-sig"))
    raw_sections = norm["sections"]

    cefr_dict = load_cefr_dict()
    if args.known_entries:
        forms = json.loads(pathlib.Path(args.known_entries).read_text("utf-8"))
        known_entries = [{"form": f, "cefr": cefr_dict.get(lemma_key(f), {}).get("cefr", "?")}
                         for f in forms]
    else:
        known_entries = collect_known_entries(slug)
    if pin:
        known_entries = pinned_known_entries(pin, known_entries)
        print(f"  {PIN_FILE}: {items_version} / {section_version} / {details_version}, "
              f"{len(known_entries)} known_entries, "
              f"{len(pin['known_cefr_levels'])} CEFR ghim")
    known_keys = {lemma_key(e["form"]) for e in known_entries}
    print(f"  known_entries: {len(known_entries)} mục từ bài trước · từ điển CEFR: {len(cefr_dict)} mục")
    extra_applied: list[str] = []

    overrides = load_overrides(OUT / slug / "overrides.json")
    # Prompt LLM giữ tiêu đề cũ (nằm trong prompt → đổi sẽ trượt cache, sinh lại nội dung đã duyệt);
    # overrides.title chỉ áp vào bundle.
    title = args.title or normalize_title(norm["title"])
    bundle_title = resolve_title(norm["title"], args.title, overrides)
    if bundle_title != title:
        extra_applied.append(f"Tiêu đề bài: '{title}' → '{bundle_title}' (chỉ bundle, prompt giữ tiêu đề cũ)")
    if (overrides.required_items or overrides.excluded_items or overrides.meanings
            or overrides.lexicon):
        print(f"  overrides.json: {len(overrides.required_items)} mục bắt buộc, "
              f"{len(overrides.excluded_items)} mục loại bỏ, "
              f"{len(overrides.meanings)} nghĩa sửa tay, "
              f"{len(overrides.lexicon)} thẻ sửa tay")

    client, deployment = get_text_client()
    slug_under = slug.replace("-", "_")

    print(f"Enrich {slug} ({level}, {category})")
    print(f"  Title: \"{title}\"  |  {len(raw_sections)} sections")
    print()

    # ── Step 1: tokenize + section enrichment ───────────────────
    sections_data: list[dict] = []
    for sec in raw_sections:
        order = sec["order"]
        sec_title = normalize_title(sec["title"])
        body = sec["body"]
        icon_hint = sec["icon_hint"]
        section_id = f"sec_{slug_under}_{order}"

        print(f"  [{order}] \"{sec_title}\" ... ", end="", flush=True)
        tokens = tokenize(body, with_tags=True)
        enrichment = enrich_section(
            client, deployment, tokens, sec_title, title, level, body,
            version=section_version,
        )
        ki_tokens = tokenize(enrichment.key_idea, with_tags=True)
        wc = count_words(tokens)
        print(f"{wc}w | key: \"{enrichment.key_idea}\"")
        # Gộp mã kiểu R2-D2 SAU lời gọi LLM (prompt giữ nguyên → cache đã duyệt còn dùng được).
        merged_tokens, merged_meanings, merged_notes = merge_codes_with_meanings(
            tokens, {m.i: m.vi for m in enrichment.meanings})
        extra_applied += [f"Gộp token sec {order}: {n}" for n in merged_notes]

        sections_data.append({
            "order": order,
            "title": sec_title,
            "body": body,
            "icon_hint": icon_hint,
            "section_id": section_id,
            "slug_under": slug_under,
            "tokens": merged_tokens,
            "meanings": merged_meanings,
            "key_idea_text": enrichment.key_idea,
            "key_idea_tokens": ki_tokens,
            "key_idea_meanings": {},
            "check": enrichment.check.model_dump() if enrichment.check else None,
        })

    extra_applied += [f"Key idea {a}" for a in apply_key_idea_overrides(sections_data, overrides)]
    extra_applied += [f"Quick Check {a}" for a in cap_quick_checks(sections_data)]
    extra_applied += [f"Quick Check {a}" for a in apply_quick_check_overrides(sections_data, overrides)]

    # ── Step 2: key-idea meanings ───────────────────────────────
    print("\n  Key idea meanings ... ", end="", flush=True)
    ki_result = enrich_key_ideas(client, deployment, sections_data, title)
    for m in ki_result.meanings:
        for sd in sections_data:
            if sd["order"] == m.section_order:
                sd["key_idea_meanings"][m.i] = m.vi
                break
    print("OK")

    # ── Step 3: items + quiz ────────────────────────────────────
    print("  Items + quiz ... ", end="", flush=True)
    def _pin_inputs(levels):
        if args.write_pin:
            run_args = {"level": level, "category": category, "source_name": source_name,
                        "source_graded": source_graded, "title": args.title}
            f = write_pin(slug, items_version, run_args, known_entries, levels,
                          section_version=section_version, details_version=details_version)
            print(f"(ghim → {f}) ", end="", flush=True)

    article_items, reused = select_items_and_quiz(
        client, deployment, sections_data, title, category, level, known_entries,
        overrides.required_items, overrides.excluded_items, cefr_dict,
        version=items_version,
        pinned_levels=pin["known_cefr_levels"] if pin else None, on_inputs=_pin_inputs,
    )
    # Quy ước glossary (từ chức năng) trước, override của người duyệt sau cùng nên luôn thắng.
    glossary_report: dict[str, list[str]] = {"cleaned": [], "default": [], "missing": []}
    for sd in sections_data:
        for toks, mean in ((sd["tokens"], sd["meanings"]),
                           (sd["key_idea_tokens"], sd["key_idea_meanings"])):
            for k, v in normalize_glossary(toks, mean).items():
                glossary_report[k] += [f"sec {sd['order']} · {x}" for x in v]
    overrides_applied = apply_meaning_overrides(sections_data, overrides)
    overridden = {(o.section_order, o.text) for o in overrides.meanings}
    glossary_report["missing"] = [m for m in glossary_report["missing"]
                                  if not any(m.startswith(f"sec {s} · {t}:") for s, t in overridden)]
    print(f"{len(article_items.items)} items ({len(reused)} tái sử dụng), {len(article_items.quiz)} quiz")

    # ── Step 4: locate ──────────────────────────────────────────
    print("  Locate ... ", end="", flush=True)
    quiz_evidence = [getattr(q, "evidence", None) for q in article_items.quiz]
    quiz_items, quiz_applied = apply_quiz_overrides(article_items.quiz, overrides)
    extra_applied += [f"Quiz {a}" for a in quiz_applied]
    occurrences, unlocated = locate_items(article_items.items, sections_data)
    occurrences, excl_applied = apply_occurrence_exclusions(occurrences, overrides)
    extra_applied += [f"Bỏ vị trí {a}" for a in excl_applied]
    print(f"{len(occurrences)} occ, {len(unlocated)} unlocated")

    # ── Step 4b: card details (needs article sentences from locate) ──
    print("  Card details ... ", end="", flush=True)
    lex_to_form = {item_to_lex_id(it.canonical_form): it.canonical_form for it in article_items.items}
    originals = pick_originals(occurrences, lex_to_form, overrides)
    entry_details = describe_entries(client, deployment, article_items.items, originals, level,
                                     version=details_version)
    v3_level = v3_floor = None
    if items_version != ITEMS_PROMPT_V2:
        from pipeline.cefr_lexicon import default_lookup
        v3_level = item_dict_level(default_lookup())
        v3_floor = phrase_floor(default_lookup())
    details, lexicon_applied = merge_entry_details(article_items.items, entry_details, overrides,
                                                   cefr_dict, v3_level, v3_floor)
    lexicon_applied += apply_vi_overrides(article_items.items, occurrences, overrides)
    lexicon_applied += apply_shared_cards(article_items.items, details, known_entries, overrides)
    selected_items = [{"form": it.canonical_form, "cefr": details[it.canonical_form]["cefr_level"]}
                      for it in article_items.items]
    article_items.items, occurrences, drop_applied = apply_drop_items(
        article_items.items, occurrences, details, overrides)
    lexicon_applied += drop_applied
    flagged = [f for f, d in details.items()
               if d["cefr_note"] and d["cefr_note"] != "sửa tay"
               and not d["cefr_note"].startswith(("từ điển", "thẻ dùng chung"))]
    print(f"OK ({len(flagged)} CEFR cần xem)")

    # ── Step 5: assemble + validate ─────────────────────────────
    print("  Bundle ... ", end="", flush=True)
    bundle_data = build_bundle(
        slug, bundle_title, category, level, source_name, source_graded,
        sections_data, article_items.items, quiz_items, occurrences, details,
        excerpt=overrides.excerpt,
    )
    if overrides.excerpt:
        extra_applied.append(f"Đoạn trích sửa tay: \"{overrides.excerpt}\"")
    bundle = ArticleBundle.model_validate(bundle_data)
    print("OK (model_validate pass)")

    out_dir = OUT / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle_path = out_dir / "bundle.json"
    bundle_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    print(f"  -> {bundle_path}")
    (out_dir / SELECTED_ITEMS_FILE).write_text(
        json.dumps(selected_items, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Step 6: review report ───────────────────────────────────
    review_path = out_dir / "review.md"
    write_review(review_path, slug, bundle, unlocated, known_keys,
                 overrides_applied, overrides.required_items, overrides.excluded_items,
                 details, lexicon_applied, reused, glossary_report, extra_applied,
                 items_version=items_version,
                 quiz_evidence=None if items_version == ITEMS_PROMPT_V2 else quiz_evidence,
                 quiz_edited=set(overrides.quiz), section_version=section_version,
                 details_version=details_version)
    print(f"  -> {review_path}")

    # ── Summary ─────────────────────────────────────────────────
    a = bundle.article
    checks = sum(1 for s in bundle.sections if s.check)
    print(f"\nOK — {a.section_count} section · {a.word_count} tu · "
          f"{len(bundle.lexicon)} muc tu · {len(bundle.occurrences)} occurrence · "
          f"{checks} quick check · {len(bundle.quiz)} quiz")
    if unlocated:
        print(f"\n⚠ KHONG DINH VI DUOC: {', '.join(unlocated)}")
        print("  Sua canonical_form hoac xoa muc trong bundle.json")


def main():
    p = argparse.ArgumentParser(prog="pipeline.enrich",
                                description="BE-03: tokenize + enrich + locate + bundle")
    sub = p.add_subparsers(dest="cmd")

    run = sub.add_parser("run", help="Full pipeline run")
    run.add_argument("--slug", required=True)
    run.add_argument("--level", default=None, choices=["A2", "B1", "B2"],
                     help=f"bắt buộc nếu bài chưa có {PIN_FILE}")
    run.add_argument("--category", default=None)
    run.add_argument("--source-name", default=None)
    run.add_argument("--source-graded", action="store_true", default=None)
    run.add_argument("--cache-only", action="store_true",
                     help="trượt cache thì dừng (không gọi API, không ghi bundle)")
    run.add_argument("--write-pin", default=None, metavar="ITEMS_VERSION",
                     choices=list(ITEMS_VERSIONS),
                     help=f"ghi {PIN_FILE} từ đầu vào hiện tại (bài đã duyệt: items-v2), bỏ qua pin cũ")
    run.add_argument("--title", default=None, help="Override article title")
    run.add_argument("--known-entries", default=None,
                     help="JSON file with list of canonical_forms from earlier articles "
                          "(mặc định: lấy từ bundle.json các bài đứng trước trong "
                          "pipeline/out/processing_order.json)")

    args = p.parse_args()
    if args.cmd == "run":
        cmd_run(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
