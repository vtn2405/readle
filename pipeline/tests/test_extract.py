"""Unit tests cho pipeline.extract (phan thuan logic, khong can PaddleOCR)."""
import pytest
from pydantic import ValidationError

from pipeline.extract import (
    LABEL_TO_ROLE,
    ExtractedArticle,
    ExtractedSection,
    NormalizedSections,
    OcrLine,
    PIPELINE_DIR,
    blocks_from_plain_ocr,
    blocks_from_structure,
    lines_from_ocr_res,
    nearest_block_index,
    normalized_from_extracted,
    poly_to_box,
    validate_normalized,
)


def line(text, box, conf=0.95):
    return OcrLine(text=text, box=box, confidence=conf)


class TestPolyToBox:
    def test_quad_points(self):
        assert poly_to_box([[10, 20], [110, 22], [110, 50], [10, 48]]) == [10, 20, 110, 50]

    def test_flat_box_passthrough(self):
        assert poly_to_box([1, 2, 3, 4]) == [1.0, 2.0, 3.0, 4.0]


class TestNearestBlock:
    boxes = [[0, 0, 100, 100], [200, 0, 300, 100]]

    def test_center_inside(self):
        assert nearest_block_index([10, 10, 50, 30], self.boxes) == 0
        assert nearest_block_index([210, 10, 290, 30], self.boxes) == 1

    def test_outside_falls_to_nearest(self):
        # tam (120, 50): cach tam block 0 (50,50) = 70 < cach tam block 1 (250,50) = 130
        assert nearest_block_index([110, 40, 130, 60], self.boxes) == 0
        # tam (200, 50): cach block 1 = 50 < cach block 0 = 150
        assert nearest_block_index([180, 40, 220, 60], self.boxes) == 1


class TestLinesFromOcrRes:
    def test_rec_boxes_format(self):
        res = {"rec_texts": ["Hello", " ", "World"],
               "rec_scores": [0.99, 0.5, 0.42],
               "rec_boxes": [[0, 0, 10, 10], [0, 20, 10, 30], [0, 40, 10, 50]]}
        lines = lines_from_ocr_res(res)
        assert [l.text for l in lines] == ["Hello", "World"]  # dong trang bi bo
        assert lines[1].confidence == 0.42

    def test_rec_polys_format(self):
        res = {"rec_texts": ["A"], "rec_scores": [0.9],
               "rec_polys": [[[0, 0], [10, 0], [10, 5], [0, 5]]]}
        assert lines_from_ocr_res(res)[0].box == [0, 0, 10, 5]


class TestBlocksFromStructure:
    def test_labels_map_to_roles_and_order(self):
        parsing = [
            {"block_label": "doc_title", "block_content": "Eating Well", "block_bbox": [0, 0, 400, 40]},
            {"block_label": "paragraph_title", "block_content": "Broccoli", "block_bbox": [0, 60, 200, 90]},
            {"block_label": "text", "block_content": "Rich in vitamins.", "block_bbox": [0, 100, 200, 160]},
            {"block_label": "image", "block_content": "", "block_bbox": [250, 60, 400, 160]},
        ]
        lines = [line("Eating Well", [5, 5, 390, 35], 0.99),
                 line("Broccoli", [5, 65, 100, 85], 0.97),
                 line("Rich in vitamins.", [5, 105, 190, 125], 0.88)]
        blocks = blocks_from_structure(parsing, lines)
        assert [b.role for b in blocks] == ["article_title", "section_title", "body"]
        assert [b.order for b in blocks] == [0, 1, 2]  # block image rong bi bo, order lien tuc
        assert blocks[2].lines[0].confidence == 0.88

    def test_fallback_text_from_lines_when_content_empty(self):
        parsing = [{"block_label": "text", "block_content": "", "block_bbox": [0, 0, 100, 100]}]
        lines = [line("second", [0, 50, 90, 70]), line("first", [0, 10, 90, 30])]
        blocks = blocks_from_structure(parsing, lines)
        assert blocks[0].text == "first second"  # xep theo y truoc khi noi

    def test_unknown_label_defaults_to_body(self):
        parsing = [{"block_label": "mystery", "block_content": "x", "block_bbox": [0, 0, 1, 1]}]
        assert blocks_from_structure(parsing, [])[0].role == "body"


class TestBlocksFromPlainOcr:
    def test_reading_order_top_down_left_right(self):
        lines = [line("b", [0, 100, 50, 120]), line("a", [0, 10, 50, 30]),
                 line("a2", [60, 10, 100, 30])]
        blocks = blocks_from_plain_ocr(lines)
        assert [b.text for b in blocks] == ["a", "a2", "b"]
        assert all(b.role == "body" for b in blocks)


class TestNormalizedSchema:
    def good(self):
        return {"schema_version": 1, "slug": "eating-well", "title": "Eating Well",
                "sections": [{"order": 0, "title": "Intro", "body": "Fifty words here.", "icon_hint": ""}]}

    def test_valid(self):
        data = NormalizedSections.model_validate(self.good())
        assert data.sections[0].order == 0

    def test_empty_sections_rejected(self):
        bad = self.good() | {"sections": []}
        with pytest.raises(ValidationError):
            NormalizedSections.model_validate(bad)

    def test_empty_body_rejected(self):
        bad = self.good()
        bad["sections"][0]["body"] = ""
        with pytest.raises(ValidationError):
            NormalizedSections.model_validate(bad)


class TestReviewTemplate:
    def test_placeholders_present(self):
        html = (PIPELINE_DIR / "review_template.html").read_text(encoding="utf-8")
        assert "__OCR_JSON__" in html
        assert "__IMAGES_JSON__" in html
        assert "normalized_sections.json" in html


class TestVisionNormalize:
    def art(self):
        return ExtractedArticle(title=" Eating Well ", sections=[
            ExtractedSection(order=5, title="Tips", body=" Eat plants. ", icon_hint="Salad"),
            ExtractedSection(order=2, title="Intro", body="Eating well matters.", icon_hint=""),
        ])

    def test_sorts_by_order_and_renumbers_from_zero(self):
        data = normalized_from_extracted("eating-well", self.art())
        assert [s.title for s in data.sections] == ["Intro", "Tips"]
        assert [s.order for s in data.sections] == [0, 1]

    def test_strips_and_lowercases_icon(self):
        data = normalized_from_extracted("eating-well", self.art())
        assert data.title == "Eating Well"
        assert data.sections[1].body == "Eat plants."
        assert data.sections[1].icon_hint == "salad"


class TestValidateNormalized:
    def test_flags_short_text_and_wrong_slug(self):
        data = normalized_from_extracted("x", ExtractedArticle(title="T", sections=[
            ExtractedSection(order=0, title="A", body="too short", icon_hint="")]))
        problems = validate_normalized(data, "y")
        assert any("qua it" in p for p in problems)
        assert any("slug" in p for p in problems)

    def test_ok_when_enough_words(self):
        body = "word " * 60
        data = normalized_from_extracted("x", ExtractedArticle(title="T", sections=[
            ExtractedSection(order=0, title="A", body=body, icon_hint="")]))
        assert validate_normalized(data, "x") == []


def test_role_map_covers_core_labels():
    for lbl in ("doc_title", "paragraph_title", "text", "image", "header", "footer"):
        assert lbl in LABEL_TO_ROLE
