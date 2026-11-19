# HANDOFF — Hộp thư giữa các agent và người dùng

> Ghi mục mới ở cuối từng phần. Khi xử lý xong, chuyển mục sang phần "Đã xử lý" kèm số run.
> Mẫu: `- [ID] (run #N, người viết → người nhận) Nội dung. **Cần:** quyết định / sửa / trả lời.`

## Câu hỏi chờ người dùng quyết định
- [Q-031] (run #94, Claude → Người dùng) BE-06i phần A: luật glossary mới chạy lại trên 10 bài (0 lời gọi API) đổi **160 nghĩa** token, liệt kê đủ trong `docs/reviews/run94-glossary-diff.md` theo 3 nhóm: (1) 78 chỗ bị động "là"/"đã" → "được" (Claude đã soát cả 78, đều là bị động thật; vài chỗ "được" chưa tự nhiên như "is located", "is based on" nhưng vẫn đúng hơn "là"); (2) 19 chỗ "there is/are/was" → "có" (trước đó nhiều chỗ hiện nhãn "(động từ to be)" cho người đọc); (3) 63 chỗ ngoặc/nhãn ("protein (chất đạm)" → "chất đạm", "(như)" → "như", "That's" "rút gọn của is" → "là"…; số và ngoặc ghi chú như "cha (từ Quảng Đông)" giữ nguyên). **Cần:** xem file, chỉ ra chỗ nào muốn giữ cách cũ (Claude ghi `overrides.json → meanings` của bài đó); đồng ý → Claude seed lại 10 bài local + cloud.
- [Q-006] (xử lý một phần run #13) (run #8, Claude → Người dùng) BE-03 DONE. `pipeline/out/eating-well/bundle.json` (9 section, 566 từ, 8 mục từ, 14 occurrence, 3 quiz) đã qua `ArticleBundle.model_validate`. `review.md` có 5 phần duyệt: key idea, mục từ, quiz, glossary. **Cần:** duyệt `review.md` (đặc biệt key idea và nghĩa từ) trước khi chạy BE-05 seed.
- [Q-005] (run #7, Claude → Người dùng) `pipeline/out/eating-well/normalized_sections.json` đã sinh bằng Vision (9 section, 568 từ, `check` pass). **Cần:** đọc lướt file đối chiếu ảnh (không sót box, không bịa chữ) trước khi Claude chạy BE-03.
- [Q-004] (run #6, Claude → Người dùng) Key Azure thật của bạn nằm trong `.env.example` (file sẽ bị commit). Tôi đã chuyển nó sang `.env` (gitignored) và trả `.env.example` về placeholder. Key CHƯA từng bị commit nên không cần xoay key. **Cần:** từ nay điền key vào `.env`, không điền `.env.example`.





- [H-022] (run #78, cập nhật run #82, #86, Claude → Antigravity) Bài thứ 9 **`paris`** đã lên **cloud + local** (`processing_order` 9, B1, category "Places & Culture" → có màu riêng từ FE-07f, DONE run #86; 12 mục có audio). **Cần:** không có việc mới.

## Claude → Antigravity
- [H-001] (run #0) Bắt đầu từ FE-01, FE-02. Dữ liệu duy nhất cần dùng là `fixtures/article_eating_well.json`; đừng chờ Supabase. Fixture có cặp chồng lấn `play a vital role in` / `vital role` ở `sec_ew_1` token 2-6 và 4-5 để test luật chạm.
- [R-FE-02] (run #5) Review FE-02: **ĐẠT**
  - Không có vấn đề bắt buộc sửa.
  - Đã kiểm: `flutter analyze` No issues · `flutter test` 4/4 pass (xác minh độc lập run #5); models khớp CONTRACTS `article_cards` view; `Occurrence.tokenEnd` inclusive đúng; lemma_key đúng.
- [R-FE-03-partial] (run #9) Review FE-03 giữa chừng (task vẫn DOING): **CẦN HOÀN THIỆN**
  - Đã đạt: `TokenTextView` render đúng text+ws, recognizer chỉ cho isWord, highlight logic collocation-wins-overlap đúng contract. Theme paper tone OK. `flutter analyze` sạch, test 4/4 pass.
  - Còn thiếu (bắt buộc cho nghiệm thu): (1) `reader_screen.dart` chưa có PageView/section card — vẫn là placeholder FE-01; (2) Key idea chưa hiển thị ở đầu card; (3) chưa lưu tiến trình trong memory (state progress).
  - Nên sửa (không chặn): (a) `app/lib/features/reader/models/highlight_kind.dart` — thêm unit test cho `computeHighlights` (ít nhất 3 ca: none, singleWord, overlap→collocation); (b) `app/lib/features/reader/widgets/token_text_view.dart:84` — recognizerIndex đếm tuyến tính dễ lệch nếu thêm filter sau này, cân nhắc dùng `Map<int, TapGestureRecognizer>` theo `token.i`.
  - Đã kiểm: `flutter analyze` No issues · `flutter test` 4/4 pass · review tĩnh (không chạy UI vì screen chưa build)
- [R-FE-03] (run #11) Review FE-03: **ĐẠT**
  - Nghiệm thu: (1) chữ + khoảng trắng đúng câu gốc — đạt (test tái dựng `text+ws`); (2) dấu câu không có vùng chạm — đạt (recognizer chỉ cho `is_word`, có test); (3) dark mode — đạt (test màu highlight dark). PageView mỗi section 1 card, Key idea đầu card và chạm được, highlight chồng lấn → cụm, tiến trình in-memory: đều có. Các mục [R-FE-03-partial] đã xử lý.
  - Bắt buộc sửa: không có.
  - Nên sửa (không chặn, làm kèm FE-04):
    - (a) `app/lib/features/reader/widgets/token_text_view.dart:8` — `OnTokenTap` chỉ truyền `Token`, không biết token nằm trong Key idea hay thân bài. Index `i` của Key idea trùng với index thân bài, nên `resolveTap` ở FE-04 sẽ tìm nhầm occurrence; event `word_tapped` (CONTRACTS mục 4) cũng cần `in_key_idea`. Đổi thành `void Function(Token token, {required bool inKeyIdea})` hoặc truyền cờ qua `TokenTextView`. Token Key idea không bao giờ khớp occurrence → chỉ tooltip.
    - (b) `token_text_view.dart:122-129` — span `ws` luôn dùng style gốc, nên cụm "plays a vital role in" hiện thành 5 mảng nền rời. Nếu token `i` và `i+1` cùng thuộc một highlight thì cho `ws` dùng chung nền (không gắn recognizer).
    - (c) `app/lib/features/reader/screens/reader_screen.dart:87-93` — `initSections` gọi qua `addPostFrameCallback` mỗi lần build; nên khởi tạo một lần (vd `ref.listen` trên `articleBundleProvider` hoặc trong provider). `computeHighlights` (dòng 106) tính lại mỗi lần build card — có thể memo theo `section.id`.
  - Đã kiểm: `flutter analyze` No issues · `flutter test` 13/13 pass (chạy độc lập run #11) · grep key trong `app/`: sạch (chỉ `String.fromEnvironment('SUPABASE_ANON_KEY')`) · phạm vi commit e3a80b5: chỉ `app/**` + docs được phép · no-pressure: chỉ báo vị trí "1 / 2", không streak/điểm/đếm ngược.

- [R-FE-04b] (run #21) Review FE-04b: **ĐẠT**
  - Nghiệm thu: (1) chạm "tend" → 6 khối đúng thứ tự (test so tọa độ dọc), không có "Xem thêm" — đạt; (2) 2 nút loa, 0.75x gọi `speed: 0.75` — đạt; (3) chạm "role" → `play a vital role in` đầy đủ, `vital role` gọn, dòng từ đơn có `/roʊl/` — đạt; (4) "folate" → tooltip không có IPA, không có "null" — đạt; (5) analyze sạch, test cũ vẫn pass — đạt. Góp ý (a)-(d) của [R-FE-04] đã xử lý.
  - Bắt buộc sửa: không có.
  - Nên sửa (không chặn, làm kèm FE-08 vì FE-08 cũng sửa các sheet này):
    - (a) `app/lib/features/reader/widgets/entry_detail_block.dart:39-41` — in đậm `extra_example` bằng so khớp nguyên chuỗi `canonical_form`, nên **không** in đậm được khi mục từ biến hình. Lỗi thật trong fixture: `play a vital role in` có ví dụ "Sleep **plays** a vital role in memory." → không có chữ nào đậm. Sửa: dựng regex từ các từ của `canonical_form`, cho mỗi từ có đuôi biến hình (`\bplay\w*\s+a\s+vital\s+role\s+in\b`, không phân biệt hoa thường); không khớp thì giữ như hiện tại (không đậm). Thêm widget test: chạm "role" → "plays a vital role in" đậm.
    - (b) `app/test/features/reader/tap_sheets_test.dart:256-258` — AC-3 chưa thực sự kiểm "cụm gọn không có định nghĩa". Fixture `vital role` có `definition_en` "a very important part or function", nên thêm `expect(find.text('a very important part or function'), findsNothing)`.
    - (c) Vùng chạm nhỏ hơn 48dp (khó bấm trên điện thoại, nhất là nút mới 0.75x): nút 0.75x (`entry_detail_block.dart:181`, khoảng 22px cao), loa trong tooltip (`word_tooltip.dart:113`, khoảng 20px), loa ở dòng từ đơn (`phrase_bottom_sheet.dart:183`, khoảng 32px). Bọc bằng `ConstrainedBox(minWidth/minHeight: 44)` hoặc dùng `IconButton` (giữ hình nhỏ, chỉ nới vùng chạm).
    - (d) `phrase_bottom_sheet.dart:109` — `onSave: () => onSavePhrase?.call(occ)` luôn khác null nên nút Lưu luôn bật kể cả khi chưa nối callback. Nối thật ở FE-08; khi đó truyền `onSave: onSavePhrase == null ? null : () => ...`.
  - Đã kiểm: `flutter analyze` No issues · `flutter test` 39/39 pass (chạy độc lập run #21) · fixture app giống hệt `fixtures/` (cmp) · grep key trong `app/`: sạch · phạm vi commit b96d3d8: chỉ `app/**` + docs được phép · no-pressure: CEFR là nhãn trung tính, không màu phán xét; không thêm khối ngoài 6 khối ADR-010 · review tĩnh UI, chưa chạy trên thiết bị.


- [H-003] (run #25) BE-04 DONE trên **Supabase local** (chưa có project cloud). Dùng cho FE-06 khi tới lượt: `npx supabase start` ở gốc repo → API `http://127.0.0.1:54321` (máy ảo Android: `http://10.0.2.2:54321`), anon key lấy bằng `npx supabase status`; truyền qua `--dart-define`, không ghi vào code. Anonymous sign-in đã bật. RPC `get_article_bundle` trả id dạng **uuid**, không phải `art_eating_well`/`sec_ew_1` như fixture; app không được giả định định dạng id. **Cần:** không có việc ngay, chỉ để tham chiếu khi làm FE-06.



- [R-FE-04c] (run #30) Review FE-04c: **ĐẠT**
  - Nghiệm thu: (1) loa 1x → `speed: 1.0`, nút 0.75x → `speed: 0.75` — đạt (test AC-2 của FE-04b giữ nguyên, pass); (2) vùng chạm 4 nút loa ≥ 44×44 — đạt (test AC-6 đo `getSize`); (3) grep `app/lib` không còn `audioSpeedProvider`/`slowSpeedProvider`/`1.25`/`1.5x`/`PopupMenuButton<double>` — đạt; (4) sheet vẫn 6 khối, analyze sạch, toàn bộ test pass — đạt.
  - Contract: fixture app giống hệt `fixtures/` (1.3); `audio_played.speed` chỉ có 1.0/0.75.
  - Bắt buộc sửa: không có.
  - Nên sửa (không chặn):
    - (a) `app/test/data/article_repository_test.dart:24` nằm ngoài danh sách file của task. Sửa là đúng (fixture lên 1.3), nhưng lần sau ghi vào "Giả định / lệch so với task" trong PROGRESS thay vì "Không có".
    - (b) `word_tooltip.dart:113`: loa 44dp làm dòng tiêu đề tooltip cao thêm khoảng 20px. Khi chạy trên máy thật nếu tooltip trông thô thì giữ vùng chạm nhưng cho phép tràn ra ngoài (vd `IconButton` với `visualDensity: VisualDensity.compact` + `materialTapTargetSize: MaterialTapTargetSize.padded`); xem ở FE-15.
    - (c) `entry_detail_block.dart:186-224`: ripple của nút 0.75x phủ cả ô 44dp, rộng hơn viền pill. Thuần thẩm mỹ, có thể để FE-15.
  - Đã kiểm: `flutter analyze` No issues · `flutter test` 40/40 pass (chạy độc lập run #30) · grep key trong `app/`: sạch · phạm vi commit 9cc3939: `app/**` + docs được phép (thay đổi trong DECISIONS/ARCHITECTURE mục 2 của commit là của Claude run #27-28, người dùng commit chung) · no-pressure: không thêm khối, không số liệu/đếm · review tĩnh UI, chưa chạy trên thiết bị.

- [H-006] (run #32) Backend đã có trên **cloud** (project `readle`): schema contract 1.3, RLS, Anonymous Sign-ins bật, bài Eating Well đã duyệt (id bài là uuid). Dùng cho FE-06: tạo `app/env/dev.json` (gitignore) với `SUPABASE_URL` (URL gốc `https://<ref>.supabase.co`, **không** có `/rest/v1`) + `SUPABASE_ANON_KEY` (người dùng lấy từ `.env` gốc, chỉ anon key) + `USE_FIXTURE`; chạy `flutter run --dart-define-from-file=env/dev.json`. Supabase local (H-003) vẫn dùng được khi phát triển. **Cần:** không có việc ngay.

- [R-FE-05] (run #35) Review FE-05: **ĐẠT**
  - Nghiệm thu: (1) unit test Hive thật: 3 box đọc/ghi, dấu xóa (`deleted && dirty`, `isSaved == false`, lưu lại gỡ cờ), `event_queue` khóa tự tăng/`peekBatch`/`remove` — đạt; (2) widget test card 2 → `ProviderScope` mới → mở ở "2 / 2" — đạt; (3) card 2 → lùi card 1 → `ProviderScope` mới → "1 / 2", `progressPercent == 100`, `completed == true` — đạt; (4) không thêm chữ/badge, analyze sạch, toàn bộ test pass — đạt.
  - Đúng 4 yêu cầu của H-005: dấu xóa, nạp đồng bộ trong constructor (`getProgressSync`), phần trăm theo `maxIndexReached`, khôi phục theo `lastReadSectionId` rồi mới tới index kẹp phạm vi + `jumpToPage`.
  - Bắt buộc sửa: không có.
  - Nên sửa (không chặn):
    - (a) **Làm trước FE-06/FE-09:** `app/lib/data/models/local_models.dart` `SavedWord.toMap` lưu `due_date` bằng `dueDate.toUtc().toIso8601String()`. Contract là kiểu `date`; ở Việt Nam (UTC+7), "hôm nay" 00:00 giờ máy đổi sang UTC thành ngày **hôm trước** (`2026-11-13` → `2026-11-12T17:00Z`), nên SRS sẽ lệch 1 ngày. Lưu `due_date` dạng chuỗi `yyyy-MM-dd` theo ngày giờ máy, không qua UTC; `saved_at`/`first_reviewed_at` giữ timestamp UTC như hiện tại.
    - (b) `reader_state.dart` `initSections(dynamic sectionsOrTotal)`: đổi thành `initSections(List<Section> sections)` và bỏ nhánh `int` (không còn ai gọi), để analyzer bắt lỗi kiểu.
    - (c) `local_providers.dart`: khi box chưa mở thì `try {} catch (_) {}` âm thầm chuyển sang repository in-memory, nên nếu Hive lỗi trên máy thật app vẫn chạy nhưng mất dữ liệu mà không ai biết. Nên `debugPrint` khi rơi vào nhánh này; test thì override provider như đang làm. `main.dart` `await initHive()` chưa có xử lý lỗi (box hỏng → app không mở được); để FE-15.
  - Đã kiểm: `flutter analyze` No issues · `flutter test` 45/45 pass (chạy độc lập run #35) · grep key trong `app/lib`: sạch · phạm vi commit 044d78c: `app/**` + docs được phép (Antigravity chỉ đổi trạng thái FE-05 trong TASKS; phần BE-06 trong diff là của Claude) · no-pressure: màn đọc chỉ có "x / n" như cũ, không thêm % hay "còn dở".

- [R-FE-04d] (run #40) Review FE-04d: **ĐẠT**
  - Nghiệm thu: (1) "tend" → khối 2 có đúng 1 `volume_up_outlined`, chip `1x`, loa phát `1.0` — đạt; (2) chạm chip → phát ngay `0.75`, chip `0.75x`; loa → `0.75`; chạm lại → `1.0`, `1x` — đạt (tính `next` trước rồi mới phát); (3) để `0.75x` → "role" cả 2 khối cụm hiện `0.75x`, dòng từ đơn phát `0.75`, tooltip "health" phát `0.75` — đạt; (4) vùng chạm loa, chip, loa tooltip, loa dòng từ đơn ≥ 44×44, sheet vẫn 6 khối — đạt; (5) analyze sạch, test pass gồm FE-05 — đạt.
  - Góp ý R-FE-05 (a) `due_date` dạng `yyyy-MM-dd` theo giờ máy + đọc được dạng ISO UTC cũ, (b) `initSections(List<Section>)`: đã xử lý đúng. (c) (`debugPrint` khi rơi về repo in-memory) chưa làm, vẫn để FE-06/FE-15.
  - Contract: `audio_played.speed` chỉ nhận `toggleSpeed` → 1.0/0.75; callback `onSpeak` đổi sang `required double speed` nên không còn chỗ nào âm thầm phát 1.0 mặc định.
  - Bắt buộc sửa: không có.
  - Nên sửa (không chặn):
    - (a) Chưa có test cho việc chạm chip ở khối cụm **gọn** (`vital role`) thì nhãn khối đầy đủ đổi theo (TASKS FE-04d việc 3). Code đúng vì cả 2 khối `watch` cùng provider; thêm 1 dòng test khi làm FE-08 (cùng sửa sheet cụm).
    - (b) `reader_screen.dart` tooltip đọc `speedModeProvider` lúc **mở** tooltip, không phải lúc bấm loa. Hiện không lệch vì tooltip không có chip và sheet đã đóng; nếu sau này đổi chế độ được khi tooltip đang mở thì chuyển `ref.read` vào trong `onSpeak`.
  - Đã kiểm: `flutter analyze` No issues · `flutter test` 47/47 pass (chạy độc lập run #40) · grep key trong `app/lib`: sạch · phạm vi commit 3d4acec: phần `app/**` + docs của Antigravity đúng phạm vi (`pipeline/**`, `DECISIONS`, `SPEC`, `sources/` trong commit là của Claude run #38 / người dùng commit chung) · no-pressure: chip là nhãn trung tính, không thêm khối, không số liệu · review tĩnh UI, chưa chạy trên thiết bị.


- [R-FE-06] (run #44) Review FE-06 (commit 448d4fb): **CẦN SỬA** (2 điểm, đều nhỏ; phần còn lại tốt)
  - Bắt buộc sửa:
    - (1) `app/lib/data/providers/sync_providers.dart` `remoteStoreProvider` chỉ kiểm `AppConfig.hasSupabaseConfig`, còn `main.dart` chỉ `Supabase.initialize` khi `hasSupabaseConfig && !useFixture`. Với `env/dev.json` có key nhưng `USE_FIXTURE=true` (hoặc khi `Supabase.initialize` lỗi và rơi vào `catch`), `Supabase.instance.client` ném lỗi vì chưa khởi tạo. `reader_screen.dart` `initState` gọi `ref.read(syncServiceProvider)` → watch `remoteStoreProvider` → **màn đọc sập**; `app.dart` post-frame `initAuth` cũng ném lỗi. Test không bắt được vì test chạy không có dart-define. Sửa: một nguồn sự thật duy nhất, ví dụ `AppConfig.useSupabase => !useFixture && hasSupabaseConfig`, cộng cờ `supabaseReady` chỉ bật sau khi `Supabase.initialize` thành công; `remoteStoreProvider`, `articleRepositoryProvider`, `syncServiceProvider` đều dùng `useSupabase && supabaseReady`, còn lại dùng `_NoopRemoteStore` + fixture. Thêm 1 test: cấu hình "có key, USE_FIXTURE=true" (override provider/cờ) → mở bài fixture không lỗi, `initAuth` không gọi Supabase.
    - (2) Nghiệm thu "chuyển `USE_FIXTURE=false` là chạy bằng dữ liệu thật; mất mạng khi đọc vẫn không mất dữ liệu" và AC-6 của plan **chưa kiểm**: PROGRESS #42 không có lần chạy thật, `app/env/` chưa tồn tại. Cần chạy `flutter run --dart-define-from-file=env/dev.json` với cloud (H-006) và ghi vào PROGRESS kết quả 4 bước: (a) Home hiện bài Eating Well (id uuid), mở được; (b) bật chế độ máy bay, đọc thêm vài card; (c) tắt hẳn app, mở lại khi vẫn offline → Home (cache) + bài mở được; (d) bật mạng, quay lại app → `reading_history` trên cloud đúng card cuối (người dùng xem bằng Table Editor, hoặc nhờ Claude kiểm bằng SQL). Nếu không chạy được máy ảo, ghi rõ và nhờ người dùng chạy.
  - Nên sửa (không chặn):
    - (a) `sync_service.dart` `_doFlush`: một `try` cho cả 3 luồng → lỗi ở `reading_history` (vd FK khi bài bị xóa khỏi DB) chặn luôn `user_saved_words` và events ở mọi lần sync sau. Bọc `try` riêng từng luồng.
    - (b) `SavedWordsRepository.markClean` so `savedAt` để biết bản ghi đổi chưa, nhưng cập nhật snapshot (FE-08) và SRS (FE-09/10) không đổi `savedAt` → thay đổi xảy ra đúng lúc đang upload sẽ bị gỡ `dirty` và không bao giờ lên server. Khi làm FE-08: so toàn bộ `toMap()` (trừ `dirty`) hoặc thêm `updatedAt` cục bộ.
    - (c) `docs/PROGRESS.md` có **2 mục Run #42 giống hệt nhau** (dòng ~35 và ~61) → xóa 1. `docs/ARCHITECTURE.md` mục 4 ghi FE-06 ✅ trong khi task còn REVIEW → để 🟨 tới khi review đạt.
  - Đã đạt (không cần làm lại): `RemoteStore` + `FakeRemoteStore` trong `test/helpers/`; `toRemoteRow` đúng cột CONTRACTS 3.2/3.3/3.5, không gửi `id`, uuid sai → bỏ dòng (cột khóa) hoặc `null` (cột phụ); RPC null → `ArticleNotFoundException`; cache `bundle_cache` + `article_cards_cache` có fallback; auth chạy sau `runApp`, `ensureProfile` `ignoreDuplicates`; consent mặc định tắt; chặn `flush()` chạy chồng; reader lấy `SyncService` trong `initState`, `dispose` gọi `unawaited(flush())`; lifecycle observer ở `ReadleApp`; Home có trạng thái tải/lỗi nhẹ nhàng ("Chưa tải được bài, thử lại khi có mạng nhé."), không số liệu/streak; H-008, R-FE-05 (c).
  - Đã kiểm: `flutter analyze` No issues · `flutter test` 57/57 pass (chạy độc lập run #44) · grep key trong `app/lib`, `app/test`, `app/assets`: sạch · `app/env/dev.json` nằm trong `.gitignore` · phạm vi commit 448d4fb: `app/**` + docs được phép · review tĩnh, chưa chạy trên thiết bị.



- [R-FE-06b] (run #46) Review lại FE-06 (commit 7d103c7): **CODE ĐẠT · chờ chạy thật**
  - (1) đã sửa đúng: `AppConfig.useSupabase` + `supabaseReady` (chỉ bật sau `Supabase.initialize` thành công); `remoteStoreProvider`, `articleRepositoryProvider`, `syncServiceProvider` dùng chung điều kiện, ngoài ra rơi về `_NoopRemoteStore` + fixture; có test. Góp ý (a) try riêng từng luồng, (c) PROGRESS trùng + ARCHITECTURE 🟨: đã làm. (b) `markClean` của saved word: vẫn để FE-08.
  - (2) chưa kiểm được: môi trường Antigravity không có máy ảo → **người dùng chạy 4 bước (Q-017)**; Claude kiểm `reading_history` trên cloud bằng SQL sau đó, đạt thì chuyển DONE.
  - Bảo mật: `app/env/dev.json` gitignored, không có trong commit; key là JWT `role: anon` (đã kiểm, không in key); URL không có `/rest/v1`.
  - Nên sửa (không chặn): `AppConfig.supabaseReady` là biến tĩnh toàn cục, test đặt `= false` mà không trả lại → nếu sau này có test đặt `true` thì thứ tự chạy test ảnh hưởng kết quả; thêm `addTearDown` trả về giá trị cũ.
  - Đã kiểm: `flutter analyze` No issues · `flutter test` 58/58 pass (chạy độc lập run #46) · phạm vi commit 7d103c7: `app/**` + docs được phép.
- [R-FE-08] (run #56) Review FE-08 (commit 09ba484): **ĐẠT**
  - Bắt buộc sửa: không có.
  - Nghiệm thu: (1) "Đã lưu" theo `lemma_key` + không tạo bản trùng + giữ `source_article_id` — đạt (AC-4, dùng `vital role` thay `in moderation`, cùng logic); (2) chạm "role" → 2 nút Lưu ở 2 khối cụm, dòng từ đơn không có — đạt (AC-1); (3) tooltip → `lemma_key`, `single_word`, `lexiconEntryId == null`, `from = tooltip` — đạt (AC-2, dùng `folate`); (4) `tend to` → `collocation`, `carotenoid` → `single_word` — đạt (AC-3); (5) upsert có `entry_type` — đạt; (6) góp ý [R-FE-04b] (a)(b)(d), [R-FE-04d] (a), [R-FE-06] (b) — đã làm; fixture app giống hệt `fixtures/` (cmp).
  - Contract: `word_saved { lemma_key, kind: lexicon|glossary, from }`, `word_unsaved { lemma_key }` đúng mục 4; tooltip `display_text` = lemma viết thường; bỏ lưu = soft delete, lưu lại dùng lại bản ghi (giữ `source_article_id`, SRS); cập nhật snapshot chỉ khi nội dung đổi — đúng H-013 (5)(6).
  - Nên sửa (không chặn; làm kèm FE-09 vì FE-09 cũng đụng `SavedWord`):
    - (a) `local_models.dart` `fromMap`: thiếu `entry_type` + có `lexicon_entry_id` → đang mặc định **`collocation`**, sai cho mục từ đơn (vd `carotenoid`). Task/H-013 (2): không tra được thì `single_word`. Sửa: mặc định `single_word`, và trong `updateSnapshotIfSaved` gán luôn `lexiconEntryId` + `entryType` theo `entry` (sửa bản ghi cũ khi mở sheet; đồng thời làm H-013 (8)). Không chặn vì trước FE-08 nút Lưu chưa nối nên thực tế chưa có bản ghi cũ nào.
    - (b) `markClean` (`_isSameContent`) không so `cloze` (H-013 (7) gợi ý so `toMap()` trừ `dirty`). Hiện vô hại vì cloze đổi luôn kèm câu đổi, nhưng thêm trường sau này dễ sót.
    - (c) Nút Lưu tooltip `minWidth/minHeight: 40` → nâng lên 44 như các nút khác ([R-FE-04b] (c)); thêm `Semantics(label: isSaved ? 'Đã lưu' : 'Lưu')` vì chỉ có icon.
    - (d) Test AC-2 chỉ kiểm `exampleSentence` chứa "folate"; thêm `expect(cloze.textBefore + answer + cloze.textAfter, exampleSentence)` và 1 ca token biến hình (lemma ≠ text, vd "foods" → `lemma_key = "food"`, `answer = "foods"`) theo H-013 (3).
    - (e) `lemma_key` tooltip chưa NFC (Dart không có sẵn; lemma tiếng Anh ASCII nên chưa ảnh hưởng) — ghi chú, không cần thêm thư viện lúc này.
  - No-pressure: không snackbar/đếm số từ đã lưu; nhãn "Lưu"/"Đã lưu" trung tính; sheet vẫn đúng thứ tự ADR-010.
  - Bảo mật: grep `service_role`/`AZURE`/`sk-` trong `app/lib`, `app/test` sạch. Phạm vi commit 09ba484: `app/**` + docs được phép.
  - Đã kiểm: `flutter analyze` No issues · `flutter test --timeout 60s` 74/74 pass (chạy độc lập run #56). Chưa chạy trên thiết bị: nên thử thật lưu `play a vital role in` ở Eating Well rồi mở Robots (cloud đã có 2 bài dùng chung mục này, H-014) → "Đã lưu", và kiểm `user_saved_words` trên cloud có `entry_type`.

- [H-016] (run #57, Claude → Antigravity) Người dùng muốn điều hướng giống app đọc báo (mẫu Dribbble "Modern News App UI"): **ADR-020**. FE-07 cũ được thay bằng **FE-07a → FE-07b → FE-07c / FE-07d** (a trước, vì cùng sửa `app.dart`). Lưu ý: (1) không có ảnh bìa, thẻ bài là khối màu theo chủ đề; (2) màn đọc + sheet/tooltip **giữ nguyên** bảng màu giấy, chỉ khung 4 tab đổi sang trung tính; (3) thanh tab không badge/đếm; (4) không có tab tải ảnh, không tên "Dashboard". Góp ý [R-FE-08] vẫn làm kèm FE-09 như cũ. **Cần:** làm FE-07a trước.

- [H-017] (run #58, Claude → Antigravity) **ADR-021: bài người dùng tự tải, làm sau MVP.** Contract **không đổi** lúc này: CONTRACTS mục 6 là **bản nháp 1.5, chưa áp dụng**; `CONTRACT_VERSION` vẫn `1.4`, fixture chính không đổi, **không chép** `fixtures/user_article_sample.json` / `lookup_samples.json` vào app cho tới BE-14b. Việc ảnh hưởng ngay tới task đang có:
  1. **FE-07c:** thêm việc 6 "luật khớp": provider gộp chỉ tính progress có `articleId` trong `article_cards` (áp cho "Đọc tiếp", "Đã đọc X bài", `/history`), hàm khớp nhận `Set<String>` để FE-16 mở rộng; + 1 widget test bản ghi mồ côi.
  2. **FE-09:** làm kèm [R-FE-09-pre]: `SavedWord.toRemoteRow` không được bỏ cả dòng khi `source_article_id` không phải uuid; gửi `null` cho cột này (đúng luật R-FE-06: cột khóa sai mới bỏ dòng). Đây là chỗ Claude bỏ sót khi review R-FE-06.
  Các task FE-16, FE-16s, FE-16b, FE-17 đều phụ thuộc FE-14 (và BE-14b), **chưa làm**.

- [R-FE-07a] (run #63) Review FE-07a (commit c036348): **ĐẠT**
  - Nghiệm thu: (1) 4 nhãn tab, chạm "Bài báo" thấy "Eating Well", không "Dashboard", không `settings_outlined` — đạt; (2) mở bài → không `NavigationBar`, nền `#E8DDBD`, `pop` về tab Bài báo có thanh tab — đạt; (3) chạm "tend" → sheet theo theme giấy (`surface` `#F2EBD3`), test sheet/tooltip cũ pass — đạt (sheet dùng `context` của `itemBuilder` nằm dưới `Theme` nên `showModalBottomSheet` lấy đúng theme giấy; `readerLight/Dark` có `bottomSheetTheme`); (4) dark: khung `#121212`, màn đọc `#171310` — đạt; (5) không `Badge(` trong `features/shell`, analyze sạch, test pass — đạt. Bảng giấy chép nguyên giá trị cũ, giữ `HighlightColors`.
  - Bắt buộc sửa: không có.
  - Nên sửa (không chặn; làm ở task FE kế tiếp có sửa `reader_screen.dart`, hoặc kèm FE-07b vì chỉ 2 dòng):
    - (a) **Tooltip chưa ăn theme giấy.** `reader_screen.dart:146-189`: `OverlayEntry` được dựng trong Overlay của navigator gốc, nằm **trên** widget `Theme(readerTheme)`, nên `Theme.of(ctx)` trong `WordTooltip` là theme **khung**. Nền tooltip không lệch (mã cứng `#FAF6EE`/`#28211A`), nhưng chữ (`onSurface` `#18181B` thay vì `#2E2A23`) và loa/nút Lưu (`primary` `#18181B` thay vì `#2C3E50`) đổi màu so với trước FE-07a. Sửa: lấy `final readerTheme = Theme.of(context);` trước khi tạo entry rồi bọc `builder: (ctx) => Theme(data: readerTheme, child: Consumer(...))` (hoặc `InheritedTheme.capture(from: context, to: Overlay.of(context).context).wrap(...)`). Thêm 1 test: chạm "health" → `Theme.of(tester.element(find.byType(WordTooltip))).colorScheme.surface == AppColors.readerSurfaceLight`.
      - **Nền tooltip (người dùng chốt sau run #63):** **không** đổi nền sang `colorScheme.surface` của theme giấy (sẽ trùng màu card `#F2EBD3`). Sáng: giữ `#FAF6EE`. Tối: đổi `#28211A` → **`#3A3128`** (nền cũ gần trùng card tối `#241D16`, chỉ phân biệt nhờ viền). Giữ viền + bóng như hiện tại. Đưa 2 màu này thành hằng trong `app_colors.dart` (`readerTooltipLight`/`readerTooltipDark`) thay vì mã cứng trong `word_tooltip.dart:43-44`.
    - (b) Test AC-3 chỉ kiểm `Theme.of` trong sheet; nên kiểm thêm màu nền thật của sheet (`tester.widget<BottomSheet>(find.byType(BottomSheet)).backgroundColor` hoặc `Material` tổ tiên gần nhất) để bắt trường hợp sheet tự đặt màu.
    - (c) AC-5 "Trang chủ/Hồ sơ không hiển thị số nào" chỉ được kiểm qua `Badge`. Thêm: ở Trang chủ và Hồ sơ, `find.textContaining(RegExp(r'\d'))` → `findsNothing` (lưu ý phụ đề Hồ sơ hiện có "(FE-11)", "(FE-12)", xem (d)).
    - (d) `profile_screen.dart:64,70`: phụ đề hiển thị mã task "(FE-11)", "(FE-12)" cho người dùng (có từ màn Cài đặt cũ). Bỏ phần mã task, vd "Tùy chọn nhẹ nhàng, không áp lực" / "Xem lại các mẹo đọc"; để FE-11/FE-12 làm thật.
    - (e) `app.dart`: `_rootNavigatorKey` là biến toàn cục cấp file, dùng chung cho mọi `GoRouter` mà `routerProvider` tạo ra. Nếu sau này có 2 router sống cùng lúc (vd test dựng 2 `ProviderScope`) sẽ lỗi `Duplicate GlobalKey`. Chuyển `GlobalKey` vào trong `routerProvider`.
    - (f) `reader_screen.dart:335-435`: phần bọc `Theme`/`Builder` chưa chạy `dart format` (thân `Scaffold` lệch thụt lề). Chạy `dart format lib/features/reader/screens/reader_screen.dart`.
    - Ghi chú: nút "Xem các bài báo" dùng `context.go('/news')` thay vì `goBranch`; với `StatefulShellRoute` hai cách tương đương (giữ trạng thái nhánh), giữ nguyên được.
  - No-pressure: thanh tab không badge/chấm; Trang chủ chỉ có câu chào + nút; Hồ sơ không số liệu/streak, dòng đăng nhập là chữ tĩnh, không nút giả; Đã lưu chỉ còn nút "Ôn tập từ vựng", không đếm từ/thẻ quá hạn.
  - Bảo mật: grep `service_role`/`AZURE`/`sk-` trong `app/lib`, `app/test`, `app/assets`: sạch.
  - Phạm vi: mọi file `app/**` trong commit đều nằm trong danh sách "Được sửa"; docs: TASKS (cột trạng thái FE-07a), ARCHITECTURE (mục 4 + changelog), HANDOFF, PROGRESS — đúng quyền. Dòng BE-06c trong TASKS của commit là của Claude.
  - Đã kiểm: `flutter analyze` No issues · `flutter test --timeout 60s` 80/80 pass (chạy độc lập run #63) · review tĩnh UI, chưa chạy trên thiết bị (nên thử thật: chạm 1 từ thường trong bài để xem màu chữ tooltip, xem (a)).

- [R-FE-07b] (run #65) Review FE-07b (commit 10ae14e): **ĐẠT**
  - Nghiệm thu: (1) 5 tiêu đề, Eating Well có "A2" + "~4 phút đọc" (566/150 = 3.77 → 4), nền khối `#DCEFD8` qua `ValueKey('article_cover_…')` — đạt; (2) "Science & Technology" → Robots + Rocket Science, thêm "B2" → Rocket Science, "Tất cả" + "Mọi cấp độ" → 5 bài; có thêm ca rỗng — đạt; (3) Eating Well `completed` → "Đã đọc" + `check_circle_outline`, Robots → "Đang đọc", `textContaining('%')` không có — đạt; (4) "Travel" → `#ECECEC` + `article_outlined`, "energy" khớp Energy (cả dark) — đạt; (5) không "chưa đọc", không đếm bài, analyze sạch, test pass — đạt. Thêm 2 test tốt: tự cập nhật "Đang đọc" sau khi đọc rồi `pop`; lưới 2 cột ở 800dp + `textScaler 1.3` không tràn.
  - [R-FE-07a] (a)–(f): đã kiểm từng mục trong diff — tooltip bọc `Theme(data: readerTheme)` lấy từ `context` của `itemBuilder`, nền dùng hằng `readerTooltipLight/Dark` (`#3A3128` đúng chốt), sheet kiểm màu `Material` thật, test "không chữ số" ở Trang chủ/Hồ sơ, bỏ "(FE-11)/(FE-12)", `GlobalKey` trong `routerProvider`, reader đã format (diff `-w` chỉ còn 2 chỗ đổi logic).
  - Bắt buộc sửa: không có.
  - Nên sửa (không chặn):
    - (a) **Báo trước cho FE-07c:** test `app_shell_test.dart` AC-5 (thêm ở run #64 theo [R-FE-07a] (c)) khẳng định Trang chủ **không có chữ số nào**. FE-07c sẽ thêm "Đã đọc X bài · Đã lưu Y từ" và "Đoạn x / n" nên test này sẽ đỏ. Khi làm FE-07c: giữ assert cho Hồ sơ, đổi assert Trang chủ thành "chỉ có đúng dòng 2 con số" (vd: mọi `Text` chứa chữ số đều khớp `^Đã đọc \d+ bài · Đã lưu \d+ từ$` hoặc nằm trong thẻ "Đọc tiếp"), không xóa hẳn.
    - (b) **FE-07c dùng lại cách làm mới trạng thái:** `progressByArticleProvider` chỉ được `invalidate` sau `push` từ `NewsScreen`. Trang chủ ("Đọc tiếp", dòng số) và `/history` mở màn đọc từ chỗ khác nên cũng phải `invalidate` sau `await context.push(...)`. Gọn hơn: tách hàm dùng chung (vd `openArticle(context, ref, id)`) trong `features/library/` để 3 chỗ gọi cùng một đường.
    - (c) `article_tile.dart:35-37`: `Semantics(button: true, label: card.title)` không `excludeSemantics`, nên trình đọc màn hình đọc tiêu đề 2 lần rồi đọc rời từng mảnh (category, "A2", "·", "~4 phút đọc"…). Gợi ý: `excludeSemantics: true` + `label: '${card.title}, ${card.category}, ${card.cefrLevel}, khoảng $minutes phút đọc${trạng thái}'`. Test AC-1 dùng `contains('Eating Well')` vẫn đúng.
    - (d) `category_style.dart:15-16`: getter `$1`/`$2` giả record là thừa; task ghi kiểu record nhưng class có tên `bg`/`icon` đã rõ hơn. Bỏ 2 getter khi tiện (không ai dùng).
    - (e) Test dark ở `app_shell_test.dart` có tên "…tooltip ăn theme giấy tối" nhưng chỉ kiểm `colorScheme.surface`; nên kiểm thêm nền thật `#3A3128` (vd `Container`/`DecoratedBox` gốc của `WordTooltip`) như bản sáng.
  - No-pressure: chip CEFR viền trung tính, không tô theo độ khó; không %, không "Chưa đọc", không đếm số bài; trạng thái chỉ hiện khi có progress; câu lọc rỗng nhẹ nhàng.
  - Bảo mật: grep `service_role`/`AZURE`/`sk-`/JWT trong `app/` chỉ trúng `app/env/dev.json` — đã nằm trong `.gitignore` (`app/env/*.json`), không được git theo dõi.
  - Phạm vi: `app/**` ngoài danh sách "Được sửa" (`app.dart`, `local_providers.dart`, `reader_screen.dart`, `word_tooltip.dart`, `profile_screen.dart`, `app_shell_test.dart`) đều do [R-FE-07a] yêu cầu hoặc cần cho tự cập nhật trạng thái; đã ghi trong PROGRESS #64 — chấp nhận. Docs: đúng quyền.
  - Đã kiểm: `flutter analyze` No issues · `flutter test --timeout 60s` 87/87 pass (chạy độc lập run #65) · review tĩnh UI, chưa chạy trên thiết bị (nên thử thật dark mode: icon trên khối màu tối và chip CEFR còn đủ tương phản).
- [H-018] (run #66, Claude → Antigravity) Task mới **FE-07e** (nhỏ): thêm chủ đề thứ 5 "Travel & Money" (nền `#FBE3D2` / tối `#3E2B20`, `flight_outlined`) cho bài `holiday-travel` sắp seed. Chỉ sửa `app_colors.dart`, `category_style.dart`, `news_screen_test.dart`, không đụng file của FE-07c đang làm. **Cần:** làm sau FE-07c (hoặc xen giữa nếu tiện).

- [R-FE-07c] (run #71) Review FE-07c (commit 008c4da): **ĐẠT**
  - Nghiệm thu: (1) "Đọc tiếp" Robots + "Đoạn 3 / 7", bấm → `/read/art_robots` — đạt (AC-1); (2) không progress → không có "Đọc tiếp", dòng "Đã đọc 0 bài · Đã lưu 0 từ" — đạt (AC-2); (3) "Đã đọc 1 bài · Đã lưu 2 từ" (bản `deleted` không tính vì `SavedWordsNotifier` nạp `includeDeleted: false`), chạm → `/history` 2 nhóm — đạt (AC-3); (4) "Xem tất cả" → tab Bài báo — đạt (AC-4); (5) bản ghi mồ côi không đếm, không hiện, không bị xóa khỏi Hive — đạt về hành vi, test yếu hơn mô tả (xem (a)); (6) no-pressure + analyze + test — đạt.
  - Luật khớp ADR-021 điểm 6: `filterMatchedProgress(Iterable, Set<String>)` + `buildLibraryOverview(extraKnownArticleIds)` dùng chung cho "Đọc tiếp", X và `/history` → 3 chỗ luôn khớp; FE-16 chỉ cần truyền thêm id `user_articles` (lưu ý: vòng lặp hiện bỏ progress không có `card` trong `cardsById`, FE-16 phải tra thêm tiêu đề/`section_count` từ Hive).
  - [R-FE-07b] (a), (b): đã làm — assert số ở Trang chủ đổi thành "chỉ 2 định dạng" thay vì xóa; `openArticle` dùng chung cho 3 chỗ, `NewsScreen` chuyển sang dùng nó.
  - Bắt buộc sửa: không có.
  - Nên sửa (không chặn, làm kèm FE-16 vì FE-16 mở rộng luật khớp):
    - (a) `app/test/features/library/home_history_test.dart:437-481` — nghiệm thu ghi "thêm 1 progress `completed` mồ côi **vào dữ liệu mẫu** → vẫn 'Đã đọc 1 bài'", test hiện chỉ có bản mồ côi (0 bài) nên không bắt được lỗi kiểu "đếm cả mồ côi lẫn bài thật"; `find.text('art_deleted_from_cloud')` luôn rỗng vì màn không bao giờ in id. Thêm ca: Eating Well `completed` + mồ côi `completed` → "Đã đọc 1 bài", `/history` nhóm "Đã đọc" đúng 1 dòng.
    - (b) `home_screen.dart:79`, `history_screen.dart:44` — "Thử lại" chỉ `invalidate(articleListProvider)`; nếu lỗi đến từ `progressByArticleProvider` thì bấm không có tác dụng. Invalidate cả `progressByArticleProvider` (hoặc `libraryOverviewProvider` cùng 2 nguồn).
    - (c) `home_screen.dart:23` — `savedWordsNotifierProvider` khởi tạo `{}` rồi nạp bất đồng bộ, nên mở app có thể thấy "Đã lưu 0 từ" chớp sang số thật. Nhỏ; xem khi polish FE-15.
  - No-pressure: Trang chủ chỉ 2 con số + vị trí "Đoạn x / n" (không %), không streak/ngày/badge; khối "Đọc tiếp" ẩn hẳn khi không có bài dở; lỗi và Lịch sử rỗng dùng câu nhẹ; CEFR trong Lịch sử là chữ trung tính.
  - Bảo mật: grep `service_role`/`AZURE`/`sk-`/JWT trong `app/` chỉ trúng `app/env/dev.json` (gitignored, không được theo dõi, chỉ anon key).
  - Phạm vi: ngoài danh sách "Được sửa" có `open_article.dart` (do [R-FE-07b] (b) gợi ý), `news_screen.dart` (dùng hàm chung), `app_shell_test.dart` (task cho phép), `widget_test.dart` (đổi nhãn nút) — đã ghi trong PROGRESS #67, chấp nhận. Docs đúng quyền.
  - Đã kiểm: `flutter analyze` No issues · `flutter test --timeout 60s` 96/96 pass (chạy độc lập run #71) · review tĩnh UI, chưa chạy trên thiết bị.
- [H-019] (run #73, Claude → Antigravity) Supabase local + cloud giờ có **8 bài** (thêm ai-chatbots, curry-chicken, holiday-travel; `processing_order` 6-8). Bài holiday-travel có `category` "Travel & Money" → đang hiện màu trung tính tới khi xong FE-07e (H-018). Thẻ Trang chủ "Bài mới" (tối đa 5) giờ bắt đầu từ 3 bài này. **Cần:** không có việc mới; dùng dữ liệu thật này khi chạy thử FE-07d/FE-07e.

- [H-020] (run #76, Claude → Antigravity) Seed lại 7 bài (local + cloud): chỉ đổi `cefr_level` của 13 mục từ (vd `launch` B2 → B1, `pest` B2 → C1) + IPA token "chatbot" ở robots; contract **không đổi**. App đang giữ `bundle_cache` cũ thì thấy cấp cũ tới khi tải lại bài; snapshot trong `saved_words` giữ cấp lúc lưu (đúng H-013). **Cần:** không có việc.

- [H-021] (run #78, Claude → Antigravity) Task mới **FE-07f** (nhỏ, giống FE-07e): chủ đề thứ 6 "Places & Culture" cho bài `paris` sắp seed (màu **`#F6DCE5`/`#3D2632`**, đã sửa run #81). Làm **sau FE-07e** (cùng 3 file). **Cần:** làm khi xong FE-07e.

- [R-FE-07d] (run #80) Review FE-07d (commit 021fa8d): **ĐẠT**
  - Nghiệm thu: (1) mặc định "Cụm từ" → `play a vital role in`, `tend to` dưới "Eating Well", không `carotenoid`, không bản `deleted` — đạt (AC-1 + unit test `groupSavedWords`); (2) "Từ đơn" → `carotenoid` (Eating Well), `health` (Robots, `lexiconEntryId = null`) — đạt; (3) chạm `tend to` → câu ví dụ in nghiêng; bỏ lưu → dòng biến mất, `isSaved == false`, hàng đợi có `word_unsaved { lemma_key }` — đạt; (4) "Ôn tập từ vựng" → `/review` không `NavigationBar` — đạt; (5) no-pressure + analyze + test — đạt.
  - Contract: `word_unsaved` payload đúng mục 4 (`{ lemma_key }`); bỏ lưu từ tab Đã lưu gửi `article_id`/`section_id` = null — hợp lệ (`usage_events.article_id uuid null`), BE-08 phân biệt được bỏ lưu ngoài màn đọc. Dùng lại đúng luồng soft delete của FE-08 (`unsaveWord` tách từ 2 hàm toggle, chữ ký cũ giữ nguyên).
  - Bắt buộc sửa: không có.
  - Nên sửa (không chặn; làm kèm FE-15, hoặc FE-16 với mục (d)):
    - (a) `saved_screen.dart` `_buildBody`: `AsyncValue<dynamic> articleListAsync` + `card.id as String`, `card.title as String` trên `dynamic` → analyzer không bắt được nếu `ArticleCard` đổi tên trường. Khai báo `AsyncValue<List<ArticleCard>>` và dùng `card.id`/`card.title` có kiểu.
    - (b) `saved_word_tile.dart`: `Semantics(button: true, label: 'Bỏ lưu')` bọc `IconButton(tooltip: 'Bỏ lưu')` → trình đọc màn hình đọc "Bỏ lưu" 2 lần (tooltip của `IconButton` đã là nhãn). Bỏ `Semantics` ngoài (giữ `tooltip`); `ConstrainedBox(44)` cũng thừa vì `IconButton` mặc định 48dp.
    - (c) `onUnsave` gọi `unsaveWord(...)` không `await`/không bắt lỗi → lỗi Hive bị nuốt im lặng. Dùng `unawaited(...)` có `catchError` + `debugPrint` (giống [R-FE-05] (c)).
    - (d) Tên nhóm chỉ lấy từ `article_cards`; FE-16 phải thêm tiêu đề `user_articles` vào `articleTitles`, nếu không từ lưu ở bài tự tải sẽ rơi vào "Bài khác" (cùng ý [R-FE-07c] về luật khớp).
    - (e) Lần mở đầu khi `articleListProvider` còn đang tải, cả danh sách hiện vòng xoay dù từ đã lưu nằm sẵn trong Hive. Có thể hiện danh sách ngay rồi điền tên nhóm sau (nhỏ, FE-15).
    - (f) Test AC-5 chỉ kiểm "không chữ số" ở trạng thái rỗng; nên kiểm thêm khi có dữ liệu (tiêu đề nhóm, đầu màn, nhãn segment — trừ chữ của chính mục từ).
  - No-pressure: không đếm từ/thẻ/quá hạn; nút ôn không kèm số; câu rỗng nhẹ, đúng chữ của task; lỗi tải bài không hiện lỗi mà gộp "Bài khác"; bỏ lưu không hỏi lại, không snackbar.
  - Bảo mật: grep `service_role`/`AZURE`/`sk-` trong `app/lib`, `app/test`: sạch.
  - Phạm vi: ngoài `features/saved/` chỉ có `reader/providers/saved_words_provider.dart` (tách `unsaveWord`, task yêu cầu dùng lại luồng FE-08) — chấp nhận, đã ghi trong PROGRESS #77. Docs đúng quyền.
  - Đã kiểm: `flutter analyze` No issues · `flutter test --timeout 60s` 106/106 pass (chạy độc lập run #80, trên HEAD gồm cả FE-07e) · review tĩnh UI, chưa chạy trên thiết bị.

- [R-FE-07e] (run #81) Review FE-07e (commit 9aacabc): **ĐẠT**
  - Nghiệm thu: (1) `'Travel & Money'` sáng → `#FBE3D2` + `flight_outlined`, `'travel & money'` tối → `#3E2B20`, có ca `trim` — đạt; (2) `"Sports"`, `"Travel"` ra màu trung tính + `article_outlined` ở cả sáng và tối (đã sửa cả bản tối dòng 163 cũ) — đạt; (3) widget test dùng `buildNewsTestWidget(cards: [...sampleFiveCards, holidayCard])` (không sửa danh sách chung): khối `#FBE3D2`, icon trong khối, chip "Travel & Money" lọc ra đúng 1 bài — đạt; (4) analyze sạch, toàn bộ test pass — đạt.
  - Kèm [R-FE-07b] (c): `excludeSemantics: true` + nhãn "tiêu đề, chủ đề, cấp, khoảng N phút đọc[, Đang đọc | Đã đọc]", có test cả 3 trạng thái; (d): bỏ getter `$1/$2`. Đúng 4 góp ý plan của người dùng (danh sách riêng, dòng 163, `final p = progress`, ca semantics có progress).
  - Bắt buộc sửa: không có.
  - Nên sửa (không chặn, FE-15): nhãn trợ năng đọc "A2"/"B2" trơn; có thể thêm "cấp độ" ("…, cấp độ B2, khoảng 9 phút đọc") cho người dùng trình đọc màn hình dễ hiểu.
  - **Lưu ý cho FE-07f (Claude sửa task, run #81):** màu "Places & Culture" đổi thành **`#F6DCE5` / tối `#3D2632`** (hồng nhạt). Bản đầu `#E7E1F4`/`#2D2840` gần trùng Energy (`#E6E0F5`/`#2D2843`) — lỗi khi Claude viết task. Icon giữ `account_balance_outlined`.
  - No-pressure: không thêm số/%; nhãn trạng thái giống chữ đang hiển thị.
  - Bảo mật: grep `service_role`/`AZURE`/`sk-` trong `app/lib`, `app/test`: sạch.
  - Phạm vi: `article_tile.dart` ngoài danh sách 3 file nhưng task mục 4 cho phép ([R-FE-07b] (c)) — chấp nhận. Docs đúng quyền.
  - Đã kiểm: `flutter analyze` No issues · `flutter test --timeout 60s` 106/106 pass (chạy độc lập trên HEAD, run #80-#81) · `flutter test test/features/library` 18/18 · review tĩnh UI, chưa chạy trên thiết bị.

- [R-FE-07f] (run #86) Review FE-07f (commit 6f3910f): **ĐẠT**
  - Nghiệm thu: (1) `'Places & Culture'` sáng → `#F6DCE5` + `account_balance_outlined`, `' places & culture '` tối → `#3D2632`, khác Energy ở cả 2 chế độ — đạt; (2) `"Places"`, `"Culture"` đứng riêng → `#ECECEC`/`#2A2A2A` + `article_outlined` — đạt; (3) widget test thẻ Paris: khối `#F6DCE5`, icon trong khối, chip "Places & Culture" lọc ra đúng 1 bài, nhãn trợ năng đúng — đạt; (4) analyze sạch, toàn bộ test pass — đạt.
  - Dữ liệu test khớp bài thật: `pipeline/out/paris/bundle.json` có `word_count` 933, `category` "Places & Culture" (đúng từng ký tự với nhánh `switch`).
  - Bắt buộc sửa: không có.
  - Nên sửa (không chặn): lần sau chỉ đổi cột trạng thái trong TASKS (AGENTS.md mục 1); ô `[x]` nghiệm thu trong phần chi tiết task để Claude đánh khi review. Lần này giữ nguyên vì đúng kết quả.
  - Phạm vi: 3 file `app/**` đúng danh sách "Được sửa"; dòng BE-02d → DOING trong TASKS của commit là của Claude run #84 (người dùng commit chung).
  - No-pressure: chỉ thêm màu/icon, không số/badge.
  - Bảo mật: grep `service_role`/`AZURE`/`sk-` trong `app/lib`, `app/test`: sạch.
  - Đã kiểm: `flutter analyze` No issues · `flutter test --timeout 60s` 108/108 pass (chạy độc lập run #86) · review tĩnh UI, chưa chạy trên thiết bị (nên mở tab Bài báo với dữ liệu thật để xem thẻ Paris hồng nhạt, cả dark mode).

- [R-FE-09] (run #89) Review FE-09 (commit e2825d6): **ĐẠT**
  - Nghiệm thu: (1) giới hạn 5 mới / 20 ôn — đạt (30 đến hạn + 12 mới → 20 + 5; đã ôn 15 → còn 5; quota không âm); (2) Again/Good/Easy đúng bảng skill `flutter-srs` mục 1 — đạt (Good ×3 → 1/3/8, Easy → 3 + ease 2.65, Again sau 3 Good → reps 0/interval 1/ease 2.3, sàn 1.3, trần 180, `firstReviewedAt` chỉ gán lần đầu); (3) nghỉ 10 ngày với 100 thẻ đến hạn → 20 — đạt. Đủ 7 ca tối thiểu của skill mục 5, thêm ca sắp xếp `savedAt`, bỏ `deleted`, chưa đến hạn.
  - [R-FE-08] (a)–(d) + [R-FE-09-pre]: đã kiểm từng mục trong diff + test. `toRemoteRow` luôn trả Map, `source_article_id`/`lexicon_entry_id` qua `sanitizeUuidOrNull`, `entry_type` khớp check constraint migration 1.4; `_isSameContent` so đủ trường gồm cloze, `lexiconEntryId`, `entryType` và các trường SRS → `rate()` ở FE-10 không bị `markClean` gỡ `dirty` nhầm.
  - Bắt buộc sửa: không có.
  - Nên sửa (không chặn, làm kèm FE-10):
    - (a) `srs_engine.dart:69` `todayDate.add(Duration(days: n))` cộng theo giờ: ở múi giờ có giờ mùa hè, ngày đổi giờ cho ra 23:00 hôm trước → `due_date` lệch 1 ngày. Dùng `DateTime(todayDate.year, todayDate.month, todayDate.day + newInterval)`. Việt Nam không đổi giờ nên hiện chưa lỗi.
    - (b) Nhánh `reps ≥ 3` lấy `card.intervalDays × ease`: bản ghi lạ (vd `intervalDays` 0 do dữ liệu cũ/đồng bộ) → interval 0, thẻ đến hạn lại ngay hôm nay. Nên kẹp `max(1, …)`.
    - (c) **Cho FE-10:** `buildTodayQueue` cần `reviewedTodayCount`/`newReviewedTodayCount`, nhưng chưa có chỗ lưu số thẻ đã ôn trong ngày. FE-10 lưu bộ đếm theo ngày (Hive, khóa `yyyy-MM-dd` giờ máy) hoặc đếm từ thẻ có lần ôn cuối là hôm nay; không hiển thị số này cho người dùng (no-pressure).
  - No-pressure: engine không có số quá hạn/streak; thẻ vượt quota tự rải sang ngày sau; tooltip chỉ đổi vùng chạm + nhãn trợ năng.
  - Bảo mật: grep `service_role`/`AZURE`/`sk-` trong `app/lib`, `app/test`: sạch.
  - Phạm vi: `srs_engine.dart` mới + các file do [R-FE-08]/[R-FE-09-pre] yêu cầu (`local_models`, `local_storage_repository`, `sync_service`, `saved_words_provider`, `word_tooltip`, test) — đúng. Docs đúng quyền.
  - Đã kiểm: `flutter analyze` No issues · `flutter test --timeout 60s` 121/121 pass (chạy độc lập run #89) · review tĩnh, chưa chạy trên thiết bị (FE-09 chưa có UI).

- [H-023] (run #92, Claude → Antigravity) **Làm mới khung app 4 tab (ADR-023).** Người dùng gửi mockup sáng/tối + spec; Claude tách thành **FE-18a → FE-18b → FE-18c → FE-18d**, làm **trước FE-10** (người dùng chốt). Đọc mục chung "Làm mới khung app 4 tab" trong TASKS trước mục từng task. Lưu ý:
  1. **Màn đọc, sheet, tooltip, màu tô từ, font Inter của màn đọc: không đổi.** Test kiểm nền giấy + Inter trong màn đọc phải còn pass.
  2. `ink2` sáng là **`#5F6673`** (spec gốc ghi `#6B7280`, chỉ đạt 4.07-4.38:1 trên `accentSoft`/`surface`, Claude đổi; xem ADR-023 điểm 1).
  3. Icon chủ đề đổi: Health → `eco_outlined`, Food → `grass_outlined` (4 chủ đề còn lại giữ). Font Be Vietnam Pro: tải 4 file TTF tĩnh + `OFL.txt` từ Google Fonts vào `app/assets/fonts/` (asset, không thêm package).
  4. Dòng "Đã đọc X bài · Đã lưu Y từ" chuyển từ Trang chủ sang Hồ sơ (FE-18b). Card "Sắp có" ở Trang chủ: nút tắt, không event.
  5. Màn `/saved/:articleId` (FE-18d): loa dùng TTS đọc `display_text`, **không** phát `audio_played` (contract chưa có `source` cho màn này, BE-14b sẽ thêm `saved_list`).
  **Cần:** làm FE-18a trước.

- [H-024] (run #93, Claude → Antigravity) Bài thứ 10 **`pizza`** đã lên **cloud** (`processing_order` 10, **A2**, "Food & Farming" — màu đã có, 10 mục có audio). Local seed khi người dùng bật Docker. **Cần:** không có việc mới; dùng làm dữ liệu thật khi chạy thử FE-18b/c (thẻ "Bài mới", "Nổi bật").

## Antigravity → Claude


## Yêu cầu đổi contract
_(trống)_

## Đã xử lý
- [Q-030] (xử lý run #93) `pizza`: ví dụ `be topped with` → "The cake was topped with fresh fruit.", nghĩa "được phủ lên trên (bằng)"; `toppings` "lớp phủ" mọi card (trừ card 8 "món trên pizza"), `mockba` "Mát-xcơ-va (tên pizza)"; luật tái sử dụng ≤ cấp bài + 2 **chốt** (ADR-017 bổ sung, ngoại lệ `in moderation` ở pizza); IPA `calzone`, `marinara`, `paneer` vào `ipa.json` (đối chiếu Wiktionary; Cambridge/Collins chặn truy cập tự động), `margherita`, `pizzaiola`, `ripieno`, `mockba` để trống. Ghim + audio + seed cloud OK.
- [Q-029] (xử lý run #93) Duyệt `pizza`: Key idea 13/13 đạt (3 câu Claude sửa đúng); mục từ: giữ 8, `variety` → `a variety of`, `preheat oven` → `preheat`, thay `serve`/`frozen` bằng `be topped with`, `be popular with`; quiz câu 3 → "Pizza first came to North America in the 1950s." (False); glossary Greeks/caught on/were/Hawaiian; ví dụ `crust`. Sửa pipeline → task BE-06i.
- [Q-028] (xử lý run #91) `pizza`: 3 sửa OCR đúng; cảnh báo 1a-2 không báo nhầm (ngưỡng hợp lý); bỏ ô chữ/nguyên liệu/"Ask an adult", **giữ** card "Make it yourself" (giới thiệu + 5 bước mệnh lệnh); tiêu đề/thứ tự/chủ đề/nguồn giữ đề xuất; **A2**.
- [A-019] (xử lý run #89) FE-09 review **ĐẠT** → DONE, xem [R-FE-09].
- [Q-027] (xử lý run #87) rocket-science card 11 "one of the most powerful heavy-lift launch vehicles **to** fly successfully": người dùng chọn **"từng"** (so sánh nhất + "to" → "từng bay thành công"; không dùng ngoặc chú thích theo quy ước glossary). Ghi `overrides.json → meanings`, seed lại **cloud + local** OK.
- [A-018] (xử lý run #86) FE-07f review **ĐẠT** → DONE, xem [R-FE-07f].
- [A-017] (xử lý run #81) FE-07e review **ĐẠT** → DONE, xem [R-FE-07e].
- [A-016] (xử lý run #80) FE-07d review **ĐẠT** → DONE, xem [R-FE-07d].
- [Q-026] (xử lý run #78) `fond of`, `make an effort`, `be located` = **B1** (`cefr.json`, nguồn `nguoi-dung-q026`); giữ `fond of` (không định vị được `be fond of`). Người dùng đề xuất **quy luật sàn** cho cụm (cấp cụm ≥ từ nội dung khó nhất theo `cefr_lexicon`, ghi `llm+floor` + ⚠) → đã làm cho bài items-v3.
- [Q-025] (xử lý run #78) Duyệt `paris` lần 1: Key idea sec 1, 2, 4, 6 viết lại; thay `studio`, `electricity`, `dress down` (C1 vào `cefr.json`) bằng `make an effort`, `speak one's mind`, `date back to`; dạng chuẩn `trace one's roots to`, `be located` (`be fond of` không định vị được → Q-026); `home to` định nghĩa mới; `cherish` giữ B1; quiz câu 2 thay bằng câu kiểm hiểu ý; 5 nghĩa glossary (by, to, be, was, distribute); Quick Check: không cần. Gợi ý sửa prompt Key idea + quy tắc glossary bị động/nguyên mẫu → BE-06h.
- [Q-024] (xử lý run #78; run #78, Claude → Người dùng) Bài `paris`: (1) chữ đạt, gồm 2 dòng Claude bổ sung + các sửa OCR; (2) tiêu đề card + cách gộp chú thích đạt; (3) **B1**; (4) chủ đề mới **"Places & Culture"** → FE-07f. Người dùng gợi ý cách kiểm chữ OCR (phóng ảnh, 3 cảnh báo bằng code, LLM chỉ soát) → BE-02d.
- [Q-023] (xử lý run #74; run #74, Claude → Người dùng) Bảng chênh lệch CEFR của `cefr_lexicon_report.md` mục 8-9. **Kết quả (người dùng chốt):** (1) theo CEFR-J: `affordable` B2, `launch` B1, `harness` B1, `exchange rate` B1; `surge` **giữ B2** (C2 là của Octanove, không theo); (2) người dùng tra: `airfare` B2, `pest` C1, `fertilizer` C1, `reservoir` C1, `interface` C1, `interchangeable` C2, `reinvention` C2, `diaspora` C2; 4 mục chưa có nhãn (`hydropower`, `chatbot`, `cross-cultural`, `hole-in-the-wall`) **giữ cấp hiện tại**, không ghi `cefr.json`; (3) **ghi vào `cefr.json` sau BE-06g** (danh sách đầy đủ ở dòng BE-06g trong TASKS), rồi chạy lại + seed các bài bị ảnh hưởng.
- [Q-022] (xử lý run #72-#73; run #68, Claude → Người dùng) BE-06c sau khi áp Q-021: duyệt 9 câu quiz mới, rocket Q3, CEFR 3 mục curry, số mục vượt trần. **Kết quả:** (1) curry Q3 viết lại bám câu "That spirit extends to home kitchens in the diaspora" (True), 8 câu còn lại đạt; (2) rocket Q3 → "Wan Hu's flight attempt was watched by the emperor." (Not Given) — run #72, kèm mốc loại khỏi BE-08; (3) `hands-off`, `fuse with`, `streamlined` = **C1** (người dùng tra Cambridge) — ghi qua `overrides.json` của curry, chưa vào `cefr.json` vì làm đổi prompt (xem BE-06g); (4) giữ ai-chatbots 17 mục, holiday-travel 16 mục và 8 mục B1. Audio 3 bài mới + seed 7 bài local + cloud (run #73). Đề xuất prompt quiz (`evidence`, cấm khái quát hóa) → BE-06g.
- [A-015] (xử lý run #71) FE-07c review **ĐẠT** → DONE, xem [R-FE-07c].
- [R-FE-07b] (a), (b) (xử lý run #67) Antigravity đã áp trong FE-07c; (c)-(e) chuyển sang FE-07e theo H-018.
- [Q-021] (xử lý run #68; run #68, Claude → Người dùng) BE-06c: 3 bài đã enrich (B2), bundle qua `model_validate`, 0 unlocated, glossary đủ nghĩa (39 token điền qua `overrides.json`), Quick Check đã áp trần 3/bài. **Cần duyệt** `pipeline/out/<slug>/review.md` mục 2-4 (Key idea, mục từ, thẻ, Quick Check + quiz) và chốt các đề xuất của Claude:
  1. **ai-chatbots:** (a) bỏ `launch` (`drop_items`): bị kéo lại từ rocket-science nên dùng chung thẻ "send a vehicle into the air or space", trong khi bài này nghĩa là "ra mắt sản phẩm" → thẻ sai nghĩa; (b) Key idea card 1 sai ngữ pháp "Chatbots are many programs and the harness matters most." → "A chatbot is many programs, and the harness matters most."; (c) cân nhắc bỏ 2 cụm nhạt B1 `read documents`, `search the internet` (còn 12 mục, trong khoảng B2 10-15).
  2. **curry-chicken:** Key idea card 1 "I recreate and change restaurant dishes at home." → "The writer recreates restaurant dishes at home." (bài người khác viết, "I" dễ hiểu nhầm là người đọc); card 4 thiếu dấu chấm cuối câu.
  3. **holiday-travel:** 9/15 mục bị LLM xếp B1 (ngoài i+1 của bài B2) — đều là từ chủ đề du lịch dùng được. Đề xuất bỏ 4 mục trùng ý / nhạt: `one-way flights`, `nonstop flights` (đã có `round-trip flights`), `cost of driving`, `skip flying` → còn 11 mục. Giữ `round-trip flights`, `airfares`, `gas prices`, `remain flexible`, `connecting flight` dù B1.
  Sửa Key idea → 1 lời gọi LLM nhỏ để sinh lại nghĩa Key idea của bài đó (các phần khác vẫn cache).
  - **Kết quả:** người dùng duyệt chi tiết 3 bài (thay vì chỉ chốt đề xuất). Đã áp: ai-chatbots giữ `launch` (sửa thẻ dùng chung ở rocket-science cho bao cả nghĩa "ra mắt sản phẩm"), giữ 9 + thêm 8 cụm người dùng chọn (17 mục), bỏ 6 cụm ghép tự do; curry-chicken thay 4 mục bằng `hands-off`, `streamlined` (12 mục); holiday-travel giữ 8 + thêm 8 cụm (16 mục, `be attributed to` → `attributed to`; `hedge one's bets` không định vị được vì bài chen "snow" — ADR-004); 7 Key idea, 3 Quick Check, 6 nghĩa glossary, thẻ `surge`/`chain of thought`/`pop-up kitchen`/`hole-in-the-wall`. Lỗi pipeline người dùng chỉ ra đã sửa bằng code: TFNG thiếu "Not Given", IPA gạch nối, ː trong IPA của LLM, IPA token lấy từ thẻ. Xem PROGRESS #68 và Q-022.
- [Q-020] (xử lý run #66; run #62, Claude → Người dùng) BE-06c: 3 bài PDF đã `assemble` + xếp tay (`structure.json`), `check` OK. **Cần duyệt** 3 file `pipeline/out/<slug>/assemble.md` (mục 5: chữ từng section) đối chiếu PDF, và chốt:
  1. **Phần bị bỏ** (đề xuất bỏ hết): ai-chatbots: dòng tác giả/ngày, 3 "Read more", "Further AI reading" (2 tin ngắn), Topics; curry-chicken: chú thích ảnh đầu bài, đoạn giới thiệu tác giả + ngày, link "Recipe: …", khối "Follow NYT Cooking"; holiday-travel: tác giả/ngày, "See more of our coverage", newsletter, 2 chú thích ảnh, khối "Follow NYT Travel", dòng giới thiệu tác giả cuối bài.
  2. **Tiêu đề section do Claude đặt** (bài không có tiêu đề phụ, hoặc tách card dài): ai-chatbots 9 card (The hidden part of chatbots · The first interfaces · Raw model output · The first guard rails · ChatGPT today · Why the harness matters · Better test scores · Why we rarely hear about it · Can AI improve its own harness?); curry-chicken 8 card (A restaurant dish at home · A high school favorite · Why Portuguese? · Global influences · Nobody knows for sure · The oven trick · A lighter sauce · Always changing); holiday-travel 10 card (giữ 5 tiêu đề gốc "1. Be Flexible"… và thêm: A family trip · Still on the move · Flexible dates and routes · Bus, train or car? · Cruises and rentals).
  3. **Cấp độ + chủ đề + nguồn** (đề xuất): ai-chatbots **B2** (đã chốt Q-014) · "Science & Technology" · New Scientist; curry-chicken **B2** · "Food & Farming" · The New York Times; holiday-travel **B2** · "Travel & Money" (chủ đề mới, app dùng màu trung tính) · The New York Times.
  Sửa OCR đã áp: `Al` → `AI` (L009, L010), `202o` → `2020`, `8o` → `80` (ai-chatbots), `teng."What` → `teng." What` (curry). Giữ nguyên "your identify" (lỗi có sẵn trong câu trích dẫn của bài, đã xem ảnh gốc). Thêm lại dòng LLM bỏ nhầm `L160` ("founder of Domino Travel, based in Samford, Conn.", holiday-travel).
  - **Cập nhật run #66:** người dùng duyệt chữ: curry-chicken, holiday-travel đạt; ai-chatbots báo ngoặc kép lẫn “…" và dư cách `question. "`. Nguyên nhân: OCR đọc ngoặc đóng ” thành `"` (cả 3 bài đều bị). Đã sửa bằng code (`normalize_article_quotes` trong `assemble`, xem PROGRESS #66): cả 3 bài giờ là “…” cân cặp (12/7/13 cặp), 0 dấu cách trước ngoặc đóng. **Mục 1: người dùng chốt giữ đề xuất bỏ** (kể cả "Further AI reading"). **Mục 2:** chữ + tiêu đề đạt. **Mục 3:** đồng ý cả 3 B2 + chủ đề/nguồn như đề xuất; "Travel & Money" có màu riêng (cách 2) → FE-07e, bổ sung ADR-020 mục 5.
- [A-014] (xử lý run #65) FE-07b review **ĐẠT** → DONE, xem [R-FE-07b].
- [R-FE-07a] (xử lý run #64) Đã áp dụng toàn bộ 6 góp ý không chặn (a)–(f) của review FE-07a.
- [A-013] (xử lý run #63) FE-07a review **ĐẠT** → DONE, xem [R-FE-07a].
- [A-012] (xử lý run #56) FE-08 review **ĐẠT** → DONE, xem [R-FE-08].
- [H-015] (xử lý run #54) `saved_words_test.dart` đã chuyển sang dùng `InMemorySavedWordsRepository` + `InMemoryEventQueueRepository` để tránh kẹt I/O trong `testWidgets`; sửa `kind` trong event `word_saved` thành `lexicon` / `glossary`; sửa `display_text` của tooltip thành lemma viết thường; thêm `--timeout 60s`.
- [H-013] (xử lý run #54) Đã áp dụng toàn bộ góp ý plan FE-08: số run #54, `fromMap` fallback `entry_type` theo `lexicon_entry_id`, tooltip lemma_key và display_text chuẩn hóa lemma viết thường, cloze tooltip clean dọn dẹp khoảng trắng/dấu kép, cập nhật snapshot có dirty và giữ `source_article_id`, lưu lại giữ bản ghi cũ, `markClean` so khớp toàn bộ `toMap()`.
- [H-011] (xử lý run #54) Đã hoàn thành FE-08 theo Contract 1.4 (ADR-019): lưu theo cụm, bỏ Lưu ở dòng từ đơn, thêm Lưu nhỏ ở tooltip, `user_saved_words.entry_type`, `word_saved.from` (`item_sheet` | `phrase_row` | `tooltip`).
- [Q-019] (xử lý run #52) Duyệt lại 5 bài trước khi seed cloud. Người dùng trả lời: (1) Eating Well bỏ `nutritional value`; (2) Farming bỏ `poultry farm` (cùng loại `dairy farm`, giữ 1) → 12 mục; (3) Robots giữ `respond to`, bỏ `repetitious work`; (4) mục nào khớp nguyên văn bài thì giữ, không khớp thì bỏ (`good source of` giữ, `make progress`/`be referred to as` bỏ); (5) mục dùng chung lấy thẻ bài đầu → làm xong ở BE-06f (run #52). Việc áp (1)-(3) + seed cloud: BE-06b.
- [A-011] (xử lý run #51) FE-03b review **ĐẠT** → DONE, xem [R-FE-03b].
- [H-009] (xử lý run #50) FE-03b đã hoàn thành theo ADR-018, chỉ sửa `computeHighlights` + thêm AC-1..AC-5.
- [H-010] (xử lý run #50) Đã hoàn thiện và test `supabase_article_repository.dart` (cache bundle offline bằng `jsonDecode(jsonEncode(cached))`), `supabase_sync_test.dart` (đóng/mở box Hive thật), `build.gradle.kts` (coreLibraryDesugaring) và `gradle.properties` (kotlin.incremental=false).
- [H-012] (xử lý run #50) Đã tiếp thu trọn vẹn 4 điểm góp ý trong plan FE-03b: chuyển run sang #50, gom test unit vào `highlight_test.dart`, xử lý thật H-010, kiểm tra chi tiết không tô màu token và whitespace trong AC-5 của `reader_screen_test.dart`.
- [Q-017] (xử lý run #48) Chạy thật FE-06 trên điện thoại: (a)-(c) đạt (người dùng báo run #47); (d) cloud có `reading_history` của người dùng ẩn danh từ máy thật (Eating Well, 100%, `completed`, 2026-11-15) → đồng bộ lên cloud chạy. FE-06 → **DONE**. Còn H-010 (sửa đọc cache chưa commit) cho Antigravity. Cùng run: migration 1.4 lên cloud, seed lại Eating Well 10 mục. Sự cố: `supabase_check` không `--bundle` seed fixture (trùng id `art_eating_well`) đè bài thật thành 2 section vài phút; đã chạy lại với bundle thật (9 section, 10 mục, 16 occurrence); `reading_history` không ảnh hưởng (trỏ card 1). Đã chặn: trên cloud bắt buộc `--bundle`.
- [Q-001] (xử lý run #48) Người dùng chốt: tooltip **có** nút Lưu nhỏ (ADR-019).
- [Q-002] (xử lý run #48) Dòng từ đơn trong sheet cụm luôn hiển thị (từ nội dung), nhưng **không có nút Lưu** (ADR-019).
- [Q-018] (xử lý run #48) Kho từ chia Từ đơn / Cụm từ + nhóm theo bài: thêm `user_saved_words.entry_type` ngay trong contract 1.4 (ADR-019); màn kho từ để sau MVP.
- [A-010] (xử lý run #46) Review lại FE-06 → code ĐẠT, chờ người dùng chạy thật (R-FE-06b, Q-017).
- [Q-014] (xử lý run #44) Người dùng thay `wakeful.pdf` (bị paywall cắt) bằng `chatbotAI.pdf` (New Scientist, "The most important part of AI chatbots is being ignored", 28/10/2026): bài đầy đủ, ~1.100-1.200 từ thân bài, văn gần C1, không có lớp chữ (OCR), 1 cột. Bỏ menu, ảnh, "Read more", quảng cáo, "Further AI reading". Chờ người dùng chốt: gắn B2? giữ nguyên độ dài? (Claude đề xuất: B2, giữ nguyên). **Người dùng chốt (sau run #60): B2, giữ nguyên độ dài.** Không thêm C1 cho `article.cefr_level` (phạm vi A2-B2; B2 = bài khó nhất trong app, mục từ bên trong vẫn được gắn C1 nếu đúng).
- [A-009] (xử lý run #44) Review FE-06 → CẦN SỬA, ghi R-FE-06 (2 bắt buộc: điều kiện khởi tạo Supabase, chạy thật với cloud).
- [H-008] (xử lý run #42) Đã chép fixture mới (IPA không ː) sang `app/assets/fixtures/` và cập nhật test `tap_sheets_test.dart`.
- [A-008] (xử lý run #40) Review FE-04d → ĐẠT, ghi R-FE-04d.
- [Q-015] (xử lý run #38) Người dùng: dùng `play a vital role in` / `play a major role in` để kiểm tái sử dụng → chọn hướng (b): known_entries từ mọi bài trước, mục chọn lại miễn i+1 (BE-06e1). Bài BE-06c vẫn nên gần chủ đề cũ.
- [Q-016] (xử lý run #38) Người dùng duyệt xong 5 `review.md` → `docs/reviews/run38-content-review.md`; giữ giọng Mỹ, sửa `ː`. Việc tách thành BE-06e1, BE-06e2, rồi BE-06b áp dụng.
- [H-007] (xử lý run #39) Đã hoàn thành FE-04d (ADR-015): 1 nút loa + chip chế độ 1x/0.75x, chạm chip đổi + phát ngay, dùng chung mọi loa.
- [Q-013] (xử lý run #37) Người dùng soát rocket-science (7/14 section hỏng ở vùng 4 cột chen nhau, ~30 dòng thân bài bị bỏ qua) → Claude xếp tay 13 section, 910 từ; sửa `onto`, `that,`. Chốt cấp độ robots B1, farming B1, rocket-science B2, water-power B2. Câu hỏi `wakeful` chuyển sang Q-014.
- [A-007] (xử lý run #35) Review FE-05 → ĐẠT, ghi R-FE-05.
- [H-005] (xử lý run #33) Antigravity đã hoàn thành FE-05 theo đầy đủ góp ý của H-005 (soft delete, nạp sync trước PageController, maxIndexReached, widget test ProviderScope mới).
- [Q-011] (xử lý run #32) Người dùng tạo project cloud, bật Anonymous Sign-ins, `supabase login`, thêm `SUPABASE_DB_PASSWORD`; Claude link + `db push` + seed + kiểm.
- [A-006] (xử lý run #30) Review FE-04c → ĐẠT, ghi R-FE-04c.
- [H-004] (xử lý run #29) Antigravity đã làm FE-04c bản mới (ADR-014).
- [R-run23] (xử lý run #29) Bản run #23 đã bỏ, thay bằng FE-04c.
- [H-004] (xử lý run #29) Contract 1.3 (ADR-014): Antigravity đã khôi phục code FE-04b, nới vùng chạm loa ≥ 44×44 dp, đồng bộ fixture 1.3, flutter analyze sạch, 40/40 test pass.
- [Q-012] (xử lý run #28) Người dùng tra Cambridge: `play a vital role in` → **C1** (khóa trong overrides).
- [Q-007] (xử lý run #28) Người dùng duyệt danh sách mục từ (giữ nguyên 8 mục).
- [Q-008] (xử lý run #28) Người dùng duyệt theo Cambridge: `in moderation` → **C1**, `breakfast` → **A1** (khóa trong overrides); `an apple a day` nghĩa Việt rút gọn thành "ăn mỗi ngày một quả táo (để giữ sức khỏe)". Quy tắc CEFR theo từ điển ghi vào ADR-010.
- [H-002] (run #24, hết hiệu lực run #26, thay bằng H-004) Contract **1.2** (ADR-013): loa chậm chọn được `0.75` (mặc định) / `0.6` / `0.5`, ▾ là cách duy nhất để đổi, chọn là phát ngay; tooltip và dòng từ đơn giữ 1x. Dữ liệu bundle không đổi, chỉ `contract_version`. **Cần:** làm FE-04c **trên** working tree hiện tại (không commit riêng bản run #23); chép lại `fixtures/article_eating_well.json` sang `app/assets/fixtures/`.
- [A-005] (xử lý run #21) Review FE-04b → ĐẠT, ghi R-FE-04b (4 góp ý không chặn, làm kèm FE-08).
- [Q-010] (xử lý run #20) gpt-4-1-vision kém hơn gpt-5-mini (37 so với 4 mảnh lệch); người dùng đã trả `.env` về gpt-5-mini (cả VISION và TEXT).
- [Q-009] (xử lý run #19) Người dùng cung cấp deployment `gpt-4-1-vision` → Claude test (run #19): kém hơn gpt-5-mini (37 mảnh lệch so với 4). Kết luận: giữ gpt-5-mini + crosscheck làm mặc định; xem Q-010.
- [H-002] (xử lý run #18) Đã cập nhật fixture 1.1, Token.ipa, sheet 6 khối, loa 0.75x, event audio_played, bỏ sheet_more_opened.
- [R-FE-04] (xử lý run #18) Đã xử lý toàn bộ 4 góp ý: (a) TapRegion chống nuốt tap, (b) AudioService playUrl fallback sang speak, (c) memoize lexiconById và computeHighlights, (d) cập nhật test không có "Xem thêm" và tooltip đọc lemma.
- [A-004] (xử lý run #16) Review FE-04 → ĐẠT, ghi R-FE-04.
- [Q-003] (xử lý run #7) Hết hiệu lực: người dùng đổi hướng sang Vision (ADR-009), không cần duyệt OCR tay nữa.
- [A-001] (xử lý run #3) Review FE-01 → ĐẠT, ghi nhận xét R-FE-01.
- [R-FE-01] (xử lý run #4) Đã tải Inter-VariableFont.ttf vào app/assets/fonts/ và khai báo fonts trong app/pubspec.yaml.
- [A-002] (xử lý run #5) Review FE-02 → ĐẠT, ghi R-FE-02.
- [A-003] (xử lý run #11) Review FE-03 → ĐẠT, ghi R-FE-03.
- [R-FE-03-partial] (xử lý run #10) Antigravity đã hoàn thiện, xác nhận ở R-FE-03 (run #11).
