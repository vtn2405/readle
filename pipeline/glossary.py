"""
Chuẩn hóa nghĩa Việt của TỪ CHỨC NĂNG (token `is_fn`) theo quy ước người dùng chốt run #38:
luôn ghi nghĩa, không dùng ngoặc, chỉ mạo từ được dùng nhãn.

Làm bằng code (không đổi prompt bước section) để cache Key idea / nghĩa đã duyệt giữ nguyên.
- "(và)" → "và"; "và (liên từ)" → "và"; "(giới từ: ở)" → "ở"; "(liên từ 'và')" → "và";
  "(bị/được - phân từ)" → "bị/được".
- Chỉ còn nhãn ("(liên từ)", "(động từ to be)") → nghĩa mặc định theo chữ (`DEFAULTS`);
  không có mặc định → giữ nguyên và báo trong review.md để sửa bằng overrides.
- Ghi chú của LLM quyết định trước (BE-06h): `be`/`is`/`was`… "(động từ bị động)" → "được";
  `to` "(đặt trước động từ)" / "(dấu nguyên mẫu)" → "để" (không còn mọi `be` → "là", mọi `to` → "đến").
- Mạo từ: the → "(mạo từ xác định)"; a/an → "một" nếu LLM ghi "một", còn lại "(mạo từ không xác định)".
"""
from __future__ import annotations

import re

ARTICLE_THE = "(mạo từ xác định)"
ARTICLE_A = "(mạo từ không xác định)"

_LABEL_WORDS = (
    "mạo từ", "giới từ", "liên từ", "đại từ", "trợ động từ", "động từ", "phân từ",
    "quá khứ", "sở hữu", "so sánh", "tương lai", "to be", "quan hệ", "chỉ định",
    "nguyên mẫu", "cấu trúc", "giả chủ ngữ", "hoàn thành", "tiếp diễn", "số nhiều",
    "viết tắt", "trạng từ", "bắt đầu ví dụ", "vô nghĩa", "phần của", "tính từ", "danh từ",
    "rút gọn",
)

# Nghĩa mặc định khi LLM chỉ ghi nhãn. Khóa = chữ thường của token.
DEFAULTS = {
    "and": "và", "or": "hoặc", "but": "nhưng", "and/or": "và/hoặc",
    "of": "của", "in": "trong", "at": "ở", "on": "trên", "for": "cho", "by": "bởi",
    "with": "với", "from": "từ", "into": "vào", "about": "về", "upon": "trên",
    "it": "nó", "its": "của nó", "'s": "của", "his": "của ông ấy", "her": "của bà ấy",
    "their": "của họ", "your": "của bạn", "our": "của chúng ta", "they": "họ",
    "is": "là", "are": "là", "am": "là", "was": "là", "were": "là", "be": "là",
    "has": "đã", "have": "đã", "had": "đã",
    "will": "sẽ", "can": "có thể", "could": "có thể", "should": "nên", "must": "phải",
    "if": "nếu", "because": "bởi vì", "when": "khi",
    "to": "đến", "there": "có", "who": "người mà",
}
# Nhãn nói "từ này là một phần của cụm khác" / "dấu nguyên mẫu": không có nghĩa riêng đoán được
# → luôn để người duyệt điền (không dùng DEFAULTS).
_NO_DEFAULT = ("phần của", "bắt đầu ví dụ", "nguyên mẫu")

# Nghĩa mặc định theo ghi chú của LLM (BE-06h, Q-025): thắng DEFAULTS và _NO_DEFAULT.
_BE_FORMS = {"be", "is", "are", "am", "was", "were", "been", "being", "'s", "'re", "'m"}
_PASSIVE_HINTS = ("bị động",)
_INFINITIVE_HINTS = ("trước động từ", "nguyên mẫu")


def _hinted_default(low: str, vi: str) -> str | None:
    """`be` có ghi chú bị động → "được"; `to` có ghi chú trước động từ / nguyên mẫu → "để"."""
    note = vi.lower()
    if low in _BE_FORMS and any(h in note for h in _PASSIVE_HINTS):
        return "được"
    if low == "to" and any(h in note for h in _INFINITIVE_HINTS):
        return "để"
    return None
_NOT_A_MEANING = {"be", "to be", "that", "it", "the", "a", "an"}

