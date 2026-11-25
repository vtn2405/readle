"""BE-17 · Ảnh bìa bài (ADR-024 điểm 1): cắt từ chính ảnh/PDF nguồn → WebP 960×600 → bucket `covers`.

    py -m pipeline.cover --slug pizza                 # tạo pipeline/out/pizza/cover.webp
    py -m pipeline.cover --all                        # mọi bài trong processing_order.json có `cover`
    py -m pipeline.cover --slug pizza --page-png 1    # PDF: xuất trang 1 (đúng DPI) để đo `box`
    py -m pipeline.seed  --slug pizza [--local]       # seed tải cover.webp lên bucket + điền cover_url

Luật:
- Vùng cắt chọn tay trong `pipeline/out/<slug>/overrides.json → cover`:
  `{"source": "sources/pizza.jpg", "box": [x0, y0, x1, y1]}` (pixel ảnh nguồn, x1/y1 không bao gồm);
  PDF thêm `"page": <số trang từ 1>` và `box` theo pixel trang render ở `dpi` (mặc định 200, như `extract`).
- Vùng chọn lệch tỉ lệ 16:10 → cắt giữa cho đúng tỉ lệ (không méo), rồi đổi cỡ 960×600.
- Không có `cover` → bài không có bìa ảnh (`cover_url = null`, app dùng bìa chủ đề).
- `cover.webp` là sản phẩm sinh ra (gitignored). Tên file trong bucket có mã băm nội dung
  (`<slug>-<sha8>.webp`) nên đổi vùng cắt là đổi URL, app/CDN không giữ ảnh cũ.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import pathlib
import sys
from typing import Optional

from pydantic import BaseModel, Field, field_validator

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "pipeline" / "out"
BUCKET = "covers"
COVER_FILE = "cover.webp"
WIDTH, HEIGHT = 960, 600
WEBP_QUALITY = 80


class CoverSpec(BaseModel):
    source: str = Field(description="đường dẫn ảnh/PDF nguồn, tính từ gốc repo (vd sources/pizza.jpg)")
    box: list[int] = Field(min_length=4, max_length=4, description="[x0, y0, x1, y1] pixel ảnh nguồn")
    page: Optional[int] = Field(default=None, ge=1, description="PDF: số trang, bắt đầu 1")
    dpi: int = Field(default=200, ge=72, le=600, description="PDF: DPI render trang")

    @field_validator("box")
    @classmethod
    def _box_order(cls, v: list[int]) -> list[int]:
        x0, y0, x1, y1 = v
        if not (0 <= x0 < x1 and 0 <= y0 < y1):
            raise ValueError(f"box phải là [x0, y0, x1, y1] với x0 < x1, y0 < y1: {v}")
        return v


def fit_ratio(box: tuple[int, int, int, int], ratio: float = WIDTH / HEIGHT) -> tuple[int, int, int, int]:
    """Thu vùng chọn về đúng tỉ lệ `ratio` (rộng/cao), giữ tâm; chỉ cắt bớt, không nới ra."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if w / h > ratio:  # quá rộng → bớt hai bên
        nw = round(h * ratio)
        x0 += (w - nw) // 2
        return x0, y0, x0 + nw, y1
    nh = round(w / ratio)  # quá cao → bớt trên dưới
    y0 += (h - nh) // 2
    return x0, y0, x1, y0 + nh


def load_source(spec: CoverSpec, root: pathlib.Path = ROOT):
    from PIL import Image
    path = root / spec.source
    if not path.exists():
        raise FileNotFoundError(f"không thấy ảnh nguồn {path}")
    if path.suffix.lower() == ".pdf":
        if spec.page is None:
            raise ValueError(f"{spec.source}: PDF cần `page`")
        import pymupdf
        with pymupdf.open(path) as doc:
            pix = doc[spec.page - 1].get_pixmap(dpi=spec.dpi)
            return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    return Image.open(path).convert("RGB")


