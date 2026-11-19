import 'dart:convert';
import 'dart:io';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:readle/core/theme/app_colors.dart';
import 'package:readle/core/theme/app_theme.dart';
import 'package:readle/data/models/article_bundle.dart';
import 'package:readle/data/models/article_card.dart';
import 'package:readle/data/providers/repository_providers.dart';
import 'package:readle/data/repositories/article_repository.dart';
import 'package:readle/features/reader/screens/reader_screen.dart';
import 'package:readle/features/reader/widgets/phrase_bottom_sheet.dart';
import 'package:readle/features/reader/widgets/section_card.dart';
import 'package:readle/features/reader/widgets/token_text_view.dart';
import 'package:readle/features/reader/widgets/word_tooltip.dart';

class MockArticleRepository implements ArticleRepository {
  final ArticleBundle bundle;

  MockArticleRepository(this.bundle);

  @override
  Future<ArticleBundle> get(String id) async => bundle;

  @override
  Future<List<ArticleCard>> list() async => [];
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

  Widget createReaderWidget({
    ThemeData? theme,
    ArticleBundle? bundle,
  }) {
    final activeBundle = bundle ?? eatingWellBundle;
    return ProviderScope(
      overrides: [
        articleRepositoryProvider.overrideWithValue(
          MockArticleRepository(activeBundle),
        ),
      ],
      child: MaterialApp(
        theme: theme ?? AppTheme.lightTheme,
        home: const ReaderScreen(articleId: 'art_eating_well'),
      ),
    );
  }

  List<TextSpan> extractLeafSpans(InlineSpan root) {
    final List<TextSpan> leaves = [];
    void visit(InlineSpan span) {
      if (span is TextSpan) {
        if (span.text != null && span.text!.isNotEmpty) {
          leaves.add(span);
        }
        span.children?.forEach(visit);
      }
    }
    visit(root);
    return leaves;
  }

