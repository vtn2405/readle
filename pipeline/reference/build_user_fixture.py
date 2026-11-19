"""
Sinh fixture cho bài người dùng tự tải (ADR-021, bản nháp Contract 1.5 — CHƯA ÁP DỤNG):
  fixtures/user_article_sample.json   UserArticleRecord (bundle 1.5 nháp + metadata Hive)
  fixtures/lookup_samples.json        ví dụ request/response của Edge Function `lookup`

Không đụng fixture chính `fixtures/article_eating_well.json` và CONTRACT_VERSION.

`dict_entries` (BE-15) chưa có, nên script giả lập bằng spaCy chạy trên từng dạng từ
đứng riêng (không ngữ cảnh) — đúng cách BE-15 sẽ sinh bảng. Nghĩa trong lookup_samples
viết tay.

Chạy: python pipeline/reference/build_user_fixture.py
"""
import json
import pathlib
import sys
from functools import lru_cache

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(ROOT))
from tokenize_and_match import get_nlp, FN_POS  # noqa: E402
from user_article import (  # noqa: E402
    UserArticleRecord, build_bundle, edited_ratio, lookup_key, sentence_for, suggest_title,
)
from pipeline.ipa import word_ipa  # noqa: E402

ARTICLE_ID = "local_3f6c2a1e-8b4d-4c7a-9e21-5d0b7a6c4f18"

# Bài viết mẫu (tự viết cho fixture). Cố ý có: rút gọn (don't, it's), sở hữu cách cong
# (children’s), gạch nối (well-known), số thập phân (3.5), năm (2025), gạch dài, nháy cong,
# 1 đoạn ngắn để thấy luật gộp đoạn, dòng tiêu đề ở đầu để thấy gợi ý tiêu đề.
RAW = """Why Small Libraries Still Matter

In many towns, the small public library is still one of the busiest places on a weekday \
afternoon. Parents bring young children to story time, students come to study after school, \
and older people use the computers to read the news or call their families. The building is \
often old, but it's warm, quiet and free.

Libraries don't only lend books. Many of them now lend tools, board games and even fishing rods. \
A well-known library in a small town lent more than 3.5 thousand items that were not books in 2025.

Librarians say the most important thing is trust. “People come here when they don't know where \
else to go,” one librarian explained. She helps visitors fill in forms, find jobs and learn new \
skills — and she never asks them to pay.

The children’s corner is the loudest part of the building, and nobody minds.

Some cities want to close small libraries to save money. But for many families, losing the \
library would mean losing a safe place to read, learn and meet their neighbours."""

# Chữ OCR giả lập cho edited_ratio (2 lỗi người dùng đã sửa: "rn" → "m", mất dấu phẩy).
OCR_RAW = RAW.replace("famil", "farnil", 1).replace("warm, quiet", "warm quiet", 1)


CONTRACTIONS = {"don't", "doesn't", "didn't", "can't", "won't", "isn't", "aren't", "it's",
                "that's", "there's", "i'm", "you're", "they're", "we're", "i've", "i'll"}


@lru_cache(maxsize=None)
def fake_dict(form: str):
    """Giả lập 1 dòng dict_entries: lemma + is_fn bằng spaCy trên dạng từ đứng riêng,
    IPA từ CMUdict (pipeline/ipa.py) theo lemma rồi theo dạng từ."""
    if form in CONTRACTIONS:  # BE-15 thêm tay danh sách rút gọn ngắn
        return {"lemma": form, "ipa": None, "is_fn": True}
    if "'" in form:  # dạng khác có ' (sở hữu cách...): không có trong bảng → app tra lại bỏ 's
        return None
    doc = get_nlp()(form)
    if len(doc) != 1:
        return None
    t = doc[0]
    return {"lemma": t.lemma_.lower(), "ipa": word_ipa(t.lemma_.lower()) or word_ipa(form),
            "is_fn": t.pos_ in FN_POS}


def main() -> None:
    title = suggest_title(RAW)
    body = RAW.split("\n", 2)[2]  # người dùng bỏ dòng tiêu đề khỏi thân bài ở màn soát chữ
    bundle = build_bundle(ARTICLE_ID, title, body, dict_get=fake_dict)
    record = {
        "bundle": bundle,
        "created_at": "2026-11-17T09:30:00Z",
        "input_source": "gallery",
        "ocr_engine": "mlkit",
        "edited_ratio": edited_ratio(OCR_RAW.split("\n", 2)[2], body),
        "dict_filled": True,
    }
    UserArticleRecord.model_validate(record)

    # Ví dụ lookup: "lend" (mới tra), "fill" trong "fill in forms" (trúng cache server),
    # "trust" (chạm trần người dùng). Kèm event lookup_requested app phải phát cho từng ca.
    samples = []
    wants = [("lend", "cho mượn", "VERB", "fresh"), ("fill", "điền (vào mẫu đơn)", "VERB", "cached"),
             ("trust", "sự tin tưởng", "NOUN", "capped_user")]
    for word, vi, pos, case in wants:
        for s in bundle["sections"]:
            hit = next((t for t in s["tokens"] if t["text"] == word), None)
            if hit:
                sentence, occ = sentence_for(s["tokens"], hit["i"])
                key = lookup_key(sentence, word, occ)
                req = {"sentence": sentence, "word": word, "lemma": hit["lemma"], "occurrence": occ}
                if case == "capped_user":
                    resp = {"status": 429, "body": {"error": "capped_user"}}
                else:
                    resp = {"status": 200, "body": {"vi": vi, "lemma": hit["lemma"], "pos": pos,
                                                    "cached": case == "cached", "lookup_key": key}}
                event = {"hit": "server" if case == "cached" else "miss",
                         "result": "capped_user" if case == "capped_user" else "ok"}
                samples.append({"case": case, "section_id": s["id"], "token_i": hit["i"],
                                "request": req, "response": resp,
                                "event": {"event_type": "lookup_requested", "payload": event}})
                break
        else:
            raise SystemExit(f"Không thấy '{word}' trong bài mẫu")

    out = ROOT / "fixtures"
    (out / "user_article_sample.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "lookup_samples.json").write_text(
        json.dumps({"draft_contract_version": "1.5", "samples": samples}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("OK ->", out / "user_article_sample.json", "| cards:",
          [sum(t["is_word"] for t in s["tokens"]) for s in bundle["sections"]],
          "| words:", bundle["article"]["word_count"], "| edited_ratio:", record["edited_ratio"])


if __name__ == "__main__":
    main()