_GROUP = re.compile(r"\(([^()]*)\)")
_QUOTED = re.compile(r"['\"‘’“”]([^'\"‘’“”]+)['\"‘’“”]")


def _is_label(s: str) -> bool:
    s = s.lower()
    return any(w in s for w in _LABEL_WORDS)


def _from_label(group: str) -> str:
    """Phần nghĩa còn dùng được bên trong một nhãn: 'liên từ 'và'' → 'và'; 'giới từ: ở' → 'ở'."""
    if any(w in group.lower() for w in _NO_DEFAULT):
        return ""
    q = _QUOTED.findall(group)
    if q:
        kept = [x for x in q if not _is_label(x) and x.lower() not in _NOT_A_MEANING]
        return kept[0] if kept else ""
    pieces = [p.strip() for p in re.split(r"[:\-–]", group)]
    kept = [p for p in pieces if p and not _is_label(p)]
    return kept[0] if kept else ""


def _tidy(s: str) -> str:
    s = re.sub(r"\s*/\s*", "/", s)
    return re.sub(r"\s+", " ", s).strip(" ,;")


def clean_meaning(vi: str) -> str:
    """Bỏ nhãn ngữ pháp và ngoặc; trả '' nếu chỉ có nhãn.
    Có chữ ngoài ngoặc → chữ đó là nghĩa, bỏ ngoặc giải thích ("chúng (robot)" → "chúng").
    Chỉ có ngoặc → mở ngoặc ("(và)" → "và"), nhãn thì lấy phần nghĩa trong nhãn."""
    outside = _tidy(_GROUP.sub(" ", vi))
    if outside:
        return "" if _is_label(outside) and not _from_label(outside) else (
            _from_label(outside) if _is_label(outside) else outside)
    parts = []
    for g in _GROUP.findall(vi):
        g = g.strip()
        parts.append(_from_label(g) if _is_label(g) else g)
    return _tidy(" ".join(p for p in parts if p))


def normalize_fn_meaning(text: str, vi: str | None) -> tuple[str | None, str]:
    """Trả (nghĩa mới, trạng thái) với trạng thái: 'same' | 'cleaned' | 'default' | 'missing'."""
    if vi is None:
        return vi, "same"
    low = text.lower().replace("’", "'")
    new = clean_meaning(vi)
    if low in {"the", "a", "an"}:
        # Mạo từ: được dùng nhãn. Giữ nghĩa thật ("càng", "một"), còn lại dùng nhãn chuẩn.
        if not new or new.lower() in {low, "là", "the"}:
            new = ARTICLE_THE if low == "the" else ARTICLE_A
        elif low != "the" and new.lower() == "một":
            new = "một"
    elif not new:
        hinted = _hinted_default(low, vi)
        if hinted:
            return hinted, "default"
        if low in DEFAULTS and not any(w in vi.lower() for w in _NO_DEFAULT):
            return DEFAULTS[low], "default"
        return vi, "missing"
    return new, "same" if new == vi else "cleaned"


_NOTE_PREFIXES = ("trong ", "trong'", "từ ", "đơn vị", "số", "ký hiệu", "tên ", "phần của",
                  "viết tắt", "loại")


_PHRASE_DEPS = {"amod", "compound"}


