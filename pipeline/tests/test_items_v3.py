"""BE-06g: prompt items-v3 (evidence, luật T/F/NG, CEFR từ điển) + ghim đầu vào prompt. Không gọi LLM."""
import json

import pytest

from pipeline.enrich import (
    ITEMS_PROMPT, ITEMS_PROMPT_V2, ITEMS_PROMPT_V3, ITEMS_PROMPT_VERSION, ArticleItems,
    ArticleItemsV3, CacheMiss, EntryDetail, EntryDetails, Overrides, QuizItemV3, SelectedItem,
    item_dict_level, known_cefr_levels, load_pin, merge_entry_details, norm_evidence,
    pinned_known_entries, single_word_levels, write_pin,
)
from pipeline import enrich
from pipeline.cefr_lexicon import CefrLookup
from pipeline.reference.tokenize_and_match import lemma_key, locate, tokenize

TEXT = ("Farmers use irrigation to water the fields. "
        "Most of the water comes from a nearby river.\n"
        "The village was “founded in 1850” by traders.")


def _q(question, answer_index=0, evidence=None, typ="true_false_ng"):
    opts = ["True", "False", "Not Given"] if typ == "true_false_ng" else ["True", "False"]
    return {"type": typ, "question": question, "options": opts,
            "answer_index": answer_index, "explanation": "E", "evidence": evidence}


CTX = {"full_text": TEXT}


# ── evidence ──

def test_true_needs_evidence_from_text():
    QuizItemV3.model_validate(_q("Farmers water the fields with irrigation.", 0,
                                 "Farmers use irrigation to water the fields."), context=CTX)
    with pytest.raises(Exception, match="give evidence"):
        QuizItemV3.model_validate(_q("Farmers water the fields.", 0, None), context=CTX)
    with pytest.raises(Exception, match="not in the text"):
        QuizItemV3.model_validate(_q("Farmers water the fields.", 0,
                                     "Farmers water their fields every day."), context=CTX)


def test_evidence_matching_ignores_case_quotes_and_final_dot():
    assert norm_evidence("The village was \"founded in 1850\" by traders") in norm_evidence(TEXT)
    QuizItemV3.model_validate(_q("Traders founded the village.", 0,
                                 'the village was "founded in 1850" by traders'), context=CTX)


def test_not_given_must_have_null_evidence():
    QuizItemV3.model_validate(_q("The river is polluted.", 2, None), context=CTX)
    with pytest.raises(Exception, match="evidence must be null"):
        QuizItemV3.model_validate(_q("The river is polluted.", 2,
                                     "Farmers use irrigation to water the fields."), context=CTX)


def test_multiple_choice_also_needs_evidence():
    q = {"type": "multiple_choice", "question": "Where does the water come from?",
         "options": ["A river", "A lake"], "answer_index": 0, "explanation": "E", "evidence": None}
    with pytest.raises(Exception, match="give evidence"):
        QuizItemV3.model_validate(q, context=CTX)


def test_no_generalizing_qualifier_absent_from_text():
    with pytest.raises(Exception, match=r"\['usually'\]"):
        QuizItemV3.model_validate(_q("Farmers usually use irrigation.", 0,
                                     "Farmers use irrigation to water the fields."), context=CTX)
    # "most" có trong bài → được dùng
    QuizItemV3.model_validate(_q("Most of the water comes from a river.", 0,
                                 "Most of the water comes from a nearby river."), context=CTX)


def test_without_context_no_text_checks():
    QuizItemV3.model_validate(_q("Anything usually.", 0, None))


# ── CEFR: từ điển cho từ đơn, miễn mục cefr.json khó hơn ──

LEX = {"entries": {"irrigation|NOUN": {"cefr": "B2", "source": "cefrj"},
                   "field|NOUN": {"cefr": "A2", "source": "cefrj"},
                   "village|NOUN": {"cefr": "A2", "source": "cefrj"},
                   "trader|NOUN": {"cefr": "B1", "source": "cefrj"},
                   "water|VERB": {"cefr": "A2", "source": "cefrj"}},
       "multiword": {}}


def _items(forms, cefr="B1"):
    return [{"canonical_form": f, "type": "single_word" if " " not in f else "collocation",
             "pos": "noun", "cefr_level": cefr, "vi": "v", "definition_en": "d",
             "extra_example": "e"} for f in forms]


def _ctx(**kw):
    toks = tokenize(TEXT)
    look = CefrLookup(LEX)
    return {"locate": locate, "section_tokens": [toks], "level": "B1",
            "allowed_cefr": ("B1", "B2"), "count_range": (6, 6), "full_text": TEXT,
            "dict_level": item_dict_level(look), **kw}


GOOD_QUIZ = [_q("Farmers water the fields with irrigation.", 0,
                "Farmers use irrigation to water the fields.")] * 3


