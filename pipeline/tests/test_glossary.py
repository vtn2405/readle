"""Quy ước glossary từ chức năng (BE-06e1): luôn ghi nghĩa, không ngoặc, chỉ mạo từ dùng nhãn."""
import pytest

from pipeline.glossary import ARTICLE_A, ARTICLE_THE, normalize_fn_meaning, normalize_glossary


@pytest.mark.parametrize("text,vi,new,status", [
    ("and", "(và)", "và", "cleaned"),
    ("and", "và (liên từ)", "và", "cleaned"),
    ("and", "(liên từ 'và')", "và", "cleaned"),
    ("at", "(giới từ: ở)", "ở", "cleaned"),
    ("been", "(bị/được - phân từ)", "bị/được", "cleaned"),
    ("by", "(bởi/ theo)", "bởi/theo", "cleaned"),
    ("they", "chúng (robot)", "chúng", "cleaned"),       # ngoặc giải thích bị bỏ
    ("and", "(liên từ)", "và", "default"),               # chỉ có nhãn → nghĩa mặc định
    ("is", "(động từ to be)", "là", "default"),
    ("'s", "(sở hữu)", "của", "default"),
    ("do", "(trợ động từ)", "(trợ động từ)", "missing"),  # không đoán → báo người duyệt
    ("up", "(phần của 'made up')", "(phần của 'made up')", "missing"),
    # BE-06h: ghi chú của LLM quyết định nghĩa mặc định
    ("to", "(dấu nguyên mẫu)", "để", "default"),
    ("to", "(đặt trước động từ)", "để", "default"),
    ("to", "(giới từ)", "đến", "default"),
    ("be", "(động từ bị động)", "được", "default"),
    ("was", "(trợ động từ bị động)", "được", "default"),
    ("be", "(động từ trợ từ)", "là", "default"),
    ("is", "(động từ to be)", "là", "default"),
    ("of", "(dấu nguyên mẫu)", "(dấu nguyên mẫu)", "missing"),  # chỉ áp cho `to`
    ("to", "đến", "đến", "same"),                               # có nghĩa thật → giữ
    ("in", "trong", "trong", "same"),
])
def test_function_word_meanings(text, vi, new, status):
    assert normalize_fn_meaning(text, vi) == (new, status)


@pytest.mark.parametrize("text,vi,new", [
    ("the", "(mạo từ xác định)", ARTICLE_THE),
    ("the", "mạo từ 'the'", ARTICLE_THE),
    ("the", "(giới từ)", ARTICLE_THE),          # nhãn sai → nhãn chuẩn
    ("the", "càng", "càng"),                     # "the more … the better": nghĩa thật được giữ
    ("a", "một (mạo từ không xác định)", "một"),
    ("a", "Một", "một"),
    ("a", "(mạo từ)", ARTICLE_A),
    ("an", "(mạo từ không xác định)", ARTICLE_A),
])
def test_articles_may_keep_label(text, vi, new):
    assert normalize_fn_meaning(text, vi)[0] == new


def test_no_parentheses_left_except_articles_and_missing():
    cases = [("of", "(của)"), ("or", "(liên từ) hoặc"), ("these", "những (này)"), ("with", "(với)")]
    for text, vi in cases:
        new, _ = normalize_fn_meaning(text, vi)
        assert "(" not in new and ")" not in new


def test_normalize_glossary_only_touches_function_words_and_reports():
    tokens = [
        {"i": 0, "text": "plays", "is_fn": False},
        {"i": 1, "text": "and", "is_fn": True},
        {"i": 2, "text": "that", "is_fn": True},
        {"i": 3, "text": "of", "is_fn": True},
    ]
    meanings = {0: "đóng (vai trò)", 1: "(và)", 2: "(liên từ)", 3: "(giới từ)"}
    report = normalize_glossary(tokens, meanings)
    assert meanings == {0: "đóng (vai trò)", 1: "và", 2: "(liên từ)", 3: "của"}
    assert len(report["cleaned"]) == 1 and len(report["default"]) == 1
    assert report["missing"] == ['that: "(liên từ)"']


