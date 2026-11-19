import 'dart:convert';
import 'dart:io';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:readle/core/theme/app_theme.dart';
import 'package:readle/data/models/article_bundle.dart';
import 'package:readle/data/models/article_card.dart';
import 'package:readle/data/models/local_models.dart';
import 'package:readle/data/providers/local_providers.dart';
import 'package:readle/data/providers/repository_providers.dart';
import 'package:readle/data/providers/sync_providers.dart';
import 'package:readle/data/repositories/article_repository.dart';
import 'package:readle/data/repositories/local_storage_repository.dart';
import 'package:readle/features/reader/screens/reader_screen.dart';
import 'package:readle/features/reader/services/audio_service.dart';
import 'package:readle/features/reader/widgets/item_bottom_sheet.dart';
import 'package:readle/features/reader/widgets/phrase_bottom_sheet.dart';
import 'package:readle/features/reader/widgets/word_tooltip.dart';

import '../../helpers/fake_remote_store.dart';

class MockArticleRepository implements ArticleRepository {
  final ArticleBundle bundle;
  MockArticleRepository(this.bundle);

  @override
  Future<ArticleBundle> get(String id) async => bundle;

  @override
  Future<List<ArticleCard>> list() async => [];
}

class TestAudioService implements AudioService {
  @override
  Future<void> speak(String text, {double speed = 1.0}) async {}

  @override
  Future<void> playUrl(String url, {double speed = 1.0, String? fallbackText}) async {}

  @override
  Future<void> stop() async {}

  @override
  void dispose() {}
}

