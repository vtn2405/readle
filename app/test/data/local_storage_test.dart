import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:readle/data/local/hive_boxes.dart';
import 'package:readle/data/models/local_models.dart';
import 'package:readle/data/repositories/local_storage_repository.dart';

void main() {
  late Directory tempDir;
  late Box<Map> progressBox;
  late Box<Map> wordsBox;
  late Box<Map> queueBox;

  late HiveReadingProgressRepository progressRepo;
  late HiveSavedWordsRepository wordsRepo;
  late HiveEventQueueRepository queueRepo;

  setUp(() async {
    tempDir = Directory.systemTemp.createTempSync('hive_local_storage_test_');
    Hive.init(tempDir.path);

    progressBox = await Hive.openBox<Map>(readingProgressBoxName);
    wordsBox = await Hive.openBox<Map>(savedWordsBoxName);
    queueBox = await Hive.openBox<Map>(eventQueueBoxName);

    progressRepo = HiveReadingProgressRepository(progressBox);
    wordsRepo = HiveSavedWordsRepository(wordsBox);
    queueRepo = HiveEventQueueRepository(queueBox);
  });

  tearDown(() async {
    await Hive.close();
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  group('ReadingProgressRepository (FE-05 / AC-2)', () {
    test('save, get, and maxIndexReached persistence logic', () async {
      final initial = ReadingProgress(
        articleId: 'art_eating_well',
        lastReadSectionId: 'sec_ew_1',
        lastSectionIndex: 0,
        maxIndexReached: 0,
        progressPercent: 50,
        completed: false,
        lastReadAt: DateTime.utc(2026, 11, 13, 8, 0),
        dirty: true,
      );

      await progressRepo.saveProgress(initial);

      // Đồng bộ
      final syncLoaded = progressRepo.getProgressSync('art_eating_well');
      expect(syncLoaded, isNotNull);
      expect(syncLoaded!.articleId, 'art_eating_well');
      expect(syncLoaded.lastReadSectionId, 'sec_ew_1');
      expect(syncLoaded.lastSectionIndex, 0);
      expect(syncLoaded.progressPercent, 50);
      expect(syncLoaded.completed, isFalse);

      // Lướt sang card 2: maxIndexReached = 1, completed = true, progress = 100
      final updated = syncLoaded.copyWith(
        lastReadSectionId: 'sec_ew_2',
        lastSectionIndex: 1,
        maxIndexReached: 1,
        progressPercent: 100,
        completed: true,
        lastReadAt: DateTime.utc(2026, 11, 13, 8, 5),
      );
      await progressRepo.saveProgress(updated);

      // Lùi về card 1: lastSectionIndex = 0, nhưng maxIndexReached = 1, progressPercent = 100, completed = true
      final backed = updated.copyWith(
        lastReadSectionId: 'sec_ew_1',
        lastSectionIndex: 0,
        lastReadAt: DateTime.utc(2026, 11, 13, 8, 6),
      );
      await progressRepo.saveProgress(backed);

      final reloaded = progressRepo.getProgressSync('art_eating_well');
      expect(reloaded!.lastSectionIndex, 0);
      expect(reloaded.maxIndexReached, 1);
      expect(reloaded.progressPercent, 100);
      expect(reloaded.completed, isTrue);
    });
  });

  group('SavedWordsRepository with Soft Delete (FE-05 / AC-3)', () {
    test('saveWord, deleteWord (soft delete/tombstone), and re-saving', () async {
      final word = SavedWord(
        id: 'uuid-1',
        lemmaKey: 'vital_role',
        lexiconEntryId: 'lex_vital_role',
        displayText: 'vital role',
        vi: 'vai trò quan trọng',
        exampleSentence: 'Eating well plays a vital role in good health.',
        cloze: const {
          'text_before': 'Eating well plays a ',
          'answer': 'vital role',
          'text_after': ' in good health.',
        },
        sourceArticleId: 'art_eating_well',
        savedAt: DateTime.utc(2026, 11, 13, 8, 10),
        dueDate: DateTime.utc(2026, 11, 13, 8, 10),
      );

      // 1. Lưu từ
      await wordsRepo.saveWord(word);
      expect(await wordsRepo.isSaved('vital_role'), isTrue);

      final words = await wordsRepo.getAllWords();
      expect(words.length, 1);
      expect(words.first.lemmaKey, 'vital_role');
      expect(words.first.deleted, isFalse);

      // 2. Xóa từ -> Soft delete (tombstone)
      await wordsRepo.deleteWord('vital_role');

      // isSaved phải false và getAllWords() bỏ qua
      expect(await wordsRepo.isSaved('vital_role'), isFalse);
      expect(await wordsRepo.getAllWords(), isEmpty);

      // Nhưng bản ghi vẫn còn trong box để SyncService biết xóa trên Supabase
      final raw = wordsBox.get('vital_role');
      expect(raw, isNotNull);
      final rawModel = SavedWord.fromMap(raw!);
      expect(rawModel.deleted, isTrue);
      expect(rawModel.dirty, isTrue);

      final allWithDeleted = await wordsRepo.getAllWords(includeDeleted: true);
      expect(allWithDeleted.length, 1);
      expect(allWithDeleted.first.deleted, isTrue);

      // 3. Lưu lại từ đó -> deleted = false, dirty = true
      await wordsRepo.saveWord(word);
      expect(await wordsRepo.isSaved('vital_role'), isTrue);

      final reSaved = await wordsRepo.getWord('vital_role');
      expect(reSaved!.deleted, isFalse);
      expect(reSaved.dirty, isTrue);
    });

    test('due_date format is yyyy-MM-dd and supports legacy ISO UTC migration', () async {
      final localDate = DateTime(2026, 11, 13);
      final word = SavedWord(
        id: 'uuid-date-test',
        lemmaKey: 'test_date',
        displayText: 'test date',
        vi: 'thử ngày',
        exampleSentence: 'Example sentence.',
        cloze: const {},
        sourceArticleId: 'art_1',
        savedAt: DateTime.utc(2026, 11, 13, 8, 0),
        dueDate: localDate,
      );

      final map = word.toMap();
      expect(map['due_date'], matches(r'^\d{4}-\d{2}-\d{2}$'));
      expect(map['due_date'], '2026-11-13');

      // Đọc lại từ map mới
      final parsed = SavedWord.fromMap(map);
      expect(parsed.dueDate.year, 2026);
      expect(parsed.dueDate.month, 11);
      expect(parsed.dueDate.day, 13);

      // Đọc từ map dạng ISO UTC cũ (ví dụ: 2026-11-12T17:00:00.000Z)
      final legacyMap = Map<String, dynamic>.from(map);
      final utcString = DateTime(2026, 11, 13).toUtc().toIso8601String();
      legacyMap['due_date'] = utcString;

      final parsedLegacy = SavedWord.fromMap(legacyMap);
      final expectedLocal = DateTime.parse(utcString).toLocal();
      expect(parsedLegacy.dueDate.year, expectedLocal.year);
      expect(parsedLegacy.dueDate.month, expectedLocal.month);
      expect(parsedLegacy.dueDate.day, expectedLocal.day);
    });

    test('entryType mapping and serialization (Contract 1.4 / ADR-019)', () {
      final collocation = SavedWord(
        id: 'uuid-colloc',
        lemmaKey: 'tend_to',
        entryType: 'collocation',
        displayText: 'tend to',
        vi: 'có xu hướng',
        exampleSentence: 'People tend to eat more vegetables.',
        cloze: const {},
        sourceArticleId: '22222222-2222-2222-2222-222222222222',
        savedAt: DateTime.utc(2026, 11, 16),
        dueDate: DateTime(2026, 11, 16),
      );

      final map = collocation.toMap();
      expect(map['entry_type'], 'collocation');

      final fromMapWord = SavedWord.fromMap(map);
      expect(fromMapWord.entryType, 'collocation');

      final remoteRow = collocation.toRemoteRow(userId: '11111111-1111-1111-1111-111111111111');
      expect(remoteRow['entry_type'], 'collocation');
      expect(remoteRow['source_article_id'], '22222222-2222-2222-2222-222222222222');

      // Test toRemoteRow với source_article_id là fixture ID -> trả map có source_article_id: null ([R-FE-09-pre])
      final fixtureWord = collocation.copyWith(sourceArticleId: 'art_eating_well');
      final fixtureRemoteRow = fixtureWord.toRemoteRow(userId: '11111111-1111-1111-1111-111111111111');
      expect(fixtureRemoteRow, isNotNull);
      expect(fixtureRemoteRow['source_article_id'], isNull);
      expect(fixtureRemoteRow['lemma_key'], 'tend_to');

      // Test fallback sang 'single_word' khi raw map thiếu entry_type và không có lexicon_entry_id
      final legacySingleMap = Map<String, dynamic>.from(map)
        ..remove('entry_type')
        ..remove('lexicon_entry_id');
      final fallbackSingle = SavedWord.fromMap(legacySingleMap);
      expect(fallbackSingle.entryType, 'single_word');

      // Test fallback sang 'single_word' khi raw map thiếu entry_type dù có lexicon_entry_id ([R-FE-08] (a))
      final legacyWithLexMap = Map<String, dynamic>.from(map)
        ..remove('entry_type')
        ..['lexicon_entry_id'] = 'lex-1';
      final fallbackWithLex = SavedWord.fromMap(legacyWithLexMap);
      expect(fallbackWithLex.entryType, 'single_word');
    });

    test('markClean compares content to avoid clearing dirty on snapshot change ([R-FE-06] (b), [R-FE-08] (b))', () async {
      final initial = SavedWord(
        id: 'uuid-mc',
        lemmaKey: 'vital_role',
        displayText: 'vital role',
        vi: 'vai trò thiết yếu',
        exampleSentence: 'Initial sentence.',
        cloze: const {'answer': 'vital role'},
        sourceArticleId: '22222222-2222-2222-2222-222222222222',
        savedAt: DateTime.utc(2026, 11, 16),
        dueDate: DateTime(2026, 11, 16),
        dirty: true,
      );

      await wordsRepo.saveWord(initial);

      // Snapshot bị đổi cloze trong lúc sync ([R-FE-08] (b))
      final modifiedCloze = initial.copyWith(
        cloze: const {'text_before': 'A ', 'answer': 'vital role', 'text_after': '.'},
        dirty: true,
      );
      await wordsRepo.saveWord(modifiedCloze);

      // Mẻ sync gửi bản 'initial' lên remote và gọi markClean(initial)
      await wordsRepo.markClean(initial);

      // Do bản ghi trong repo hiện tại đã khác cloze, cờ dirty KHÔNG bị xóa
      final afterClozeClean = await wordsRepo.getWord('vital_role');
      expect(afterClozeClean!.dirty, isTrue);

      // Cập nhật lại exampleSentence
      final modifiedSentence = modifiedCloze.copyWith(
        exampleSentence: 'Updated sentence from another article.',
        dirty: true,
      );
      await wordsRepo.saveWord(modifiedSentence);

      await wordsRepo.markClean(initial);
      final afterSentenceClean = await wordsRepo.getWord('vital_role');
      expect(afterSentenceClean!.dirty, isTrue);
      expect(afterSentenceClean.exampleSentence, 'Updated sentence from another article.');

      // Khi markClean đúng bản mới nhất, dirty mới thành false
      await wordsRepo.markClean(afterSentenceClean);
      final finalClean = await wordsRepo.getWord('vital_role');
      expect(finalClean!.dirty, isFalse);
    });

    test('buildWordSavedPayload and buildWordUnsavedPayload schema (Contract 3.5 & 4)', () {
      final savedPayload = buildWordSavedPayload(
        lemmaKey: 'play a vital role in',
        kind: 'lexicon',
        from: WordSavedFrom.phraseRow,
      );
      expect(savedPayload, {
        'lemma_key': 'play a vital role in',
        'kind': 'lexicon',
        'from': 'phrase_row',
      });

      final unsavedPayload = buildWordUnsavedPayload(
        lemmaKey: 'play a vital role in',
      );
      expect(unsavedPayload, {
        'lemma_key': 'play a vital role in',
      });
    });
  });

  group('EventQueueRepository (FE-05 / AC-4)', () {
    test('enqueue, peekBatch, and remove', () async {
      expect(await queueRepo.count(), 0);

      final id1 = await queueRepo.enqueue(QueuedEvent(
        eventType: 'word_tapped',
        articleId: 'art_eating_well',
        sectionId: 'sec_ew_1',
        payload: const {'token_i': 5, 'result': 'phrase_plus_word'},
        clientTs: DateTime.utc(2026, 11, 13, 8, 15),
      ));

      final id2 = await queueRepo.enqueue(QueuedEvent(
        eventType: 'audio_played',
        articleId: 'art_eating_well',
        sectionId: 'sec_ew_1',
        payload: const {'source': 'item', 'speed': 0.75},
        clientTs: DateTime.utc(2026, 11, 13, 8, 16),
      ));

      expect(await queueRepo.count(), 2);
      expect(id1, isA<int>());
      expect(id2, isA<int>());

      // Peek batch
      final batch = await queueRepo.peekBatch(limit: 1);
      expect(batch.length, 1);
      expect(batch.first.id, id1);
      expect(batch.first.eventType, 'word_tapped');
      expect(batch.first.payload['speed'], isNull);

      // Remove batch item
      await queueRepo.remove([id1]);
      expect(await queueRepo.count(), 1);

      final remaining = await queueRepo.peekBatch();
      expect(remaining.length, 1);
      expect(remaining.first.id, id2);
      expect(remaining.first.eventType, 'audio_played');
      expect(remaining.first.payload['speed'], 0.75);
    });
  });
}

