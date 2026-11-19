import 'package:hive_flutter/hive_flutter.dart';

const String readingProgressBoxName = 'reading_progress';
const String savedWordsBoxName = 'saved_words';
const String eventQueueBoxName = 'event_queue';
const String bundleCacheBoxName = 'bundle_cache';
const String articleCardsCacheBoxName = 'article_cards_cache';

/// Khởi tạo Hive và mở sẵn các box chính cho tầng local-first.
/// Nếu truyền [customPath] (thường dùng trong unit tests), dùng `Hive.init(customPath)`.
Future<void> initHive({String? customPath}) async {
  if (customPath != null) {
    Hive.init(customPath);
  } else {
    await Hive.initFlutter();
  }

  await Future.wait([
    Hive.openBox<Map>(readingProgressBoxName),
    Hive.openBox<Map>(savedWordsBoxName),
    Hive.openBox<Map>(eventQueueBoxName),
    Hive.openBox<Map>(bundleCacheBoxName),
    Hive.openBox<Map>(articleCardsCacheBoxName),
  ]);
}

/// Đóng toàn bộ các box Hive đang mở
Future<void> closeHive() async {
  await Hive.close();
}

