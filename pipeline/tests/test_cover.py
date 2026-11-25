"""BE-17 · Contract 1.5: ảnh bìa (pipeline.cover), đoạn trích, seed điền cover_url/excerpt. Không gọi mạng."""
from __future__ import annotations

import io
import json

import pytest
from PIL import Image
from pydantic import ValidationError

from pipeline.cover import (HEIGHT, WIDTH, CoverSpec, build_cover, bucket_name, fit_ratio, is_cover_of,
                            render_cover, upload_cover)
from pipeline.enrich import Overrides
from pipeline.reference.contract_models import ArticleBundle
from pipeline.reference.tokenize_and_match import article_excerpt, clip_excerpt, tokenize
from pipeline.seed import plan_rows

FIXTURE = json.loads(open("fixtures/article_eating_well.json", encoding="utf-8").read())


# ---------------------------------------------------------------- vùng cắt
def test_fit_ratio_keeps_exact_16_10():
    assert fit_ratio((0, 0, 1600, 1000)) == (0, 0, 1600, 1000)


def test_fit_ratio_too_wide_trims_sides_around_center():
    x0, y0, x1, y1 = fit_ratio((100, 0, 2100, 1000))  # 2000×1000 → 1600×1000
    assert (x1 - x0, y1 - y0) == (1600, 1000) and x0 == 300


def test_fit_ratio_too_tall_trims_top_bottom():
    x0, y0, x1, y1 = fit_ratio((0, 0, 800, 800))  # → 800×500
    assert (x1 - x0, y1 - y0) == (800, 500) and y0 == 150


def test_cover_spec_rejects_reversed_box():
    with pytest.raises(ValidationError):
        CoverSpec(source="sources/x.jpg", box=[100, 0, 50, 10])


