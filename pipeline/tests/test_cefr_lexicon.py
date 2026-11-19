"""Tests for pipeline.cefr_lexicon (BE-15a, ADR-022). Không gọi mạng/LLM."""
import json
import re

import pytest

from pipeline.cefr_lexicon import (
    LEXICON_PATH, VENDOR, CefrLookup, build_lexicon, default_sources, dump_lexicon,
    lookup_cefr, sha256, split_variants,
)


def _write(tmp_path, name, rows, header="headword,pos,CEFR"):
    p = tmp_path / name
    p.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return p


@pytest.fixture(scope="module")
def real():
    return build_lexicon(default_sources())


# ── build (dữ liệu nhỏ dựng trong test) ──

def test_slash_variants_give_all_keys(tmp_path):
    cj = _write(tmp_path, "cj.csv", ["a.m./A.M./am/AM,adverb,A1",
                                     '"check-in counter/check-in",noun,A2'])
    lex, _ = build_lexicon((("cefrj", cj),))
    assert split_variants("a.m./A.M./am/AM") == ["a.m.", "am"]
    assert lex["entries"]["a.m.|ADV"]["cefr"] == "A1"
    assert lex["entries"]["am|ADV"]["cefr"] == "A1"
    assert lex["entries"]["check-in|NOUN"]["cefr"] == "A2"
    assert lex["multiword"]["check-in counter"]["cefr"] == "A2"


def test_whitespace_trimmed_and_nfc(tmp_path):
    oc = _write(tmp_path, "oc.csv", ["turn to ,verb,C1", "café,noun,C1"])
    lex, _ = build_lexicon((("octanove", oc),))
    assert "turn to" in lex["multiword"]
    assert not any(k != k.strip() for k in lex["multiword"])
    assert "café|NOUN" in lex["entries"]


def test_unknown_pos_dropped_and_logged(tmp_path):
    oc = _write(tmp_path, "oc.csv", ["remonstrate,vern,C2", "batter,,C1", "timid,adjective,C1"])
    lex, log = build_lexicon((("octanove", oc),))
    assert not any(k.startswith(("remonstrate|", "batter|")) for k in lex["entries"])
    dropped = " ".join(w for w, _ in log["dropped"])
    assert "remonstrate" in dropped and "batter" in dropped


def test_pos_maps_to_several_upos(tmp_path):
    cj = _write(tmp_path, "cj.csv", ["be,be-verb,A1", "and,conjunction,A1"])
    lex, _ = build_lexicon((("cefrj", cj),))
    assert {"be|AUX", "be|VERB", "and|CCONJ", "and|SCONJ"} <= set(lex["entries"])


def test_duplicate_same_source_keeps_lowest(tmp_path):
    cj = _write(tmp_path, "cj.csv", ["right,adjective,B1", "right,adjective,A1"])
    lex, log = build_lexicon((("cefrj", cj),))
    assert lex["entries"]["right|ADJ"]["cefr"] == "A1"
    assert log["duplicates"]


def test_cefrj_wins_over_octanove(tmp_path):
    cj = _write(tmp_path, "cj.csv", ["agency,noun,A2"])
    oc = _write(tmp_path, "oc.csv", ["agency,noun,C2", "timid,adjective,C1"])
    lex, log = build_lexicon((("cefrj", cj), ("octanove", oc)))
    assert lex["entries"]["agency|NOUN"] == {"cefr": "A2", "source": "cefrj"}
    assert lex["entries"]["timid|ADJ"] == {"cefr": "C1", "source": "octanove"}
    assert log["shadowed"] == [("agency|NOUN", "cefrj", "A2", "octanove", "C2")]


# ── dữ liệu thật ──

def test_lexicon_file_up_to_date_and_stable(real):
    lex, _ = real
    again, _ = build_lexicon(default_sources())
    assert dump_lexicon(lex) == dump_lexicon(again)
    on_disk = LEXICON_PATH.read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert on_disk == dump_lexicon(lex), "chạy `py -m pipeline.cefr_lexicon build`"
    assert json.loads(on_disk)["entries"] == lex["entries"]


def test_source_md_sha256_matches_files():
    text = (VENDOR / "SOURCE.md").read_text("utf-8")
    for _, p in default_sources():
        m = re.search(rf"`{re.escape(p.name)}` \| `([0-9a-f]{{64}})`", text)
        assert m, p.name
        assert m.group(1) == sha256(p)


def test_real_vern_dropped(real):
    _, log = real
    assert any("remonstrate" in w for w, _ in log["dropped"])


@pytest.mark.parametrize("args, expected", [
    (("stage",), ("B2", "human")),            # cefr.json thắng CEFR-J A1
    (("robot",), ("A2", "human")),            # cefr.json thắng CEFR-J B1
    (("access", "VERB"), ("B2", "cefrj")),
    (("access",), ("B1", "cefrj")),           # không UPOS → cấp thấp nhất
    (("agency",), ("A2", "cefrj")),           # không phải C2 Octanove
    (("timid",), ("C1", "octanove")),         # chỉ có ở Octanove
    (("climate change",), ("B2", "cefrj")),   # mục nhiều từ
    (("datum", "NOUN", "data"), ("B2", "cefrj")),
    (("accord", "VERB", "according"), ("B1", "cefrj")),  # qua form → "according to"
])
def test_lookup_real(args, expected):
    assert lookup_cefr(*args) == expected


def test_lookup_misses():
    assert lookup_cefr("accord", "VERB") is None      # không có form thì không đoán
    assert lookup_cefr("propellant") is None
    assert lookup_cefr("change climate") is None      # cụm chỉ khớp nguyên văn


def test_human_entry_beats_dictionary():
    lex = {"entries": {"stage|NOUN": {"cefr": "A1", "source": "cefrj"}}, "multiword": {}}
    look = CefrLookup(lex, {"stage": {"cefr": "B2", "form": "stage", "source": "x"}})
    assert look("stage", "NOUN") == ("B2", "human")
    assert look("stage", "NOUN", use_human=False) == ("A1", "cefrj")
