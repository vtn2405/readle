import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:readle/core/config.dart';
import 'package:readle/data/local/hive_boxes.dart';
import 'package:readle/data/models/article_card.dart';
import 'package:readle/data/models/local_models.dart';
import 'package:readle/data/providers/repository_providers.dart';
import 'package:readle/data/providers/sync_providers.dart';
import 'package:readle/data/repositories/fixture_article_repository.dart';
import 'package:readle/data/repositories/local_storage_repository.dart';
import 'package:readle/data/repositories/supabase_article_repository.dart';
import 'package:readle/data/services/auth_service.dart';
import 'package:readle/data/services/sync_service.dart';

import '../helpers/fake_remote_store.dart';

void main() {
  late Directory tempDir;
  late Box<Map> progressBox;
  late Box<Map> wordsBox;
  late Box<Map> queueBox;
  late Box<Map> bundleCacheBox;
  late Box<Map> cardsCacheBox;

  late HiveReadingProgressRepository progressRepo;
  late HiveSavedWordsRepository wordsRepo;
  late HiveEventQueueRepository queueRepo;

  late FakeRemoteStore fakeRemoteStore;
  late bool originalSupabaseReady;

  const validUserUuid = '11111111-1111-1111-1111-111111111111';
  const validArticleUuid = '22222222-2222-2222-2222-222222222222';
  const validSectionUuid = '33333333-3333-3333-3333-333333333333';
  const validLexiconUuid = '44444444-4444-4444-4444-444444444444';

  setUp(() async {
    tempDir = Directory.systemTemp.createTempSync('supabase_sync_test_');
    Hive.init(tempDir.path);

    progressBox = await Hive.openBox<Map>(readingProgressBoxName);
    wordsBox = await Hive.openBox<Map>(savedWordsBoxName);
    queueBox = await Hive.openBox<Map>(eventQueueBoxName);
    bundleCacheBox = await Hive.openBox<Map>(bundleCacheBoxName);
    cardsCacheBox = await Hive.openBox<Map>(articleCardsCacheBoxName);

    progressRepo = HiveReadingProgressRepository(progressBox);
    wordsRepo = HiveSavedWordsRepository(wordsBox);
    queueRepo = HiveEventQueueRepository(queueBox);

    fakeRemoteStore = FakeRemoteStore(currentUserId: validUserUuid);
    originalSupabaseReady = AppConfig.supabaseReady;
  });

  tearDown(() async {
    AppConfig.supabaseReady = originalSupabaseReady;
    await Hive.close();
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  group('AuthService (AC-1)', () {
    test('initAuth signs in anonymously and ensures profile', () async {
      fakeRemoteStore.currentUserId = null;
      final authService = AuthService(fakeRemoteStore);

      final uid = await authService.initAuth();
      expect(uid, isNotNull);
      expect(fakeRemoteStore.ensuredProfiles, contains(uid));
    });

    test('initAuth handles network loss safely without throwing', () async {
      fakeRemoteStore.currentUserId = null;
      fakeRemoteStore.shouldThrowOnNetwork = true;
      final authService = AuthService(fakeRemoteStore);

      final uid = await authService.initAuth();
      expect(uid, isNull);
    });
  });

  group('SupabaseArticleRepository & Cache Offline (AC-2)', () {
    test('list() caches cards in Hive and returns cached cards when offline', () async {
      final repo = SupabaseArticleRepository(
        remoteStore: fakeRemoteStore,
        articleCardsCacheBox: cardsCacheBox,
        bundleCacheBox: bundleCacheBox,
      );

      fakeRemoteStore.cards.add(
        const ArticleCard(
          id: validArticleUuid,
          title: 'Cloud Eating Well',
          category: 'Health',
          cefrLevel: 'A2',
          sourceName: 'Cloud',
          wordCount: 100,
          sectionCount: 2,
          processingOrder: 1,
        ),
      );

      // 1. Lần đầu online: lấy từ RemoteStore và ghi vào cache
      final cardsOnline = await repo.list();
      expect(cardsOnline.length, 1);
      expect(cardsOnline.first.title, 'Cloud Eating Well');
      expect(cardsCacheBox.containsKey(validArticleUuid), isTrue);

      // 2. Mất mạng: vẫn đọc được từ Hive cache
      fakeRemoteStore.shouldThrowOnNetwork = true;
      final cardsOffline = await repo.list();
      expect(cardsOffline.length, 1);
      expect(cardsOffline.first.title, 'Cloud Eating Well');
    });

    test('get(id) caches bundle and falls back to offline cache', () async {
      final repo = SupabaseArticleRepository(
        remoteStore: fakeRemoteStore,
        bundleCacheBox: bundleCacheBox,
      );

      // Nạp fixture bundle vào fake store
      final fixtureFile = File('../fixtures/article_eating_well.json');
      final jsonStr = fixtureFile.existsSync()
          ? fixtureFile.readAsStringSync()
          : File('assets/fixtures/article_eating_well.json').readAsStringSync();
      final bundleMap = jsonDecode(jsonStr) as Map<String, dynamic>;

      fakeRemoteStore.bundles[validArticleUuid] = bundleMap;

      // 1. Online: tải về thành công và lưu cache
      final bundleOnline = await repo.get(validArticleUuid);
      expect(bundleOnline.article.id, 'art_eating_well');
      expect(bundleCacheBox.containsKey(validArticleUuid), isTrue);

      // 2. Offline: mất mạng vẫn mở được bài từ cache (đóng/mở box để Hive nạp lại từ đĩa với Map lồng nhau)
      fakeRemoteStore.shouldThrowOnNetwork = true;
      await bundleCacheBox.close();
      bundleCacheBox = await Hive.openBox<Map>(bundleCacheBoxName);
      final repoOffline = SupabaseArticleRepository(
        remoteStore: fakeRemoteStore,
        bundleCacheBox: bundleCacheBox,
      );

      final bundleOffline = await repoOffline.get(validArticleUuid);
      expect(bundleOffline.article.id, 'art_eating_well');
    });

    test('get(id) throws ArticleNotFoundException when bundle is null', () async {
      final repo = SupabaseArticleRepository(
        remoteStore: fakeRemoteStore,
        bundleCacheBox: bundleCacheBox,
      );

      expect(
        () => repo.get('non-existent-uuid'),
        throwsA(isA<ArticleNotFoundException>()),
      );
    });
  });

  group('SyncService - Reading Progress & UUID Sanitization (AC-3)', () {
    test('upserts valid UUID progress and marks clean; skips fixture id', () async {
      bool consentGiven = true;
      final syncService = SyncService(
        remoteStore: fakeRemoteStore,
        progressRepo: progressRepo,
        wordsRepo: wordsRepo,
        queueRepo: queueRepo,
        hasConsent: () => consentGiven,
      );

      // Bản ghi 1: UUID hợp lệ
      final validProgress = ReadingProgress(
        articleId: validArticleUuid,
        lastReadSectionId: validSectionUuid,
        lastSectionIndex: 1,
        maxIndexReached: 1,
        progressPercent: 100,
        completed: true,
        lastReadAt: DateTime.utc(2026, 11, 14, 10, 0),
        dirty: true,
      );
      await progressRepo.saveProgress(validProgress);

      // Bản ghi 2: id fixture cũ (art_eating_well) không phải UUID
      final fixtureProgress = ReadingProgress(
        articleId: 'art_eating_well',
        lastReadSectionId: 'sec_ew_1',
        lastSectionIndex: 0,
        maxIndexReached: 0,
        progressPercent: 50,
        completed: false,
        lastReadAt: DateTime.utc(2026, 11, 14, 10, 0),
        dirty: true,
      );
      await progressRepo.saveProgress(fixtureProgress);

      // Chạy flush()
      await syncService.flush();

      // Chỉ có bản ghi validArticleUuid được gửi lên Supabase
      expect(fakeRemoteStore.readingHistoryRows.length, 1);
      final remoteRow = fakeRemoteStore.readingHistoryRows.first;
      expect(remoteRow['user_id'], validUserUuid);
      expect(remoteRow['article_id'], validArticleUuid);
      expect(remoteRow['last_read_section_id'], validSectionUuid);
      // Không chứa cột nội bộ Hive
      expect(remoteRow.containsKey('dirty'), isFalse);
      expect(remoteRow.containsKey('max_index_reached'), isFalse);

      // Bản ghi hợp lệ được gỡ cờ dirty
      final updatedValid = progressRepo.getProgressSync(validArticleUuid);
      expect(updatedValid!.dirty, isFalse);

      // Bản ghi fixture vẫn được giữ nguyên trong Hive với dirty = true (không crash mẻ sync)
      final keptFixture = progressRepo.getProgressSync('art_eating_well');
      expect(keptFixture!.dirty, isTrue);
    });
  });

  group('SyncService - Saved Words & Soft Delete (AC-3)', () {
    test('upserts active words and permanently deletes soft-deleted words', () async {
      final syncService = SyncService(
        remoteStore: fakeRemoteStore,
        progressRepo: progressRepo,
        wordsRepo: wordsRepo,
        queueRepo: queueRepo,
      );

      // 1. Từ đang lưu hợp lệ
      final activeWord = SavedWord(
        id: 'local-id-1',
        lemmaKey: 'vital_role',
        lexiconEntryId: validLexiconUuid,
        entryType: 'collocation',
        displayText: 'vital role',
        vi: 'vai trò quan trọng',
        exampleSentence: 'Example sentence.',
        cloze: const {},
        sourceArticleId: validArticleUuid,
        savedAt: DateTime.utc(2026, 11, 14, 10, 5),
        dueDate: DateTime(2026, 11, 14),
        dirty: true,
      );
      await wordsRepo.saveWord(activeWord);

      // 2. Từ đã bị xóa (soft delete / tombstone)
      final deletedWord = SavedWord(
        id: 'local-id-2',
        lemmaKey: 'old_word',
        displayText: 'old word',
        vi: 'từ cũ',
        exampleSentence: '',
        cloze: const {},
        sourceArticleId: validArticleUuid,
        savedAt: DateTime.utc(2026, 11, 14, 9, 0),
        dueDate: DateTime(2026, 11, 14),
        dirty: true,
        deleted: true,
      );
      // Giả lập lưu trực tiếp tombstone vào box
      await wordsBox.put('old_word', deletedWord.toMap());

      await syncService.flush();

      // Từ active được upsert lên Supabase
      expect(fakeRemoteStore.savedWordsRows.length, 1);
      final wordRow = fakeRemoteStore.savedWordsRows.first;
      expect(wordRow['user_id'], validUserUuid);
      expect(wordRow['lemma_key'], 'vital_role');
      expect(wordRow['entry_type'], 'collocation');
      expect(wordRow.containsKey('id'), isFalse); // Không gửi id local
      expect(wordRow.containsKey('dirty'), isFalse);
      expect(wordRow.containsKey('deleted'), isFalse);

      // Từ active gỡ cờ dirty
      final savedActive = await wordsRepo.getWord('vital_role');
      expect(savedActive!.dirty, isFalse);

      // Từ soft-delete bị xóa hẳn khỏi Hive box
      expect(wordsBox.containsKey('old_word'), isFalse);
    });

    test('upserts word with fixture source_article_id setting remote column to null ([R-FE-09-pre])', () async {
      final syncService = SyncService(
        remoteStore: fakeRemoteStore,
        progressRepo: progressRepo,
        wordsRepo: wordsRepo,
        queueRepo: queueRepo,
      );

      final fixtureWord = SavedWord(
        id: 'local-fixture-1',
        lemmaKey: 'tend_to',
        displayText: 'tend to',
        vi: 'có xu hướng',
        exampleSentence: 'Example sentence.',
        cloze: const {},
        sourceArticleId: 'art_eating_well', // fixture id
        savedAt: DateTime.utc(2026, 11, 14, 10, 5),
        dueDate: DateTime(2026, 11, 14),
        dirty: true,
      );
      await wordsRepo.saveWord(fixtureWord);

      await syncService.flush();

      expect(fakeRemoteStore.savedWordsRows.length, 1);
      final wordRow = fakeRemoteStore.savedWordsRows.first;
      expect(wordRow['lemma_key'], 'tend_to');
      expect(wordRow['source_article_id'], isNull);

      final cleanWord = await wordsRepo.getWord('tend_to');
      expect(cleanWord!.dirty, isFalse);
    });
  });

  group('SyncService - Usage Events, Consent Gate & Mutex (AC-4)', () {
    test('skips events when consent is false; sends batch when consent is true', () async {
      bool consentGiven = false;
      final syncService = SyncService(
        remoteStore: fakeRemoteStore,
        progressRepo: progressRepo,
        wordsRepo: wordsRepo,
        queueRepo: queueRepo,
        hasConsent: () => consentGiven,
      );

      await queueRepo.enqueue(QueuedEvent(
        eventType: 'article_opened',
        articleId: validArticleUuid,
        payload: const {},
        clientTs: DateTime.utc(2026, 11, 14, 10, 10),
      ));

      // 1. Chưa có consent -> không gửi
      await syncService.flush();
      expect(fakeRemoteStore.usageEventsRows, isEmpty);
      expect(await queueRepo.count(), 1);

      // 2. Bật consent -> gửi thành công và xóa khỏi hàng đợi
      consentGiven = true;
      await syncService.flush();
      expect(fakeRemoteStore.usageEventsRows.length, 1);
      expect(fakeRemoteStore.usageEventsRows.first['event_type'], 'article_opened');
      expect(await queueRepo.count(), 0);
    });

    test('retains events in queue on network error without loss', () async {
      final syncService = SyncService(
        remoteStore: fakeRemoteStore,
        progressRepo: progressRepo,
        wordsRepo: wordsRepo,
        queueRepo: queueRepo,
        hasConsent: () => true,
      );

      await queueRepo.enqueue(QueuedEvent(
        eventType: 'word_tapped',
        articleId: validArticleUuid,
        sectionId: validSectionUuid,
        payload: const {'token_i': 5},
        clientTs: DateTime.utc(2026, 11, 14, 10, 15),
      ));

      fakeRemoteStore.shouldThrowOnNetwork = true;
      await syncService.flush();

      // Không mất event khi offline
      expect(fakeRemoteStore.usageEventsRows, isEmpty);
      expect(await queueRepo.count(), 1);

      // Khi có mạng lại -> gửi thành công
      fakeRemoteStore.shouldThrowOnNetwork = false;
      await syncService.flush();
      expect(fakeRemoteStore.usageEventsRows.length, 1);
      expect(await queueRepo.count(), 0);
    });

    test('re-entrancy guard (Mutex) prevents duplicate event batch sending', () async {
      final syncService = SyncService(
        remoteStore: fakeRemoteStore,
        progressRepo: progressRepo,
        wordsRepo: wordsRepo,
        queueRepo: queueRepo,
        hasConsent: () => true,
      );

      await queueRepo.enqueue(QueuedEvent(
        eventType: 'section_viewed',
        articleId: validArticleUuid,
        sectionId: validSectionUuid,
        payload: const {},
        clientTs: DateTime.utc(2026, 11, 14, 10, 20),
      ));

      // Gọi flush() 2 lần đồng thời
      final f1 = syncService.flush();
      final f2 = syncService.flush();
      await Future.wait([f1, f2]);

      // Sự kiện chỉ được chèn đúng 1 lần
      expect(fakeRemoteStore.usageEventsRows.length, 1);
      expect(await queueRepo.count(), 0);
    });
  });

  group('Supabase Initialization Guard & Safety', () {
    test('remoteStoreProvider returns _NoopRemoteStore safely when Supabase is not initialized', () {
      // Giả lập chưa khởi tạo Supabase thành công
      AppConfig.isSupabaseInitialized = false;

      final container = ProviderContainer();
      addTearDown(container.dispose);

      // Đọc remoteStoreProvider không được sập hoặc ném Exception
      final store = container.read(remoteStoreProvider);
      expect(store, isNotNull);
      expect(store.currentUserId, isNull);

      // articleRepositoryProvider fallback an toàn về FixtureArticleRepository
      final repo = container.read(articleRepositoryProvider);
      expect(repo, isA<FixtureArticleRepository>());
    });
  });
}
