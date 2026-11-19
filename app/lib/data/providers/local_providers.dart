import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive/hive.dart';

import '../local/hive_boxes.dart';
import '../models/local_models.dart';
import '../repositories/local_storage_repository.dart';

final readingProgressBoxProvider = Provider<Box<Map>>((ref) {
  return Hive.box<Map>(readingProgressBoxName);
});

final savedWordsBoxProvider = Provider<Box<Map>>((ref) {
  return Hive.box<Map>(savedWordsBoxName);
});

final eventQueueBoxProvider = Provider<Box<Map>>((ref) {
  return Hive.box<Map>(eventQueueBoxName);
});

final bundleCacheBoxProvider = Provider<Box<Map>>((ref) {
  return Hive.box<Map>(bundleCacheBoxName);
});

final articleCardsCacheBoxProvider = Provider<Box<Map>>((ref) {
  return Hive.box<Map>(articleCardsCacheBoxName);
});

final readingProgressRepositoryProvider = Provider<ReadingProgressRepository>((ref) {
  try {
    if (Hive.isBoxOpen(readingProgressBoxName)) {
      final box = ref.watch(readingProgressBoxProvider);
      return HiveReadingProgressRepository(box);
    }
  } catch (e) {
    debugPrint('[local_providers] readingProgressBox chưa mở, fallback sang in-memory: $e');
  }
  return InMemoryReadingProgressRepository();
});

final savedWordsRepositoryProvider = Provider<SavedWordsRepository>((ref) {
  try {
    if (Hive.isBoxOpen(savedWordsBoxName)) {
      final box = ref.watch(savedWordsBoxProvider);
      return HiveSavedWordsRepository(box);
    }
  } catch (e) {
    debugPrint('[local_providers] savedWordsBox chưa mở, fallback sang in-memory: $e');
  }
  return InMemorySavedWordsRepository();
});

final eventQueueRepositoryProvider = Provider<EventQueueRepository>((ref) {
  try {
    if (Hive.isBoxOpen(eventQueueBoxName)) {
      final box = ref.watch(eventQueueBoxProvider);
      return HiveEventQueueRepository(box);
    }
  } catch (e) {
    debugPrint('[local_providers] eventQueueBox chưa mở, fallback sang in-memory: $e');
  }
  return InMemoryEventQueueRepository();
});

/// Ánh xạ articleId -> ReadingProgress dùng cho danh sách bài báo (FE-07b)
/// và Trang chủ / Lịch sử đọc (FE-07c). Gọi `ref.invalidate(progressByArticleProvider)`
/// sau khi quay lại từ màn đọc để cập nhật trạng thái tức thì.
final progressByArticleProvider =
    FutureProvider<Map<String, ReadingProgress>>((ref) async {
  final repo = ref.watch(readingProgressRepositoryProvider);
  final allProgress = await repo.getAllProgress();
  return {
    for (final p in allProgress) p.articleId: p,
  };
});

