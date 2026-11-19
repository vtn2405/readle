import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:readle/data/models/article_bundle.dart';
import 'package:readle/data/repositories/fixture_article_repository.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('ArticleBundle JSON Model parsing', () {
    late String jsonString;
    late Map<String, dynamic> jsonMap;

    setUpAll(() {
      final file = File('assets/fixtures/article_eating_well.json');
      jsonString = file.readAsStringSync();
      jsonMap = jsonDecode(jsonString) as Map<String, dynamic>;
    });

    test('Parse eating well fixture meets acceptance criteria', () {
      final bundle = ArticleBundle.fromJson(jsonMap);

      // Contract version & Article Meta
      expect(bundle.contractVersion, '1.4');
      expect(bundle.article.id, 'art_eating_well');
      expect(bundle.article.title, 'Eating Well');
      expect(bundle.article.category, 'Health & Nutrition');
      expect(bundle.article.cefrLevel, 'A2');

      // Acceptance criterion 1: 2 sections
      expect(bundle.sections.length, 2);
      expect(bundle.sections[0].id, 'sec_ew_1');
      expect(bundle.sections[1].id, 'sec_ew_2');

      // Acceptance criterion 2: 6 occurrences
      expect(bundle.occurrences.length, 6);

      // Acceptance criterion 3: token sec_ew_1#5 = "role"
      final sec1 = bundle.sections.firstWhere((s) => s.id == 'sec_ew_1');
      final token5 = sec1.tokens.firstWhere((t) => t.i == 5);
      expect(token5.text, 'role');
      expect(token5.lemma, 'role');
      expect(token5.pos, 'NOUN');
      expect(token5.isWord, isTrue);
      expect(token5.ipa, '/roʊl/');

      // Verify token with null ipa (folate in sec_ew_2)
      final sec2 = bundle.sections.firstWhere((s) => s.id == 'sec_ew_2');
      final folateToken = sec2.tokens.firstWhere((t) => t.text == 'folate');
      expect(folateToken.ipa, isNull);

      // Verify overlapping occurrences (play a vital role in & vital role)
      final occ1 = bundle.occurrences.firstWhere((o) => o.id == 'occ_ew_1');
      final occ2 = bundle.occurrences.firstWhere((o) => o.id == 'occ_ew_2');
      expect(occ1.tokenStart, 2);
      expect(occ1.tokenEnd, 6); // inclusive
      expect(occ2.tokenStart, 4);
      expect(occ2.tokenEnd, 5); // inclusive

      // Verify lexicon entries
      expect(bundle.lexicon.length, 6);
      final playRole =
          bundle.lexicon.firstWhere((l) => l.id == 'lex_play_vital_role_in');
      expect(playRole.type, 'collocation');
      expect(playRole.canonicalForm, 'play a vital role in');
      expect(playRole.lemmaKey, 'play a vital role in');

      // Verify quiz items
      expect(bundle.quiz.length, 3);
    });

    test('Token parsing is backward compatible with contract 1.0 (missing ipa key)', () {
      final tokenJson = {
        'i': 0,
        'text': 'Eat',
        'ws': ' ',
        'lemma': 'eat',
        'pos': 'VERB',
        'is_word': true,
        'is_fn': false,
        'vi': 'ăn',
      };
      final token = Token.fromJson(tokenJson);
      expect(token.ipa, isNull);
      expect(token.text, 'Eat');
    });

    test('Throws FormatException on missing required fields', () {
      expect(
        () => Token.fromJson({'i': 0, 'text': 'test'}),
        throwsFormatException,
      );
      expect(
        () => ArticleBundle.fromJson({'contract_version': '1.0'}),
        throwsFormatException,
      );
      expect(
        () => Section.fromJson({'id': 's1'}),
        throwsFormatException,
      );
    });
  });

  group('FixtureArticleRepository', () {
    test('list() and get() through FixtureArticleRepository', () async {
      final repo = FixtureArticleRepository();

      // get() loads asset fixture
      final bundle = await repo.get('art_eating_well');
      expect(bundle.article.id, 'art_eating_well');
      expect(bundle.sections.length, 2);
      expect(bundle.occurrences.length, 6);

      // list() returns article cards
      final cards = await repo.list();
      expect(cards.length, 1);
      final card = cards.first;
      expect(card.id, 'art_eating_well');
      expect(card.title, 'Eating Well');
      expect(card.category, 'Health & Nutrition');
      expect(card.cefrLevel, 'A2');
      expect(card.sourceName, 'World of Wonder');
      expect(card.sectionCount, 2);
    });
  });
}