def render_cover(spec: CoverSpec, root: pathlib.Path = ROOT) -> tuple[bytes, list[str]]:
    """Trả (bytes WebP 960×600, cảnh báo)."""
    from PIL import Image
    img = load_source(spec, root)
    x0, y0, x1, y1 = spec.box
    if x1 > img.width or y1 > img.height:
        raise ValueError(f"box {spec.box} vượt ảnh nguồn {img.width}×{img.height}")
    warnings = []
    box = fit_ratio((x0, y0, x1, y1))
    if box != (x0, y0, x1, y1):
        warnings.append(f"vùng chọn lệch 16:10, cắt giữa còn {list(box)}")
    if box[2] - box[0] < WIDTH * 0.6:
        warnings.append(f"vùng cắt chỉ rộng {box[2] - box[0]}px, phóng to nhiều sẽ mờ")
    out = img.crop(box).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, "WEBP", quality=WEBP_QUALITY, method=6)
    return buf.getvalue(), warnings


def cover_spec(slug: str, out_dir: pathlib.Path = OUT) -> Optional[CoverSpec]:
    f = out_dir / slug / "overrides.json"
    if not f.exists():
        return None
    raw = json.loads(f.read_text("utf-8-sig")).get("cover")
    return CoverSpec.model_validate(raw) if raw else None


def build_cover(slug: str, out_dir: pathlib.Path = OUT, root: pathlib.Path = ROOT) -> Optional[pathlib.Path]:
    """Sinh `<out>/<slug>/cover.webp` theo overrides; bài không có `cover` thì xóa file cũ (nếu có)."""
    target = out_dir / slug / COVER_FILE
    spec = cover_spec(slug, out_dir)
    if spec is None:
        target.unlink(missing_ok=True)
        return None
    data, warnings = render_cover(spec, root)
    target.write_bytes(data)
    for w in warnings:
        print(f"  ⚠ {slug}: {w}")
    return target


# ---------------------------------------------------------------- bucket (seed gọi)
def bucket_name(article_id: str, data: bytes) -> str:
    """'art_pizza' + bytes → 'pizza-1a2b3c4d.webp'."""
    slug = article_id.removeprefix("art_").replace("_", "-")
    return f"{slug}-{hashlib.sha256(data).hexdigest()[:8]}.webp"


def is_cover_of(file_name: str, prefix: str) -> bool:
    """'pizza-1a2b3c4d.webp' thuộc prefix 'pizza-'; 'pizza-hut-1a2b3c4d.webp' thì không."""
    rest = file_name.removeprefix(prefix)
    return (rest != file_name and rest.endswith(".webp") and len(rest) == 13
            and all(c in "0123456789abcdef" for c in rest[:8]))


def upload_cover(db, article_id: str, cover_path: Optional[pathlib.Path]) -> Optional[str]:
    """Tải bìa (nếu chưa có trong bucket), xóa bìa cũ cùng bài, trả URL công khai; không có file → None."""
    if cover_path is None or not cover_path.exists():
        return None
    data = cover_path.read_bytes()
    name = bucket_name(article_id, data)
    prefix = name.rsplit("-", 1)[0] + "-"
    store = db.storage.from_(BUCKET)
    files = {f["name"] for f in store.list("", {"limit": 10000}) if f.get("name")}
    if name not in files:
        store.upload(name, data, {"content-type": "image/webp", "upsert": "true"})
    stale = [f for f in files if f != name and is_cover_of(f, prefix)]
    if stale:
        store.remove(stale)
    return store.get_public_url(name).rstrip("?")


def main() -> None:
    ap = argparse.ArgumentParser(prog="pipeline.cover", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--page-png", type=int, default=None,
                    help="PDF: xuất trang này (theo dpi của cover hoặc 200) ra cover_page.png để đo box")
    args = ap.parse_args()

    if args.page_png:
        spec = cover_spec(args.slug)
        dpi = spec.dpi if spec else 200
        src = spec.source if spec else None
        if not src:
            sys.exit("cần `cover.source` trong overrides.json để biết file PDF")
        import pymupdf
        with pymupdf.open(ROOT / src) as doc:
            p = OUT / args.slug / "cover_page.png"
            doc[args.page_png - 1].get_pixmap(dpi=dpi).save(p)
        print(f"-> {p}")
        return

    slugs = json.loads((OUT / "processing_order.json").read_text("utf-8")) if args.all else [args.slug]
    for s in slugs:
        p = build_cover(s)
        print(f"{s}: {p.relative_to(ROOT) if p else 'không có cover (bìa chủ đề)'}")


if __name__ == "__main__":
    main()