void main() {
  late InMemorySavedWordsRepository savedWordsRepo;
  late InMemoryEventQueueRepository eventQueueRepo;
  late ArticleBundle bundle;
  late FakeRemoteStore fakeRemoteStore;

  setUpAll(() {
    final file = File('../fixtures/article_eating_well.json');
    final jsonStr = file.existsSync()
        ? file.readAsStringSync()
        : File('assets/fixtures/article_eating_well.json').readAsStringSync();
    bundle =
        ArticleBundle.fromJson(jsonDecode(jsonStr) as Map<String, dynamic>);
  });

  setUp(() {
    savedWordsRepo = InMemorySavedWordsRepository();
    eventQueueRepo = InMemoryEventQueueRepository();
    fakeRemoteStore = FakeRemoteStore(currentUserId: '11111111-1111-1111-1111-111111111111');
  });

  Widget createTestWidget() {
    return ProviderScope(
      overrides: [
        articleRepositoryProvider.overrideWithValue(
          MockArticleRepository(bundle),
        ),
        savedWordsRepositoryProvider.overrideWithValue(savedWordsRepo),
        eventQueueRepositoryProvider.overrideWithValue(eventQueueRepo),
        remoteStoreProvider.overrideWithValue(fakeRemoteStore),
        audioServiceProvider.overrideWithValue(TestAudioService()),
      ],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        home: const ReaderScreen(articleId: 'art_eating_well'),
      ),
    );
  }

  Future<void> tapWordToken(WidgetTester tester, String word) async {
    final richTexts = tester.widgetList<RichText>(find.byType(RichText));
    for (final richText in richTexts) {
      final span = richText.text;
      if (span is TextSpan) {
        bool found = false;
        void search(InlineSpan s) {
          if (found) return;
          if (s is TextSpan) {
            if (s.text == word && s.recognizer is TapGestureRecognizer) {
              final recognizer = s.recognizer as TapGestureRecognizer;
              recognizer.onTapUp?.call(
                TapUpDetails(
                  kind: PointerDeviceKind.touch,
                  globalPosition: const Offset(150, 300),
                ),
              );
              found = true;
              return;
            }
            s.children?.forEach(search);
          }
        }

        search(span);
        if (found) {
          await tester.pumpAndSettle();
          return;
        }
      }
    }
    fail('Could not find TapGestureRecognizer for word: "$word"');
  }

  group('FE-08: Luồng lưu từ theo ADR-019 và Contract 1.4', () {
    testWidgets(
        'AC-1: Phrase sheet has Save button for each phrase and NONE on word row; saving toggles state and enqueues event',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Chạm "role" để mở PhraseBottomSheet (có 2 cụm: play a vital role in, vital role)
      await tapWordToken(tester, 'role');
      expect(find.byType(PhraseBottomSheet), findsOneWidget);

      // Cả 2 khối cụm đều có nút Lưu (OutlinedButton) với nhãn "Lưu" ban đầu
      final saveButtons = find.descendant(
        of: find.byType(PhraseBottomSheet),
        matching: find.byType(OutlinedButton),
      );
      expect(saveButtons, findsNWidgets(2));
      expect(find.text('Lưu'), findsNWidgets(2));

      // Bấm nút Lưu của cụm thứ 2 ("vital role")
      await tester.ensureVisible(saveButtons.at(1));
      await tester.tap(saveButtons.at(1));
      await tester.pumpAndSettle();

      // Nút Lưu cụm 2 chuyển thành "Đã lưu", cụm 1 vẫn là "Lưu"
      expect(find.text('Đã lưu'), findsOneWidget);
      expect(find.text('Lưu'), findsOneWidget);

      // Kiểm tra trong repo: 'vital role' đã được lưu với entryType = 'collocation'
      final savedWord = await savedWordsRepo.getWord('vital role');
      expect(savedWord, isNotNull);
      expect(savedWord!.entryType, 'collocation');
      expect(savedWord.deleted, isFalse);

      // Kiểm tra event queue: có sự kiện word_saved từ phrase_row với kind = 'lexicon'
      final events = await eventQueueRepo.peekBatch();
      expect(events.length, 1);
      expect(events.first.eventType, 'word_saved');
      expect(events.first.payload['lemma_key'], 'vital role');
      expect(events.first.payload['kind'], 'lexicon');
      expect(events.first.payload['from'], 'phrase_row');

      // Bấm lại nút "Đã lưu" -> un-save (soft delete)
      final savedBtn = find.text('Đã lưu');
      await tester.ensureVisible(savedBtn);
      await tester.tap(savedBtn);
      await tester.pumpAndSettle();

      // Nút trở lại nhãn "Lưu"
      expect(find.text('Đã lưu'), findsNothing);
      expect(find.text('Lưu'), findsNWidgets(2));

      // Kiểm tra soft-delete trong repo
      expect(await savedWordsRepo.isSaved('vital role'), isFalse);
      final tombstone = await savedWordsRepo.getWord('vital role');
      expect(tombstone!.deleted, isTrue);

      // Có thêm sự kiện word_unsaved
      final allEvents = await eventQueueRepo.peekBatch();
      expect(allEvents.length, 2);
      expect(allEvents.last.eventType, 'word_unsaved');
      expect(allEvents.last.payload['lemma_key'], 'vital role');
    });

    testWidgets(
        'AC-2: Tooltip Save button saves glossary word with auto-generated Cloze, entryType single_word, and lexiconEntryId null',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Vuốt sang card 2
      await tester.fling(find.byType(PageView), const Offset(-400, 0), 1000);
      await tester.pumpAndSettle();

      // Chạm "folate" (glossary single word không thuộc lexicon)
      await tapWordToken(tester, 'folate');
      expect(find.byType(WordTooltip), findsOneWidget);

      // Tooltip có nút Lưu (Key: tooltip_save_button) đạt chuẩn ≥ 44x44dp và có Semantics ([R-FE-08] (c))
      final tooltipSaveBtn = find.byKey(const Key('tooltip_save_button'));
      expect(tooltipSaveBtn, findsOneWidget);
      final saveBtnSize = tester.getSize(tooltipSaveBtn);
      expect(saveBtnSize.width, greaterThanOrEqualTo(44.0));
      expect(saveBtnSize.height, greaterThanOrEqualTo(44.0));
      expect(tester.getSemantics(tooltipSaveBtn).label, 'Lưu');

      // Ban đầu icon là bookmark_border_outlined (chưa lưu)
      expect(
        find.descendant(
          of: tooltipSaveBtn,
          matching: find.byIcon(Icons.bookmark_border_outlined),
        ),
        findsOneWidget,
      );

      // Bấm lưu
      await tester.tap(tooltipSaveBtn);
      await tester.pumpAndSettle();

      // Semantics đổi sang 'Đã lưu' và icon đổi thành bookmark đầy
      expect(tester.getSemantics(tooltipSaveBtn).label, 'Đã lưu');
      expect(
        find.descendant(
          of: tooltipSaveBtn,
          matching: find.byIcon(Icons.bookmark),
        ),
        findsOneWidget,
      );

      // Kiểm tra dữ liệu được lưu
      final savedFolate = await savedWordsRepo.getWord('folate');
      expect(savedFolate, isNotNull);
      expect(savedFolate!.entryType, 'single_word');
      expect(savedFolate.lexiconEntryId, isNull);
      expect(savedFolate.displayText, 'folate'); // Lemma viết thường
      expect(savedFolate.vi, 'folate (một loại vitamin B)');

      // Cloze tự động trích xuất đúng và ghép lại đúng bằng câu gốc ([R-FE-08] (d))
      expect(savedFolate.cloze['answer'], 'folate');
      expect(savedFolate.exampleSentence, contains('folate'));
      final before = savedFolate.cloze['text_before'] as String;
      final answer = savedFolate.cloze['answer'] as String;
      final after = savedFolate.cloze['text_after'] as String;
      expect(before + answer + after, savedFolate.exampleSentence);

      // Event word_saved từ tooltip với kind = 'glossary'
      final events = await eventQueueRepo.peekBatch();
      expect(events.length, 1);
      expect(events.first.eventType, 'word_saved');
      expect(events.first.payload['lemma_key'], 'folate');
      expect(events.first.payload['kind'], 'glossary');
      expect(events.first.payload['from'], 'tooltip');
    });

    testWidgets(
        'AC-2b: Tooltip saves inflected token ("vitamins" -> lemma_key: "vitamin", answer: "vitamins") ([R-FE-08] (d))',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Vuốt sang card 2
      await tester.fling(find.byType(PageView), const Offset(-400, 0), 1000);
      await tester.pumpAndSettle();

      // Chạm token biến hình "vitamins" (lemma: "vitamin")
      await tapWordToken(tester, 'vitamins');
      expect(find.byType(WordTooltip), findsOneWidget);

      final tooltipSaveBtn = find.byKey(const Key('tooltip_save_button'));
      await tester.tap(tooltipSaveBtn);
      await tester.pumpAndSettle();

      final savedVitamin = await savedWordsRepo.getWord('vitamin');
      expect(savedVitamin, isNotNull);
      expect(savedVitamin!.lemmaKey, 'vitamin');
      expect(savedVitamin.displayText, 'vitamin');
      expect(savedVitamin.entryType, 'single_word');
      // answer trong cloze phải là dạng biến hình xuất hiện trong bài ("vitamins")
      expect(savedVitamin.cloze['answer'], 'vitamins');

      // Ghép lại đúng bằng câu ví dụ
      final before = savedVitamin.cloze['text_before'] as String;
      final ans = savedVitamin.cloze['answer'] as String;
      final after = savedVitamin.cloze['text_after'] as String;
      expect(before + ans + after, savedVitamin.exampleSentence);
    });

    testWidgets(
        'AC-3: Item sheet saves lexicon word ("carotenoid") with entryType single_word and "tend to" with collocation',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // 1. Chạm "tend" ở section 1
      await tapWordToken(tester, 'tend');
      expect(find.byType(PhraseBottomSheet), findsOneWidget);
      final tendSaveBtn = find.descendant(
        of: find.byType(PhraseBottomSheet),
        matching: find.byType(OutlinedButton),
      ).first;
      await tester.ensureVisible(tendSaveBtn);
      await tester.tap(tendSaveBtn);
      await tester.pumpAndSettle();

      final savedTend = await savedWordsRepo.getWord('tend to');
      expect(savedTend, isNotNull);
      expect(savedTend!.entryType, 'collocation');

      // Đóng sheet
      await tester.tapAt(const Offset(20, 20));
      await tester.pumpAndSettle();

      // 2. Sang section 2 và chạm "carotenoids"
      await tester.fling(find.byType(PageView), const Offset(-400, 0), 1000);
      await tester.pumpAndSettle();

      await tapWordToken(tester, 'carotenoids');
      expect(find.byType(ItemBottomSheet), findsOneWidget);
      final carotSaveBtn = find.descendant(
        of: find.byType(ItemBottomSheet),
        matching: find.byType(OutlinedButton),
      ).first;
      await tester.ensureVisible(carotSaveBtn);
      await tester.tap(carotSaveBtn);
      await tester.pumpAndSettle();

      final savedCarotenoid = await savedWordsRepo.getWord('carotenoid');
      expect(savedCarotenoid, isNotNull);
      expect(savedCarotenoid!.entryType, 'single_word');
    });

    testWidgets(
        'AC-4: Opening sheet of already saved word in another article updates snapshot (vi, example, cloze) while PRESERVING original source_article_id',
        (tester) async {
      // Giả sử từ "vital role" đã được lưu từ một bài viết khác ('art_previous_article')
      final initialSavedWord = SavedWord(
        id: 'uuid-vital-role',
        lemmaKey: 'vital role',
        lexiconEntryId: 'lex_vital_role_old',
        entryType: 'collocation',
        displayText: 'vital role',
        vi: 'nghĩa cũ ở bài trước',
        exampleSentence: 'Previous article example sentence.',
        cloze: const {
          'text_before': 'Previous article ',
          'answer': 'vital role',
          'text_after': ' sentence.',
        },
        sourceArticleId: 'art_previous_article', // Nguồn ban đầu
        savedAt: DateTime.utc(2026, 11, 10),
        dueDate: DateTime(2026, 11, 10),
        dirty: false,
      );
      await savedWordsRepo.saveWord(initialSavedWord);

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Chạm "role" để mở PhraseBottomSheet
      await tapWordToken(tester, 'role');
      expect(find.byType(PhraseBottomSheet), findsOneWidget);

      // Cụm "vital role" đã hiển thị trạng thái "Đã lưu" ngay khi mở
      expect(find.text('Đã lưu'), findsOneWidget);

      // Kiểm tra dữ liệu trong repo sau khi mở sheet
      final updatedWord = await savedWordsRepo.getWord('vital role');
      expect(updatedWord, isNotNull);

      // Snapshot được cập nhật theo ngữ cảnh bài hiện tại (art_eating_well) gồm cả lexiconEntryId và entryType ([R-FE-08] (a))
      expect(updatedWord!.lexiconEntryId, 'lex_vital_role');
      expect(updatedWord.entryType, 'collocation');
      expect(updatedWord.vi, 'vai trò thiết yếu');
      expect(updatedWord.exampleSentence, contains('vital role'));

      // Nhưng sourceArticleId VẪN ĐƯỢC GIỮ NGUYÊN là 'art_previous_article' theo Contract 3.3
      expect(updatedWord.sourceArticleId, 'art_previous_article');

      // Cờ dirty được bật lại để đồng bộ snapshot mới
      expect(updatedWord.dirty, isTrue);
    });
  });
}
