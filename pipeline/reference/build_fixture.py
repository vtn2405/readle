"""
Sinh fixtures/article_eating_well.json theo contract v1 để Antigravity dựng UI
trước khi có Supabase. Nghĩa tiếng Việt ở đây viết tay; pipeline thật sẽ do LLM sinh.

Chạy: python pipeline/reference/build_fixture.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(ROOT))
from tokenize_and_match import tokenize, locate, lemma_key, sentence_cloze  # noqa: E402
from contract_models import ArticleBundle, CONTRACT_VERSION  # noqa: E402
from pipeline.ipa import add_token_ipa, phrase_ipa  # noqa: E402


def with_vi(text: str, meanings: list[str]) -> list[dict]:
    toks = add_token_ipa(tokenize(text))
    words = [t for t in toks if t["is_word"]]
    assert len(words) == len(meanings), (len(words), len(meanings), [w["text"] for w in words])
    for t, vi in zip(words, meanings):
        t["vi"] = vi
    return toks


S1 = ("Eating well plays a vital role in good health and disease prevention. "
      "Eating lots of fruits and vegetables is one of the easiest and most delicious ways to eat healthy. "
      "Choosing food that is close to its natural form and not overly processed is best practice. "
      "Restaurant and takeout meals tend to have more added salt, sugar and fat, so eat out in moderation.")
S1_VI = ["việc ăn uống", "tốt, lành mạnh", "đóng (vai trò)", "một", "quan trọng, thiết yếu", "vai trò",
         "trong", "tốt", "sức khỏe", "và", "bệnh tật", "sự phòng ngừa",
         "ăn", "nhiều", "của", "trái cây", "và", "rau củ", "là", "một", "trong số", "(mạo từ xác định)",
         "dễ nhất", "và", "nhất", "ngon", "cách", "để", "ăn", "lành mạnh",
         "việc chọn", "thức ăn", "mà", "thì", "gần", "với", "của nó", "tự nhiên", "dạng, hình thái", "và",
         "không", "quá mức", "được chế biến", "là", "tốt nhất", "cách làm, thói quen",
         "nhà hàng", "và", "mang đi", "bữa ăn", "có xu hướng", "(đi với 'tend')", "có", "nhiều hơn",
         "được thêm vào", "muối", "đường", "và", "chất béo", "vì vậy", "ăn", "ra ngoài", "trong",
         "sự điều độ"]
K1 = "Healthy food helps your body, so eat restaurant food less often."
K1_VI = ["lành mạnh", "thức ăn", "giúp", "của bạn", "cơ thể", "vì vậy", "ăn", "nhà hàng", "đồ ăn",
         "ít hơn", "thường xuyên"]

S2 = ("Broccoli and dark green leafy vegetables, like spinach and kale, are excellent sources of fiber, "
      "folate and carotenoids. These vegetables also contain vitamins C and K and minerals iron and calcium.")
S2_VI = ["bông cải xanh", "và", "sẫm, đậm", "xanh lá", "nhiều lá", "rau", "như", "rau chân vịt", "và",
         "cải xoăn", "là", "tuyệt vời, rất tốt", "nguồn", "của", "chất xơ", "folate (một loại vitamin B)",
         "và", "carotenoid (chất tạo màu vàng/cam)", "những ... này", "rau củ", "cũng", "chứa", "vitamin",
         "C", "và", "K", "và", "khoáng chất", "sắt", "và", "canxi"]
K2 = "Dark green vegetables give your body many good things."
K2_VI = ["sẫm", "xanh lá", "rau", "mang lại", "của bạn", "cơ thể", "nhiều", "tốt", "thứ"]

sections = [
    {"id": "sec_ew_1", "order_index": 0, "title": "Eating well", "icon_hint": "salad",
     "tokens": with_vi(S1, S1_VI), "key_idea": {"text": K1, "tokens": with_vi(K1, K1_VI)},
     # Fixture cố ý có Quick Check ở section ngắn để UI có dữ liệu dựng màn; pipeline thật chỉ đặt ở section dài.
     "check": {"question": "What kind of food does the text say is best to choose?",
               "options": ["Food close to its natural form", "Food with more added salt", "Takeout meals"],
               "answer_index": 0,
               "explanation": "Đoạn văn nói chọn thức ăn gần với dạng tự nhiên, không chế biến quá mức là tốt nhất."}},
    {"id": "sec_ew_2", "order_index": 1, "title": "Dark green veggies", "icon_hint": "broccoli",
     "tokens": with_vi(S2, S2_VI), "key_idea": {"text": K2, "tokens": with_vi(K2, K2_VI)}, "check": None},
]

LEX = [
    # id, canonical, type, pos, cefr, ipa, def, extra, section_id, vi
    ("lex_play_vital_role_in", "play a vital role in", "collocation", "Verb phrase", "B1",
     "/pleɪ ə ˈvaɪtl roʊl ɪn/", "to be very important in making something happen",
     "Sleep plays a vital role in memory.", "sec_ew_1", "đóng vai trò quan trọng trong"),
    # Cụm chồng lấn cố ý, để test luật "2 cụm chồng nhau" ở mục 3.6.
    ("lex_vital_role", "vital role", "collocation", "Noun phrase", "B1",
     "/ˈvaɪtl roʊl/", "a very important part or function",
     "Teachers have a vital role in our lives.", "sec_ew_1", "vai trò thiết yếu"),
    ("lex_tend_to", "tend to", "collocation", "Verb phrase", "B1",
     "/tɛnd tu/", "to usually do or be something",
     "Children tend to sleep more in winter.", "sec_ew_1", "có xu hướng"),
    ("lex_in_moderation", "in moderation", "collocation", "Adverb phrase", "B1",
     "/ɪn ˌmɑdəˈreɪʃn/", "in reasonable amounts, not too much",
     "Coffee is fine in moderation.", "sec_ew_1", "có chừng mực, vừa phải"),
    ("lex_excellent_source_of", "excellent source of", "collocation", "Noun phrase", "B1",
     "/ˈɛksələnt sɔrs əv/", "something that gives you a lot of a useful thing",
     "Eggs are an excellent source of protein.", "sec_ew_2", "nguồn cung cấp dồi dào"),
    ("lex_carotenoid", "carotenoid", "single_word", "Noun", "B2",
     "/kəˈrɑtənɔɪd/", "a natural substance that gives yellow, orange or red colour to plants",
     "Carrots are rich in carotenoids.", "sec_ew_2", "carotenoid (hợp chất tạo màu vàng/cam trong rau quả)"),
]

sec_by_id = {s["id"]: s for s in sections}
lexicon, occurrences = [], []
for k, (lid, form, typ, pos, cefr, ipa, d, ex, sid, vi) in enumerate(LEX):
    toks = sec_by_id[sid]["tokens"]
    spans = locate(toks, form)
    assert spans, f"Không định vị được '{form}' trong {sid}"
    start, end = spans[0]
    cloze = sentence_cloze(toks, start, end)
    lexicon.append({"id": lid, "canonical_form": form, "lemma_key": lemma_key(form), "type": typ,
                    # IPA từ CMUdict (ADR-010); không tra được thì giữ bản viết tay.
                    "pos": pos, "cefr_level": cefr, "ipa": phrase_ipa(form) or ipa, "definition_en": d,
                    "extra_example": ex, "audio_url": None})
    occurrences.append({"id": f"occ_ew_{k + 1}", "lexicon_entry_id": lid, "section_id": sid,
                        "token_start": start, "token_end": end, "vi": vi,
                        "example_sentence": (cloze["text_before"] + cloze["answer"] + cloze["text_after"]).strip(),
                        "cloze": cloze})

bundle = {
    "contract_version": CONTRACT_VERSION,
    "article": {"id": "art_eating_well", "title": "Eating Well", "category": "Health & Nutrition",
                "cefr_level": "A2", "source": {"name": "World of Wonder", "is_graded": False},
                "word_count": sum(t["is_word"] for s in sections for t in s["tokens"]),
                "section_count": len(sections)},
    "sections": sections,
    "lexicon": lexicon,
    "occurrences": occurrences,
    "quiz": [
        {"id": "q_ew_1", "type": "true_false", "question": "Restaurant meals often have more added salt and sugar.",
         "options": ["True", "False"], "answer_index": 0,
         "explanation": "Đoạn 1 nói đồ ăn nhà hàng và mang đi thường nhiều muối, đường và chất béo hơn."},
        {"id": "q_ew_2", "type": "multiple_choice", "question": "What does the text call 'best practice'?",
         "options": ["Eating only fruit", "Choosing food that is not overly processed", "Eating out every day"],
         "answer_index": 1, "explanation": "Chọn thức ăn gần dạng tự nhiên, không chế biến quá mức."},
        {"id": "q_ew_3", "type": "true_false", "question": "Broccoli and kale have no vitamins.",
         "options": ["True", "False"], "answer_index": 1,
         "explanation": "Đoạn 2 nói các loại rau này chứa vitamin C và K."},
    ],
}

ArticleBundle.model_validate(bundle)  # ném lỗi nếu vi phạm contract
out = ROOT / "fixtures" / "article_eating_well.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
print("OK ->", out, "| occurrences:", [(o["lexicon_entry_id"], o["token_start"], o["token_end"]) for o in occurrences])
