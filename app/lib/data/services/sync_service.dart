import 'dart:async';
import 'package:flutter/foundation.dart';

import '../models/local_models.dart';
import '../repositories/local_storage_repository.dart';
import 'remote_store.dart';

/// Dịch vụ đồng bộ dữ liệu local-first lên Supabase:
/// - reading_history (upsert tiến trình dirty)
/// - user_saved_words (upsert từ dirty, delete từ soft-deleted)
/// - usage_events (insert theo lô khi đã có consent)
class SyncService {
  final RemoteStore remoteStore;
  final ReadingProgressRepository progressRepo;
  final SavedWordsRepository wordsRepo;
  final EventQueueRepository queueRepo;
  final bool Function()? hasConsent;
  final bool enabled;

  Future<void>? _runningFlush;

  SyncService({
    required this.remoteStore,
    required this.progressRepo,
    required this.wordsRepo,
    required this.queueRepo,
    this.hasConsent,
    this.enabled = true,
  });

  /// Đẩy dữ liệu dirty lên Supabase.
  /// Có cơ chế Mutex (re-entrancy guard) ngăn chạy chồng lấn dẫn đến gửi trùng event.
  Future<void> flush() {
    if (!enabled) return Future.value();
    if (_runningFlush != null) {
      return _runningFlush!;
    }
    _runningFlush = _doFlush().whenComplete(() {
      _runningFlush = null;
    });
    return _runningFlush!;
  }

  Future<void> _doFlush() async {
    final userId = remoteStore.currentUserId;
    if (userId == null) {
      debugPrint('[SyncService] Chưa có currentUser, bỏ qua đợt sync này.');
      return;
    }

    try {
      await _syncReadingProgress(userId);
    } catch (e) {
      debugPrint('[SyncService] Lỗi sync reading_progress: $e');
    }

    try {
      await _syncSavedWords(userId);
    } catch (e) {
      debugPrint('[SyncService] Lỗi sync saved_words: $e');
    }

    try {
      await _syncUsageEvents();
    } catch (e) {
      debugPrint('[SyncService] Lỗi sync usage_events: $e');
    }
  }

  Future<void> _syncReadingProgress(String userId) async {
    final allProgress = await progressRepo.getAllProgress();
    final dirtyItems = allProgress.where((p) => p.dirty).toList();
    if (dirtyItems.isEmpty) return;

    final rowsToSync = <Map<String, dynamic>>[];
    final progressToSync = <ReadingProgress>[];

    for (final p in dirtyItems) {
      final row = p.toRemoteRow(userId: userId);
      if (row != null) {
        rowsToSync.add(row);
        progressToSync.add(p);
      } else {
        debugPrint('[SyncService] Bỏ qua progress có article_id không phải UUID: ${p.articleId}');
      }
    }

    if (rowsToSync.isNotEmpty) {
      await remoteStore.upsertReadingHistory(rowsToSync);
      for (final p in progressToSync) {
        await progressRepo.markClean(p);
      }
    }
  }

  Future<void> _syncSavedWords(String userId) async {
    final allWords = await wordsRepo.getAllWords(includeDeleted: true);
    final dirtyWords = allWords.where((w) => w.dirty).toList();
    if (dirtyWords.isEmpty) return;

    final toUpsertRows = <Map<String, dynamic>>[];
    final wordsToMarkClean = <SavedWord>[];
    final wordsToDelete = <SavedWord>[];

    for (final w in dirtyWords) {
      if (w.deleted) {
        wordsToDelete.add(w);
      } else {
        final row = w.toRemoteRow(userId: userId);
        toUpsertRows.add(row);
        wordsToMarkClean.add(w);
      }
    }

    // 1. Upsert các từ mới hoặc được cập nhật
    if (toUpsertRows.isNotEmpty) {
      await remoteStore.upsertSavedWords(toUpsertRows);
      for (final w in wordsToMarkClean) {
        await wordsRepo.markClean(w);
      }
    }

    // 2. Delete các từ đã soft-delete trên Supabase và dọn sạch khỏi Hive
    for (final w in wordsToDelete) {
      await remoteStore.deleteSavedWord(userId: userId, lemmaKey: w.lemmaKey);
      await wordsRepo.permanentlyDelete(w.lemmaKey);
    }
  }

  Future<void> _syncUsageEvents() async {
    // CONTRACTS 3.5: Chỉ gửi khi đã có consent
    final consent = hasConsent?.call() ?? false;
    if (!consent) {
      return;
    }

    final batch = await queueRepo.peekBatch(limit: 50);
    if (batch.isEmpty) return;

    final rows = batch.map((e) => e.toRemoteRow()).toList();
    await remoteStore.insertEvents(rows);
    // Thành công mới xóa khỏi hàng đợi Hive
    await queueRepo.remove(batch.map((e) => e.id!).toList());
  }
}
