import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/models/local_models.dart';
import '../../../data/providers/local_providers.dart';
import '../../reader/providers/saved_words_provider.dart';

/// Đại diện cho một nhóm từ vựng theo bài viết trên Tab Đã lưu.
@immutable
class SavedWordsGroup {
  final String groupKey;
  final String title;
  final List<SavedWord> words;

  const SavedWordsGroup({
    required this.groupKey,
    required this.title,
    required this.words,
  });
}

/// Khóa nhóm dùng chung cho các bài viết lạ hoặc không tìm thấy thông tin.
const String otherArticleGroupKey = '_other';
const String otherArticleTitle = 'Bài khác';

/// Hàm thuần nhóm và sắp xếp từ vựng đã lưu theo bài viết (ADR-019, ADR-020).
///
/// - Lọc theo [entryType] ('collocation' hoặc 'single_word').
/// - Bỏ qua các bản ghi [w.deleted == true].
/// - Các bài viết lạ/null hoặc không có trong [articleTitles] được gộp chung vào 1 nhóm duy nhất [otherArticleGroupKey].
/// - Các từ trong từng nhóm được sắp theo [savedAt] giảm dần.
/// - Các nhóm được sắp xếp theo thời gian [savedAt] mới nhất của nhóm giảm dần.
List<SavedWordsGroup> groupSavedWords({
  required List<SavedWord> words,
  required Map<String, String> articleTitles,
  required String entryType,
}) {
  final filtered = words.where((w) => !w.deleted && w.entryType == entryType).toList();
  if (filtered.isEmpty) return const [];

  final Map<String, List<SavedWord>> groupsMap = {};
  final Map<String, String> titlesMap = {};

  for (final word in filtered) {
    final rawId = word.sourceArticleId;
    final String key;
    final String title;

    if (rawId.isNotEmpty && articleTitles.containsKey(rawId)) {
      key = rawId;
      title = articleTitles[rawId]!;
    } else {
      key = otherArticleGroupKey;
      title = otherArticleTitle;
    }

    titlesMap[key] = title;
    groupsMap.putIfAbsent(key, () => []).add(word);
  }

  final result = <SavedWordsGroup>[];
  for (final entry in groupsMap.entries) {
    final list = entry.value;
    // Sắp xếp các từ trong từng nhóm theo thời gian lưu mới nhất lên đầu
    list.sort((a, b) => b.savedAt.compareTo(a.savedAt));
    result.add(
      SavedWordsGroup(
        groupKey: entry.key,
        title: titlesMap[entry.key] ?? otherArticleTitle,
        words: list,
      ),
    );
  }

  // Sắp xếp thứ tự các nhóm theo thời gian lưu mới nhất của nhóm (list.first.savedAt)
  result.sort((a, b) => b.words.first.savedAt.compareTo(a.words.first.savedAt));
  return result;
}

/// Provider danh sách từ vựng đã lưu từ repository.
/// Tự động nạp lại khi [savedWordsNotifierProvider] có thay đổi (lưu/bỏ lưu).
final savedWordsListProvider = FutureProvider<List<SavedWord>>((ref) async {
  ref.watch(savedWordsNotifierProvider);
  final repo = ref.watch(savedWordsRepositoryProvider);
  return repo.getAllWords(includeDeleted: false);
});

/// Loại từ đang được chọn trên Tab Đã lưu ('collocation' mặc định hoặc 'single_word').
final selectedSavedTypeProvider = StateProvider<String>((ref) => 'collocation');
