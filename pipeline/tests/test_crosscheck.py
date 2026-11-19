"""Tests cho phan doi chieu Vision <-> OCR (BE-02b) — thuan logic, khong can PaddleOCR."""
from pipeline.extract import (
    CROSSCHECK_THRESHOLD,
    ExtractedArticle,
    ExtractedSection,
    OcrLine,
    crosscheck_markdown,
    crosscheck_sections,
    crosscheck_status,
    file_sha256,
    group_lines,
    norm_chars,
    normalized_from_extracted,
    partial_ratio,
    split_chunks,
)


def L(text, x0, y0, x1=None, y1=None, conf=0.99):
    """Dong OCR cao 13px, rong theo so ky tu neu khong cho x1."""
    x1 = x1 if x1 is not None else x0 + 6 * len(text)
    y1 = y1 if y1 is not None else y0 + 13
    return OcrLine(text=text, box=[x0, y0, x1, y1], confidence=conf)


class TestNormAndSplit:
    def test_norm_drops_spaces_and_punct(self):
        assert norm_chars("Eating well plays a vital role") == norm_chars("Eatingwellplaysa vitalrole")
        assert norm_chars("preven-tion.") == "prevention"

    def test_split_merges_short_pieces(self):
        chunks = split_chunks("Eat well. Yes, really; it matters a lot — every single day of the year.")
        assert all(len(norm_chars(c)) >= 18 for c in chunks)
        assert "Eat well. Yes" in chunks[0]

    def test_split_single_short_text(self):
        assert split_chunks("Hi there.") == ["Hi there."]


class TestPartialRatio:
    def test_exact_substring(self):
        assert partial_ratio("vitalrole", "eatingwellplaysavitalroleingoodhealth") == 100

    def test_ocr_char_errors_only_dent_score(self):
        assert partial_ratio("energybooster", "xxxxxeneraybooster" + "y" * 50) >= 85

    def test_paraphrase_drops_score(self):
        needle = norm_chars("for example whole grain cereal")
        hay = norm_chars("Eating a breakfast high in quality protein from enriched cereal, yogurt, milk")
        assert partial_ratio(needle, hay) < CROSSCHECK_THRESHOLD

    def test_empty(self):
        assert partial_ratio("", "abc") == 100
        assert partial_ratio("abc", "") == 0


class TestGroupLines:
    def test_two_columns_not_interleaved(self):
        left = [L("Just two", 636, 495, 672), L("bananas provide", 635, 506, 703),
                L("enough energy", 636, 517, 697)]
        right_col_other = [L("meat (bacon, hot dogs.", 402, 489, 504), L("bologna, etc.) you eat", 403, 502, 501)]
        blocks = group_lines(left + right_col_other)
        texts = [" ".join(l.text for l in b) for b in blocks]
        assert "Just two bananas provide enough energy" in texts
        assert "meat (bacon, hot dogs. bologna, etc.) you eat" in texts

    def test_centered_last_line_joins_paragraph(self):
        para = [L("Restaurant and takeout meals tend to have more added salt.", 200, 189, 528),
                L("sugar and fat, so eat out in moderation.", 256, 206, 472)]
        assert len(group_lines(para)) == 1

    def test_big_vertical_gap_splits(self):
        assert len(group_lines([L("a line here", 10, 10), L("another line", 10, 80)])) == 2

    def test_empty(self):
        assert group_lines([]) == []


def _article(body7: str):
    return normalized_from_extracted("t", ExtractedArticle(title="Eating Well", sections=[
        ExtractedSection(order=0, title="Almost perfect", body=body7, icon_hint="banana"),
    ]))


