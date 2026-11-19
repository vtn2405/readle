# Nguồn dữ liệu CEFR (ADR-022, BE-15a)

- Repo: https://github.com/openlanguageprofiles/olp-en-cefrj
- Commit ghim: `d4e45b75b38f27b30dfc5c44d8c571aec7e7092f`
- Ngày tải: 2026-11-18 (raw.githubusercontent.com, đúng commit trên; không sửa nội dung)
- Chỉ chép 2 file dưới đây (không dùng Grammar Profile). Giấy phép: xem `NOTICE`.

| File | sha256 |
|---|---|
| `cefrj-vocabulary-profile-1.5.csv` | `b0dd3c635f1c9a4fdf1490c7e5b7c48e8bbe55b652ad0c9860a95f98e10ae498` |
| `octanove-vocabulary-profile-c1c2-1.0.csv` | `18c33a407f2f89f7b8de9671c6d45fe3ea0bce45e7d2d7dcaab48d73e0f7b380` |

Tải lại (Git Bash):

```
C=d4e45b75b38f27b30dfc5c44d8c571aec7e7092f
for f in cefrj-vocabulary-profile-1.5.csv octanove-vocabulary-profile-c1c2-1.0.csv; do
  curl -sSfL -o $f https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/$C/$f
done
sha256sum *.csv
```

Sau đó: `py -m pipeline.cefr_lexicon build` → `pipeline/data/cefr_lexicon.json`.
