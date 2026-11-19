# Báo cáo từ điển CEFR (BE-15a, ADR-022)

> Sinh bằng `py -m pipeline.cefr_lexicon report`. Không sửa tay.

## 1. Nguồn

| Nguồn | File | sha256 | Số dòng |
|---|---|---|---|
| cefrj | `cefrj-vocabulary-profile-1.5.csv` | `b0dd3c635f1c9a4f…` | 7799 |
| octanove | `octanove-vocabulary-profile-c1c2-1.0.csv` | `18c33a407f2f89f7…` | 2136 |

Commit: `d4e45b75b38f27b30dfc5c44d8c571aec7e7092f`.

## 2. Số mục theo nguồn và cấp

| Bảng | Nguồn | A1 | A2 | B1 | B2 | C1 | C2 | Tổng |
|---|---|---|---|---|---|---|---|---|
| entries | cefrj | 1209 | 1411 | 2440 | 2822 | 0 | 0 | 7882 |
| entries | octanove | 0 | 0 | 0 | 0 | 1060 | 948 | 2008 |
| multiword | cefrj | 14 | 42 | 54 | 35 | 0 | 0 | 145 |
| multiword | octanove | 0 | 0 | 0 | 0 | 4 | 6 | 10 |

Khóa `lemma|UPOS`: 9890 · lemma khác nhau: 8689 · mục nhiều từ: 155.

## 3. Dòng bị bỏ

- octanove:606 `batter` pos=`` C1 — POS lạ/rỗng → không nạp
- octanove:2129 `remonstrate` pos=`vern` C2 — POS lạ/rỗng → không nạp

## 4. Trùng khóa cùng nguồn (giữ cấp thấp nhất)

- cefrj `march|NOUN`: A1 / B1 → A1
- cefrj `need|VERB`: A1 / A2 → A1
- octanove `envisage|VERB`: C1 / C2 → C1
- octanove `apprentice|VERB`: C1 / C2 → C1
- octanove `predecessor|NOUN`: C1 / C2 → C1
- octanove `daunt|VERB`: C1 / C2 → C1
- octanove `daunting|ADJ`: C1 / C2 → C1
- octanove `tedium|NOUN`: C1 / C2 → C1
- octanove `deprivation|NOUN`: C1 / C2 → C1
- octanove `envisage|VERB`: C1 / C2 → C1
- octanove `contextual|ADJ`: C1 / C2 → C1
- octanove `contextually|ADV`: C1 / C2 → C1
- octanove `maneuver|NOUN`: C1 / C2 → C1
- octanove `manoeuvre|NOUN`: C1 / C2 → C1
- octanove `maneuver|VERB`: C1 / C2 → C1
- octanove `manoeuvre|VERB`: C1 / C2 → C1
- octanove `tantamount|ADJ`: C1 / C2 → C1
- octanove `commission|NOUN`: C1 / C2 → C1
- octanove `commission|VERB`: C1 / C2 → C1
- octanove `grumble|VERB`: C1 / C2 → C1
- octanove `relinquish|VERB`: C1 / C2 → C1
- octanove `resin|NOUN`: C1 / C2 → C1
- octanove `sedately|ADV`: C1 / C2 → C1
- octanove `exhibitionist|NOUN`: C1 / C2 → C1
- octanove `proliferate|VERB`: C1 / C2 → C1
- octanove `advantageous|ADJ`: C1 / C2 → C1

## 5. Octanove bị CEFR-J che (cùng khóa, khác cấp; CEFR-J thắng)

101 khóa.

