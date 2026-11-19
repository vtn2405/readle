"""Unit test phần thuần của pipeline/supabase_check.py (không cần Supabase chạy)."""
import uuid

from pipeline.supabase_check import normalize, restore_ids, stable_uuid


def test_stable_uuid_is_deterministic_and_kind_scoped():
    a = stable_uuid("article", "art_eating_well")
    assert a == stable_uuid("article", "art_eating_well")
    assert a != stable_uuid("section", "art_eating_well")
    assert uuid.UUID(a).version == 5


def test_restore_ids_maps_nested_uuids_back():
    u = stable_uuid("lexicon", "tend to")
    got = restore_ids({"lexicon": [{"id": u, "canonical_form": "tend to"}], "n": 3}, {u: "lex_tend_to"})
    assert got == {"lexicon": [{"id": "lex_tend_to", "canonical_form": "tend to"}], "n": 3}


def test_normalize_ignores_version_and_lexicon_order():
    a = {"contract_version": "1.2", "lexicon": [{"id": "b"}, {"id": "a"}], "occurrences": []}
    b = {"contract_version": "1.1", "lexicon": [{"id": "a"}, {"id": "b"}], "occurrences": []}
    assert normalize(a) == normalize(b)


def test_resolve_bundle_requires_explicit_bundle_on_cloud():
    import pathlib

    import pytest

    from pipeline.supabase_check import DEFAULT_BUNDLE, resolve_bundle

    assert resolve_bundle(None, local=True) == DEFAULT_BUNDLE
    p = pathlib.Path("pipeline/out/eating-well/bundle.json")
    assert resolve_bundle(p, local=False) == p
    with pytest.raises(SystemExit):
        resolve_bundle(None, local=False)  # fixture trùng id bài thật → không được seed lên cloud
