"""BE-06e2: tách token (R2-D2, dấu ” đầu câu), IPA viết tay dùng chung, override key idea / quiz /
Quick Check / bỏ occurrence / chọn câu gốc."""
import pytest

from pipeline.enrich import (
    Overrides,
    QuickCheckResponse,
    QuizItemResponse,
    apply_key_idea_overrides,
    apply_occurrence_exclusions,
    apply_quick_check_overrides,
    apply_quiz_overrides,
    cap_quick_checks,
    clean_llm_ipa,
    extract_sentence,
    item_to_lex_id,
    merge_codes_with_meanings,
    pick_originals,
)
from pipeline.ipa import phrase_ipa, word_ipa
from pipeline.reference.tokenize_and_match import locate, merge_code_tokens, sentence_cloze, tokenize


# ── Tách câu: dấu nháy đóng thuộc câu trước ─────────────────────

QUOTE = ("There is some truth in the old saying “an apple a day keeps the doctor away.” "
         "Apples help reduce the risk of diabetes.")


def test_sentence_after_closing_quote_does_not_start_with_quote():
    t = tokenize(QUOTE)
    s, e = locate(t, "reduce the risk of")[0]
    assert extract_sentence(t, s, e) == "Apples help reduce the risk of diabetes."
    assert sentence_cloze(t, s, e)["text_before"] == "Apples help "


def test_closing_quote_stays_with_its_sentence():
    t = tokenize(QUOTE)
    s, e = locate(t, "an apple a day")[0]
    assert extract_sentence(t, s, e).endswith("doctor away.”")


# ── Gộp mã viết liền bằng gạch nối ──────────────────────────────

def test_merge_code_tokens():
    toks, remap = merge_code_tokens(tokenize("R2-D2 and C-3PO use 3-D printing, low-fat food and 90-minute runs."))
    texts = [t["text"] for t in toks]
    assert texts[:3] == ["R2-D2", "and", "C-3PO"] and "3-D" in texts
    assert "low" in texts and "fat" in texts and "90" in texts      # từ ghép thường không gộp
    assert [t["i"] for t in toks] == list(range(len(toks)))           # chỉ số liên tục
    assert remap[0] == remap[1] == remap[2] == 0
    r2 = toks[0]
    assert r2["is_word"] and not r2["is_fn"] and r2["ws"] == " "


def test_merge_keeps_proper_name_meaning_and_remaps_others():
    t = tokenize("R2-D2 is a robot.")
    meanings = {0: "R2", 2: "D2", 3: "là", 4: "một", 5: "người máy"}
    toks, m, notes = merge_codes_with_meanings(t, meanings)
    assert toks[0]["text"] == "R2-D2" and m[0] == "R2-D2"
    assert m[1] == "là" and m[3] == "người máy"
    assert len(notes) == 1


# ── IPA viết tay dùng chung ────────────────────────────────────

def test_manual_ipa_beats_cmudict_for_words_and_phrases():
    assert word_ipa("reservoir") == "/ˈrɛzɚˌvwɑr/"
    assert word_ipa("emus") == "/ˈimjuz/"
    assert word_ipa("cultivator") == "/ˈkʌltəˌveɪtɚ/"            # CMUdict không có
    assert phrase_ipa("artificial intelligence") == "/ˌɑrtəˈfɪʃəl ɪnˈtɛlədʒəns/"
    assert phrase_ipa("heavy-lift rocket") == "/ˈhɛviˌlɪft ˈrɑkət/"
    assert word_ipa("rocket") == "/ˈrɑkət/"                        # ngoài từ điển: vẫn CMUdict


# ── Override mới ───────────────────────────────────────────────

def _sd(order, key_idea="Old idea.", check=None):
    return {"order": order, "key_idea_text": key_idea, "key_idea_tokens": tokenize(key_idea), "check": check}


def test_key_idea_override_retokenizes():
    sds = [_sd(2)]
    ov = Overrides.model_validate({"key_ideas": {"2": "There are many types of farms."}})
    applied = apply_key_idea_overrides(sds, ov)
    assert sds[0]["key_idea_text"] == "There are many types of farms."
    assert sds[0]["key_idea_tokens"][0]["text"] == "There" and len(applied) == 1


