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
import 'package:readle/features/library/providers/library_providers.dart';
import 'package:readle/features/library/screens/history_screen.dart';
import 'package:readle/features/shell/app_shell.dart';

import '../../helpers/fake_remote_store.dart';

const List<ArticleCard> sampleFiveCards = [
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
  ArticleCard(
    id: 'art_farming',
    title: 'Farming',
    category: 'Food & Farming',
    cefrLevel: 'B1',
    sourceName: 'World of Wonder',
    wordCount: 710,
    sectionCount: 8,
    processingOrder: 3,
  ),
  ArticleCard(
    id: 'art_rocket_science',
    title: 'Rocket Science',
    category: 'Science & Technology',
    cefrLevel: 'B2',
    sourceName: 'World of Wonder',
    wordCount: 910,
    sectionCount: 13,
    processingOrder: 4,
  ),
  ArticleCard(
    id: 'art_water_power',
    title: 'Water Power',
    category: 'Energy',
    cefrLevel: 'B2',
    sourceName: 'World of Wonder',
    wordCount: 680,
    sectionCount: 8,
    processingOrder: 5,
  ),
];

class MockArticleRepo implements ArticleRepository {
  final ArticleBundle baseBundle;
  final List<ArticleCard> cards;

  MockArticleRepo({
    required this.baseBundle,
    this.cards = sampleFiveCards,
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

  group('FE-07c Unit tests - filterMatchedProgress & buildLibraryOverview', () {
    test('filterMatchedProgress: lọc bỏ bản ghi mồ côi, giữ lại bản ghi khớp', () {
      final progressList = [
        ReadingProgress(
          articleId: 'art_robots',
          lastReadSectionId: 'sec_1',
          lastSectionIndex: 2,
          maxIndexReached: 2,
          progressPercent: 30,
          completed: false,
          lastReadAt: DateTime.parse('2026-11-18T10:00:00Z'),
        ),
        ReadingProgress(
          articleId: 'art_orphan_unknown',
          lastReadSectionId: 'sec_x',
          lastSectionIndex: 1,
          maxIndexReached: 1,
          progressPercent: 10,
          completed: false,
          lastReadAt: DateTime.parse('2026-11-18T09:00:00Z'),
        ),
        ReadingProgress(
          articleId: 'art_eating_well',
          lastReadSectionId: 'sec_8',
          lastSectionIndex: 8,
          maxIndexReached: 8,
          progressPercent: 100,
          completed: true,
          lastReadAt: DateTime.parse('2026-11-17T10:00:00Z'),
        ),
      ];

      final knownIds = {'art_robots', 'art_eating_well', 'art_farming'};
      final matched = filterMatchedProgress(progressList, knownIds);

      expect(matched.length, 2);
      expect(matched.map((p) => p.articleId), containsAll(['art_robots', 'art_eating_well']));
      expect(matched.any((p) => p.articleId == 'art_orphan_unknown'), isFalse);
    });

    test('buildLibraryOverview: sắp xếp Đọc tiếp, Recent articles và kẹp vị trí đoạn x / n', () {
      final progressList = [
        ReadingProgress(
          articleId: 'art_robots',
          lastReadSectionId: 'sec_rob',
          lastSectionIndex: 10, // Vượt quá sectionCount = 7
          maxIndexReached: 10,
          progressPercent: 90,
          completed: false,
          lastReadAt: DateTime.parse('2026-11-18T11:00:00Z'),
        ),
        ReadingProgress(
          articleId: 'art_farming',
          lastReadSectionId: 'sec_farm',
          lastSectionIndex: 1,
          maxIndexReached: 1,
          progressPercent: 20,
          completed: false,
          lastReadAt: DateTime.parse('2026-11-18T09:00:00Z'),
        ),
        ReadingProgress(
          articleId: 'art_eating_well',
          lastReadSectionId: 'sec_ew',
          lastSectionIndex: 8,
          maxIndexReached: 8,
          progressPercent: 100,
          completed: true,
          lastReadAt: DateTime.parse('2026-11-17T10:00:00Z'),
        ),
      ];

      final overview = buildLibraryOverview(
        cards: sampleFiveCards,
        allProgress: progressList,
      );

      // Bài đọc tiếp mới nhất là art_robots
      expect(overview.continueReading, isNotNull);
      expect(overview.continueReading!.card.id, 'art_robots');

      // Đã đọc 1 bài hoàn thành
      expect(overview.completedCount, 1);

      // Recent articles tối đa 5 bài theo processingOrder giảm dần
      expect(overview.recentArticles.length, 5);
      expect(overview.recentArticles.first.id, 'art_water_power'); // order = 5
      expect(overview.recentArticles.last.id, 'art_eating_well'); // order = 1

      // History: đang đọc gồm robots và farming (robots trước vì mới hơn)
      expect(overview.inProgressItems.length, 2);
      expect(overview.inProgressItems[0].card.id, 'art_robots');
      expect(overview.inProgressItems[1].card.id, 'art_farming');

      // History: đã đọc gồm eating well
      expect(overview.completedItems.length, 1);
      expect(overview.completedItems.first.card.id, 'art_eating_well');
    });
  });

  group('FE-07c Widget tests - Trang chủ & Lịch sử đọc', () {
    Widget buildTestApp({
      required ArticleRepository articleRepo,
      required InMemoryReadingProgressRepository progressRepo,
      required InMemorySavedWordsRepository savedWordsRepo,
    }) {
      final fakeRemoteStore = FakeRemoteStore();
      final eventQueueRepo = InMemoryEventQueueRepository();

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

    testWidgets('AC-1: Trang chủ hiển thị khối Đọc tiếp (Robots Đoạn 3 / 7), bấm vào mở /read/art_robots',
        (tester) async {
      final progressRepo = InMemoryReadingProgressRepository();
      final savedWordsRepo = InMemorySavedWordsRepository();

      // art_robots đọc dở ở section index 2 -> Đoạn 3 / 7
      await progressRepo.saveProgress(
        ReadingProgress(
          articleId: 'art_robots',
          lastReadSectionId: 'sec_2',
          lastSectionIndex: 2,
          maxIndexReached: 2,
          progressPercent: 30,
          completed: false,
          lastReadAt: DateTime.parse('2026-11-18T10:00:00Z'),
        ),
      );

      final articleRepo = MockArticleRepo(baseBundle: fixtureBundle);

      await tester.pumpWidget(buildTestApp(
        articleRepo: articleRepo,
        progressRepo: progressRepo,
        savedWordsRepo: savedWordsRepo,
      ));
      await tester.pumpAndSettle();

      // Kiểm tra tiêu đề header Trang chủ
      expect(find.text('Readle'), findsOneWidget);
      expect(find.text('Chào bạn, hôm nay muốn đọc gì?'), findsOneWidget);

      // Kiểm tra khối Đọc tiếp
      expect(find.text('Đọc tiếp'), findsWidgets);
      expect(find.text('Robots'), findsWidgets);
      expect(find.text('Đoạn 3 / 7'), findsOneWidget);

      // Bấm nút Đọc tiếp trong card
      final continueButtonFinder = find.widgetWithText(FilledButton, 'Đọc tiếp');
      expect(continueButtonFinder, findsOneWidget);
      await tester.tap(continueButtonFinder);
      await tester.pumpAndSettle();

      // Đã mở Reader toàn màn hình (không có NavigationBar)
      expect(find.byType(NavigationBar), findsNothing);
      expect(find.text('Key idea'), findsOneWidget);
    });

    testWidgets('AC-2: Không có bài đọc dở -> khối Đọc tiếp ẩn hoàn toàn, không có placeholder thay thế',
        (tester) async {
      final progressRepo = InMemoryReadingProgressRepository();
      final savedWordsRepo = InMemorySavedWordsRepository();
      final articleRepo = MockArticleRepo(baseBundle: fixtureBundle);

      await tester.pumpWidget(buildTestApp(
        articleRepo: articleRepo,
        progressRepo: progressRepo,
        savedWordsRepo: savedWordsRepo,
      ));
      await tester.pumpAndSettle();

      // Khối Đọc tiếp hoàn toàn không xuất hiện
      expect(find.text('Đọc tiếp'), findsNothing);
      expect(find.textContaining('Đoạn'), findsNothing);

      // Dòng 2 con số: "Đã đọc 0 bài · Đã lưu 0 từ"
      expect(find.text('Đã đọc 0 bài · Đã lưu 0 từ'), findsOneWidget);
    });

    testWidgets('AC-3: Dòng 2 con số (Đã đọc 1 bài · Đã lưu 2 từ), bấm vào mở /history hiển thị 2 nhóm',
        (tester) async {
      final progressRepo = InMemoryReadingProgressRepository();
      final savedWordsRepo = InMemorySavedWordsRepository();

      // 1 bài đang đọc dở: Robots
      await progressRepo.saveProgress(
        ReadingProgress(
          articleId: 'art_robots',
          lastReadSectionId: 'sec_1',
          lastSectionIndex: 1,
          maxIndexReached: 1,
          progressPercent: 15,
          completed: false,
          lastReadAt: DateTime.parse('2026-11-18T10:00:00Z'),
        ),
      );
      // 1 bài đã đọc xong: Eating Well
      await progressRepo.saveProgress(
        ReadingProgress(
          articleId: 'art_eating_well',
          lastReadSectionId: 'sec_8',
          lastSectionIndex: 8,
          maxIndexReached: 8,
          progressPercent: 100,
          completed: true,
          lastReadAt: DateTime.parse('2026-11-17T10:00:00Z'),
        ),
      );

      // 3 từ đã lưu, trong đó 1 từ deleted -> chỉ tính 2 từ
      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w1',
          lemmaKey: 'tend to',
          lexiconEntryId: 'lex_tend_to',
          entryType: 'collocation',
          displayText: 'tend to',
          vi: 'có xu hướng',
          exampleSentence: 'People tend to eat more.',
          cloze: const {'before': 'People ', 'target': 'tend to', 'after': ' eat more.'},
          sourceArticleId: 'art_eating_well',
          savedAt: DateTime.now(),
          dueDate: DateTime.now(),
        ),
      );
      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w2',
          lemmaKey: 'nutrition',
          lexiconEntryId: 'lex_nutrition',
          entryType: 'single_word',
          displayText: 'nutrition',
          vi: 'dinh dưỡng',
          exampleSentence: 'Good nutrition is important.',
          cloze: const {'before': 'Good ', 'target': 'nutrition', 'after': ' is important.'},
          sourceArticleId: 'art_eating_well',
          savedAt: DateTime.now(),
          dueDate: DateTime.now(),
        ),
      );
      await savedWordsRepo.saveWord(
        SavedWord(
          id: 'w3',
          lemmaKey: 'junk food',
          lexiconEntryId: 'lex_junk_food',
          entryType: 'collocation',
          displayText: 'junk food',
          vi: 'đồ ăn vặt',
          exampleSentence: 'Avoid junk food.',
          cloze: const {'before': 'Avoid ', 'target': 'junk food', 'after': '.'},
          sourceArticleId: 'art_eating_well',
          savedAt: DateTime.now(),
          dueDate: DateTime.now(),
        ),
      );
      await savedWordsRepo.deleteWord('junk food');

      final articleRepo = MockArticleRepo(baseBundle: fixtureBundle);

      await tester.pumpWidget(buildTestApp(
        articleRepo: articleRepo,
        progressRepo: progressRepo,
        savedWordsRepo: savedWordsRepo,
      ));
      await tester.pumpAndSettle();

      // Dòng 2 con số chính xác: "Đã đọc 1 bài · Đã lưu 2 từ"
      final statsFinder = find.text('Đã đọc 1 bài · Đã lưu 2 từ');
      expect(statsFinder, findsOneWidget);

      // Cuộn tới dòng 2 con số và bấm vào -> mở màn hình /history
      await tester.ensureVisible(statsFinder);
      await tester.pumpAndSettle();
      await tester.tap(statsFinder);
      await tester.pumpAndSettle();

      // Màn hình /history nằm ngoài shell: không có NavigationBar
      expect(find.byType(NavigationBar), findsNothing);
      expect(find.byType(HistoryScreen), findsOneWidget);
      expect(find.text('Lịch sử đọc'), findsOneWidget);

      // Nhóm "Đang đọc" có bài Robots và nút "Đọc tiếp"
      expect(find.text('Đang đọc'), findsOneWidget);
      expect(find.text('Robots'), findsOneWidget);
      expect(find.widgetWithText(TextButton, 'Đọc tiếp'), findsOneWidget);

      // Nhóm "Đã đọc" có bài Eating Well và nút "Đọc lại"
      expect(find.text('Đã đọc'), findsOneWidget);
      expect(find.text('Eating Well'), findsOneWidget);
      expect(find.widgetWithText(TextButton, 'Đọc lại'), findsOneWidget);

      // Bấm nút back trên AppBar -> quay lại Trang chủ, NavigationBar hiện lại
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();

      expect(find.byType(NavigationBar), findsOneWidget);
      expect(find.text('Chào bạn, hôm nay muốn đọc gì?'), findsOneWidget);
    });

    testWidgets('AC-4: Bấm nút "Xem tất cả" chuyển ngay sang tab Bài báo (index 1)',
        (tester) async {
      final progressRepo = InMemoryReadingProgressRepository();
      final savedWordsRepo = InMemorySavedWordsRepository();
      final articleRepo = MockArticleRepo(baseBundle: fixtureBundle);

      await tester.pumpWidget(buildTestApp(
        articleRepo: articleRepo,
        progressRepo: progressRepo,
        savedWordsRepo: savedWordsRepo,
      ));
      await tester.pumpAndSettle();

      // Bấm "Xem tất cả"
      final viewAllButton = find.text('Xem tất cả');
      expect(viewAllButton, findsOneWidget);
      await tester.tap(viewAllButton);
      await tester.pumpAndSettle();

      // Đã chuyển sang tab Bài báo: NewsScreen hiển thị
      expect(find.text('Bài báo'), findsAtLeastNWidgets(1));
      expect(find.text('Eating Well'), findsOneWidget);
      expect(find.text('Farming'), findsOneWidget);
    });

    testWidgets('AC-5: Luật khớp ADR-021 điểm 6 - Bản ghi mồ côi không hiện, không đếm, không bị xóa',
        (tester) async {
      final progressRepo = InMemoryReadingProgressRepository();
      final savedWordsRepo = InMemorySavedWordsRepository();

      // Progress mồ côi: articleId không có trong sampleFiveCards
      await progressRepo.saveProgress(
        ReadingProgress(
          articleId: 'art_deleted_from_cloud',
          lastReadSectionId: 'sec_cloud',
          lastSectionIndex: 3,
          maxIndexReached: 3,
          progressPercent: 50,
          completed: true,
          lastReadAt: DateTime.parse('2026-11-18T12:00:00Z'),
        ),
      );

      final articleRepo = MockArticleRepo(baseBundle: fixtureBundle);

      await tester.pumpWidget(buildTestApp(
        articleRepo: articleRepo,
        progressRepo: progressRepo,
        savedWordsRepo: savedWordsRepo,
      ));
      await tester.pumpAndSettle();

      // Số bài đã đọc không tăng (vẫn là 0 bài)
      final zeroStatsFinder = find.text('Đã đọc 0 bài · Đã lưu 0 từ');
      expect(zeroStatsFinder, findsOneWidget);

      // Mở /history
      await tester.ensureVisible(zeroStatsFinder);
      await tester.pumpAndSettle();
      await tester.tap(zeroStatsFinder);
      await tester.pumpAndSettle();

      // Màn history hiển thị câu rỗng nhẹ nhàng
      expect(find.text('Chưa có bài đọc nào trong lịch sử.'), findsOneWidget);
      expect(find.text('art_deleted_from_cloud'), findsNothing);

      // Bản ghi mồ côi trong progressRepo KHÔNG bị xóa
      final allStorageProgress = await progressRepo.getAllProgress();
      expect(allStorageProgress.any((p) => p.articleId == 'art_deleted_from_cloud'), isTrue);
    });

    testWidgets('Error state: Khi danh sách bài bị lỗi, không hiện "Đã đọc", ẩn các khối và hiện Thử lại',
        (tester) async {
      final progressRepo = InMemoryReadingProgressRepository();
      final savedWordsRepo = InMemorySavedWordsRepository();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            articleListProvider.overrideWith((ref) async => throw Exception('Network error')),
            readingProgressRepositoryProvider.overrideWithValue(progressRepo),
            savedWordsRepositoryProvider.overrideWithValue(savedWordsRepo),
          ],
          child: const ReadleApp(),
        ),
      );
      await tester.pumpAndSettle();