OCR_BANANA = [
    L("Almost perfect", 598, 395, 698),
    L("Some consider bananas", 598, 413, 705),
    L("the perfect food because", 597, 426, 707),
    L("they are affordable.", 597, 437, 683),
    L("delicious and nutritious.", 598, 449, 700),
    L("Bananas have no fat, cho-", 597, 459, 703),
    L("lesterol or sodium, and they", 597, 470, 708),
    L("are loaded with vitamins.", 597, 481, 697),
    L("Just two", 636, 495, 672),
    L("bananas provide", 635, 506, 703),
    L("enough eneray", 636, 517, 697),          # loi OCR co y
    L("for a strenuous", 635, 526, 696),
    L("90-minute work-", 636, 537, 700),
    L("out. They also", 636, 548, 694),
    L("replenish carbo-", 636, 559, 700),
    L("hydrates, glyco-", 635, 570, 699),
    L("gen and bodily", 635, 581, 695),
    L("fluids burned", 635, 590, 688),
    L("during exercise.", 636, 601, 699),
    L("Banana", 542, 570, 581),                 # nhan hinh: khoi 1 tu, khong duoc lam cau bia dat diem
    L("SOURCES: World Booe Encyclap", 27, 962, 114, conf=0.90),
]
TRUE_BODY = ("Some consider bananas the perfect food because they are affordable, delicious and nutritious. "
             "Bananas have no fat, cholesterol or sodium, and they are loaded with vitamins. "
             "Just two bananas provide enough energy for a strenuous 90-minute workout. "
             "They also replenish carbohydrates, glycogen and bodily fluids burned during exercise.")
PARAPHRASED_BODY = ("Some consider bananas the perfect food because they are affordable, delicious and nutritious. "
                    "Bananas are a great energy booster and are loaded with vitamins. "
                    "Bananas provide enough energy for a strenuous 45-minute workout. "
                    "They also replenish carbohydrates and body fluids burned during exercise.")


class TestCrosscheck:
    def test_verbatim_text_passes_despite_hyphens_and_ocr_errors(self):
        rep = crosscheck_sections(_article(TRUE_BODY), OCR_BANANA)
        assert rep.flagged == [], [(c.chunk, c.score) for c in rep.flagged]

    def test_paraphrase_is_flagged_with_closest_ocr(self):
        rep = crosscheck_sections(_article(PARAPHRASED_BODY), OCR_BANANA)
        flagged = " | ".join(c.chunk for c in rep.flagged)
        assert "great energy booster" in flagged
        assert "45-minute" in flagged and "số không có trong OCR: 45" in flagged
        assert all(c.closest_ocr for c in rep.flagged)

    def test_short_label_block_does_not_rescue_invented_sentence(self):
        rep = crosscheck_sections(_article(PARAPHRASED_BODY), OCR_BANANA)
        booster = next(c for c in rep.chunks if "great energy booster" in c.chunk)
        assert booster.score < 70

    def test_titles_reported_separately_and_do_not_block(self):
        data = normalized_from_extracted("t", ExtractedArticle(title="Eating Well", sections=[
            ExtractedSection(order=0, title="Introduction", body=TRUE_BODY, icon_hint="")]))
        rep = crosscheck_sections(data, OCR_BANANA)
        assert rep.flagged == []
        assert [t.chunk for t in rep.odd_titles] == ["Introduction"]

    def test_crosscheck_status(self, tmp_path):
        sec = tmp_path / "normalized_sections.json"
        sec.write_text("{}", encoding="utf-8")
        assert crosscheck_status(tmp_path, sec)[0] == "missing"
        rep = crosscheck_sections(_article(PARAPHRASED_BODY), OCR_BANANA, sections_file=sec.name)
        rep.sections_sha256 = file_sha256(sec)
        (tmp_path / "crosscheck.json").write_text(rep.model_dump_json(), encoding="utf-8")
        assert crosscheck_status(tmp_path, sec)[0] == "flagged"
        sec.write_text("{ }", encoding="utf-8")
        assert crosscheck_status(tmp_path, sec)[0] == "stale"
        ok = crosscheck_sections(_article(TRUE_BODY), OCR_BANANA, sections_file=sec.name)
        ok.sections_sha256 = file_sha256(sec)
        (tmp_path / "crosscheck.json").write_text(ok.model_dump_json(), encoding="utf-8")
        assert crosscheck_status(tmp_path, sec)[0] == "ok"

    def test_number_present_in_ocr_is_not_flagged(self):
        rep = crosscheck_sections(_article(TRUE_BODY), OCR_BANANA)
        assert not any("số không có" in c.chunk for c in rep.chunks)

    def test_missed_ocr_line_reported_but_short_labels_ignored(self):
        rep = crosscheck_sections(_article(TRUE_BODY), OCR_BANANA + [L("Rainbow trout", 291, 587, 353)])
        assert [m.text for m in rep.missed] == ["SOURCES: World Booe Encyclap"]

    def test_markdown_has_sections(self):
        md = crosscheck_markdown(crosscheck_sections(_article(PARAPHRASED_BODY), OCR_BANANA))
        assert "## 1." in md and "## 2." in md and "45-minute" in md