def normalize_content_meaning(text: str, vi: str | None, dep: str | None = None) -> tuple[str | None, str]:
    """Từ nội dung (BE-06i): giữ ngoặc giải thích sau một nghĩa thật ("phủ (lên)"), chỉ sửa 3 kiểu lỗi:
    - "<chữ của token> (<nghĩa>)" → "<nghĩa>" ("eel (lươn)" → "lươn"); không áp khi token bổ nghĩa
      cho từ sau trong một cụm (`dep` amod/compound: "bucket (danh sách mong muốn)" của "bucket list");
    - "<nghĩa> (<nhãn ngữ pháp>)" → "<nghĩa>" ("Ý (tính từ)" → "Ý"); không áp khi ngoặc ghi token
      thuộc cụm nào ("món (phần của 'hot dog')", Q-031);
    - toàn bộ trong ngoặc → mở ngoặc ("(thế kỷ)" → "thế kỷ"), chỉ là nhãn → mặc định / báo thiếu."""
    if vi is None:
        return vi, "same"
    outside = _tidy(_GROUP.sub(" ", vi))
    groups = [g.strip() for g in _GROUP.findall(vi) if g.strip()]
    if not groups:
        return vi, "same"
    if outside and any("phần của" in g.lower() for g in groups):
        return vi, "same"
    if not outside:
        new = clean_meaning(vi)
        if new:
            return new, "cleaned"
        low = text.lower().replace("’", "'")
        if low in DEFAULTS and not any(w in vi.lower() for w in _NO_DEFAULT):
            return DEFAULTS[low], "default"
        return vi, "missing"
    # Chỉ bỏ chữ Anh lặp lại khi ngoặc là bản dịch: không áp cho số ("60 (năm)") và ngoặc là
    # ghi chú ("cha (từ Quảng Đông)", "pop (trong 'pop-up')", "gallon (đơn vị)").
    inner = groups[0] if len(groups) == 1 else ""
    if (outside.lower() == text.lower() and inner and not _is_label(inner) and dep not in _PHRASE_DEPS
            and re.fullmatch(r"[A-Za-z][A-Za-z'’-]*", text)
            and not inner.lower().startswith(_NOTE_PREFIXES)):
        return inner, "cleaned"
    if all(_is_label(g) for g in groups) and not _is_label(outside):
        return outside, "cleaned"
    return vi, "same"


# Nghĩa LLM hay gán cho `be` mà không xét ngữ cảnh → được thay theo ngữ cảnh (BE-06i).
_BE_PLAIN = {"là", "đã", "đã là", "thì"}
_SKIP_DEPS = {"advmod", "npadvmod", "neg"}
_CONTRACTED_BE = {"'s", "'re", "'m"}

# be + V-ed chỉ trạng thái / hướng, không phải hành động bị tác động (Q-031): giữ nghĩa LLM.
# Giá trị = từ phải đứng ngay sau phân từ (None = không cần): "is made up of" là trạng thái,
# "were made to copy" vẫn là bị động.
_STATIVE_VBN = {"locate": None, "base": None, "head": None, "mean": None, "bear": None,
                "make": {"up", "of"}, "load": {"with"}}
# Bị động mang sắc thái bất lợi cho chủ ngữ → "bị" (Q-031: "was destroyed", "is limited", "is hidden").
_ADVERSE_VBN = {
    "destroy", "damage", "limit", "hide", "kill", "injure", "hurt", "break", "ban", "burn",
    "attack", "steal", "lose", "punish", "arrest", "delay", "cancel", "force", "defeat",
    "reject", "abandon", "criticize", "criticise", "block", "ruin", "threaten", "wound",
    "flood", "forget", "ignore", "restrict",
}


def _verb_after_be(tokens: list[dict], k: int) -> tuple[dict | None, dict | None]:
    """(từ chính sau `be` khi bỏ qua trạng từ, từ ngay sau từ đó)."""
    for j in range(k + 1, len(tokens)):
        nxt = tokens[j]
        if not nxt["is_word"]:
            return None, None
        if nxt.get("pos") == "ADV" or nxt.get("dep") in _SKIP_DEPS:
            continue
        after = next((x for x in tokens[j + 1:] if x["is_word"]), None)
        return nxt, after
    return None, None


def _is_passive_be(tokens: list[dict], k: int) -> bool:
    """`be` là trợ động từ bị động: spaCy gắn `auxpass`, hoặc từ kế tiếp (bỏ qua trạng từ,
    "is often called", "is hand tossed") có tag VBN. Ca không phải: "has been around", "were hungry"."""
    if tokens[k].get("dep") == "auxpass":
        return True
    verb, _ = _verb_after_be(tokens, k)
    return bool(verb) and verb.get("tag") == "VBN"


def _passive_meaning(tokens: list[dict], k: int) -> str | None:
    """Nghĩa cho `be` bị động: "được"; sắc thái bất lợi → "bị"; chỉ trạng thái → None (giữ nghĩa cũ)."""
    verb, after = _verb_after_be(tokens, k)
    lemma = ((verb or {}).get("lemma") or "").lower()
    if lemma in _STATIVE_VBN:
        need = _STATIVE_VBN[lemma]
        if need is None or (after and after["text"].lower() in need):
            return None
    return "bị" if lemma in _ADVERSE_VBN else "được"


