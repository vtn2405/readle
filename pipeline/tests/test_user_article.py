"""Tests cho bản tham chiếu bài tự tải (ADR-021, bản nháp Contract 1.5) — thuần logic, không gọi mạng,
không cần spaCy. Các ca này cũng là danh sách ca Antigravity cần lặp lại bằng Dart (FE-16)."""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline" / "reference"))

from user_article import (  # noqa: E402
    MSG_NO_TITLE, MSG_NOT_ENGLISH, MSG_TOO_LONG, MSG_TOO_SHORT,
    UserArticleBundle, UserArticleRecord, apply_dict, build_bundle, edited_ratio, is_pure_number, lookup_forms,
    lookup_key, sentence_for, split_cards, split_paragraphs, suggest_title, tokenize_paragraph,
    validate_text, word_count,
)

AID = "local_3f6c2a1e-8b4d-4c7a-9e21-5d0b7a6c4f18"


def texts(toks):
    return [t["text"] for t in toks]


def render(toks):
    return "".join(t["text"] + t["ws"] for t in toks)


def para(n, word="word"):
    """Đoạn n từ, mỗi 10 từ 1 câu."""
    words = [word] * n
    out = []
    for k in range(0, n, 10):
        out.append(" ".join(words[k:k + 10]) + ".")
    return " ".join(out)


# ── tách đoạn + token ──
class TestTokenize:
    def test_paragraphs_blank_line_and_soft_wrap(self):
        raw = "First line\nsame para.\r\n\r\n  \n\nSecond para​."
        assert split_paragraphs(raw) == ["First line same para.", "Second para."]

    def test_special_tokens(self):
        toks = tokenize_paragraph("It's a well-known fact: children’s books cost 3.5 dollars — in 2025.")
        assert texts(toks) == ["It's", "a", "well-known", "fact", ":", "children’s", "books", "cost",
                               "3.5", "dollars", "—", "in", "2025", "."]
        by = {t["text"]: t for t in toks}
        assert by["It's"]["is_word"] and by["well-known"]["is_word"]
        # số thuần chạm được (như bài đã duyệt); dấu câu thì không
        assert by["3.5"]["is_word"] and by["2025"]["is_word"]
        assert not by["—"]["is_word"] and not by[":"]["is_word"]

    def test_pure_number(self):
        for s in ("2025", "3.5", "1,000", "1.000,5"):
            assert is_pure_number(s)
        for s in ("1990s", "90-minute", "5G", "COVID-19", "3.", "."):
            assert not is_pure_number(s)
        toks = tokenize_paragraph("In 1990s, a 90-minute film cost 3.5 dollars.")
        assert texts(toks)[1] == "1990s" and "90-minute" in texts(toks)

    def test_alnum_codes_are_words(self):
        toks = tokenize_paragraph("COVID-19 and 5G arrived.")
        assert texts(toks) == ["COVID-19", "and", "5G", "arrived", "."]
        assert all(t["is_word"] for t in toks[:4])

    def test_quotes_and_ws_roundtrip(self):
        p = "“Hello,” she said. (Really?) Yes!"
        toks = tokenize_paragraph(p)
        assert render(toks) == p
        assert toks[-1]["ws"] == ""
        assert texts(toks)[:4] == ["“", "Hello", ",", "”"]

    def test_defaults_before_dict(self):
        t = tokenize_paragraph("Running")[0]
        assert t == {"i": 0, "text": "Running", "ws": "", "lemma": "running", "pos": None,
                     "is_word": True, "is_fn": False, "vi": None, "ipa": None}


# ── chia card ──
class TestCards:
    def toks(self, *sizes):
        return [tokenize_paragraph(para(n)) for n in sizes]

    def test_merge_short_paragraphs(self):
        cards = split_cards(self.toks(30, 30, 30, 100))
        assert [word_count(c) for c in cards] == [90, 100]
        assert render(cards[0]).count("\n\n") == 2

    def test_long_paragraph_split_by_sentence(self):
        cards = split_cards(self.toks(320))
        assert [word_count(c) for c in cards] == [150, 170]  # đuôi 20 < 40 gộp vào card trước (≤ 200)
        assert "\n\n" not in render(cards[0])

    def test_tail_merge_limit(self):
        assert [word_count(c) for c in split_cards(self.toks(150, 30))] == [180]
        assert [word_count(c) for c in split_cards(self.toks(150, 30, 30))] == [150, 60]

    def test_reindex_and_last_ws(self):
        for c in split_cards(self.toks(30, 30, 100, 20)):
            assert [t["i"] for t in c] == list(range(len(c)))
            assert c[-1]["ws"] == ""