# ── BE-06i: từ nội dung + `be` theo ngữ cảnh ──
from pipeline.glossary import normalize_content_meaning  # noqa: E402
from pipeline.reference.tokenize_and_match import tokenize  # noqa: E402


@pytest.mark.parametrize("text,vi,new,status", [
    ("eel", "eel (lươn)", "lươn", "cleaned"),             # chép lại chữ Anh rồi mới nghĩa
    ("Curry", "Curry (cà ri)", "cà ri", "cleaned"),
    ("Italian", "Ý (tính từ)", "Ý", "cleaned"),            # nhãn ngữ pháp sau nghĩa
    ("century", "(thế kỷ)", "thế kỷ", "cleaned"),          # toàn bộ trong ngoặc
    ("are", "(động từ 'to be')", "là", "default"),         # chỉ nhãn → mặc định
    ("topped", "phủ (lên)", "phủ (lên)", "same"),          # ngoặc giải thích hợp lệ
    ("dough", "bột (làm vỏ)", "bột (làm vỏ)", "same"),
    ("paneer", "phô mai paneer", "phô mai paneer", "same"),
    ("mockba", "Mát-xcơ-va (tên pizza)", "Mát-xcơ-va (tên pizza)", "same"),
    ("60", "60 (năm)", "60 (năm)", "same"),                  # số: không bỏ chữ số
    ("4.29", "4.29 (số tiền)", "4.29 (số tiền)", "same"),
    ("cha", "cha (từ Quảng Đông)", "cha (từ Quảng Đông)", "same"),  # ngoặc là ghi chú
    ("pop", "pop (trong 'pop-up')", "pop (trong 'pop-up')", "same"),
    ("gallon", "gallon (đơn vị)", "gallon (đơn vị)", "same"),
    ("km", "km (kilômét)", "kilômét", "cleaned"),
    ("robots", "robot (số nhiều)", "robot", "cleaned"),
])
def test_content_word_meanings(text, vi, new, status):
    assert normalize_content_meaning(text, vi) == (new, status)


@pytest.mark.parametrize("sentence,word,llm,expected", [
    # Q-031 nhóm 3: token thuộc cụm → giữ ngoặc
    ("Limit the hot dogs you eat.", "hot", "món (phần của 'hot dog')", "món (phần của 'hot dog')"),
    ("It checks items off its bucket list.", "bucket", "bucket (danh sách mong muốn)",
     "bucket (danh sách mong muốn)"),
    ("Notre Dame used the flying buttress.", "flying", "flying (kiểu kiến trúc)",
     "flying (kiểu kiến trúc)"),
    # đứng riêng → vẫn bỏ chữ Anh lặp lại
    ("It included this droid on its list.", "droid", "droid (robot)", "robot"),
    ("Eat quality protein every morning.", "protein", "protein (chất đạm)", "chất đạm"),
])
def test_content_word_in_phrase(sentence, word, llm, expected):
    assert _norm(sentence, {word: llm})[word] == expected


def _norm(sentence: str, meanings_by_text: dict[str, str]) -> dict[str, str]:
    toks = tokenize(sentence, with_tags=True)
    mean = {t["i"]: meanings_by_text.get(t["text"], t["text"]) for t in toks if t["is_word"]}
    normalize_glossary(toks, mean)
    return {t["text"]: mean[t["i"]] for t in toks if t["is_word"]}


