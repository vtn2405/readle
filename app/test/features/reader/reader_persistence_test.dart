import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:readle/core/theme/app_theme.dart';
import 'package:readle/data/models/article_bundle.dart';
import 'package:readle/data/models/article_card.dart';
import 'package:readle/data/providers/local_providers.dart';
import 'package:readle/data/providers/repository_providers.dart';
import 'package:readle/data/repositories/article_repository.dart';
import 'package:readle/data/repositories/local_storage_repository.dart';
import 'package:readle/features/reader/providers/reader_state.dart';
import 'package:readle/features/reader/screens/reader_screen.dart';

class MockArticleRepository implements ArticleRepository {
  final ArticleBundle bundle;

  MockArticleRepository(this.bundle);

  @override
  Future<List<ArticleCard>> list() async => [];

  @override
  Future<ArticleBundle> get(String id) async => bundle;
}

void main() {
  late ArticleBundle eatingWellBundle;

  setUpAll(() {
    final file = File('../fixtures/article_eating_well.json');
    final jsonStr = file.existsSync()
        ? file.readAsStringSync()
        : File('assets/fixtures/article_eating_well.json').readAsStringSync();
    eatingWellBundle =
        ArticleBundle.fromJson(jsonDecode(jsonStr) as Map<String, dynamic>);
  });

  Widget buildReaderApp({
    required ReadingProgressRepository progressRepo,
    required ArticleBundle bundle,
  }) {
    return ProviderScope(
      overrides: [
        articleRepositoryProvider.overrideWithValue(
          MockArticleRepository(bundle),
        ),
        readingProgressRepositoryProvider.overrideWithValue(
          progressRepo,
        ),
      ],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        home: const ReaderScreen(articleId: 'art_eating_well'),
      ),
    );
  }

  group('Reader Persistence & Resume Reading Tests (FE-05 / AC-5)', () {
    testWidgets(
        'Tắt app mở lại vẫn đọc tiếp đúng card (dựng ProviderScope mới hoàn toàn)',
        (tester) async {
      final sharedProgressRepo = InMemoryReadingProgressRepository();

      // ==========================================
      // PHIÊN 1: Mở bài đọc lần đầu
      // ==========================================
      await tester.pumpWidget(buildReaderApp(
        progressRepo: sharedProgressRepo,
        bundle: eatingWellBundle,
      ));
      await tester.pumpAndSettle();

      // Ban đầu mở ở card 1: "1 / 2"
      expect(find.text('1 / 2'), findsOneWidget);
      expect(find.text('Eating Well'), findsOneWidget);

      // Lướt sang Card 2
      await tester.drag(find.byType(PageView), const Offset(-500, 0));
      await tester.pumpAndSettle();

      // Hiển thị Card 2: "2 / 2"
      expect(find.text('2 / 2'), findsOneWidget);

      // Kiểm tra repository đã lưu tiến trình của card 2
      final savedProgress = sharedProgressRepo.getProgressSync('art_eating_well');
      expect(savedProgress, isNotNull);
      expect(savedProgress!.lastSectionIndex, 1);
      expect(savedProgress.lastReadSectionId, 'sec_ew_2');
      expect(savedProgress.maxIndexReached, 1);
      expect(savedProgress.progressPercent, 100);
      expect(savedProgress.completed, isTrue);

      // ==========================================
      // PHIÊN 2: Thoát app hoàn toàn và mở lại bài
      // Dựng ProviderScope mới hoàn toàn nhưng dùng chung sharedProgressRepo
      // ==========================================
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();

      await tester.pumpWidget(buildReaderApp(
        progressRepo: sharedProgressRepo,
        bundle: eatingWellBundle,
      ));
      await tester.pumpAndSettle();

      // Màn hình phải tự động hiển thị ngay Card 2 ("2 / 2")
      expect(find.text('2 / 2'), findsOneWidget);
    });

    testWidgets(
        'Tới card 2 -> lùi về card 1 -> mở lại: mở ở card 1, progressPercent vẫn 100, completed vẫn true',
        (tester) async {
      final sharedProgressRepo = InMemoryReadingProgressRepository();

      // 1. Mở bài đọc
      await tester.pumpWidget(buildReaderApp(
        progressRepo: sharedProgressRepo,
        bundle: eatingWellBundle,
      ));
      await tester.pumpAndSettle();

      // 2. Lướt sang Card 2
      await tester.drag(find.byType(PageView), const Offset(-500, 0));
      await tester.pumpAndSettle();
      expect(find.text('2 / 2'), findsOneWidget);

      // 3. Lướt lùi về Card 1
      await tester.drag(find.byType(PageView), const Offset(500, 0));
      await tester.pumpAndSettle();
      expect(find.text('1 / 2'), findsOneWidget);

      // Kiểm tra repository: lastSectionIndex = 0 nhưng maxIndexReached = 1, progress = 100%, completed = true
      final savedProgress = sharedProgressRepo.getProgressSync('art_eating_well');
      expect(savedProgress, isNotNull);
      expect(savedProgress!.lastSectionIndex, 0);
      expect(savedProgress.lastReadSectionId, 'sec_ew_1');
      expect(savedProgress.maxIndexReached, 1);
      expect(savedProgress.progressPercent, 100);
      expect(savedProgress.completed, isTrue);

      // 4. Thoát app và mở lại với ProviderScope mới hoàn toàn
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();

      await tester.pumpWidget(buildReaderApp(
        progressRepo: sharedProgressRepo,
        bundle: eatingWellBundle,
      ));
      await tester.pumpAndSettle();

      // Kết quả: mở ở Card 1 ("1 / 2")
      expect(find.text('1 / 2'), findsOneWidget);

      // Xác minh state vẫn giữ tiến độ 100% và completed = true
      final element = tester.element(find.byType(ReaderScreen));
      final container = ProviderScope.containerOf(element);
      final readerState = container.read(readerProvider('art_eating_well'));
      expect(readerState.currentSectionIndex, 0);
      expect(readerState.progressPercent, 100);
      expect(readerState.isCompleted, isTrue);

      // AC-7 (no-pressure UX): màn đọc chỉ có chỉ số vị trí "1 / 2", không có streak hay badge phán xét nào
      expect(find.textContaining(RegExp(r'streak', caseSensitive: false)), findsNothing);
      expect(find.textContaining('chưa hoàn thành'), findsNothing);
    });
  });
}
