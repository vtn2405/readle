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
    "viết tắt", "trạng từ", "bắt đầu ví dụ", "vô nghĩa", "phần của",
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


def normalize_glossary(tokens: list[dict], meanings: dict[int, str]) -> dict[str, list[str]]:
    """Sửa tại chỗ `meanings` cho token is_fn. Trả {'cleaned': [...], 'default': [...], 'missing': [...]}
    (mỗi mục 'text: cũ → mới') để ghi vào review.md."""
    report: dict[str, list[str]] = {"cleaned": [], "default": [], "missing": []}
    for t in tokens:
        if not t.get("is_fn") or t["i"] not in meanings:
            continue
        old = meanings[t["i"]]
        new, status = normalize_fn_meaning(t["text"], old)
        if status == "same":
            continue
        meanings[t["i"]] = new
        report[status].append(f"{t['text']}: \"{old}\"" + ("" if status == "missing" else f" → \"{new}\""))
    return report
