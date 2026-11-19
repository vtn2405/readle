"""BE-02d: cảnh báo kiểm chữ OCR bằng code (từ lạ, khoảng hở dọc, khối kết thúc dở) + phóng ảnh.
Dữ liệu mô phỏng đúng các lỗi thật của bài `paris` (run #78). Không chạy OCR/LLM."""
from pipeline.extract import (
    AsmLine, AssembledArticle, AssembledSection, OcrLine, assemble_sections, gap_warnings,
    is_known_word, scale_lines, text_warnings, unfinished_warnings, unknown_word_warnings,
    upscale_image,
)


def _line(i, text, y, x=27):
    return AsmLine(id=f"L{i:03d}", page=0, text=text, box=[x, y, x + 130, y + 10], confidence=0.99)


# Card "Parisians": dòng "are old, but cherished for their or-" bị OCR sót giữa L003 và L004.
PARIS_LINES = [
    _line(0, "PARIS", 0, x=270),
    _line(1, "More than half of all city", 576),
    _line(2, "dwellers live in studio and two-", 587),
    _line(3, "room apartments. The apartments", 598),
    _line(4, "nate fireplaces and historic charm.", 619),          # hở 21px
    _line(5, "Fashion and fine dining are very", 631),
    _line(6, "important to Parisians.", 643),
    _line(7, "It was finished around 1345. Hundreds of statues and", 700, x=163),
    _line(8, "gargoyles decorate the", 710, x=163),                 # sót dòng cuối
    _line(9, "Paris against the Enolish. This bridoe is old.", 780, x=35),
]
PARIS_ART = AssembledArticle.model_construct(
    title_lines=["L000"], ignore=[],
    sections=[
        AssembledSection(body_lines=["L001", "L002", "L003", "L004", "L005", "L006"],
                         paragraph_starts=["L005"], icon_hint="people"),
        AssembledSection(body_lines=["L007", "L008"], icon_hint="cathedral"),
        AssembledSection(body_lines=["L009"], icon_hint="fortress"),
    ])


def _data():
    data, _ = assemble_sections("paris", PARIS_ART, PARIS_LINES)
    return data


def test_known_word_rules():
    assert is_known_word("bridge")
    assert is_known_word("museum's")
    assert is_known_word("Parisians'")      # sở hữu số nhiều
    assert not is_known_word("bridoe")
    assert not is_known_word("Enolish")
    assert is_known_word("English")


def test_unknown_words_catch_ocr_typos_once_per_article():
    ws = unknown_word_warnings(_data(), PARIS_ART, PARIS_LINES)
    words = {w.detail for w in ws}
    assert {"Enolish", "bridoe"} <= words
    assert next(w for w in ws if w.detail == "bridoe").line_id == "L009"
    assert "apartments" not in words and "fireplaces" not in words


def test_unknown_word_repeated_reported_once_with_count():
    lines = [_line(0, "T", 0), _line(1, "OpenAI said OpenAI will", 20), _line(2, "OpenAI again.", 40)]
    art = AssembledArticle.model_construct(title_lines=["L000"], ignore=[], sections=[
        AssembledSection(body_lines=["L001"], icon_hint="a"),
        AssembledSection(body_lines=["L002"], icon_hint="b")])
    data, _ = assemble_sections("x", art, lines)
    ws = unknown_word_warnings(data, art, lines)
    assert [w.detail for w in ws] == ["OpenAI (×3)"]


def test_gap_catches_missing_line_but_not_paragraph_break():
    ws = gap_warnings(_data(), PARIS_ART, PARIS_LINES)
    assert [w.line_id for w in ws] == ["L004"]
    assert "21px" in ws[0].detail


def test_gap_ignores_other_columns():
    lines = [_line(0, "T", 0), _line(1, "a b c", 100), _line(2, "d e f", 111),
             _line(3, "g h i", 122), _line(4, "far column.", 300, x=500)]
    art = AssembledArticle.model_construct(title_lines=["L000"], ignore=[], sections=[
        AssembledSection(body_lines=["L001", "L002", "L003", "L004"], icon_hint="a")])
    data, _ = assemble_sections("x", art, lines)
    assert gap_warnings(data, art, lines) == []


def test_unfinished_block():
    ws = unfinished_warnings(_data())
    assert len(ws) == 1 and ws[0].detail.endswith("decorate the")


def test_text_warnings_finds_all_paris_problems():
    ws = text_warnings(_data(), PARIS_ART, PARIS_LINES)
    kinds = {(w.kind, w.line_id) for w in ws}
    assert ("gap", "L004") in kinds
    assert any(w.kind == "unfinished" for w in ws)
    assert {"Enolish", "bridoe"} <= {w.detail for w in ws if w.kind == "unknown_word"}


def test_upscale_and_scale_back(tmp_path):
    from PIL import Image
    src = tmp_path / "a.png"
    Image.new("RGB", (100, 50), "white").save(src)
    out = upscale_image(src, tmp_path / "b.png", 2)
    with Image.open(out) as im:
        assert im.size == (200, 100)
    (line,) = scale_lines([OcrLine(text="x", box=[20, 40, 60, 60], confidence=0.9)], 2)
    assert line.box == [10, 20, 30, 30]


# ── run #85 (góp ý người dùng sau BE-02d) ──

import json
from pathlib import Path

from pipeline.extract import (
    OcrRaw, apply_extra_lines, assign_line_ids, ocr_lines_for_source, punctuation_suspects,
)

DATA = Path(__file__).parent / "data"


