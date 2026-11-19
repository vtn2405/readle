import 'package:flutter/foundation.dart';
import 'package:hive/hive.dart';

import '../models/local_models.dart';

abstract class ReadingProgressRepository {
  ReadingProgress? getProgressSync(String articleId);
  Future<ReadingProgress?> getProgress(String articleId);
  Future<void> saveProgress(ReadingProgress progress);
  Future<List<ReadingProgress>> getAllProgress();
  Future<void> markClean(ReadingProgress syncedProgress);
}

class HiveReadingProgressRepository implements ReadingProgressRepository {
  final Box<Map> _box;

  HiveReadingProgressRepository(this._box);

  @override
  ReadingProgress? getProgressSync(String articleId) {
    final raw = _box.get(articleId);
    if (raw == null) return null;
    return ReadingProgress.fromMap(raw);
  }

  @override
  Future<ReadingProgress?> getProgress(String articleId) async {
    return getProgressSync(articleId);
  }

  @override
  Future<void> saveProgress(ReadingProgress progress) async {
    await _box.put(progress.articleId, progress.toMap());
  }

  @override
  Future<List<ReadingProgress>> getAllProgress() async {
    final list = <ReadingProgress>[];
    for (final raw in _box.values) {
      list.add(ReadingProgress.fromMap(raw));
    }
    return list;
  }

  @override
  Future<void> markClean(ReadingProgress syncedProgress) async {
    final existing = getProgressSync(syncedProgress.articleId);
    // Chỉ gỡ dirty nếu bản ghi chưa bị thay đổi trong lúc đang sync
    if (existing != null && existing.lastReadAt == syncedProgress.lastReadAt) {
      await saveProgress(existing.copyWith(dirty: false));
    }
  }
}

class InMemoryReadingProgressRepository implements ReadingProgressRepository {
  final Map<String, ReadingProgress> _storage;

  InMemoryReadingProgressRepository([Map<String, ReadingProgress>? initialData])
      : _storage = initialData ?? {};

  @override
  ReadingProgress? getProgressSync(String articleId) => _storage[articleId];

  @override
  Future<ReadingProgress?> getProgress(String articleId) async => _storage[articleId];

  @override
  Future<void> saveProgress(ReadingProgress progress) async {
    _storage[progress.articleId] = progress;
  }

  @override
  Future<List<ReadingProgress>> getAllProgress() async => _storage.values.toList();

  @override
  Future<void> markClean(ReadingProgress syncedProgress) async {
    final existing = _storage[syncedProgress.articleId];
    if (existing != null && existing.lastReadAt == syncedProgress.lastReadAt) {
      _storage[syncedProgress.articleId] = existing.copyWith(dirty: false);
    }
  }
}

abstract class SavedWordsRepository {
  Future<SavedWord?> getWord(String lemmaKey);
  Future<void> saveWord(SavedWord word);
  Future<void> deleteWord(String lemmaKey);
  Future<void> permanentlyDelete(String lemmaKey);
  Future<void> markClean(SavedWord syncedWord);
  Future<List<SavedWord>> getAllWords({bool includeDeleted = false});
  Future<bool> isSaved(String lemmaKey);
}

class HiveSavedWordsRepository implements SavedWordsRepository {
  final Box<Map> _box;

  HiveSavedWordsRepository(this._box);

  @override
  Future<SavedWord?> getWord(String lemmaKey) async {
    final raw = _box.get(lemmaKey);
    if (raw == null) return null;
    return SavedWord.fromMap(raw);
  }

  @override
  Future<void> saveWord(SavedWord word) async {
    // Nếu từ từng bị soft-delete, lưu lại sẽ gỡ cờ deleted và đánh dirty = true
    final toSave = word.copyWith(
      deleted: false,
      dirty: true,
    );
    await _box.put(word.lemmaKey, toSave.toMap());
  }

  @override
  Future<void> deleteWord(String lemmaKey) async {
    // Soft-delete (Tombstone): giữ lại bản ghi với deleted: true, dirty: true
    // để SyncService ở FE-06 biết mà gửi yêu cầu delete() lên Supabase.
    final existing = await getWord(lemmaKey);
    if (existing != null) {
      final updated = existing.copyWith(
        deleted: true,
        dirty: true,
      );
      await _box.put(lemmaKey, updated.toMap());
    }
  }

  @override
  Future<void> permanentlyDelete(String lemmaKey) async {
    await _box.delete(lemmaKey);
  }

  bool _isSameContent(SavedWord a, SavedWord b) {
    return a.id == b.id &&
        a.lemmaKey == b.lemmaKey &&
        a.lexiconEntryId == b.lexiconEntryId &&
        a.entryType == b.entryType &&
        a.displayText == b.displayText &&
        a.vi == b.vi &&
        a.exampleSentence == b.exampleSentence &&
        mapEquals(a.cloze, b.cloze) &&
        a.sourceArticleId == b.sourceArticleId &&
        a.savedAt == b.savedAt &&
        a.isNew == b.isNew &&
        a.firstReviewedAt == b.firstReviewedAt &&
        a.reps == b.reps &&
        a.intervalDays == b.intervalDays &&
        a.ease == b.ease &&
        a.dueDate == b.dueDate &&
        a.deleted == b.deleted;
  }

