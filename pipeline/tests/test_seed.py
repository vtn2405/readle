"""Unit test phần thuần của pipeline/seed.py (không cần Supabase chạy)."""
import copy
import json
import pathlib

from pipeline.seed import plan_rows, stable_uuid

FIXTURE = json.loads((pathlib.Path(__file__).resolve().parents[2] / "fixtures" / "article_eating_well.json")
                     .read_text(encoding="utf-8"))


def test_plan_rows_is_deterministic():
    a, b = plan_rows(FIXTURE, "infographic"), plan_rows(FIXTURE, "infographic")
    assert a.article_id == b.article_id
    assert [s["id"] for s in a.sections] == [s["id"] for s in b.sections]
    assert [o["id"] for o in a.occurrences] == [o["id"] for o in b.occurrences]


def test_section_uuid_depends_on_order_index_not_string_id():
    renamed = copy.deepcopy(FIXTURE)
    mapping = {s["id"]: f"sec_new_{s['order_index']}" for s in renamed["sections"]}
    for s in renamed["sections"]:
        s["id"] = mapping[s["id"]]
    for o in renamed["occurrences"]:
        o["section_id"] = mapping[o["section_id"]]
    a, b = plan_rows(FIXTURE, "infographic"), plan_rows(renamed, "infographic")
    assert [s["id"] for s in a.sections] == [s["id"] for s in b.sections]
    assert [o["section_id"] for o in a.occurrences] == [o["section_id"] for o in b.occurrences]


def test_occurrence_and_quiz_ids_are_scoped_by_article():
    other = copy.deepcopy(FIXTURE)
    other["article"]["id"] = "art_other"
    a, b = plan_rows(FIXTURE, "infographic"), plan_rows(other, "infographic")
    assert a.article_id != b.article_id
    assert not {o["id"] for o in a.occurrences} & {o["id"] for o in b.occurrences}
    assert not {q["id"] for q in a.quiz} & {q["id"] for q in b.quiz}
    # lexicon dùng chung theo lemma_key → cùng uuid ở mọi bài
    assert [e["id"] for e in a.lexicon] == [e["id"] for e in b.lexicon]


def test_rows_reference_each_other_and_map_back():
    r = plan_rows(FIXTURE, "pdf")
    sec_ids = {s["id"] for s in r.sections}
    lex_ids = {e["id"] for e in r.lexicon}
    assert r.source["type"] == "pdf"
    assert all(o["section_id"] in sec_ids and o["lexicon_entry_id"] in lex_ids for o in r.occurrences)
    assert r.back[r.article_id] == FIXTURE["article"]["id"]
    assert r.back[stable_uuid("lexicon", "tend to")] == "lex_tend_to"
    assert [q["order_index"] for q in r.quiz] == list(range(len(FIXTURE["quiz"])))
    first = next(s for s in FIXTURE["sections"] if s["order_index"] == 0)
    row0 = next(s for s in r.sections if s["order_index"] == 0)
    assert row0["key_idea"] == first["key_idea"]["text"] and row0["check_data"] == first.get("check")