def test_existing_ocr_raw_with_upscale_no_warning_unless_user_passes_it(tmp_path, capsys):
    raw = OcrRaw(slug="x", source="x.jpg", engine="paddleocr", blocks=[], upscale=2)
    (tmp_path / "ocr_raw.json").write_text(raw.model_dump_json(), encoding="utf-8")
    ocr_lines_for_source(Path("x.jpg"), tmp_path)                 # crosscheck / assemble không truyền
    assert "upscale" not in capsys.readouterr().out
    ocr_lines_for_source(Path("x.jpg"), tmp_path, upscale=2)      # trùng giá trị đã lưu
    assert "upscale" not in capsys.readouterr().out
    ocr_lines_for_source(Path("x.jpg"), tmp_path, upscale=3)      # người dùng truyền khác
    assert "bo qua --upscale 3" in capsys.readouterr().out


def test_unit_abbreviations_not_punct_suspects():
    assert punctuation_suspects("Area 40.7 sq. mi. (105.4 sq. km)") == []
    assert punctuation_suspects("Ask Dr. smith or Mr. jones.") == []
    assert punctuation_suspects("salt. sugar and fat") != []


def test_table_rows_not_unfinished():
    lines = [_line(0, "T", 0), _line(1, "Country France", 20), _line(2, "Population 2.34 million", 40),
             _line(3, "Tourists (annually) 15.6 million", 60), _line(4, "Hundreds of statues decorate the", 80)]
    art = AssembledArticle.model_construct(title_lines=["L000"], ignore=[], sections=[
        AssembledSection(body_lines=["L001", "L002", "L003", "L004"],
                         paragraph_starts=["L002", "L003", "L004"], icon_hint="a")])
    data, _ = assemble_sections("x", art, lines)
    assert [w.detail for w in unfinished_warnings(data)] == ["…Hundreds of statues decorate the"]


def test_unknown_words_in_titles_too():
    lines = [_line(0, "Parizz", 0), _line(1, "Notre Dame", 20), _line(2, "A big church.", 40)]
    art = AssembledArticle.model_construct(title_lines=["L000"], ignore=[], sections=[
        AssembledSection(title_lines=["L001"], body_lines=["L002"], icon_hint="a")])
    data, _ = assemble_sections("x", art, lines)
    ws = {w.detail: w for w in unknown_word_warnings(data, art, lines)}
    assert ws["Parizz"].where == "(tiêu đề bài)" and ws["Parizz"].line_id == "L000"


def test_extra_lines_insert_after_and_silence_gap():
    lines = PARIS_LINES[:1] + PARIS_LINES[1:]
    spec = {"title_lines": ["L000"], "sections": [
        {"body_lines": ["L001", "L002", "L003", "L004", "L005", "L006"], "paragraph_starts": ["L005"],
         "icon_hint": "people"},
        {"body_lines": ["L007", "L008"], "icon_hint": "cathedral"},
        {"body_lines": ["L009"], "icon_hint": "fortress"}]}
    out = apply_extra_lines(spec, lines, [
        {"after": "L003", "text": "are old, but cherished for their or-"},
        {"after": "L008", "text": "building, many serving as water spouts."}])
    assert spec["sections"][0]["body_lines"][3] == "L003a"
    added = [l for l in out if l.added]
    assert [l.id for l in added] == ["L003a", "L008a"]
    assert 598 < added[0].box[1] < 619                      # nằm giữa 2 dòng
    art = AssembledArticle.model_validate(spec, context={"line_ids": [l.id for l in out],
                                                         "line_words": {}})
    data, _ = assemble_sections("paris", art, out)
    assert "apartments are old, but cherished for their ornate fireplaces" in data.sections[0].body
    ws = text_warnings(data, art, out)
    assert not [w for w in ws if w.kind == "gap"]
    assert not [w for w in ws if w.kind == "unfinished"]


def test_extra_lines_unknown_id():
    import pytest
    with pytest.raises(ValueError, match="khong ton tai"):
        apply_extra_lines({"sections": []}, PARIS_LINES, [{"after": "L999", "text": "x"}])


def test_paris_regression_raw_ocr_finds_all_known_errors():
    """Bộ kiểm hồi quy: OCR thô của bài Paris + structure.json gốc, BỎ line_fixes/extra_lines
    → phải báo đủ 5 lỗi chữ, 1 khoảng hở (Parisians), 1 đoạn dở (Notre-Dame). Chỉnh ngưỡng
    (GAP_FACTOR, danh sách từ) mà làm mất cảnh báo thật thì test này đỏ."""
    raw = OcrRaw.model_validate_json((DATA / "paris_ocr_raw.json").read_text(encoding="utf-8-sig"))
    lines = assign_line_ids(raw)
    spec = json.loads((DATA / "paris_structure.json").read_text(encoding="utf-8"))
    for k in ("line_fixes", "extra_lines", "section_titles"):
        spec.pop(k, None)
    art = AssembledArticle.model_validate(
        spec, context={"line_ids": [l.id for l in lines], "line_words": {}})
    data, _ = assemble_sections("paris", art, lines)
    ws = text_warnings(data, art, lines)
    words = {w.detail.split(" (×")[0] for w in ws if w.kind == "unknown_word"}
    assert {"Enolish", "worid's", "musoums", "bridoe", "Effel"} <= words
    gaps = [w for w in ws if w.kind == "gap"]
    assert [w.line_id for w in gaps] == ["L139"]                 # sót dòng sau L136
    unfinished = [w.detail for w in ws if w.kind == "unfinished"]
    assert any(d.endswith("decorate the") for d in unfinished)   # sót dòng cuối Notre-Dame
    assert not any("Country France" in d or "2.34 million" in d for d in unfinished)
