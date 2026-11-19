import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:readle/app.dart';
import 'package:readle/data/models/article_bundle.dart';
import 'package:readle/data/models/article_card.dart';
import 'package:readle/data/models/local_models.dart';
import 'package:readle/data/providers/local_providers.dart';
import 'package:readle/data/providers/repository_providers.dart';
import 'package:readle/data/providers/sync_providers.dart';
import 'package:readle/data/repositories/article_repository.dart';
import 'package:readle/data/repositories/local_storage_repository.dart';
import 'package:readle/features/saved/providers/saved_tab_providers.dart';
import 'package:readle/features/saved/screens/saved_screen.dart';
import 'package:readle/features/saved/widgets/saved_word_tile.dart';

import '../../helpers/fake_remote_store.dart';

const List<ArticleCard> sampleCards = [
  ArticleCard(
    id: 'art_eating_well',
    title: 'Eating Well',
    category: 'Health & Nutrition',
    cefrLevel: 'A2',
    sourceName: 'World of Wonder',
    wordCount: 566,
    sectionCount: 9,
    processingOrder: 1,
  ),
  ArticleCard(
    id: 'art_robots',
    title: 'Robots',
    category: 'Science & Technology',
    cefrLevel: 'B1',
    sourceName: 'World of Wonder',
    wordCount: 620,
    sectionCount: 7,
    processingOrder: 2,
  ),
];

class MockArticleRepo implements ArticleRepository {
  final ArticleBundle baseBundle;
  final List<ArticleCard> cards;

  MockArticleRepo({
    required this.baseBundle,
    this.cards = sampleCards,
  });

  @override
  Future<List<ArticleCard>> list() async => cards;

  @override
  Future<ArticleBundle> get(String id) async => baseBundle;
}