def _progressive_meaning(tokens: list[dict], k: int) -> str | None:
    """`be` + V-ing làm trợ động từ ("has been growing", "you're looking") → "đang";
    "be going to + động từ" là tương lai → "sẽ" ("we are going to be hearing")."""
    if tokens[k].get("dep") not in {"aux", None}:
        return None
    verb, after = _verb_after_be(tokens, k)
    if not verb or verb.get("tag") != "VBG":
        return None
    if (verb.get("lemma") or "").lower() == "go" and after and after["text"].lower() == "to":
        j = tokens.index(after)
        then = next((x for x in tokens[j + 1:] if x["is_word"]), None)
        if then and then.get("tag") == "VB":
            return "sẽ"
    return "đang"


def _after_there(tokens: list[dict], k: int) -> bool:
    prev = next((x for x in reversed(tokens[:k]) if x["is_word"]), None)
    return bool(prev) and prev["text"].lower() == "there"


def _plain_be(vi: str | None) -> bool:
    return vi is not None and (vi.strip().lower() in _BE_PLAIN
                               or (not _tidy(_GROUP.sub(" ", vi)) and not clean_meaning(vi)))


def context_meaning(tokens: list[dict], k: int, vi: str | None, llm_vi: str | None = None) -> str | None:
    """Nghĩa theo ngữ cảnh cho `be`: bị động → "được" ("bị" khi bất lợi; giữ nguyên khi chỉ
    trạng thái như "is located"); tiếp diễn → "đang"; "there is/are" → "có".
    Chỉ thay khi nghĩa (sau chuẩn hóa `vi` hoặc gốc của LLM `llm_vi`) là nghĩa chung chung
    ("là", "đã"…) hoặc chỉ là nhãn, vd "there's" "(rút gọn của is)"."""
    t = tokens[k]
    if (t.get("lemma") or "").lower() != "be" or vi is None:
        return None
    if not (_plain_be(vi) or _plain_be(llm_vi)):
        return None
    if _is_passive_be(tokens, k):
        return _passive_meaning(tokens, k)
    prog = _progressive_meaning(tokens, k)
    if prog:
        return prog
    if _after_there(tokens, k):
        return "có"
    return None


def normalize_glossary(tokens: list[dict], meanings: dict[int, str]) -> dict[str, list[str]]:
    """Sửa tại chỗ `meanings`: từ chức năng theo quy ước run #38, từ nội dung theo
    `normalize_content_meaning`, rồi `be` theo ngữ cảnh (bị động, "there are"). Trả
    {'cleaned': [...], 'default': [...], 'missing': [...]} (mỗi mục 'text: cũ → mới') cho review.md."""
    report: dict[str, list[str]] = {"cleaned": [], "default": [], "missing": []}
    for k, t in enumerate(tokens):
        if not t.get("is_word", True) or t["i"] not in meanings:
            continue
        old = meanings[t["i"]]
        if t.get("is_fn"):
            new, status = normalize_fn_meaning(t["text"], old)
        else:
            new, status = normalize_content_meaning(t["text"], old, dep=t.get("dep"))
        # `be` chỉ có nhãn: dạng rút gọn ("That's" "rút gọn của is") → "là" (DEFAULTS của `'s` là
        # sở hữu → sai); `been` ("(phân từ)", "(trợ động từ)") → "đã" ("have been around").
        # Luật ngữ cảnh bên dưới vẫn áp (bị động, tiếp diễn "has been growing" → "đang").
        low = t["text"].lower().replace("’", "'")
        if ((t.get("lemma") or "").lower() == "be" and old and _is_label(old)
                and (status == "missing" or (new or "").lower() in {"của", "is", "are", "am"})):
            if low in _CONTRACTED_BE:
                new, status = "là", "default"
            elif low == "been":
                new, status = "đã", "default"
        ctx = context_meaning(tokens, k, new if status != "missing" else old, llm_vi=old)
        if ctx and ctx != new:
            new, status = ctx, "default"
        if status == "same":
            continue
        meanings[t["i"]] = new
        report[status].append(f"{t['text']}: \"{old}\"" + ("" if status == "missing" else f" → \"{new}\""))
    return report
