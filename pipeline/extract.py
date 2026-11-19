"""B1-B2: trich xuat anh/PDF -> normalized_sections.json.

Duong chinh (ADR-012): OCR doc chu, LLM chi chon ID dong (khong the dien dat lai / bia chu):
  assemble : PaddleOCR dong + anh -> LLM tra cau truc bang ID -> code ghep chu nguyen van OCR
             -> normalized_sections.json + assemble.md (cho can soat: dau cau, dong sot, gach noi).
  check    : kiem tra lai normalized_sections.json truoc khi chay B3 (spaCy).

Du phong (ADR-009): vision : LLM chep chu tu anh -> normalized_sections.json (co the dien dat lai).

Fallback tuy chon (ADR-008, khi khong co API — can cai paddleocr[doc-parser]):
  ocr    : PaddleOCR / PP-StructureV3 -> ocr_raw.json (text + box + confidence + label + order).
  review : sinh review_ocr.html de nguoi duyet keo block, gop doan, sua loi OCR -> Export.

spaCy (BE-03) CHI chay tren normalized_sections.json.

Doi chieu cheo (BE-02b): Vision co the DIEN DAT LAI (thay tu dong nghia, viet lai cau) ma nguoi doc
luot khong thay. `crosscheck` OCR cuc bo roi so tung manh cau cua Vision voi chu OCR -> crosscheck.md.

Usage:
  py -m pipeline.extract assemble   --input sources/eating_well.jpg --slug eating-well
  # xep tay (structure.json: line_fixes / extra_lines / section_titles):
  py -m pipeline.extract assemble   --input sources/paris.jpg --slug paris --force --structure pipeline/out/paris/structure.json
  py -m pipeline.extract assemble   --input sources/x.jpg --slug x --upscale 2      # chi khi chua co ocr_raw.json
  py -m pipeline.extract crosscheck --input sources/eating_well.jpg --slug eating-well
  py -m pipeline.extract check      --slug eating-well
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, model_validator

PIPELINE_DIR = Path(__file__).resolve().parent
OUT_DIR = PIPELINE_DIR / "out"
CACHE_DIR = PIPELINE_DIR / ".cache"
SCHEMA_VERSION = 1
PROMPT_VERSION = 2  # v2: chep nguyen van (BE-02b)

Role = Literal["article_title", "section_title", "body", "ignore"]

# PP-StructureV3 block_label -> vai tro de xuat (nguoi duyet co the doi trong review_ocr.html)
LABEL_TO_ROLE: dict[str, Role] = {
    "doc_title": "article_title",
    "paragraph_title": "section_title",
    "title": "section_title",
    "text": "body",
    "abstract": "body",
    "content": "body",
    "aside_text": "body",
    "table": "body",
    "algorithm": "body",
    "figure_title": "ignore",
    "chart_title": "ignore",
    "image": "ignore",
    "figure": "ignore",
    "chart": "ignore",
    "header": "ignore",
    "footer": "ignore",
    "header_image": "ignore",
    "footer_image": "ignore",
    "number": "ignore",
    "seal": "ignore",
    "footnote": "ignore",
    "reference": "ignore",
    "formula": "ignore",
    "formula_number": "ignore",
}


# ---------------------------------------------------------------- models
class OcrLine(BaseModel):
    text: str
    box: list[float] = Field(min_length=4, max_length=4)  # [x0, y0, x1, y1]
    confidence: float = Field(ge=0.0, le=1.0)


class OcrBlock(BaseModel):
    block_id: str
    order: int = Field(ge=0)          # thu tu doc de xuat
    page: int = Field(ge=0, default=0)
    label: str                        # nhan goc tu engine (doc_title, text, ...)
    role: Role                        # vai tro de xuat khi dung section
    box: list[float] = Field(min_length=4, max_length=4)
    text: str
    lines: list[OcrLine] = []


class PageInfo(BaseModel):
    file: str                         # ten file anh trong out/<slug>/ (de review nhung vao html)
    width: int
    height: int


class OcrRaw(BaseModel):
    schema_version: int = SCHEMA_VERSION
    slug: str
    source: str
    engine: Literal["pp_structure_v3", "paddleocr", "pymupdf_text"]
    pages: list[PageInfo] = []        # rong khi engine = pymupdf_text
    blocks: list[OcrBlock]
    upscale: float = 1.0              # BE-02d: anh duoc phong truoc OCR (box da quy ve toa do anh goc)


class NormalizedSection(BaseModel):
    order: int = Field(ge=0)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    icon_hint: str = ""


class NormalizedSections(BaseModel):
    schema_version: int = SCHEMA_VERSION
    slug: str
    title: str = Field(min_length=1)
    sections: list[NormalizedSection] = Field(min_length=1)


# -------- Vision (ADR-009): model ma LLM phai tra ve --------
class ExtractedSection(BaseModel):
    order: int = Field(ge=0)
    title: str = Field(description="Heading of the box/section exactly as printed")
    body: str = Field(description=(
        "All body text of this section, verbatim, in reading order. "
        "No captions of pictures unless they are full sentences."))
    icon_hint: str = Field(description="One lowercase English noun for an icon, e.g. 'broccoli', 'apple'")


class ExtractedArticle(BaseModel):
    title: str
    sections: list[ExtractedSection] = Field(min_length=1)


EXTRACT_PROMPT = (
    "This is a page from an English infographic or article. Extract the main title and every text "
    "section (a heading plus its paragraph).\n"
    "You are a TRANSCRIBER, not a writer. Copy the printed text character for character:\n"
    "- Never replace a word with a synonym or a more common word (e.g. do not turn 'bologna' into "
    "'salami' or 'enriched cereal' into 'whole grain cereal').\n"
    "- Never add, drop, merge, reorder or shorten sentences; never fix grammar, spelling or style.\n"
    "- Copy every number, unit and list item exactly as printed (e.g. '90-minute' stays '90-minute').\n"
    "- If a word is hard to read, write your best reading of the printed letters; do not substitute "
    "a plausible word.\n"
    "Order sections the way a reader would read them: the intro paragraph under the title first, "
    "then boxes from top to bottom, left column before right column. Ignore the source/credits line "
    "and labels that only name a picture (e.g. 'Broccoli' under a drawing). "
    "If the intro paragraph has no heading of its own, use the main title as its section title."
)


def normalized_from_extracted(slug: str, art: ExtractedArticle) -> NormalizedSections:
    sections = sorted(art.sections, key=lambda s: s.order)
    return NormalizedSections(
        slug=slug,
        title=art.title.strip(),
        sections=[
            NormalizedSection(order=i, title=s.title.strip(), body=s.body.strip(),
                              icon_hint=s.icon_hint.strip().lower())
            for i, s in enumerate(sections)
        ],
    )


def validate_normalized(data: NormalizedSections, slug: str) -> list[str]:
    """Tra ve danh sach van de (rong = OK)."""
    problems = []
    orders = [s.order for s in data.sections]
    if orders != list(range(len(orders))):
        problems.append(f"order khong lien tuc tu 0: {orders}")
    total_words = sum(len(s.body.split()) for s in data.sections)
    if total_words < 50:
        problems.append(f"tong so tu qua it ({total_words} < 50)")
    if data.slug != slug:
        problems.append(f"slug trong file ({data.slug}) khac --slug ({slug})")
    return problems


def print_summary(data: NormalizedSections) -> None:
    total_words = sum(len(s.body.split()) for s in data.sections)
    print(f"'{data.title}' · {len(data.sections)} section · {total_words} tu")
    for s in data.sections:
        print(f"  [{s.order}] {s.title} ({len(s.body.split())} tu)"
              + (f" · icon: {s.icon_hint}" if s.icon_hint else ""))


# ---------------------------------------------------------------- pure helpers
def poly_to_box(poly) -> list[float]:
    """[[x,y] x4] hoac [x0,y0,x1,y1] -> [x0,y0,x1,y1]."""
    flat = list(poly)
    if len(flat) == 4 and all(isinstance(v, (int, float)) for v in flat):
        return [float(v) for v in flat]
    xs = [float(p[0]) for p in poly]
    ys = [float(p[1]) for p in poly]
    return [min(xs), min(ys), max(xs), max(ys)]


def box_center(box: list[float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def box_contains(box: list[float], pt: tuple[float, float]) -> bool:
    return box[0] <= pt[0] <= box[2] and box[1] <= pt[1] <= box[3]


def nearest_block_index(line_box: list[float], block_boxes: list[list[float]]) -> int:
    """Block chua tam dong; khong co thi block co tam gan nhat."""
    c = box_center(line_box)
    for i, b in enumerate(block_boxes):
        if box_contains(b, c):
            return i
    def dist2(b):
        bc = box_center(b)
        return (bc[0] - c[0]) ** 2 + (bc[1] - c[1]) ** 2
    return min(range(len(block_boxes)), key=lambda i: dist2(block_boxes[i]))


def lines_from_ocr_res(ocr_res: dict) -> list[OcrLine]:
    """Doc rec_texts/rec_scores/rec_polys|rec_boxes tu ket qua PaddleOCR."""
    texts = ocr_res.get("rec_texts", [])
    scores = ocr_res.get("rec_scores", [])
    boxes = ocr_res.get("rec_boxes") or ocr_res.get("rec_polys") or ocr_res.get("dt_polys") or []
    lines = []
    for i, text in enumerate(texts):
        if not str(text).strip():
            continue
        score = float(scores[i]) if i < len(scores) else 0.0
        box = poly_to_box(boxes[i]) if i < len(boxes) else [0.0, 0.0, 0.0, 0.0]
        lines.append(OcrLine(text=str(text), box=box, confidence=max(0.0, min(1.0, score))))
    return lines


def blocks_from_structure(parsing_res_list: list[dict], lines: list[OcrLine],
                          page: int = 0, id_prefix: str = "b") -> list[OcrBlock]:
    """Ghep parsing_res_list (block + label + thu tu doc) voi cac dong OCR (confidence)."""
    raw_blocks = []
    for item in parsing_res_list:
        label = str(item.get("block_label", "text"))
        content = str(item.get("block_content", "") or "")
        bbox = item.get("block_bbox") or item.get("block_box") or [0, 0, 0, 0]
        raw_blocks.append((label, content, [float(v) for v in bbox]))

    assigned: dict[int, list[OcrLine]] = {i: [] for i in range(len(raw_blocks))}
    if raw_blocks:
        block_boxes = [b[2] for b in raw_blocks]
        for ln in lines:
            assigned[nearest_block_index(ln.box, block_boxes)].append(ln)

    blocks: list[OcrBlock] = []
    for i, (label, content, bbox) in enumerate(raw_blocks):
        block_lines = sorted(assigned[i], key=lambda l: (l.box[1], l.box[0]))
        text = content.strip() or " ".join(l.text for l in block_lines).strip()
        if not text:
            continue  # block khong co chu (hinh anh thuan) -> bo
        blocks.append(OcrBlock(
            block_id=f"{id_prefix}{i}", order=len(blocks), page=page,
            label=label, role=LABEL_TO_ROLE.get(label, "body"),
            box=bbox, text=text, lines=block_lines,
        ))
    return blocks


def blocks_from_plain_ocr(lines: list[OcrLine], page: int = 0, id_prefix: str = "b") -> list[OcrBlock]:
    """Khong co layout model: moi dong OCR la 1 block, xep tren-xuong-duoi, trai-sang-phai."""
    ordered = sorted(lines, key=lambda l: (l.box[1], l.box[0]))
    return [
        OcrBlock(block_id=f"{id_prefix}{i}", order=i, page=page, label="text", role="body",
                 box=ln.box, text=ln.text, lines=[ln])
        for i, ln in enumerate(ordered)
    ]


def renumber(blocks: list[OcrBlock]) -> list[OcrBlock]:
    for i, b in enumerate(blocks):
        b.order = i
    return blocks


# ---------------------------------------------------------------- engines (lazy import)
def _load_result_json(result_obj, tmp_dir: Path) -> dict:
    """Luu ket qua paddle ra file JSON roi doc lai -> dict thuan (tranh numpy)."""
    result_obj.save_to_json(save_path=str(tmp_dir))
    files = sorted(tmp_dir.glob("*.json"))
    if not files:
        raise RuntimeError("PaddleOCR khong luu duoc JSON ket qua")
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    for f in files:
        f.unlink()
    return data.get("res", data)


def run_structure_on_image(image_path: Path) -> tuple[list[dict], list[OcrLine]]:
    from paddleocr import PPStructureV3  # lazy: chi can khi chay lenh ocr
    pipe = PPStructureV3(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,  # oneDNN loi "ConvertPirAttribute2RuntimeAttribute" tren Windows
    )
    outputs = pipe.predict(str(image_path))
    with tempfile.TemporaryDirectory() as td:
        res = _load_result_json(outputs[0], Path(td))
    parsing = res.get("parsing_res_list", [])
    ocr_res = res.get("overall_ocr_res", {})
    return parsing, lines_from_ocr_res(ocr_res)


FAST_OCR_MODELS = {"text_detection_model_name": "PP-OCRv6_small_det",
                   "text_recognition_model_name": "PP-OCRv6_small_rec"}
_OCR_ENGINES: dict[tuple[str, bool], object] = {}


def get_ocr_engine(lang: str = "en", fast: bool = False):
    """Nap PaddleOCR 1 lan cho moi (lang, fast) — truoc day moi trang nap lai mo hinh.
    fast=True: mo hinh small (nhanh tren CPU, du cho bao in 1 cot); mac dinh giu nhu cu
    (medium/server, dung cho infographic nhieu khung chu)."""
    key = (lang, fast)
    if key not in _OCR_ENGINES:
        from paddleocr import PaddleOCR  # lazy
        _OCR_ENGINES[key] = PaddleOCR(
            lang=lang,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,  # oneDNN loi "ConvertPirAttribute2RuntimeAttribute" tren Windows
            **(FAST_OCR_MODELS if fast else {}),
        )
    return _OCR_ENGINES[key]


def run_plain_ocr_on_image(image_path: Path, lang: str = "en", fast: bool = False) -> list[OcrLine]:
    ocr = get_ocr_engine(lang, fast)
    outputs = ocr.predict(str(image_path))
    with tempfile.TemporaryDirectory() as td:
        res = _load_result_json(outputs[0], Path(td))
    return lines_from_ocr_res(res)


def image_size(path: Path) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as im:
        return im.width, im.height


def pdf_has_text_layer(path: Path) -> bool:
    import pymupdf
    with pymupdf.open(path) as doc:
        return any(page.get_text().strip() for page in doc)


def blocks_from_pdf_text(path: Path) -> list[OcrBlock]:
    import pymupdf
    blocks: list[OcrBlock] = []
    with pymupdf.open(path) as doc:
        for pno, page in enumerate(doc):
            # block = (x0, y0, x1, y1, text, block_no, block_type); type 0 = text
            for b in page.get_text("blocks", sort=True):
                if b[6] == 0 and b[4].strip():
                    text = " ".join(b[4].split())
                    blocks.append(OcrBlock(
                        block_id=f"p{pno}_b{len(blocks)}", order=len(blocks), page=pno,
                        label="text", role="body",
                        box=[float(b[0]), float(b[1]), float(b[2]), float(b[3])],
                        text=text,
                        lines=[OcrLine(text=text, box=[float(b[0]), float(b[1]), float(b[2]), float(b[3])],
                                       confidence=1.0)],
                    ))
    return blocks


def pdf_pages_as_png(path: Path, out_dir: Path, dpi: int = 200) -> list[Path]:
    import pymupdf
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with pymupdf.open(path) as doc:
        for n, page in enumerate(doc):
            p = out_dir / f"page_{n + 1}.png"
            page.get_pixmap(dpi=dpi).save(p)
            paths.append(p)
    return paths


# ---------------------------------------------------------------- crosscheck (BE-02b)
# Y tuong: OCR cuc bo doc sai vai ky tu va dinh chu ("Eatingwellplaysa"), nhung KHONG doi tu.
# Vision doc dung ky tu nhung co the thay tu / viet lai cau. Vay so khop o muc KY TU sau khi bo
# khoang trang va dau: loi OCR chi ha diem nhe, dien dat lai thi rot han.
CROSSCHECK_THRESHOLD = 85     # manh cau cua Vision co diem < nguong -> "lech"
MISSED_THRESHOLD = 70         # dong OCR co diem < nguong -> "co the sot"
CHUNK_MIN_CHARS = 18          # manh qua ngan thi gop voi manh ke tiep
MISSED_MIN_CHARS = 20         # dong OCR ngan (nhan hinh) khong xet chieu nguoc
_SPLIT_RE = re.compile(r"(?<=[.!?;:])\s+|\s+[—–-]\s+|,\s+")
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def numbers_in(text: str) -> set[str]:
    """So trong van ban ('3.5', '90', '18'). Doi so la loi hay gap cua Vision ma diem ky tu khong bat duoc."""
    return {n.replace(",", ".") for n in _NUM_RE.findall(text)}


def norm_chars(s: str) -> str:
    """Chi giu chu va so, chu thuong, bo moi khoang trang/dau -> so khop khong phu thuoc OCR dinh chu."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def split_chunks(text: str, min_chars: int = CHUNK_MIN_CHARS) -> list[str]:
    """Tach doan thanh manh ngan (cau / menh de) de mot tu bi thay cung lam diem manh do rot ro."""
    parts = [p.strip() for p in _SPLIT_RE.split(text) if p and p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in parts:
        buf = f"{buf} {p}".strip() if buf else p
        if len(norm_chars(buf)) >= min_chars:
            chunks.append(buf)
            buf = ""
    if buf:
        if chunks:
            chunks[-1] = f"{chunks[-1]} {buf}"
        else:
            chunks.append(buf)
    return chunks


def partial_ratio(needle: str, hay: str) -> int:
    """0-100: needle giong nhat voi mot cua so nao do cua hay (nhu rapidfuzz.partial_ratio, difflib thuan)."""
    if not needle:
        return 100
    if not hay:
        return 0
    if len(hay) <= len(needle):
        return round(100 * SequenceMatcher(None, needle, hay, autojunk=False).ratio())
    sm = SequenceMatcher(None, needle, hay, autojunk=False)
    best = 0.0
    tried: set[int] = set()
    for blk in sm.get_matching_blocks():
        if blk.size == 0:
            continue
        start = min(max(0, blk.b - blk.a), len(hay) - len(needle))
        if start in tried:
            continue
        tried.add(start)
        window = hay[start:start + len(needle)]
        best = max(best, SequenceMatcher(None, needle, window, autojunk=False).ratio())
        if best >= 0.999:
            break
    return round(100 * best)


def group_lines(lines: list[OcrLine], tol_factor: float = 1.5) -> list[list[OcrLine]]:
    """Gop dong OCR thanh khoi (cot/hop) theo hinh hoc, de cau xuong dong khong bi dong cot ben chen vao.

    Dong j noi tiep dong cuoi i cua mot khoi khi: khoang cach doc <= tol (1.5 x chieu cao dong trung vi),
    x-range chong nhau >= 50% dong hep hon, va thang mep trai / mep phai / tam (<= tol).
    Khoi tra ve theo thu tu dong dau tien (tren xuong, trai sang) ~ thu tu doc."""
    if not lines:
        return []
    hs = sorted(l.box[3] - l.box[1] for l in lines)
    h = max(hs[len(hs) // 2], 1.0)
    tol = tol_factor * h
    order = sorted(range(len(lines)), key=lambda i: (lines[i].box[1], lines[i].box[0]))
    blocks: list[list[int]] = []
    for j in order:
        bj = lines[j].box
        best: tuple[float, int] | None = None
        for k, blk in enumerate(blocks):
            bi = lines[blk[-1]].box
            gap = bj[1] - bi[3]
            if gap < -h or gap > tol:
                continue
            overlap = min(bi[2], bj[2]) - max(bi[0], bj[0])
            if overlap < 0.5 * min(bi[2] - bi[0], bj[2] - bj[0]):
                continue
            aligned = (abs(bi[0] - bj[0]) <= tol or abs(bi[2] - bj[2]) <= tol
                       or abs((bi[0] + bi[2]) - (bj[0] + bj[2])) / 2 <= tol)
            if not aligned:
                continue
            if best is None or gap < best[0]:
                best = (gap, k)
        if best is None:
            blocks.append([j])
        else:
            blocks[best[1]].append(j)
    return [[lines[i] for i in blk] for blk in blocks]


class ChunkCheck(BaseModel):
    section_order: int
    section_title: str
    chunk: str
    score: int
    closest_ocr: str = ""     # dong OCR giong manh nay nhat (de nguoi duyet doi chieu)


class MissedLine(BaseModel):
    text: str
    confidence: float
    score: int


class CrossCheckReport(BaseModel):
    slug: str
    sections_file: str
    sections_sha256: str = ""             # de `check` biet bao cao con khop voi file sections hien tai
    threshold: int = CROSSCHECK_THRESHOLD
    chunks: list[ChunkCheck]              # manh than bai, ke ca dat
    titles: list[ChunkCheck]              # tieu de section (khong chan: co the la bien tap co y, vd "Introduction")
    missed: list[MissedLine]              # dong OCR khong thay trong Vision

    @property
    def flagged(self) -> list[ChunkCheck]:
        return [c for c in self.chunks if c.score < self.threshold]

    @property
    def odd_titles(self) -> list[ChunkCheck]:
        return [t for t in self.titles if t.score < self.threshold]


def crosscheck_sections(data: NormalizedSections, ocr_lines: list[OcrLine],
                        sections_file: str = "normalized_sections.json",
                        threshold: int = CROSSCHECK_THRESHOLD) -> CrossCheckReport:
    """Thuan logic (test duoc khong can PaddleOCR)."""
    blocks = group_lines([l for l in ocr_lines if l.text.strip()])
    block_texts = [" ".join(l.text for l in blk) for blk in blocks]
    block_norms = [norm_chars(t) for t in block_texts]
    hay_all = "".join(block_norms)  # du phong: cau vat qua ranh gioi khoi
    ocr_numbers = numbers_in(" ".join(block_texts))

    def block_score(needle: str, bn: str) -> int:
        # Khoi ngan hon cau (nhan hinh "Banana") KHONG duoc dung partial: no se khop 100% ben trong cau bia.
        if len(bn) >= len(needle):
            return partial_ratio(needle, bn)
        return round(100 * SequenceMatcher(None, needle, bn, autojunk=False).ratio())

    def closest_block(needle: str) -> tuple[int, str]:
        per_block = [block_score(needle, bn) for bn in block_norms]
        k = max(range(len(per_block)), key=per_block.__getitem__)
        return per_block[k], block_texts[k][:160]

    chunks: list[ChunkCheck] = []
    titles: list[ChunkCheck] = []
    for sec in data.sections:
        for is_title, chunk in [(True, sec.title)] + [(False, c) for c in split_chunks(sec.body)]:
            needle = norm_chars(chunk)
            if not needle:
                continue
            score = partial_ratio(needle, hay_all)
            closest = ""
            if score < threshold and block_norms:
                best_block, closest = closest_block(needle)
                score = max(score, best_block)
                if score >= threshold:
                    closest = ""
            missing_nums = sorted(numbers_in(chunk) - ocr_numbers)
            if missing_nums:
                # So sai la loi nang nhung chi doi 1-2 ky tu -> ep diem xuong duoi nguong.
                score = min(score, threshold - 1)
                closest = closest or closest_block(needle)[1]
                chunk = f"{chunk}  ⚠ số không có trong OCR: {', '.join(missing_nums)}"
            (titles if is_title else chunks).append(ChunkCheck(
                section_order=sec.order, section_title=sec.title,
                chunk=chunk, score=score, closest_ocr=closest))

    vision_all = norm_chars(data.title + " " + " ".join(s.title + " " + s.body for s in data.sections))
    missed: list[MissedLine] = []
    for ln in ocr_lines:
        needle = norm_chars(ln.text)
        if len(needle) < MISSED_MIN_CHARS:
            continue
        score = partial_ratio(needle, vision_all)
        if score < MISSED_THRESHOLD:
            missed.append(MissedLine(text=ln.text, confidence=ln.confidence, score=score))

    return CrossCheckReport(slug=data.slug, sections_file=sections_file, threshold=threshold,
                            chunks=chunks, titles=titles, missed=missed)


def crosscheck_markdown(rep: CrossCheckReport) -> str:
    flagged = rep.flagged
    lines = [
        f"# Đối chiếu Vision ↔ OCR: {rep.slug} (`{rep.sections_file}`)",
        "",
        f"Mảnh câu: {len(rep.chunks)} · lệch (< {rep.threshold}): **{len(flagged)}** · "
        f"dòng OCR có thể sót: {len(rep.missed)}",
        "",
        "## 1. Mảnh câu Vision KHÔNG khớp chữ OCR (nghi diễn đạt lại / bịa — đối chiếu ảnh gốc)",
        "",
    ]
    if flagged:
        lines += ["| Section | Mảnh câu (Vision) | Điểm | Dòng OCR gần nhất |", "|---|---|---|---|"]
        for c in flagged:
            lines.append(f"| {c.section_order}. {c.section_title} | {c.chunk} | {c.score} "
                         f"| {c.closest_ocr} |")
        lines += ["", "Sửa trong `normalized_sections.json` theo ảnh, rồi chạy lại `crosscheck`."]
    else:
        lines.append("- Không có.")
    lines += ["", "## 1b. Tiêu đề section không khớp OCR (không chặn — kiểm xem có phải biên tập cố ý)", ""]
    if rep.odd_titles:
        lines += [f"- [{t.section_order}] \"{t.chunk}\" ({t.score})" for t in rep.odd_titles]
    else:
        lines.append("- Không có.")
    lines += ["", "## 2. Dòng OCR không thấy trong Vision (có thể sót box; hoặc là credit / nhãn hình)", ""]
    if rep.missed:
        lines += ["| Dòng OCR | Conf | Điểm |", "|---|---|---|"]
        lines += [f"| {m.text} | {m.confidence:.2f} | {m.score} |" for m in rep.missed]
    else:
        lines.append("- Không có.")
    low = sorted(rep.chunks, key=lambda c: c.score)[:10]
    lines += ["", "## 3. 10 mảnh điểm thấp nhất (kể cả đạt)", "", "| Điểm | Section | Mảnh |", "|---|---|---|"]
    lines += [f"| {c.score} | {c.section_order} | {c.chunk} |" for c in low]
    return "\n".join(lines) + "\n"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def crosscheck_status(out_dir: Path, sec_file: Path) -> tuple[str, str]:
    """('missing' | 'stale' | 'flagged' | 'ok', thong bao) — `check` dung de chan khi con manh lech."""
    f = out_dir / "crosscheck.json"
    if not f.exists():
        return "missing", "chua doi chieu OCR (crosscheck.json khong co)"
    rep = CrossCheckReport.model_validate_json(f.read_text(encoding="utf-8"))
    if rep.sections_file != sec_file.name or rep.sections_sha256 != file_sha256(sec_file):
        return "stale", f"crosscheck.json lam cho ban khac cua {rep.sections_file} — chay lai crosscheck"
    n = len(rep.flagged)
    if n:
        return "flagged", f"con {n} manh cau lech voi OCR (xem crosscheck.md)"
    return "ok", "da doi chieu OCR, khong co manh lech"


def upscale_image(src: Path, dst: Path, factor: float, sharpen: bool = False) -> Path:
    """Phong anh (Lanczos) + lam net nhe truoc OCR (BE-02d): chu than bai infographic ~735 px
    chi cao < 10 px, OCR hay doc sai chu (bridoe, Effel) va bo sot dong."""
    from PIL import Image, ImageFilter
    with Image.open(src) as im:
        im = im.convert("RGB")
        big = im.resize((round(im.width * factor), round(im.height * factor)), Image.LANCZOS)
        if sharpen:  # run #84: lam net gay nham e→o (bocame, largost, conturies) → mac dinh tat
            big = big.filter(ImageFilter.UnsharpMask(radius=1.5, percent=60, threshold=2))
        big.save(dst)
    return dst


def scale_lines(lines: list[OcrLine], factor: float) -> list[OcrLine]:
    """Box cua anh da phong → toa do anh goc (khoang cach doc cua canh bao 1b so duoc giua cac bai)."""
    return [OcrLine(text=l.text, box=[v / factor for v in l.box], confidence=l.confidence) for l in lines]


def ocr_lines_for_source(src: Path, out_dir: Path, lang: str = "en", fast: bool = False,
                         upscale: float | None = None) -> list[OcrLine]:
    """Dung lai ocr_raw.json neu da co; khong thi OCR dong (khong layout) va luu lai de lan sau khong chay nua.
    ocr_raw.json da co thi KHONG OCR lai du upscale khac: ID dong doi → structure.json cua bai hong."""
    raw_file = out_dir / "ocr_raw.json"
    if raw_file.exists():
        raw = OcrRaw.model_validate_json(raw_file.read_text(encoding="utf-8-sig"))
        if upscale is not None and upscale != raw.upscale:  # chi khi nguoi dung co truyen --upscale
            print(f"CHU Y: ocr_raw.json da co (upscale {raw.upscale}) -> giu nguyen, bo qua --upscale {upscale}. "
                  "Muon OCR lai: xoa ocr_raw.json (chi voi bai chua co structure.json).")
        return [l for b in raw.blocks for l in b.lines]
    if src.suffix.lower() == ".pdf":
        page_files = pdf_pages_as_png(src, out_dir / "pages")
    else:
        page_files = [src]
    upscale = upscale or 1.0
    blocks: list[OcrBlock] = []
    for pno, img in enumerate(page_files):
        print(f"  OCR trang {pno + 1}/{len(page_files)}" + (" (fast)" if fast else "")
              + (f" (phong x{upscale:g})" if upscale != 1 else ""), flush=True)
        if upscale != 1:
            big = upscale_image(img, out_dir / f"ocr_input_p{pno}_x{upscale:g}.png", upscale)
            lines = scale_lines(run_plain_ocr_on_image(big, lang=lang, fast=fast), upscale)
        else:
            lines = run_plain_ocr_on_image(img, lang=lang, fast=fast)
        blocks += blocks_from_plain_ocr(lines, page=pno, id_prefix=f"p{pno}_b" if len(page_files) > 1 else "b")
    raw = OcrRaw(slug=out_dir.name, source=str(src).replace("\\", "/"), engine="paddleocr",
                 pages=[], blocks=renumber(blocks), upscale=upscale)
    raw_file.write_text(raw.model_dump_json(indent=2), encoding="utf-8")
    return [l for b in raw.blocks for l in b.lines]


def cmd_crosscheck(args: argparse.Namespace) -> None:
    out_dir = OUT_DIR / args.slug
    sec_file = Path(args.sections) if args.sections else out_dir / "normalized_sections.json"
    if not sec_file.exists():
        sys.exit(f"Chua co {sec_file} — chay lenh vision truoc.")
    src = Path(args.input)
    if not src.exists() and not (out_dir / "ocr_raw.json").exists():
        sys.exit(f"Khong tim thay input: {src}")
    data = NormalizedSections.model_validate_json(sec_file.read_text(encoding="utf-8-sig"))
    ocr_lines = ocr_lines_for_source(src, out_dir, lang=args.lang)
    if not ocr_lines:
        sys.exit("OCR khong doc duoc dong nao — kiem tra lai anh dau vao.")
    rep = crosscheck_sections(data, ocr_lines, sections_file=sec_file.name, threshold=args.threshold)
    rep.sections_sha256 = file_sha256(sec_file)
    out_file = out_dir / "crosscheck.md"
    out_file.write_text(crosscheck_markdown(rep), encoding="utf-8")
    (out_dir / "crosscheck.json").write_text(rep.model_dump_json(indent=2), encoding="utf-8")
    flagged = rep.flagged
    print(f"OK -> {out_file}")
    print(f"  {len(ocr_lines)} dong OCR · {len(rep.chunks)} manh cau · "
          f"lech: {len(flagged)} · co the sot: {len(rep.missed)}")
    for c in flagged:
        print(f"  LECH [{c.section_order}] ({c.score}) {c.chunk}")
        if c.closest_ocr:
            print(f"        OCR: {c.closest_ocr}")
    for t in rep.odd_titles:
        print(f"  TIEU DE [{t.section_order}] ({t.score}) \"{t.chunk}\" — khong co trong OCR (bien tap co y?)")
    if flagged:
        sys.exit(1)
    print("Khong co manh lech. Van doc luot file doi chieu anh (OCR khong bat duoc loi hoan doi thu tu cau).")


# ---------------------------------------------------------------- assemble (BE-02c, ADR-012)
# OCR doc chu, LLM chi chon ID dong. LLM khong xuat chu nao -> khong the dien dat lai / bia.
ASSEMBLE_PROMPT_VERSION = 4  # v2: doc theo cot; nhan trong so do/logo -> ignore. v3: moi tieu de = 1 section.
# v4: chu thich anh viet thanh cau -> section rieng (khong ignore); validator chan ignore > 50% so tu
MAX_IGNORED_WORD_SHARE = 0.5  # thuc do bai dat: bo 14-31% so tu; robots lan 2 bo 95% -> phai hoi lai
# Bai dat: 9-14 section, trung binh > 50 tu/section; robots lan 3 chia ~200 section 1-5 tu -> hoi lai
MAX_SECTIONS = 30
MIN_MEAN_SECTION_WORDS = 15
LOW_CONF = 0.90
_LINE_ID_RE = re.compile(r"^L\d{3,}$")
_PUNCT_SUSPECT_RE = re.compile(r"\b([A-Za-z]+)\. ([a-z]\w*)")
_PUNCT_OK_BEFORE = {"etc", "e.g", "eg", "i.e", "ie", "vs", "approx", "no",
                    # don vi / chuc danh viet tat ("40.7 sq. mi.", "Dr. smith"), run #85
                    "sq", "mi", "ft", "in", "oz", "lb", "mr", "mrs", "dr", "st"}
_TRAILING_HYPHEN_RE = re.compile(r"([A-Za-z]+)-$")
_LEADING_WORD_RE = re.compile(r"^([a-z][a-z']*)")


def max_missing(n_lines: int) -> int:
    """So dong LLM duoc phep bo sot (code tu xep); nhieu hon thi coi nhu LLM sai, hoi lai."""
    return max(3, round(0.03 * n_lines))


class AssembledSection(BaseModel):
    title_lines: list[str] = Field(
        default_factory=list,
        description="IDs of the line(s) forming this section's printed heading; [] if it has none")
    body_lines: list[str] = Field(
        min_length=1, description="IDs of the body lines of this section, in reading order")
    paragraph_starts: list[str] = Field(
        default_factory=list,
        description="IDs (from body_lines) that start a new paragraph, excluding the first body line")
    icon_hint: str = Field(description="One lowercase English noun for an icon, e.g. 'broccoli'")


class AssembledArticle(BaseModel):
    title_lines: list[str] = Field(min_length=1, description="IDs of the main article title line(s)")
    sections: list[AssembledSection] = Field(min_length=1, description="Sections in reading order")
    ignore: list[str] = Field(
        default_factory=list,
        description="IDs of lines that are not article text: series header, credits, picture labels, page numbers")

    @model_validator(mode="after")
    def _covers_every_line_once(self, info: ValidationInfo):
        ids = (info.context or {}).get("line_ids")
        if ids is None:
            return self
        used = list(self.title_lines) + list(self.ignore)
        for s in self.sections:
            used += s.title_lines + s.body_lines
            bad = [p for p in s.paragraph_starts if p not in s.body_lines[1:]]
            if bad:
                raise ValueError(f"paragraph_starts {bad} must be IDs from the same section's body_lines "
                                 "(not its first line)")
        need = set(ids)
        seen: set[str] = set()
        dup = sorted({u for u in used if u in seen or seen.add(u)})
        missing, unknown = sorted(need - seen), sorted(seen - need)
        # Sot vai dong le: code tu xep theo hinh hoc (repair_missing_lines) thay vi hoi lai —
        # thuc do gpt-5-mini quen cung 1 dong qua 4 lan hoi. Sot nhieu (ca box) thi van hoi lai.
        if len(missing) <= max_missing(len(ids)):
            missing = []
        if dup or missing or unknown:
            raise ValueError(
                "Every line ID must appear exactly once across title_lines, sections and ignore. "
                f"duplicated={dup} missing={missing} unknown={unknown}")
        words = (info.context or {}).get("line_words")
        if words:
            total = sum(words.values())
            ignored = sum(words.get(i, 0) for i in self.ignore)
            if total and ignored / total > MAX_IGNORED_WORD_SHARE:
                raise ValueError(
                    f"ignore holds {ignored} of {total} words ({ignored / total:.0%}); at most "
                    f"{MAX_IGNORED_WORD_SHARE:.0%} is allowed. Only picture labels, credits, page furniture and "
                    "words inside diagrams belong in ignore. Every box of sentences, including captions "
                    "written as full sentences next to a picture, must be a section.")
            body_words = [sum(words.get(i, 0) for i in s.body_lines) for s in self.sections]
            mean = sum(body_words) / len(body_words)
            if len(self.sections) > MAX_SECTIONS or mean < MIN_MEAN_SECTION_WORDS:
                raise ValueError(
                    f"{len(self.sections)} sections averaging {mean:.0f} words; expected at most {MAX_SECTIONS} "
                    f"sections averaging at least {MIN_MEAN_SECTION_WORDS} words. A section is a whole box: its "
                    "heading plus all lines of its paragraph(s). Never make one section per line; one-word "
                    "picture labels go to ignore.")
        return self


ASSEMBLE_PROMPT = (
    "This is a page from an English infographic or article, followed by the list of text lines that "
    "an OCR engine read from it. Each line is `ID [x0,y0,x1,y1] text` (pixel box on the page).\n"
    "Your job is ONLY to organise these lines into the article structure. You never write text: "
    "you answer with line IDs, and the text will be taken from the OCR exactly as listed.\n"
    "- title_lines: the main article title.\n"
    "- sections: every text box/section in reading order: the intro paragraph under the title first, "
    "then column by column: finish the whole left column from top to bottom (including boxes at the "
    "bottom of that column) before moving to the next column to the right. For each: its "
    "printed heading lines (title_lines, [] if it has none), its body lines in reading order "
    "(body_lines; follow the column of the box, never jump to a neighbouring column mid-sentence), "
    "paragraph_starts for body lines that begin a new paragraph, and one icon_hint noun. Every "
    "printed box heading (a larger or coloured line above a paragraph) starts its own section: never "
    "merge two boxes into one section. Bold run-in phrases at the start of a paragraph inside a box "
    "(e.g. 'Avoid foods high in ...') are body text, not new sections.\n"
    "- ignore: lines that are not article text: series header or tagline, source/credits line, page "
    "numbers, labels that only name a picture (e.g. 'Broccoli' under a drawing), and words printed "
    "inside a chart, diagram or logo (e.g. 'Fruits', 'Grains', 'Dairy' on a plate chart, or a website "
    "address shown as a logo such as 'ChooseMyPlate.gov'). A line that is part of a sentence is never ignored.\n"
    "- A caption next to a picture that is written as full sentences (e.g. 'R2-D2 is a famous robot from "
    "the Star Wars movies.') is article text: make it its own section (title_lines [] if it has no heading).\n"
    "Use every ID exactly once across title_lines, sections and ignore. Use the image to decide "
    "which box and which column each line belongs to."
)


class AsmLine(BaseModel):
    id: str
    page: int = 0
    text: str
    box: list[float]
    confidence: float
    added: bool = False   # dong nguoi duyet tu doc tu anh (structure.json extra_lines), khong phai OCR


def assign_line_ids(raw: OcrRaw) -> list[AsmLine]:
    """Moi dong OCR -> ID on dinh L000.., xep theo (trang, tren-xuong, trai-sang)."""
    items = [(b.page, ln) for b in raw.blocks for ln in b.lines if ln.text.strip()]
    items.sort(key=lambda t: (t[0], round(t[1].box[1]), t[1].box[0]))
    return [AsmLine(id=f"L{i:03d}", page=p, text=ln.text.strip(), box=ln.box, confidence=ln.confidence)
            for i, (p, ln) in enumerate(items)]


def format_lines_for_prompt(lines: list[AsmLine]) -> str:
    multi = len({l.page for l in lines}) > 1
    out = []
    for l in lines:
        box = ",".join(str(round(v)) for v in l.box)
        out.append(f"{l.id} {'p' + str(l.page) + ' ' if multi else ''}[{box}] {l.text}")
    return "\n".join(out)


class RepairNote(BaseModel):
    line_id: str
    text: str
    placed: str           # "after Lxxx" | "before Lxxx" | "ignore"


def repair_missing_lines(art: AssembledArticle, lines: list[AsmLine]) -> list[RepairNote]:
    """Xep dong LLM bo sot canh dong gan nhat CUNG COT (x chong >= 50%, cach doc <= 3 dong).
    Khong co dong nao nhu vay -> dua vao ignore. Sua `art` tai cho; tra ghi chu cho bao cao."""
    by_id = {l.id: l for l in lines}
    containers: list[list[str]] = [art.title_lines]
    for s in art.sections:
        containers += [s.title_lines, s.body_lines]
    assigned = {i for c in containers for i in c}
    missing = [l for l in lines if l.id not in assigned and l.id not in set(art.ignore)]
    if not missing:
        return []
    hs = sorted(l.box[3] - l.box[1] for l in lines)
    h = max(hs[len(hs) // 2], 1.0)
    notes: list[RepairNote] = []
    for m in sorted(missing, key=lambda l: (l.page, l.box[1], l.box[0])):
        my = (m.box[1] + m.box[3]) / 2
        best: tuple[float, list[str], str] | None = None
        for c in containers:
            for cid in c:
                n = by_id[cid]
                if n.page != m.page:
                    continue
                overlap = min(n.box[2], m.box[2]) - max(n.box[0], m.box[0])
                if overlap < 0.5 * min(n.box[2] - n.box[0], m.box[2] - m.box[0]):
                    continue
                dy = abs((n.box[1] + n.box[3]) / 2 - my)
                if dy <= 3 * h and (best is None or dy < best[0]):
                    best = (dy, c, cid)
        if best is None:
            art.ignore.append(m.id)
            notes.append(RepairNote(line_id=m.id, text=m.text, placed="ignore"))
            continue
        _, c, cid = best
        n = by_id[cid]
        k = c.index(cid)
        if (n.box[1] + n.box[3]) / 2 <= my:
            c.insert(k + 1, m.id)
            notes.append(RepairNote(line_id=m.id, text=m.text, placed=f"after {cid}"))
        else:
            c.insert(k, m.id)
            notes.append(RepairNote(line_id=m.id, text=m.text, placed=f"before {cid}"))
    return notes


class HyphenNote(BaseModel):
    left: str
    right: str
    result: str
    joined: bool          # True: bo gach, noi lien; False: giu gach
    known: bool           # tu ghep co trong tu dien hay khong


def _is_dict_word(word: str) -> bool:
    from pipeline.ipa import _dict
    return word.lower() in _dict()


def join_lines(texts: list[str], is_word=None) -> tuple[str, list[HyphenNote]]:
    """Noi cac dong thanh 1 doan. Gach noi cuoi dong + dong sau bat dau bang chu thuong:
    - tu ghep (bo gach) co trong tu dien -> noi lien ("veg-"+"etables" -> "vegetables");
    - khong co nhung 2 nua deu la tu -> giu gach ("well-"+"being" -> "well-being"), ghi chu;
    - con lai -> noi lien, ghi chu (tu hiem bi ngat dong)."""
    is_word = is_word or _is_dict_word
    notes: list[HyphenNote] = []
    out = ""
    for t in texts:
        t = t.strip()
        if not t:
            continue
        if not out:
            out = t
            continue
        m_left = _TRAILING_HYPHEN_RE.search(out)
        m_right = _LEADING_WORD_RE.match(t)
        if m_left and m_right:
            left, right = m_left.group(1), m_right.group(1)
            joined_word = left + right
            if is_word(joined_word):
                out = out[:-1] + t
                notes.append(HyphenNote(left=left, right=right, result=joined_word, joined=True, known=True))
            elif is_word(left) and is_word(right):
                out = out + t
                notes.append(HyphenNote(left=left, right=right, result=f"{left}-{right}",
                                        joined=False, known=False))
            else:
                out = out[:-1] + t
                notes.append(HyphenNote(left=left, right=right, result=joined_word,
                                        joined=True, known=False))
        else:
            out = f"{out} {t}"
    return out, notes


def assemble_sections(slug: str, art: AssembledArticle, lines: list[AsmLine],
                      is_word=None) -> tuple[NormalizedSections, list[HyphenNote]]:
    """Ghep text NGUYEN VAN tu OCR theo cau truc ID cua LLM."""
    by_id = {l.id: l for l in lines}
    notes: list[HyphenNote] = []

    def text_of(ids: list[str]) -> str:
        t, n = join_lines([by_id[i].text for i in ids], is_word=is_word)
        notes.extend(n)
        return t

    title = text_of(art.title_lines)
    sections = []
    for order, s in enumerate(art.sections):
        paragraphs: list[list[str]] = [[]]
        for lid in s.body_lines:
            if lid in s.paragraph_starts and paragraphs[-1]:
                paragraphs.append([])
            paragraphs[-1].append(lid)
        body = "\n\n".join(text_of(p) for p in paragraphs if p)
        sec_title = text_of(s.title_lines) if s.title_lines else title
        sections.append(NormalizedSection(order=order, title=sec_title, body=body,
                                          icon_hint=s.icon_hint.strip().lower()))
    return NormalizedSections(slug=slug, title=title, sections=sections), notes


_DQ = '"“”'


def normalize_quotes_paragraph(text: str) -> str | None:
    """Ghep cap ngoac kep trong 1 doan -> “…” (OCR hay doc ngoac dong ” thanh ").
    Bo dau cach thua truoc ngoac dong ('question. "' -> 'question.”').
    So ngoac le (trich dan keo qua nhieu doan / OCR sot) -> None, giu nguyen de nguoi duyet xem."""
    if sum(text.count(c) for c in _DQ) % 2:
        return None
    out: list[str] = []
    is_open = False
    for ch in text:
        if ch in _DQ:
            if is_open:
                while out and out[-1] == " ":
                    out.pop()
                out.append("”")
            else:
                out.append("“")
            is_open = not is_open
        else:
            out.append(ch)
    return "".join(out)


def normalize_article_quotes(data: NormalizedSections) -> list[str]:
    """Chi ap khi bai co it nhat 1 ngoac cong (ban goc dung kieu cong) -> dong nhat ca bai ve “…”.
    Bai chi co ngoac thang giu nguyen (khong doi chu cac bai da seed). Tra cac doan ngoac le."""
    texts = [data.title] + [s.title for s in data.sections] + [s.body for s in data.sections]
    if not any(c in t for t in texts for c in "“”"):
        return []
    odd: list[str] = []

    def fix(text: str, where: str) -> str:
        paras = text.split("\n\n")
        for i, p in enumerate(paras):
            q = normalize_quotes_paragraph(p)
            if q is None:
                odd.append(f"[{where}] {p[:80]}…")
            else:
                paras[i] = q
        return "\n\n".join(paras)

    data.title = fix(data.title, "tiêu đề bài")
    for s in data.sections:
        s.title = fix(s.title, f"{s.order}. tiêu đề")
        s.body = fix(s.body, f"{s.order}. {s.title}")
    return odd


def punctuation_suspects(text: str) -> list[str]:
    """'salt. sugar' -> nghi OCR doc dau phay thanh dau cham. Bo qua 'etc. you', 'e.g. apples'."""
    hits = []
    for m in _PUNCT_SUSPECT_RE.finditer(text):
        before = m.group(1).lower()
        if before in _PUNCT_OK_BEFORE or text[max(0, m.start() - 2):m.start()].endswith("."):
            continue
        s, e = max(0, m.start() - 25), min(len(text), m.end() + 25)
        hits.append(text[s:e].replace("\n", " "))
    return hits


# ---------------------------------------------------------------- kiem chu OCR bang code (BE-02d)
# Ly do (run #78, bai paris): moi loi OCR deu co confidence cao (Enolish 0,985; bridoe 0,970)
# nen loc confidence < 0,9 khong bat duoc gi; dong bi sot thi khong co confidence. 3 canh bao duoi
# chi BAO, khong tu sua (ADR-012: chu chi den tu OCR + nguoi duyet).
GAP_FACTOR = 1.6
_WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")  # chu co dau (Musée) la 1 tu
_BLOCK_END = tuple('.?!:"”’)')


@lru_cache(maxsize=1)
def known_words() -> frozenset[str]:
    """CMUdict + ipa.json + lemma cua cefr_lexicon.json (viet thuong)."""
    from pipeline.ipa import _dict, _manual
    words = set(_dict()) | {k.lower() for k in _manual()}
    lex = PIPELINE_DIR / "data" / "cefr_lexicon.json"
    if lex.exists():
        d = json.loads(lex.read_text(encoding="utf-8"))
        words |= {k.rsplit("|", 1)[0] for k in d["entries"]}
    return frozenset(words)


def is_known_word(word: str, known: frozenset[str] | None = None) -> bool:
    known = known if known is not None else known_words()
    w = word.lower().replace("’", "'")
    for cand in (w, re.sub(r"'s$", "", w), w.rstrip("'")):
        if cand in known:
            return True
    return False


class TextWarning(BaseModel):
    kind: Literal["unknown_word", "gap", "unfinished"]
    where: str                       # "<order>. <title>"
    line_id: str | None = None
    detail: str


def unknown_word_warnings(data: NormalizedSections, art: AssembledArticle, lines: list[AsmLine],
                          known: frozenset[str] | None = None) -> list[TextWarning]:
    """Tu khong co trong CMUdict / ipa.json / cefr_lexicon → nghi loi OCR (ten rieng cung bi bao)."""
    by_id = {l.id: l for l in lines}
    first: dict[str, TextWarning] = {}
    count: dict[str, int] = {}
    parts = [("(tiêu đề bài)", art.title_lines, data.title)]
    parts += [(f"{s_out.order}. {s_out.title}", s.title_lines + s.body_lines, f"{s_out.title}\n{s_out.body}")
              for s_out, s in zip(data.sections, art.sections)]
    for where, ids, text in parts:
        for word in _WORD_RE.findall(text):
            key = word.lower()
            if key in count:
                count[key] += 1
                continue
            if is_known_word(word, known):
                continue
            count[key] = 1
            lid = next((i for i in ids if word in by_id[i].text), None)
            first[key] = TextWarning(kind="unknown_word", where=where, line_id=lid, detail=word)
    # Moi tu la 1 dong cho ca bai (ten rieng lap lai nhieu card chi bao 1 lan, kem so lan gap)
    return [w.model_copy(update={"detail": w.detail + (f" (×{count[k]})" if count[k] > 1 else "")})
            for k, w in first.items()]


def _x_overlap(a: list[float], b: list[float]) -> bool:
    return min(a[2], b[2]) - max(a[0], b[0]) > 0.3 * min(a[2] - a[0], b[2] - b[0])


def gap_warnings(data: NormalizedSections, art: AssembledArticle, lines: list[AsmLine],
                 factor: float = GAP_FACTOR) -> list[TextWarning]:
    """Trong 1 section, 2 dong lien nhau cung cot cach nhau > factor × khoang cach trung vi
    → nghi sot dong. Bo qua cap ma dong sau mo dau doan moi (khoang cach doan lon hon la binh thuong)."""
    by_id = {l.id: l for l in lines}
    out: list[TextWarning] = []
    for s_out, s in zip(data.sections, art.sections):
        pairs = []
        for a_id, b_id in zip(s.body_lines, s.body_lines[1:]):
            a, b = by_id[a_id], by_id[b_id]
            if a.added or b.added:
                continue  # dong nguoi duyet them da lap cho ho nay
            if a.page == b.page and _x_overlap(a.box, b.box) and b.box[1] > a.box[1]:
                pairs.append((a, b, b.box[1] - a.box[1], b_id in s.paragraph_starts))
        steps = sorted(d for *_, d, para in pairs if not para)
        if len(steps) < 2:
            continue
        median = steps[len(steps) // 2]
        for a, b, d, para in pairs:
            if not para and d > factor * median:
                out.append(TextWarning(
                    kind="gap", where=f"{s_out.order}. {s_out.title}", line_id=b.id,
                    detail=f"giữa `{a.id}` và `{b.id}` cách {d:.0f}px (thường {median:.0f}px): "
                           f"…{a.text[-30:]} ‖ {b.text[:30]}…"))
    return out


def unfinished_warnings(data: NormalizedSections) -> list[TextWarning]:
    """Doan van ket thuc khong bang . ? ! : hay ngoac dong → nghi sot dong cuoi / OCR mat dau cau."""
    out: list[TextWarning] = []
    for s in data.sections:
        for para in s.body.split("\n\n"):
            p = para.rstrip()
            n = len(p.split())
            if n <= 3 or (n <= 5 and re.search(r"\d", p)):
                continue  # dong bang so lieu "Country France", "Population 2.34 million" (nhan + gia tri)
            if p and not p.endswith(_BLOCK_END):
                out.append(TextWarning(kind="unfinished", where=f"{s.order}. {s.title}",
                                       detail=f"…{p[-50:]}"))
    return out


def text_warnings(data: NormalizedSections, art: AssembledArticle, lines: list[AsmLine],
                  known: frozenset[str] | None = None) -> list[TextWarning]:
    return (unknown_word_warnings(data, art, lines, known) + gap_warnings(data, art, lines)
            + unfinished_warnings(data))


def assemble_report(data: NormalizedSections, art: AssembledArticle, lines: list[AsmLine],
                    notes: list[HyphenNote], repairs: list[RepairNote] | None = None,
                    odd_quotes: list[str] | None = None) -> str:
    by_id = {l.id: l for l in lines}
    sec_of: dict[str, str] = {}
    for s_out, s in zip(data.sections, art.sections):
        for lid in s.title_lines + s.body_lines:
            sec_of[lid] = f"{s_out.order}. {s_out.title}"
    for lid in art.title_lines:
        sec_of[lid] = "(tiêu đề bài)"

    low = [l for l in lines if l.confidence < LOW_CONF and l.id not in art.ignore]
    punct = [(f"{s.order}. {s.title}", h) for s in data.sections for h in punctuation_suspects(s.body)]
    odd_hyphen = [n for n in notes if not n.known]
    out = [
        f"# Ghép từ OCR: {data.slug}",
        "",
        "Chữ lấy nguyên văn từ OCR; LLM chỉ chọn ID dòng (ADR-012). Phải soát: lỗi OCR (mục 1-2), "
        "dòng bị bỏ (mục 3), gạch nối (mục 4), chia section (mục 5).",
        "",
        f"'{data.title}' · {len(data.sections)} section · "
        f"{sum(len(s.body.split()) for s in data.sections)} từ · {len(lines)} dòng OCR · "
        f"bỏ {len(art.ignore)} dòng",
        "",
        "## 0. Dòng LLM bỏ sót — code tự xếp cạnh dòng gần nhất cùng cột (soát vị trí)",
        "",
    ]
    out += [f"- `{r.line_id}` {r.text} → "
            + (f"**bỏ qua** (không có dòng cùng cột gần đó)" if r.placed == "ignore"
               else f"{'sau' if r.placed.startswith('after') else 'trước'} `{r.placed.split()[1]}` "
                    f"({sec_of.get(r.line_id, '?')})")
            for r in (repairs or [])] or ["- Không có."]
    added = [l for l in lines if l.added]
    if added:
        out += ["", "**Dòng do người duyệt thêm (`extra_lines`, đọc từ ảnh — không phải chữ OCR):**", ""]
        out += [f"- `{l.id}` {l.text} — {sec_of.get(l.id, '?')}" for l in added]
    warns = text_warnings(data, art, lines)
    groups = [
        ("unknown_word", "1a. Từ lạ (không có trong CMUdict / ipa.json / cefr_lexicon) — nghi lỗi OCR; "
                         "tên riêng cũng bị báo, bỏ qua nếu đúng"),
        ("gap", f"1b. Khoảng hở dọc > {GAP_FACTOR}× bình thường — nghi OCR sót dòng (soát ảnh)"),
        ("unfinished", "1c. Đoạn kết thúc không có dấu câu — nghi sót dòng cuối hoặc mất dấu chấm"),
    ]
    out += ["", "## 1. Cảnh báo kiểm chữ (BE-02d) — chỉ báo, không tự sửa", ""]
    for kind, head in groups:
        out += [f"**{head}:**", ""]
        out += [f"- [{w.where}]" + (f" `{w.line_id}`" if w.line_id else "") + f" {w.detail}"
                for w in warns if w.kind == kind] or ["- Không có."]
        out.append("")
    out += [f"**1d. Dòng OCR confidence < {LOW_CONF:.2f}:**", ""]
    out += [f"- `{l.id}` ({l.confidence:.2f}) {l.text} — {sec_of.get(l.id, '?')}" for l in low] or ["- Không có."]
    out += ["", "## 2. Nghi lỗi dấu câu (`. ` + chữ thường — OCR hay đọc dấu phẩy thành dấu chấm)", ""]
    out += [f"- [{sec}] …{h}…" for sec, h in punct] or ["- Không có."]
    out += ["", "## 2b. Đoạn có số ngoặc kép lẻ (chưa chuẩn hóa “…”, soát với ảnh)", ""]
    out += [f"- {o}" for o in (odd_quotes or [])] or ["- Không có."]
    out += ["", "## 3. Dòng bị bỏ qua (chắc chắn không phải câu thân bài?)", ""]
    out += [f"- `{i}` {by_id[i].text}" for i in art.ignore] or ["- Không có."]
    out += ["", "## 4. Gạch nối cuối dòng không có trong từ điển (kiểm cách viết)", ""]
    out += [f"- `{n.left}-` + `{n.right}` → **{n.result}**" + ("" if n.joined else " (giữ gạch)")
            for n in odd_hyphen] or ["- Không có."]
    out += ["", "## 5. Section (đọc lướt: đúng box, đúng thứ tự, không lẫn cột)", ""]
    for s_out, s in zip(data.sections, art.sections):
        out.append(f"### {s_out.order}. {s_out.title} · icon: {s_out.icon_hint} · "
                   f"dòng {', '.join(s.body_lines[:1] + (['…', s.body_lines[-1]] if len(s.body_lines) > 1 else []))}")
        out += ["", s_out.body, ""]
    return "\n".join(out) + "\n"


def assemble_cache_key(deployment: str, image_paths: list[Path], lines: list[AsmLine]) -> str:
    h = hashlib.sha256()
    h.update(f"{deployment}|{ASSEMBLE_PROMPT_VERSION}|{ASSEMBLE_PROMPT}".encode())
    h.update(format_lines_for_prompt(lines).encode())
    for p in image_paths:
        h.update(p.read_bytes())
    return h.hexdigest()[:32]


def call_assemble(image_paths: list[Path], lines: list[AsmLine]) -> tuple[AssembledArticle, bool]:
    from dotenv import load_dotenv
    load_dotenv(PIPELINE_DIR.parent / ".env")
    deployment = os.environ.get("AZURE_DEPLOYMENT_VISION", "")
    if not deployment or not os.environ.get("AZURE_OPENAI_API_KEY"):
        sys.exit("Thieu AZURE_DEPLOYMENT_VISION / AZURE_OPENAI_API_KEY trong .env")
    ctx = {"line_ids": [l.id for l in lines], "line_words": {l.id: len(l.text.split()) for l in lines}}

    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"assemble_{assemble_cache_key(deployment, image_paths, lines)}.json"
    if cache_file.exists():
        try:
            return AssembledArticle.model_validate_json(cache_file.read_text(encoding="utf-8"), context=ctx), True
        except ValueError:
            cache_file.unlink()  # cache cu khong con qua validator moi -> hoi lai LLM

    import instructor
    from instructor.processing.multimodal import Image
    client = instructor.from_provider(f"azure_openai/{deployment}",
                                      api_version=os.environ["AZURE_OPENAI_API_VERSION"])
    content: list = [ASSEMBLE_PROMPT] + [Image.from_path(str(p)) for p in image_paths] + [
        "OCR lines:\n" + format_lines_for_prompt(lines)]
    art = client.create(
        response_model=AssembledArticle,
        messages=[{"role": "user", "content": content}],
        context=ctx,
        max_retries=2,
    )
    cache_file.write_text(art.model_dump_json(indent=2), encoding="utf-8")
    return art, False


def apply_extra_lines(spec: dict, lines: list[AsmLine], extras: list[dict]) -> list[AsmLine]:
    """structure.json `extra_lines` [{"after": "L136", "text": "..."}]: dong OCR bo sot, nguoi duyet
    doc tu anh. Chen dong moi (ID "L136a", "L136b"…) ngay sau `after` trong `lines` va trong danh sach
    ID cua spec (title_lines / section title_lines / body_lines). Box dat giua dong truoc va dong sau
    cung cot de canh bao khoang ho (1b) khong bao lai. `after` co the la ID vua them (chuoi nhieu dong)."""
    out = list(lines)
    for ex in extras:
        after, text = ex["after"], ex["text"].strip()
        idx = next((k for k, l in enumerate(out) if l.id == after), None)
        if idx is None:
            raise ValueError(f"extra_lines: ID '{after}' khong ton tai")
        base = out[idx]
        suffix = "a"
        while any(l.id == f"{after}{suffix}" for l in out):
            suffix = chr(ord(suffix) + 1)
        new_id = f"{after}{suffix}"
        lists = [spec.get("title_lines", [])] + [x for sec in spec["sections"]
                                                  for x in (sec.get("title_lines", []), sec["body_lines"])]
        host = next((lst for lst in lists if after in lst), None)
        if host is None:
            raise ValueError(f"extra_lines: '{after}' khong nam trong section nao cua structure.json")
        pos = host.index(after)
        nxt = next((l for l in out if pos + 1 < len(host) and l.id == host[pos + 1]), None)
        h = base.box[3] - base.box[1]
        y0 = (base.box[1] + nxt.box[1]) / 2 if nxt and nxt.box[1] > base.box[1] else base.box[1] + h + 1
        host.insert(pos + 1, new_id)
        out.insert(idx + 1, AsmLine(id=new_id, page=base.page, text=text, confidence=1.0, added=True,
                                    box=[base.box[0], y0, base.box[2], y0 + h]))
    return out


def cmd_assemble(args: argparse.Namespace) -> None:
    src = Path(args.input)
    out_dir = OUT_DIR / args.slug
    out_dir.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        sys.exit(f"Khong tim thay input: {src}")
    image_paths = pdf_pages_as_png(src, out_dir / "pages") if src.suffix.lower() == ".pdf" else [src]

    ocr_lines_for_source(src, out_dir, lang=args.lang, fast=args.fast,
                         upscale=args.upscale)  # tao ocr_raw.json neu chua co
    raw = OcrRaw.model_validate_json((out_dir / "ocr_raw.json").read_text(encoding="utf-8-sig"))
    lines = assign_line_ids(raw)
    if not lines:
        sys.exit("OCR khong doc duoc dong nao — kiem tra lai anh dau vao.")

    if args.structure:
        # Cau truc xep tay (khi LLM lam hong, vd poster nhieu chu thich): van chi la ID dong,
        # chu lay nguyen van OCR, qua cung validator (ADR-012).
        # Tuy chon them: line_fixes {ID: chu dung} sua loi OCR tung dong (nguoi duyet chi ra);
        # section_titles {"k": "tieu de"} cho section khong co tieu de in san.
        spec = json.loads(Path(args.structure).read_text(encoding="utf-8"))
        line_fixes: dict[str, str] = spec.pop("line_fixes", {})
        section_titles: dict[str, str] = spec.pop("section_titles", {})
        lines = apply_extra_lines(spec, lines, spec.pop("extra_lines", []))
        for l in lines:
            if l.added:
                print(f"  them dong {l.id} (nguoi duyet): {l.text!r}")
        unknown = sorted(set(line_fixes) - {l.id for l in lines})
        if unknown:
            sys.exit(f"line_fixes co ID khong ton tai: {unknown}")
        for l in lines:
            if l.id in line_fixes:
                print(f"  sua OCR {l.id}: {l.text!r} -> {line_fixes[l.id]!r}")
                l.text = line_fixes[l.id]
        ctx = {"line_ids": [l.id for l in lines], "line_words": {l.id: len(l.text.split()) for l in lines}}
        art = AssembledArticle.model_validate(spec, context=ctx)
        cache_hit = True
    else:
        section_titles = {}
        art, cache_hit = call_assemble(image_paths, lines)
    repairs = repair_missing_lines(art, lines)
    data, notes = assemble_sections(args.slug, art, lines)
    for k, title in section_titles.items():
        data.sections[int(k)].title = title
    odd_quotes = normalize_article_quotes(data)
    problems = validate_normalized(data, args.slug)

    out_file = out_dir / "normalized_sections.json"
    if out_file.exists() and not args.force:
        out_file = out_dir / "assembled_sections.json"
        print("CHU Y: normalized_sections.json da ton tai (co the da sua tay) -> ghi ra "
              "assembled_sections.json. Dung --force de ghi de.")
    out_file.write_text(data.model_dump_json(indent=2), encoding="utf-8")
    report = out_dir / "assemble.md"
    report.write_text(assemble_report(data, art, lines, notes, repairs, odd_quotes), encoding="utf-8")
    print(f"OK -> {out_file}" + (" (cache hit, khong goi API)" if cache_hit else ""))
    print(f"  bao cao: {report} · {len(lines)} dong OCR · bo qua {len(art.ignore)}"
          + (f" · LLM bo sot {len(repairs)} dong (code tu xep, xem muc 0)" if repairs else ""))
    print_summary(data)
    if problems:
        for p in problems:
            print(f"CHU Y: {p}")
        sys.exit(1)
    print(f"Tiep theo: doc {report.name}, roi py -m pipeline.extract crosscheck --input {src} "
          f"--slug {args.slug}" + (f" --sections {out_file}" if out_file.name != "normalized_sections.json" else ""))


# ---------------------------------------------------------------- vision (ADR-009)
def vision_cache_key(deployment: str, image_paths: list[Path]) -> str:
    h = hashlib.sha256()
    h.update(f"{deployment}|{PROMPT_VERSION}|{EXTRACT_PROMPT}".encode())
    for p in image_paths:
        h.update(p.read_bytes())
    return h.hexdigest()[:32]


def call_vision(image_paths: list[Path]) -> tuple[ExtractedArticle, bool]:
    """Goi Azure Vision qua instructor, co cache. Tra (ket_qua, cache_hit)."""
    from dotenv import load_dotenv
    load_dotenv(PIPELINE_DIR.parent / ".env")
    deployment = os.environ.get("AZURE_DEPLOYMENT_VISION", "")
    if not deployment or not os.environ.get("AZURE_OPENAI_API_KEY"):
        sys.exit("Thieu AZURE_DEPLOYMENT_VISION / AZURE_OPENAI_API_KEY trong .env")

    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"vision_{vision_cache_key(deployment, image_paths)}.json"
    if cache_file.exists():
        return ExtractedArticle.model_validate_json(cache_file.read_text(encoding="utf-8")), True

    import instructor
    from instructor.processing.multimodal import Image
    client = instructor.from_provider(
        f"azure_openai/{deployment}",  # instructor >= 1.17 doi ten provider azure -> azure_openai
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )
    content: list = [EXTRACT_PROMPT] + [Image.from_path(str(p)) for p in image_paths]
    article = client.create(
        response_model=ExtractedArticle,
        messages=[{"role": "user", "content": content}],
        max_retries=2,
    )
    cache_file.write_text(article.model_dump_json(indent=2), encoding="utf-8")
    return article, False


def cmd_vision(args: argparse.Namespace) -> None:
    src = Path(args.input)
    if not src.exists():
        sys.exit(f"Khong tim thay input: {src}")
    out_dir = OUT_DIR / args.slug
    out_dir.mkdir(parents=True, exist_ok=True)

    if src.suffix.lower() == ".pdf":
        image_paths = pdf_pages_as_png(src, out_dir / "pages")
    else:
        image_paths = [src]

    article, cache_hit = call_vision(image_paths)
    data = normalized_from_extracted(args.slug, article)
    problems = validate_normalized(data, args.slug)

    out_file = out_dir / "normalized_sections.json"
    if out_file.exists() and not args.force:
        # Ban dang co thuong da duoc sua tay theo anh -> khong ghi de; ghi ban moi ra file rieng.
        out_file = out_dir / "vision_sections.json"
        print("CHU Y: normalized_sections.json da ton tai (co the da sua tay) -> ghi ra "
              "vision_sections.json. Dung --force de ghi de.")
    out_file.write_text(data.model_dump_json(indent=2), encoding="utf-8")
    print(f"OK -> {out_file}" + (" (cache hit, khong goi API)" if cache_hit else ""))
    print_summary(data)
    if problems:
        for p in problems:
            print(f"CHU Y: {p}")
        sys.exit(1)
    print(f"Tiep theo: py -m pipeline.extract crosscheck --input {src} --slug {args.slug}"
          + (f" --sections {out_file}" if out_file.name != "normalized_sections.json" else ""))


# ---------------------------------------------------------------- commands
def cmd_ocr(args: argparse.Namespace) -> None:
    src = Path(args.input)
    if not src.exists():
        sys.exit(f"Khong tim thay input: {src}")
    out_dir = OUT_DIR / args.slug
    out_dir.mkdir(parents=True, exist_ok=True)

    pages: list[PageInfo] = []
    blocks: list[OcrBlock] = []
    engine: str

    if src.suffix.lower() == ".pdf" and pdf_has_text_layer(src):
        engine = "pymupdf_text"
        blocks = blocks_from_pdf_text(src)
    else:
        if src.suffix.lower() == ".pdf":
            page_files = pdf_pages_as_png(src, out_dir / "pages")
        else:
            dst = out_dir / f"source{src.suffix.lower()}"
            dst.write_bytes(src.read_bytes())
            page_files = [dst]
        engine = "paddleocr" if args.no_structure else "pp_structure_v3"
        for pno, img in enumerate(page_files):
            w, h = image_size(img)
            pages.append(PageInfo(file=img.relative_to(out_dir).as_posix(), width=w, height=h))
            prefix = f"p{pno}_b" if len(page_files) > 1 else "b"
            if args.no_structure:
                lines = run_plain_ocr_on_image(img, lang=args.lang)
                blocks += blocks_from_plain_ocr(lines, page=pno, id_prefix=prefix)
            else:
                parsing, lines = run_structure_on_image(img)
                blocks += blocks_from_structure(parsing, lines, page=pno, id_prefix=prefix)
        blocks = renumber(blocks)

    if not blocks:
        sys.exit("OCR khong doc duoc block nao — kiem tra lai anh dau vao.")

    raw = OcrRaw(slug=args.slug, source=str(src).replace("\\", "/"), engine=engine,
                 pages=pages, blocks=blocks)
    out_file = out_dir / "ocr_raw.json"
    out_file.write_text(raw.model_dump_json(indent=2), encoding="utf-8")

    low = [b for b in blocks if b.lines and min(l.confidence for l in b.lines) < 0.90]
    print(f"OK -> {out_file}")
    print(f"  engine={engine} · {len(blocks)} block · {sum(len(b.lines) for b in blocks)} dong")
    if low:
        print(f"  CHU Y: {len(low)} block co dong confidence < 0.90 — xem ky trong man duyet")
    print(f"Tiep theo: py -m pipeline.extract review --slug {args.slug}")


def cmd_review(args: argparse.Namespace) -> None:
    out_dir = OUT_DIR / args.slug
    raw_file = out_dir / "ocr_raw.json"
    if not raw_file.exists():
        sys.exit(f"Chua co {raw_file} — chay lenh ocr truoc.")
    raw = OcrRaw.model_validate_json(raw_file.read_text(encoding="utf-8-sig"))

    images: dict[int, str] = {}
    for i, page in enumerate(raw.pages):
        img_path = out_dir / page.file
        mime = "image/png" if img_path.suffix.lower() == ".png" else "image/jpeg"
        images[i] = f"data:{mime};base64,{base64.b64encode(img_path.read_bytes()).decode()}"

    template = (PIPELINE_DIR / "review_template.html").read_text(encoding="utf-8")
    html = (template
            .replace("__OCR_JSON__", json.dumps(raw.model_dump(), ensure_ascii=False))
            .replace("__IMAGES_JSON__", json.dumps(images)))
    out_file = out_dir / "review_ocr.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"OK -> {out_file}")
    print("Mo file nay trong trinh duyet, duyet xong bam 'Xuat normalized_sections.json'")
    print(f"roi luu file tai xuong vao {out_dir}\\normalized_sections.json")


def cmd_check(args: argparse.Namespace) -> None:
    out_dir = OUT_DIR / args.slug
    f = out_dir / "normalized_sections.json"
    if not f.exists():
        sys.exit(f"Chua co {f} — duyet trong review_ocr.html va luu file xuong do.")
    # utf-8-sig: chiu duoc BOM khi nguoi duyet luu file bang Notepad/PowerShell
    data = NormalizedSections.model_validate_json(f.read_text(encoding="utf-8-sig"))
    problems = validate_normalized(data, args.slug)
    print_summary(data)
    if problems:
        for p in problems:
            print(f"LOI: {p}")
        sys.exit(1)
    level, msg = crosscheck_status(out_dir, f)
    if level == "flagged":
        print(f"LOI: {msg}")
        sys.exit(1)
    if level in ("missing", "stale"):
        print(f"CHU Y: {msg} — nen chay `py -m pipeline.extract crosscheck --input <anh> --slug {args.slug}`.")
    else:
        print(f"  {msg}")
    print("OK — san sang cho B3 (tokenize bang spaCy tren normalized text).")


def main() -> None:
    ap = argparse.ArgumentParser(prog="pipeline.extract", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("vision", help="Vision (Azure, instructor) -> normalized_sections.json")
    p.add_argument("--input", required=True, help="anh (jpg/png) hoac PDF")
    p.add_argument("--slug", required=True)
    p.add_argument("--force", action="store_true",
                   help="ghi de normalized_sections.json da co (mac dinh ghi ra vision_sections.json)")
    p.set_defaults(func=cmd_vision)

    p = sub.add_parser("assemble", help="OCR doc chu + LLM chi chon ID dong -> normalized_sections.json")
    p.add_argument("--input", required=True, help="anh (jpg/png) hoac PDF")
    p.add_argument("--slug", required=True)
    p.add_argument("--force", action="store_true",
                   help="ghi de normalized_sections.json da co (mac dinh ghi ra assembled_sections.json)")
    p.add_argument("--lang", default="en")
    p.add_argument("--structure", default=None,
                   help="JSON cau truc xep tay (title_lines/sections/ignore bang ID dong) thay cho LLM")
    p.add_argument("--fast", action="store_true",
                   help="OCR bang PP-OCRv6_small (nhanh tren CPU; cho bao/PDF 1 cot). Chi co tac dung "
                        "khi chua co ocr_raw.json")
    p.add_argument("--upscale", type=float, default=None,
                   help="phong anh truoc OCR (BE-02d; infographic nen 2). Chi co tac dung khi chua co ocr_raw.json")
    p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("crosscheck", help="OCR cuc bo + so tung manh cau cua Vision -> crosscheck.md")
    p.add_argument("--input", required=True, help="anh (jpg/png) hoac PDF goc")
    p.add_argument("--slug", required=True)
    p.add_argument("--sections", default=None,
                   help="file sections can doi chieu (mac dinh out/<slug>/normalized_sections.json)")
    p.add_argument("--threshold", type=int, default=CROSSCHECK_THRESHOLD)
    p.add_argument("--lang", default="en")
    p.set_defaults(func=cmd_crosscheck)

    p = sub.add_parser("ocr", help="[fallback] PaddleOCR/PP-StructureV3 -> ocr_raw.json")
    p.add_argument("--input", required=True, help="anh (jpg/png) hoac PDF")
    p.add_argument("--slug", required=True)
    p.add_argument("--no-structure", action="store_true",
                   help="bo qua PP-StructureV3, chi OCR dong (anh 1 cot don gian)")
    p.add_argument("--lang", default="en")
    p.set_defaults(func=cmd_ocr)

    p = sub.add_parser("review", help="sinh review_ocr.html tu ocr_raw.json")
    p.add_argument("--slug", required=True)
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("check", help="kiem tra normalized_sections.json")
    p.add_argument("--slug", required=True)
    p.set_defaults(func=cmd_check)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
