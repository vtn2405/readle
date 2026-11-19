"""Tests for pipeline.ipa (contract 1.1, ADR-010; giọng Mỹ không `ː`, run #41)."""
import pytest

from pipeline.ipa import add_token_ipa, phrase_ipa, word_ipa
from pipeline.reference.tokenize_and_match import tokenize


@pytest.mark.parametrize("word,ipa", [
    ("tend", "/tɛnd/"),                 # 1 âm tiết: không dấu nhấn
    ("vital", "/ˈvaɪtəl/"),
    ("moderation", "/ˌmɑdəˈreɪʃən/"),   # ER0 trước nguyên âm → ə + r sang âm tiết sau
    ("breakfast", "/ˈbrɛkfəst/"),       # onset "br" giữ nguyên
    ("about", "/əˈbaʊt/"),
    ("Eating", "/ˈitɪŋ/"),              # chữ hoa vẫn tra được
    ("fiber", "/ˈfaɪbɚ/"),
    ("rocket", "/ˈrɑkət/"),             # ví dụ người dùng (run #38)
    ("heavy", "/ˈhɛvi/"),
    ("food", "/fud/"),
])
def test_word_ipa(word, ipa):
    assert word_ipa(word) == ipa


def test_no_length_mark_anywhere():
    for w in ["moderation", "rocket", "food", "eat", "water", "work", "thought", "car"]:
        assert "ː" not in (word_ipa(w) or "")


def test_unknown_word_is_none():
    assert word_ipa("carotenoids") is None
    assert word_ipa("90") is None


def test_phrase_ipa():
    assert phrase_ipa("tend to") == "/tɛnd tu/"
    assert phrase_ipa("play a vital role in") == "/pleɪ ə ˈvaɪtəl roʊl ɪn/"
    assert phrase_ipa("rich in carotenoids") is None


def test_weak_forms_only_inside_phrases():
    assert phrase_ipa("a good source of") == "/ə ɡʊd sɔrs əv/"
    assert phrase_ipa("reduce the risk of").endswith("ðə rɪsk əv/")
    assert word_ipa("of") == "/ʌv/"      # token đứng riêng giữ dạng nhấn
    assert phrase_ipa("of") == "/ʌv/"


def test_add_token_ipa_skips_punctuation_and_keeps_input():
    toks = tokenize("Eat well, often.")
    out = add_token_ipa(toks)
    assert "ipa" not in toks[0]
    assert [t["ipa"] for t in out] == ["/it/", "/wɛl/", None, "/ˈɔfən/", None]


def test_token_ipa_uses_lemma():
    out = add_token_ipa(tokenize("Sleep plays a role."))
    plays = next(t for t in out if t["text"] == "plays")
    assert plays["lemma"] == "play" and plays["ipa"] == "/pleɪ/"
