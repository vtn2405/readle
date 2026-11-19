"""BE-06h: prompt bước 1 v2 (Key idea chỉ dùng chữ trong bài, nói nội dung) + ghim version theo bài."""
import json

import pytest
from pydantic import ValidationError

from pipeline import enrich
from pipeline.enrich import (
    SECTION_PROMPT,
    SECTION_PROMPT_V1,
    SECTION_PROMPT_VERSION,
    SECTION_PROMPTS,
    SectionEnrichment,
    load_pin,
    pinned_section_version,
    write_pin,
)

FMT = dict(level="B1", section_title="s", article_title="a", body="b", lines="0\tx",
           check_instruction="c")


def test_v1_prompt_text_unchanged():
    # Chữ v1 nằm trong khóa cache của 9 bài đã duyệt: không được đổi.
    assert SECTION_PROMPTS[SECTION_PROMPT_V1] is SECTION_PROMPT
    assert "general knowledge" not in SECTION_PROMPT
    assert "Do not simply copy the first sentence.\n2. meanings" in SECTION_PROMPT


def test_v2_prompt_adds_two_rules_only():
    v2 = SECTION_PROMPTS[SECTION_PROMPT_VERSION]
    assert SECTION_PROMPT_VERSION == "section-v2"
    assert "Use only facts stated in the section; do not add details from general knowledge." in v2
    assert "State the content, not what the section does" in v2
    v2.format(**FMT)
    # ngoài mục 1, phần còn lại giống v1
    assert v2.split("2. meanings")[1] == SECTION_PROMPT.split("2. meanings")[1]


def test_section_messages_differ_by_version(monkeypatch):
    seen = []
    monkeypatch.setattr(enrich, "cached_create",
                        lambda c, d, m, msgs, context=None, version=None: seen.append((msgs, context)))
    toks = [{"i": 0, "text": "Paris", "is_word": True}]
    enrich.enrich_section(None, "d", toks, "s", "a", "B1", "Paris.", version=SECTION_PROMPT_V1)
    enrich.enrich_section(None, "d", toks, "s", "a", "B1", "Paris.")
    (m1, c1), (m2, c2) = seen
    assert m1 != m2
    assert c1["key_idea_v2"] is False and c2["key_idea_v2"] is True


def _payload(key_idea):
    return json.dumps({"key_idea": key_idea, "meanings": [{"i": 0, "vi": "Paris"}], "check": None})


@pytest.mark.parametrize("ki", [
    "This section gives facts about Paris.",
    "The section explains how the tower moves.",
    "this part describes Bastille Day.",
])
def test_v2_validator_rejects_meta_key_idea(ki):
    with pytest.raises(ValidationError, match="describes the section"):
        SectionEnrichment.model_validate_json(_payload(ki),
                                              context={"word_indexes": [0], "key_idea_v2": True})


def test_v1_cache_with_meta_key_idea_still_loads():
    # cache v1 của paris có "This section gives…" (đã sửa bằng overrides) → phải đọc được
    r = SectionEnrichment.model_validate_json(_payload("This section gives facts about Paris."),
                                              context={"word_indexes": [0], "key_idea_v2": False})
    assert r.key_idea.startswith("This section")


def test_v2_validator_accepts_content_sentence():
    r = SectionEnrichment.model_validate_json(
        _payload("This section of the city is very old."),  # "section" là nội dung, không phải bài
        context={"word_indexes": [0], "key_idea_v2": True})
    assert r.key_idea


def test_pinned_section_version(tmp_path):
    assert pinned_section_version(None) == SECTION_PROMPT_VERSION     # bài mới
    assert pinned_section_version({"items_prompt_version": "items-v2"}) == SECTION_PROMPT_V1
    (tmp_path / "art").mkdir()
    args = {"level": "B1", "category": "c", "source_name": "s", "source_graded": False, "title": None}
    write_pin("art", "items-v3", args, [], [], out_dir=tmp_path)
    assert load_pin("art", out_dir=tmp_path)["section_prompt_version"] == SECTION_PROMPT_VERSION
    write_pin("art", "items-v3", args, [], [], out_dir=tmp_path, section_version=SECTION_PROMPT_V1)
    assert pinned_section_version(load_pin("art", out_dir=tmp_path)) == SECTION_PROMPT_V1


def test_approved_articles_pinned_section_v1():
    order = json.loads((enrich.OUT / "processing_order.json").read_text("utf-8"))
    for slug in order[:9]:  # 9 bài đã duyệt trước BE-06h
        pin = load_pin(slug)
        assert pin and pin["section_prompt_version"] == SECTION_PROMPT_V1, slug
