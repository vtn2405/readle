"""Tests for pipeline.enrich (BE-03) — pure helpers and validators only (no LLM)."""
import pytest

from pipeline.reference.contract_models import ArticleBundle
from pipeline.reference.tokenize_and_match import tokenize, locate, sentence_cloze, lemma_key
from pipeline.enrich import (
    Overrides,
    MeaningOverride,
    apply_meaning_overrides,
    load_overrides,
    format_token_lines,
    count_words,
    normalize_title,
    resolve_title,
    extract_sentence,
    item_to_lex_id,
    apply_meanings,
    build_bundle,
    TokenMeaning,
    SectionEnrichment,
    AllKeyIdeaMeanings,
    KeyIdeaTokenMeaning,
    QuickCheckResponse,
    ArticleItems,
    SelectedItem,
    QuizItemResponse,
    EntryDetail,
    EntryDetails,
    LexiconOverride,
    merge_entry_details,
)


# ── Pure helpers ────────────────────────────────────────────────

class TestFormatTokenLines:
    def test_excludes_punctuation(self):
        toks = tokenize("Hello, world.")
        lines = format_token_lines(toks)
        assert "Hello" in lines and "world" in lines
        assert "," not in lines

    def test_tab_separated(self):
        toks = tokenize("Hello world.")
        for line in format_token_lines(toks).strip().split("\n"):
            parts = line.split("\t")
            assert len(parts) == 2
            assert parts[0].isdigit()


class TestCountWords:
    def test_basic(self):
        assert count_words(tokenize("Hello, world.")) == 2

    def test_no_words(self):
        assert count_words(tokenize("...")) == 0


class TestNormalizeTitle:
    def test_all_caps(self):
        assert normalize_title("EATING WELL") == "Eating Well"

    def test_mixed_case_unchanged(self):
        assert normalize_title("Dark green veggies") == "Dark green veggies"

    def test_single_char(self):
        assert normalize_title("A") == "A"


class TestExtractSentence:
    def test_whole_single_sentence(self):
        toks = tokenize("Eating well plays a vital role.")
        sent = extract_sentence(toks, 2, 2)  # "plays"
        assert "Eating" in sent and "role" in sent and sent.endswith(".")

    def test_middle_sentence_only(self):
        toks = tokenize("First. The role is vital. Last.")
        i = next(t["i"] for t in toks if t["text"] == "role")
        sent = extract_sentence(toks, i, i)
        assert "role" in sent
        assert "First" not in sent
        assert "Last" not in sent


class TestItemToLexId:
    def test_single_word(self):
        assert item_to_lex_id("carotenoid") == "lex_carotenoid"

    def test_collocation(self):
        assert item_to_lex_id("play a vital role in") == "lex_play_a_vital_role_in"


class TestApplyMeanings:
    def test_applies_vi(self):
        toks = tokenize("Hello world.")
        result = apply_meanings(toks, {0: "xin chào", 1: "thế giới"})
        assert result[0]["vi"] == "xin chào"
        assert result[1]["vi"] == "thế giới"

    def test_no_mutation(self):
        toks = tokenize("Hello.")
        orig_vi = toks[0].get("vi")
        apply_meanings(toks, {0: "xin chào"})
        assert toks[0].get("vi") == orig_vi


# ── Response-model validators ───────────────────────────────────

class TestSectionEnrichmentValidator:
    def test_rejects_missing(self):
        with pytest.raises(Exception):
            SectionEnrichment.model_validate(
                {"key_idea": "Test.", "meanings": [], "check": None},
                context={"word_indexes": [0, 1]},
            )

    def test_rejects_extra(self):
        with pytest.raises(Exception):
            SectionEnrichment.model_validate(
                {"key_idea": "Test.", "meanings": [
                    {"i": 0, "vi": "a"}, {"i": 1, "vi": "b"}, {"i": 99, "vi": "x"},
                ], "check": None},
                context={"word_indexes": [0, 1]},
            )

    def test_accepts_exact(self):
        r = SectionEnrichment.model_validate(
            {"key_idea": "Test.", "meanings": [
                {"i": 0, "vi": "a"}, {"i": 1, "vi": "b"},
            ], "check": None},
            context={"word_indexes": [0, 1]},
        )
        assert len(r.meanings) == 2


