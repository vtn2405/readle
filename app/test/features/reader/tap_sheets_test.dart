import 'dart:convert';
import 'dart:io';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:readle/core/theme/app_theme.dart';
import 'package:readle/data/models/article_bundle.dart';
import 'package:readle/data/models/article_card.dart';
import 'package:readle/data/providers/repository_providers.dart';
import 'package:readle/data/repositories/article_repository.dart';
import 'package:readle/features/reader/screens/reader_screen.dart';
import 'package:readle/features/reader/services/audio_service.dart';
import 'package:readle/features/reader/widgets/entry_detail_block.dart';
import 'package:readle/features/reader/widgets/item_bottom_sheet.dart';
import 'package:readle/features/reader/widgets/phrase_bottom_sheet.dart';
import 'package:readle/features/reader/widgets/word_tooltip.dart';

class MockArticleRepository implements ArticleRepository {
  final ArticleBundle bundle;
  MockArticleRepository(this.bundle);

  @override
  Future<ArticleBundle> get(String id) async => bundle;

  @override
  Future<List<ArticleCard>> list() async => [];
}

class TestAudioService implements AudioService {
  String? lastSpokenText;
  String? lastPlayedUrl;
  double? lastSpeed;
  String? lastFallbackText;
  bool wasStopped = false;

  @override
  Future<void> speak(String text, {double speed = 1.0}) async {
    lastSpokenText = text;
    lastSpeed = speed;
  }

  @override
  Future<void> playUrl(
    String url, {
    double speed = 1.0,
    String? fallbackText,
  }) async {
    lastPlayedUrl = url;
    lastSpeed = speed;
    lastFallbackText = fallbackText;
  }

  @override
  Future<void> stop() async {
    wasStopped = true;
  }

  @override
  void dispose() {}
}

