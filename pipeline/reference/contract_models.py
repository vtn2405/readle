"""
Pydantic models cho ArticleBundle contract v1.

Nguồn sự thật của contract là docs/CONTRACTS.md. File này phải khớp với tài liệu đó.
Mọi bundle do pipeline sinh ra phải qua `ArticleBundle.model_validate(...)`
và `check_bundle_invariants(...)` trước khi seed vào Supabase.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator

CONTRACT_VERSION = "1.4"
DEFINITION_MAX_WORDS = 15


class Token(BaseModel):
    i: int = Field(ge=0, description="Vị trí token trong section, bắt đầu từ 0, liên tục")
    text: str
    ws: str = Field(description="Khoảng trắng ngay sau token ('' hoặc ' ' ...). App render text + ws")
    lemma: str
    pos: str
    is_word: bool = Field(description="False với dấu câu; token không phải word thì không chạm được")
    is_fn: bool = Field(description="Từ chức năng (DET, ADP, AUX, CCONJ, SCONJ, PART, PRON)")
    vi: Optional[str] = Field(default=None, description="Nghĩa theo ngữ cảnh; bắt buộc khi is_word")
    ipa: Optional[str] = Field(default=None, description="IPA (US) của lemma; null với dấu câu / từ không tra được (1.1)")


class KeyIdea(BaseModel):
    text: str
    tokens: list[Token]


class QuickCheck(BaseModel):
    question: str
    options: list[str] = Field(min_length=2, max_length=4)
    answer_index: int = Field(ge=0)
    explanation: str


class Section(BaseModel):
    id: str
    order_index: int = Field(ge=0)
    title: str
    icon_hint: str
    tokens: list[Token]
    key_idea: KeyIdea
    check: Optional[QuickCheck] = None


class Source(BaseModel):
    name: str
    is_graded: bool


class Article(BaseModel):
    id: str
    title: str
    category: str
    cefr_level: Literal["A2", "B1", "B2"]
    source: Source
    word_count: int
    section_count: int


class LexiconEntry(BaseModel):
    id: str
    canonical_form: str
    lemma_key: str
    type: Literal["single_word", "collocation"]
    pos: str
    cefr_level: str
    ipa: Optional[str] = None
    definition_en: Optional[str] = None
    extra_example: Optional[str] = None
    audio_url: Optional[str] = None


class Cloze(BaseModel):
    text_before: str
    answer: str
    text_after: str


class Occurrence(BaseModel):
    id: str
    lexicon_entry_id: str
    section_id: str
    token_start: int = Field(ge=0)
    token_end: int = Field(ge=0, description="Bao gồm (inclusive)")
    vi: str
    example_sentence: str
    cloze: Cloze


class QuizItem(BaseModel):
    id: str
    type: Literal["true_false", "multiple_choice", "true_false_ng"]
    question: str
    options: list[str] = Field(min_length=2, max_length=4)
    answer_index: int = Field(ge=0)
    explanation: str


class ArticleBundle(BaseModel):
    # 1.2, 1.3 chỉ đổi event audio_played (ADR-013, ADR-014); 1.4 chỉ đổi bảng người dùng + event
    # word_saved (ADR-019). Dữ liệu bundle giống 1.1 nên chấp nhận cả bốn.
    contract_version: Literal["1.1", "1.2", "1.3", "1.4"] = CONTRACT_VERSION
    article: Article
    sections: list[Section]
    lexicon: list[LexiconEntry]
    occurrences: list[Occurrence]
    quiz: list[QuizItem] = Field(max_length=3)

    @model_validator(mode="after")
    def _invariants(self) -> "ArticleBundle":
        check_bundle_invariants(self)
        return self


def check_bundle_invariants(b: ArticleBundle) -> None:
    """Các luật mà kiểu dữ liệu không tự bắt được. Lỗi -> ValueError."""
    errors: list[str] = []
    sec_by_id = {s.id: s for s in b.sections}
    lex_ids = {e.id for e in b.lexicon}

    if b.article.section_count != len(b.sections):
        errors.append("article.section_count khác số section")

    for s in b.sections:
        for toks, where in ((s.tokens, s.id), (s.key_idea.tokens, f"{s.id}.key_idea")):
            for k, t in enumerate(toks):
                if t.i != k:
                    errors.append(f"{where}: token index không liên tục tại {k}")
                    break
                if t.is_word and not t.vi:
                    errors.append(f"{where}: token {t.i} '{t.text}' thiếu vi")
        if s.check and s.check.answer_index >= len(s.check.options):
            errors.append(f"{s.id}: check.answer_index vượt số options")

    for e in b.lexicon:
        if e.definition_en and len(e.definition_en.split()) > DEFINITION_MAX_WORDS:
            errors.append(f"{e.id}: definition_en dài hơn {DEFINITION_MAX_WORDS} từ")

    for o in b.occurrences:
        if o.lexicon_entry_id not in lex_ids:
            errors.append(f"{o.id}: lexicon_entry_id không tồn tại")
        s = sec_by_id.get(o.section_id)
        if s is None:
            errors.append(f"{o.id}: section_id không tồn tại")
            continue
        if not (0 <= o.token_start <= o.token_end < len(s.tokens)):
            errors.append(f"{o.id}: khoảng token ngoài phạm vi")

    for q in b.quiz:
        if q.answer_index >= len(q.options):
            errors.append(f"{q.id}: answer_index vượt số options")
        if b.article.cefr_level == "A2" and q.type == "true_false_ng":
            errors.append(f"{q.id}: bài A2 không dùng true_false_ng")

    if errors:
        raise ValueError("Bundle vi phạm contract:\n- " + "\n- ".join(errors))
