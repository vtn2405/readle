"""BE-04/BE-05 · Kiểm tra đầu-cuối Supabase theo contract.

    py -m pipeline.supabase_check --local [--bundle fixtures/article_eating_well.json]
    py -m pipeline.supabase_check --bundle pipeline/out/<slug>/bundle.json   # cloud: --bundle bắt buộc

1. Seed bundle bằng `pipeline.seed.seed_bundle` 2 lần → số dòng mọi bảng nội dung không đổi ở lần 2.
2. Gọi `rpc('get_article_bundle')` bằng anon key → `ArticleBundle.model_validate`, rồi so từng
   trường với bundle gốc (sau khi đổi id ngược lại).
3. Hai người dùng ẩn danh thật (`sign_in_anonymously`): A lưu từ, B không thấy và không sửa được.

`--local` lấy URL/key từ `npx supabase status -o env` (key demo của Supabase local, không phải bí mật).
Không có `--local` thì đọc SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY từ `.env`.
"""
from __future__ import annotations

import argparse
import json
import pathlib

from supabase import create_client

from pipeline.reference.contract_models import CONTRACT_VERSION, ArticleBundle
from pipeline.seed import local_env, remote_env, seed_bundle, stable_uuid  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "fixtures" / "article_eating_well.json"
CONTENT_TABLES = ("sources", "articles", "sections", "lexicon_entries", "vocabulary_occurrences", "quiz_items")


def restore_ids(x, back: dict[str, str]):
    if isinstance(x, dict):
        return {k: restore_ids(v, back) for k, v in x.items()}
    if isinstance(x, list):
        return [restore_ids(v, back) for v in x]
    return back.get(x, x) if isinstance(x, str) else x


def normalize(b: dict) -> dict:
    """Bỏ phần không so được: version, thứ tự lexicon/occurrences (contract không quy định)."""
    b = json.loads(json.dumps(b))
    b.pop("contract_version", None)
    b["lexicon"] = sorted(b["lexicon"], key=lambda e: e["id"])
    b["occurrences"] = sorted(b["occurrences"], key=lambda o: o["id"])
    return b


def check_bundle(env: dict, bundle_path: pathlib.Path, source_type: str) -> None:
    src = json.loads(bundle_path.read_text(encoding="utf-8"))
    ArticleBundle.model_validate(src)
    service = create_client(env["url"], env["service"])

    def counts() -> dict[str, int]:
        return {tb: service.table(tb).select("id", count="exact").limit(1).execute().count for tb in CONTENT_TABLES}

    res = seed_bundle(service, src, source_type)
    art_id, back = res.rows.article_id, res.rows.back
    before = counts()
    seed_bundle(service, src, source_type)  # lần 2: phải không lỗi, không thêm dòng nào
    after = counts()
    assert before == after, f"seed 2 lần làm đổi số dòng: {before} → {after}"
    n = service.table("vocabulary_occurrences").select("id", count="exact").eq("article_id", art_id).execute().count
    assert n == len(src["occurrences"]), f"occurrence của bài: {n} != {len(src['occurrences'])}"

    anon = create_client(env["url"], env["anon"])
    got = anon.rpc("get_article_bundle", {"p_article_id": art_id}).execute().data
    ArticleBundle.model_validate(got)
    assert got["contract_version"] == CONTRACT_VERSION, got["contract_version"]
    diff = [k for k in ("article", "sections", "lexicon", "occurrences", "quiz")
            if normalize(restore_ids(got, back))[k] != normalize(src)[k]]
    assert not diff, f"bundle từ RPC khác bundle gốc ở: {diff}"
    cards = anon.table("article_cards").select("*").eq("id", art_id).execute().data
    assert len(cards) == 1 and cards[0]["section_count"] == len(src["sections"]), cards
    print(f"OK  get_article_bundle({src['article']['id']} → {art_id}): {len(got['sections'])} section, "
          f"{len(got['lexicon'])} mục từ, {len(got['occurrences'])} occurrence; khớp bundle gốc; seed lại không trùng")
    return art_id