def test_key_idea_override_rejects_long_and_unknown_section():
    with pytest.raises(Exception, match="15"):
        Overrides.model_validate({"key_ideas": {"1": " ".join(["word"] * 16)}})
    with pytest.raises(ValueError, match="không tồn tại"):
        apply_key_idea_overrides([_sd(1)], Overrides.model_validate({"key_ideas": {"9": "x"}}))


CHECK = {"question": "Which robot?", "options": ["Unimate", "R2-D2"], "answer_index": 0, "explanation": "vì"}


def test_quick_check_override_adds_option_and_revalidates():
    sds = [_sd(9, check=dict(CHECK))]
    ov = Overrides.model_validate({"quick_checks": {"9": {"options": ["Unimate", "R2-D2", "ASIMO"]}}})
    apply_quick_check_overrides(sds, ov)
    assert sds[0]["check"]["options"][-1] == "ASIMO" and sds[0]["check"]["answer_index"] == 0
    bad = Overrides.model_validate({"quick_checks": {"9": {"answer_index": 5}}})
    with pytest.raises(ValueError, match="quick_checks\\[9\\]"):
        apply_quick_check_overrides([_sd(9, check=dict(CHECK))], bad)


def test_quick_check_remove():
    sds = [_sd(3, check=dict(CHECK))]
    apply_quick_check_overrides(sds, Overrides.model_validate({"quick_checks": {"3": {"remove": True}}}))
    assert sds[0]["check"] is None


def _sd_words(order, n_words, check=True):
    sd = _sd(order, check=dict(CHECK) if check else None)
    sd["tokens"] = tokenize(" ".join(["word"] * n_words) + ".")
    return sd


def test_cap_quick_checks_keeps_three_longest():
    sds = [_sd_words(0, 150), _sd_words(1, 200), _sd_words(2, 130), _sd_words(3, 180),
           _sd_words(4, 90, check=False), _sd_words(5, 150)]
    notes = cap_quick_checks(sds)
    assert [sd["order"] for sd in sds if sd["check"]] == [0, 1, 3]   # 200, 180, 150 (bằng nhau → sec trước)
    assert len(notes) == 2 and notes[0].startswith("sec 2")


def _tfng(options, question="Wan Hu flew into space.", answer=1):
    return QuizItemResponse(type="true_false_ng", question=question, options=options,
                            answer_index=answer, explanation="vì")


def test_tfng_options_normalized_to_three():
    assert _tfng(["True", "False"]).options == ["True", "False", "Not Given"]
    assert _tfng(["True", "False", "Not given"], answer=2).options == ["True", "False", "Not Given"]
    with pytest.raises(Exception, match="true_false_ng options"):
        _tfng(["Yes", "No"])


def test_tfng_rejects_statement_about_the_article():
    for q in ("The article gives an exact dollar cost.", "According to the article, prices drop.",
              "The writer recommends waiting."):
        with pytest.raises(Exception, match="about the world"):
            _tfng(["True", "False", "Not Given"], question=q)
    assert _tfng(["True", "False"], question="The first plant was built in 1879.").answer_index == 1


def test_true_false_options_untouched():
    q = QuizItemResponse(type="true_false", question="X?", options=["True", "False"],
                         answer_index=0, explanation="vì")
    assert q.options == ["True", "False"]


def test_clean_llm_ipa_drops_length_marks():
    assert clean_llm_ipa("/ˌriːˈbʊkɪŋ wɪˈðaʊt ˈpɛnəlti/") == "/ˌriˈbʊkɪŋ wɪˈðaʊt ˈpɛnəlti/"
    assert clean_llm_ipa("ˈtʃætbɒt") == "/ˈtʃætbɒt/" and clean_llm_ipa(None) is None