class TestAllKeyIdeaMeaningsValidator:
    def test_rejects_incomplete(self):
        with pytest.raises(Exception):
            AllKeyIdeaMeanings.model_validate(
                {"meanings": [{"section_order": 0, "i": 0, "vi": "a"}]},
                context={"expected_pairs": {(0, 0), (0, 1)}},
            )

    def test_accepts_complete(self):
        r = AllKeyIdeaMeanings.model_validate(
            {"meanings": [
                {"section_order": 0, "i": 0, "vi": "a"},
                {"section_order": 0, "i": 1, "vi": "b"},
            ]},
            context={"expected_pairs": {(0, 0), (0, 1)}},
        )
        assert len(r.meanings) == 2


class TestArticleItemsValidator:
    def _make_items(self, forms):
        return [
            {"canonical_form": f, "type": "single_word", "pos": "Noun",
             "cefr_level": "A2", "vi": "v", "definition_en": "d",
             "extra_example": "e"} for f in forms
        ]

    def _make_quiz(self, n=3, typ="true_false"):
        return [
            {"type": typ, "question": f"Q{i}?",
             "options": ["True", "False"] + (["NG"] if typ == "true_false_ng" else []),
             "answer_index": 0, "explanation": "E"} for i in range(n)
        ]

    def test_rejects_unlocatable(self):
        toks = tokenize("Eating well is good for health.")
        with pytest.raises(Exception, match="not found"):
            ArticleItems.model_validate(
                {"items": self._make_items(["nonexistent xyz"] * 6),
                 "quiz": self._make_quiz()},
                context={"locate": locate, "section_tokens": [toks], "level": "A2"},
            )

    def test_rejects_ng_for_a2(self):
        toks = tokenize("Eating well is good for health.")
        with pytest.raises(Exception, match="true_false_ng"):
            ArticleItems.model_validate(
                {"items": self._make_items(["eating"] * 6),
                 "quiz": [self._make_quiz(1, "true_false_ng")[0],
                          *self._make_quiz(2)]},
                context={"locate": locate, "section_tokens": [toks], "level": "A2"},
            )

    def test_rejects_missing_required_item(self):
        toks = tokenize("Eating well plays a vital role in good health.")
        with pytest.raises(Exception, match="Required items missing"):
            ArticleItems.model_validate(
                {"items": self._make_items(["health"] * 6), "quiz": self._make_quiz()},
                context={"locate": locate, "section_tokens": [toks], "level": "A2",
                         "required_keys": {lemma_key("play a vital role in"): "play a vital role in"}},
            )

    def test_accepts_required_item_present(self):
        toks = tokenize("Eating well plays a vital role in good health.")
        res = ArticleItems.model_validate(
            {"items": self._make_items(["play a vital role in"] + ["health"] * 5),
             "quiz": self._make_quiz()},
            context={"locate": locate, "section_tokens": [toks], "level": "A2",
                     "required_keys": {lemma_key("play a vital role in"): "play a vital role in"}},
        )
        assert res.items[0].canonical_form == "play a vital role in"

    def test_rejects_excluded_item(self):
        toks = tokenize("Avoid saturated and trans fats for good health.")
        with pytest.raises(Exception, match="Excluded items selected"):
            ArticleItems.model_validate(
                {"items": self._make_items(["saturated and trans fats"] + ["health"] * 5),
                 "quiz": self._make_quiz()},
                context={"locate": locate, "section_tokens": [toks], "level": "A2",
                         "excluded_keys": {lemma_key("saturated and trans fats"):
                                           "saturated and trans fats"}},
            )


