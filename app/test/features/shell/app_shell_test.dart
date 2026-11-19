import 'dart:convert';
import 'dart:io';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:readle/app.dart';
import 'package:readle/core/theme/app_colors.dart';
import 'package:readle/core/theme/app_theme.dart';
import 'package:readle/data/models/article_bundle.dart';
import 'package:readle/data/models/article_card.dart';
import 'package:readle/data/providers/local_providers.dart';
import 'package:readle/data/providers/repository_providers.dart';
import 'package:readle/data/providers/sync_providers.dart';
import 'package:readle/data/repositories/article_repository.dart';
import 'package:readle/data/repositories/local_storage_repository.dart';
import 'package:readle/features/reader/widgets/phrase_bottom_sheet.dart';
import 'package:readle/features/reader/widgets/word_tooltip.dart';
import 'package:readle/features/shell/app_shell.dart';

import '../../helpers/fake_remote_store.dart';

class MockArticleRepository implements ArticleRepository {
  final ArticleBundle bundle;
  MockArticleRepository(this.bundle);

  @override
  Future<ArticleBundle> get(String id) async => bundle;

  @override
  Future<List<ArticleCard>> list() async {
    return [
      ArticleCard(
        id: bundle.article.id,
        title: bundle.article.title,
        category: bundle.article.category,
        cefrLevel: bundle.article.cefrLevel,
        sourceName: bundle.article.source.name,
        wordCount: 566,
        sectionCount: bundle.sections.length,
      ),
    ];
  }
}

