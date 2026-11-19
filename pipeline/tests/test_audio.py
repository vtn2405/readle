"""BE-06d: tên file audio, cache TTS, upload bỏ qua file đã có, seed điền audio_url."""
import pytest

from pipeline import audio
from pipeline.audio import audio_file_name, fill_audio_urls, ssml, upload_bundle_audio


class FakeBucket:
    def __init__(self, store):
        self.store = store

    def list(self, path="", options=None):
        return [{"name": n} for n in sorted(self.store)]

    def upload(self, name, data, options=None):
        assert options["content-type"] == "audio/mpeg"
        self.store[name] = data

    def get_public_url(self, name):
        return f"http://host/storage/v1/object/public/audio/{name}?"


class FakeStorage:
    def __init__(self):
        self.files = {}

    def from_(self, bucket):
        assert bucket == "audio"
        return FakeBucket(self.files)


class FakeDb:
    def __init__(self):
        self.storage = FakeStorage()


def _bundle(*forms):
    from pipeline.reference.tokenize_and_match import lemma_key
    return {"lexicon": [{"canonical_form": f, "lemma_key": lemma_key(f), "audio_url": None} for f in forms]}


def test_file_name_is_slug_of_lemma_key():
    assert audio_file_name("play a vital role in") == "play-a-vital-role-in.mp3"
    assert audio_file_name("heavy - lift rocket") == "heavy-lift-rocket.mp3"
    with pytest.raises(ValueError):
        audio_file_name("  ")


def test_ssml_escapes_text():
    assert "R&amp;D" in ssml("R&D")


def test_upload_skips_existing_and_shared_items(monkeypatch):
    calls = []
    monkeypatch.setattr(audio, "synthesize", lambda text, k, r: calls.append(text) or b"ID3x")
    db = FakeDb()
    db.storage.files["irrigation.mp3"] = b"ID3old"
    up, have = upload_bundle_audio(db, _bundle("irrigation", "reservoir"), "k", "r")
    assert up == ["reservoir.mp3"] and have == ["irrigation.mp3"] and calls == ["reservoir"]
    up2, _ = upload_bundle_audio(db, _bundle("reservoir"), "k", "r")    # bài khác, cùng mục
    assert up2 == [] and calls == ["reservoir"]


def test_fill_audio_urls_only_for_files_in_bucket():
    db = FakeDb()
    db.storage.files["reservoir.mp3"] = b"ID3"
    b = _bundle("reservoir", "flood control")
    assert fill_audio_urls(db, b) == 1
    assert b["lexicon"][0]["audio_url"] == "http://host/storage/v1/object/public/audio/reservoir.mp3"
    assert b["lexicon"][1]["audio_url"] is None


def test_synthesize_uses_cache_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "CACHE", tmp_path)
    p = audio.cache_path("tend to")
    p.write_bytes(b"ID3cached")
    assert audio.synthesize("tend to", "no-key", "no-region") == b"ID3cached"
    assert audio.cache_path("tend to") != audio.cache_path("tend to", "en-US-GuyNeural")