def test_hyphen_compound_ipa_keeps_stress():
    assert word_ipa("pop-up") == "/ˈpɑpˌʌp/"
    assert word_ipa("hole-in-the-wall") == "/ˈhoʊlɪnðəˌwɔl/"
    assert word_ipa("heavy-lift") == "/ˈhɛviˌlɪft/"             # khớp kiểu ipa.json đã duyệt
    assert phrase_ipa("round-trip flights") == "/ˈraʊndˌtrɪp flaɪts/"


def test_cap_quick_checks_noop_when_within_limit():
    sds = [_sd_words(0, 150), _sd_words(1, 200)]
    assert cap_quick_checks(sds) == [] and all(sd["check"] for sd in sds)


def test_quiz_override_partial():
    quiz = [QuizItemResponse(type="multiple_choice", question=f"Q{n}?", options=["A", "Appleton", "C"],
                             answer_index=0, explanation="E") for n in range(3)]
    ov = Overrides.model_validate({"quiz": {"1": {"options": ["A", "Three Gorges Dam", "C"]},
                                            "2": {"explanation": "mới"}}})
    out, applied = apply_quiz_overrides(quiz, ov)
    assert out[0].options[1] == "Three Gorges Dam" and out[0].question == "Q0?"
    assert out[1].explanation == "mới" and out[2].explanation == "E" and len(applied) == 2
    with pytest.raises(ValueError, match="câu 4"):
        apply_quiz_overrides(quiz, Overrides.model_validate({"quiz": {"4": {"question": "x"}}}))


def _occ(form, sent):
    return {"lexicon_entry_id": item_to_lex_id(form), "example_sentence": sent}


OCCS = [_occ("thrust", "The balloon is thrust forward."),
        _occ("thrust", "The reaction is the thrust (pushing force) of the rocket."),
        _occ("stage", "Each stage burns fuel.")]


def test_exclude_occurrence_and_errors():
    ov = Overrides.model_validate({"exclude_occurrences": [{"item": "thrust", "sentence_contains": "is thrust forward"}]})
    out, applied = apply_occurrence_exclusions(OCCS, ov)
    assert len(out) == 2 and "balloon" not in out[0]["example_sentence"] and len(applied) == 1
    with pytest.raises(ValueError, match="không có occurrence"):
        apply_occurrence_exclusions(OCCS, Overrides.model_validate(
            {"exclude_occurrences": [{"item": "thrust", "sentence_contains": "nope"}]}))
    with pytest.raises(ValueError, match="không còn"):
        apply_occurrence_exclusions(OCCS, Overrides.model_validate(
            {"exclude_occurrences": [{"item": "stage", "sentence_contains": "Each stage"}]}))


def test_pick_originals_default_first_and_override():
    lex = {item_to_lex_id("thrust"): "thrust", item_to_lex_id("stage"): "stage"}
    assert pick_originals(OCCS, lex, Overrides())["thrust"] == "The balloon is thrust forward."
    ov = Overrides.model_validate({"lexicon": {"thrust": {"original_contains": "The reaction is the thrust"}}})
    got = pick_originals(OCCS, lex, ov)
    assert got["thrust"].startswith("The reaction") and got["stage"] == "Each stage burns fuel."
    bad = Overrides.model_validate({"lexicon": {"thrust": {"original_contains": "nope"}}})
    with pytest.raises(ValueError, match="original_contains"):
        pick_originals(OCCS, lex, bad)


def test_original_contains_is_not_written_into_lexicon_entry():
    from pipeline.enrich import EntryDetail, EntryDetails, SelectedItem, merge_entry_details
    item = SelectedItem(canonical_form="thrust", type="single_word", pos="noun", cefr_level="C1",
                        vi="lực đẩy", definition_en="d", extra_example="e")
    det = EntryDetails.model_construct(entries=[EntryDetail.model_construct(
        canonical_form="thrust", cefr_level="C1", definition_en="a pushing force", extra_example="e")])
    ov = Overrides.model_validate({"lexicon": {"thrust": {"original_contains": "reaction"}}})
    out, applied = merge_entry_details([item], det, ov)
    assert "original_contains" not in out["thrust"] and applied == []
    assert QuickCheckResponse  # import dùng cho test khác