  @override
  Future<void> markClean(SavedWord syncedWord) async {
    final existing = await getWord(syncedWord.lemmaKey);
    // [R-FE-06b]: Chỉ gỡ dirty nếu toàn bộ nội dung bản ghi chưa bị thay đổi trong lúc đang sync
    if (existing != null && _isSameContent(existing, syncedWord)) {
      await _box.put(syncedWord.lemmaKey, existing.copyWith(dirty: false).toMap());
    }
  }

  @override
  Future<List<SavedWord>> getAllWords({bool includeDeleted = false}) async {
    final list = <SavedWord>[];
    for (final raw in _box.values) {
      final word = SavedWord.fromMap(raw);
      if (includeDeleted || !word.deleted) {
        list.add(word);
      }
    }
    return list;
  }

  @override
  Future<bool> isSaved(String lemmaKey) async {
    final word = await getWord(lemmaKey);
    return word != null && !word.deleted;
  }
}

class InMemorySavedWordsRepository implements SavedWordsRepository {
  final Map<String, SavedWord> _storage;

  InMemorySavedWordsRepository([Map<String, SavedWord>? initialData])
      : _storage = initialData ?? {};

  @override
  Future<SavedWord?> getWord(String lemmaKey) async => _storage[lemmaKey];

  @override
  Future<void> saveWord(SavedWord word) async {
    _storage[word.lemmaKey] = word.copyWith(deleted: false, dirty: true);
  }

  @override
  Future<void> deleteWord(String lemmaKey) async {
    final existing = _storage[lemmaKey];
    if (existing != null) {
      _storage[lemmaKey] = existing.copyWith(deleted: true, dirty: true);
    }
  }

  @override
  Future<void> permanentlyDelete(String lemmaKey) async {
    _storage.remove(lemmaKey);
  }

  @override
  Future<void> markClean(SavedWord syncedWord) async {
    final existing = _storage[syncedWord.lemmaKey];
    if (existing != null && _isSameContent(existing, syncedWord)) {
      _storage[syncedWord.lemmaKey] = existing.copyWith(dirty: false);
    }
  }

  bool _isSameContent(SavedWord a, SavedWord b) {
    return a.id == b.id &&
        a.lemmaKey == b.lemmaKey &&
        a.lexiconEntryId == b.lexiconEntryId &&
        a.entryType == b.entryType &&
        a.displayText == b.displayText &&
        a.vi == b.vi &&
        a.exampleSentence == b.exampleSentence &&
        mapEquals(a.cloze, b.cloze) &&
        a.sourceArticleId == b.sourceArticleId &&
        a.savedAt == b.savedAt &&
        a.isNew == b.isNew &&
        a.firstReviewedAt == b.firstReviewedAt &&
        a.reps == b.reps &&
        a.intervalDays == b.intervalDays &&
        a.ease == b.ease &&
        a.dueDate == b.dueDate &&
        a.deleted == b.deleted;
  }

  @override
  Future<List<SavedWord>> getAllWords({bool includeDeleted = false}) async {
    return _storage.values.where((w) => includeDeleted || !w.deleted).toList();
  }

  @override
  Future<bool> isSaved(String lemmaKey) async {
    final word = _storage[lemmaKey];
    return word != null && !word.deleted;
  }
}

abstract class EventQueueRepository {
  Future<int> enqueue(QueuedEvent event);
  Future<List<QueuedEvent>> peekBatch({int limit = 50});
  Future<void> remove(List<int> ids);
  Future<int> count();
}

class HiveEventQueueRepository implements EventQueueRepository {
  final Box<Map> _box;

  HiveEventQueueRepository(this._box);

  @override
  Future<int> enqueue(QueuedEvent event) async {
    final autoId = await _box.add(event.toMap());
    return autoId;
  }

  @override
  Future<List<QueuedEvent>> peekBatch({int limit = 50}) async {
    final result = <QueuedEvent>[];
    int count = 0;
    for (final key in _box.keys) {
      if (count >= limit) break;
      if (key is int) {
        final raw = _box.get(key);
        if (raw != null) {
          result.add(QueuedEvent.fromMap(raw, id: key));
          count++;
        }
      }
    }
    return result;
  }

  @override
  Future<void> remove(List<int> ids) async {
    await _box.deleteAll(ids);
  }

  @override
  Future<int> count() async {
    return _box.length;
  }
}

class InMemoryEventQueueRepository implements EventQueueRepository {
  final Map<int, QueuedEvent> _storage = {};
  int _nextId = 0;

  @override
  Future<int> enqueue(QueuedEvent event) async {
    final id = _nextId++;
    _storage[id] = QueuedEvent(
      id: id,
      eventType: event.eventType,
      articleId: event.articleId,
      sectionId: event.sectionId,
      payload: event.payload,
      clientTs: event.clientTs,
    );
    return id;
  }

  @override
  Future<List<QueuedEvent>> peekBatch({int limit = 50}) async {
    return _storage.values.take(limit).toList();
  }

  @override
  Future<void> remove(List<int> ids) async {
    for (final id in ids) {
      _storage.remove(id);
    }
  }

  @override
  Future<int> count() async => _storage.length;
}
