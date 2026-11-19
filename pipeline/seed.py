"""BE-05 · Seed một ArticleBundle vào Supabase bằng service role (chỉ chạy trên máy cá nhân).

    py -m pipeline.seed --slug eating-well --local                  # Supabase local (npx supabase start)
    py -m pipeline.seed --slug eating-well                          # project cloud, key trong .env
    py -m pipeline.seed --bundle fixtures/article_eating_well.json --local

Luật:
- Bundle phải qua `ArticleBundle.model_validate` trước khi ghi.
- Id chuỗi → uuid5 ổn định, nên seed lại bao nhiêu lần cũng không tạo bản ghi trùng:
  article theo `article.id`; section theo (article, `order_index`) vì pipeline chạy lại có thể đổi id section;
  occurrence/quiz theo (article, id); lexicon theo `lemma_key` (dùng chung toàn hệ thống).
- Seed lại: upsert theo id, chỉ xóa dòng thừa (section có `order_index` vượt số section mới, occurrence/quiz
  không còn trong bundle). Không xóa-rồi-chèn, để `user_quiz_results.quiz_item_id` không bị set null oan.
- Mục từ đã có trong DB và **đang được bài khác dùng**: không ghi đè (giữ bản đã duyệt trước), chỉ cảnh báo;
  muốn ghi đè thì thêm `--update-shared-lexicon`.
- Các lời gọi REST không nằm trong một transaction; lỗi giữa chừng thì chạy lại (idempotent) là về đúng.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import uuid
from dataclasses import dataclass, field

from dotenv import load_dotenv
from supabase import Client, create_client

from pipeline.audio import fill_audio_urls
from pipeline.reference.contract_models import ArticleBundle

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Namespace cố định cho uuid5. KHÔNG đổi: đổi là mọi id trong DB đổi theo.
ID_NAMESPACE = uuid.UUID("6f1c2d3e-8a4b-5c6d-9e0f-a1b2c3d4e5f6")
LEXICON_FIELDS = ("canonical_form", "lemma_key", "type", "pos", "cefr_level",
                  "ipa", "definition_en", "extra_example", "audio_url")


def stable_uuid(kind: str, key: str) -> str:
    return str(uuid.uuid5(ID_NAMESPACE, f"{kind}:{key}"))


# ---------------------------------------------------------------- kết nối
def local_env() -> dict[str, str]:
    out = subprocess.run("npx --yes supabase status -o env", shell=True, cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    env = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"')
    return {"url": env["API_URL"], "anon": env["ANON_KEY"], "service": env["SERVICE_ROLE_KEY"]}


def remote_env() -> dict[str, str]:
    load_dotenv(ROOT / ".env")
    vals = {"url": os.getenv("SUPABASE_URL", ""), "anon": os.getenv("SUPABASE_ANON_KEY", ""),
            "service": os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")}
    if not all(vals.values()):
        sys.exit("Thiếu SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY trong .env (hoặc dùng --local)")
    return vals


# ---------------------------------------------------------------- bundle → dòng DB (thuần, test được)
@dataclass
class SeedRows:
    article_id: str
    source: dict
    article: dict
    sections: list[dict]
    lexicon: list[dict]
    occurrences: list[dict]
    quiz: list[dict]
    back: dict[str, str] = field(default_factory=dict)  # uuid → id chuỗi gốc


def plan_rows(b: dict, source_type: str) -> SeedRows:
    a = b["article"]
    aid = a["id"]
    back: dict[str, str] = {}

    def u(kind: str, key: str, original: str) -> str:
        v = stable_uuid(kind, key)
        back[v] = original
        return v

    src_id = stable_uuid("source", a["source"]["name"])
    art_id = u("article", aid, aid)
    sec = {s["id"]: u("section", f"{aid}#{s['order_index']}", s["id"]) for s in b["sections"]}
    lex = {e["id"]: u("lexicon", e["lemma_key"], e["id"]) for e in b["lexicon"]}

    return SeedRows(
        article_id=art_id,
        source={"id": src_id, "name": a["source"]["name"], "type": source_type,
                "is_graded": a["source"]["is_graded"]},
        article={"id": art_id, "title": a["title"], "source_id": src_id, "category": a["category"],
                 "cefr_level": a["cefr_level"], "word_count": a["word_count"]},
        sections=[{
            "id": sec[s["id"]], "article_id": art_id, "order_index": s["order_index"],
            "title": s["title"], "icon_hint": s["icon_hint"], "tokens": s["tokens"],
            "key_idea": s["key_idea"]["text"], "key_idea_tokens": s["key_idea"]["tokens"],
            "check_data": s.get("check"),
        } for s in b["sections"]],
        lexicon=[{"id": lex[e["id"]], **{k: e.get(k) for k in LEXICON_FIELDS}} for e in b["lexicon"]],
        occurrences=[{
            "id": u("occurrence", f"{aid}#{o['id']}", o["id"]),
            "lexicon_entry_id": lex[o["lexicon_entry_id"]], "article_id": art_id,
            "section_id": sec[o["section_id"]], "token_start": o["token_start"],
            "token_end": o["token_end"], "vi": o["vi"], "example_sentence": o["example_sentence"],
            "cloze": o["cloze"],
        } for o in b["occurrences"]],
        quiz=[{
            "id": u("quiz", f"{aid}#{q['id']}", q["id"]), "article_id": art_id, "order_index": k,
            "type": q["type"], "question": q["question"], "options": q["options"],
            "answer_index": q["answer_index"], "explanation": q["explanation"],
        } for k, q in enumerate(b["quiz"])],
        back=back,
    )


# ---------------------------------------------------------------- ghi DB
@dataclass
class SeedResult:
    rows: SeedRows
    processing_order: int
    lexicon_written: int
    lexicon_kept: list[str]  # lemma_key đang được bài khác dùng, giữ bản trong DB


def _delete_stale(db: Client, table: str, article_id: str, keep_ids: list[str]) -> None:
    q = db.table(table).delete().eq("article_id", article_id)
    if keep_ids:
        q = q.not_.in_("id", keep_ids)
    q.execute()


def seed_bundle(db: Client, bundle: dict, source_type: str = "infographic",
                processing_order: int | None = None, update_shared_lexicon: bool = False) -> SeedResult:
    ArticleBundle.model_validate(bundle)
    fill_audio_urls(db, bundle)  # BE-06d: URL của đúng nơi đang seed (sửa bundle tại chỗ)
    r = plan_rows(bundle, source_type)

    if processing_order is None:
        cur = db.table("articles").select("processing_order").eq("id", r.article_id).execute().data
        if cur:
            processing_order = cur[0]["processing_order"]
        else:
            top = db.table("articles").select("processing_order").order("processing_order", desc=True) \
                .limit(1).execute().data
            processing_order = (top[0]["processing_order"] + 1) if top else 1

    db.table("sources").upsert(r.source).execute()
    db.table("articles").upsert({**r.article, "processing_order": processing_order}).execute()

    db.table("sections").delete().eq("article_id", r.article_id) \
        .gte("order_index", len(r.sections)).execute()
    db.table("sections").upsert(r.sections).execute()

    # Lexicon dùng chung: mục đã có, nội dung khác, và đang được bài khác dùng → giữ nguyên.
    keys = [e["lemma_key"] for e in r.lexicon]
    existing = {e["lemma_key"]: e for e in
                db.table("lexicon_entries").select("*").in_("lemma_key", keys).execute().data} if keys else {}
    kept: list[str] = []
    to_write: list[dict] = []
    for e in r.lexicon:
        old = existing.get(e["lemma_key"])
        # Chỉ thêm audio (null → URL) không tính là khác nội dung: vẫn ghi.
        differs = any(old.get(k) != e.get(k) for k in LEXICON_FIELDS if k != "audio_url") if old else False
        if old and (old.get("audio_url") and e.get("audio_url") != old.get("audio_url")):
            differs = True
        if old and differs and not update_shared_lexicon:
            others = db.table("vocabulary_occurrences").select("id").eq("lexicon_entry_id", old["id"]) \
                .neq("article_id", r.article_id).limit(1).execute().data
            if others:
                kept.append(e["lemma_key"])
                continue
        to_write.append(e)
    if to_write:
        db.table("lexicon_entries").upsert(to_write, on_conflict="lemma_key").execute()

    _delete_stale(db, "vocabulary_occurrences", r.article_id, [o["id"] for o in r.occurrences])
    if r.occurrences:
        db.table("vocabulary_occurrences").upsert(r.occurrences).execute()
    _delete_stale(db, "quiz_items", r.article_id, [q["id"] for q in r.quiz])
    if r.quiz:
        db.table("quiz_items").upsert(r.quiz).execute()

    return SeedResult(rows=r, processing_order=processing_order,
                      lexicon_written=len(to_write), lexicon_kept=kept)


def main() -> None:
    ap = argparse.ArgumentParser(prog="pipeline.seed", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--slug", help="đọc pipeline/out/<slug>/bundle.json")
    src.add_argument("--bundle", type=pathlib.Path, help="đường dẫn bundle.json bất kỳ")
    ap.add_argument("--local", action="store_true", help="Supabase local (npx supabase status)")
    ap.add_argument("--source-type", default="infographic", choices=["infographic", "text_article", "pdf"])
    ap.add_argument("--processing-order", type=int, default=None,
                    help="thứ tự trên Home; mặc định giữ giá trị cũ, bài mới thì max + 1")
    ap.add_argument("--update-shared-lexicon", action="store_true",
                    help="ghi đè cả mục từ đang được bài khác dùng")
    args = ap.parse_args()

    path = args.bundle or ROOT / "pipeline" / "out" / args.slug / "bundle.json"
    bundle = json.loads(path.read_text(encoding="utf-8"))
    env = local_env() if args.local else remote_env()
    print(f"Seed {path} → {env['url']}")
    res = seed_bundle(create_client(env["url"], env["service"]), bundle, args.source_type,
                      args.processing_order, args.update_shared_lexicon)
    r = res.rows
    print(f"OK  {bundle['article']['id']} → {r.article_id} (processing_order {res.processing_order}): "
          f"{len(r.sections)} section, {len(r.occurrences)} occurrence, {len(r.quiz)} quiz, "
          f"lexicon ghi {res.lexicon_written}/{len(r.lexicon)}")
    if res.lexicon_kept:
        print("CẢNH BÁO  mục từ đang được bài khác dùng, giữ bản trong DB (thêm --update-shared-lexicon để ghi đè): "
              + ", ".join(res.lexicon_kept))


if __name__ == "__main__":
    main()
