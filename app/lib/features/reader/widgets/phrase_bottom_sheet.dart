import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/models/article_bundle.dart';
import '../models/tap_result.dart';
import '../providers/saved_words_provider.dart';
import '../services/audio_service.dart';
import 'entry_detail_block.dart';

class PhraseBottomSheet extends ConsumerWidget {
  final TapResult tapResult;
  final Map<String, LexiconEntry> lexiconById;
  final void Function(String text, String? audioUrl, {required double speed})
      onSpeakPhrase;
  final void Function(String text, {required double speed}) onSpeakWord;
  final void Function(Occurrence phrase)? onSavePhrase;
  final bool Function(Occurrence phrase)? isPhraseSaved;

  const PhraseBottomSheet({
    super.key,
    required this.tapResult,
    required this.lexiconById,
    required this.onSpeakPhrase,
    required this.onSpeakWord,
    this.onSavePhrase,
    this.isPhraseSaved,
  });

  String _formatPos(String pos) {
    switch (pos.toUpperCase()) {
      case 'NOUN':
        return '(n.)';
      case 'VERB':
        return '(v.)';
      case 'ADJ':
        return '(adj.)';
      case 'ADV':
        return '(adv.)';
      case 'PRON':
        return '(pron.)';
      default:
        return '';
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final speedMode = ref.watch(speedModeProvider);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Thanh kéo đỉnh sheet
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  decoration: BoxDecoration(
                    color: theme.dividerColor.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Danh sách các khối cụm (cụm dài trước)
              // Cụm đầu tiên: hiện đầy đủ 6 khối (isCompact = false)
              // Cụm thứ 2 trở đi: hiện khối gọn 1-3 + Lưu (isCompact = true)
              for (int i = 0; i < tapResult.phrases.length; i++) ...[
                if (i > 0) const Divider(height: 28, thickness: 0.5),
                _buildPhraseBlock(
                  context,
                  ref,
                  tapResult.phrases[i],
                  i > 0, // isCompact nếu là cụm thứ 2 trở đi
                  speedMode,
                ),
              ],

              // Dòng từ đơn ở cuối (nếu có showWordRow)
              if (tapResult.showWordRow) ...[
                const Divider(height: 28, thickness: 0.5),
                _buildWordRow(context, theme, speedMode),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPhraseBlock(
    BuildContext context,
    WidgetRef ref,
    Occurrence occ,
    bool isCompact,
    double speedMode,
  ) {
    final entry = lexiconById[occ.lexiconEntryId];
    if (entry == null) {
      return const SizedBox.shrink();
    }

    final savedWords = ref.watch(savedWordsNotifierProvider);
    final isSaved =
        (isPhraseSaved?.call(occ) ?? false) || savedWords.contains(entry.lemmaKey);

    return EntryDetailBlock(
      occurrence: occ,
      entry: entry,
      isCompact: isCompact,
      isSaved: isSaved,
      speedMode: speedMode,
      onSpeedModeChanged: (newSpeed) {
        ref.read(speedModeProvider.notifier).state = newSpeed;
      },
      onPlayAudio: (speed) {
        onSpeakPhrase(entry.canonicalForm, entry.audioUrl, speed: speed);
      },
      onSave: onSavePhrase != null ? () => onSavePhrase!(occ) : null,
    );
  }

  Widget _buildWordRow(
    BuildContext context,
    ThemeData theme,
    double speedMode,
  ) {
    // Nếu token trùng một mục từ single_word đã lưu trong lexicon
    final wordItem = tapResult.wordRowItem;
    final singleEntry =
        wordItem != null ? lexiconById[wordItem.lexiconEntryId] : null;

    final wordText =
        singleEntry?.canonicalForm ?? tapResult.token.lemma.toLowerCase();
    final posText = _formatPos(tapResult.token.pos);
    final ipaText = singleEntry?.ipa ?? tapResult.token.ipa;
    final viText = wordItem?.vi ?? tapResult.token.vi ?? '';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: theme.dividerColor.withValues(alpha: 0.08),
        ),
      ),
      child: Row(
        children: [
          // Từ đơn + POS
          Text(
            wordText,
            style: theme.textTheme.bodyMedium?.copyWith(
              fontWeight: FontWeight.bold,
              fontSize: 15,
            ),
          ),
          if (posText.isNotEmpty) ...[
            const SizedBox(width: 4),
            Text(
              posText,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.textTheme.bodySmall?.color?.withValues(alpha: 0.8),
                fontStyle: FontStyle.italic,
              ),
            ),
          ],
          if (ipaText != null && ipaText.isNotEmpty) ...[
            const SizedBox(width: 6),
            Text(
              ipaText,
              style: theme.textTheme.bodySmall?.copyWith(
                color:
                    theme.textTheme.bodySmall?.color?.withValues(alpha: 0.75),
                fontStyle: FontStyle.italic,
              ),
            ),
          ],
          const SizedBox(width: 8),

          // Nghĩa
          Expanded(
            child: Text(
              viText,
              style: theme.textTheme.bodyMedium?.copyWith(
                fontSize: 14,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.9),
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),

          // Nút loa
          ConstrainedBox(
            constraints: const BoxConstraints(
              minWidth: 44,
              minHeight: 44,
            ),
            child: InkWell(
              onTap: () => onSpeakWord(wordText, speed: speedMode),
              borderRadius: BorderRadius.circular(22),
              child: Center(
                child: Icon(
                  Icons.volume_up_outlined,
                  size: 20,
                  color: theme.colorScheme.primary,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