def check_rls(env: dict, art_id: str) -> list[str]:
    a = create_client(env["url"], env["anon"])
    b = create_client(env["url"], env["anon"])
    ua = a.auth.sign_in_anonymously().user
    ub = b.auth.sign_in_anonymously().user
    assert ua.is_anonymous and ub.is_anonymous and ua.id != ub.id

    a.table("user_saved_words").upsert({"user_id": ua.id, "lemma_key": "tend to", "display_text": "tend to",
                                        "vi": "có xu hướng", "example_sentence": "x", "cloze": {},
                                        "source_article_id": art_id},
                                       on_conflict="user_id,lemma_key").execute()
    a.table("reading_history").upsert({"user_id": ua.id, "article_id": art_id, "progress_percent": 50},
                                      on_conflict="user_id,article_id").execute()
    assert len(a.table("user_saved_words").select("*").execute().data) == 1
    assert b.table("user_saved_words").select("*").execute().data == []
    assert b.table("reading_history").select("*").execute().data == []
    assert b.table("user_saved_words").update({"vi": "hacked"}).eq("user_id", ua.id).execute().data == []
    assert a.table("user_saved_words").select("vi").execute().data[0]["vi"] == "có xu hướng"
    a.table("usage_events").insert({"event_type": "audio_played", "client_ts": "2026-11-13T00:00:00Z",
                                    "payload": {"source": "item", "speed": 0.6}}, returning="minimal").execute()
    try:
        a.table("usage_events").select("*").execute()
        raise AssertionError("đọc được usage_events qua API")
    except AssertionError:
        raise
    except Exception:
        pass  # permission denied: đúng
    print("OK  RLS: 2 người dùng ẩn danh thật; B không thấy/sửa được dữ liệu của A; usage_events chỉ ghi")
    return [ua.id, ub.id]


def cleanup_users(env: dict, user_ids: list[str]) -> None:
    """Xóa người dùng thử: bảng người dùng tự xóa theo (FK auth.users on delete cascade);
    usage_events không có FK nên xóa riêng, để không lẫn vào số liệu đo (BE-08)."""
    svc = create_client(env["url"], env["service"])
    svc.table("usage_events").delete().in_("user_id", user_ids).execute()
    for uid in user_ids:
        svc.auth.admin.delete_user(uid)
    print(f"OK  dọn {len(user_ids)} người dùng thử và event của họ")


def resolve_bundle(bundle: pathlib.Path | None, local: bool) -> pathlib.Path:
    """Fixture dùng chung id `art_eating_well` với bài thật, nên seed fixture lên cloud sẽ ghi đè
    bài Eating Well thật (9 section → 2; xảy ra ở run #48). Trên cloud bắt buộc chỉ rõ --bundle."""
    if bundle is not None:
        return bundle
    if local:
        return DEFAULT_BUNDLE
    raise SystemExit("Trên cloud phải chỉ rõ --bundle (vd pipeline/out/eating-well/bundle.json): "
                     "fixture trùng id với bài thật và sẽ ghi đè nội dung đang chạy.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local", action="store_true", help="dùng Supabase local (npx supabase status)")
    ap.add_argument("--bundle", type=pathlib.Path, default=None,
                    help="bundle để seed + so; mặc định fixture, nhưng BẮT BUỘC khi chạy trên cloud")
    ap.add_argument("--source-type", default="infographic", choices=["infographic", "text_article", "pdf"])
    ap.add_argument("--keep-test-users", action="store_true", help="không xóa 2 người dùng ẩn danh thử")
    args = ap.parse_args()
    args.bundle = resolve_bundle(args.bundle, args.local)
    env = local_env() if args.local else remote_env()
    art_id = check_bundle(env, args.bundle, args.source_type)
    users = check_rls(env, art_id)
    if not args.keep_test_users:
        cleanup_users(env, users)


if __name__ == "__main__":
    main()
