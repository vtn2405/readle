"""BE-06i phần B: items-v4 (cụm lặp, ≥ 40% cụm, quiz có câu False), thẻ details-v2 (ví dụ ≤ cấp bài),
luật tái sử dụng ≤ cấp bài + 2, ghim version thẻ. Không gọi LLM."""
import json

import pytest

from pipeline import enrich
from pipeline.cefr_lexicon import CefrLookup
from pipeline.enrich import (
    DETAILS_PROMPT, DETAILS_PROMPT_V1, DETAILS_PROMPT_V2, DETAILS_PROMPT_VERSION, ITEMS_PROMPT_V3,
    ITEMS_PROMPT_V4, ITEMS_PROMPT_VERSION, ITEMS_VERSION_V3, ArticleItemsV3, ArticleItemsV4,
    EntryDetail, QuizItemResponse, SelectedItem, describe_entries, example_words_above, load_pin,
    pinned_details_version, plan_reuse, quiz_has_negative, repeated_phrases, reuse_ceiling,
    select_items_and_quiz, write_pin,
)
from pipeline.reference.tokenize_and_match import locate, tokenize

TEXT = ("Farmers depend on rain. Farmers depend on rivers too. "
        "They take care of the fields and make a decision about water. Irrigation helps the crops. "
        "The village is famous for rice.")


def _sections(text=TEXT):
    return [{"title": "T", "body": text, "tokens": tokenize(text)}]


# ── cụm lặp ──

def test_repeated_phrases_groups_be_forms_and_skips_junk():
    text = ("Pizza is topped with cheese. Bread was topped with butter. The pie is topped with fruit. "
            "Most of the pizza is hot. Most of the bread is cold.")
    rep = repeated_phrases(_sections(text))
    assert rep[0] == ("be topped with", 3)
    assert not any(p.startswith(("of ", "the ")) for p, _ in rep)   # bắt đầu bằng giới từ/mạo từ
    assert ("topped with", 3) not in rep                           # cụm con cùng số lần → bỏ


def test_repeated_phrases_skip_all_content_word_combinations():
    # "baked flat bread" ×2 là ghép tự do (thử pizza run #98) → bỏ; "made with" ×2 → giữ
    text = "We ate baked flat bread made with oil. They sold baked flat bread made with salt."
    rep = dict(repeated_phrases(_sections(text)))
    assert "baked flat bread" not in rep and "flat bread" not in rep
    assert any("made with" in p and c == 2 for p, c in rep.items())  # có thể gộp vào cụm dài hơn


def test_repeated_phrases_needs_two_and_no_punctuation_crossing():
    rep = repeated_phrases(_sections("They eat bread, rice and fish. They sell bread, rice and fish."))
    assert not any("bread rice" in p for p, _ in rep)   # dấu phẩy cắt cụm
    assert repeated_phrases(_sections("We make a cake. Then we eat.")) == []


def test_repeated_phrases_on_real_pizza_text():
    norm = json.loads((enrich.OUT / "pizza" / "normalized_sections.json").read_text("utf-8"))
    sd = [{"tokens": tokenize(s["body"])} for s in norm["sections"]]
    got = dict(repeated_phrases(sd))
    assert got.get("topped with", 0) >= 6 and got.get("be topped with", 0) >= 3


# ── validator v4 ──

def _item(form, typ):
    return {"canonical_form": form, "type": typ, "pos": "x", "cefr_level": "B1", "vi": "v",
            "definition_en": "d", "extra_example": "e"}


EV = "Farmers depend on rain."


def _q(answer, typ="true_false", evidence=EV):
    opts = ["True", "False", "Not Given"] if typ == "true_false_ng" else ["True", "False"]
    return {"type": typ, "question": "Farmers depend on rain.", "options": opts,
            "answer_index": opts.index(answer), "explanation": "E",
            "evidence": None if answer == "Not Given" else evidence}


def _ctx(level="B1"):
    return {"locate": locate, "section_tokens": [tokenize(TEXT)], "level": level,
            "count_range": (6, 6), "full_text": TEXT}


# 3/6 cụm = 50% ≥ 40% (cần ceil(2.4) = 3)
ITEMS_OK = [_item("depend on", "collocation"), _item("take care of", "collocation"),
            _item("make a decision", "collocation"), _item("irrigation", "single_word"),
            _item("village", "single_word"), _item("crop", "single_word")]
QUIZ_OK = [_q("True"), _q("False"), _q("True")]