void main() {
  late ArticleBundle fixtureBundle;

  setUpAll(() {
    final file = File('../fixtures/article_eating_well.json');
    final jsonStr = file.existsSync()
        ? file.readAsStringSync()
        : File('assets/fixtures/article_eating_well.json').readAsStringSync();
    fixtureBundle = ArticleBundle.fromJson(
      jsonDecode(jsonStr) as Map<String, dynamic>,
    );
  });

  group('FE-07d Unit test groupSavedWords', () {
    test('Lọc entryType, loại bỏ deleted, gộp các id lạ vào 1 nhóm "Bài khác" và sắp xếp theo savedAt mới nhất', () {
      final now = DateTime.parse('2026-11-18T10:00:00Z');

      final words = [
        SavedWord(
          id: 'w1',
          lemmaKey: 'tend to',
          entryType: 'collocation',
          displayText: 'tend to',
          vi: 'có xu hướng',
          exampleSentence: 'People tend to eat more.',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now.subtract(const Duration(hours: 1)),
          dueDate: now,
        ),
        SavedWord(
          id: 'w2',
          lemmaKey: 'play a vital role in',
          entryType: 'collocation',
          displayText: 'play a vital role in',
          vi: 'đóng vai trò quan trọng',
          exampleSentence: 'Sleep plays a vital role in health.',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now.subtract(const Duration(hours: 3)),
          dueDate: now,
        ),
        SavedWord(
          id: 'w3',
          lemmaKey: 'deleted phrase',
          entryType: 'collocation',
          displayText: 'deleted phrase',
          vi: 'cụm đã xóa',
          exampleSentence: '',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now,
          dueDate: now,
          deleted: true,
        ),
        SavedWord(
          id: 'w4',
          lemmaKey: 'strange phrase 1',
          entryType: 'collocation',
          displayText: 'strange phrase 1',
          vi: 'cụm lạ 1',
          exampleSentence: '',
          cloze: const {},
          sourceArticleId: 'art_non_existent_1',
          savedAt: now.subtract(const Duration(hours: 2)),
          dueDate: now,
        ),
        SavedWord(
          id: 'w5',
          lemmaKey: 'strange phrase 2',
          entryType: 'collocation',
          displayText: 'strange phrase 2',
          vi: 'cụm lạ 2',
          exampleSentence: '',
          cloze: const {},
          sourceArticleId: 'art_non_existent_2',
          savedAt: now.subtract(const Duration(minutes: 10)), // Mới nhất trong nhóm "Bài khác"
          dueDate: now,
        ),
        SavedWord(
          id: 'w6',
          lemmaKey: 'nutrition',
          entryType: 'single_word',
          displayText: 'nutrition',
          vi: 'dinh dưỡng',
          exampleSentence: '',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now,
          dueDate: now,
        ),
      ];

      final articleTitles = {
        'art_eating_well': 'Eating Well',
      };

      // 1. Kiểm tra với collocation
      final collocGroups = groupSavedWords(
        words: words,
        articleTitles: articleTitles,
        entryType: 'collocation',
      );

      // Có đúng 2 nhóm: "Bài khác" (do có w5 lưu cách 10m) và "Eating Well" (w1 lưu cách 1h)
      expect(collocGroups.length, 2);
      expect(collocGroups[0].groupKey, '_other');
      expect(collocGroups[0].title, 'Bài khác');
      // Nhóm "Bài khác" gộp cả 2 id lạ khác nhau w5 và w4
      expect(collocGroups[0].words.length, 2);
      expect(collocGroups[0].words[0].lemmaKey, 'strange phrase 2');
      expect(collocGroups[0].words[1].lemmaKey, 'strange phrase 1');

      expect(collocGroups[1].groupKey, 'art_eating_well');
      expect(collocGroups[1].title, 'Eating Well');
      expect(collocGroups[1].words.length, 2);
      expect(collocGroups[1].words[0].lemmaKey, 'tend to');
      expect(collocGroups[1].words[1].lemmaKey, 'play a vital role in');

      // 2. Kiểm tra với single_word
      final singleGroups = groupSavedWords(
        words: words,
        articleTitles: articleTitles,
        entryType: 'single_word',
      );
      expect(singleGroups.length, 1);
      expect(singleGroups[0].title, 'Eating Well');
      expect(singleGroups[0].words.length, 1);
      expect(singleGroups[0].words[0].lemmaKey, 'nutrition');
    });
  });

  group('FE-07d Widget tests - SavedScreen', () {
    Widget buildTestApp({
      required ArticleRepository articleRepo,
      required InMemorySavedWordsRepository savedWordsRepo,
      required InMemoryEventQueueRepository eventQueueRepo,
    }) {
      final fakeRemoteStore = FakeRemoteStore();
      final progressRepo = InMemoryReadingProgressRepository();

      return ProviderScope(
        overrides: [
          articleRepositoryProvider.overrideWithValue(articleRepo),
          readingProgressRepositoryProvider.overrideWithValue(progressRepo),
          savedWordsRepositoryProvider.overrideWithValue(savedWordsRepo),
          eventQueueRepositoryProvider.overrideWithValue(eventQueueRepo),
          remoteStoreProvider.overrideWithValue(fakeRemoteStore),
        ],
        child: const ReadleApp(),
      );
    }

    testWidgets('AC-1: Mặc định hiện Cụm từ (Eating Well có play a vital role in và tend to), không hiện từ đơn hay từ đã xóa',
        (tester) async {
      final savedWordsRepo = InMemorySavedWordsRepository();
      final eventQueueRepo = InMemoryEventQueueRepository();
      final now = DateTime.now();

      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w1',
          lemmaKey: 'play a vital role in',
          entryType: 'collocation',
          displayText: 'play a vital role in',
          vi: 'đóng vai trò quan trọng',
          exampleSentence: 'Sleep plays a vital role in health.',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now.subtract(const Duration(hours: 3)),
          dueDate: now,
        ),
      );
      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w2',
          lemmaKey: 'tend to',
          entryType: 'collocation',
          displayText: 'tend to',
          vi: 'có xu hướng',
          exampleSentence: 'People tend to eat more.',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now.subtract(const Duration(hours: 1)),
          dueDate: now,
        ),
      );
      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w3',
          lemmaKey: 'carotenoid',
          entryType: 'single_word',
          displayText: 'carotenoid',
          vi: 'sắc tố carotenoid',
          exampleSentence: '',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now.subtract(const Duration(hours: 2)),
          dueDate: now,
        ),
      );
      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w4',
          lemmaKey: 'health',
          lexiconEntryId: null,
          entryType: 'single_word',
          displayText: 'health',
          vi: 'sức khỏe',
          exampleSentence: '',
          cloze: const {},
          sourceArticleId: 'art_robots',
          savedAt: now.subtract(const Duration(minutes: 30)),
          dueDate: now,
        ),
      );
      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w5',
          lemmaKey: 'junk food',
          entryType: 'collocation',
          displayText: 'junk food',
          vi: 'đồ ăn vặt',
          exampleSentence: '',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now,
          dueDate: now,
        ),
      );
      await savedWordsRepo.deleteWord('junk food'); // Soft-delete

      final articleRepo = MockArticleRepo(baseBundle: fixtureBundle);

      await tester.pumpWidget(buildTestApp(
        articleRepo: articleRepo,
        savedWordsRepo: savedWordsRepo,
        eventQueueRepo: eventQueueRepo,
      ));
      await tester.pumpAndSettle();

      // Chuyển sang tab Đã lưu
      await tester.tap(find.text('Đã lưu'));
      await tester.pumpAndSettle();

      // Tiêu đề & nút Ôn tập từ vựng
      expect(find.text('Đã lưu'), findsWidgets);
      expect(find.widgetWithText(FilledButton, 'Ôn tập từ vựng'), findsOneWidget);

      // Mặc định segment "Cụm từ" được chọn
      expect(find.text('Cụm từ'), findsOneWidget);
      expect(find.text('Từ đơn'), findsOneWidget);

      // Thấy 2 cụm từ dưới nhóm "Eating Well"
      expect(find.text('Eating Well'), findsOneWidget);
      expect(find.text('play a vital role in'), findsOneWidget);
      expect(find.text('tend to'), findsOneWidget);

      // KHÔNG thấy các từ đơn và từ đã xóa
      expect(find.text('carotenoid'), findsNothing);
      expect(find.text('health'), findsNothing);
      expect(find.text('junk food'), findsNothing);
    });

    testWidgets('AC-2: Chạm "Từ đơn" hiện carotenoid (Eating Well) và health (Robots, lexiconEntryId=null)',
        (tester) async {
      final savedWordsRepo = InMemorySavedWordsRepository();
      final eventQueueRepo = InMemoryEventQueueRepository();
      final now = DateTime.now();

      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w1',
          lemmaKey: 'play a vital role in',
          entryType: 'collocation',
          displayText: 'play a vital role in',
          vi: 'đóng vai trò quan trọng',
          exampleSentence: 'Sleep plays a vital role in health.',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now.subtract(const Duration(hours: 3)),
          dueDate: now,
        ),
      );
      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w3',
          lemmaKey: 'carotenoid',
          entryType: 'single_word',
          displayText: 'carotenoid',
          vi: 'sắc tố carotenoid',
          exampleSentence: '',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now.subtract(const Duration(hours: 2)),
          dueDate: now,
        ),
      );
      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w4',
          lemmaKey: 'health',
          lexiconEntryId: null,
          entryType: 'single_word',
          displayText: 'health',
          vi: 'sức khỏe',
          exampleSentence: '',
          cloze: const {},
          sourceArticleId: 'art_robots',
          savedAt: now.subtract(const Duration(minutes: 30)),
          dueDate: now,
        ),
      );

      final articleRepo = MockArticleRepo(baseBundle: fixtureBundle);

      await tester.pumpWidget(buildTestApp(
        articleRepo: articleRepo,
        savedWordsRepo: savedWordsRepo,
        eventQueueRepo: eventQueueRepo,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Đã lưu'));
      await tester.pumpAndSettle();

      // Bấm chọn "Từ đơn"
      await tester.tap(find.text('Từ đơn'));
      await tester.pumpAndSettle();

      // Hiển thị carotenoid dưới Eating Well và health dưới Robots
      expect(find.text('Eating Well'), findsOneWidget);
      expect(find.text('carotenoid'), findsOneWidget);
      expect(find.text('Robots'), findsOneWidget);
      expect(find.text('health'), findsOneWidget);

      // Không hiển thị cụm từ
      expect(find.text('play a vital role in'), findsNothing);
    });

    testWidgets('AC-3: Chạm mở rộng câu ví dụ in nghiêng, bỏ lưu xóa dòng, repo cập nhật, event_queue có word_unsaved (articleId=null), giữ trạng thái tile khác (ValueKey)',
        (tester) async {
      final savedWordsRepo = InMemorySavedWordsRepository();
      final eventQueueRepo = InMemoryEventQueueRepository();
      final now = DateTime.now();

      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w1',
          lemmaKey: 'play a vital role in',
          entryType: 'collocation',
          displayText: 'play a vital role in',
          vi: 'đóng vai trò quan trọng',
          exampleSentence: 'Sleep plays a vital role in health.',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now.subtract(const Duration(hours: 3)),
          dueDate: now,
        ),
      );
      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w2',
          lemmaKey: 'tend to',
          entryType: 'collocation',
          displayText: 'tend to',
          vi: 'có xu hướng',
          exampleSentence: 'People tend to eat more.',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now.subtract(const Duration(hours: 1)),
          dueDate: now,
        ),
      );

      final articleRepo = MockArticleRepo(baseBundle: fixtureBundle);

      await tester.pumpWidget(buildTestApp(
        articleRepo: articleRepo,
        savedWordsRepo: savedWordsRepo,
        eventQueueRepo: eventQueueRepo,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Đã lưu'));
      await tester.pumpAndSettle();

      // Ban đầu câu ví dụ chưa hiển thị
      expect(find.text('People tend to eat more.'), findsNothing);
      expect(find.text('Sleep plays a vital role in health.'), findsNothing);

      // Chạm vào dòng tend to để mở rộng
      await tester.tap(find.text('tend to'));
      await tester.pumpAndSettle();

      // Câu ví dụ của tend to xuất hiện với kiểu in nghiêng
      final exampleFinder = find.text('People tend to eat more.');
      expect(exampleFinder, findsOneWidget);
      final textWidget = tester.widget<Text>(exampleFinder);
      expect(textWidget.style?.fontStyle, FontStyle.italic);

      // Dòng play a vital role in vẫn đang đóng
      expect(find.text('Sleep plays a vital role in health.'), findsNothing);

      // Bấm nút bookmark của tend to để bỏ lưu
      final tendToTile = find.ancestor(
        of: find.text('tend to'),
        matching: find.byType(SavedWordTile),
      );
      final bookmarkBtn = find.descendant(
        of: tendToTile,
        matching: find.byTooltip('Bỏ lưu'),
      );
      await tester.tap(bookmarkBtn);
      await tester.pumpAndSettle();

      // tend to biến mất khỏi màn hình ngay lập tức
      expect(find.text('tend to'), findsNothing);
      expect(find.text('People tend to eat more.'), findsNothing);

      // play a vital role in vẫn còn và VẪN ĐANG ĐÓNG (nhờ ValueKey)
      expect(find.text('play a vital role in'), findsOneWidget);
      expect(find.text('Sleep plays a vital role in health.'), findsNothing);

      // Repo isSaved('tend to') == false
      final isSaved = await savedWordsRepo.isSaved('tend to');
      expect(isSaved, isFalse);

      // Hàng đợi eventQueue có event word_unsaved với lemma_key = 'tend to', articleId = null, sectionId = null
      final events = await eventQueueRepo.peekBatch();
      final unsavedEvent = events.firstWhere((e) => e.eventType == 'word_unsaved');
      expect(unsavedEvent.payload['lemma_key'], 'tend to');
      expect(unsavedEvent.articleId, isNull);
      expect(unsavedEvent.sectionId, isNull);

      // Không có SnackBar hay Undo
      expect(find.byType(SnackBar), findsNothing);
    });

    testWidgets('AC-4: Bấm nút "Ôn tập từ vựng" mở /review toàn màn hình (không có NavigationBar)',
        (tester) async {
      final savedWordsRepo = InMemorySavedWordsRepository();
      final eventQueueRepo = InMemoryEventQueueRepository();
      final articleRepo = MockArticleRepo(baseBundle: fixtureBundle);

      await tester.pumpWidget(buildTestApp(
        articleRepo: articleRepo,
        savedWordsRepo: savedWordsRepo,
        eventQueueRepo: eventQueueRepo,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Đã lưu'));
      await tester.pumpAndSettle();

      // Bấm nút Ôn tập từ vựng
      await tester.tap(find.widgetWithText(FilledButton, 'Ôn tập từ vựng'));
      await tester.pumpAndSettle();

      // Màn hình /review mở ngoài shell -> không có NavigationBar
      expect(find.byType(NavigationBar), findsNothing);
      expect(find.text('Ôn tập'), findsOneWidget);

      // Quay lại tab Đã lưu
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();

      expect(find.byType(NavigationBar), findsOneWidget);
    });

    testWidgets('AC-5: No-pressure UX (không số, empty states câu chữ nhẹ nhàng)',
        (tester) async {
      final savedWordsRepo = InMemorySavedWordsRepository();
      final eventQueueRepo = InMemoryEventQueueRepository();
      final articleRepo = MockArticleRepo(baseBundle: fixtureBundle);

      await tester.pumpWidget(buildTestApp(
        articleRepo: articleRepo,
        savedWordsRepo: savedWordsRepo,
        eventQueueRepo: eventQueueRepo,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Đã lưu'));
      await tester.pumpAndSettle();

      // 1. Empty state tab Cụm từ
      expect(
        find.text('Chưa có cụm từ nào. Khi đọc, chạm vào cụm được tô màu rồi bấm Lưu nhé.'),
        findsOneWidget,
      );

      // 2. Empty state tab Từ đơn
      await tester.tap(find.text('Từ đơn'));
      await tester.pumpAndSettle();
      expect(find.text('Chưa có từ đơn nào.'), findsOneWidget);

      // 3. Kiểm tra No-pressure: không có Text nào chứa chữ số trên Tab Đã lưu
      final allTextWidgets = tester.widgetList<Text>(find.byType(Text));
      for (final t in allTextWidgets) {
        expect(
          t.data?.contains(RegExp(r'\d')),
          isNot(true),
          reason: 'Tab Đã lưu không được chứa chữ số: "${t.data}"',
        );
      }
    });

    testWidgets('Vùng chạm nút bookmark >= 44x44 dp', (tester) async {
      final savedWordsRepo = InMemorySavedWordsRepository();
      final eventQueueRepo = InMemoryEventQueueRepository();
      final now = DateTime.now();

      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w1',
          lemmaKey: 'tend to',
          entryType: 'collocation',
          displayText: 'tend to',
          vi: 'có xu hướng',
          exampleSentence: '',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now,
          dueDate: now,
        ),
      );

      final articleRepo = MockArticleRepo(baseBundle: fixtureBundle);

      await tester.pumpWidget(buildTestApp(
        articleRepo: articleRepo,
        savedWordsRepo: savedWordsRepo,
        eventQueueRepo: eventQueueRepo,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Đã lưu'));
      await tester.pumpAndSettle();

      final bookmarkFinder = find.byTooltip('Bỏ lưu');
      expect(bookmarkFinder, findsOneWidget);
      final size = tester.getSize(bookmarkFinder);
      expect(size.width, greaterThanOrEqualTo(44.0));
      expect(size.height, greaterThanOrEqualTo(44.0));
    });

    testWidgets('Offline resilience: khi articleListProvider ném Exception vẫn hiển thị danh sách từ gộp vào Bài khác',
        (tester) async {
      final savedWordsRepo = InMemorySavedWordsRepository();
      final eventQueueRepo = InMemoryEventQueueRepository();
      final now = DateTime.now();

      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w1',
          lemmaKey: 'tend to',
          entryType: 'collocation',
          displayText: 'tend to',
          vi: 'có xu hướng',
          exampleSentence: '',
          cloze: const {},
          sourceArticleId: 'art_eating_well',
          savedAt: now,
          dueDate: now,
        ),
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            articleListProvider.overrideWith((ref) async => throw Exception('Network offline')),
            savedWordsRepositoryProvider.overrideWithValue(savedWordsRepo),
            eventQueueRepositoryProvider.overrideWithValue(eventQueueRepo),
          ],
          child: const MaterialApp(
            home: SavedScreen(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Vẫn hiển thị từ tend to, nhưng nhóm gộp thành "Bài khác", không hiện câu báo lỗi
      expect(find.text('Bài khác'), findsOneWidget);
      expect(find.text('tend to'), findsOneWidget);
      expect(find.textContaining(RegExp(r'lỗi', caseSensitive: false)), findsNothing);
    });
  });
}