def _jpg(tmp_path, w=1200, h=900, name="src.jpg"):
    img = Image.new("RGB", (w, h), (200, 30, 30))
    img.paste((20, 20, 220), (0, 0, w // 2, h))  # nửa trái xanh để thấy vùng cắt
    p = tmp_path / name
    img.save(p, "JPEG")
    return p


def test_render_cover_is_webp_960x600_and_warns_on_ratio(tmp_path):
    _jpg(tmp_path)
    data, warnings = render_cover(CoverSpec(source="src.jpg", box=[0, 0, 1200, 900]), root=tmp_path)
    out = Image.open(io.BytesIO(data))
    assert out.format == "WEBP" and out.size == (WIDTH, HEIGHT)
    assert any("16:10" in w for w in warnings)


def test_render_cover_box_outside_image_fails(tmp_path):
    _jpg(tmp_path)
    with pytest.raises(ValueError, match="vượt"):
        render_cover(CoverSpec(source="src.jpg", box=[0, 0, 1300, 800]), root=tmp_path)


def test_render_cover_warns_when_crop_is_small(tmp_path):
    _jpg(tmp_path)
    _, warnings = render_cover(CoverSpec(source="src.jpg", box=[0, 0, 320, 200]), root=tmp_path)
    assert any("mờ" in w for w in warnings)


def test_build_cover_writes_file_and_removes_when_spec_dropped(tmp_path):
    _jpg(tmp_path)
    out = tmp_path / "out"
    (out / "x").mkdir(parents=True)
    ov = out / "x" / "overrides.json"
    ov.write_text(json.dumps({"cover": {"source": "src.jpg", "box": [0, 0, 960, 600]}}), "utf-8")
    p = build_cover("x", out_dir=out, root=tmp_path)
    assert p.exists() and Image.open(p).size == (WIDTH, HEIGHT)
    ov.write_text("{}", "utf-8")
    assert build_cover("x", out_dir=out, root=tmp_path) is None and not p.exists()


# ---------------------------------------------------------------- bucket
def test_bucket_name_has_slug_and_content_hash():
    a, b = bucket_name("art_holiday_travel", b"one"), bucket_name("art_holiday_travel", b"two")
    assert a.startswith("holiday-travel-") and a.endswith(".webp") and a != b


def test_is_cover_of_does_not_match_other_article_with_same_prefix():
    assert is_cover_of("pizza-1a2b3c4d.webp", "pizza-")
    assert not is_cover_of("pizza-hut-1a2b3c4d.webp", "pizza-")
    assert not is_cover_of("pizza-1a2b3c4d.mp3", "pizza-")


class _Store:
    def __init__(self, files):
        self.files, self.uploaded, self.removed = set(files), [], []

    def list(self, *_):
        return [{"name": f} for f in self.files]

    def upload(self, name, data, opts):
        assert opts["content-type"] == "image/webp"
        self.uploaded.append(name)
        self.files.add(name)

    def remove(self, names):
        self.removed += names
        self.files -= set(names)

    def get_public_url(self, name):
        return f"http://x/storage/v1/object/public/covers/{name}?"


class _Db:
    def __init__(self, store):
        self.storage = self
        self.store = store

    def from_(self, bucket):
        assert bucket == "covers"
        return self.store


def test_upload_cover_uploads_new_removes_stale_keeps_other_articles(tmp_path):
    p = tmp_path / "cover.webp"
    p.write_bytes(b"new")
    name = bucket_name("art_pizza", b"new")
    store = _Store({"pizza-00000000.webp", "pizza-hut-00000000.webp", "paris-11111111.webp"})
    url = upload_cover(_Db(store), "art_pizza", p)
    assert url == f"http://x/storage/v1/object/public/covers/{name}"
    assert store.uploaded == [name] and store.removed == ["pizza-00000000.webp"]
    # chạy lại: không tải lại, không xóa gì
    store.uploaded, store.removed = [], []
    upload_cover(_Db(store), "art_pizza", p)
    assert store.uploaded == [] and store.removed == []


def test_upload_cover_without_file_is_none(tmp_path):
    assert upload_cover(_Db(_Store(set())), "art_x", tmp_path / "cover.webp") is None
    assert upload_cover(_Db(_Store(set())), "art_x", None) is None


# ---------------------------------------------------------------- đoạn trích
def test_excerpt_is_first_sentence_verbatim():
    toks = tokenize("Pizza is popular. It came from Italy.")
    assert article_excerpt(toks) == "Pizza is popular."


def test_excerpt_keeps_closing_quote_and_leading_quote():
    toks = tokenize("“We eat well,” she said. Then we left.")
    assert article_excerpt(toks) == "“We eat well,” she said."


def test_excerpt_long_sentence_cut_at_word_boundary():
    text = "word " * 50
    out = clip_excerpt(text)
    assert len(out) <= 160 and out.endswith("…") and not out.endswith(" …") and "wor…" not in out


def test_excerpt_none_without_words():
    assert article_excerpt(tokenize("...")) is None


def test_fixture_excerpt_matches_first_sentence():
    assert FIXTURE["contract_version"] == "1.5"
    assert FIXTURE["article"]["excerpt"] == "Eating well plays a vital role in good health and disease prevention."
    assert FIXTURE["article"]["cover_url"] is None


# ---------------------------------------------------------------- contract + overrides + seed
def test_contract_accepts_old_bundle_without_new_fields():
    b = json.loads(json.dumps(FIXTURE))
    b["contract_version"] = "1.4"
    del b["article"]["cover_url"], b["article"]["excerpt"]
    ArticleBundle.model_validate(b)


def test_contract_rejects_excerpt_over_160():
    b = json.loads(json.dumps(FIXTURE))
    b["article"]["excerpt"] = "x" * 161
    with pytest.raises(ValidationError):
        ArticleBundle.model_validate(b)


def test_overrides_accept_cover_and_excerpt():
    o = Overrides.model_validate({"excerpt": "Short.", "cover": {"source": "sources/a.pdf", "page": 2,
                                                                 "box": [0, 0, 10, 10]}})
    assert o.cover.page == 2 and o.cover.dpi == 200
    with pytest.raises(ValidationError):
        Overrides.model_validate({"excerpt": "x" * 161})


def test_plan_rows_writes_cover_url_and_excerpt():
    b = json.loads(json.dumps(FIXTURE))
    b["article"]["cover_url"] = "http://x/c.webp"
    r = plan_rows(b, "infographic")
    assert r.article["cover_url"] == "http://x/c.webp"
    assert r.article["excerpt"] == FIXTURE["article"]["excerpt"]