def test_v3_rejects_single_word_below_i_plus_1_by_dictionary():
    # LLM nói B1 nhưng từ điển: village A2 → ngoài i+1
    with pytest.raises(Exception, match=r"village \(A2, dictionary\)"):
        ArticleItemsV3.model_validate({"items": _items(["village"] * 6), "quiz": GOOD_QUIZ},
                                      context=_ctx())
    ArticleItemsV3.model_validate({"items": _items(["irrigation"] * 6), "quiz": GOOD_QUIZ},
                                  context=_ctx())


def test_v3_unknown_word_uses_llm_level():
    ArticleItemsV3.model_validate({"items": _items(["river"] * 6, "B2"), "quiz": GOOD_QUIZ},
                                  context=_ctx())


def test_v3_known_harder_item_exempt_but_easier_rejected():
    # người duyệt chốt C1 (vd pest ở bài B1) → miễn; A1 → vẫn bị loại
    ArticleItemsV3.model_validate({"items": _items(["irrigation"] * 6), "quiz": GOOD_QUIZ},
                                  context=_ctx(cefr_dict={"irrigation": "C1"}))
    with pytest.raises(Exception, match="outside the allowed CEFR"):
        ArticleItemsV3.model_validate({"items": _items(["irrigation"] * 6), "quiz": GOOD_QUIZ},
                                      context=_ctx(cefr_dict={"irrigation": "A1"}))


def test_v2_validator_unchanged_no_exemption():
    ctx = _ctx(cefr_dict={"irrigation": "C1"})
    ctx.pop("dict_level")
    quiz = [{k: v for k, v in q.items() if k != "evidence"} for q in GOOD_QUIZ]
    with pytest.raises(Exception, match="outside the allowed CEFR"):
        ArticleItems.model_validate({"items": _items(["irrigation"] * 6), "quiz": quiz},
                                    context=ctx)


def test_single_word_levels_lists_content_words_in_range():
    toks = tokenize(TEXT)
    sw = single_word_levels([{"tokens": toks}], CefrLookup(LEX), {}, ("B1", "B2"))
    assert sw == [("irrigation", "B2"), ("trader", "B1")]
    sw = single_word_levels([{"tokens": toks}], CefrLookup(LEX),
                            {lemma_key("trader"): {"cefr": "C1"}}, ("B1", "B2"))
    assert ("trader", "B1") not in sw   # có trong cefr.json → khối KNOWN CEFR LEVELS lo


def test_merge_uses_dictionary_for_v3_only():
    item = SelectedItem(canonical_form="village", type="single_word", pos="noun",
                        cefr_level="B1", vi="làng", definition_en="d", extra_example="e")
    det = EntryDetails.model_construct(entries=[EntryDetail.model_construct(
        canonical_form="village", cefr_level="B1", definition_en="A small town.",
        extra_example="e")])
    out, _ = merge_entry_details([item], det, Overrides(), {})
    assert out["village"]["cefr_level"] == "B1"
    out, _ = merge_entry_details([item], det, Overrides(), {}, item_dict_level(CefrLookup(LEX)))
    assert out["village"]["cefr_level"] == "A2"
    assert out["village"]["cefr_note"] == "từ điển (cefr_lexicon)"
    # cefr.json vẫn thắng từ điển
    out, _ = merge_entry_details([item], det, Overrides(),
                                 {"village": {"cefr": "B2", "source": "x"}},
                                 item_dict_level(CefrLookup(LEX)))
    assert out["village"]["cefr_level"] == "B2"


# ── prompt + ghim ──

def test_v3_prompt_has_new_rules_and_v2_unchanged():
    assert ITEMS_PROMPT_VERSION == "items-v3" and ITEMS_PROMPT_V2 == "items-v2"
    for s in ("evidence", "read documents", "Not Given", "more general", "legend"):
        assert s in ITEMS_PROMPT_V3
    assert "evidence" not in ITEMS_PROMPT  # prompt v2 của 8 bài đã ghim giữ nguyên
    fmt = dict(title="t", category="c", level="B1", combined="x", known_block="k",
               count_lo=1, count_hi=2, cefr_a="B1", cefr_b="B2", ng_note="")
    ITEMS_PROMPT_V3.format(**fmt)


def test_pin_roundtrip_and_cards(tmp_path):
    (tmp_path / "art").mkdir()
    known = [{"form": "launch", "cefr": "B2", "slug": "a", "card": {"x": 1}},
             {"form": "nutritional value", "cefr": "B1", "slug": "a", "dropped": True}]
    write_pin("art", "items-v2", {"level": "B2", "category": "c", "source_name": "s",
                                   "source_graded": False, "title": None},
              known, [("stage", "B2")], out_dir=tmp_path)
    pin = load_pin("art", out_dir=tmp_path)
    assert pin["items_prompt_version"] == "items-v2"
    assert pin["known_entries"][0] == {"form": "launch", "cefr": "B2", "slug": "a"}  # không lưu thẻ
    assert pin["known_cefr_levels"] == [["stage", "B2"]]
    # CEFR bài trước đổi → danh sách ghim giữ cấp cũ, thẻ lấy bản hiện tại
    live = [{"form": "launch", "cefr": "B1", "slug": "a", "card": {"x": 2}}]
    got = pinned_known_entries(pin, live)
    assert got[0]["cefr"] == "B2" and got[0]["card"] == {"x": 2}
    assert got[1].get("dropped") and "card" not in got[1]
    assert load_pin("missing", out_dir=tmp_path) is None