# ── kiểm tra trước khi lưu ──
class TestValidate:
    def ps(self, text):
        return [tokenize_paragraph(p) for p in split_paragraphs(text)]

    def test_messages(self):
        assert validate_text("", self.ps(para(60))) == MSG_NO_TITLE
        assert validate_text("T", self.ps(para(49))) == MSG_TOO_SHORT
        assert validate_text("T", self.ps(para(2001))) == MSG_TOO_LONG
        vi = " ".join(["Thư viện nhỏ vẫn rất quan trọng với mọi người."] * 8)
        assert validate_text("T", self.ps(vi)) == MSG_NOT_ENGLISH
        assert validate_text("T", self.ps(para(50))) is None

    def test_suggest_title(self):
        assert suggest_title("\n\n  Why Small   Libraries\nbody") == "Why Small Libraries"

    def test_build_bundle_raises_soft_message(self):
        with pytest.raises(ValueError, match="Bài hơi ngắn"):
            build_bundle(AID, "T", "Too short.")


# ── dict_entries ──
class TestDict:
    def test_forms_and_possessive_fallback(self):
        toks = tokenize_paragraph("The children’s Books, the 3 cats.")
        assert lookup_forms(toks) == ["the", "children's", "children", "books", "cats"]
        d = {"the": {"lemma": "the", "ipa": "/ðə/", "is_fn": True},
             "children": {"lemma": "child", "ipa": "/tʃaɪld/", "is_fn": False}}
        out = apply_dict(toks, d.get)
        by = {t["text"]: t for t in out}
        assert by["children’s"]["lemma"] == "child" and by["children’s"]["ipa"] == "/tʃaɪld/"
        assert by["The"]["is_fn"] is True
        assert by["Books"]["lemma"] == "books" and by["Books"]["ipa"] is None  # không có → giữ mặc định
        assert by["3"]["is_word"] and by["3"]["lemma"] == "3"  # số thuần: không tra, giữ nguyên


# ── edited_ratio + lookup_key ──
class TestMetrics:
    def test_edited_ratio(self):
        assert edited_ratio("a b c d.", "a b c d.") == 0.0
        assert edited_ratio("a b c d.", "a x c d.") == 0.2  # 1 / 5 token
        assert edited_ratio("a.", "completely different text here.") == 1.0

    def test_sentence_and_occurrence(self):
        toks = tokenize_paragraph("I read. He read the book and read it again! Done.")
        second_read = [k for k, t in enumerate(toks) if t["text"] == "read"][2]
        sentence, occ = sentence_for(toks, second_read)
        assert sentence == "He read the book and read it again!" and occ == 1

    def test_lookup_key_normalizes(self):
        k = lookup_key("He  read the book.", "Read", 0)
        assert k == lookup_key("He read the book.", "read", 0)
        assert k != lookup_key("He read the book.", "read", 1)
        assert len(k) == 64


# ── fixture đã sinh ──
class TestFixture:
    def test_user_article_fixture_valid(self):
        rec = json.loads((ROOT / "fixtures" / "user_article_sample.json").read_text(encoding="utf-8"))
        UserArticleRecord.model_validate(rec)
        b = rec["bundle"]
        assert b["contract_version"] == "1.5" and b["article"]["origin"] == "user"
        assert all(t["vi"] is None and t["pos"] is None for s in b["sections"] for t in s["tokens"])

    def test_fixture_reproducible_without_dict(self):
        """Tách lại thân bài (không dict) phải ra đúng text/ws/is_word như fixture."""
        rec = json.loads((ROOT / "fixtures" / "user_article_sample.json").read_text(encoding="utf-8"))
        sys.path.insert(0, str(ROOT / "pipeline" / "reference"))
        from build_user_fixture import RAW
        b2 = build_bundle(AID, "x", RAW.split("\n", 2)[2])
        strip = lambda b: [[(t["text"], t["ws"], t["is_word"]) for t in s["tokens"]] for s in b["sections"]]  # noqa: E731
        assert strip(b2) == strip(rec["bundle"])

    def test_lookup_samples_keys_match(self):
        data = json.loads((ROOT / "fixtures" / "lookup_samples.json").read_text(encoding="utf-8"))
        results = {"ok", "capped_user", "capped_global", "offline", "error"}
        for s in data["samples"]:
            r = s["request"]
            ev = s["event"]["payload"]
            assert ev["hit"] in {"local", "server", "miss"} and ev["result"] in results
            if s["response"]["status"] == 200:
                assert ev["hit"] == ("server" if s["response"]["body"]["cached"] else "miss")
            else:
                assert ev["hit"] == "miss" and ev["result"] == s["response"]["body"]["error"]
            if s["response"]["status"] == 200:
                assert s["response"]["body"]["lookup_key"] == lookup_key(r["sentence"], r["word"], r["occurrence"])
                assert len(s["response"]["body"]["vi"]) <= 80

    def test_main_fixture_untouched(self):
        main = json.loads((ROOT / "fixtures" / "article_eating_well.json").read_text(encoding="utf-8"))
        assert main["contract_version"] == "1.4"


def test_bundle_model_rejects_wrong_ids():
    bad = build_bundle(AID, "T", para(60))
    bad["sections"][0]["id"] = "sec_x"
    with pytest.raises(ValueError):
        UserArticleBundle.model_validate(bad)