      // KHÔNG được hiện text chứa 'Đã đọc' (không có "Đã đọc 0 bài")
      expect(find.textContaining('Đã đọc'), findsNothing);

      // Ẩn khối Đọc tiếp & Bài mới
      expect(find.text('Bài mới'), findsNothing);
      expect(find.text('Xem tất cả'), findsNothing);

      // Hiện câu nhẹ nhàng và nút Thử lại
      expect(find.text('Chưa tải được bài, thử lại khi có mạng nhé.'), findsOneWidget);
      expect(find.text('Thử lại'), findsOneWidget);
    });

    testWidgets('No-pressure UX: Không có %, không có streak, không có badge',
        (tester) async {
      final progressRepo = InMemoryReadingProgressRepository();
      final savedWordsRepo = InMemorySavedWordsRepository();

      await progressRepo.saveProgress(
        ReadingProgress(
          articleId: 'art_robots',
          lastReadSectionId: 'sec_rob_2',
          lastSectionIndex: 2,
          maxIndexReached: 2,
          progressPercent: 30,
          completed: false,
          lastReadAt: DateTime.parse('2026-11-18T10:00:00Z'),
        ),
      );

      final articleRepo = MockArticleRepo(baseBundle: fixtureBundle);

      await tester.pumpWidget(buildTestApp(
        articleRepo: articleRepo,
        progressRepo: progressRepo,
        savedWordsRepo: savedWordsRepo,
      ));
      await tester.pumpAndSettle();

      // Không có ký hiệu %
      expect(find.textContaining('%'), findsNothing);

      // Không có từ streak
      expect(find.textContaining(RegExp(r'streak', caseSensitive: false)), findsNothing);

      // Không có badge trên AppShell
      expect(find.descendant(of: find.byType(AppShell), matching: find.byType(Badge)),
          findsNothing);
    });
  });
}