class TestMeaningOverrides:
    def _sd(self, text, order=5):
        toks = tokenize(text)
        return {"order": order, "tokens": toks,
                "meanings": {t["i"]: "x" for t in toks if t["is_word"]}}

    def test_overrides_by_text_and_nth(self):
        sd = self._sd("Serve fish. Serve eggs.")
        ov = Overrides(meanings=[MeaningOverride(section_order=5, text="Serve", vi="ăn", nth=2)])
        applied = apply_meaning_overrides([sd], ov)
        serve_idx = [t["i"] for t in sd["tokens"] if t["text"] == "Serve"]
        assert sd["meanings"][serve_idx[0]] == "x"
        assert sd["meanings"][serve_idx[1]] == "ăn"
        assert len(applied) == 1

    def test_override_in_key_idea(self):
        sd = self._sd("People do eat fish.")
        ki = tokenize("People do not know.")
        sd.update(key_idea_tokens=ki, key_idea_meanings={t["i"]: "x" for t in ki if t["is_word"]})
        ov = Overrides(meanings=[MeaningOverride(section_order=5, text="do", vi="không", in_key_idea=True)])
        applied = apply_meaning_overrides([sd], ov)
        do_ki = [t["i"] for t in ki if t["text"] == "do"][0]
        do_body = [t["i"] for t in sd["tokens"] if t["text"] == "do"][0]
        assert sd["key_idea_meanings"][do_ki] == "không" and sd["meanings"][do_body] == "x"
        assert "key idea" in applied[0]

    def test_missing_target_raises(self):
        sd = self._sd("Serve fish.")
        ov = Overrides(meanings=[MeaningOverride(section_order=5, text="great", vi="tốt")])
        with pytest.raises(ValueError, match="không tìm thấy"):
            apply_meaning_overrides([sd], ov)

    def test_load_missing_file_is_empty(self, tmp_path):
        ov = load_overrides(tmp_path / "overrides.json")
        assert ov.required_items == [] and ov.meanings == []


class TestQuickCheckValidator:
    def test_rejects_bad_index(self):
        with pytest.raises(Exception):
            QuickCheckResponse(question="Q?", options=["A", "B"],
                               answer_index=5, explanation="E")

    def test_accepts_valid(self):
        qc = QuickCheckResponse(question="Q?", options=["A", "B"],
                                answer_index=1, explanation="E")
        assert qc.answer_index == 1


# ── Bundle assembly ─────────────────────────────────────────────