def test_v4_collocation_share_at_least_40_percent():
    ArticleItemsV4.model_validate({"items": ITEMS_OK, "quiz": QUIZ_OK}, context=_ctx())  # 3/6
    one = ITEMS_OK[:2] + [_item(f, "single_word") for f in ("irrigation", "village", "crop", "rice")]
    with pytest.raises(Exception, match="Only 2 of 6 items are collocations; at least 3"):
        ArticleItemsV4.model_validate({"items": one, "quiz": QUIZ_OK}, context=_ctx())
    ArticleItemsV3.model_validate({"items": one, "quiz": QUIZ_OK}, context=_ctx())  # v3 không đổi


def test_v4_quiz_needs_a_false_answer():
    with pytest.raises(Exception, match='answer "False"'):
        ArticleItemsV4.model_validate({"items": ITEMS_OK, "quiz": [_q("True")] * 3},
                                      context=_ctx())
    # B1+: một câu Not Given cũng được
    ArticleItemsV4.model_validate(
        {"items": ITEMS_OK, "quiz": [_q("True"), _q("Not Given", "true_false_ng"), _q("True")]},
        context=_ctx("B1"))


def test_quiz_has_negative_levels():
    qs = [QuizItemResponse.model_validate({k: v for k, v in q.items() if k != "evidence"})
          for q in (_q("True"), _q("Not Given", "true_false_ng"))]
    assert quiz_has_negative(qs, "B1") and not quiz_has_negative(qs, "A2")
    f = QuizItemResponse.model_validate({k: v for k, v in _q("False").items() if k != "evidence"})
    assert quiz_has_negative([f], "A2")


# ── tái sử dụng ≤ cấp bài + 2 ──

@pytest.mark.parametrize("level, ceil", [("A2", "B2"), ("B1", "C1"), ("B2", "C2")])
def test_reuse_ceiling(level, ceil):
    assert reuse_ceiling(level) == ceil


def test_plan_reuse_skips_items_above_ceiling():
    sd = _sections("Eat sweets in moderation. Water plays a vital role in health. Farmers depend on rain.")
    known = [{"form": "in moderation", "cefr": "C1"}, {"form": "play a vital role in", "cefr": "C1"},
             {"form": "depend on", "cefr": "B1"}]
    assert plan_reuse(sd, known, level="A2") == ["in moderation", "play a vital role in", "depend on"]
    assert plan_reuse(sd, known, level="A2", ceiling="B2") == ["depend on"]
    assert plan_reuse(sd, known, level="B1", ceiling="C1") == ["in moderation", "play a vital role in",
                                                               "depend on"]


def _capture(monkeypatch):
    seen = {}

    def fake(client, deployment, model, messages, context=None, version=None):
        seen.update(model=model, prompt=messages[0]["content"], context=context, version=version)
        return "RES"
    monkeypatch.setattr(enrich, "cached_create", fake)
    return seen


def test_select_v4_prompt_filters_known_and_lists_repeats(monkeypatch):
    seen = _capture(monkeypatch)
    text = "Eat sweets in moderation. Farmers depend on rain. Farmers depend on rivers. " * 3
    known = [{"form": "in moderation", "cefr": "C1"}, {"form": "depend on", "cefr": "B1"}]
    res, reused = select_items_and_quiz(None, "d", _sections(text), "T", "C", "A2", known,
                                        version=ITEMS_PROMPT_VERSION)
    assert seen["model"] is ArticleItemsV4 and seen["version"] == "items-v4"
    assert reused == ["depend on"]
    assert "- in moderation (C1)" not in seen["prompt"]   # C1 > B2: không gợi ý, không ép
    assert "- depend on (B1)" in seen["prompt"]
    assert "REPEATED PHRASES" in seen["prompt"] and "depend on (×" in seen["prompt"]
    assert "At least 40% of the items" in seen["prompt"] and "must be FALSE" in seen["prompt"]
    assert seen["context"]["exempt_ceiling"] == "B2"


def test_select_v3_prompt_unchanged(monkeypatch):
    seen = _capture(monkeypatch)
    known = [{"form": "in moderation", "cefr": "C1"}]
    select_items_and_quiz(None, "d", _sections("Eat sweets in moderation."), "T", "C", "A2", known,
                          version=ITEMS_VERSION_V3)
    assert seen["model"] is ArticleItemsV3 and seen["version"] == "items-v3"
    assert "REPEATED PHRASES" not in seen["prompt"] and "- in moderation (C1)" in seen["prompt"]
    assert "exempt_ceiling" not in seen["context"]


def test_v4_prompt_extends_v3_text():
    assert ITEMS_PROMPT_VERSION == "items-v4"
    # luật của v3 còn nguyên trong v4, v3 không chứa luật mới
    for line in ITEMS_PROMPT_V3.splitlines():
        if line.strip() and "{" not in line:
            assert line in ITEMS_PROMPT_V4 or line.startswith(("3. COLLOCATIONS", "- Do not ask")), line
    assert "REPEATED PHRASES" not in ITEMS_PROMPT_V3 and "must be FALSE" not in ITEMS_PROMPT_V3
    ITEMS_PROMPT_V4.format(title="t", category="c", level="B1", combined="x", known_block="k",
                           count_lo=1, count_hi=2, cefr_a="B1", cefr_b="B2", ng_note="",
                           coll_min=1, ng_false_note="")


