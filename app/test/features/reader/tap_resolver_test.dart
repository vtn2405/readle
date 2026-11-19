import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:readle/data/models/article_bundle.dart';
import 'package:readle/features/reader/models/tap_result.dart';
import 'package:readle/features/reader/services/tap_resolver.dart';

void main() {
  late ArticleBundle bundle;
  late Section sec1;
  late Section sec2;
  late List<Occurrence> sec1Occurrences;
  late List<Occurrence> sec2Occurrences;
  late Map<String, LexiconEntry> lexiconById;

  setUpAll(() {
    final file = File('../fixtures/article_eating_well.json');
    final jsonStr = file.existsSync()
        ? file.readAsStringSync()
        : File('assets/fixtures/article_eating_well.json').readAsStringSync();
    bundle =
        ArticleBundle.fromJson(jsonDecode(jsonStr) as Map<String, dynamic>);

    sec1 = bundle.sections.firstWhere((s) => s.id == 'sec_ew_1');
    sec2 = bundle.sections.firstWhere((s) => s.id == 'sec_ew_2');
    sec1Occurrences =
        bundle.occurrences.where((o) => o.sectionId == 'sec_ew_1').toList();
    sec2Occurrences =
        bundle.occurrences.where((o) => o.sectionId == 'sec_ew_2').toList();
    lexiconById = {for (final e in bundle.lexicon) e.id: e};
  });

  group('resolveTap - 12 ca kiểm thử chuẩn (references/tap-resolution.md)', () {
    test('Ca 1: sec_ew_1 token 5 "role" -> phrase 2 cụm (dài trước) + dòng từ đơn', () {
      final res = resolveTap(
        tokens: sec1.tokens,
        i: 5,
        sectionOccurrences: sec1Occurrences,
        lexiconById: lexiconById,
      );

      expect(res.kind, equals(TapKind.phrase));
      expect(res.token.text, equals('role'));
      expect(res.phrases.length, equals(2));
      expect(
        lexiconById[res.phrases[0].lexiconEntryId]?.canonicalForm,
        equals('play a vital role in'),
      );
      expect(
        lexiconById[res.phrases[1].lexiconEntryId]?.canonicalForm,
        equals('vital role'),
      );
      expect(res.showWordRow, isTrue);
      expect(res.token.lemma.toLowerCase(), equals('role'));
      expect(res.token.vi, equals('vai trò'));
      expect(res.eventResult, equals('phrase_plus_word'));
    });

    test('Ca 2: sec_ew_1 token 4 "vital" -> phrase 2 cụm + dòng từ đơn', () {
      final res = resolveTap(
        tokens: sec1.tokens,
        i: 4,
        sectionOccurrences: sec1Occurrences,
        lexiconById: lexiconById,
      );

      expect(res.kind, equals(TapKind.phrase));
      expect(res.token.text, equals('vital'));
      expect(res.phrases.length, equals(2));
      expect(res.showWordRow, isTrue);
      expect(res.eventResult, equals('phrase_plus_word'));
    });

    test('Ca 3: sec_ew_1 token 2 "plays" -> phrase 1 cụm + dòng từ đơn', () {
      final res = resolveTap(
        tokens: sec1.tokens,
        i: 2,
        sectionOccurrences: sec1Occurrences,
        lexiconById: lexiconById,
      );

      expect(res.kind, equals(TapKind.phrase));
      expect(res.token.text, equals('plays'));
      expect(res.phrases.length, equals(1));
      expect(
        lexiconById[res.phrases[0].lexiconEntryId]?.canonicalForm,
        equals('play a vital role in'),
      );
      expect(res.showWordRow, isTrue);
      expect(res.token.lemma.toLowerCase(), equals('play'));
      expect(res.eventResult, equals('phrase_plus_word'));
    });

    test('Ca 4: sec_ew_1 token 6 "in" (từ chức năng) -> phrase không có dòng từ đơn', () {
      final res = resolveTap(
        tokens: sec1.tokens,
        i: 6,
        sectionOccurrences: sec1Occurrences,
        lexiconById: lexiconById,
      );

      expect(res.kind, equals(TapKind.phrase));
      expect(res.token.text, equals('in'));
      expect(res.phrases.length, equals(1));
      expect(res.showWordRow, isFalse);
      expect(res.eventResult, equals('phrase_only'));
    });

    test('Ca 5: sec_ew_1 token 54 "to" -> phrase tend to, không có dòng từ đơn', () {
      final res = resolveTap(
        tokens: sec1.tokens,
        i: 54,
        sectionOccurrences: sec1Occurrences,
        lexiconById: lexiconById,
      );

      expect(res.kind, equals(TapKind.phrase));
      expect(res.token.text, equals('to'));
      expect(
        lexiconById[res.phrases[0].lexiconEntryId]?.canonicalForm,
        equals('tend to'),
      );
      expect(res.showWordRow, isFalse);
      expect(res.eventResult, equals('phrase_only'));
    });

    test('Ca 6: sec_ew_1 token 67 "in" -> phrase in moderation, không có dòng từ đơn', () {
      final res = resolveTap(
        tokens: sec1.tokens,
        i: 67,
        sectionOccurrences: sec1Occurrences,
        lexiconById: lexiconById,
      );

      expect(res.kind, equals(TapKind.phrase));
      expect(res.token.text, equals('in'));
      expect(
        lexiconById[res.phrases[0].lexiconEntryId]?.canonicalForm,
        equals('in moderation'),
      );
      expect(res.showWordRow, isFalse);
      expect(res.eventResult, equals('phrase_only'));
    });

    test('Ca 7: sec_ew_1 token 68 "moderation" -> phrase in moderation + dòng từ đơn', () {
      final res = resolveTap(
        tokens: sec1.tokens,
        i: 68,
        sectionOccurrences: sec1Occurrences,
        lexiconById: lexiconById,
      );

      expect(res.kind, equals(TapKind.phrase));
      expect(res.token.text, equals('moderation'));
      expect(
        lexiconById[res.phrases[0].lexiconEntryId]?.canonicalForm,
        equals('in moderation'),
      );
      expect(res.showWordRow, isTrue);
      expect(res.eventResult, equals('phrase_plus_word'));
    });

    test('Ca 8: sec_ew_1 token 8 "health" -> tooltip', () {
      final res = resolveTap(
        tokens: sec1.tokens,
        i: 8,
        sectionOccurrences: sec1Occurrences,
        lexiconById: lexiconById,
      );

      expect(res.kind, equals(TapKind.tooltip));
      expect(res.token.text, equals('health'));
      expect(res.token.vi, equals('sức khỏe'));
      expect(res.eventResult, equals('tooltip'));
    });

    test('Ca 9: sec_ew_1 token 12 "." -> none, eventResult == null', () {
      final res = resolveTap(
        tokens: sec1.tokens,
        i: 12,
        sectionOccurrences: sec1Occurrences,
        lexiconById: lexiconById,
      );

      expect(res.kind, equals(TapKind.none));
      expect(res.token.isWord, isFalse);
      expect(res.eventResult, isNull);
    });

    test('Ca 10: sec_ew_2 token 20 "carotenoids" -> sheet mục từ single_word', () {
      final res = resolveTap(
        tokens: sec2.tokens,
        i: 20,
        sectionOccurrences: sec2Occurrences,
        lexiconById: lexiconById,
      );

      expect(res.kind, equals(TapKind.item));
      expect(res.token.text, equals('carotenoids'));
      expect(res.item, isNotNull);
      expect(
        lexiconById[res.item!.lexiconEntryId]?.canonicalForm,
        equals('carotenoid'),
      );
      expect(
        lexiconById[res.item!.lexiconEntryId]?.type,
        equals('single_word'),
      );
      expect(res.eventResult, equals('item'));
    });

    test('Ca 11: sec_ew_2 token 14 "sources" -> phrase excellent source of + dòng từ đơn', () {
      final res = resolveTap(
        tokens: sec2.tokens,
        i: 14,
        sectionOccurrences: sec2Occurrences,
        lexiconById: lexiconById,
      );

      expect(res.kind, equals(TapKind.phrase));
      expect(res.token.text, equals('sources'));
      expect(
        lexiconById[res.phrases[0].lexiconEntryId]?.canonicalForm,
        equals('excellent source of'),
      );
      expect(res.showWordRow, isTrue);
      expect(res.eventResult, equals('phrase_plus_word'));
    });

    test('Ca 12: sec_ew_1 key_idea token 0 "Healthy" -> tooltip từ đúng danh sách key_idea.tokens', () {
      final res = resolveTap(
        tokens: sec1.keyIdea.tokens,
        i: 0,
        sectionOccurrences: sec1Occurrences,
        lexiconById: lexiconById,
        inKeyIdea: true,
      );

      expect(res.kind, equals(TapKind.tooltip));
      expect(res.token.text, equals('Healthy'));
      expect(res.token.vi, equals('lành mạnh'));
      expect(res.eventResult, equals('tooltip'));
    });

    test('Ca 13 (bổ sung): token thiếu nghĩa vi == null -> missing_meaning', () {
      const missingViToken = Token(
        i: 99,
        text: 'rareword',
        ws: ' ',
        lemma: 'rareword',
        pos: 'NOUN',
        isWord: true,
        isFn: false,
        vi: null,
      );

      final res = resolveTap(
        tokens: [missingViToken],
        i: 0,
        sectionOccurrences: [],
        lexiconById: lexiconById,
      );

      expect(res.kind, equals(TapKind.tooltip));
      expect(res.token.vi, isNull);
      expect(res.eventResult, equals('missing_meaning'));
    });
  });
}