class TestBuildBundle:
    """Minimal bundle from hand-crafted data passes ArticleBundle.model_validate."""

    def test_validates(self):
        body = "Eating well is good for your health."
        tokens = tokenize(body)
        meanings = {t["i"]: f"m{t['i']}" for t in tokens if t["is_word"]}

        ki = "Food helps your body."
        ki_tokens = tokenize(ki)
        ki_meanings = {t["i"]: f"k{t['i']}" for t in ki_tokens if t["is_word"]}

        sd = {
            "order": 0, "title": "Test", "body": body,
            "icon_hint": "food", "section_id": "sec_test_0",
            "slug_under": "test", "tokens": tokens,
            "meanings": meanings, "key_idea_text": ki,
            "key_idea_tokens": ki_tokens,
            "key_idea_meanings": ki_meanings, "check": None,
        }

        items = [
            SelectedItem(canonical_form="eating", type="single_word", pos="Verb",
                         cefr_level="A2", vi="ăn", definition_en="d", extra_example="e"),
            SelectedItem(canonical_form="health", type="single_word", pos="Noun",
                         cefr_level="A2", vi="sk", definition_en="d", extra_example="e"),
            SelectedItem(canonical_form="well", type="single_word", pos="Adverb",
                         cefr_level="A2", vi="tốt", definition_en="d", extra_example="e"),
            SelectedItem(canonical_form="good", type="single_word", pos="Adj",
                         cefr_level="A2", vi="tốt", definition_en="d", extra_example="e"),
        ]
        # pad to 6 with additional locatable words
        for w in ["eating well", "your"]:
            items.append(SelectedItem(
                canonical_form=w, type="collocation" if " " in w else "single_word",
                pos="VP" if " " in w else "Pron", cefr_level="A2", vi="v",
                definition_en="d", extra_example="e",
            ))

        quiz = [
            QuizItemResponse(type="true_false", question=f"Q{n}?",
                             options=["True", "False"], answer_index=0,
                             explanation="E")
            for n in range(3)
        ]

        occs = []
        counter = 1
        for item in items:
            lex_id = item_to_lex_id(item.canonical_form)
            for start, end in locate(tokens, item.canonical_form):
                cloze = sentence_cloze(tokens, start, end)
                sent = extract_sentence(tokens, start, end)
                occs.append({
                    "id": f"occ_test_{counter}",
                    "lexicon_entry_id": lex_id,
                    "section_id": "sec_test_0",
                    "token_start": start, "token_end": end,
                    "vi": item.vi,
                    "example_sentence": sent, "cloze": cloze,
                })
                counter += 1

        details = {it.canonical_form: {"cefr_level": "B1", "ipa": "/x/", "definition_en": "def",
                                       "extra_example": "ex"} for it in items}
        data = build_bundle("test", "Test", "Cat", "A2", "Src", False,
                            [sd], items, quiz, occs, details)
        bundle = ArticleBundle.model_validate(data)
        assert bundle.contract_version == "1.5"
        # 1.5: bundle giữ cover_url null (seed điền), excerpt = câu đầu card đầu
        assert bundle.article.cover_url is None
        first = "".join(t["text"] + t["ws"] for t in data["sections"][0]["tokens"])
        assert bundle.article.excerpt and first.startswith(bundle.article.excerpt.rstrip("…"))
        assert build_bundle("test", "Test", "Cat", "A2", "Src", False, [sd], items, quiz, occs, details,
                            excerpt="Hand-written.")["article"]["excerpt"] == "Hand-written."
        assert bundle.article.word_count > 0
        assert bundle.article.section_count == 1
        assert all(e.cefr_level == "B1" and e.definition_en == "def" for e in bundle.lexicon)
        for s in bundle.sections:
            for t in s.tokens:
                if t.is_word:
                    assert t.vi, f"body token {t.i} '{t.text}' missing vi"
                    assert t.ipa, f"body token '{t.text}' missing ipa"
                else:
                    assert t.ipa is None
            for t in s.key_idea.tokens:
                if t.is_word:
                    assert t.vi, f"key_idea token {t.i} '{t.text}' missing vi"
                    assert t.ipa


# ── Card details (step 4b) ──────────────────────────────────────

def _item(form, typ="collocation", cefr="B1", ipa=None):
    return SelectedItem(canonical_form=form, type=typ, pos="phrase", cefr_level=cefr,
                        vi="v", ipa=ipa, definition_en="d", extra_example="e")


class TestEntryDetail:
    CTX = {"forms": ["tend to"], "originals": {"tend to": "Meals tend to have more salt."}}

    def _make(self, **kw):
        base = {"canonical_form": "tend to", "cefr_level": "B1",
                "definition_en": "to be likely to do something",
                "extra_example": "I tend to wake up early on weekends."}
        base.update(kw)
        return EntryDetails.model_validate({"entries": [base]}, context=self.CTX)

    def test_valid(self):
        assert self._make().entries[0].cefr_level == "B1"

    def test_inflected_example_ok(self):
        self._make(extra_example="She tends to sleep late.")

    def test_definition_too_long(self):
        with pytest.raises(Exception, match="definition_en has"):
            self._make(definition_en=" ".join(["word"] * 16))

    def test_example_must_contain_item(self):
        with pytest.raises(Exception, match="must contain the item"):
            self._make(extra_example="I usually wake up early.")

    def test_example_must_not_copy_article(self):
        with pytest.raises(Exception, match="copies the article"):
            self._make(extra_example="Meals tend to have more salt")

    def test_coverage(self):
        with pytest.raises(Exception, match="missing"):
            EntryDetails.model_validate({"entries": []}, context=self.CTX)


