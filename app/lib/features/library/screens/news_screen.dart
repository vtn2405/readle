import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/models/article_card.dart';
import '../../../data/models/local_models.dart';
import '../../../data/providers/local_providers.dart';
import '../../../data/providers/repository_providers.dart';
import '../open_article.dart';
import '../widgets/article_tile.dart';

/// Tab Bài báo: thẻ khối màu theo chủ đề + lọc chủ đề/cấp độ (ADR-020 mục 5 & FE-07b).
class NewsScreen extends ConsumerStatefulWidget {
  const NewsScreen({super.key});

  @override
  ConsumerState<NewsScreen> createState() => _NewsScreenState();
}

class _NewsScreenState extends ConsumerState<NewsScreen> {
  String? _selectedCategory;
  String? _selectedCefr;

  /// Trích danh sách chủ đề duy nhất theo đúng thứ tự xuất hiện trong danh sách bài.
  List<String> _extractCategories(List<ArticleCard> cards) {
    final seen = <String>{};
    final result = <String>[];
    for (final card in cards) {
      if (card.category.isNotEmpty && seen.add(card.category)) {
        result.add(card.category);
      }
    }
    return result;
  }

  /// Trích danh sách cấp độ CEFR thực sự có bài theo thứ tự A2, B1, B2.
  List<String> _extractCefrLevels(List<ArticleCard> cards) {
    final present = {for (final c in cards) c.cefrLevel};
    const orderedLevels = ['A2', 'B1', 'B2'];
    final result = <String>[
      for (final level in orderedLevels)
        if (present.contains(level)) level,
    ];
    for (final c in cards) {
      if (!result.contains(c.cefrLevel) && c.cefrLevel.isNotEmpty) {
        result.add(c.cefrLevel);
      }
    }
    return result;
  }

  Future<void> _openArticle(String articleId) =>
      openArticle(context, ref, articleId);

  @override
  Widget build(BuildContext context) {
    final articleListAsync = ref.watch(articleListProvider);
    final progressMap =
        ref.watch(progressByArticleProvider).valueOrNull ??
        const <String, ReadingProgress>{};

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Bài báo',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: SafeArea(
        child: articleListAsync.when(
          data: (cards) {
            if (cards.isEmpty) {
              return const Center(
                child: Text('Chưa có bài viết nào.'),
              );
            }

            final categories = _extractCategories(cards);
            final cefrLevels = _extractCefrLevels(cards);

            final filteredCards = cards.where((card) {
              final matchCategory =
                  _selectedCategory == null ||
                  card.category == _selectedCategory;
              final matchCefr =
                  _selectedCefr == null || card.cefrLevel == _selectedCefr;
              return matchCategory && matchCefr;
            }).toList();

            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Hàng 1: Lọc theo chủ đề
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
                  child: Row(
                    children: [
                      ChoiceChip(
                        label: const Text('Tất cả'),
                        selected: _selectedCategory == null,
                        onSelected: (_) {
                          setState(() => _selectedCategory = null);
                        },
                      ),
                      for (final category in categories) ...[
                        const SizedBox(width: 8),
                        ChoiceChip(
                          label: Text(category),
                          selected: _selectedCategory == category,
                          onSelected: (_) {
                            setState(() => _selectedCategory = category);
                          },
                        ),
                      ],
                    ],
                  ),
                ),

                // Hàng 2: Lọc theo cấp độ CEFR
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                  child: Row(
                    children: [
                      ChoiceChip(
                        label: const Text('Mọi cấp độ'),
                        selected: _selectedCefr == null,
                        onSelected: (_) {
                          setState(() => _selectedCefr = null);
                        },
                      ),
                      for (final level in cefrLevels) ...[
                        const SizedBox(width: 8),
                        ChoiceChip(
                          label: Text(level),
                          selected: _selectedCefr == level,
                          onSelected: (_) {
                            setState(() => _selectedCefr = level);
                          },
                        ),
                      ],
                    ],
                  ),
                ),

                // Danh sách bài báo hoặc thông báo rỗng khi lọc
                Expanded(
                  child: filteredCards.isEmpty
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(24.0),
                            child: Text(
                              'Chưa có bài phù hợp, thử chọn khác nhé.',
                              style: Theme.of(context).textTheme.bodyMedium,
                              textAlign: TextAlign.center,
                            ),
                          ),
                        )
                      : LayoutBuilder(
                          builder: (context, constraints) {
                            final isTwoColumns = constraints.maxWidth >= 600;
                            if (!isTwoColumns) {
                              return SingleChildScrollView(
                                padding: const EdgeInsets.fromLTRB(
                                  16,
                                  8,
                                  16,
                                  24,
                                ),
                                child: Column(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.stretch,
                                  children: [
                                    for (
                                      int i = 0;
                                      i < filteredCards.length;
                                      i++
                                    ) ...[
                                      if (i > 0) const SizedBox(height: 20),
                                      ArticleTile(
                                        card: filteredCards[i],
                                        progress:
                                            progressMap[filteredCards[i].id],
                                        onTap: () =>
                                            _openArticle(filteredCards[i].id),
                                      ),
                                    ],
                                  ],
                                ),
                              );
                            }

                            // Lưới 2 cột dùng Row + IntrinsicHeight để co giãn tự nhiên theo chữ
                            final rowCount = (filteredCards.length + 1) ~/ 2;
                            return SingleChildScrollView(
                              padding: const EdgeInsets.fromLTRB(
                                16,
                                8,
                                16,
                                24,
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  for (
                                    int rowIndex = 0;
                                    rowIndex < rowCount;
                                    rowIndex++
                                  ) ...[
                                    if (rowIndex > 0)
                                      const SizedBox(height: 20),
                                    Builder(
                                      builder: (context) {
                                        final leftCard =
                                            filteredCards[rowIndex * 2];
                                        final rightIndex = rowIndex * 2 + 1;
                                        final rightCard =
                                            rightIndex < filteredCards.length
                                            ? filteredCards[rightIndex]
                                            : null;

                                        return IntrinsicHeight(
                                          child: Row(
                                            crossAxisAlignment:
                                                CrossAxisAlignment.stretch,
                                            children: [
                                              Expanded(
                                                child: ArticleTile(
                                                  card: leftCard,
                                                  progress:
                                                      progressMap[leftCard.id],
                                                  onTap: () => _openArticle(
                                                    leftCard.id,
                                                  ),
                                                ),
                                              ),
                                              const SizedBox(width: 16),
                                              Expanded(
                                                child: rightCard != null
                                                    ? ArticleTile(
                                                        card: rightCard,
                                                        progress:
                                                            progressMap[
                                                              rightCard.id
                                                            ],
                                                        onTap: () =>
                                                            _openArticle(
                                                              rightCard.id,
                                                            ),
                                                      )
                                                    : const SizedBox.shrink(),
                                              ),
                                            ],
                                          ),
                                        );
                                      },
                                    ),
                                  ],
                                ],
                              ),
                            );
                          },
                        ),
                ),
              ],
            );
          },
          loading: () => const Center(
            child: CircularProgressIndicator(),
          ),
          error: (err, _) => Center(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Chưa tải được bài, thử lại khi có mạng nhé.',
                    style: Theme.of(context).textTheme.bodyMedium,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 12),
                  TextButton(
                    onPressed: () => ref.refresh(articleListProvider),
                    child: const Text('Thử lại'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
