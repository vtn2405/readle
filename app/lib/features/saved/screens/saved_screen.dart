import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../data/models/local_models.dart';
import '../../../data/providers/repository_providers.dart';
import '../../reader/providers/saved_words_provider.dart';
import '../providers/saved_tab_providers.dart';
import '../widgets/saved_word_tile.dart';

/// Tab Đã lưu (kho từ Cụm từ / Từ đơn theo ADR-020, ADR-019, FE-07d).
class SavedScreen extends ConsumerWidget {
  const SavedScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final selectedType = ref.watch(selectedSavedTypeProvider);
    final savedWordsAsync = ref.watch(savedWordsListProvider);
    final articleListAsync = ref.watch(articleListProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Đã lưu',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Khối đầu màn: Nút "Ôn tập từ vựng" (không hiển thị số thẻ)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: FilledButton.tonalIcon(
                onPressed: () => context.push('/review'),
                icon: const Icon(Icons.style_outlined),
                label: const Text('Ôn tập từ vựng'),
              ),
            ),

            // Bộ chọn Cụm từ / Từ đơn (SegmentedButton)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: SegmentedButton<String>(
                segments: const [
                  ButtonSegment<String>(
                    value: 'collocation',
                    label: Text('Cụm từ'),
                  ),
                  ButtonSegment<String>(
                    value: 'single_word',
                    label: Text('Từ đơn'),
                  ),
                ],
                selected: {selectedType},
                onSelectionChanged: (newSelection) {
                  ref.read(selectedSavedTypeProvider.notifier).state =
                      newSelection.first;
                },
              ),
            ),

            const SizedBox(height: 8),

            // Danh sách từ vựng theo nhóm bài viết
            Expanded(
              child: _buildBody(
                context: context,
                ref: ref,
                theme: theme,
                selectedType: selectedType,
                savedWordsAsync: savedWordsAsync,
                articleListAsync: articleListAsync,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBody({
    required BuildContext context,
    required WidgetRef ref,
    required ThemeData theme,
    required String selectedType,
    required AsyncValue<List<SavedWord>> savedWordsAsync,
    required AsyncValue<dynamic> articleListAsync,
  }) {
    // Nếu danh sách bài đang tải lần đầu -> hiện vòng xoay
    if (articleListAsync.isLoading && !articleListAsync.hasValue) {
      return const Center(child: CircularProgressIndicator());
    }

    // Map tiêu đề bài viết; nếu lỗi mạng thì fallback rỗng (các từ sẽ gộp vào "Bài khác", không hiện lỗi)
    final Map<String, String> articleTitles = {};
    if (articleListAsync.hasValue) {
      final cards = articleListAsync.value as List<dynamic>;
      for (final card in cards) {
        articleTitles[card.id as String] = card.title as String;
      }
    }

    return savedWordsAsync.when(
      skipLoadingOnReload: true,
      skipLoadingOnRefresh: true,
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (err, stack) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Text(
            'Chưa tải được danh sách từ đã lưu.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
        ),
      ),
      data: (words) {
        final groups = groupSavedWords(
          words: words,
          articleTitles: articleTitles,
          entryType: selectedType,
        );

        if (groups.isEmpty) {
          final emptyText = selectedType == 'collocation'
              ? 'Chưa có cụm từ nào. Khi đọc, chạm vào cụm được tô màu rồi bấm Lưu nhé.'
              : 'Chưa có từ đơn nào.';

          return Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32.0),
              child: Text(
                emptyText,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
            ),
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
          itemCount: groups.length,
          itemBuilder: (context, groupIndex) {
            final group = groups[groupIndex];
            return Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 4,
                      vertical: 8,
                    ),
                    child: Text(
                      group.title,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  for (final word in group.words)
                    SavedWordTile(
                      word: word,
                      onUnsave: () {
                        ref
                            .read(savedWordsNotifierProvider.notifier)
                            .unsaveWord(word.lemmaKey);
                      },
                    ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}