class TestMergeEntryDetails:
    def _details(self, cefr="B1"):
        return EntryDetails.model_construct(entries=[EntryDetail.model_construct(
            canonical_form="tend to", cefr_level=cefr, definition_en="def",
            extra_example="I tend to wake up early.")])

    def test_ipa_from_cmudict_and_no_flag(self):
        out, applied = merge_entry_details([_item("tend to", ipa="/llm/")], self._details(), Overrides())
        assert out["tend to"]["ipa"] == "/tɛnd tu/"
        assert out["tend to"]["ipa_source"] == "cmudict"
        assert out["tend to"]["cefr_note"] == "" and applied == []

    def test_llm_ipa_fallback_for_oov(self):
        out, _ = merge_entry_details([_item("carotenoids", "single_word", ipa="/k/")],
                                     EntryDetails.model_construct(entries=[EntryDetail.model_construct(
                                         canonical_form="carotenoids", cefr_level="B2",
                                         definition_en="d", extra_example="e")]),
                                     Overrides())
        assert out["carotenoids"]["ipa"] == "/k/" and out["carotenoids"]["ipa_source"] == "llm"

    def test_cefr_disagreement_flagged(self):
        out, _ = merge_entry_details([_item("tend to", cefr="A2")], self._details("B1"), Overrides())
        assert "A2" in out["tend to"]["cefr_note"]

    def test_override_wins(self):
        ov = Overrides(lexicon={"tend to": LexiconOverride(cefr_level="B2", definition_en="x")})
        out, applied = merge_entry_details([_item("tend to", cefr="A2")], self._details(), ov)
        assert out["tend to"]["cefr_level"] == "B2" and out["tend to"]["definition_en"] == "x"
        assert out["tend to"]["cefr_note"] == "sửa tay" and len(applied) == 2

    def test_override_unknown_item_raises(self):
        ov = Overrides(lexicon={"eat out": LexiconOverride(cefr_level="A2")})
        with pytest.raises(ValueError, match="eat out"):
            merge_entry_details([_item("tend to")], self._details(), ov)


# ── overrides.lexicon[*].vi (run #28) ───────────────────────────

def test_apply_vi_overrides_updates_item_and_all_occurrences():
    from pipeline.enrich import apply_vi_overrides
    items = [_item("an apple a day"), _item("tend to")]
    lex = item_to_lex_id("an apple a day")
    occs = [{"lexicon_entry_id": lex, "vi": "v"}, {"lexicon_entry_id": lex, "vi": "v"},
            {"lexicon_entry_id": item_to_lex_id("tend to"), "vi": "v"}]
    ov = Overrides.model_validate({"lexicon": {"An apple a day": {"vi": "mỗi ngày một quả táo"}}})
    applied = apply_vi_overrides(items, occs, ov)
    assert items[0].vi == "mỗi ngày một quả táo" and items[1].vi == "v"
    assert [o["vi"] for o in occs] == ["mỗi ngày một quả táo"] * 2 + ["v"]
    assert applied == ['an apple a day.vi: "v" → "mỗi ngày một quả táo"']


def test_vi_override_does_not_break_merge_entry_details():
    from pipeline.enrich import merge_entry_details
    items = [_item("in moderation", cefr="A2")]
    details = EntryDetails.model_construct(entries=[EntryDetails.model_fields["entries"].annotation.__args__[0]
                                                    .model_construct(canonical_form="in moderation", cefr_level="B1",
                                                                     definition_en="d", extra_example="e")])
    ov = Overrides.model_validate({"lexicon": {"in moderation": {"cefr_level": "C1", "vi": "x"}}})
    out, applied = merge_entry_details(items, details, ov)
    assert out["in moderation"]["cefr_level"] == "C1" and out["in moderation"]["cefr_note"] == "sửa tay"
    assert all(".vi" not in a for a in applied)


# ── ADR-016: số mục từ theo cấp độ + độ dài; CEFR i+1 ───────────