@pytest.mark.parametrize("sentence,word,llm,expected", [
    ("Calzone is stuffed with ricotta and mozzarella.", "is", "là", "được"),
    ("Pizza is often called tomato pie in the northeast.", "is", "là", "được"),
    ("Many large pizza chains were established in that time.", "were", "đã", "được"),
    ("The U.S. patent was issued in 1985.", "was", "(trợ động từ)", "được"),
    ("There are many kinds of pizza.", "are", "(động từ 'to be')", "có"),
    ("The peasants were hungry enough to eat it.", "were", "là", "là"),     # không bị động
    ("Pizza has been around for a long time.", "been", "đã", "đã"),       # không bị động
    ("Pizza is a popular food.", "is", "là", "là"),
    ("The windows were broken by the storm.", "were", "bị", "bị"),         # nghĩa thật giữ nguyên
    ("Recipes change because there's a constant evolution.", "'s", "(rút gọn của is)", "có"),
    ("That's a big question.", "'s", "rút gọn của is", "là"),
    # Q-031 nhóm 1: tiếp diễn → "đang"; `been` chỉ có nhãn → "đã" (không phải "là")
    ("If you're looking for a deal, book early.", "'re", "rút gọn 'are'", "đang"),
    ("Robot technology has been growing in leaps and bounds.", "been",
     "(phần của thì hoàn thành tiếp diễn)", "đang"),
    ("Engineers at Honda have been working on a robot.", "been", "(trợ động từ)", "đang"),
    ("Robots have been around since ancient times.", "been", "(phân từ)", "đã"),
    ("We are going to be hearing much more about harnesses.", "are", "là", "sẽ"),  # tương lai
    ("We are going to the market.", "are", "là", "đang"),  # "go to" + danh từ: vẫn tiếp diễn
    ("You're Jacob Aron, a senior reporter.", "'re", "rút gọn are", "là"),
    # Q-031 nhóm 2: be + V-ed chỉ trạng thái / hướng → giữ nghĩa LLM
    ("Paris is located on the Seine River.", "is", "là", "là"),
    ("The hydraulic turbine is based on the same principles.", "is", "là", "là"),
    ("Soil is made up of fine rock particles.", "is", "là", "là"),
    ("They are loaded with vitamins.", "are", "là", "là"),
    ("Generally they are all headed in the same direction.", "are", "là", "là"),
    ("Portuguese chicken rice is not meant to be cooked fast.", "is", "là", "là"),
    ("Early robots were made to copy animals.", "were", "đã", "được"),  # make + to: vẫn bị động
    # Q-031: bị động bất lợi → "bị"
    ("Although the building was destroyed in 1789, the day is celebrated.", "was", "đã", "bị"),
    ("It is limited by the information it has.", "is", "là", "bị"),
    ("The harness is mostly hidden from the user.", "is", "là", "bị"),
])
def test_be_by_context(sentence, word, llm, expected):
    assert _norm(sentence, {word: llm})[word] == expected


def test_context_rule_reported_in_review():
    toks = tokenize("Calzone is stuffed with ricotta.", with_tags=True)
    mean = {t["i"]: ("là" if t["text"] == "is" else t["text"]) for t in toks if t["is_word"]}
    report = normalize_glossary(toks, mean)
    assert any(r.startswith('is: "là" → "được"') for r in report["default"])


def test_collocation_word_ipas_split_by_word():
    from types import SimpleNamespace
    from pipeline.enrich import collocation_word_ipas
    items = [SimpleNamespace(canonical_form="preheat oven", type="collocation"),
             SimpleNamespace(canonical_form="speak one's mind", type="collocation"),
             SimpleNamespace(canonical_form="a variety of", type="collocation"),
             SimpleNamespace(canonical_form="crust", type="single_word")]
    details = {"preheat oven": {"ipa": "/ˌpriˈhit ˈʌvən/"},
               "speak one's mind": {"ipa": "/spik wʌnz maɪnd/"},
               "a variety of": {"ipa": "/ə vəˈraɪəti/"},           # lệch số đoạn → bỏ
               "crust": {"ipa": "/krʌst/"}}
    got = collocation_word_ipas(items, details)
    assert got["preheat"] == "/ˌpriˈhit/" and got["oven"] == "/ˈʌvən/"
    assert got["speak"] == "/spik/" and "one's" not in got
    assert "variety" not in got and "crust" not in got
