import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/models/article_bundle.dart';
import '../providers/saved_words_provider.dart';
import '../services/audio_service.dart';
import 'entry_detail_block.dart';

class ItemBottomSheet extends ConsumerWidget {
  final Occurrence occurrence;
  final LexiconEntry entry;
  final void Function({required double speed}) onSpeak;
  final VoidCallback? onSave;
  final bool isSaved;

  const ItemBottomSheet({
    super.key,
    required this.occurrence,
    required this.entry,
    required this.onSpeak,
    this.onSave,
    this.isSaved = false,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final speedMode = ref.watch(speedModeProvider);
    final savedWords = ref.watch(savedWordsNotifierProvider);
    final isItemSaved = isSaved || savedWords.contains(entry.lemmaKey);

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

              // Khối mục từ đầy đủ 6 khối (SPEC 3.6, ADR-010, ADR-015)
              EntryDetailBlock(
                occurrence: occurrence,
                entry: entry,
                isCompact: false,
                isSaved: isItemSaved,
                speedMode: speedMode,
                onSpeedModeChanged: (newSpeed) {
                  ref.read(speedModeProvider.notifier).state = newSpeed;
                },
                onPlayAudio: (speed) => onSpeak(speed: speed),
                onSave: onSave,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
