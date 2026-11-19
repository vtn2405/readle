"""Tests cho `assemble` (BE-02c, ADR-012) — thuan logic, khong goi API, khong can PaddleOCR."""
import pytest
from pydantic import ValidationError

from pipeline.extract import (
    AssembledArticle,
    AsmLine,
    OcrBlock,
    OcrLine,
    OcrRaw,
    assemble_report,
    assemble_sections,
    assign_line_ids,
    NormalizedSection,
    NormalizedSections,
    join_lines,
    normalize_article_quotes,
    normalize_quotes_paragraph,
    punctuation_suspects,
)


class TestNormalizeQuotes:
    def test_mixed_curly_open_straight_close(self):
        assert normalize_quotes_paragraph('called it “an early demo" and') == "called it “an early demo” and"

    def test_space_before_closing_removed(self):
        assert (normalize_quotes_paragraph('started "That\'s a big question. ". When')
                == "started “That's a big question.”. When")

    def test_straight_pairs_and_multi_sentence(self):
        s = 'a "raw" output. “You don\'t want to do that. The rest." Then “festive season,"'
        assert normalize_quotes_paragraph(s) == (
            "a “raw” output. “You don't want to do that. The rest.” Then “festive season,”")

    def test_odd_count_returns_none(self):
        assert normalize_quotes_paragraph('“opens here and never closes') is None

    def test_apostrophes_untouched(self):
        assert normalize_quotes_paragraph("it's “Jacob's\"") == "it's “Jacob's”"

    def _doc(self, body: str) -> NormalizedSections:
        return NormalizedSections(slug="x", title="T", sections=[NormalizedSection(order=0, title="S", body=body)])

    def test_article_without_curly_is_unchanged(self):
        d = self._doc('a "raw" output')
        assert normalize_article_quotes(d) == []
        assert d.sections[0].body == 'a "raw" output'

    def test_article_with_curly_normalizes_all_and_reports_odd(self):
        d = self._doc('a "raw" output\n\n“opens and never closes\n\n“ok"')
        odd = normalize_article_quotes(d)
        assert d.sections[0].body == "a “raw” output\n\n“opens and never closes\n\n“ok”"
        assert len(odd) == 1 and "opens" in odd[0]

WORDS = {"vegetables", "prevention", "well", "being", "breakfast", "improving"}


def is_word(w: str) -> bool:
    return w.lower() in WORDS


def line(i, text, y, x=10, conf=0.99, page=0):
    return AsmLine(id=f"L{i:03d}", page=page, text=text, box=[x, y, x + 200, y + 13], confidence=conf)


LINES = [
    line(0, "WORLD OF WONDER", 0),
    line(1, "EATING WELL", 20),
    line(2, "Eat more fruit and veg-", 40),
    line(3, "etables every day. It helps", 55),
    line(4, "disease preven-", 70),
    line(5, "tion.", 85),
    line(6, "Tips", 100),
    line(7, "Restaurant meals have added salt. sugar and fat.", 115),
    line(8, "Broccoli", 130, x=400),
]
IDS = [l.id for l in LINES]


def article(**over):
    data = {
        "title_lines": ["L001"],
        "sections": [
            {"title_lines": [], "body_lines": ["L002", "L003", "L004", "L005"], "icon_hint": "Apple"},
            {"title_lines": ["L006"], "body_lines": ["L007"], "icon_hint": "list"},
        ],
        "ignore": ["L000", "L008"],
    }
    data.update(over)
    return data


def validate(data):
    return AssembledArticle.model_validate(data, context={"line_ids": IDS})