- `complexity|NOUN`: cefrj B2 ← octanove C1
- `wing|NOUN`: cefrj B1 ← octanove C1
- `conceive|VERB`: cefrj B2 ← octanove C1
- `conceivable|ADJ`: cefrj B2 ← octanove C1
- `humble|ADJ`: cefrj B2 ← octanove C1
- `cast|NOUN`: cefrj B2 ← octanove C1
- `cast|VERB`: cefrj B2 ← octanove C1
- `tomb|NOUN`: cefrj B2 ← octanove C1
- `lap|NOUN`: cefrj B2 ← octanove C1
- `exploit|VERB`: cefrj B2 ← octanove C1
- `fit|ADJ`: cefrj A2 ← octanove C1
- `drive|VERB`: cefrj A2 ← octanove C1
- `drive|NOUN`: cefrj A1 ← octanove C1
- `pupil|NOUN`: cefrj B1 ← octanove C1
- `withdrawal|NOUN`: cefrj B2 ← octanove C1
- `talkative|ADJ`: cefrj B1 ← octanove C1
- `agonize|VERB`: cefrj B2 ← octanove C1
- `recite|VERB`: cefrj B1 ← octanove C1
- `ecstasy|NOUN`: cefrj B1 ← octanove C1
- `ecstatic|ADJ`: cefrj B2 ← octanove C1
- `nature|NOUN`: cefrj A2 ← octanove C1
- `automatically|ADV`: cefrj A2 ← octanove C1
- `calf|NOUN`: cefrj B1 ← octanove C1
- `dispensable|ADJ`: cefrj B2 ← octanove C1
- `indispensable|ADJ`: cefrj B2 ← octanove C1
- `innovation|NOUN`: cefrj B2 ← octanove C1
- `innovative|ADJ`: cefrj B2 ← octanove C1
- `jog|VERB`: cefrj B1 ← octanove C1
- `expedition|NOUN`: cefrj B2 ← octanove C1
- `resort|NOUN`: cefrj B1 ← octanove C1
- `commission|NOUN`: cefrj B2 ← octanove C1
- `recollection|NOUN`: cefrj B2 ← octanove C1
- `allegation|NOUN`: cefrj B2 ← octanove C1
- `exotic|ADJ`: cefrj B2 ← octanove C1
- `rich|ADJ`: cefrj A1 ← octanove C1
- `battery|NOUN`: cefrj A2 ← octanove C1
- `behind|ADP`: cefrj A1 ← octanove C1
- `personification|NOUN`: cefrj B2 ← octanove C1
- `imperative|NOUN`: cefrj B2 ← octanove C1
- `drill|NOUN`: cefrj A2 ← octanove C1
- `outpatient|NOUN`: cefrj B2 ← octanove C2
- `utilize|VERB`: cefrj B2 ← octanove C2
- `utility|NOUN`: cefrj B2 ← octanove C2
- `utter|VERB`: cefrj B2 ← octanove C2
- `indulge|VERB`: cefrj B2 ← octanove C2
- `circuit|NOUN`: cefrj B2 ← octanove C2
- `succeed|VERB`: cefrj A2 ← octanove C2
- `adorn|VERB`: cefrj B2 ← octanove C2
- `familiarize|VERB`: cefrj B2 ← octanove C2
- `familiarise|VERB`: cefrj B2 ← octanove C2
- `adverse|ADJ`: cefrj B2 ← octanove C2
- `adversely|ADV`: cefrj B2 ← octanove C2
- `phase|NOUN`: cefrj B2 ← octanove C2
- `notorious|ADJ`: cefrj B1 ← octanove C2
- `deficit|NOUN`: cefrj B2 ← octanove C2
- `dive|NOUN`: cefrj B1 ← octanove C2
- `mere|ADJ`: cefrj B1 ← octanove C2
- `abolish|VERB`: cefrj B2 ← octanove C2
- `paralyze|VERB`: cefrj B1 ← octanove C2
- `paralyse|VERB`: cefrj B1 ← octanove C2
- `paralysis|NOUN`: cefrj B2 ← octanove C2
- `preoccupy|VERB`: cefrj B2 ← octanove C2
- `audit|NOUN`: cefrj B2 ← octanove C2
- `punctual|ADJ`: cefrj B2 ← octanove C2
- `punctuality|NOUN`: cefrj B2 ← octanove C2
- `curriculum|NOUN`: cefrj B1 ← octanove C2
- `abundant|ADJ`: cefrj B1 ← octanove C2
- `abundance|NOUN`: cefrj B1 ← octanove C2
- `crystallize|VERB`: cefrj B2 ← octanove C2
- `crystallise|VERB`: cefrj B2 ← octanove C2
- `retrospect|NOUN`: cefrj B1 ← octanove C2
- `tactile|ADJ`: cefrj B2 ← octanove C2
- `vocalist|NOUN`: cefrj B2 ← octanove C2
- `chronological|ADJ`: cefrj B1 ← octanove C2
- `haven|NOUN`: cefrj B1 ← octanove C2
- `catastrophic|ADJ`: cefrj B2 ← octanove C2
- `inert|ADJ`: cefrj B2 ← octanove C2
- `lark|NOUN`: cefrj B2 ← octanove C2
- `soliloquy|NOUN`: cefrj B2 ← octanove C2
- `wax|VERB`: cefrj B1 ← octanove C2
- `plane|NOUN`: cefrj A1 ← octanove C2
- `figurative|ADJ`: cefrj B2 ← octanove C2
- `attainment|NOUN`: cefrj B2 ← octanove C2
- `skim|VERB`: cefrj B2 ← octanove C2
- `barometer|NOUN`: cefrj B2 ← octanove C2
- `strait|NOUN`: cefrj B2 ← octanove C2
- `redundant|ADJ`: cefrj B2 ← octanove C2
- `diligent|ADJ`: cefrj B1 ← octanove C2
- `diligence|NOUN`: cefrj B1 ← octanove C2
- `sulphur|NOUN`: cefrj B2 ← octanove C2
- `converse|NOUN`: cefrj B2 ← octanove C2
- `glint|NOUN`: cefrj B1 ← octanove C2
- `venture|NOUN`: cefrj B2 ← octanove C2
- `agency|NOUN`: cefrj A2 ← octanove C2
- `accessibility|NOUN`: cefrj B2 ← octanove C2
- `cascade|NOUN`: cefrj B2 ← octanove C2
- `formidable|ADJ`: cefrj B2 ← octanove C2
- `wither|VERB`: cefrj B1 ← octanove C2
- `hover|VERB`: cefrj B2 ← octanove C2
- `merger|NOUN`: cefrj B2 ← octanove C2
- `surge|NOUN`: cefrj B2 ← octanove C2