  group('ReaderScreen Widget Tests', () {
    testWidgets(
        'renders PageView, Section title, Key idea, and body tokens correctly',
        (tester) async {
      await tester.pumpWidget(createReaderWidget());
      await tester.pumpAndSettle();

      // AppBar title & progress indicator
      expect(find.text('Eating Well'), findsOneWidget);
      expect(find.text('1 / 2'), findsOneWidget);

      // Section card header
      expect(find.text('Eating well'), findsOneWidget);
      expect(find.text('Key idea'), findsOneWidget);

      // Key idea text presence
      expect(find.textContaining('Healthy food helps your body'), findsOneWidget);

      // Body text presence
      expect(find.textContaining('Eating well plays a vital role in good health'),
          findsOneWidget);
    });

    testWidgets('preserves exact words and whitespaces as original text',
        (tester) async {
      await tester.pumpWidget(createReaderWidget());
      await tester.pumpAndSettle();

      final tokenTextViews = tester.widgetList<TokenTextView>(find.byType(TokenTextView));
      // First is Key idea, second is body
      expect(tokenTextViews.length, greaterThanOrEqualTo(2));
      final bodyView = tokenTextViews.firstWhere((w) => w.tokens.length > 50);

      // Reconstructed text from token.text + token.ws
      final reconstructed = bodyView.tokens.map((t) => '${t.text}${t.ws}').join();
      expect(reconstructed.startsWith('Eating well plays a vital role in good health'), isTrue);
      expect(reconstructed.contains('and not overly processed is best practice.'), isTrue);
    });

    testWidgets('punctuation tokens and whitespace do NOT have tap recognizer',
        (tester) async {
      await tester.pumpWidget(createReaderWidget());
      await tester.pumpAndSettle();

      final richTextFinders = find.descendant(
        of: find.byType(SectionCard),
        matching: find.byType(RichText),
      );

      bool foundWordWithRecognizer = false;
      bool foundPunctuationWithoutRecognizer = false;
      bool allWhitespaceLackRecognizer = true;

      for (final candidate in tester.widgetList<RichText>(richTextFinders)) {
        final leaves = extractLeafSpans(candidate.text);
        for (final child in leaves) {
          final text = child.text ?? '';
          if (text == 'plays') {
            foundWordWithRecognizer = child.recognizer is TapGestureRecognizer;
          } else if (text == '.') {
            foundPunctuationWithoutRecognizer = child.recognizer == null;
          } else if (text.trim().isEmpty) {
            if (child.recognizer != null) {
              allWhitespaceLackRecognizer = false;
            }
          }
        }
      }

      expect(foundWordWithRecognizer, isTrue,
          reason: 'Word token "plays" should have a TapGestureRecognizer');
      expect(foundPunctuationWithoutRecognizer, isTrue,
          reason: 'Punctuation "." must NOT have any recognizer');
      expect(allWhitespaceLackRecognizer, isTrue,
          reason: 'Whitespace spans must NEVER have a recognizer');
    });

    testWidgets('swiping page updates in-memory progress and completes article',
        (tester) async {
      await tester.pumpWidget(createReaderWidget());
      await tester.pumpAndSettle();

      expect(find.text('1 / 2'), findsOneWidget);

      // Swipe to next card
      await tester.fling(find.byType(PageView), const Offset(-400, 0), 1000);
      await tester.pumpAndSettle();

      // Now on page 2 / 2
      expect(find.text('2 / 2'), findsOneWidget);
      expect(find.text('Dark green veggies'), findsOneWidget);
      expect(
          find.textContaining('Dark green vegetables give your body many good things'),
          findsOneWidget);
    });

    testWidgets('collocation whitespace is highlighted continuously between words',
        (tester) async {
      await tester.pumpWidget(createReaderWidget());
      await tester.pumpAndSettle();

      final richTextFinders = find.descendant(
        of: find.byType(SectionCard),
        matching: find.byType(RichText),
      );

      bool foundCollocSpace = false;
      bool foundTrailingSpaceClean = false;

      for (final candidate in tester.widgetList<RichText>(richTextFinders)) {
        final leaves = extractLeafSpans(candidate.text);
        for (int i = 0; i < leaves.length - 1; i++) {
          final current = leaves[i];
          final next = leaves[i + 1];

          // Khoảng trắng giữa 'plays' và 'a' trong cụm collocation
          if (current.text == 'plays' && next.text == ' ') {
            if (next.style?.backgroundColor ==
                HighlightColors.light.collocationBg) {
              foundCollocSpace = true;
            }
          }

          // Khoảng trắng sau 'in' (từ cuối của cụm collocation 'play a vital role in')
          if (current.text == 'in' && next.text == ' ') {
            if (next.style?.backgroundColor == null ||
                next.style?.backgroundColor !=
                    HighlightColors.light.collocationBg) {
              foundTrailingSpaceClean = true;
            }
          }
        }
      }

      expect(foundCollocSpace, isTrue,
          reason:
              'Khoảng trắng giữa các từ của cụm collocation phải có nền màu để dải highlight liền mạch');
      expect(foundTrailingSpaceClean, isTrue,
          reason:
              'Khoảng trắng sau từ cuối cùng của cụm collocation không được tô màu');
    });

    testWidgets('Key idea sets inKeyIdea = true and body sets inKeyIdea = false',
        (tester) async {
      await tester.pumpWidget(createReaderWidget());
      await tester.pumpAndSettle();

      final tokenTextViews =
          tester.widgetList<TokenTextView>(find.byType(TokenTextView)).toList();
      expect(tokenTextViews.length, greaterThanOrEqualTo(2));

      final keyIdeaView = tokenTextViews.firstWhere((w) => w.inKeyIdea);
      final bodyView = tokenTextViews.firstWhere((w) => !w.inKeyIdea);

      expect(keyIdeaView.inKeyIdea, isTrue);
      expect(bodyView.inKeyIdea, isFalse);
    });

    testWidgets('renders cleanly in dark mode without error and with correct highlights',
        (tester) async {
      await tester.pumpWidget(createReaderWidget(theme: AppTheme.darkTheme));
      await tester.pumpAndSettle();

      expect(find.text('Eating Well'), findsOneWidget);
      expect(find.text('1 / 2'), findsOneWidget);
      expect(find.text('Eating well'), findsOneWidget);

      // Verify HighlightColors.dark is applied to collocation tokens
      final richTextFinders = find.descendant(
        of: find.byType(SectionCard),
        matching: find.byType(RichText),
      );

      bool verifiedDarkCollocation = false;
      for (final candidate in tester.widgetList<RichText>(richTextFinders)) {
        final leaves = extractLeafSpans(candidate.text);
        for (final child in leaves) {
          if (child.text == 'plays') {
            if (child.style?.backgroundColor == HighlightColors.dark.collocationBg) {
              verifiedDarkCollocation = true;
            }
          }
        }
      }

      expect(verifiedDarkCollocation, isTrue,
          reason: 'Collocation token in dark mode should use dark collocation background');
    });

    testWidgets(
        'AC-5: repeating occurrence in same card is not highlighted (token and whitespace clean), but tapping it opens bottom sheet',
        (tester) async {
      final repeatBundle = ArticleBundle(
        contractVersion: '1.4',
        article: const ArticleMeta(
          id: 'art_repeat_test',
          title: 'Repeat Test',
          category: 'Health',
          cefrLevel: 'A2',
          source: ArticleSource(name: 'Test Source', isGraded: false),
          wordCount: 11,
          sectionCount: 1,
        ),
        sections: [
          Section(
            id: 'sec_repeat_1',
            orderIndex: 0,
            title: 'Section 1',
            iconHint: 'test_icon',
            tokens: const [
              Token(i: 0, text: 'Eating', ws: ' ', lemma: 'eat', pos: 'VERB', isWord: true, isFn: false),
              Token(i: 1, text: 'well', ws: ' ', lemma: 'well', pos: 'ADV', isWord: true, isFn: false),
              Token(i: 2, text: 'vital', ws: ' ', lemma: 'vital', pos: 'ADJ', isWord: true, isFn: false),
              Token(i: 3, text: 'role', ws: ' ', lemma: 'role', pos: 'NOUN', isWord: true, isFn: false),
              Token(i: 4, text: 'is', ws: ' ', lemma: 'be', pos: 'AUX', isWord: true, isFn: true),
              Token(i: 5, text: 'good', ws: '. ', lemma: 'good', pos: 'ADJ', isWord: true, isFn: false),
              Token(i: 6, text: 'Another', ws: ' ', lemma: 'another', pos: 'DET', isWord: true, isFn: true),
              Token(i: 7, text: 'time', ws: ' ', lemma: 'time', pos: 'NOUN', isWord: true, isFn: false),
              Token(i: 8, text: 'vital', ws: ' ', lemma: 'vital', pos: 'ADJ', isWord: true, isFn: false),
              Token(i: 9, text: 'role', ws: ' ', lemma: 'role', pos: 'NOUN', isWord: true, isFn: false),
              Token(i: 10, text: 'matters', ws: '.', lemma: 'matter', pos: 'VERB', isWord: true, isFn: false),
            ],
            keyIdea: const KeyIdea(
              text: 'Healthy habits matter.',
              tokens: [
                Token(i: 0, text: 'Healthy', ws: ' ', lemma: 'healthy', pos: 'ADJ', isWord: true, isFn: false),
                Token(i: 1, text: 'habits', ws: ' ', lemma: 'habit', pos: 'NOUN', isWord: true, isFn: false),
                Token(i: 2, text: 'matter', ws: '.', lemma: 'matter', pos: 'VERB', isWord: true, isFn: false),
              ],
            ),
          ),
        ],
        lexicon: const [
          LexiconEntry(
            id: 'lex_repeat_colloc',
            canonicalForm: 'vital role',
            lemmaKey: 'vital role',
            type: 'collocation',
            pos: 'Noun phrase',
            cefrLevel: 'B1',
            ipa: '/ˈvaɪtəl roʊl/',
          ),
        ],
        occurrences: const [
          Occurrence(
            id: 'occ_rep_1',
            lexiconEntryId: 'lex_repeat_colloc',
            sectionId: 'sec_repeat_1',
            tokenStart: 2,
            tokenEnd: 3,
            vi: 'vai trò quan trọng (lần 1)',
            exampleSentence: 'Eating well vital role is good.',
            cloze: Cloze(textBefore: 'Eating well ', answer: 'vital role', textAfter: ' is good.'),
          ),
          Occurrence(
            id: 'occ_rep_2',
            lexiconEntryId: 'lex_repeat_colloc',
            sectionId: 'sec_repeat_1',
            tokenStart: 8,
            tokenEnd: 9,
            vi: 'vai trò quan trọng (lần 2)',
            exampleSentence: 'Another time vital role matters.',
            cloze: Cloze(textBefore: 'Another time ', answer: 'vital role', textAfter: ' matters.'),
          ),
        ],
        quiz: const [],
      );

      await tester.pumpWidget(createReaderWidget(bundle: repeatBundle));
      await tester.pumpAndSettle();

      final bodyRichTextFinder = find.descendant(
        of: find.byWidgetPredicate((w) => w is TokenTextView && !w.inKeyIdea),
        matching: find.byType(RichText),
      );
      final bodyRichText = tester.widget<RichText>(bodyRichTextFinder);
      final leaves = extractLeafSpans(bodyRichText.text);

      // 1. Lần 1 (token 2-3): 'vital' và 'role' có màu collocationBg
      final firstVital = leaves.firstWhere((s) => s.text == 'vital');
      expect(firstVital.style?.backgroundColor, equals(HighlightColors.light.collocationBg),
          reason: 'Token "vital" lần 1 phải được tô màu collocation');

      final firstVitalIndex = leaves.indexOf(firstVital);
      final spaceAfterFirstVital = leaves[firstVitalIndex + 1];
      expect(spaceAfterFirstVital.text, equals(' '));
      expect(spaceAfterFirstVital.style?.backgroundColor, equals(HighlightColors.light.collocationBg),
          reason: 'Khoảng trắng giữa cụm lần 1 phải có màu nền collocationBg');

      final firstRole = leaves.firstWhere((s) => s.text == 'role');
      expect(firstRole.style?.backgroundColor, equals(HighlightColors.light.collocationBg),
          reason: 'Token "role" lần 1 phải được tô màu collocation');

      // 2. Lần 2 (token 8-9): KHÔNG tô màu (null hoặc khác collocationBg)
      final vitalSpans = leaves.where((s) => s.text == 'vital').toList();
      expect(vitalSpans.length, equals(2));
      final secondVital = vitalSpans[1];
      expect(secondVital.style?.backgroundColor, isNull,
          reason: 'Token "vital" lần 2 không được tô màu');

      final secondVitalIndex = leaves.lastIndexOf(secondVital);
      final spaceAfterSecondVital = leaves[secondVitalIndex + 1];
      expect(spaceAfterSecondVital.text, equals(' '));
      expect(spaceAfterSecondVital.style?.backgroundColor, isNull,
          reason: 'Khoảng trắng sau token "vital" lần 2 không được tô màu');

      final roleSpans = leaves.where((s) => s.text == 'role').toList();
      expect(roleSpans.length, equals(2));
      final secondRole = roleSpans[1];
      expect(secondRole.style?.backgroundColor, isNull,
          reason: 'Token "role" lần 2 không được tô màu');

      // 3. Chạm vào token 8 ("vital" lần 2) vẫn có TapGestureRecognizer và mở PhraseBottomSheet
      expect(secondVital.recognizer, isA<TapGestureRecognizer>());
      final recognizer = secondVital.recognizer as TapGestureRecognizer;
      recognizer.onTapUp?.call(
        TapUpDetails(
          kind: PointerDeviceKind.touch,
          globalPosition: const Offset(150, 300),
        ),
      );
      await tester.pumpAndSettle();

      // Kiểm tra mở đúng PhraseBottomSheet cho cụm "vital role" (lần 2), không phải WordTooltip
      expect(find.byType(PhraseBottomSheet), findsOneWidget);
      expect(find.text('vital role'), findsWidgets);
      expect(find.text('vai trò quan trọng (lần 2)'), findsOneWidget);
      expect(find.byType(WordTooltip), findsNothing);
    });
  });
}