def test_item_count_range_matches_user_examples():
    # Người dùng chốt run #38: khoảng 1 mục / 60-80 từ, kẹp trong trần theo cấp.
    from pipeline.enrich import item_count_range
    assert item_count_range("A2", 650) == (8, 10)      # 650/80 ≈ 8, 650/60 ≈ 11 → trần A2 10
    assert item_count_range("B2", 769) == (10, 13)     # 769/80 ≈ 10, 769/60 ≈ 13
    assert item_count_range("B1", 761) == (10, 12)     # robots
    assert item_count_range("B1", 300) == (8, 9)       # bài ngắn: kẹp ở đáy B1
    assert item_count_range("B2", 2000) == (14, 15)    # bài dài: kẹp ở trần B2
    for lvl, (lo_b, hi_b) in {"A2": (6, 10), "B1": (8, 12), "B2": (10, 15)}.items():
        for w in range(100, 3000, 37):
            lo, hi = item_count_range(lvl, w)
            assert lo_b <= lo < hi <= hi_b


def test_allowed_cefr_is_i_plus_one():
    from pipeline.enrich import allowed_cefr
    assert allowed_cefr("A2") == ("A2", "B1")
    assert allowed_cefr("B1") == ("B1", "B2")
    assert allowed_cefr("B2") == ("B2", "C1")


# ── BE-06e1: từ điển CEFR dùng chung, known_entries mọi bài, định nghĩa ──

def test_cefr_dict_has_reviewed_values_and_one_level_per_item():
    from pipeline.enrich import load_cefr_dict
    d = load_cefr_dict()
    expect = {"play a vital role in": "C1", "in moderation": "C1", "irrigation": "B2",
              "lie fallow": "C2", "water wheel": "B1", "stage": "B2", "high in": "B1"}
    for form, lvl in expect.items():
        assert d[lemma_key(form)]["cefr"] == lvl
    assert len(d) >= 40  # mỗi lemma_key đúng 1 cấp → mọi bài dùng chung


def test_cefr_dict_beats_llm_but_article_override_beats_dict():
    from pipeline.enrich import load_cefr_dict
    d = load_cefr_dict()
    det = EntryDetails.model_construct(entries=[EntryDetail.model_construct(
        canonical_form="irrigation", cefr_level="B1", definition_en="Supplying water to land.",
        extra_example="e")])
    out, _ = merge_entry_details([_item("irrigation", "single_word", cefr="B1")], det, Overrides(), d)
    assert out["irrigation"]["cefr_level"] == "B2"
    assert out["irrigation"]["cefr_note"].startswith("từ điển")
    ov = Overrides(lexicon={"irrigation": LexiconOverride(cefr_level="C1")})
    out, _ = merge_entry_details([_item("irrigation", "single_word", cefr="B1")], det, ov, d)
    assert out["irrigation"]["cefr_level"] == "C1" and out["irrigation"]["cefr_note"] == "sửa tay"


def test_validator_uses_dict_level_for_i_plus_one():
    toks = tokenize("Farmers use irrigation to water the fields.")
    items = [{"canonical_form": "irrigation", "type": "single_word", "pos": "Noun",
              "cefr_level": "A2", "vi": "v", "definition_en": "d", "extra_example": "e"}] * 6
    quiz = [{"type": "true_false", "question": "Q?", "options": ["T", "F"],
             "answer_index": 0, "explanation": "E"}] * 3
    ctx = {"locate": locate, "section_tokens": [toks], "level": "B1",
           "allowed_cefr": ("B1", "B2"), "count_range": (6, 6)}
    with pytest.raises(Exception, match="outside the allowed CEFR"):   # LLM nói A2
        ArticleItems.model_validate({"items": items, "quiz": quiz}, context=ctx)
    ArticleItems.model_validate({"items": items, "quiz": quiz},
                                context={**ctx, "cefr_dict": {"irrigation": "B2"}})


