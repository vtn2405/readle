import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:readle/app.dart';
import 'package:readle/core/theme/app_colors.dart';
import 'package:readle/core/theme/app_theme.dart';
import 'package:readle/data/models/article_bundle.dart';
import 'package:readle/data/models/article_card.dart';
import 'package:readle/data/models/local_models.dart';
import 'package:readle/data/providers/local_providers.dart';
import 'package:readle/data/providers/repository_providers.dart';
import 'package:readle/data/providers/sync_providers.dart';
import 'package:readle/data/repositories/article_repository.dart';
import 'package:readle/data/repositories/local_storage_repository.dart';
import 'package:readle/features/library/screens/news_screen.dart';
import 'package:readle/features/library/widgets/article_tile.dart';
import 'package:readle/features/library/widgets/category_style.dart';

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

class MockFiveArticlesRepository implements ArticleRepository {
  final ArticleBundle baseBundle;
  final List<ArticleCard> cards;

  MockFiveArticlesRepository({
    required this.baseBundle,
    this.cards = sampleFiveCards,
  });

  @override
  Future<List<ArticleCard>> list() async => cards;

  @override
  Future<ArticleBundle> get(String id) async {
    // Tạo bundle có 3 sections từ fixture để kiểm tra trạng thái đọc dở (card 1, 2) và hoàn thành (card 3)
    final sec1 = baseBundle.sections.first;
    final sec2 = baseBundle.sections.last;
    final sec3 = Section(
      id: 'sec_ew_3',
      orderIndex: 2,
      title: 'Section 3',
      iconHint: sec2.iconHint,
      keyIdea: sec2.keyIdea,
      tokens: sec2.tokens,
      check: sec2.check,
    );
    return ArticleBundle(
      contractVersion: baseBundle.contractVersion,
      article: baseBundle.article,
      sections: [sec1, sec2, sec3],
      lexicon: baseBundle.lexicon,
      occurrences: baseBundle.occurrences,
      quiz: baseBundle.quiz,
    );
  }
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