def test_v4_exemption_for_known_harder_item_capped(monkeypatch):
    # cefr.json C1 ở bài A2: v3 miễn (người duyệt chốt), v4 không miễn vì vượt cấp bài + 2
    ctx = {**_ctx("A2"), "allowed_cefr": ("A2", "B1"), "cefr_dict": {"depend on": "C1"},
           "dict_level": lambda it: None}
    items = ITEMS_OK[:1] + [dict(it, cefr_level="A2") for it in ITEMS_OK[1:]]
    ArticleItemsV3.model_validate({"items": items, "quiz": QUIZ_OK}, context=ctx)
    with pytest.raises(Exception, match=r"depend on \(C1\)"):
        ArticleItemsV4.model_validate({"items": items, "quiz": QUIZ_OK},
                                      context={**ctx, "exempt_ceiling": "B2"})


# ── thẻ details-v2: ví dụ ≤ cấp bài ──

LEX = {"entries": {"interior|NOUN": {"cefr": "B2", "source": "cefrj"},
                   "crust|NOUN": {"cefr": "C1", "source": "cefrj"},
                   "soft|ADJ": {"cefr": "A2", "source": "cefrj"},
                   "bread|NOUN": {"cefr": "A1", "source": "cefrj"}},
       "multiword": {}}


def test_example_words_above_ignores_item_and_unknown_words():
    look = CefrLookup(LEX)
    assert example_words_above("The crust has a soft interior.", "crust", "A2", look) == [("interior", "B2")]
    assert example_words_above("I like the crust on this bread.", "crust", "A2", look) == []
    assert example_words_above("The interior is soft.", "crust", "B2", look) == []


def test_entry_detail_v2_rejects_hard_example_only_with_context():
    look = CefrLookup(LEX)
    d = {"canonical_form": "crust", "cefr_level": "B2", "definition_en": "the hard outside of bread",
         "extra_example": "The crust has a soft interior."}
    EntryDetail.model_validate(d)  # v1: không có ngữ cảnh → không kiểm
    with pytest.raises(Exception, match=r"interior \(B2\)"):
        EntryDetail.model_validate(d, context={"example_level": "A2", "example_look": look})
    EntryDetail.model_validate({**d, "extra_example": "I like the crust on this bread."},
                               context={"example_level": "A2", "example_look": look})


def test_describe_entries_v1_keeps_old_prompt_and_cache_version(monkeypatch):
    seen = _capture(monkeypatch)
    it = SelectedItem(canonical_form="crust", type="single_word", pos="noun", cefr_level="B2", vi="vỏ",
                      definition_en="d", extra_example="e")
    describe_entries(None, "d", [it], {"crust": "The crust is thin."}, "A2")
    assert seen["version"] == DETAILS_PROMPT_V1 == "enrich-v1"     # khóa cache cũ của 10 bài
    assert "no harder than A2 level" in seen["prompt"] and "example_level" not in seen["context"]
    describe_entries(None, "d", [it], {"crust": "The crust is thin."}, "A2",
                     version=DETAILS_PROMPT_VERSION, look=CefrLookup(LEX))
    assert seen["version"] == "details-v2" and seen["context"]["example_level"] == "A2"
    assert "uses ONLY words at or below A2 level" in seen["prompt"]
    assert DETAILS_PROMPT_V2 != DETAILS_PROMPT and "{level}" in DETAILS_PROMPT_V2


# ── ghim version thẻ ──

def test_pinned_details_version(tmp_path):
    assert pinned_details_version(None) == DETAILS_PROMPT_VERSION          # bài mới
    assert pinned_details_version({"items_prompt_version": "items-v3"}) == DETAILS_PROMPT_V1
    (tmp_path / "art").mkdir()
    write_pin("art", "items-v4", {"level": "A2"}, [], [], out_dir=tmp_path)
    assert load_pin("art", out_dir=tmp_path)["details_prompt_version"] == DETAILS_PROMPT_VERSION


def test_all_reviewed_articles_pinned_on_old_details_prompt():
    order = json.loads((enrich.OUT / "processing_order.json").read_text("utf-8"))
    for slug in order:
        pin = load_pin(slug)
        assert pin, slug
        assert pinned_details_version(pin) == DETAILS_PROMPT_V1, slug
        assert pin["items_prompt_version"] in ("items-v2", "items-v3"), slug
