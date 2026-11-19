"""Quy ước glossary từ chức năng (BE-06e1): luôn ghi nghĩa, không ngoặc, chỉ mạo từ dùng nhãn."""
import pytest

from pipeline.glossary import ARTICLE_A, ARTICLE_THE, normalize_fn_meaning, normalize_glossary


@pytest.mark.parametrize("text,vi,new,status", [
    ("and", "(và)", "và", "cleaned"),
    ("and", "và (liên từ)", "và", "cleaned"),
    ("and", "(liên từ 'và')", "và", "cleaned"),
    ("at", "(giới từ: ở)", "ở", "cleaned"),
    ("been", "(bị/được - phân từ)", "bị/được", "cleaned"),
    ("by", "(bởi/ theo)", "bởi/theo", "cleaned"),
    ("they", "chúng (robot)", "chúng", "cleaned"),       # ngoặc giải thích bị bỏ
    ("and", "(liên từ)", "và", "default"),               # chỉ có nhãn → nghĩa mặc định
    ("is", "(động từ to be)", "là", "default"),
    ("'s", "(sở hữu)", "của", "default"),
    ("do", "(trợ động từ)", "(trợ động từ)", "missing"),  # không đoán → báo người duyệt
    ("up", "(phần của 'made up')", "(phần của 'made up')", "missing"),
    # BE-06h: ghi chú của LLM quyết định nghĩa mặc định
    ("to", "(dấu nguyên mẫu)", "để", "default"),
    ("to", "(đặt trước động từ)", "để", "default"),
    ("to", "(giới từ)", "đến", "default"),
    ("be", "(động từ bị động)", "được", "default"),
    ("was", "(trợ động từ bị động)", "được", "default"),
    ("be", "(động từ trợ từ)", "là", "default"),
    ("is", "(động từ to be)", "là", "default"),
    ("of", "(dấu nguyên mẫu)", "(dấu nguyên mẫu)", "missing"),  # chỉ áp cho `to`
    ("to", "đến", "đến", "same"),                               # có nghĩa thật → giữ
    ("in", "trong", "trong", "same"),
])
def test_function_word_meanings(text, vi, new, status):
    assert normalize_fn_meaning(text, vi) == (new, status)


@pytest.mark.parametrize("text,vi,new", [
    ("the", "(mạo từ xác định)", ARTICLE_THE),
    ("the", "mạo từ 'the'", ARTICLE_THE),
    ("the", "(giới từ)", ARTICLE_THE),          # nhãn sai → nhãn chuẩn
    ("the", "càng", "càng"),                     # "the more … the better": nghĩa thật được giữ
    ("a", "một (mạo từ không xác định)", "một"),
    ("a", "Một", "một"),
    ("a", "(mạo từ)", ARTICLE_A),
    ("an", "(mạo từ không xác định)", ARTICLE_A),
])
def test_articles_may_keep_label(text, vi, new):
    assert normalize_fn_meaning(text, vi)[0] == new


def test_no_parentheses_left_except_articles_and_missing():
    cases = [("of", "(của)"), ("or", "(liên từ) hoặc"), ("these", "những (này)"), ("with", "(với)")]
    for text, vi in cases:
        new, _ = normalize_fn_meaning(text, vi)
        assert "(" not in new and ")" not in new


def test_normalize_glossary_only_touches_function_words_and_reports():
    tokens = [
        {"i": 0, "text": "plays", "is_fn": False},
        {"i": 1, "text": "and", "is_fn": True},
        {"i": 2, "text": "that", "is_fn": True},
        {"i": 3, "text": "of", "is_fn": True},
    ]
    meanings = {0: "đóng (vai trò)", 1: "(và)", 2: "(liên từ)", 3: "(giới từ)"}
    report = normalize_glossary(tokens, meanings)
    assert meanings == {0: "đóng (vai trò)", 1: "và", 2: "(liên từ)", 3: "của"}
    assert len(report["cleaned"]) == 1 and len(report["default"]) == 1
    assert report["missing"] == ['that: "(liên từ)"']