  group('FE-07b Unit test categoryStyle', () {
    test('Khớp không phân biệt hoa thường cho cả 4 chủ đề chính (Light & Dark)', () {
      final healthLight = categoryStyle('Health & Nutrition', Brightness.light);
      expect(healthLight.bg, const Color(0xFFDCEFD8));
      expect(healthLight.icon, Icons.restaurant_outlined);

      final healthDark = categoryStyle('HEALTH & NUTRITION', Brightness.dark);
      expect(healthDark.bg, const Color(0xFF22352A));
      expect(healthDark.icon, Icons.restaurant_outlined);

      final scienceLight = categoryStyle(
        'science & technology',
        Brightness.light,
      );
      expect(scienceLight.bg, const Color(0xFFDCE6F7));
      expect(scienceLight.icon, Icons.memory_outlined);

      final foodLight = categoryStyle('Food & Farming', Brightness.light);
      expect(foodLight.bg, const Color(0xFFF6E7C8));
      expect(foodLight.icon, Icons.agriculture_outlined);

      // "energy" (chữ thường) khớp Energy
      final energyLight = categoryStyle('energy', Brightness.light);
      expect(energyLight.bg, const Color(0xFFE6E0F5));
      expect(energyLight.icon, Icons.bolt_outlined);

      final energyDark = categoryStyle('  energy ', Brightness.dark);
      expect(energyDark.bg, const Color(0xFF2D2843));
      expect(energyDark.icon, Icons.bolt_outlined);
    });

    test(
      'Chủ đề lạ ("Sports", "Travel", "Places", "Culture") trả về màu trung tính và Icons.article_outlined ở cả sáng lẫn tối',
      () {
        final sportsLight = categoryStyle('Sports', Brightness.light);
        expect(sportsLight.bg, const Color(0xFFECECEC));
        expect(sportsLight.icon, Icons.article_outlined);

        final sportsDark = categoryStyle('Sports', Brightness.dark);
        expect(sportsDark.bg, const Color(0xFF2A2A2A));
        expect(sportsDark.icon, Icons.article_outlined);

        final travelLight = categoryStyle('Travel', Brightness.light);
        expect(travelLight.bg, const Color(0xFFECECEC));
        expect(travelLight.icon, Icons.article_outlined);

        final travelDark = categoryStyle('Travel', Brightness.dark);
        expect(travelDark.bg, const Color(0xFF2A2A2A));
        expect(travelDark.icon, Icons.article_outlined);

        final placesLight = categoryStyle('Places', Brightness.light);
        expect(placesLight.bg, const Color(0xFFECECEC));
        expect(placesLight.icon, Icons.article_outlined);

        final placesDark = categoryStyle('Places', Brightness.dark);
        expect(placesDark.bg, const Color(0xFF2A2A2A));
        expect(placesDark.icon, Icons.article_outlined);

        final cultureLight = categoryStyle('Culture', Brightness.light);
        expect(cultureLight.bg, const Color(0xFFECECEC));
        expect(cultureLight.icon, Icons.article_outlined);

        final cultureDark = categoryStyle('Culture', Brightness.dark);
        expect(cultureDark.bg, const Color(0xFF2A2A2A));
        expect(cultureDark.icon, Icons.article_outlined);
      },
    );

    test(
      'FE-07e: Chủ đề thứ 5 "Travel & Money" khớp màu và Icons.flight_outlined (Light & Dark, trim)',
      () {
        final travelMoneyLight = categoryStyle('Travel & Money', Brightness.light);
        expect(travelMoneyLight.bg, const Color(0xFFFBE3D2));
        expect(travelMoneyLight.bg, AppColors.categoryTravelLight);
        expect(travelMoneyLight.icon, Icons.flight_outlined);

        final travelMoneyDark = categoryStyle('travel & money', Brightness.dark);
        expect(travelMoneyDark.bg, const Color(0xFF3E2B20));
        expect(travelMoneyDark.bg, AppColors.categoryTravelDark);
        expect(travelMoneyDark.icon, Icons.flight_outlined);

        final trimmedLight = categoryStyle('  Travel & Money  ', Brightness.light);
        expect(trimmedLight.bg, const Color(0xFFFBE3D2));
        expect(trimmedLight.icon, Icons.flight_outlined);
      },
    );

    test(
      'FE-07f: Chủ đề thứ 6 "Places & Culture" khớp màu và Icons.account_balance_outlined (Light & Dark, trim), khác màu Energy',
      () {
        final placesLight = categoryStyle('Places & Culture', Brightness.light);
        expect(placesLight.bg, const Color(0xFFF6DCE5));
        expect(placesLight.bg, AppColors.categoryPlacesLight);
        expect(placesLight.icon, Icons.account_balance_outlined);

        final placesDark = categoryStyle(' places & culture ', Brightness.dark);
        expect(placesDark.bg, const Color(0xFF3D2632));
        expect(placesDark.bg, AppColors.categoryPlacesDark);
        expect(placesDark.icon, Icons.account_balance_outlined);

        // Khác màu Energy ở cả 2 chế độ (tránh lỗi xung đột màu ở Run #81)
        expect(placesLight.bg != AppColors.categoryEnergyLight, isTrue);
        expect(placesDark.bg != AppColors.categoryEnergyDark, isTrue);
      },
    );
  });