@pytest.mark.parametrize("raw,norm", [
    ("Grains that keep all parts of the seed.", "grains that keep all parts of the seed"),
    ("to usually do or be something", "to usually do or be something"),
    ("  A machine that can think.  ", "a machine that can think"),
    ("AI used to make decisions.", "AI used to make decisions"),
])
def test_normalize_definition(raw, norm):
    from pipeline.enrich import normalize_definition
    assert normalize_definition(raw) == norm


def _write_bundle(root, slug, forms):
    (root / slug).mkdir(parents=True)
    lex = [{"canonical_form": f, "lemma_key": lemma_key(f), "cefr_level": c} for f, c in forms]
    (root / slug / "bundle.json").write_text(__import__("json").dumps({"lexicon": lex}), "utf-8")


def test_known_entries_from_all_earlier_articles_any_level(tmp_path):
    import json
    from pipeline.enrich import collect_known_entries
    _write_bundle(tmp_path, "eating-well", [("play a vital role in", "C1"), ("high in", "B1")])
    _write_bundle(tmp_path, "robots", [("make decisions", "B1"), ("high in", "B1")])
    _write_bundle(tmp_path, "water-power", [("generate electricity", "B2")])
    (tmp_path / "processing_order.json").write_text(
        json.dumps(["eating-well", "robots", "water-power"]), "utf-8")
    got = collect_known_entries("water-power", tmp_path)
    assert [e["form"] for e in got] == ["play a vital role in", "high in", "make decisions"]
    assert collect_known_entries("eating-well", tmp_path) == []
    assert len(collect_known_entries("new-slug", tmp_path)) == 4   # ngoài danh sách → mọi bài


def _shared_known(card_overrides=None):
    card = {"canonical_form": "play a vital role in", "type": "collocation", "pos": "verb phrase",
            "cefr_level": "C1", "ipa": "/old/", "definition_en": "to be very important in something",
            "extra_example": "Teachers play a vital role in our lives."}
    card.update(card_overrides or {})
    return [{"form": "play a vital role in", "cefr": "C1", "slug": "eating-well", "card": card}]


def test_known_entries_carry_card_of_first_article(tmp_path):
    import json
    from pipeline.enrich import collect_known_entries
    _write_bundle(tmp_path, "eating-well", [("high in", "B1")])
    _write_bundle(tmp_path, "robots", [("high in", "B2")])
    (tmp_path / "processing_order.json").write_text(json.dumps(["eating-well", "robots", "x"]), "utf-8")
    got = collect_known_entries("x", tmp_path)
    assert len(got) == 1 and got[0]["slug"] == "eating-well"
    assert got[0]["card"]["cefr_level"] == "B1"


def test_shared_card_replaces_generated_card_in_bundle():
    from pipeline.enrich import apply_shared_cards
    item = _item("play a vital role in", cefr="B2")
    details = {"play a vital role in": {"cefr_level": "B2", "ipa": "/new/", "ipa_source": "llm",
                                        "definition_en": "new def", "extra_example": "New one.",
                                        "cefr_note": ""}}
    applied = apply_shared_cards([item], details, _shared_known(), Overrides())
    d = details["play a vital role in"]
    assert d["definition_en"] == "to be very important in something"
    assert d["extra_example"] == "Teachers play a vital role in our lives."
    assert (d["cefr_level"], d["ipa"], d["pos"]) == ("C1", "/old/", "verb phrase")
    assert d["cefr_note"].startswith("thẻ dùng chung")
    assert "eating-well" in applied[0] and "definition_en" in applied[0]


def test_shared_card_skips_items_not_known_and_known_without_card():
    from pipeline.enrich import apply_shared_cards
    details = {"tend to": {"cefr_level": "B1", "definition_en": "x", "cefr_note": ""}}
    known = [{"form": "tend to", "cefr": "B1", "slug": "a"}]          # --known-entries: không có thẻ
    assert apply_shared_cards([_item("tend to")], details, known, Overrides()) == []
    assert apply_shared_cards([_item("tend to")], details, _shared_known(), Overrides()) == []
    assert details["tend to"]["definition_en"] == "x"


