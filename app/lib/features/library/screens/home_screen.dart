import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../data/models/article_card.dart';
import '../../../data/providers/local_providers.dart';
import '../../../data/providers/repository_providers.dart';
import '../../reader/providers/saved_words_provider.dart';
import '../open_article.dart';
import '../providers/library_providers.dart';
import '../widgets/category_style.dart';

/// Tab Trang chủ: khối "Đọc tiếp", danh sách ngang "Bài mới", và dòng 2 con số (ADR-020 & FE-07c).
/// Tuân thủ no-pressure UX: chỉ hiện đúng 2 con số ("Đã đọc X bài · Đã lưu Y từ") và vị trí "Đoạn x / n".
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final overviewAsync = ref.watch(libraryOverviewProvider);
    final savedWordsCount = ref.watch(savedWordsNotifierProvider).length;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Readle',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: SafeArea(
        child: overviewAsync.when(
          skipLoadingOnReload: true,
          skipLoadingOnRefresh: true,
          loading: () => Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Chào bạn, hôm nay muốn đọc gì?',
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Expanded(
                  child: Center(
                    child: CircularProgressIndicator(),
                  ),
                ),
              ],
            ),
          ),
          error: (err, _) => Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Chào bạn, hôm nay muốn đọc gì?',
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Expanded(
                  child: Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          'Chưa tải được bài, thử lại khi có mạng nhé.',
                          style: theme.textTheme.bodyMedium,
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 12),
                        TextButton(
                          onPressed: () => ref.invalidate(articleListProvider),
                          child: const Text('Thử lại'),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          data: (overview) {
            return SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Chào bạn, hôm nay muốn đọc gì?',
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 20),

                  // 1. Khối "Đọc tiếp" (ẩn hoàn toàn khi không có bài đang đọc dở)
                  if (overview.continueReading != null) ...[
                    _ContinueReadingCard(
                      item: overview.continueReading!,
                      onContinue: () => openArticle(
                        context,
                        ref,
                        overview.continueReading!.card.id,
                      ),
                    ),
                    const SizedBox(height: 24),
                  ],

                  // 2. Khối "Bài mới" + nút "Xem tất cả"
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Bài mới',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      TextButton(
                        onPressed: () => context.go('/news'),
                        child: const Text('Xem tất cả'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  if (overview.recentArticles.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 16.0),
                      child: Text(
                        'Chưa có bài viết nào.',
                        style: theme.textTheme.bodyMedium,
                      ),
                    )
                  else
                    SizedBox(
                      height: 176,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        itemCount: overview.recentArticles.length,
                        separatorBuilder: (context, _) =>
                            const SizedBox(width: 12),
                        itemBuilder: (context, index) {
                          final card = overview.recentArticles[index];
                          return _RecentArticleCard(
                            card: card,
                            onTap: () => openArticle(context, ref, card.id),
                          );
                        },
                      ),
                    ),

                  const SizedBox(height: 24),

                  // 3. Dòng 2 con số duy nhất: "Đã đọc X bài · Đã lưu Y từ" -> /history
                  Card(
                    clipBehavior: Clip.antiAlias,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: InkWell(
                      key: const ValueKey('home_stats_row'),
                      onTap: () async {
                        await context.push('/history');
                        if (context.mounted) {
                          ref.invalidate(progressByArticleProvider);
                        }
                      },
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 14,
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.history,
                              size: 20,
                              color: theme.textTheme.bodySmall?.color,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                'Đã đọc ${overview.completedCount} bài · Đã lưu $savedWordsCount từ',
                                style: theme.textTheme.bodyMedium?.copyWith(
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                            Icon(
                              Icons.arrow_forward_ios,
                              size: 14,
                              color: theme.textTheme.bodySmall?.color,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class _ContinueReadingCard extends StatelessWidget {
  final MatchedArticleProgress item;
  final VoidCallback onContinue;

  const _ContinueReadingCard({
    required this.item,
    required this.onContinue,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final style = categoryStyle(item.card.category, theme.brightness);
    final totalSections = math.max(1, item.card.sectionCount);
    final currentSection = math.max(
      1,
      math.min(item.progress.lastSectionIndex + 1, totalSections),
    );

    return Card(
      key: const ValueKey('continue_reading_card'),
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
      ),
      child: InkWell(
        onTap: onContinue,
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                height: 108,
                width: double.infinity,
                decoration: BoxDecoration(
                  color: style.bg,
                  borderRadius: BorderRadius.circular(12),
                ),
                alignment: Alignment.center,
                child: Icon(
                  style.icon,
                  size: 42,
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.75),
                ),
              ),
              const SizedBox(height: 12),
              Text(
                item.card.category,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                item.card.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Đoạn $currentSection / $totalSections',
                    style: theme.textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  FilledButton.icon(
                    onPressed: onContinue,
                    icon: const Icon(Icons.play_arrow_rounded, size: 18),
                    label: const Text('Đọc tiếp'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RecentArticleCard extends StatelessWidget {
  final ArticleCard card;
  final VoidCallback onTap;

  const _RecentArticleCard({
    required this.card,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final style = categoryStyle(card.category, theme.brightness);

    return SizedBox(
      width: 168,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Padding(
          padding: const EdgeInsets.all(4.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                height: 92,
                width: double.infinity,
                decoration: BoxDecoration(
                  color: style.bg,
                  borderRadius: BorderRadius.circular(14),
                ),
                alignment: Alignment.center,
                child: Icon(
                  style.icon,
                  size: 34,
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.75),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                card.category,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                card.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  height: 1.25,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