  group('FE-07b Widget test NewsScreen & ArticleTile', () {
    Widget buildNewsTestWidget({
      InMemoryReadingProgressRepository? progressRepo,
      List<ArticleCard> cards = sampleFiveCards,
      TextScaler textScaler = TextScaler.noScaling,
    }) {
      final repo = progressRepo ?? InMemoryReadingProgressRepository();
      return ProviderScope(
        overrides: [
          articleListProvider.overrideWith((ref) async => cards),
          readingProgressRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp(
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          builder: (context, child) {
            return MediaQuery(
              data: MediaQuery.of(context).copyWith(textScaler: textScaler),
              child: child!,
            );
          },
          home: const NewsScreen(),
        ),
      );
    }

    testWidgets(
      'AC-1: Hiện đủ 5 tiêu đề; thẻ Eating Well có "A2", "~4 phút đọc", nền khối màu #DCEFD8 và Semantics button',
      (tester) async {
        await tester.pumpWidget(buildNewsTestWidget());
        await tester.pumpAndSettle();

        // 5 thẻ hiện đủ tiêu đề
        expect(find.text('Eating Well'), findsOneWidget);
        expect(find.text('Robots'), findsOneWidget);
        expect(find.text('Farming'), findsOneWidget);
        expect(find.text('Rocket Science'), findsOneWidget);
        expect(find.text('Water Power'), findsOneWidget);

        // Thẻ Eating Well có chữ "A2" và "~4 phút đọc"
        final eatingWellTile = find.ancestor(
          of: find.text('Eating Well'),
          matching: find.byType(ArticleTile),
        );
        expect(eatingWellTile, findsOneWidget);
        expect(
          find.descendant(of: eatingWellTile, matching: find.text('A2')),
          findsOneWidget,
        );
        expect(
          find.descendant(
            of: eatingWellTile,
            matching: find.text('~4 phút đọc'),
          ),
          findsOneWidget,
        );

        // Nền khối màu Eating Well = #DCEFD8 (sáng)
        final coverContainer = tester.widget<Container>(
          find.byKey(const ValueKey('article_cover_art_eating_well')),
        );
        final boxDeco = coverContainer.decoration as BoxDecoration;
        expect(boxDeco.color, const Color(0xFFDCEFD8));
        expect(boxDeco.color, AppColors.categoryHealthLight);

        // Semantics button có excludeSemantics và label đầy đủ thông tin
        final semantics = tester.getSemantics(eatingWellTile);
        expect(
          semantics.label,
          'Eating Well, Health & Nutrition, A2, khoảng 4 phút đọc',
        );
      },
    );

    testWidgets(
      'AC-2: Lọc theo chủ đề "Science & Technology", kết hợp cấp độ "B2", quay về "Tất cả" + "Mọi cấp độ", và trạng thái lọc rỗng',
      (tester) async {
        await tester.pumpWidget(buildNewsTestWidget());
        await tester.pumpAndSettle();

        // Chọn chip "Science & Technology" -> chỉ còn Robots và Rocket Science
        await tester.tap(
          find.widgetWithText(ChoiceChip, 'Science & Technology'),
        );
        await tester.pumpAndSettle();

        expect(find.text('Robots'), findsOneWidget);
        expect(find.text('Rocket Science'), findsOneWidget);
        expect(find.text('Eating Well'), findsNothing);
        expect(find.text('Farming'), findsNothing);
        expect(find.text('Water Power'), findsNothing);

        // Chọn thêm chip "B2" -> chỉ còn Rocket Science
        await tester.tap(find.widgetWithText(ChoiceChip, 'B2'));
        await tester.pumpAndSettle();

        expect(find.text('Rocket Science'), findsOneWidget);
        expect(find.text('Robots'), findsNothing);

        // Lọc tổ hợp rỗng ("Health & Nutrition" + "B2") -> thông báo nhẹ nhàng
        await tester.tap(find.widgetWithText(ChoiceChip, 'Health & Nutrition'));
        await tester.pumpAndSettle();

        expect(
          find.text('Chưa có bài phù hợp, thử chọn khác nhé.'),
          findsOneWidget,
        );

        // Chọn "Tất cả" + "Mọi cấp độ" -> hiện lại đủ 5 bài
        await tester.tap(find.widgetWithText(ChoiceChip, 'Tất cả'));
        await tester.pumpAndSettle();
        await tester.tap(find.widgetWithText(ChoiceChip, 'Mọi cấp độ'));
        await tester.pumpAndSettle();

        expect(find.text('Eating Well'), findsOneWidget);
        expect(find.text('Robots'), findsOneWidget);
        expect(find.text('Farming'), findsOneWidget);
        expect(find.text('Rocket Science'), findsOneWidget);
        expect(find.text('Water Power'), findsOneWidget);
      },
    );

    testWidgets(
      'AC-3 & AC-5: Eating Well completed=true hiện "Đã đọc", Robots chưa xong hiện "Đang đọc", không có "%" hay "chưa đọc"',
      (tester) async {
        final progressRepo = InMemoryReadingProgressRepository({
          'art_eating_well': ReadingProgress(
            articleId: 'art_eating_well',
            lastSectionIndex: 8,
            maxIndexReached: 8,
            lastReadSectionId: 'sec_ew_9',
            progressPercent: 100,
            completed: true,
            lastReadAt: DateTime(2026, 11, 18),
          ),
          'art_robots': ReadingProgress(
            articleId: 'art_robots',
            lastSectionIndex: 2,
            maxIndexReached: 2,
            lastReadSectionId: 'sec_rb_3',
            progressPercent: 43,
            completed: false,
            lastReadAt: DateTime(2026, 11, 18),
          ),
        });

        await tester.pumpWidget(
          buildNewsTestWidget(progressRepo: progressRepo),
        );
        await tester.pumpAndSettle();

        final eatingWellTile = find.ancestor(
          of: find.text('Eating Well'),
          matching: find.byType(ArticleTile),
        );
        expect(
          find.descendant(of: eatingWellTile, matching: find.text('Đã đọc')),
          findsOneWidget,
        );
        expect(
          find.descendant(
            of: eatingWellTile,
            matching: find.byIcon(Icons.check_circle_outline),
          ),
          findsOneWidget,
        );

        final robotsTile = find.ancestor(
          of: find.text('Robots'),
          matching: find.byType(ArticleTile),
        );
        expect(
          find.descendant(of: robotsTile, matching: find.text('Đang đọc')),
          findsOneWidget,
        );

        // Semantics của thẻ có trạng thái tiến trình
        final eatingWellSemantics = tester.getSemantics(eatingWellTile);
        expect(
          eatingWellSemantics.label,
          'Eating Well, Health & Nutrition, A2, khoảng 4 phút đọc, Đã đọc',
        );

        final robotsSemantics = tester.getSemantics(robotsTile);
        expect(
          robotsSemantics.label,
          'Robots, Science & Technology, B1, khoảng 4 phút đọc, Đang đọc',
        );

        // Không thẻ nào có ký tự '%' hoặc chữ 'chưa đọc' (no-pressure UX)
        expect(find.textContaining('%'), findsNothing);
        expect(
          find.textContaining(RegExp('chưa đọc', caseSensitive: false)),
          findsNothing,
        );
      },
    );

    testWidgets(
      'Mở Eating Well -> sang card 2 -> pop quay lại tab Bài báo -> thẻ tự cập nhật hiện "Đang đọc"',
      (tester) async {
        final progressRepo = InMemoryReadingProgressRepository();
        final savedWordsRepo = InMemorySavedWordsRepository();
        final eventQueueRepo = InMemoryEventQueueRepository();
        final fakeRemoteStore = FakeRemoteStore();

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              articleRepositoryProvider.overrideWithValue(
                MockFiveArticlesRepository(baseBundle: fixtureBundle),
              ),
              readingProgressRepositoryProvider.overrideWithValue(progressRepo),
              savedWordsRepositoryProvider.overrideWithValue(savedWordsRepo),
              eventQueueRepositoryProvider.overrideWithValue(eventQueueRepo),
              remoteStoreProvider.overrideWithValue(fakeRemoteStore),
            ],
            child: const ReadleApp(),
          ),
        );
        await tester.pumpAndSettle();

        // Sang tab Bài báo
        await tester.tap(find.text('Bài báo'));
        await tester.pumpAndSettle();

        // Ban đầu chưa đọc -> không có "Đang đọc" hay "Đã đọc"
        expect(find.text('Đang đọc'), findsNothing);
        expect(find.text('Đã đọc'), findsNothing);

        // Chạm mở Eating Well
        await tester.tap(find.text('Eating Well'));
        await tester.pumpAndSettle();

        expect(find.text('1 / 3'), findsOneWidget);

        // Vuốt sang card 2 (2 / 3, chưa completed)
        await tester.drag(find.byType(PageView), const Offset(-500, 0));
        await tester.pumpAndSettle();
        expect(find.text('2 / 3'), findsOneWidget);

        // Pop quay lại tab Bài báo
        await tester.tap(find.byType(BackButton));
        await tester.pumpAndSettle();

        // Thẻ Eating Well đã tự cập nhật hiện "Đang đọc"
        final eatingWellTile = find.ancestor(
          of: find.text('Eating Well'),
          matching: find.byType(ArticleTile),
        );
        expect(
          find.descendant(of: eatingWellTile, matching: find.text('Đang đọc')),
          findsOneWidget,
        );
      },
    );