class TestCoverageValidator:
    def test_valid(self):
        assert len(validate(article()).sections) == 2

    def test_few_missing_ids_tolerated_for_repair(self):
        assert validate(article(ignore=["L000"])).ignore == ["L000"]

    def test_many_missing_ids_rejected(self):
        a = article(ignore=[])
        a["sections"][0]["body_lines"] = ["L002"]
        with pytest.raises(ValidationError, match=r"missing=\['L000', 'L003', 'L004', 'L005', 'L008'\]"):
            validate(a)

    def test_duplicate_id(self):
        with pytest.raises(ValidationError, match=r"duplicated=\['L001'\]"):
            validate(article(ignore=["L000", "L008", "L001"]))

    def test_too_many_ignored_words_rejected(self):
        words = {l.id: len(l.text.split()) for l in LINES}
        a = article(ignore=["L000", "L008", "L002", "L003", "L004", "L005", "L007"])
        a["sections"] = [{"title_lines": [], "body_lines": ["L006"], "icon_hint": "x"}]
        with pytest.raises(ValidationError, match=r"ignore holds \d+ of \d+ words"):
            AssembledArticle.model_validate(a, context={"line_ids": IDS, "line_words": words})

    def test_one_section_per_line_rejected(self):
        words = {i: 3 for i in IDS}  # bai that: moi dong ~3-6 tu
        a = article()
        a["sections"] = [{"title_lines": [], "body_lines": [i], "icon_hint": "x"}
                         for i in ["L002", "L003", "L004", "L005"]] + [
                        {"title_lines": ["L006"], "body_lines": ["L007"], "icon_hint": "x"}]
        with pytest.raises(ValidationError, match=r"5 sections averaging \d+ words"):
            AssembledArticle.model_validate(a, context={"line_ids": IDS, "line_words": words})

    def test_normal_ignore_share_accepted(self):
        words = {i: 20 for i in IDS}  # 2/9 dong bi bo, section trung binh >= 15 tu
        art = AssembledArticle.model_validate(article(), context={"line_ids": IDS, "line_words": words})
        assert art.ignore == ["L000", "L008"]

    def test_unknown_id(self):
        with pytest.raises(ValidationError, match=r"unknown=\['L999'\]"):
            validate(article(ignore=["L000", "L008", "L999"]))

    def test_paragraph_start_must_be_in_own_body(self):
        bad = article()
        bad["sections"][1]["paragraph_starts"] = ["L003"]
        with pytest.raises(ValidationError, match="paragraph_starts"):
            validate(bad)

    def test_no_context_skips_coverage(self):
        assert AssembledArticle.model_validate(article(ignore=[])).ignore == []

    def test_model_has_no_free_text_field_except_icon(self):
        # Thiet ke ADR-012: LLM khong duoc xuat chu cua bai.
        sec_fields = set(AssembledArticle.model_fields["sections"].annotation.__args__[0].model_fields)
        assert sec_fields == {"title_lines", "body_lines", "paragraph_starts", "icon_hint"}
        assert set(AssembledArticle.model_fields) == {"title_lines", "sections", "ignore"}


class TestJoinLines:
    def test_joins_dictionary_word(self):
        text, notes = join_lines(["Eat more veg-", "etables now."], is_word=is_word)
        assert text == "Eat more vegetables now."
        assert notes[0].joined and notes[0].known

    def test_keeps_hyphen_when_both_halves_are_words(self):
        text, notes = join_lines(["for your well-", "being."], is_word=is_word)
        assert text == "for your well-being."
        assert not notes[0].joined and not notes[0].known

    def test_unknown_word_joined_and_flagged(self):
        text, notes = join_lines(["rich in carot-", "enoids."], is_word=is_word)
        assert text == "rich in carotenoids."
        assert notes[0].joined and not notes[0].known

    def test_no_join_when_next_line_capitalised(self):
        text, notes = join_lines(["Fruit -", "Apples"], is_word=is_word)
        assert text == "Fruit - Apples"
        assert notes == []

    def test_dash_with_space_is_not_hyphenation(self):
        text, _ = join_lines(["very good for you -", "helping to reduce"], is_word=is_word)
        assert text == "very good for you - helping to reduce"

    def test_plain_lines_joined_with_space(self):
        assert join_lines(["a b", " c "], is_word=is_word)[0] == "a b c"


class TestAssemble:
    def test_text_is_verbatim_ocr(self):
        data, _ = assemble_sections("ew", validate(article()), LINES, is_word=is_word)
        assert data.title == "EATING WELL"
        assert data.sections[0].title == "EATING WELL"  # khong co tieu de rieng -> tieu de bai
        assert data.sections[0].body == "Eat more fruit and vegetables every day. It helps disease prevention."
        assert data.sections[1].body == "Restaurant meals have added salt. sugar and fat."  # khong tu sua
        assert data.sections[0].icon_hint == "apple"
        assert "WORLD OF WONDER" not in data.model_dump_json()

    def test_paragraph_breaks(self):
        a = article()
        a["sections"][0]["paragraph_starts"] = ["L004"]
        data, _ = assemble_sections("ew", validate(a), LINES, is_word=is_word)
        assert data.sections[0].body == "Eat more fruit and vegetables every day. It helps\n\ndisease prevention."

    def test_body_order_follows_llm_not_geometry(self):
        a = article()
        a["sections"] = [{"title_lines": ["L006"], "body_lines": ["L007"], "icon_hint": "x"},
                         {"title_lines": [], "body_lines": ["L002", "L003", "L004", "L005"], "icon_hint": "y"}]
        data, _ = assemble_sections("ew", validate(a), LINES, is_word=is_word)
        assert [s.title for s in data.sections] == ["Tips", "EATING WELL"]
        assert [s.order for s in data.sections] == [0, 1]