void main() {
  late ArticleBundle bundle;
  late TestAudioService testAudioService;

  setUpAll(() {
    final file = File('../fixtures/article_eating_well.json');
    final jsonStr = file.existsSync()
        ? file.readAsStringSync()
        : File('assets/fixtures/article_eating_well.json').readAsStringSync();
    bundle =
        ArticleBundle.fromJson(jsonDecode(jsonStr) as Map<String, dynamic>);
  });

  setUp(() {
    testAudioService = TestAudioService();
  });

  Widget createTestWidget() {
    return ProviderScope(
      overrides: [
        articleRepositoryProvider.overrideWithValue(
          MockArticleRepository(bundle),
        ),
        audioServiceProvider.overrideWithValue(testAudioService),
      ],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        home: const ReaderScreen(articleId: 'art_eating_well'),
      ),
    );
  }

  /// Helper tìm và kích hoạt TapGestureRecognizer cho token cụ thể
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

  group('Tap Resolution & Sheet 1.1 Tests (FE-04b)', () {
    testWidgets(
        'AC-1: Chạm "tend" hiển thị đầy đủ 6 khối theo thứ tự chuẩn, không có "Xem thêm"',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tapWordToken(tester, 'tend');

      // Xác minh PhraseBottomSheet đã mở (do "tend" thuộc collocation "tend to")
      expect(find.byType(PhraseBottomSheet), findsOneWidget);

      // 1. Tiêu đề + badge + CEFR
      expect(find.text('tend to'), findsOneWidget);
      expect(find.text('Collocation'), findsOneWidget);
      expect(find.text('B1'), findsOneWidget);

      // 2. IPA
      expect(find.text('/tɛnd tu/'), findsOneWidget);

      // 3. Nghĩa Việt theo ngữ cảnh
      expect(find.text('có xu hướng'), findsAtLeastNWidgets(1));

      // 4. Định nghĩa tiếng Anh hiện mặc định
      expect(find.text('to usually do or be something'), findsOneWidget);

      // 5. Câu gốc và ví dụ mới (in đậm mục từ)
      expect(
        find.textContaining('Children tend to sleep more in winter.'),
        findsOneWidget,
      );

      // 6. Nút Lưu
      expect(find.text('Lưu'), findsAtLeastNWidgets(1));

      // Bắt buộc: KHÔNG có chữ "Xem thêm"
      expect(find.text('Xem thêm'), findsNothing);

      // Kiểm tra thứ tự hiển thị dọc: dy tăng dần từ khối 1 đến khối 6
      final dyTitle = tester.getTopLeft(find.text('tend to')).dy;
      final dyCefr = tester.getTopLeft(find.text('B1')).dy;
      final dyIpa = tester.getTopLeft(find.text('/tɛnd tu/')).dy;
      final dyVi = tester.getTopLeft(find.text('có xu hướng').first).dy;
      final dyDef =
          tester.getTopLeft(find.text('to usually do or be something')).dy;
      final dyExample = tester
          .getTopLeft(
              find.textContaining('Children tend to sleep more in winter.'))
          .dy;
      final dySave = tester.getTopLeft(find.text('Lưu').first).dy;

      expect(dyTitle, lessThanOrEqualTo(dyCefr));
      expect(dyTitle, lessThan(dyIpa));
      expect(dyIpa, lessThan(dyVi));
      expect(dyVi, lessThan(dyDef));
      expect(dyDef, lessThan(dyExample));
      expect(dyExample, lessThan(dySave));

      // AC-8: Xác minh in đậm "tend to" trong extra_example
      final richTexts = tester.widgetList<RichText>(find.byType(RichText));
      bool foundBoldCanonical = false;
      for (final rt in richTexts) {
        if (rt.text.toPlainText().contains('Children tend to sleep more')) {
          void checkBold(InlineSpan span) {
            if (span is TextSpan) {
              if (span.text == 'tend to' &&
                  span.style?.fontWeight == FontWeight.bold) {
                foundBoldCanonical = true;
              }
              span.children?.forEach(checkBold);
            }
          }

          checkBold(rt.text);
        }
      }
      expect(foundBoldCanonical, isTrue,
          reason: 'canonicalForm "tend to" must be bold in extra_example');
    });

    testWidgets(
        'AC-1 & AC-2 (FE-04d): 1 nút loa + chip chế độ 1x/0.75x; chạm chip = đổi + phát ngay',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tapWordToken(tester, 'tend');

      // Trong EntryDetailBlock chỉ có duy nhất 1 icon volume_up_outlined
      final detailBlock = find.byType(EntryDetailBlock);
      expect(detailBlock, findsOneWidget);
      final speakersInBlock = find.descendant(
        of: detailBlock,
        matching: find.byIcon(Icons.volume_up_outlined),
      );
      expect(speakersInBlock, findsOneWidget);

      // Chip chế độ ban đầu hiện 1x
      final speedChip = find.byTooltip('Đổi tốc độ');
      expect(speedChip, findsOneWidget);
      expect(
        find.descendant(of: speedChip, matching: find.text('1x')),
        findsOneWidget,
      );

      // Bấm nút loa phát âm với speed 1.0
      final speakerButton = find.byTooltip('Phát âm');
      expect(speakerButton, findsOneWidget);
      await tester.tap(speakerButton);
      await tester.pump();
      expect(testAudioService.lastSpeed, equals(1.0));
      expect(testAudioService.lastSpokenText, equals('tend to'));

      // Chạm chip chế độ 1x: đổi sang 0.75x và PHÁT NGAY ở tốc độ 0.75
      await tester.tap(speedChip);
      await tester.pump();
      expect(testAudioService.lastSpeed, equals(0.75));
      expect(
        find.descendant(of: speedChip, matching: find.text('0.75x')),
        findsOneWidget,
      );

      // Bấm nút loa lúc này phát với speed 0.75
      await tester.tap(speakerButton);
      await tester.pump();
      expect(testAudioService.lastSpeed, equals(0.75));

      // Chạm chip lần nữa: đổi về 1x và PHÁT NGAY ở tốc độ 1.0
      await tester.tap(speedChip);
      await tester.pump();
      expect(testAudioService.lastSpeed, equals(1.0));
      expect(
        find.descendant(of: speedChip, matching: find.text('1x')),
        findsOneWidget,
      );
    });

    testWidgets(
        'AC-3 (FE-04d): Chế độ tốc độ áp dụng cho mọi khối cụm, dòng từ đơn, và tooltip',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // 1. Mở sheet "tend" và chuyển chế độ sang 0.75x
      await tapWordToken(tester, 'tend');
      final speedChip = find.byTooltip('Đổi tốc độ');
      await tester.tap(speedChip);
      await tester.pump();
      expect(testAudioService.lastSpeed, equals(0.75));

      // Đóng sheet
      await tester.tapAt(const Offset(20, 20));
      await tester.pumpAndSettle();

      // 2. Chạm "role" mở sheet cụm: cả 2 khối cụm đều hiển thị 0.75x
      await tapWordToken(tester, 'role');
      expect(find.byType(PhraseBottomSheet), findsOneWidget);
      expect(find.byType(EntryDetailBlock), findsNWidgets(2));
      expect(find.text('0.75x'), findsNWidgets(2));

      // Bấm loa dòng từ đơn: phát với speed 0.75
      final phraseIcons = find.descendant(
        of: find.byType(PhraseBottomSheet),
        matching: find.byIcon(Icons.volume_up_outlined),
      );
      final wordRowSpeaker = find.ancestor(
        of: phraseIcons.last,
        matching: find.byType(InkWell),
      );
      await tester.ensureVisible(wordRowSpeaker);
      await tester.pumpAndSettle();
      await tester.tap(wordRowSpeaker);
      await tester.pump();
      expect(testAudioService.lastSpeed, equals(0.75));
      expect(testAudioService.lastSpokenText, equals('role'));

      // Đóng sheet
      await tester.tapAt(const Offset(20, 20));
      await tester.pumpAndSettle();

      // 3. Chạm "health" mở tooltip: loa tooltip phát với speed 0.75
      await tapWordToken(tester, 'health');
      expect(find.byType(WordTooltip), findsOneWidget);
      final tooltipSpeaker = find.byKey(const Key('tooltip_speaker_button'));
      await tester.tap(tooltipSpeaker);
      await tester.pump();
      expect(testAudioService.lastSpeed, equals(0.75));
      expect(testAudioService.lastSpokenText, equals('health'));
    });

    testWidgets(
        'AC-4 (FE-04d): Vùng chạm của loa 1x, chip chế độ, loa tooltip, loa dòng từ đơn đều ≥ 44x44 dp',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // 1. Chạm "tend" kiểm tra loa và chip chế độ trong sheet
      await tapWordToken(tester, 'tend');
      expect(find.byType(PhraseBottomSheet), findsOneWidget);

      final normalSpeaker = find.byTooltip('Phát âm');
      expect(normalSpeaker, findsOneWidget);
      final normalSpeakerSize = tester.getSize(normalSpeaker);
      expect(normalSpeakerSize.width, greaterThanOrEqualTo(44.0));
      expect(normalSpeakerSize.height, greaterThanOrEqualTo(44.0));

      final speedChip = find.byTooltip('Đổi tốc độ');
      expect(speedChip, findsOneWidget);
      final chipSize = tester.getSize(speedChip);
      expect(chipSize.width, greaterThanOrEqualTo(44.0));
      expect(chipSize.height, greaterThanOrEqualTo(44.0));

      // Đóng sheet
      await tester.tapAt(const Offset(20, 20));
      await tester.pumpAndSettle();
      expect(find.byType(PhraseBottomSheet), findsNothing);

      // 2. Chạm "health" kiểm tra loa tooltip
      await tapWordToken(tester, 'health');
      expect(find.byType(WordTooltip), findsOneWidget);

      final tooltipSpeaker = find.byKey(const Key('tooltip_speaker_button'));
      expect(tooltipSpeaker, findsOneWidget);
      final tooltipSpeakerSize = tester.getSize(tooltipSpeaker);
      expect(tooltipSpeakerSize.width, greaterThanOrEqualTo(44.0));
      expect(tooltipSpeakerSize.height, greaterThanOrEqualTo(44.0));

      // Đóng tooltip
      await tester.tapAt(const Offset(20, 20));
      await tester.pumpAndSettle();
      expect(find.byType(WordTooltip), findsNothing);

      // 3. Chạm "role" kiểm tra loa dòng từ đơn trong PhraseBottomSheet
      await tapWordToken(tester, 'role');
      expect(find.byType(PhraseBottomSheet), findsOneWidget);

      final phraseIcons = find.descendant(
        of: find.byType(PhraseBottomSheet),
        matching: find.byIcon(Icons.volume_up_outlined),
      );
      final wordRowSpeakerIcon = phraseIcons.last;
      final wordRowSpeaker = find.ancestor(
        of: wordRowSpeakerIcon,
        matching: find.byType(InkWell),
      );
      final wordRowSpeakerSize = tester.getSize(wordRowSpeaker);
      expect(wordRowSpeakerSize.width, greaterThanOrEqualTo(44.0));
      expect(wordRowSpeakerSize.height, greaterThanOrEqualTo(44.0));
    });

    testWidgets(
        'AC-3: Chạm "role" -> cụm "play a vital role in" đầy đủ, cụm "vital role" gọn, dòng từ đơn có /roʊl/',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tapWordToken(tester, 'role');

      expect(find.byType(PhraseBottomSheet), findsOneWidget);

      // Cụm 1 (đầy đủ): có định nghĩa tiếng Anh
      expect(find.text('play a vital role in'), findsOneWidget);
      expect(
        find.text(
          'to be very important in making something happen',
        ),
        findsOneWidget,
      );

      // Cụm 2 (gọn): có tiêu đề, badge, IPA, loa, nghĩa, nhưng không có định nghĩa riêng
      expect(find.text('vital role'), findsOneWidget);
      expect(find.text('vai trò thiết yếu'), findsOneWidget);

      // Cả 2 cụm đều có chip chế độ (mặc định hiện 1x)
      expect(find.text('1x'), findsNWidgets(2));

      // Dòng từ đơn: có IPA /roʊl/
      expect(find.text('role'), findsOneWidget);
      expect(find.text('(n.)'), findsOneWidget);
      expect(find.text('/roʊl/'), findsOneWidget);
      expect(find.text('vai trò'), findsOneWidget);
    });

    testWidgets(
        'AC-4: Chạm "folate" (sec 2) mở tooltip không có dòng IPA, không có chữ "null"',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Sang section 2
      await tester.fling(find.byType(PageView), const Offset(-400, 0), 1000);
      await tester.pumpAndSettle();
      expect(find.text('2 / 2'), findsOneWidget);

      await tapWordToken(tester, 'folate');

      expect(find.byType(WordTooltip), findsOneWidget);
      expect(find.text('folate'), findsOneWidget);
      expect(find.text('folate (một loại vitamin B)'), findsOneWidget);

      // Không hiển thị "null" hay khoảng trống IPA bên trong tooltip
      expect(
        find.descendant(
          of: find.byType(WordTooltip),
          matching: find.text('null'),
        ),
        findsNothing,
      );
      expect(
        find.descendant(
          of: find.byType(WordTooltip),
          matching: find.textContaining('/'),
        ),
        findsNothing,
      );
    });

    testWidgets(
        'AC-5: Chuyển từ không bị nuốt tap nhờ TapRegion (health -> disease)',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Mở tooltip "health"
      await tapWordToken(tester, 'health');
      expect(find.byType(WordTooltip), findsOneWidget);
      expect(find.text('sức khỏe'), findsOneWidget);

      // Ngay lập tức chạm "disease" (từ kế bên)
      await tapWordToken(tester, 'disease');

      // Tooltip chuyển ngay sang "disease" chỉ trong 1 lần chạm
      expect(find.byType(WordTooltip), findsOneWidget);
      expect(find.text('bệnh tật'), findsOneWidget);
      expect(find.text('sức khỏe'), findsNothing);
    });

    testWidgets(
        'Chạm "carotenoids" ở section 2 mở ItemBottomSheet theo 6 khối và không có "Xem thêm"',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Vuốt sang section 2
      await tester.fling(find.byType(PageView), const Offset(-400, 0), 1000);
      await tester.pumpAndSettle();

      await tapWordToken(tester, 'carotenoids');

      expect(find.byType(ItemBottomSheet), findsOneWidget);
      expect(find.text('carotenoid'), findsOneWidget);
      expect(find.text('Word'), findsOneWidget);
      expect(find.text('/kəˈrɑtənɔɪd/'), findsOneWidget);
      expect(
        find.text('carotenoid (hợp chất tạo màu vàng/cam trong rau quả)'),
        findsOneWidget,
      );

      // Định nghĩa hiện mặc định
      expect(
        find.textContaining('a natural substance that gives yellow'),
        findsOneWidget,
      );

      // Bỏ "Xem thêm"
      expect(find.text('Xem thêm'), findsNothing);
    });

    testWidgets(
        '[R-FE-04b] (a): EntryDetailBlock bolds inflected forms in extra_example ("plays a vital role in")',
        (tester) async {
      const occurrence = Occurrence(
        id: 'occ-1',
        lexiconEntryId: 'lex-play-role',
        sectionId: 'sec-1',
        tokenStart: 0,
        tokenEnd: 5,
        vi: 'đóng vai trò quan trọng trong',
        exampleSentence: 'Eating well plays a vital role in health.',
        cloze: Cloze(
          textBefore: 'Eating well ',
          answer: 'plays a vital role in',
          textAfter: ' health.',
        ),
      );

      const entry = LexiconEntry(
        id: 'lex-play-role',
        canonicalForm: 'play a vital role in',
        lemmaKey: 'play_a_vital_role_in',
        type: 'collocation',
        pos: 'verb',
        cefrLevel: 'B1',
        extraExample: 'Sleep plays a vital role in memory consolidation.',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: Scaffold(
            body: SingleChildScrollView(
              child: EntryDetailBlock(
                occurrence: occurrence,
                entry: entry,
                onPlayAudio: (_) {},
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Tìm RichText hiển thị ví dụ extra
      final richTexts = tester.widgetList<RichText>(find.byType(RichText));
      bool foundBoldInflected = false;
      for (final rt in richTexts) {
        if (rt.text is TextSpan) {
          final rootSpan = rt.text as TextSpan;
          rootSpan.visitChildren((child) {
            if (child is TextSpan &&
                child.text == 'plays a vital role in' &&
                child.style?.fontWeight == FontWeight.bold) {
              foundBoldInflected = true;
              return false;
            }
            return true;
          });
        }
      }
      expect(foundBoldInflected, isTrue);
    });

    testWidgets(
        '[R-FE-04b] (b) & (d): Compact block has no English definition and disabled Save button when onSave is null',
        (tester) async {
      const occurrence = Occurrence(
        id: 'occ-compact',
        lexiconEntryId: 'lex-compact',
        sectionId: 'sec-1',
        tokenStart: 0,
        tokenEnd: 2,
        vi: 'vai trò thiết yếu',
        exampleSentence: 'A vital role in life.',
        cloze: Cloze(textBefore: 'A ', answer: 'vital role', textAfter: ' in life.'),
      );

      const entry = LexiconEntry(
        id: 'lex-compact',
        canonicalForm: 'vital role',
        lemmaKey: 'vital_role',
        type: 'collocation',
        pos: 'noun',
        cefrLevel: 'B2',
        definitionEn: 'extremely important role',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const Scaffold(
            body: EntryDetailBlock(
              occurrence: occurrence,
              entry: entry,
              isCompact: true,
              onPlayAudio: _dummyPlayAudio,
              onSave: null, // onSave null -> nút Lưu bị disable
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // [R-FE-04b] (b): Không hiển thị definitionEn trong khối compact
      expect(find.text('extremely important role'), findsNothing);

      // [R-FE-04b] (d): Nút Lưu bị disabled
      final saveBtn = tester.widget<OutlinedButton>(find.byType(OutlinedButton));
      expect(saveBtn.enabled, isFalse);
    });

    testWidgets(
        '[R-FE-04d] (a): Toggling speed chip on compact block (phrase 2) updates speedMode and full block',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Chạm "role" để mở sheet cụm có 2 khối cụm
      await tapWordToken(tester, 'role');
      expect(find.byType(PhraseBottomSheet), findsOneWidget);
      expect(find.byType(EntryDetailBlock), findsNWidgets(2));

      // Cả 2 khối cụm ban đầu đều có chip '1x'
      expect(find.text('1x'), findsNWidgets(2));

      // Bấm chip đổi tốc độ ở khối thứ 2 (compact block)
      final speedChips = find.byTooltip('Đổi tốc độ');
      expect(speedChips, findsNWidgets(2));
      await tester.tap(speedChips.at(1));
      await tester.pumpAndSettle();

      // Cả 2 khối cụm đồng bộ chuyển sang '0.75x'
      expect(find.text('0.75x'), findsNWidgets(2));
    });

    testWidgets(
        'FE-08 (AC-1): Word row at the bottom of PhraseBottomSheet does NOT have Save button',
        (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      // Chạm "role" mở PhraseBottomSheet
      await tapWordToken(tester, 'role');
      expect(find.byType(PhraseBottomSheet), findsOneWidget);

      // Có 2 nút Lưu/Đã lưu ứng với 2 khối cụm trong EntryDetailBlock
      final entryDetailBlocks = find.byType(EntryDetailBlock);
      expect(entryDetailBlocks, findsNWidgets(2));

      // Tổng số nút Lưu (OutlinedButton) trong sheet đúng bằng 2 (không có nút Lưu ở word row)
      final saveButtonsInSheet = find.descendant(
        of: find.byType(PhraseBottomSheet),
        matching: find.byType(OutlinedButton),
      );
      expect(saveButtonsInSheet, findsNWidgets(2));

      // Dòng từ đơn có từ "role", POS "(n.)", IPA "/roʊl/", nghĩa "vai trò", nút loa
      expect(find.text('role'), findsOneWidget);
      expect(find.text('(n.)'), findsOneWidget);
      expect(find.text('/roʊl/'), findsOneWidget);
      expect(find.text('vai trò'), findsOneWidget);
    });
  });
}

void _dummyPlayAudio(double speed) {}