    testWidgets(
      'Lưới 2 cột ở chiều rộng 800dp và textScaler 1.3 không bị tràn chữ (overflow)',
      (tester) async {
        tester.view.physicalSize = const Size(800, 1000);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
        });

        final progressRepo = InMemoryReadingProgressRepository({
          'art_eating_well': ReadingProgress(
            articleId: 'art_eating_well',
            lastSectionIndex: 8,
            maxIndexReached: 8,
            lastReadSectionId: 'sec_ew_9',
            progressPercent: 100,
            completed: true,
            lastReadAt: DateTime(2026, 11, 18),
          ),
        });

        await tester.pumpWidget(
          buildNewsTestWidget(
            progressRepo: progressRepo,
            textScaler: const TextScaler.linear(1.3),
          ),
        );
        await tester.pumpAndSettle();

        // Không có bất kỳ lỗi tràn bố cục nào
        expect(tester.takeException(), isNull);
        expect(find.text('Eating Well'), findsOneWidget);
        expect(find.text('Rocket Science'), findsOneWidget);
      },
    );

    testWidgets(
      'FE-07e: Card "Travel & Money" hiện đúng khối màu #FBE3D2, icon flight_outlined, hàng chip lọc có "Travel & Money" và Semantics đúng',
      (tester) async {
        const holidayCard = ArticleCard(
          id: 'art_holiday_travel',
          title: 'Holiday Travel',
          category: 'Travel & Money',
          cefrLevel: 'B2',
          sourceName: 'The New York Times',
          wordCount: 1302,
          sectionCount: 10,
          processingOrder: 8,
        );

        await tester.pumpWidget(
          buildNewsTestWidget(
            cards: [...sampleFiveCards, holidayCard],
          ),
        );
        await tester.pumpAndSettle();

        // Thẻ Holiday Travel hiện diện
        final holidayTile = find.ancestor(
          of: find.text('Holiday Travel'),
          matching: find.byType(ArticleTile),
        );
        expect(holidayTile, findsOneWidget);

        // Khối màu nền của thẻ là #FBE3D2 (AppColors.categoryTravelLight)
        final coverFinder =
            find.byKey(const ValueKey('article_cover_art_holiday_travel'));
        final coverContainer = tester.widget<Container>(coverFinder);
        final boxDeco = coverContainer.decoration as BoxDecoration;
        expect(boxDeco.color, const Color(0xFFFBE3D2));
        expect(boxDeco.color, AppColors.categoryTravelLight);

        // Icon trong khối là flight_outlined
        expect(
          find.descendant(
            of: coverFinder,
            matching: find.byIcon(Icons.flight_outlined),
          ),
          findsOneWidget,
        );

        // Hàng chip lọc có chip "Travel & Money" (cuộn vào tầm nhìn để chạm)
        final travelChip = find.widgetWithText(ChoiceChip, 'Travel & Money');
        expect(travelChip, findsOneWidget);
        await tester.ensureVisible(travelChip);
        await tester.pumpAndSettle();

        // Lọc theo "Travel & Money" -> chỉ còn Holiday Travel
        await tester.tap(travelChip);
        await tester.pumpAndSettle();

        expect(find.text('Holiday Travel'), findsOneWidget);
        expect(find.text('Eating Well'), findsNothing);
        expect(find.text('Robots'), findsNothing);

        // Kiểm tra Semantics của thẻ không có progress (1302 từ / 150 = 9 phút)
        final semantics = tester.getSemantics(holidayTile);
        expect(
          semantics.label,
          'Holiday Travel, Travel & Money, B2, khoảng 9 phút đọc',
        );
      },
    );

    testWidgets(
      'FE-07f: Card "Places & Culture" hiện đúng khối màu #F6DCE5, icon account_balance_outlined, hàng chip lọc có "Places & Culture" và Semantics đúng',
      (tester) async {
        const parisCard = ArticleCard(
          id: 'art_paris',
          title: 'Paris',
          category: 'Places & Culture',
          cefrLevel: 'B1',
          sourceName: 'World of Wonder',
          wordCount: 933,
          sectionCount: 11,
          processingOrder: 9,
        );

        await tester.pumpWidget(
          buildNewsTestWidget(
            cards: [...sampleFiveCards, parisCard],
          ),
        );
        await tester.pumpAndSettle();

        // Thẻ Paris hiện diện
        final parisTile = find.ancestor(
          of: find.text('Paris'),
          matching: find.byType(ArticleTile),
        );
        expect(parisTile, findsOneWidget);

        // Khối màu nền của thẻ là #F6DCE5 (AppColors.categoryPlacesLight)
        final coverFinder =
            find.byKey(const ValueKey('article_cover_art_paris'));
        final coverContainer = tester.widget<Container>(coverFinder);
        final boxDeco = coverContainer.decoration as BoxDecoration;
        expect(boxDeco.color, const Color(0xFFF6DCE5));
        expect(boxDeco.color, AppColors.categoryPlacesLight);

        // Icon trong khối là account_balance_outlined
        expect(
          find.descendant(
            of: coverFinder,
            matching: find.byIcon(Icons.account_balance_outlined),
          ),
          findsOneWidget,
        );

        // Hàng chip lọc có chip "Places & Culture" (cuộn vào tầm nhìn để chạm)
        final placesChip = find.widgetWithText(ChoiceChip, 'Places & Culture');
        expect(placesChip, findsOneWidget);
        await tester.ensureVisible(placesChip);
        await tester.pumpAndSettle();

        // Lọc theo "Places & Culture" -> chỉ còn Paris
        await tester.tap(placesChip);
        await tester.pumpAndSettle();

        expect(find.text('Paris'), findsOneWidget);
        expect(find.text('Eating Well'), findsNothing);
        expect(find.text('Robots'), findsNothing);

        // Kiểm tra Semantics của thẻ không có progress (933 từ / 150 = 6 phút)
        final semantics = tester.getSemantics(parisTile);
        expect(
          semantics.label,
          'Paris, Places & Culture, B1, khoảng 6 phút đọc',
        );
      },
    );
  });
}