def test_known_cefr_levels_only_forms_in_text():
    toks = tokenize(TEXT)
    d = {"irrigation": {"form": "irrigation", "cefr": "B2"},
         "rocket": {"form": "rocket", "cefr": "A2"}}
    assert known_cefr_levels(d, [{"tokens": toks}]) == [("irrigation", "B2")]


def test_cache_only_raises_on_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(enrich, "CACHE", tmp_path)
    monkeypatch.setattr(enrich, "CACHE_ONLY", True)
    with pytest.raises(CacheMiss):
        enrich.cached_create(None, "d", ArticleItems, [{"role": "user", "content": "x"}])


BATCH_1 = ["eating-well", "robots", "farming", "rocket-science", "water-power",
           "ai-chatbots", "curry-chicken", "holiday-travel"]


def test_batch_1_pinned_v2_and_other_pins_valid():
    order = json.loads((enrich.OUT / "processing_order.json").read_text("utf-8"))
    assert order[:8] == BATCH_1
    for slug in order:
        pin = load_pin(slug)
        if slug in BATCH_1:
            assert pin and pin["items_prompt_version"] == "items-v2", slug
        if pin:  # bài lô 2 chỉ có pin sau khi duyệt + seed
            assert pin["items_prompt_version"] in ("items-v2", "items-v3"), slug
            assert pin["run_args"]["level"] in ("A2", "B1", "B2")


# ── locate: chỗ trống sở hữu "one's" (BE-07, Q-025) ──

@pytest.mark.parametrize("text, form, span", [
    ("The name Paris can trace its roots to the 3rd century.", "trace one's roots to", (4, 7)),
    ("They also like to speak their minds, which is fine.", "speak one's mind", (4, 6)),
    ("She made up her mind quickly.", "make up one's mind", (1, 4)),
])
def test_locate_ones_placeholder(text, form, span):
    assert locate(tokenize(text), form) == [span]


def test_locate_ones_needs_a_possessive():
    assert locate(tokenize("They speak the mind of the city."), "speak one's mind") == []
    # cụm không có "one's" vẫn như cũ
    assert locate(tokenize("It dates back to 1358."), "date back to") == [(1, 3)]


# ── quy luật sàn cho cụm (Q-026) ──

FLOOR_LEX = {"entries": {"fond|ADJ": {"cefr": "B1", "source": "cefrj"},
                         "effort|NOUN": {"cefr": "A2", "source": "cefrj"},
                         "make|VERB": {"cefr": "A1", "source": "cefrj"},
                         "locate|VERB": {"cefr": "B1", "source": "cefrj"}},
             "multiword": {}}


def _phrase(form, cefr):
    item = SelectedItem(canonical_form=form, type="collocation", pos="phrase",
                        cefr_level=cefr, vi="v", definition_en="d", extra_example="e")
    det = EntryDetails.model_construct(entries=[EntryDetail.model_construct(
        canonical_form=form, cefr_level=cefr, definition_en="d.", extra_example="e")])
    return [item], det


@pytest.mark.parametrize("form, llm, expected, raised", [
    ("fond of", "A2", "B1", True),         # sàn = fond B1
    ("be located", "A2", "B1", True),      # sàn = locate B1
    ("make an effort", "A2", "A2", False),  # sàn = effort A2 → quy luật không quyết
    ("fond of", "B2", "B2", False),        # LLM cao hơn sàn → giữ
])
def test_phrase_floor(form, llm, expected, raised):
    from pipeline.enrich import phrase_floor
    items, det = _phrase(form, llm)
    out, _ = merge_entry_details(items, det, Overrides(), {}, None,
                                 phrase_floor(CefrLookup(FLOOR_LEX)))
    assert out[form]["cefr_level"] == expected
    assert out[form]["cefr_note"].startswith("llm+floor") == raised


def test_phrase_floor_loses_to_cefr_json_and_absent_in_v2():
    from pipeline.enrich import phrase_floor
    items, det = _phrase("fond of", "A2")
    out, _ = merge_entry_details(items, det, Overrides(),
                                 {lemma_key("fond of"): {"cefr": "A2", "source": "x"}},
                                 None, phrase_floor(CefrLookup(FLOOR_LEX)))
    assert out["fond of"]["cefr_level"] == "A2"
    out, _ = merge_entry_details(items, det, Overrides(), {})   # v2: không có sàn
    assert out["fond of"]["cefr_level"] == "A2"