void main() {
  late ArticleBundle bundle;
  late InMemoryReadingProgressRepository progressRepo;
  late InMemorySavedWordsRepository savedWordsRepo;
  late InMemoryEventQueueRepository eventQueueRepo;
  late FakeRemoteStore fakeRemoteStore;

  setUpAll(() {
    final file = File('../fixtures/article_eating_well.json');
    final jsonStr = file.existsSync()
        ? file.readAsStringSync()
        : File('assets/fixtures/article_eating_well.json').readAsStringSync();
    bundle = ArticleBundle.fromJson(jsonDecode(jsonStr) as Map<String, dynamic>);
  });

  setUp(() {
    progressRepo = InMemoryReadingProgressRepository();
    savedWordsRepo = InMemorySavedWordsRepository();
    eventQueueRepo = InMemoryEventQueueRepository();
    fakeRemoteStore = FakeRemoteStore();
  });

  Widget buildTestApp({ThemeMode themeMode = ThemeMode.light}) {
    return ProviderScope(
      overrides: [
        articleRepositoryProvider.overrideWithValue(MockArticleRepository(bundle)),
        readingProgressRepositoryProvider.overrideWithValue(progressRepo),
        savedWordsRepositoryProvider.overrideWithValue(savedWordsRepo),
        eventQueueRepositoryProvider.overrideWithValue(eventQueueRepo),
        remoteStoreProvider.overrideWithValue(fakeRemoteStore),
      ],
      child: ReadleAppTestWrapper(themeMode: themeMode),
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
        if (found) break;
      }
    }
  }

  group('FE-07a Khung 4 tab + Theme 2 lớp + Tab Hồ sơ', () {
    testWidgets(
        'AC-1: Khởi động app có NavigationBar 4 tab, không có Dashboard, không có settings trên AppBar, tab Bài báo hiển thị danh sách bài',
        (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // NavigationBar có đúng 4 nhãn
      final navBarFinder = find.byType(NavigationBar);
      expect(navBarFinder, findsOneWidget);
      expect(find.text('Trang chủ'), findsOneWidget);
      expect(find.text('Bài báo'), findsOneWidget);
      expect(find.text('Đã lưu'), findsOneWidget);
      expect(find.text('Hồ sơ'), findsOneWidget);

      // Không còn Dashboard và không còn icon settings trên Home
      expect(find.text('Dashboard'), findsNothing);
      expect(find.byIcon(Icons.settings_outlined), findsNothing);

      // Chạm "Bài báo" -> hiển thị danh sách bài (Eating Well)
      await tester.tap(find.text('Bài báo'));
      await tester.pumpAndSettle();

      expect(find.text('Eating Well'), findsOneWidget);
    });

    testWidgets(
        'AC-2: Chạm bài báo mở Reader toàn màn hình (không có NavigationBar), nền giấy #E8DDBD, pop quay lại tab Bài báo có NavigationBar',
        (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Sang tab Bài báo
      await tester.tap(find.text('Bài báo'));
      await tester.pumpAndSettle();

      // Chạm vào Eating Well
      await tester.tap(find.text('Eating Well'));
      await tester.pumpAndSettle();

      // Màn đọc mở ra: NavigationBar KHÔNG xuất hiện
      expect(find.byType(NavigationBar), findsNothing);
      expect(find.text('Key idea'), findsOneWidget);

      // Nền Scaffold màn đọc là màu giấy sáng #E8DDBD
      final readerScaffold = tester.widget<Scaffold>(find.byType(Scaffold).last);
      expect(readerScaffold.backgroundColor, AppColors.readerBgLight);

      // Quay lại (pop)
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();

      // Quay lại tab Bài báo: NavigationBar hiện lại
      expect(find.byType(NavigationBar), findsOneWidget);
      expect(find.text('Eating Well'), findsOneWidget);
    });

    testWidgets(
        'AC-3: Trong màn đọc, sheet mục từ và tooltip kế thừa theme giấy sáng (#F2EBD3 / #FAF6EE)',
        (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Vào bài đọc
      await tester.tap(find.text('Bài báo'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Eating Well'));
      await tester.pumpAndSettle();

      // Chạm vào từ "tend" để mở sheet mục từ (PhraseBottomSheet cho cụm "tend to")
      await tapWordToken(tester, 'tend');
      await tester.pumpAndSettle();

      expect(find.byType(PhraseBottomSheet), findsOneWidget);

      // Theme của bottom sheet phải kế thừa readerLight với surfaceLight #F2EBD3
      final context = tester.element(find.byType(PhraseBottomSheet));
      final theme = Theme.of(context);
      expect(theme.scaffoldBackgroundColor, AppColors.readerBgLight);
      expect(theme.colorScheme.surface, AppColors.readerSurfaceLight);

      // Kiểm màu nền thật của BottomSheet ([R-FE-07a] (b))
      final bottomSheetMaterial = tester.widget<Material>(
        find
            .ancestor(
              of: find.byType(PhraseBottomSheet),
              matching: find.byType(Material),
            )
            .first,
      );
      expect(bottomSheetMaterial.color, AppColors.readerSurfaceLight);

      // Đóng sheet và chạm từ thường "health" để kiểm tra WordTooltip ([R-FE-07a] (a))
      Navigator.of(context).pop();
      await tester.pumpAndSettle();

      await tapWordToken(tester, 'health');
      await tester.pumpAndSettle();

      expect(find.byType(WordTooltip), findsOneWidget);
      final tooltipContext = tester.element(find.byType(WordTooltip));
      final tooltipTheme = Theme.of(tooltipContext);
      expect(tooltipTheme.colorScheme.surface, AppColors.readerSurfaceLight);
      expect(tooltipTheme.colorScheme.onSurface, AppColors.readerTextPrimaryLight);
    });

    testWidgets(
        'AC-4: Dark theme có nền khung #121212, nền màn đọc #171310 và tooltip ăn theme giấy tối',
        (tester) async {
      await tester.pumpWidget(buildTestApp(themeMode: ThemeMode.dark));
      await tester.pumpAndSettle();

      // Nền Scaffold khung ở dark theme là #121212
      final shellScaffold = tester.widget<Scaffold>(find.byType(Scaffold).first);
      expect(shellScaffold.backgroundColor, AppColors.shellBgDark);

      // Vào bài đọc
      await tester.tap(find.text('Bài báo'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Eating Well'));
      await tester.pumpAndSettle();

      // Nền Scaffold màn đọc ở dark theme là #171310
      final readerScaffold = tester.widget<Scaffold>(find.byType(Scaffold).last);
      expect(readerScaffold.backgroundColor, AppColors.readerBgDark);

      // Chạm "health" ở dark mode: tooltip kế thừa readerDark và có nền #3A3128 ([R-FE-07a] (a))
      await tapWordToken(tester, 'health');
      await tester.pumpAndSettle();

      expect(find.byType(WordTooltip), findsOneWidget);
      final tooltipContext = tester.element(find.byType(WordTooltip));
      final tooltipTheme = Theme.of(tooltipContext);
      expect(tooltipTheme.colorScheme.surface, AppColors.readerSurfaceDark);
    });

    testWidgets(
        'AC-5: No-pressure: không có Badge trên NavigationBar, tab Hồ sơ và Trang chủ không có số',
        (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Khung AppShell hoàn toàn không có Badge
      expect(find.descendant(of: find.byType(AppShell), matching: find.byType(Badge)),
          findsNothing);

      // Trang chủ: chỉ cho phép 2 định dạng có số là "Đã đọc X bài · Đã lưu Y từ" hoặc "Đoạn x / n"
      final homeDigits = tester.widgetList<Text>(find.textContaining(RegExp(r'\d')));
      for (final t in homeDigits) {
        expect(
          t.data,
          matches(RegExp(r'^(Đã đọc \d+ bài · Đã lưu \d+ từ|Đoạn \d+ / \d+)$')),
        );
      }

      // Chuyển sang tab Hồ sơ
      await tester.tap(find.text('Hồ sơ'));
      await tester.pumpAndSettle();

      expect(find.text('Khách'), findsOneWidget);
      expect(find.text('Đăng nhập để đồng bộ nhiều máy — sẽ có sau'), findsOneWidget);
      expect(find.text('Nhắc nhở đọc bài'), findsOneWidget);
      expect(find.text('Hướng dẫn sử dụng'), findsOneWidget);

      // Không có số liệu thống kê / streak / chữ số trên tab Hồ sơ ([R-FE-07a] (c))
      expect(find.descendant(of: find.byType(AppShell), matching: find.byType(Badge)),
          findsNothing);
      expect(find.textContaining(RegExp(r'\d')), findsNothing);
    });

    testWidgets(
        'Tab Đã lưu mở màn ReviewScreen toàn màn hình (không có NavigationBar)',
        (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Chuyển sang tab Đã lưu
      await tester.tap(find.text('Đã lưu'));
      await tester.pumpAndSettle();

      expect(find.text('Ôn tập từ vựng'), findsOneWidget);

      // Bấm nút Ôn tập từ vựng
      await tester.tap(find.text('Ôn tập từ vựng'));
      await tester.pumpAndSettle();

      // Màn review mở ra ngoài shell: không có NavigationBar
      expect(find.byType(NavigationBar), findsNothing);
      expect(find.text('Ôn tập'), findsOneWidget);

      // Quay lại tab Đã lưu
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();

      expect(find.byType(NavigationBar), findsOneWidget);
      expect(find.text('Đã lưu'), findsWidgets);
    });
  });
}

/// Wrapper kiểm thử cho phép truyền themeMode tùy chỉnh
class ReadleAppTestWrapper extends ConsumerWidget {
  final ThemeMode themeMode;
  const ReadleAppTestWrapper({super.key, this.themeMode = ThemeMode.light});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'Readle',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: themeMode,
      routerConfig: router,
    );
  }
}
