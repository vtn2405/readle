import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/models/article_card.dart';
import '../../../data/models/local_models.dart';
import '../../../data/providers/local_providers.dart';
import '../../../data/providers/repository_providers.dart';

/// Luật khớp tiến trình đọc (ADR-021 điểm 6):
/// Chỉ giữ các bản ghi tiến trình có `articleId` nằm trong tập `knownArticleIds`.
/// Bản ghi mồ côi (bài bị gỡ khỏi cloud) không hiện, không đếm, nhưng không xóa khỏi Hive.
/// Ở FE-16, `knownArticleIds` sẽ được mở rộng thêm tập id của `user_articles`.
List<ReadingProgress> filterMatchedProgress(
  Iterable<ReadingProgress> allProgress,
  Set<String> knownArticleIds,
) {
  return allProgress
      .where((p) => knownArticleIds.contains(p.articleId))
      .toList();
}

@immutable
class MatchedArticleProgress {
  final ArticleCard card;
  final ReadingProgress progress;

  const MatchedArticleProgress({
    required this.card,
    required this.progress,
  });
}

@immutable
class LibraryOverview {
  final MatchedArticleProgress? continueReading;
  final List<ArticleCard> recentArticles;
  final int completedCount;
  final List<MatchedArticleProgress> inProgressItems;
  final List<MatchedArticleProgress> completedItems;

  const LibraryOverview({
    required this.continueReading,
    required this.recentArticles,
    required this.completedCount,
    required this.inProgressItems,
    required this.completedItems,
  });
}

/// Dựng dữ liệu tổng hợp cho Trang chủ và Lịch sử đọc từ danh sách bài và tiến trình đọc.
LibraryOverview buildLibraryOverview({
  required List<ArticleCard> cards,
  required Iterable<ReadingProgress> allProgress,
  Set<String>? extraKnownArticleIds,
}) {
  final cardsById = {for (final c in cards) c.id: c};
  final knownArticleIds = <String>{
    ...cardsById.keys,
    ...?extraKnownArticleIds,
  };

  final matched = filterMatchedProgress(allProgress, knownArticleIds);

  final inProgressItems = <MatchedArticleProgress>[];
  final completedItems = <MatchedArticleProgress>[];

  for (final progress in matched) {
    final card = cardsById[progress.articleId];
    if (card == null) continue;
    final item = MatchedArticleProgress(card: card, progress: progress);
    if (progress.completed) {
      completedItems.add(item);
    } else {
      inProgressItems.add(item);
    }
  }

  inProgressItems.sort(
    (a, b) => b.progress.lastReadAt.compareTo(a.progress.lastReadAt),
  );
  completedItems.sort(
    (a, b) => b.progress.lastReadAt.compareTo(a.progress.lastReadAt),
  );

  final sortedRecent = List<ArticleCard>.of(cards)
    ..sort((a, b) => b.processingOrder.compareTo(a.processingOrder));
  final recentArticles = sortedRecent.take(5).toList();

  return LibraryOverview(
    continueReading: inProgressItems.isNotEmpty ? inProgressItems.first : null,
    recentArticles: recentArticles,
    completedCount: completedItems.length,
    inProgressItems: inProgressItems,
    completedItems: completedItems,
  );
}

/// Provider gộp danh sách bài báo và tiến trình đọc cho Trang chủ & Lịch sử đọc (FE-07c).
final libraryOverviewProvider = FutureProvider<LibraryOverview>((ref) async {
  final cards = await ref.watch(articleListProvider.future);
  final progressMap = await ref.watch(progressByArticleProvider.future);
  return buildLibraryOverview(
    cards: cards,
    allProgress: progressMap.values,
  );
});