class TestRepairMissing:
    # Ca that (Eating Well): gpt-5-mini quen L028 giua 2 dong cung cot, 4 lan lien.
    COL = [
        AsmLine(id="L025", text="your plate with fruits and veg-", box=[222, 286, 351, 299], confidence=0.99),
        AsmLine(id="L026", text="risk of diabetes, high blood", box=[567, 286, 686, 299], confidence=0.99),
        AsmLine(id="L028", text="etables, you are on your way to a", box=[223, 297, 368, 310], confidence=0.99),
        AsmLine(id="L029", text="pressure and many types of", box=[567, 299, 690, 312], confidence=0.99),
        AsmLine(id="L030", text="healthy diet.", box=[224, 309, 277, 319], confidence=0.99),
        AsmLine(id="L033", text="Dairy", box=[900, 316, 922, 328], confidence=0.99),
    ]

    def art(self, ignore=()):
        return AssembledArticle.model_validate({
            "title_lines": ["L026"],
            "sections": [{"title_lines": [], "body_lines": ["L025", "L030"], "icon_hint": "x"},
                         {"title_lines": [], "body_lines": ["L029"], "icon_hint": "y"}],
            "ignore": list(ignore)})

    def test_missing_line_goes_between_same_column_neighbours(self):
        from pipeline.extract import repair_missing_lines
        a = self.art(ignore=["L033"])
        notes = repair_missing_lines(a, self.COL)
        assert a.sections[0].body_lines == ["L025", "L028", "L030"]
        assert [n.line_id for n in notes] == ["L028"]
        assert notes[0].placed in ("after L025", "before L030")
        data, _ = assemble_sections("ew", a, self.COL, is_word=lambda w: w == "vegetables")
        assert data.sections[0].body == "your plate with fruits and vegetables, you are on your way to a healthy diet."

    def test_line_with_no_column_neighbour_is_ignored_and_reported(self):
        from pipeline.extract import repair_missing_lines
        a = self.art()
        notes = repair_missing_lines(a, self.COL)
        assert "L033" in a.ignore
        assert ("L033", "ignore") in [(n.line_id, n.placed) for n in notes]
        data, hn = assemble_sections("ew", a, self.COL, is_word=lambda w: True)
        md = assemble_report(data, a, self.COL, hn, notes)
        assert "`L028` etables, you are on your way to a → trước `L030` (0. " in md
        assert "`L033` Dairy → **bỏ qua**" in md

    def test_nothing_missing(self):
        from pipeline.extract import repair_missing_lines
        a = self.art(ignore=["L033", "L028"])
        assert repair_missing_lines(a, self.COL) == []


class TestReport:
    def test_punctuation_suspects(self):
        assert punctuation_suspects("added salt. sugar and fat")
        assert punctuation_suspects("hot dogs. bologna, etc.) you eat")
        assert not punctuation_suspects("bacon, etc. you eat")
        assert not punctuation_suspects("fruit, e.g. apples")
        assert not punctuation_suspects("The U.S. Department")
        assert not punctuation_suspects("End. Next sentence")

    def test_report_lists_review_items(self):
        lines = LINES[:7] + [line(7, "Restaurant meals have added salt. sugar and fat.", 115, conf=0.72), LINES[8]]
        art = validate(article())
        data, notes = assemble_sections("ew", art, lines, is_word=is_word)
        md = assemble_report(data, art, lines, notes)
        assert "`L007` (0.72)" in md
        assert "salt. sugar" in md
        assert "`L000` WORLD OF WONDER" in md and "`L008` Broccoli" in md


def test_assign_line_ids_orders_by_page_then_position():
    def ol(t, x, y):
        return OcrLine(text=t, box=[x, y, x + 50, y + 10], confidence=0.9)
    raw = OcrRaw(slug="s", source="x", engine="paddleocr", blocks=[
        OcrBlock(block_id="b0", order=0, page=1, label="text", role="body", box=[0, 0, 1, 1],
                 text="", lines=[ol("p1 top", 0, 0)]),
        OcrBlock(block_id="b1", order=1, page=0, label="text", role="body", box=[0, 0, 1, 1],
                 text="", lines=[ol("p0 right", 300, 5), ol("p0 left", 0, 5), ol("  ", 0, 0), ol("p0 low", 0, 90)]),
    ])
    lines = assign_line_ids(raw)
    assert [l.text for l in lines] == ["p0 left", "p0 right", "p0 low", "p1 top"]
    assert [l.id for l in lines] == ["L000", "L001", "L002", "L003"]
