"""BE-06d · Audio mục từ: Azure Speech TTS → mp3 → bucket `audio` (chỉ chạy trên máy cá nhân).

    py -m pipeline.audio --slug eating-well --local     # tạo mp3 (cache) + upload lên Supabase local
    py -m pipeline.audio --slug eating-well             # upload lên project cloud
    py -m pipeline.seed  --slug eating-well [--local]   # seed điền audio_url theo file có trong bucket

Luật:
- Đọc `canonical_form`, giọng en-US cố định, tốc độ thường (app tự phát 0.75x, ADR-014/015).
- Tên file trong bucket: `<lemma_key slug hóa>.mp3` → mục dùng chung giữa các bài chỉ có 1 file.
- Cache mp3 trong `pipeline/.cache/audio/` theo (giọng, chữ): chạy lại / đổi nơi upload không gọi TTS lại.
- `bundle.json` giữ `audio_url = null` (không phụ thuộc local/cloud); `pipeline.seed` điền URL công khai
  của đúng nơi đang seed cho mục có file trong bucket (`fill_audio_urls`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
from xml.sax.saxutils import escape

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "pipeline" / ".cache" / "audio"
OUT = ROOT / "pipeline" / "out"
BUCKET = "audio"
VOICE = "en-US-JennyNeural"
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"


def audio_file_name(lemma_key: str) -> str:
    """'play a vital role in' → 'play-a-vital-role-in.mp3'."""
    slug = re.sub(r"[^a-z0-9]+", "-", lemma_key.lower()).strip("-")
    if not slug:
        raise ValueError(f"lemma_key không tạo được tên file: {lemma_key!r}")
    return f"{slug}.mp3"


def ssml(text: str, voice: str = VOICE) -> str:
    return (f"<speak version='1.0' xml:lang='en-US'><voice name='{voice}'>"
            f"{escape(text)}</voice></speak>")


def cache_path(text: str, voice: str = VOICE) -> pathlib.Path:
    h = hashlib.sha256(f"{voice}|{OUTPUT_FORMAT}|{text}".encode()).hexdigest()[:16]
    return CACHE / f"{h}.mp3"


def synthesize(text: str, key: str, region: str, voice: str = VOICE) -> bytes:
    """mp3 của `text`; có trong cache thì không gọi Azure."""
    p = cache_path(text, voice)
    if p.exists():
        return p.read_bytes()
    import httpx
    r = httpx.post(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml",
                 "X-Microsoft-OutputFormat": OUTPUT_FORMAT, "User-Agent": "pipeline-tts"},
        content=ssml(text, voice).encode("utf-8"), timeout=30)
    r.raise_for_status()
    if not r.content.startswith((b"ID3", b"\xff\xf3", b"\xff\xfb", b"\xff\xf2")):
        raise RuntimeError(f"Azure TTS không trả mp3 cho {text!r}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(r.content)
    return r.content


# ---------------------------------------------------------------- bucket
def bucket_files(db) -> set[str]:
    return {f["name"] for f in db.storage.from_(BUCKET).list("", {"limit": 10000}) if f.get("name")}


def public_url(db, name: str) -> str:
    return db.storage.from_(BUCKET).get_public_url(name).rstrip("?")


def fill_audio_urls(db, bundle: dict) -> int:
    """Điền `audio_url` (sửa tại chỗ) cho mục có file trong bucket của `db`. Trả số mục đã điền."""
    files = bucket_files(db)
    n = 0
    for e in bundle["lexicon"]:
        name = audio_file_name(e["lemma_key"])
        if name in files:
            e["audio_url"] = public_url(db, name)
            n += 1
    return n


def upload_bundle_audio(db, bundle: dict, key: str, region: str) -> tuple[list[str], list[str]]:
    """Tạo + upload mp3 cho mục chưa có file trong bucket. Trả (đã upload, đã có sẵn)."""
    files = bucket_files(db)
    uploaded, existing = [], []
    for e in bundle["lexicon"]:
        name = audio_file_name(e["lemma_key"])
        if name in files:
            existing.append(name)
            continue
        data = synthesize(e["canonical_form"], key, region)
        db.storage.from_(BUCKET).upload(name, data, {"content-type": "audio/mpeg", "upsert": "true"})
        files.add(name)
        uploaded.append(name)
    return uploaded, existing


def main() -> None:
    from supabase import create_client
    from pipeline.seed import local_env, remote_env

    ap = argparse.ArgumentParser(prog="pipeline.audio", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--local", action="store_true", help="Supabase local thay vì cloud")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    key, region = os.getenv("AZURE_SPEECH_KEY", ""), os.getenv("AZURE_SPEECH_REGION", "")
    if not key or not region:
        sys.exit("Thiếu AZURE_SPEECH_KEY / AZURE_SPEECH_REGION trong .env")
    env = local_env() if args.local else remote_env()
    db = create_client(env["url"], env["service"])
    bundle = json.loads((OUT / args.slug / "bundle.json").read_text("utf-8"))
    uploaded, existing = upload_bundle_audio(db, bundle, key, region)
    print(f"Audio {args.slug} → {env['url']}: upload {len(uploaded)}, đã có {len(existing)} "
          f"/ {len(bundle['lexicon'])} mục")
    for n in uploaded:
        print(f"  + {n}")


if __name__ == "__main__":
    main()