def test_override_on_shared_card_in_later_article_is_error():
    from pipeline.enrich import apply_shared_cards
    item = _item("play a vital role in")
    details = {"play a vital role in": {"cefr_level": "B2", "definition_en": "x", "cefr_note": ""}}
    ov = Overrides.model_validate({"lexicon": {"play a vital role in": {"definition_en": "y"}}})
    with pytest.raises(ValueError, match="eating-well"):
        apply_shared_cards([item], details, _shared_known(), ov)
    ov_vi = Overrides.model_validate({"lexicon": {"play a vital role in": {"vi": "đóng vai trò"}}})
    apply_shared_cards([item], details, _shared_known(), ov_vi)       # vi theo bài: vẫn được


def test_drop_items_removes_item_occurrences_and_card():
    from pipeline.enrich import apply_drop_items
    items = [_item("tend to"), _item("in moderation")]
    occ = [{"lexicon_entry_id": "lex_tend_to"}, {"lexicon_entry_id": "lex_in_moderation"}]
    details = {"tend to": {}, "in moderation": {}}
    ov = Overrides.model_validate({"drop_items": ["in moderation"]})
    kept, occ2, applied = apply_drop_items(items, occ, details, ov)
    assert [i.canonical_form for i in kept] == ["tend to"]
    assert occ2 == [{"lexicon_entry_id": "lex_tend_to"}]
    assert list(details) == ["tend to"] and applied
    with pytest.raises(ValueError, match="drop_items"):
        apply_drop_items(items, occ, {}, Overrides.model_validate({"drop_items": ["nope"]}))


def test_known_entries_keep_dropped_items_in_order_but_never_force_reuse(tmp_path):
    import json
    from pipeline.enrich import SELECTED_ITEMS_FILE, collect_known_entries, plan_reuse
    _write_bundle(tmp_path, "eating-well", [("high in", "B1"), ("tend to", "B1")])
    (tmp_path / "eating-well" / SELECTED_ITEMS_FILE).write_text(json.dumps(
        [{"form": "high in", "cefr": "B1"}, {"form": "nutritional value", "cefr": "B2"},
         {"form": "tend to", "cefr": "B1"}]), "utf-8")
    (tmp_path / "processing_order.json").write_text(json.dumps(["eating-well", "x"]), "utf-8")
    got = collect_known_entries("x", tmp_path)
    assert [e["form"] for e in got] == ["high in", "nutritional value", "tend to"]  # prompt bài sau không đổi
    assert got[1].get("dropped") and "card" not in got[1]
    sd = [{"tokens": tokenize("Its nutritional value is high in summer.")}]
    assert plan_reuse(sd, got) == ["high in"]


def test_plan_reuse_requires_known_items_found_in_text():
    from pipeline.enrich import plan_reuse
    sd = [{"tokens": tokenize("Robots play a vital role in factories and make decisions fast.")}]
    known = [{"form": "play a vital role in", "cefr": "C1"}, {"form": "high in", "cefr": "B1"},
             {"form": "make decisions", "cefr": "B1"}]
    assert plan_reuse(sd, known) == ["play a vital role in", "make decisions"]
    assert plan_reuse(sd, known, excluded_items=["make decisions"]) == ["play a vital role in"]
    assert plan_reuse(sd, known, cap=1) == ["play a vital role in"]
    # Mục dễ hơn cấp bài không bị ép chọn lại (robots chọn "learn" A1 → farming B1 bỏ qua)
    assert plan_reuse(sd, known, level="B2") == ["play a vital role in"]


def test_resolve_title_override_wins():
    """overrides.title > --title > normalized title (ALL CAPS → Title Case)."""
    ov = Overrides.model_validate({"title": "Farming"})
    assert resolve_title("FARMING Feeding the world", "CLI", ov) == "Farming"
    assert resolve_title("FARMING Feeding the world", "CLI", Overrides()) == "CLI"
    assert resolve_title("ROBOTS", None, Overrides()) == "Robots"
    with pytest.raises(Exception):
        Overrides.model_validate({"title": ""})
