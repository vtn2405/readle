import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:readle/data/models/article_bundle.dart';
import 'package:readle/features/reader/models/highlight_kind.dart';

void main() {
  group('computeHighlights', () {
    final lexicon = [
      const LexiconEntry(
        id: 'lex_play_role',
        canonicalForm: 'play a vital role in',
        lemmaKey: 'play a vital role in',
        type: 'collocation',
        pos: 'Verb phrase',
        cefrLevel: 'B1',
      ),
      const LexiconEntry(
        id: 'lex_vital_role',
        canonicalForm: 'vital role',
        lemmaKey: 'vital role',
        type: 'collocation',
        pos: 'Noun phrase',
        cefrLevel: 'B1',
      ),
      const LexiconEntry(
        id: 'lex_carotenoid',
        canonicalForm: 'carotenoid',
        lemmaKey: 'carotenoid',
        type: 'single_word',
        pos: 'Noun',
        cefrLevel: 'B2',
      ),
    ];

    test('highlights single word correctly', () {
      final occurrences = [
        const Occurrence(
          id: 'occ_1',
          lexiconEntryId: 'lex_carotenoid',
          sectionId: 'sec_1',
          tokenStart: 10,
          tokenEnd: 10,
          vi: 'chất carotenoid',
          exampleSentence: 'Eating carotenoids is good.',
          cloze: Cloze(
            textBefore: 'Eating ',
            answer: 'carotenoids',
            textAfter: ' is good.',
          ),
        ),
      ];

      final highlights = computeHighlights(
        sectionId: 'sec_1',
        occurrences: occurrences,
        lexicon: lexicon,
      );

      expect(highlights[10], equals(HighlightKind.singleWord));
      expect(highlights[9], isNull);
      expect(highlights[11], isNull);
    });

    test('highlights collocation across entire span', () {
      final occurrences = [
        const Occurrence(
          id: 'occ_colloc',
          lexiconEntryId: 'lex_play_role',
          sectionId: 'sec_1',
          tokenStart: 2,
          tokenEnd: 6,
          vi: 'đóng vai trò quan trọng trong',
          exampleSentence: 'Eating well plays a vital role in good health.',
          cloze: Cloze(
            textBefore: 'Eating well ',
            answer: 'plays a vital role in',
            textAfter: ' good health.',
          ),
        ),
      ];

      final highlights = computeHighlights(
        sectionId: 'sec_1',
        occurrences: occurrences,
        lexicon: lexicon,
      );

      for (int i = 2; i <= 6; i++) {
        expect(highlights[i], equals(HighlightKind.collocation),
            reason: 'Token $i should be collocation');
      }
      expect(highlights[1], isNull);
      expect(highlights[7], isNull);
    });

    test('overlapping occurrences prioritize collocation over single_word', () {
      final occurrences = [
        const Occurrence(
          id: 'occ_single',
          lexiconEntryId: 'lex_carotenoid',
          sectionId: 'sec_1',
          tokenStart: 4,
          tokenEnd: 5,
          vi: 'vai trò',
          exampleSentence: '...',
          cloze: Cloze(textBefore: '', answer: 'vital role', textAfter: ''),
        ),
        const Occurrence(
          id: 'occ_colloc',
          lexiconEntryId: 'lex_play_role',
          sectionId: 'sec_1',
          tokenStart: 2,
          tokenEnd: 6,
          vi: 'đóng vai trò quan trọng trong',
          exampleSentence: '...',
          cloze: Cloze(
              textBefore: '', answer: 'plays a vital role in', textAfter: ''),
        ),
      ];

      // Regardless of list order, collocation takes precedence
      final highlights1 = computeHighlights(
        sectionId: 'sec_1',
        occurrences: occurrences,
        lexicon: lexicon,
      );

      for (int i = 2; i <= 6; i++) {
        expect(highlights1[i], equals(HighlightKind.collocation),
            reason: 'Token $i should be collocation');
      }

      final highlights2 = computeHighlights(
        sectionId: 'sec_1',
        occurrences: occurrences.reversed.toList(),
        lexicon: lexicon,
      );

      for (int i = 2; i <= 6; i++) {
        expect(highlights2[i], equals(HighlightKind.collocation),
            reason: 'Token $i should be collocation even when reversed');
      }
    });

    test('ignores occurrences belonging to other sections', () {
      final occurrences = [
        const Occurrence(
          id: 'occ_sec2',
          lexiconEntryId: 'lex_carotenoid',
          sectionId: 'sec_2',
          tokenStart: 3,
          tokenEnd: 3,
          vi: 'chất',
          exampleSentence: '...',
          cloze: Cloze(textBefore: '', answer: 'carotenoid', textAfter: ''),
        ),
      ];

      final highlights = computeHighlights(
        sectionId: 'sec_1',
        occurrences: occurrences,
        lexicon: lexicon,
      );

      expect(highlights.isEmpty, isTrue);
    });

    test(
        'AC-1: card-scoped deduplication - only highlights first occurrence per lexicon entry in each section',
        () {
      final occurrences = [
        const Occurrence(
          id: 'occ_a_3',
          lexiconEntryId: 'lex_carotenoid',
          sectionId: 'sec_a',
          tokenStart: 3,
          tokenEnd: 3,
          vi: 'chất carotenoid',
          exampleSentence: '...',
          cloze: Cloze(textBefore: '', answer: 'carotenoids', textAfter: ''),
        ),
        const Occurrence(
          id: 'occ_a_10',
          lexiconEntryId: 'lex_carotenoid',
          sectionId: 'sec_a',
          tokenStart: 10,
          tokenEnd: 10,
          vi: 'chất carotenoid',
          exampleSentence: '...',
          cloze: Cloze(textBefore: '', answer: 'carotenoids', textAfter: ''),
        ),
        const Occurrence(
          id: 'occ_a_20',
          lexiconEntryId: 'lex_carotenoid',
          sectionId: 'sec_a',
          tokenStart: 20,
          tokenEnd: 20,
          vi: 'chất carotenoid',
          exampleSentence: '...',
          cloze: Cloze(textBefore: '', answer: 'carotenoids', textAfter: ''),
        ),
        const Occurrence(
          id: 'occ_b_5',
          lexiconEntryId: 'lex_carotenoid',
          sectionId: 'sec_b',
          tokenStart: 5,
          tokenEnd: 5,
          vi: 'chất carotenoid',
          exampleSentence: '...',
          cloze: Cloze(textBefore: '', answer: 'carotenoids', textAfter: ''),
        ),
      ];

      // Section A: chỉ token 3 có highlight, token 10 và 20 là null
      final highlightsA = computeHighlights(
        sectionId: 'sec_a',
        occurrences: occurrences,
        lexicon: lexicon,
      );
      expect(highlightsA[3], equals(HighlightKind.singleWord));
      expect(highlightsA[10], isNull);
      expect(highlightsA[20], isNull);

      // Section B: token 5 vẫn được tô riêng biệt cho card B
      final highlightsB = computeHighlights(
        sectionId: 'sec_b',
        occurrences: occurrences,
        lexicon: lexicon,
      );
      expect(highlightsB[5], equals(HighlightKind.singleWord));
    });

    test(
        'AC-2: order independence - picks minimum tokenStart even if list is not sorted',
        () {
      final occurrences = [
        const Occurrence(
          id: 'occ_15',
          lexiconEntryId: 'lex_carotenoid',
          sectionId: 'sec_1',
          tokenStart: 15,
          tokenEnd: 15,
          vi: 'chất carotenoid',
          exampleSentence: '...',
          cloze: Cloze(textBefore: '', answer: 'carotenoids', textAfter: ''),
        ),
        const Occurrence(
          id: 'occ_4',
          lexiconEntryId: 'lex_carotenoid',
          sectionId: 'sec_1',
          tokenStart: 4,
          tokenEnd: 4,
          vi: 'chất carotenoid',
          exampleSentence: '...',
          cloze: Cloze(textBefore: '', answer: 'carotenoids', textAfter: ''),
        ),
      ];

      final highlights = computeHighlights(
        sectionId: 'sec_1',
        occurrences: occurrences,
        lexicon: lexicon,
      );

      expect(highlights[4], equals(HighlightKind.singleWord));
      expect(highlights[15], isNull);
    });

    test(
        'AC-3: backward compatibility - fixture sec_ew_1 highlights collocation across tokens 2-6',
        () {
      final fixtureFile = File('../fixtures/article_eating_well.json');
      final jsonStr = fixtureFile.existsSync()
          ? fixtureFile.readAsStringSync()
          : File('assets/fixtures/article_eating_well.json').readAsStringSync();
      final bundle =
          ArticleBundle.fromJson(jsonDecode(jsonStr) as Map<String, dynamic>);

      final highlights = computeHighlights(
        sectionId: 'sec_ew_1',
        occurrences: bundle.occurrences,
        lexicon: bundle.lexicon,
      );

      for (int i = 2; i <= 6; i++) {
        expect(highlights[i], equals(HighlightKind.collocation),
            reason: 'Token $i in sec_ew_1 should be collocation');
      }
    });

    test(
        'AC-4: collocation deduplication - only highlights first occurrence of repeating collocation in same section',
        () {
      final occurrences = [
        const Occurrence(
          id: 'occ_c1',
          lexiconEntryId: 'lex_vital_role',
          sectionId: 'sec_1',
          tokenStart: 2,
          tokenEnd: 3,
          vi: 'vai trò quan trọng',
          exampleSentence: '...',
          cloze: Cloze(textBefore: '', answer: 'vital role', textAfter: ''),
        ),
        const Occurrence(
          id: 'occ_c2',
          lexiconEntryId: 'lex_vital_role',
          sectionId: 'sec_1',
          tokenStart: 10,
          tokenEnd: 11,
          vi: 'vai trò quan trọng',
          exampleSentence: '...',
          cloze: Cloze(textBefore: '', answer: 'vital role', textAfter: ''),
        ),
      ];

      final highlights = computeHighlights(
        sectionId: 'sec_1',
        occurrences: occurrences,
        lexicon: lexicon,
      );

      expect(highlights[2], equals(HighlightKind.collocation));
      expect(highlights[3], equals(HighlightKind.collocation));
      expect(highlights[10], isNull);
      expect(highlights[11], isNull);
    });
  });
}