## 6. Xung đột với `cefr.json` (giữ bản duyệt)

| Mục | cefr.json | Từ điển | Nguồn |
|---|---|---|---|
| stage | B2 (duyet-run38) | A1 | cefrj |
| robot | A2 (duyet-run38) | B1 | cefrj |

`cefr.json`: 58 mục, 8 mục có trong từ điển.

## 7. Độ phủ token theo bài

Token từ (`is_word`) tra ra cấp bằng `lookup_cefr(lemma, pos, text)` (gồm cefr.json).

| Bài | Tra được | Tổng | % | Lemma trượt nhiều nhất |
|---|---|---|---|---|
| eating-well | 509 | 569 | 89.5 | cholesterol (3), moderation (2), antioxidant (2), protein (2), celery (2), takeout (1), leafy (1), kale (1) |
| robots | 696 | 773 | 90.0 | mars (4), asimo (3), robotic (2), 1960 (2), humanlike (2), ai (2), watson (2), sensor (2) |
| farming | 819 | 903 | 90.7 | plow (8), livestock (3), erosion (3), planting (2), harvesting (2), oxen (2), kernel (2), arable (2) |
| rocket-science | 825 | 922 | 89.5 | propellant (13), newton (4), ignition (4), nasa (3), chamber (3), nozzle (3), wan (2), hu (2) |
| water-power | 656 | 778 | 84.3 | hydropower (8), hydroelectric (5), states (4), turbine (4), watermill (4), hydropow (3), china (3), shaft (3) |
| ai-chatbots | 1182 | 1299 | 91.0 | ai (14), openai (12), chatgpt (7), llm (6), api (5), gpt-3 (4), chatbot (3), gpt-6 (3) |
| curry-chicken | 780 | 918 | 85.0 | hong (8), kong (8), cha (8), chaan (8), teng (8), portuguese (6), sin (5), roux (3) |
| holiday-travel | 1150 | 1344 | 85.6 | $ (14), thanksgiving (10), christmas (10), u.s. (4), cuomo (3), york (3), 15 (3), 22 (3) |
| **Tổng 8 bài** | 6617 | 7506 | 88.2 | |

## 8. Chênh lệch CEFR của mục từ đơn (cần người duyệt)

Mục `single_word`/từ đơn trong `bundle.json` có `cefr_level` khác kết quả tra (hoặc từ điển không có). **Không tự sửa.** Muốn đổi: ghi vào `cefr.json` rồi seed lại bài (sau BE-06g để không lỡ cache).

| Bài | Mục | pos | Hiện tại | Tra được | Nguồn | Ghi chú |
|---|---|---|---|---|---|---|
| water-power | hydropower | noun | B2 | — | không có |  |
| ai-chatbots | chatbot | noun | B1 | — | không có |  |
| curry-chicken | hole-in-the-wall | adjective | B2 | — | không có |  |
| curry-chicken | cross-cultural | adjective | B2 | — | không có |  |

## 9. Cụm khớp nguyên văn từ điển nhưng khác cấp

| Bài | Cụm | Hiện tại | Tra được | Nguồn | Ghi chú |
|---|---|---|---|---|---|
| (không có) | | | | | |
